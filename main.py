import json, time, uuid, os, sys
import pandas as pd, numpy as np

#from utils import Cache
import equip
from equip import Equipment, Location, Building, Battery, _calc_battery_costs
from model import ConstraintSolver, total_building_energy_costs, _update_building

if __name__ == "__main__":
    bt1 = Battery()
    bt2 = Battery()
    bt2.battery_capacity_Ah = 60
    bt2.battery_energy_Wh = 2880
    bt2.battery_voltage = 48
    bt2.battery_discharge_factor = 0.6
    bt2.battery_price_per_Wh = 3.738

    eq1 = Equipment()
    eq2 = Equipment()
    eq2.pv_size_mm = (eq2.pv_size_mm[0] * 3, eq2.pv_size_mm[1] * 3)

    loc1 = Location()
    loc1.equipment = [eq1]
    loc2 = Location()
    loc2.equipment = [eq2]

    building = Building()
    building.locations = [loc1, loc2]

    #print(f"total_production: {building.production['production'].sum():.1f}")
    #print(f"total_consumption: {building.consumption['consumption'].sum():.1f}")
    #print(f"total_solar_energy_consumption: {building.total_solar_energy_consumption:.1f}")
    #print(f"total_solar_energy_underproduction: {building.total_solar_energy_underproduction:.1f}")
    #print(f"total_renting_costs: {building.total_renting_costs:.1f}")

    components = {
        'location' : {
                        1: loc1,
                        2: loc2,
        },
        'equipment' : {
                        1: eq1,
                        2: eq2,
        },
        'battery' : {
                        1: bt1,
                        2: bt2,
        },
    }
    
    #sys.exit()
    start_time = time.time()
    solver = ConstraintSolver(building, components)
    solutions = solver.get_solutions()
    print(f'solving time: {time.time() - start_time}')
    print(f'top-5 solutions:')
    for s in solutions[:5]:
        print(s, 'cost:', solver.calc_solution_costs(s))

    print()
    print(f"optimal solution: {solutions[0]}")
    _update_building(building, components, solutions[0])
    
    print(f"total_production: {building.production['production'].sum():.1f}")
    print(f"total_solar_energy_underproduction: {building.total_solar_energy_underproduction:.1f}")
    print(f"total_building_energy_costs: {total_building_energy_costs(building):.1f}")
    print(f"total_renting_costs: {building.total_renting_costs:.1f}")
    print(f"total_battery_costs: {building.total_battery_costs:.1f}")