import json, time, requests, uuid, os, datetime, jsonpickle, pickle
import pandas as pd, numpy as np
from pandas import json_normalize

def is_empty(x):
    if isinstance(x, (list, dict, str, pd.DataFrame, pd.Series)):
        return len(x) == 0
    return pd.isna(x)

def to_json(obj):
        return jsonpickle.encode(obj)

def from_json(json_data):
        return jsonpickle.decode(json_data)

def _timestamp(x):
    return time.mktime(datetime.datetime.strptime(x, "%Y%m%d:%H%M").timetuple())

def _datetime(x):
    return datetime.datetime.strptime(x, "%Y%m%d:%H%M")

def _serie(x, datatype='hourly', name='production'):
    v = [(_datetime(i['time']), i['P']) for i in x[datatype]]
    v = pd.DataFrame(v).rename(columns={0:'timestamp', 1:name})
    v['timestamp'] = pd.DatetimeIndex(v['timestamp'])
    return v.set_index('timestamp')

def request_PVGIS(datatype='hourly', pvtechchoice='CIS', angle=0, aspect=0, loss=14, lat=52.373, lon=9.738, startyear=2016, endyear=2016, timeout=3):
    # https://re.jrc.ec.europa.eu/pvg_tools/en/tools.html
    # https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/getting-started-pvgis/api-non-interactive-service_en
    # pvtechchoice	"crystSi", "CIS", "CdTe" and "Unknown".
    # aspect	(azimuth) angle of the (fixed) plane, 0=south, 90=west, -90=east. Not relevant for tracking planes.
    # {"P": {"description": "PV system power", "units": "W"}
    if datatype=='hourly':
      req = r"https://re.jrc.ec.europa.eu/api/seriescalc?outputformat=json&pvcalculation=1&peakpower=1&mountingplace=building"+\
            f"&lat={lat}&lon={lon}&pvtechchoice={pvtechchoice}&loss={loss}&angle={angle}&aspect={aspect}"+\
            f"&raddatabase=PVGIS-SARAH&startyear={startyear}&endyear={endyear}"
    else:
      raise NotImplementedError(datatype)
    try:
        time.sleep(50)
        r = requests.get(req)
        r.raise_for_status()
    except requests.exceptions.Timeout:
        time.sleep(timeout)
        r = requests.get(req)
        r.raise_for_status()
    return r.json()

class PVGIS:
    def __init__(self, storage='./'):
        self.inputs_storage = os.path.join(storage, 'pv_inputs.csv')
        self.outputs_storage = os.path.join(storage, 'pv_outputs')
        os.makedirs(self.outputs_storage, exist_ok=True)
        self.inputs = pd.read_csv(self.inputs_storage, sep=';') if os.path.exists(self.inputs_storage) else None
        
    def from_storage(self, data_key):
        with open(os.path.join(self.outputs_storage, data_key['outputs']+'.json'), 'r') as fp:
            return json.load(fp)
    
    def to_storage(self, data_key, data):
        with open(os.path.join(self.outputs_storage, data_key['outputs'].iloc[0]+'.json'), 'w') as fp:
            json.dump(data, fp)
        self.inputs = pd.concat([self.inputs, data_key], ignore_index=True)
        self.inputs.to_csv(self.inputs_storage, sep=';', index=False)    
    
    def get_nominal_pv(self, angle=0, aspect=0, pvtech='CIS', loss=14, lat=52.373, lon=9.738, datayear=2016, datatype='hourly', request_if_none=True, save_if_none=True):
        # Watt per 1 kWp {"P": {"description": "PV system power", "units": "W"}
        filtered = self.inputs.query(
                f"`location.latitude` == {lat} & `location.longitude` == {lon} & "+\
                f"`data.type` == '{datatype}' & `data.year` == {datayear} & "+\
                f"`mounting_system.fixed.slope.value` == {angle} & "+\
                f"`mounting_system.fixed.azimuth.value` == {aspect} & "+\
                f"`pv_module.technology` == '{pvtech}' & `pv_module.system_loss` == {loss}") if not is_empty(self.inputs) else None
        if is_empty(filtered) and request_if_none:
            pv_raw_data = request_PVGIS(angle=angle,
                                 aspect=aspect,
                                 pvtechchoice=pvtech,
                                 loss=loss,
                                 lat=lat,
                                 lon=lon,
                                 startyear=datayear,
                                 endyear=datayear,
                                 datatype=datatype)
            if save_if_none:
                data_key = json_normalize(pv_raw_data['inputs'])
                data_key['outputs'] = uuid.uuid4().hex
                data_key['data.year'] = datayear       
                data_key['data.type'] = datatype
                data_key['data.timestamp'] = time.time()
                self.to_storage(data_key, pv_raw_data['outputs'])
            return _serie(pv_raw_data['outputs'], datatype=datatype)
        else:
            # filtered = filtered.sort_values(by='data.timestamp', ascending=False)
            return _serie(self.from_storage(filtered.iloc[0]), datatype=datatype)      
        
class Cache:
    def __init__(self, storage='./', use_pickle=True):
        self.storage_file = os.path.join(storage, f"cache{'.pickle' if use_pickle else '.json'}")
        self.module = pickle if use_pickle else json
        self.load()

    def load(self):
        if os.path.exists(self.storage_file):
            with open(self.storage_file, 'r' if '.json' in self.storage_file else 'rb') as fp:
                self.storage = self.module.load(fp)
        else:
            self.storage = {}
        
    def save(self):
        with open(self.storage_file, 'w' if '.json' in self.storage_file else 'wb') as fp:
            self.module.dump(self.storage, fp, protocol=pickle.HIGHEST_PROTOCOL)
            
    def get_cached_solution(self, key, calc_if_none_method=None):
        if key in self.storage:
            return self.storage[key]
        elif calc_if_none_method:
            self.storage[key] = calc_if_none_method()
            return self.storage[key]
        