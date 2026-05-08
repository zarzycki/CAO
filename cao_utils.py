import os

def ensure_ascending_lat(ds):
    if ds["lat"].values[0] > ds["lat"].values[-1]:
        ds = ds.isel(lat=slice(None, None, -1))
    return ds

def load_namelist():
    base = os.path.dirname(os.path.abspath(__file__))
    cfg = {}
    for fname in ("namelist_defaults.sh", "namelist.sh"):
        fpath = os.path.join(base, fname)
        if not os.path.exists(fpath):
            continue
        with open(fpath) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, _, val = line.partition("=")
                cfg[key.strip()] = val.strip()
    return cfg
