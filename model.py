import json, time, requests, uuid, os, datetime, random
import pandas as pd, numpy as np
from tqdm.notebook import tqdm
from pandas import json_normalize
import constraint, itertools

from utils import Cache
from equip import Equipment, Location, Building, Battery, _calc_battery_costs

# IC – installation costs / kWp and installation costs / kWh
# solar panel overproduction SPO = max{0, (building solar production - building consumption)}
# solar energy consumption SEC = min{building solar production, building consumption}
# solar panel underproduction SPU = max{0, (building consumption - building solar production)}
# grid buying price BP: price at which the respective energy provider is buying energy
# grid selling price SP: price at which the respective energy provider is selling energy
# city price CP: price at which the Genossenschaft is selling energy to the city # city_solar_energy_price
# max: Genossenschaft profit = (SPO * BP) + (SEC * CP) – IC - roof renting costs
# min: building energy cost = (SEC * CP) + (SPU * SP) + roof renting costs

def total_building_energy_costs(b, city_solar_energy_price=1, grid_selling_price=1.5):
    return b.total_solar_energy_consumption * city_solar_energy_price +\
           b.total_solar_energy_underproduction * grid_selling_price +\
           b.total_renting_costs

def _locations(combination, locations):
    return [locations[i] for i in combination if i in locations]    

def _update_building(building, components, solution):
    A, B, C, D, E = solution['A'], solution['B'], solution['C'], solution['D'], solution['E']
    locations, equipment, equipment_count, battery, battery_count = _locations(A, components['location']), components['equipment'][B], C, components['battery'][D], E
    for l in locations:
        l.equipment = []
    if equipment != None:
        equipment.pv_count = equipment_count
        locations[0].equipment = [equipment]
        if battery != None:
            battery.battery_count = battery_count
            equipment.battery = [battery]
        else:
            equipment.battery = []
    building.locations = locations
    building.updated()
    return building

class ConstraintSolver:
    def __init__(self, building, possible_components, cache_storage='./'):
        self.cached_solutions = Cache(storage=cache_storage)
        self.components = possible_components
        self.building = building
        self.locations_combinations = list(itertools.combinations(range(0, len(self.components['location'])+1), 
                                                                           len(self.components['location'])))
        self.solutions = []
        self.problem = constraint.Problem()
        self.problem.addVariable('A', self.locations_combinations) # locations involved
        self.problem.addVariable('B', range(1, len(self.components['equipment'])+1)) # equipment id
        self.problem.addVariable('D', range(1, len(self.components['battery'])+1)) # battery id
        self.problem.addVariable('C', range(1, 7)) # equipment count
        self.problem.addVariable('E', range(0, 7)) # battery count
        self.problem.addConstraint(self.equipment_square_constraint, "ABC")
        self.problem.addConstraint(self.battery_voltage_constraint, "BD")
        self.problem.addConstraint(self.battery_capacity_constraint, "ABCDE")        
        
    def equipment_square_constraint(self, A, B, C):
        locations, eq, eq_count = _locations(A, self.components['location']), self.components['equipment'][B], C
        total_square_available = sum([loc.size_m[0] * loc.size_m[1] * 10 ** 6 for loc in locations])
        return eq.pv_size_mm[0] * eq.pv_size_mm[1] * eq_count < total_square_available

    def battery_voltage_constraint(self, B, D):
        eq, bt = self.components['equipment'][B], self.components['battery'][D]
        return eq.pv_voltage == bt.battery_voltage

    def battery_capacity_constraint(self, A, B, C, D, E):
        bt, bt_count = self.components['battery'][D], E
        _, _total_energy_storage_needed = self.get_cached_solution(A, B, C, D, E)
        return (bt.battery_energy_Wh * bt.battery_discharge_factor * bt_count >= _total_energy_storage_needed)

    def get_cached_solution(self, A, B, C, D, E):
        def _calc():
            _update_building(self.building, self.components, dict(A=A, B=B, C=C, D=D, E=E))
            return total_building_energy_costs(self.building), self.building.get_total_energy_storage_needed()
        return self.cached_solutions.get_cached_solution((A, B, C), _calc)

    def calc_solution_costs(self, solution):
        A, B, C, D, E = solution['A'], solution['B'], solution['C'], solution['D'], solution['E']
        _total_building_energy_costs, _total_energy_storage_needed = self.get_cached_solution(A, B, C, D, E)
        loc, eq, eq_count, bt, bt_count = _locations(A, self.components['location']), self.components['equipment'][B], C, self.components['battery'][D], E
        bt.battery_count = bt_count
        return _total_building_energy_costs + _calc_battery_costs(bt) + len(loc)

    def get_solutions(self, recalc=False):
        if len(self.solutions) == 0 or recalc:
            self.solutions = self.problem.getSolutions()
            self.cached_solutions.save()
            print(f"solutions: {len(self.solutions)}, cahed: {len(self.cached_solutions.storage)}")
        return sorted(self.solutions, key=self.calc_solution_costs)
       