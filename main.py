import time, os, glob#, pickle, json, uuid
import pandas as pd, numpy as np
from humanfriendly import format_timespan

#from ppretty import ppretty
from ast import literal_eval
from operator import itemgetter

import equip
#from equip import Building, Equipment, Location, Battery
from utils import save_pickle, load_pickle, move_files, make_figure
from solver import ConstraintSolver, total_building_energy_costs, total_installation_costs, genossenschaft_profit, _update_building

import ray


base_dir = './'
config = {'city_solar_energy_price': 1.0, 
            'grid_selling_price': 2.0,
            'grid_buying_price': 1.5,
            'top_limit': 7,
            'max_equipment_count': 300,
            'min_equipment_count': 10,
            'autonomy_period_days': 0.05, # ~1h
            'use_roof_sq' : 1,
            'save_opt_production' : 1,
            'ray_rate': 1.0,
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
        

def get_soultion_metrics(building):
    metrics = {
        'building': building.uuid,
        'total_production': building.production['production'].sum(),
        'total_consumption': building.consumption['consumption'].sum(),
        'total_solar_energy_consumption': building.total_solar_energy_consumption,
        'total_solar_energy_underproduction': building.total_solar_energy_underproduction,
        'total_solar_energy_overproduction': building.total_solar_energy_overproduction,
        'total_building_energy_costs': total_building_energy_costs(building, **config),
        'locations_involved': len(building._locations),
        'total_renting_costs': building.total_renting_costs,
        'equipment_units_used': sum([eq['pv_count'] for loc in building._locations for eq in loc['_equipment']]),
        'total_equipment_costs': building.total_equipment_costs,
        'baterry_units_used': sum([bt['battery_count'] for bt in building._battery]),
        'total_battery_costs': building.total_battery_costs,
        'total_installation_costs': total_installation_costs(building, **config),
        'genossenschaft_profit': genossenschaft_profit(building, **config),
    }
    #_print(str(metrics))
    return metrics
    
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
            s.update(get_soultion_metrics(building))
            _print(f"solution for building {b['uuid']}: {s}")
            data_tables['solution_data'] = ConstraintSolver(building, components, config=config).save_solution(data_tables['solution_data'], building, s, storage=solution_dir)
            if config['save_opt_production']:
                data_tables['production_data'] = building.save_production(data_tables['production_data'], storage=production_dir)

    save_pickle(data_tables, os.path.join(base_dir, 'components.pickle'))    
