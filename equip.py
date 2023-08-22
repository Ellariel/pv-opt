import pandas as pd
import numpy as np
import json, random, math
import utils

# https://www.youtube.com/watch?v=OPNBWaBZvjc&ab_channel=%D0%94%D0%B5%D1%80%D0%B5%D0%B2%D0%B5%D0%BD%D1%81%D0%BA%D0%B8%D0%B9%D1%84%D0%BE%D1%82%D0%BE%D0%B3%D1%80%D0%B0%D1%84
# https://www.youtube.com/watch?v=Oriqr7K9kAc&ab_channel=%D0%94%D0%B5%D1%80%D0%B5%D0%B2%D0%B5%D0%BD%D1%81%D0%BA%D0%B8%D0%B9%D1%84%D0%BE%D1%82%D0%BE%D0%B3%D1%80%D0%B0%D1%84
# потребление - 1 кВт 8 часов в сутки
# аккумулятор - 12 В х 60 Ah = 720 Втч * 0,7 = 504 Втч - полчас
        
class Battery:
    def __init__(self):
        self.uuid = None
        self.type = 'LiFePO4'
        self.battery_count = 1
        self.battery_capacity_Ah = 100
        self.battery_energy_Wh = 4800
        self.battery_voltage = 48
        self.battery_discharge_factor = 0.7
        self.battery_price_per_Wh = 9.738 

class Equipment:
    def __init__(self, battery=[]):
        self.uuid = None
        self.type = 'CIS'
        self.pv_count = 1
        self.pv_size_mm = (2176, 1098)
        self.pv_efficiency = 18
        self.pv_watt_peak = 500
        self.pv_price_per_Wp = 0.90
        self.pv_loss = 14
        self.pv_voltage = 48
        self.battery = battery
        self._total_battery_costs = None   
        
    def get_total_battery_costs(self):
        self._total_battery_costs = 0
        for bt in self.battery:
            self._total_battery_costs += bt.battery_energy_Wh * bt.battery_price_per_Wh * bt.battery_count             
        return self._total_battery_costs   
    
    total_battery_costs = property(fget=get_total_battery_costs)

class Location:
    def __init__(self, equipment=[]):
        self.uuid = None
        self.angle = 0
        self.aspect = 0
        self.size_m = (10, 10)
        self.price_per_sqm = 1
        self.lat = 52.373
        self.lon = 9.738
        self.equipment = equipment
        
class Building:
    def __init__(self, locations=[]):
        self.uuid = None
        self.address = 'Hannover'
        self.lat = 52.373
        self.lon = 9.738
        self._locations = locations
        self._production = None
        self._consumption = None
        self._total_renting_costs = None
        self._total_energy_storage_needed = None
        self._total_solar_energy_consumption = None
        self._total_solar_energy_underproduction = None
        
    def get_total_renting_costs(self):
        if self._total_renting_costs == None:
            self._total_renting_costs = 0
            for loc in self._locations:
                total_sq = 0
                for eq in loc.equipment:
                    total_sq += (eq.pv_size_mm[0] / 1000) * (eq.pv_size_mm[1] / 1000) * eq.pv_count
                self._total_renting_costs += total_sq * loc.price_per_sqm              
        return self._total_renting_costs        

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
    
    def set_locations(self, value):
        if self._locations != value:
            self._locations = value
            self.updated()
            
    def get_locations(self):
        return self._locations
    
    def updated(self):
        self._production = None
        self._total_renting_costs = None
        self._total_energy_storage_needed = None
        self._total_solar_energy_consumption = None
        self._total_solar_energy_underproduction = None
        self.get_production()
        self.get_total_renting_costs()
        self.get_total_solar_energy_consumption()
        self.get_total_solar_energy_underproduction()     
        self.get_total_energy_storage_needed()   
    
    locations = property(fget=get_locations, fset=set_locations)
    production = property(fget=get_production) # {"P": {"description": "PV system power", "units": "W"}
    consumption = property(fget=get_consumption)
    total_renting_costs = property(fget=get_total_renting_costs)
    total_energy_storage_needed = property(fget=get_total_energy_storage_needed)
    total_solar_energy_consumption = property(fget=get_total_solar_energy_consumption)
    total_solar_energy_underproduction = property(fget=get_total_solar_energy_underproduction)

def _calc_equipment_production(loc, eq):
    nominal_pv = utils.get_nominal_pv(angle=loc.angle,
                             aspect=loc.aspect, 
                             pvtech=eq.type, 
                             loss=eq.pv_loss, 
                             lat=loc.lat, 
                             lon=loc.lon,)
    production = (nominal_pv / 1000) * eq.pv_watt_peak * eq.pv_count
    return production.rename(columns={'pv' : 'production'})

def _calc_location_production(loc):
    pv = 0
    for eq in loc.equipment:
      pv = pv + _calc_equipment_production(loc, eq)
    return pv

def _calc_building_production(b):
    pv = 0
    for loc in b.locations:
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

