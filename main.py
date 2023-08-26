import json, time, uuid, os, sys, pickle
import pandas as pd, numpy as np
from ppretty import ppretty
from ast import literal_eval

import equip
from equip import Building, Equipment, Location, Battery
from model import ConstraintSolver, total_building_energy_costs, _update_building

base_dir = './'

if __name__ == "__main__":
    
    components = {}
    print(f'base_dir: {base_dir}')
    location = pd.read_csv(os.path.join(base_dir, 'location.csv'), sep=';', converters={'size_m': literal_eval})
    location.index = range(1, len(location)+1)
    components['location'] = location.to_dict(orient='index')
    del location
    
    equipment = pd.read_csv(os.path.join(base_dir, 'equipment.csv'), sep=';', converters={'pv_size_mm': literal_eval})
    equipment.index = range(1, len(equipment)+1)
    components['equipment'] = equipment.to_dict(orient='index')
    del equipment
    
    battery = pd.read_csv(os.path.join(base_dir, 'battery.csv'), sep=';')
    battery.index = range(1, len(battery)+1)
    components['battery'] = battery.to_dict(orient='index')
    del battery
    
    buildings = []
    if os.path.exists(os.path.join(base_dir, 'building.pickle')): 
        with open(os.path.join(base_dir, 'building.pickle'), 'rb') as fp:
            buildings = pickle.load(fp)
    
    print(f"locations: {len(components['location'])}, equipment: {len(components['equipment'])}, batteries: {len(components['battery'])}, buildings: {len(buildings)}")    
    
    building = buildings[0]
    building._erase_equipment()

    print('solving...')
    start_time = time.time()
    solver = ConstraintSolver(building, components)
    solutions = solver.get_solutions()   
    print(f'solving time: {time.time() - start_time}')
    
    print(f'top-5 solutions:')
    for s in solutions[:5]:
        print(s, 'cost:', solver.calc_solution_costs(s))

    print('''A - location, B - equipment, C - equipment count, D - battery, E - battery count''')
    #print()
    print(f"optimal solution: {solutions[0]}")
    
    #solutions[0]['C'] = 1
    
    _update_building(building, components, solutions[0])
    print(f"total_production: {building.production['production'].sum():.1f}")
    print(f"total_consumption: {building.consumption['consumption'].sum():.1f}")
    print(f"total_solar_energy_underproduction: {building.total_solar_energy_underproduction:.1f}")
    print(f"total_building_energy_costs: {total_building_energy_costs(building):.1f}")
    print(f"locations_involved: {len(building._locations)}")
    print(f"total_renting_costs: {building.total_renting_costs:.1f}")
    print(f"total_battery_costs: {building.total_battery_costs:.1f}")
       
    with open(os.path.join(base_dir, 'building.pickle'), 'wb') as fp:
        pickle.dump(buildings, fp)
    
    #print()
    #print('locations', ppretty(building._locations, show_protected=False, show_static=True, show_properties=True))
    #print('batteries', ppretty(building._battery, show_protected=False, show_static=True, show_properties=True))
    
    #buildings = [buildings[0]]
    
    #print(type(location['size_m'].iloc[0]))

    #sys.exit(0)

    '''
    print(components)
    bt1 = Battery.copy()
    bt1['uuid'] = 1
    bt2 = Battery.copy()
    bt2['uuid'] = 2
    bt2['battery_capacity_Ah'] = 60
    bt2['battery_energy_Wh'] = 2880
    bt2['battery_voltage'] = 48
    bt2['battery_discharge_factor'] = 0.6
    bt2['battery_price_per_Wh'] = 3.738

    eq1 = Equipment.copy()
    eq1['uuid'] = 1
    eq2 = Equipment.copy()
    eq2['uuid'] = 2
    eq2['pv_size_mm'] = (eq2['pv_size_mm'][0] * 3, eq2['pv_size_mm'][1] * 3)

    loc1 = Location.copy()
    loc1['uuid'] = 1
    loc2 = Location.copy()
    loc2['uuid'] = 2
    loc2['price_per_sqm'] = 2

    eq_ = eq1.copy()
    loc_ = loc1.copy()
    loc_['_equipment'] = [eq_]
    building = Building(locations=[loc_])
    print(f"total_consumption: {building.consumption['consumption'].sum():.1f}")

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
    
    d = pd.DataFrame.from_dict(components['location'], orient='index')
    #d.index = d.index + 1
    d.to_csv('location.csv', index=False, sep=';')
    d = pd.DataFrame.from_dict(components['equipment'], orient='index')
    #d.index = d.index + 1
    d.to_csv('equipment.csv', index=False, sep=';')
    d = pd.DataFrame.from_dict(components['battery'], orient='index')
    #d.index = d.index + 1
    d.to_csv('battery.csv', index=False, sep=';')
    sys.exit()
    
    
    eq_ = components['equipment'][1].copy()
    loc_ = components['location'][1].copy()
    loc_['_equipment'] = [eq_]
    building = Building(locations=[loc_])
    print(f"total_consumption: {building.consumption['consumption'].sum():.1f}")   
    buildings.append(building)


    '''
 
    
    sys.exit()