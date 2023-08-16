import json, time, requests, uuid, os, datetime, jsonpickle
import pandas as pd, numpy as np
from pandas import json_normalize

def is_empty(x):
    if isinstance(x, (list, dict, str, pd.DataFrame)):
        return len(x) == 0
    return pd.isna(x)

def to_json(obj):
        return jsonpickle.encode(obj)

def from_json(json_data):
        return jsonpickle.decode(json_data)

def _timestamp(x):
    return time.mktime(datetime.datetime.strptime(x, "%Y%m%d:%H%M").timetuple())

def _serie(x, datatype='hourly', name='pv'):
    v = [(_timestamp(i['time']), i['P']) for i in x[datatype]]
    return pd.DataFrame(v).rename(columns={0:'timestamp', 1:name}).set_index('timestamp')

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

def get_nominal_pv(angle=0, aspect=0, pvtech='CIS', loss=14, lat=52.373, lon=9.738, datayear=2016, request_if_none=True, datatype='hourly', store='./'):
    # Watt per 1 kWp
    # {"P": {"description": "PV system power", "units": "W"}
    inputs_store = os.path.join(store, 'pv_inputs.csv')
    outputs_store = os.path.join(store, 'pv_outputs')
    os.makedirs(outputs_store, exist_ok=True)
    inputs = pd.read_csv(inputs_store, sep=';') if os.path.exists(inputs_store) else None
    filtered = inputs.query(
                f"`location.latitude` == {lat} & `location.longitude` == {lon} & "+\
                f"`data.type` == '{datatype}' & `data.year` == {datayear} & "+\
                f"`mounting_system.fixed.slope.value` == {angle} & "+\
                f"`mounting_system.fixed.azimuth.value` == {aspect} & "+\
                f"`pv_module.technology` == '{pvtech}' & `pv_module.system_loss` == {loss}") if not is_empty(inputs) else None
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
        data_key = json_normalize(pv_raw_data['inputs'])
        file_name = uuid.uuid4().hex + '.json'
        data_key['outputs'] = file_name
        data_key['data.year'] = datayear       
        data_key['data.type'] = datatype
        data_key['data.timestamp'] = time.time()
        with open(os.path.join(outputs_store, file_name), 'w') as outfile:
            json.dump(pv_raw_data['outputs'], outfile)
        pd.concat([inputs, data_key], ignore_index=True).to_csv(inputs_store, sep=';', index=False)
        return _serie(pv_raw_data['outputs'], datatype=datatype)
    else:
      filtered = filtered.sort_values(by='data.timestamp', ascending=False)
      with open(os.path.join(outputs_store, filtered.iloc[0]['outputs']), 'r') as infile:
            return _serie(json.load(infile), datatype=datatype)      