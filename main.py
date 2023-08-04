import json, time, uuid, os
import pandas as pd, numpy as np

from utils import get_nominal_pv

if __name__ == "__main__":

    nom_pv = get_nominal_pv(angle=1.0)
    print(nom_pv)
