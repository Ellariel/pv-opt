import time, os, sys, glob#, pickle, json, uuid
import pandas as pd, numpy as np
from humanfriendly import format_timespan

#from ppretty import ppretty
from ast import literal_eval
from operator import itemgetter

import equip
#from equip import Building, Equipment, Location, Battery
from utils import save_pickle, load_pickle, move_files, make_figure
from solver import ConstraintSolver, total_building_energy_costs, total_installation_costs, _update_building

import ray


base_dir = './'
config = {'city_solar_energy_price': 1.0, 
            'grid_selling_price': 2.0,
            'top_limit': 7,
            'max_equipment_count': 300,
            'min_equipment_count': 10,
            'autonomy_period_days': 0.05, # ~1h
            'use_roof_sq' : 1,
            'save_opt_production' : 1,
            'ray_rate': 0.3,
        }
components = {}
#building_objects = []
data_tables = {'location_data': None,
              'equipment_data': None, 
              'battery_data': None,
              'building_data': None,
              'consumption_data': None,
              'production_data': None,
              'solution_data': None,
}  

consumption_dir = os.path.join(base_dir, 'consumption')
production_dir = os.path.join(base_dir, 'production')
solution_dir = os.path.join(base_dir, 'solution')

os.makedirs(consumption_dir, exist_ok=True)
os.makedirs(production_dir, exist_ok=True)
os.makedirs(solution_dir, exist_ok=True)

log = ''
def _print(value, clear=False):
    global log
    if clear:
        log = ''
    log += '\n' + value
    print(value)    

_rename = {'A': 'location_uuid',
           'B': 'equipment_uuid',
           'C': 'equipment_count',
           'D': 'battery_uuid',
           'E': 'battery_count',
           }

def _ren(s):
    global components
    def _match(k, v):
        if 'uuid' in k:
            k = k.split('_')[0]
            if isinstance(v, (int, str)):
                return components[k][v]['uuid']
            elif isinstance(v, tuple):
                return [components[k][i]['uuid'] for i in v]
        return v
    _r = {}
    for k, v in s.items():
        if k in _rename:   
            k = _rename[k]
            #v = _match(k, v)
            _r.update({k: v})
    return _r
        

def print_building(building):
    status = f"""building {building.uuid}:
    total_production: {building.production['production'].sum():.1f}
    total_consumption: {building.consumption['consumption'].sum():.1f}
    total_solar_energy_underproduction: {building.total_solar_energy_underproduction:.1f}
    total_solar_energy_overproduction: {building.total_solar_energy_overproduction:.1f}
    total_building_energy_costs: {total_building_energy_costs(building, **config):.1f}
    locations_involved: {len(building._locations)}
    total_renting_costs: {building.total_renting_costs:.1f}
    equipment_units_used: {sum([eq['pv_count'] for loc in building._locations for eq in loc['_equipment']])}
    total_equipment_costs: {building.total_equipment_costs:.1f}
    baterry_units_used: {sum([bt['battery_count'] for bt in building._battery])}
    total_battery_costs: {building.total_battery_costs:.1f}
    total_installation_costs: {total_installation_costs(building, **config):.1f}"""
    _print(status)
    
def update_config(new_config):
    global config
    config.update(new_config)
    
def init_components(base_dir, upload_dir=None):
    global components, data_tables
    
    _print(f'base_dir: {base_dir}', clear=True)
    
    if not upload_dir:
        data_tables = load_pickle(os.path.join(base_dir, 'components.pickle'))
    else:
        move_files(upload_dir['consumption_file'], consumption_dir)
        move_files(upload_dir['production_file'], production_dir)
        excel_file = glob.glob(os.path.join(upload_dir['excel_file'], '*.xlsx'))
        if len(excel_file) and os.path.exists(excel_file[0]):
            excel_file = excel_file[0] 
            for k in data_tables.keys():  
                try:    
                    print(f'attempt to load {k} from {excel_file}')      
                    df = pd.read_excel(excel_file, sheet_name=k.split('_')[0], converters={'size_WxHm': literal_eval,
                                                                                           'pv_size_mm': literal_eval,
                                                                                           'uuid': str,
                                                                                           'building_uuid': str,
                    })
                    df.index = range(1, len(df)+1)
                    #print(df.info())
                    #print(df)
                    data_tables[k] = df
                    data_tables[k].index = data_tables[k].uuid.copy()
                    
                    if 'battery_price' in data_tables[k].columns:
                        data_tables[k]['battery_price_per_kWh'] = (data_tables[k]['battery_price'] / data_tables[k]['battery_energy_kWh']).fillna(0)
                        #data_tables[k].loc[pd.isna(data_tables[k]['battery_energy_kWh']), ['battery_price_per_kWh']] = 0
                        #print(data_tables[k]['battery_price_per_kWh'])
                        
                    if 'pv_price' in data_tables[k].columns:
                        data_tables[k]['pv_price_per_Wp'] = (data_tables[k]['pv_price'] / data_tables[k]['pv_watt_peak']).fillna(0)
                    
                    print(f'loaded data length: {len(df)}')
                    save_pickle(data_tables, os.path.join(base_dir, 'components.pickle'))
                except Exception as e:
                    print(f'error: {e}')
            os.remove(excel_file)
   
    components['location'] = data_tables['location_data'].to_dict(orient='index')
    components['equipment'] = data_tables['equipment_data'].to_dict(orient='index')
    components['battery'] = data_tables['battery_data'].to_dict(orient='index')

    _print('data loading:')  
    _print(f"    locations: {len(components['location'])}, equipment: {len(components['equipment'])}, batteries: {len(components['battery'])}")
    _print(f"    buildings: {len(data_tables['building_data'])}, production: {len(data_tables['production_data'])}, consumption: {len(data_tables['consumption_data'])}") 
    _print(f"    stored solutions: {len(data_tables['solution_data'])}")
    
    #print(data_tables['production_data'])
    '''
    for idx, item in data_tables['building_data'].iterrows():
        #try:        
            b = equip.Building(**item.to_dict())
            b.load_production(data_tables['production_data'], storage=production_dir)
            b.load_consumption(data_tables['consumption_data'], storage=consumption_dir)
            for idx, item in data_tables['location_data'][data_tables['location_data']['building_uuid'] == b.uuid].iterrows():
                loc = equip.Location.copy()
                loc.update(item.to_dict())
                b._locations.append(loc)
            b.updated(update_production=False)
            #print(b.production['production'].sum())
            building_objects.append(b)
        #except Exception as e:
        #    print(f'error loading building {b.uuid}: {str(e)}')
    '''

def dict_to_building(building_dict):
        global components, data_tables, config
        b = equip.Building(**building_dict)
        b.load_production(data_tables['production_data'], storage=production_dir)
        b.load_consumption(data_tables['consumption_data'], storage=consumption_dir)
        for idx, item in data_tables['location_data'][data_tables['location_data']['building_uuid'] == b.uuid].iterrows():
                loc = equip.Location.copy()
                loc.update(item.to_dict())
                b._locations.append(loc)
        return b

def calculate(base_dir):   
    global components, data_tables, config
    ray.init(ignore_reinit_error=True)
    
    #ray_rate = 1.0
    
    @ray.remote
    def solve(building, components, config):
        solutions, costs = [], []
        try:
            building._erase_equipment()
            print(f'solving building: {building.uuid}')
            start_time = time.time()
            solver = ConstraintSolver(building, components, config=config)
            solutions, costs = solver.get_solutions()   
            print(f'{building.uuid} solving time: {format_timespan(time.time() - start_time)}')
        except Exception as e:
            print(f'error calculating building {building.uuid}: {str(e)}')
        return solutions, costs  
    
    _print(f"config: {config}")
    
    if config['autonomy_period_days'] == 0.0:
        split_key = 'equipment'
    else:
        if len(components['equipment']) >= len(components['battery']):
            split_key = 'equipment'
        else:
            split_key = 'battery'        
    
    split_list = list(components[split_key].keys())
    split_count = len(split_list)
    chunk_size = int(config['ray_rate'] * split_count)
    if chunk_size < 1:
        chunk_size = 1
        
    print(f"splitting by: {split_key}, chunk size: {chunk_size}")
    start_time = time.time()
    
    ray_instances = {}
    for chunk in range(0, split_count, chunk_size):
        print(split_list[chunk:chunk + chunk_size])
        _components = components.copy()
        _components[split_key] = {k : v for k, v in components[split_key].items() if k in split_list[chunk:chunk + chunk_size]}
        for _, b in data_tables['building_data'].iterrows(): #.iloc[:2]
            if b['uuid'] not in ray_instances:
                ray_instances[b['uuid']] = []
            ray_instances[b['uuid']] += [solve.remote(dict_to_building(b.to_dict()), _components, config)]
    
    ray_results = {}
    for _, b in data_tables['building_data'].iterrows(): #.iloc[:2]
        solutions, costs = [], []
        for (s, c) in ray.get(ray_instances[b['uuid']]):
                solutions += s
                costs += c
        if len(solutions) > 1:
            solutions = itemgetter(*np.argsort(costs))(solutions) 
            costs = itemgetter(*np.argsort(costs))(costs)
            solutions = solutions[:config['top_limit']]
            costs = costs[:config['top_limit']]
        ray_results[b['uuid']] = (solutions, costs)

    print(f'total solving time: {format_timespan(time.time() - start_time)}')
    ray.shutdown()
    print(ray_results)
    
    for _, b in data_tables['building_data'].iterrows(): #.iloc[:2]
        if b['uuid'] in ray_results:
            building = dict_to_building(b.to_dict())
            s = ray_results[b['uuid']][0][0]
            _update_building(building, components, s, use_roof_sq=config['use_roof_sq'])
            s = _ren(s)
            data_tables['solution_data'] = ConstraintSolver(building, components, config=config).save_solution(data_tables['solution_data'], building, s, storage=solution_dir)
            if config['save_opt_production']:
                data_tables['production_data'] = building.save_production(data_tables['production_data'], storage=production_dir)
            _print(f"solution for building {b['uuid']}: {s}")
            print_building(building)        
        
    save_pickle(data_tables, os.path.join(base_dir, 'components.pickle'))    
    
    
    '''
    
# Start two tasks in the background.
x_id = solve1.remote(0)
y_id = solve2.remote(1)

# Block until the tasks are done and get the results.
x, y = ray.get([x_id, y_id])    
    
    
    
    for building in building_objects:
        try:
            #print_building(building)
            building._erase_equipment()
            _print(f'building {building.uuid} solving...')
            start_time = time.time()
            solver = ConstraintSolver(building, components, config=config)
            solutions = solver.get_solutions()   
            _print(f'    solving time (sec): {time.time() - start_time:.1f}')
            solutions = solutions[:config['top_limit']]
            #solutions.reverse()
            if len(solutions):
                _print(f"    top-{config['top_limit']} solutions:")
                #_print(f'    A - location, B - equipment, C - equipment count, D - battery, E - battery count')
                for i, s in enumerate(solutions):
                    if i == 0:
                        _print(f"    {i+1}) better solution for building {building.uuid}: {_ren(s)} solution costs: {solver.calc_solution_costs(s):.3f}")
                        _update_building(building, components, s, use_roof_sq=config['use_roof_sq'])
                        data_tables['solution_data'] = solver.save_solution(data_tables['solution_data'], building, _ren(s), storage=solution_dir)
                        if config['save_opt_production']:
                            data_tables['production_data'] = building.save_production(data_tables['production_data'], storage=production_dir)
                        print_building(building)
                    else:
                        _print(f'    {i+1}) {_ren(s)} solution costs: {solver.calc_solution_costs(s):.3f}')
            else:
                _print('no solution meets criteria.')
                    
            #break        
                          
        except Exception as e:
            print(f'error calculating building {building.uuid}: {str(e)}')
                
    save_pickle(data_tables, os.path.join(base_dir, 'components.pickle'))
    #data_tables['solution_data'].to_csv(os.path.join(base_dir, 'solution.csv'), index=False, sep=';')  
    '''
'''
def _init_components(base_dir):
    global components, building_objects, data_tables
    
    _print(f'base_dir: {base_dir}', clear=True)
    location_data = pd.read_csv(os.path.join(base_dir, 'location.csv'), sep=';', converters={'size_m': literal_eval})
    location_data.index = range(1, len(location_data)+1)
    components['location'] = location_data.to_dict(orient='index')

    equipment_data = pd.read_csv(os.path.join(base_dir, 'equipment.csv'), sep=';', converters={'pv_size_mm': literal_eval})
    equipment_data.index = range(1, len(equipment_data)+1)
    components['equipment'] = equipment_data.to_dict(orient='index')
    #del equipment_data
    
    battery_data = pd.read_csv(os.path.join(base_dir, 'battery.csv'), sep=';')
    battery_data.index = range(1, len(battery_data)+1)
    components['battery'] = battery_data.to_dict(orient='index')
    #del battery_data
    
    building_data = pd.read_csv(os.path.join(base_dir, 'building.csv'), sep=';')
    building_data.index = range(1, len(building_data)+1)
    
    consumption_data = pd.read_csv(os.path.join(base_dir, 'consumption.csv'), sep=';')
    consumption_data.index = range(1, len(consumption_data)+1)
    
    production_data = pd.read_csv(os.path.join(base_dir, 'production.csv'), sep=';')
    production_data.index = range(1, len(production_data)+1)
    
    solution_data = pd.read_csv(os.path.join(base_dir, 'solution.csv'), sep=';', converters={'solution': literal_eval})
    solution_data.index = range(1, len(solution_data)+1)
    
    data_tables = {'location_data': location_data,
              'equipment_data': equipment_data, 
              'battery_data': battery_data,
              'building_data': building_data,
              'consumption_data': consumption_data,
              'production_data': production_data,
              'solution_data': solution_data,
    }    
    
    _print('data loading:')  
    _print(f"    locations: {len(components['location'])}, equipment: {len(components['equipment'])}, batteries: {len(components['battery'])}")
    _print(f"    buildings: {len(building_data)}, production: {len(production_data)}, consumption: {len(consumption_data)}") 
    _print(f"    stored solutions: {len(solution_data)}")
    
    for idx, item in building_data.iterrows():
        b = equip.Building(**item.to_dict())
        
        b.load_production(production_data, storage=production_dir)
        b.load_consumption(consumption_data, storage=consumption_dir)
        for idx, item in location_data[location_data['building'] == b.uuid].iterrows():
            loc = equip.Location.copy()
            loc.update(item.to_dict())
            b._locations.append(loc)
        b.updated(update_production=False)
        building_objects.append(b)
    
    #save_pickle(data_tables, os.path.join(base_dir, 'components.pickle'))

def _calculate(base_dir):   
    global components, building_objects, data_tables
    
    for building in building_objects:
        #print_building(building)
        building._erase_equipment()
        _print('solving...')
        start_time = time.time()
        solver = ConstraintSolver(building, components)
        solutions = solver.get_solutions()   
        _print(f'    solving time: {time.time() - start_time}')
        solutions = solutions[:top_limit]
        solutions.reverse()
    
        _print(f'    top-5 solutions (reversed order):')
        #_print(f'    A - location, B - equipment, C - equipment count, D - battery, E - battery count')
        for i, s in enumerate(solutions):
            if i == top_limit-1:
                _print(f"    optimal: {_ren(s)} cost: {solver.calc_solution_costs(s):.3f}")
                _update_building(building, components, solutions[0])
                data_tables['solution_data'] = solver.save_solution(data_tables['solution_data'], building, solutions[0], storage=solution_dir)
                print_building(building)
            else:
                _print(f'    {_ren(s)} cost: {solver.calc_solution_costs(s):.3f}')            
    
    data_tables['solution_data'].to_csv(os.path.join(base_dir, 'solution.csv'), index=False, sep=';')  

if __name__ == "__main__":
    pass
'''



    
    
    
    
    
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
 
    
    #sys.exit()
