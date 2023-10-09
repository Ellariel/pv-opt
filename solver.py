import time, os, copy, pickle#, datetime, random, requests, uuid, json, 
import pandas as pd, numpy as np
#from tqdm.notebook import tqdm
#from pandas import json_normalize
import constraint, itertools
from uuid import uuid4

from utils import Cache, is_empty
#from equip import Building, Equipment, Location, Battery, _calc_battery_costs

# IC – installation costs / kWp and installation costs / kWh
# solar panel overproduction SPO = max{0, (building solar production - building consumption)}
# solar energy consumption SEC = min{building solar production, building consumption}
# solar panel underproduction SPU = max{0, (building consumption - building solar production)}
# grid buying price BP: price at which the respective energy provider is buying energy
# grid selling price SP: price at which the respective energy provider is selling energy
# city price CP: price at which the Genossenschaft is selling energy to the city # city_solar_energy_price
# max: Genossenschaft profit = (SPO * BP) + (SEC * CP) – IC - roof renting costs
# min: building energy cost = (SEC * CP) + (SPU * SP) + roof renting costs

def total_building_energy_costs(b, city_solar_energy_price=1.0, grid_selling_price=1.5, **kwargs):
    #print(f'city_solar_energy_price: {city_solar_energy_price}, grid_selling_price: {grid_selling_price}')
    return b.total_solar_energy_consumption * city_solar_energy_price +\
           b.total_solar_energy_underproduction * grid_selling_price +\
           b.total_renting_costs

Solution = dict(
        uuid = None,
        selected = 0,
        timestamp = 1692989661.8293242,
        building = 1,
        solution = {},
        stored = '5c75deb8d33045cd86bb3ee9b7e98c25'
)

def _locations(combination, locations):
    return [locations[i] for i in combination if i in locations]    

def _update_building(building, components, solution):
    A, B, C, D, E = solution['A'], solution['B'], solution['C'], solution['D'], solution['E']
    loc, eq, eq_count, bt, bt_count = copy.deepcopy(_locations(A, components['location'])), components['equipment'][B], C, copy.deepcopy(components['battery'][D]), E
    eq_square_needed = eq['pv_size_mm'][0] * eq['pv_size_mm'][1]
    for l in loc:
        l['_equipment'] = []
        if eq_count > 0:
            total_square_available = l['size_m'][0] * l['size_m'][1] * 10 ** 6
            _eq = eq.copy()
            _eq['pv_count'] = min(np.ceil(total_square_available / eq_square_needed), eq_count)
            eq_count -= _eq['pv_count']
            l['_equipment'] = [_eq]   
    bt['battery_count'] = bt_count
    building._battery = [bt]
    building._locations = loc
    building.updated()
    return building

class ConstraintSolver:
    def __init__(self, building, possible_components, cache_storage='./', config={}):
        self.cached_solutions = Cache(storage=cache_storage)
        self.components = possible_components
        self.building = building
        self.config = config
        
        _filtered_locations = [k for k, v in self.components['location'].items() if v['building'] == self.building.uuid]
        #self.locations_combinations = list(itertools.permutations(range(0, len(self.components['location'])+1), 
        #                                                                   len(self.components['location'])))
        #self.locations_combinations = list(set([tuple([i for i in j if i > 0]) for j in self.locations_combinations]))
        self.locations_combinations = list(itertools.permutations(range(0, len(_filtered_locations)+1), 
                                                                           len(_filtered_locations)))
        self.locations_combinations = list(set([tuple([_filtered_locations[i-1] for i in j if i > 0]) for j in self.locations_combinations]))
        #print(self.locations_combinations)
        
        self.solutions = []
        self.problem = constraint.Problem()
        #print(self.locations_combinations)
        self.problem.addVariable('A', self.locations_combinations) # locations involved
        self.problem.addVariable('B', list(self.components['equipment'].keys())) #range(1, len(self.components['equipment'])+1)) # equipment id
        self.problem.addVariable('D', list(self.components['battery'].keys())) #range(1, len(self.components['battery'])+1)) # battery id
        self.problem.addVariable('C', range(1, self.config['max_equipment_count'])) # equipment count
        self.problem.addVariable('E', range(0, self.config['max_equipment_count'])) # battery count
        self.problem.addConstraint(self.equipment_square_constraint, "ABC")
        #self.problem.addConstraint(self.battery_voltage_constraint, "BD")
        self.problem.addConstraint(self.battery_capacity_constraint, "ABCDE")        
        
    def equipment_square_constraint(self, A, B, C):
        loc, eq, eq_count = _locations(A, self.components['location']), self.components['equipment'][B], C
        max_count = sum([min(np.floor(l['size_m'][0] * 1000 / eq['pv_size_mm'][0]), np.floor(l['size_m'][1] * 1000 / eq['pv_size_mm'][1])) for l in loc])
        #print(max_count, eq_count)
        return eq_count <= max_count        
        #total_square_available = sum([l['size_m'][0] * l['size_m'][1] * 10 ** 6 for l in loc])
        #return eq['pv_size_mm'][0] * eq['pv_size_mm'][1] * eq_count < total_square_available
        

    def battery_voltage_constraint(self, B, D):
        eq, bt = self.components['equipment'][B], self.components['battery'][D]
        return eq['pv_voltage'] == bt['battery_voltage']

    def battery_capacity_constraint(self, A, B, C, D, E):
        bt, bt_count = self.components['battery'][D], E
        _, _total_energy_storage_needed = self.get_cached_solution(A, B, C, D, E)
        return (bt['battery_energy_Wh'] * bt['battery_discharge_factor'] * bt_count >= _total_energy_storage_needed)

    def get_cached_solution(self, A, B, C, D, E):
        def _calc():
            _update_building(self.building, self.components, dict(A=A, B=B, C=C, D=D, E=E))
            return total_building_energy_costs(self.building, **self.config), self.building.get_total_energy_storage_needed()
        return self.cached_solutions.get_cached_solution((A, B, C), _calc)

    def calc_solution_costs(self, solution):
        A, B, C, D, E = solution['A'], solution['B'], solution['C'], solution['D'], solution['E']
        _total_building_energy_costs, _total_energy_storage_needed = self.get_cached_solution(A, B, C, D, E)
        loc, bt, bt_count = _locations(A, self.components['location']), self.components['battery'][D], E
        return _total_building_energy_costs + len(loc) + (bt['battery_energy_Wh'] * bt['battery_price_per_Wh'] * bt_count)

    def get_solutions(self, always_recalc=False):
        if len(self.solutions) == 0 or always_recalc:
            self.solutions = self.problem.getSolutions()
            self.cached_solutions.save()
            print(f"solutions: {len(self.solutions)}, cahed: {len(self.cached_solutions.storage)}")
        return sorted(self.solutions, key=self.calc_solution_costs)

    def from_storage(self, data_key, storage='./'):
        file_name = os.path.join(storage, data_key)+'.pickle'
        if os.path.exists(file_name):
            with open(file_name, 'rb') as fp:
                return pickle.load(fp)        

    def to_storage(self, data_key, data, storage='./'):
        file_name = os.path.join(storage, data_key)+'.pickle'
        with open(file_name, 'wb') as fp:
            pickle.dump(data, fp)
            
    def save_solution(self, solution_data, building, solution, selected=False, timestamp=None, uuid=None, storage='./'):
        data_key = Solution.copy()
        data_key['uuid'] = uuid if uuid != None else uuid4().hex
        data_key['selected'] = 1 if selected else 0
        data_key['stored'] = uuid4().hex
        data_key['solution'] = str(solution)
        data_key['building'] = building.uuid
        data_key['timestamp'] = timestamp if timestamp != None else time.time()
        self.to_storage(data_key['stored'], building, storage=storage)
        return pd.concat([solution_data, pd.DataFrame.from_dict({0: data_key}, orient='index')], ignore_index=True)
    
    def load_solution(self, solution_data, building, selected_only=False, timestamp=None, uuid=None, storage='./'):
        query = f"`building` == {building.uuid}"
        query += f" & `uuid` == {uuid}" if uuid != None else ''
        query += f" & `timestamp` == {timestamp}" if timestamp != None else ''
        query += f" & `selected` == 1" if selected_only else ''
        filtered = solution_data.query(query)
        if not is_empty(filtered):
            filtered = filtered.sort_values(by=['selected', 'timestamp'], ascending=False)
            return filtered.iloc[0]['solution'], self.from_storage(filtered.iloc[0]['stored'], storage=storage)