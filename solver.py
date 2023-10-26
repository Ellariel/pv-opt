import time, os, copy, pickle, time, random#, datetime, random, requests, uuid, json, 
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

# min: building energy cost = (SEC * CP) + (SPU * SP) + roof renting costs
def total_building_energy_costs(b, city_solar_energy_price=1.0, grid_selling_price=1.5, **kwargs):
    #print(f'city_solar_energy_price: {city_solar_energy_price}, grid_selling_price: {grid_selling_price}')
    return b.total_solar_energy_consumption * city_solar_energy_price +\
           b.total_solar_energy_underproduction * grid_selling_price +\
           b.total_renting_costs
           
# installation costs = costofequipment and battery
def total_installation_costs(b, **kwargs):
    #print(f'city_solar_energy_price: {city_solar_energy_price}, grid_selling_price: {grid_selling_price}')
    return b.total_equipment_costs + b.total_battery_costs

Solution = dict(
        uuid = None,
        building_uuid = 1,
        solution = {},
        selected = 0,
        timestamp = 1692989661.8293242,
        stored = '5c75deb8d33045cd86bb3ee9b7e98c25'
)

def _locations(combination, locations):
    return [locations[i] for i in combination if i in locations]    

def _update_building(building, components, solution, use_roof_sq=False, autonomy_period_days=None):
    #print('use_roof_sq', use_roof_sq)
    A, B, C, D, E = solution['A'], solution['B'], solution['C'], solution['D'], solution['E']
    loc, eq, eq_count, bt, bt_count = copy.deepcopy(sorted(_locations(A, components['location']), key=lambda x: x['price_per_sqm'])), components['equipment'][B], C, copy.deepcopy(components['battery'][D]), E
    eq_square_needed = eq['pv_size_Wmm'] * eq['pv_size_Hmm']
    for l in loc:
        l['_equipment'] = []
        if eq_count > 0:
            if use_roof_sq:
                total_square_available = l['size_sqm'] * 10 ** 6
            else:
                total_square_available = l['size_WxHm'][0] * l['size_WxHm'][1] * 10 ** 6
            _eq = eq.copy()
            _eq['pv_count'] = min(np.ceil(total_square_available / eq_square_needed), eq_count)
            #print('pv_count', _eq['pv_count'])
            eq_count -= _eq['pv_count']
            l['_equipment'] = [_eq]   
    bt['battery_count'] = bt_count
    building._battery = [bt]
    building._locations = loc
    building.updated(autonomy_period_days=autonomy_period_days)
    #print(building.production['production'].sum() - building.consumption['consumption'].sum())
    return building

def _max_equipment_count_in_loc(locations, equipment, use_roof_sq=True):
        max_count = []
        for eq in equipment:
                if use_roof_sq: 
                    max_count += [sum([np.floor((l['size_sqm'] * 10 ** 6) / (eq['pv_size_Wmm'] * eq['pv_size_Hmm'])) for l in locations])]
                else:
                    max_count += [sum([min(np.floor(l['size_WxHm'][0] * 1000 / eq['pv_size_Wmm']), np.floor(l['size_WxHm'][1] * 1000 / eq['pv_size_Hmm'])) for l in locations])]
        return max_count

def _combinations(a): 
    _comb = set()
    for j in list(itertools.combinations_with_replacement(range(0, len(a)+1), len(a))) :
        c = []
        for i in j:
            if i > 0 and i not in c:
                c += [i]
        if len(c):
            _comb.add(tuple(sorted([a[i-1] for i in c])))
    return list(_comb)

def _range(min_count=10, max_count=100, zero=False):
    def _primes(_from, _to):
        out = list()
        sieve = [True] * (_to+1)
        for p in range(_from, _to+1):
            if sieve[p]:
                out.append(p)
                for i in range(p, _to+1, p):
                    sieve[i] = False
        return out
    _out = set(list(range(0 if zero else 1, min_count+1)) + _primes(min_count+1, max_count))
    _out.add(min_count)
    _out.add(max_count)
    return list(_out)

class ConstraintSolver:
    def __init__(self, building, possible_components, cache_storage='./', config={}):
        self.cached_solutions = Cache(storage=cache_storage)
        self.components = possible_components
        self.building = building
        self.config = config
        
        _filtered_locations = [k for k, v in self.components['location'].items() if v['building_uuid'] == self.building.uuid]
        #self.locations_combinations = list(itertools.permutations(range(0, len(self.components['location'])+1), 
        #                                                                   len(self.components['location'])))
        #self.locations_combinations = list(set([tuple([i for i in j if i > 0]) for j in self.locations_combinations]))
        #self.locations_combinations = list(itertools.combinations_with_replacement(range(0, len(_filtered_locations)+1), #combinations #permutations
        #                                                                   len(_filtered_locations)))       
        #print(self.locations_combinations)
        #self.locations_combinations = list(set([tuple(set([_filtered_locations[i-1] for i in j if i > 0])) for j in self.locations_combinations]))
        
        #_combinations = set()
        #for j in self.locations_combinations:
        #    c = []
        #    for i in j:
        #        if i > 0 and i not in c:
        #            c += [i]
        #    if len(c):
        #        _combinations.add(tuple(sorted([_filtered_locations[i-1] for i in c])))
        #self.locations_combinations = list(_combinations)
        self.locations_combinations =_combinations(_filtered_locations)
        print(f"locations_combinations count: {len(self.locations_combinations)}")
        
        self.solutions = []
        self.costs = []
        self.problem = constraint.Problem()
        #print(self.locations_combinations)
        self.problem.addVariable('A', self.locations_combinations) # locations involved
        self.problem.addVariable('B', list(self.components['equipment'].keys())) #range(1, len(self.components['equipment'])+1)) # equipment id

        if self.config['autonomy_period_days'] == 0.0:
            self.problem.addVariable('D', ['NONE']) # # battery id
        else:        
            self.problem.addVariable('D', list(self.components['battery'].keys())) #range(1, len(self.components['battery'])+1)) # battery id
        #self.problem.addVariable('C', range(1, self.config['max_equipment_count'])) # equipment count
        #self.problem.addVariable('E', range(0, self.config['max_equipment_count'])) # battery count
        
        max_equipment_count = _max_equipment_count_in_loc([v for k, v in self.components['location'].items() if k in _filtered_locations], [v for k, v in self.components['equipment'].items()])
        #print(f"max_equipment_count: {self.config['max_equipment_count']}, min_equipment_count: {self.config['min_equipment_count']}, _max_equipment_count_in_loc: {max_equipment_count}")
        #max_equipment_count = int(np.max(max_equipment_count + [self.config['max_equipment_count']]))
        max_equipment_count = int(np.max(max_equipment_count))
        print(f"max_equipment_count: {max_equipment_count}")
        
        self.problem.addVariable('C', _range(self.config['min_equipment_count'], max_equipment_count)) # equipment count
        
        if self.config['autonomy_period_days'] == 0.0:
            self.problem.addVariable('E', [0]) # battery count 
        else:
            self.problem.addVariable('E', _range(self.config['min_equipment_count'], max_equipment_count, zero=True)) # battery count
            
        #print(_range(self.config['min_equipment_count'], self.config['max_equipment_count']))       
        self.problem.addConstraint(self.equipment_square_constraint, "ABC")
        #self.problem.addConstraint(self.battery_voltage_constraint, "BD")
        self.problem.addConstraint(self.battery_capacity_constraint, "ABCDE")        
        
    def equipment_square_constraint(self, A, B, C):
        loc, eq, eq_count = _locations(A, self.components['location']), self.components['equipment'][B], C
        max_count = sum(_max_equipment_count_in_loc(loc, [eq], self.config['use_roof_sq']))
        #print(f"equipment_square_constraint: {eq_count} <= {max_count}")
        return eq_count <= max_count       

    def battery_voltage_constraint(self, B, D):
        eq, bt = self.components['equipment'][B], self.components['battery'][D]
        return eq['pv_voltage'] == bt['battery_voltage']

    def battery_capacity_constraint(self, A, B, C, D, E):       
        bt, bt_count = self.components['battery'][D], E        
        _total_building_energy_costs, _total_installation_costs, _total_energy_storage_needed = self.get_cached_solution(A, B, C, D, E)
        _total_energy_storage = bt['battery_energy_kWh'] * bt['battery_discharge_factor'] * bt_count * 1000
        if self.config['autonomy_period_days'] == 0.0 and bt_count == 0:
            return True
        #print(f"battery_capacity_constraint: {bt['battery_energy_Wh'] * bt['battery_discharge_factor'] * bt_count} >= {_total_energy_storage_needed}")
        return _total_energy_storage >= _total_energy_storage_needed and _total_energy_storage <= _total_energy_storage_needed * 1.1

    def get_cached_solution(self, A, B, C, D, E):
        def _calc():
            _update_building(self.building, self.components, dict(A=A, B=B, C=C, D=D, E=E), use_roof_sq=self.config['use_roof_sq'], autonomy_period_days=self.config['autonomy_period_days'])
            return total_building_energy_costs(self.building, **self.config), total_installation_costs(self.building, **self.config), self.building.get_total_energy_storage_needed(autonomy_period_days=self.config['autonomy_period_days'])
        return self.cached_solutions.get_cached_solution((A, B, C), _calc)

    def calc_solution_costs(self, solution):
        A, B, C, D, E = solution['A'], solution['B'], solution['C'], solution['D'], solution['E']
        _total_building_energy_costs, _total_installation_costs, _total_energy_storage_needed = self.get_cached_solution(A, B, C, D, E)
        loc, bt, bt_count = _locations(A, self.components['location']), self.components['battery'][D], E
        return _total_building_energy_costs + _total_installation_costs + len(loc)/100# + (bt['battery_energy_kWh'] * bt['battery_price_per_kWh'] * bt_count)

    def get_solutions(self, always_recalc=False):
        if len(self.solutions) == 0 or always_recalc:
            self.solutions = self.problem.getSolutions()
            time.sleep(random.randint(1, 5))
            self.cached_solutions.save()
            self.costs = [self.calc_solution_costs(s) for s in self.solutions]
        print(f"solutions: {len(self.solutions)}, cahed: {len(self.cached_solutions.storage)}")
        return self.solutions, self.costs
        #return sorted(self.solutions, key=self.calc_solution_costs)

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
        data_key['building_uuid'] = building.uuid
        data_key['timestamp'] = timestamp if timestamp != None else time.time()
        self.to_storage(data_key['stored'], building, storage=storage)
        return pd.concat([solution_data, pd.DataFrame.from_dict({0: data_key}, orient='index')], ignore_index=True)
    
    def load_solution(self, solution_data, building, selected_only=False, timestamp=None, uuid=None, storage='./'):
        query = f"`building_uuid` == {building.uuid}"
        query += f" & `uuid` == {uuid}" if uuid != None else ''
        query += f" & `timestamp` == {timestamp}" if timestamp != None else ''
        query += f" & `selected` == 1" if selected_only else ''
        filtered = solution_data.query(query)
        if not is_empty(filtered):
            filtered = filtered.sort_values(by=['selected', 'timestamp'], ascending=False)
            return filtered.iloc[0]['solution'], self.from_storage(filtered.iloc[0]['stored'], storage=storage)