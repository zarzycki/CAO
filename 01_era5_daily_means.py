"""
Step 1: Read ERA5 hourly T2m, compute daily means, save one file per calendar month.

  Output: /glade/derecho/scratch/zarzycki/CAO/daily_t2m/t2m_{YYYY}_{MM:02d}.nc
  Domain: global (no lat clipping — subsetting is applied in step 2)

  Range: 1979-01 through 2021-03
    - Full years 1979-2020 support the stone_orig annual-cycle detrend
    - Nov/Mar shoulder months (1979-11, 2021-03) support the NDJFM running mean

Usage:
  python3 01_era5_daily_means.py YYYY MM    # one month
  python3 01_era5_daily_means.py            # all months in range
"""

import xarray as xr
import glob
import os
import sys

def _load_namelist():
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

NL = _load_namelist()

ERA5_SFC = NL["ERA5_SFC"]
OUT_DIR  = os.path.join(NL["SCRATCH_ROOT"], "daily_t2m")
os.makedirs(OUT_DIR, exist_ok=True)

# Return the path to the ERA5 T2m hourly netCDF for the given year/month
def era5_t2m_file(year, month):
    # ERA5 2m temperature: ECMWF parameter 128_167, 0.25-degree surface analysis
    pattern = (f"{ERA5_SFC}/{year:04d}{month:02d}/"
               f"e5.oper.an.sfc.128_167_2t.ll025sc.{year:04d}{month:02d}*.nc")
    matches = glob.glob(pattern)
    if not matches:
        raise FileNotFoundError(f"No ERA5 T2m file found: {pattern}")
    return matches[0]

# Compute daily-mean T2m for one calendar month and write a compressed netCDF
def process_month(year, month):
    outfile = f"{OUT_DIR}/t2m_{year:04d}_{month:02d}.nc"
    if os.path.exists(outfile):
        print(f"Exists, skipping: {outfile}")
        return

    print(f"Processing {year:04d}-{month:02d} ...")
    ds = xr.open_dataset(era5_t2m_file(year, month))

    # Collapse 24 hourly values per calendar day into a single daily mean
    da = ds["VAR_2T"].resample(time="1D").mean(dim="time")

    # Cleanup
    ds.close()

    # Write output
    out = da.to_dataset(name="T2m")  # promote DataArray to Dataset for netCDF output

    # Add attributes
    out["T2m"].attrs.update({"long_name": "2m temperature daily mean", "units": "K"})

    # Rename coordinate names lat/lon to not deal with ERA5
    out = out.rename({"latitude": "lat", "longitude": "lon"})
    if out["lat"].values[0] > out["lat"].values[-1]:
        print("Latitude detected as decreasing, flipping!")
        out = out.isel(lat=slice(None, None, -1))  # flip descending lat to ascending (-90→90)

    # float32 + zlib level 4 gives ~4× compression with negligible precision loss for T2m
    out.to_netcdf(outfile, encoding={"T2m": {"dtype": "float32", "zlib": True, "complevel": 4}})
    print(f"  Saved: {outfile}")

# Accept YYYY MM as arguments for parallel execution; no args = full range
if len(sys.argv) == 3:
    process_month(int(sys.argv[1]), int(sys.argv[2]))
elif len(sys.argv) == 1:
    for year in range(int(NL["DEC_YEAR_START"]), int(NL["DEC_YEAR_END"]) + 2):
        for month in range(1, 13):
            process_month(year, month)
else:
    print("Usage: 01_era5_daily_means.py [YYYY MM]")
    sys.exit(1)

print("Step 1 complete.")
