import pandas as pd
import numpy as np
from uuid import uuid4
import json, os, pickle, time#, random, math
import utils

pv_gis = utils.PVGIS()

# https://www.youtube.com/watch?v=OPNBWaBZvjc&ab_channel=%D0%94%D0%B5%D1%80%D0%B5%D0%B2%D0%B5%D0%BD%D1%81%D0%BA%D0%B8%D0%B9%D1%84%D0%BE%D1%82%D0%BE%D0%B3%D1%80%D0%B0%D1%84
# https://www.youtube.com/watch?v=Oriqr7K9kAc&ab_channel=%D0%94%D0%B5%D1%80%D0%B5%D0%B2%D0%B5%D0%BD%D1%81%D0%BA%D0%B8%D0%B9%D1%84%D0%BE%D1%82%D0%BE%D0%B3%D1%80%D0%B0%D1%84
# потребление - 1 кВт 8 часов в сутки
# аккумулятор - 12 В х 60 Ah = 720 Втч * 0,7 = 504 Втч - полчас
Battery = dict(
        uuid = None,
        battery_count = 1,
        type = 'LiFePO4',
        battery_capacity_Ah = 100,
        battery_energy_Wh = 4800,
        battery_voltage = 48,
        battery_discharge_factor = 0.7,
        battery_price_per_Wh = 9.738,
)
Equipment = dict(
        uuid = None,
        pv_count = 1,
        type = 'CIS',
        pv_size_mm = (2176, 1098),
        pv_efficiency = 18,
        pv_watt_peak = 500,
        pv_price_per_Wp = 0.90,
        pv_loss = 14,
        pv_voltage = 48,
)
Location = dict(
        uuid = None,
        angle = 0,
        aspect = 0,
        size_m = (10, 10),
        price_per_sqm = 1,
        lat = 52.373,
        lon = 9.738,
        _equipment = []
)
Production = dict(
        uuid = None,
        timestamp = 1692989661.8293242,
        year = 2022,
        building = 1,
        production = '5c75deb8d33045cd86bb3ee9b7e98c25'
)
Consumption = dict(
        uuid = None,
        timestamp = 1692989661.8293242,
        year = 2022,
        building = 1,
        consumption = '5c75deb8d33045cd86bb3ee9b7e98c25'
)

class Building:
    def __init__(self, uuid=None, 
                       name='noname',
                       address='Hannover',
                       lat=52.373,
                       lon=9.738,
                       locations=[],
                       batteries=[]):
        self.uuid = uuid
        self.name = name
        self.address = address
        self.lat = lat
        self.lon = lon
        self._locations = locations
        self._battery = batteries
        self._production = None
        self._consumption = None
        self._total_renting_costs = None
        self._total_battery_costs = None
        self._total_equipment_costs = None
        self._total_energy_storage_needed = None
        self._total_solar_energy_consumption = None
        self._total_solar_energy_underproduction = None
        
    def _erase_equipment(self, keep_consumption=True):
        self._battery = []
        for loc in self._locations:
            loc['_equipment'] = []
        self._production = None
        if not keep_consumption:
            self._consumption = None
        self._total_renting_costs = None
        self._total_battery_costs = None
        self._total_equipment_costs = None
        self._total_energy_storage_needed = None
        self._total_solar_energy_consumption = None
        self._total_solar_energy_underproduction = None

    def from_storage(self, data_key, storage='./'):
        file_name = os.path.join(storage, data_key)
        if os.path.exists(file_name+'.json'):
            with open(file_name+'.json', 'r') as fp:
                return pd.read_json(json.load(fp))
        elif os.path.exists(file_name+'.pickle'):
            with open(file_name+'.pickle', 'rb') as fp:
                return pickle.load(fp)        

    def to_storage(self, data_key, data, storage='./', use_pickle=False):
        file_name = os.path.join(storage, data_key)
        if use_pickle:
            with open(file_name+'.pickle', 'wb') as fp:
                pickle.dump(data, fp)
        else:     
            with open(file_name+'.json', 'w') as fp:
                json.dump(data.to_json(), fp)

    def load_production(self, production_data, building=None, year=None, timestamp=None, uuid=None, storage='./'):
        query = f"`building` == {self.uuid if building == None else building}"
        query += f" & `uuid` == {uuid}" if uuid != None else ''
        query += f" & `timestamp` == {timestamp}" if timestamp != None else ''
        query += f" & `year` == {year}" if year != None else ''
        filtered = production_data.query(query)
        if not utils.is_empty(filtered):
            filtered = filtered.sort_values(by=['year', 'timestamp'], ascending=False)
            self._production = self.from_storage(filtered.iloc[0]['production'], storage=storage)
            return self._production
                
    def save_production(self, production_data, building=None, year=None, timestamp=None, uuid=None, storage='./', use_pickle=False):
        data_key = Production.copy()
        data_key['uuid'] = uuid if uuid != None else uuid4().hex
        data_key['production'] = uuid4().hex
        data_key['building'] = self.uuid if building == None else building
        data_key['timestamp'] = timestamp if timestamp != None else time.time()
        data_key['year'] = year if year != None else self._production.index[0].year
        self.to_storage(data_key['production'], self._production, storage=storage, use_pickle=use_pickle)
        return pd.concat([production_data, pd.DataFrame.from_dict({0: data_key}, orient='index')], ignore_index=True)
    
    def load_consumption(self, consumption_data, building=None, year=None, timestamp=None, uuid=None, storage='./'):
        query = f"`building` == {self.uuid if building == None else building}"
        query += f" & `uuid` == {uuid}" if uuid != None else ''
        query += f" & `timestamp` == {timestamp}" if timestamp != None else ''
        query += f" & `year` == {year}" if year != None else ''
        filtered = consumption_data.query(query)
        if not utils.is_empty(filtered):
            filtered = filtered.sort_values(by=['year', 'timestamp'], ascending=False)
            self._consumption = self.from_storage(filtered.iloc[0]['consumption'], storage=storage)
            return self._consumption
                
    def save_consumption(self, consumption_data, building=None, year=None, timestamp=None, uuid=None, storage='./', use_pickle=False):
        data_key = Consumption.copy()
        data_key['uuid'] = uuid if uuid != None else uuid4().hex
        data_key['consumption'] = uuid4().hex
        data_key['building'] = self.uuid if building == None else building
        data_key['timestamp'] = timestamp if timestamp != None else time.time()
        data_key['year'] = year if year != None else self._consumption.index[0].year
        self.to_storage(data_key['consumption'], self._consumption, storage=storage, use_pickle=use_pickle)
        return pd.concat([consumption_data, pd.DataFrame.from_dict({0: data_key}, orient='index')], ignore_index=True)
        
    def get_total_renting_costs(self):
        if self._total_renting_costs == None:
            self._total_renting_costs = 0
            for loc in self._locations:
                total_sq = 0
                for eq in loc['_equipment']:
                    total_sq += (eq['pv_size_mm'][0] / 1000) * (eq['pv_size_mm'][1] / 1000) * eq['pv_count']
                self._total_renting_costs += total_sq * loc['price_per_sqm']              
        return self._total_renting_costs     
    
    def get_total_battery_costs(self):   
        if self._total_battery_costs == None:
            self._total_battery_costs = 0
            for bt in self._battery:
                self._total_battery_costs += _calc_battery_costs(bt)          
        return self._total_battery_costs
    
    def get_total_equipment_costs(self):   
        if self._total_equipment_costs == None:
            self._total_equipment_costs = 0
            for loc in self._locations:
                for eq in loc['_equipment']:
                    self._total_equipment_costs += _calc_equipment_costs(eq)          
        return self._total_equipment_costs

    def get_total_energy_storage_needed(self):
        if self._total_energy_storage_needed == None:
            self._total_energy_storage_needed = _calc_total_energy_storage_needed(self)
        return self._total_energy_storage_needed

    def get_total_solar_energy_consumption(self):
        if self._total_solar_energy_consumption == None:
            self._total_solar_energy_consumption = min(self.production['production'].sum(), self.consumption['consumption'].sum())
        return self._total_solar_energy_consumption

    def get_total_solar_energy_underproduction(self):
        if self._total_solar_energy_underproduction == None:
            self._total_solar_energy_underproduction = max(0, self.consumption['consumption'].sum() - self.production['production'].sum())
        return self._total_solar_energy_underproduction
        
    def get_production(self):
        if not isinstance(self._production, (pd.Series, pd.DataFrame)):
            self._production = _calc_building_production(self)
        return self._production
    
    def get_consumption(self):
        if not isinstance(self._consumption, (pd.Series, pd.DataFrame)):
            self._consumption = _mook_building_consumption(self)
        return self._consumption
    
    def updated(self, update_production=True):
        if update_production:
            self._production = None
        self._total_battery_costs = None
        self._total_renting_costs = None
        self._total_equipment_costs = None
        self._total_energy_storage_needed = None
        self._total_solar_energy_consumption = None
        self._total_solar_energy_underproduction = None
        self.get_production()
        self.get_total_solar_energy_consumption()
        self.get_total_solar_energy_underproduction()     
        self.get_total_energy_storage_needed() 
        self.get_total_equipment_costs()  
        self.get_total_renting_costs()
        self.get_total_battery_costs()
    
    production = property(fget=get_production) # {"P": {"description": "PV system power", "units": "W"}
    consumption = property(fget=get_consumption)
    total_renting_costs = property(fget=get_total_renting_costs)
    total_battery_costs = property(fget=get_total_battery_costs)
    total_equipment_costs = property(fget=get_total_equipment_costs)
    total_energy_storage_needed = property(fget=get_total_energy_storage_needed)
    total_solar_energy_consumption = property(fget=get_total_solar_energy_consumption)
    total_solar_energy_underproduction = property(fget=get_total_solar_energy_underproduction)

def _calc_equipment_production(loc, eq):
    nominal_pv = pv_gis.get_nominal_pv(angle=loc['angle'], # Watt per 1 kWp
                             aspect=loc['aspect'], 
                             pvtech=eq['type'], 
                             loss=eq['pv_loss'], 
                             lat=loc['lat'], 
                             lon=loc['lon'],)
    production = nominal_pv * (eq['pv_watt_peak'] / 1000) * eq['pv_count']
    return production

def _calc_location_production(loc):
    pv = 0
    for eq in loc['_equipment']:
      pv = pv + _calc_equipment_production(loc, eq)
    return pv

def _calc_building_production(b):
    pv = 0
    for loc in b._locations:
      pv = pv + _calc_location_production(loc)
    return pv

def _mook_building_consumption(b, multiplicator=1):
    np.random.seed(13)
    pv = b.production.copy()
    m = pv.mean()
    sd = pv.std()
    pv['consumption'] = np.abs(np.random.normal(m, 0.5*sd, len(pv)) * multiplicator)
    return pv[['consumption']]

def _calc_total_energy_storage_needed(b, autonomy_period_days=None):
    peak_daily_consumption = b.consumption.resample('D').sum().max()['consumption']
    if autonomy_period_days == None:
        avg_daily_production = b.production.resample('D').sum().mean()['production']
        autonomy_period_days = np.ceil(peak_daily_consumption / avg_daily_production)
    return peak_daily_consumption * autonomy_period_days

def _calc_battery_costs(bt):
    return bt['battery_energy_Wh'] * bt['battery_price_per_Wh'] * bt['battery_count']

def _calc_equipment_costs(eq):
    return eq['pv_watt_peak'] * eq['pv_price_per_Wp'] * eq['pv_count']
