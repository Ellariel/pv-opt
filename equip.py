import pandas as pd
import numpy as np
import json, random, math
import utils

class Location:
    def __init__(self):
        self.uuid = None
        self.angle = 0
        self.aspect = 0
        self.size_m = (10, 10)
        self.price_per_sqm = 1
        self.lat = 52.373
        self.lon = 9.738
        self.equipment = []

class Equipment:
    def __init__(self):
        self.uuid = None
        self.type = 'CIS'
        self.pv_count = 1
        self.pv_size_mm = (2176, 1098)
        self.pv_efficiency = 18
        self.pv_watt_peak = 500
        self.pv_price_per_Wp = 0.90
        self.pv_loss = 14
        self.battery_count = 1
        self.battery_capacity_Ah = 100
        self.battery_energy_Wh = 24000
        self.battery_price_per_Wh = 9.738
        
class Building:
    def __init__(self):
        self.uuid = None
        self.address = 'Hannover'
        self.lat = 52.373
        self.lon = 9.738
        self._locations = []
        self._production = None
        self._consumption = None
        self._total_renting_costs = None
        
    def get_total_renting_costs(self):
        if self._total_renting_costs == None:
            self._total_renting_costs = 0
            for loc in self._locations:
                total_sq = 0
                for eq in loc.equipment:
                    total_sq += (eq.pv_size_mm[0] / 1000) * (eq.pv_size_mm[1] / 1000) * eq.pv_count
                self._total_renting_costs += total_sq * loc.price_per_sqm              
        return self._total_renting_costs        
    
    def total_solar_energy_consumption(self):
        return min(self.production['production'].sum(), self.consumption['consumption'].sum())

    def total_solar_energy_underproduction(self):
        return max(0, self.consumption['consumption'].sum() - self.production['production'].sum())
        
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
            self._production = self.get_production()
            self._total_renting_costs = self.get_total_renting_costs()
            
    def get_locations(self):
        return self._locations
    
    locations = property(fget=get_locations, fset=set_locations)
    production = property(fget=get_production)
    consumption = property(fget=get_consumption)
    total_renting_costs = property(fget=get_total_renting_costs)

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

def _mook_building_consumption(b):
    np.random.seed(13)
    pv = b.production
    m = pv.mean()
    sd = pv.std()
    pv['consumption'] = np.abs(np.random.normal(m, 0.5*sd, len(pv)) - 50)
    return pv[['consumption']]

