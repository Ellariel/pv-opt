import json, time, uuid, os, sys, pickle
import pandas as pd, numpy as np
from ppretty import ppretty
from ast import literal_eval

import equip
from equip import Building, Equipment, Location, Battery
from solver import ConstraintSolver, total_building_energy_costs, _update_building

base_dir = './'
consumption_dir = os.path.join(base_dir, 'consumption')
production_dir = os.path.join(base_dir, 'production')
solution_dir = os.path.join(base_dir, 'solution')
os.makedirs(consumption_dir, exist_ok=True)
os.makedirs(production_dir, exist_ok=True)
os.makedirs(solution_dir, exist_ok=True)

top_limit = 5

def print_building(building):
    print(f'building {building.uuid}:')
    print(f" total_production: {building.production['production'].sum():.1f}")
    print(f" total_consumption: {building.consumption['consumption'].sum():.1f}")
    print(f" total_solar_energy_underproduction: {building.total_solar_energy_underproduction:.1f}")
    print(f" total_building_energy_costs: {total_building_energy_costs(building):.1f}")
    print(f" locations_involved: {len(building._locations)}")
    print(f" total_renting_costs: {building.total_renting_costs:.1f}")
    print(f" equipment_units_used: {sum([eq['pv_count'] for loc in building._locations for eq in loc['_equipment']])}")
    print(f" total_equipment_costs: {building.total_equipment_costs:.1f}")
    print(f" baterry_units_used: {sum([bt['battery_count'] for bt in building._battery])}")
    print(f" total_battery_costs: {building.total_battery_costs:.1f}")

if __name__ == "__main__":
        
    components = {}
    print(f'base_dir: {base_dir}')
    location_data = pd.read_csv(os.path.join(base_dir, 'location.csv'), sep=';', converters={'size_m': literal_eval})
    location_data.index = range(1, len(location_data)+1)
    components['location'] = location_data.to_dict(orient='index')

    equipment_data = pd.read_csv(os.path.join(base_dir, 'equipment.csv'), sep=';', converters={'pv_size_mm': literal_eval})
    equipment_data.index = range(1, len(equipment_data)+1)
    components['equipment'] = equipment_data.to_dict(orient='index')
    del equipment_data
    
    battery_data = pd.read_csv(os.path.join(base_dir, 'battery.csv'), sep=';')
    battery_data.index = range(1, len(battery_data)+1)
    components['battery'] = battery_data.to_dict(orient='index')
    del battery_data
    
    building_data = pd.read_csv(os.path.join(base_dir, 'building.csv'), sep=';')
    building_data.index = range(1, len(building_data)+1)
    
    consumption_data = pd.read_csv(os.path.join(base_dir, 'consumption.csv'), sep=';')
    consumption_data.index = range(1, len(consumption_data)+1)
    
    production_data = pd.read_csv(os.path.join(base_dir, 'production.csv'), sep=';')
    production_data.index = range(1, len(production_data)+1)
    
    solution_data = pd.read_csv(os.path.join(base_dir, 'solution.csv'), sep=';', converters={'solution': literal_eval})
    solution_data.index = range(1, len(solution_data)+1)  
    print('data loading:')  
    print(f" locations: {len(components['location'])}, equipment: {len(components['equipment'])}, batteries: {len(components['battery'])}")
    print(f" buildings: {len(building_data)}, production: {len(production_data)}, consumption: {len(consumption_data)}") 
    print(f" stored solutions: {len(solution_data)}")

    buildings = []
    for idx, item in building_data.iterrows():
        b = Building(**item.to_dict())
        b.load_production(production_data, storage=production_dir)
        b.load_consumption(consumption_data, storage=consumption_dir)
        for idx, item in location_data[location_data['building'] == b.uuid].iterrows():
            loc = Location.copy()
            loc.update(item.to_dict())
            b._locations.append(loc)
        b.updated(update_production=False)
        buildings.append(b)

    for building in buildings:
        print_building(building)
        building._erase_equipment()
        print('solving...')
        start_time = time.time()
        solver = ConstraintSolver(building, components)
        solutions = solver.get_solutions()   
        print(f' solving time: {time.time() - start_time}')
        solutions = solutions[:top_limit]
        solutions.reverse()
    
        print(f' top-5 solutions (reversed):')
        print('  A - location, B - equipment, C - equipment count, D - battery, E - battery count')
        for i, s in enumerate(solutions):
            if i == top_limit-1:
                print(f"  optimal: {s} cost: {solver.calc_solution_costs(s):.3f}")
                _update_building(building, components, solutions[0])
                solution_data = solver.save_solution(solution_data, building, solutions[0], storage=solution_dir)
                print_building(building)
            else:
                print(f'  {s} cost: {solver.calc_solution_costs(s):.3f}')            
    
    solution_data.to_csv(os.path.join(base_dir, 'solution.csv'), index=False, sep=';')  
    
    
    
    
    
    #print(solution_data)
    #solution, building_solved = solver.load_solution(solution_data, building, storage=solution_dir)
    #print(solution)
    
       
    #with open(os.path.join(base_dir, 'building.pickle'), 'wb') as fp:
    #    pickle.dump(buildings, fp)
    
    #print()
    #print('locations', ppretty(building._locations, show_protected=False, show_static=True, show_properties=True))
    #print('batteries', ppretty(building._battery, show_protected=False, show_static=True, show_properties=True))
    
    #buildings = [buildings[0]]
    
    #print(type(location['size_m'].iloc[0]))

    #sys.exit(0)
    
            



    #sys.exit()
    #buildings = []
    #if os.path.exists(os.path.join(base_dir, 'building.pickle')): 
    #    with open(os.path.join(base_dir, 'building.pickle'), 'rb') as fp:
    #        buildings = pickle.load(fp)
    
       
    
    #
    #building.uuid = 1
    
    #production = building.save_production(production, building=1, storage=production_dir)
    #production.to_csv(os.path.join(base_dir, 'production.csv'), index=False, sep=';')  
    #print(production)
    #p = building.load_production(production, storage=production_dir)
    #print(p)
    
    #consumption = building.save_consumption(consumption, building=1, storage=consumption_dir)
    #consumption.to_csv(os.path.join(base_dir, 'consumption.csv'), index=False, sep=';')  
    #print(consumption)
    #c = building.load_consumption(consumption, storage=consumption_dir)
    #print(c)
    
    #sys.exit()

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