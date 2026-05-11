#!/usr/bin/env python3
"""
Extract DJF days with T2m <= -2 sigma at the nearest grid point to a given location.

Usage:
  python extract_cao_point.py --lat LAT --lon LON [--out FILE]

  --lat   Latitude in decimal degrees (°N)
  --lon   Longitude in decimal degrees; negative values treated as °W
  --out   Output CSV path (default: cao_days_<lat>_<lon>.csv)

Output CSV columns:
  date            - calendar date (YYYY-MM-DD)
  T2m_C           - raw 2-m temperature in Celsius
  T2m_clim_C      - smoothed climatological mean in Celsius (21-day running mean)
  clim_ref_period - reference period used to compute the climatology (e.g. "1979-2020")
  t2m_stdanom     - standardized anomaly (sigma, using smoothed climatology)
  blob            - 1 if a tracked CAO blob exists at this point on this day, 0 otherwise
"""

import argparse
import os
import sys
import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cao_utils import load_namelist

THRESHOLD = -2.0   # sigma

def main():
    parser = argparse.ArgumentParser(description="Extract CAO days at a grid point.")
    parser.add_argument("--lat", type=float, required=True,
                        help="Latitude in decimal degrees (°N)")
    parser.add_argument("--lon", type=float, required=True,
                        help="Longitude in decimal degrees (negative = °W)")
    parser.add_argument("--out", type=str, default=None,
                        help="Output CSV path")
    args = parser.parse_args()

    lat = args.lat
    lon = args.lon % 360.0   # normalize to 0-360
    cfg = load_namelist()
    scratch = cfg["SCRATCH_ROOT"]
    yr_start = int(cfg["DEC_YEAR_START"])
    yr_end   = int(cfg["DEC_YEAR_END"])

    # default output name encodes the requested coordinates
    if args.out:
        out_path = args.out
    else:
        lat_tag = f"{lat:.2f}N"
        lon_tag = f"{lon:.2f}E"
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                f"cao_days_{lat_tag}_{lon_tag}.csv")

    anom_dir  = os.path.join(scratch, "std_anom")
    blob_dir  = os.path.join(scratch, "blobs_reproduced")

    rows = []

    for dec_yr in range(yr_start, yr_end + 1):
        anom_file = os.path.join(anom_dir,  f"stdanom_djf_{dec_yr}_{dec_yr+1}.nc")
        blob_file = os.path.join(blob_dir,  f"blobs_{dec_yr}_{dec_yr+1}.nc")

        if not os.path.exists(anom_file):
            continue
        if not os.path.exists(blob_file):
            print(f"Warning: blob file missing for {dec_yr}-{dec_yr+1}, skipping", file=sys.stderr)
            continue

        ds_a = xr.open_dataset(anom_file)
        ds_b = xr.open_dataset(blob_file)

        # Nearest-neighbor selection to requested grid point
        anom_pt = ds_a[["t2m_stdanom", "t2m_raw", "clim_mean"]].sel(
            lat=lat, lon=lon, method="nearest"
        )
        blob_pt = ds_b["BLOB_t2m_stdanom"].sel(
            lat=lat, lon=lon, method="nearest"
        )

        # prefer attribute embedded in file; fall back to namelist for older files
        clim_ref = ds_a.attrs.get("clim_ref_period") or (
            f"{cfg.get('REF_PERIOD_START') or yr_start}-{cfg.get('REF_PERIOD_END') or yr_end}"
        )

        stdanom   = anom_pt["t2m_stdanom"].values   # (time,)
        t2m_raw   = anom_pt["t2m_raw"].values       # (time,) in Kelvin
        clim_mean = anom_pt["clim_mean"].values     # (time,) in Kelvin
        blob_id   = blob_pt.values                  # (time,) integer
        times     = pd.to_datetime(anom_pt["time"].values)

        # Filter to days where anomaly <= threshold
        cold_mask = stdanom <= THRESHOLD

        # any blob ID > 0 means a tracked CAO (size/duration/overlap filtered) is present
        for i, date in enumerate(times):
            if not cold_mask[i]:
                continue
            rows.append({
                "date":            date.strftime("%Y-%m-%d"),
                "T2m_C":           round(float(t2m_raw[i]) - 273.15, 2),
                "T2m_clim_C":      round(float(clim_mean[i]) - 273.15, 2),
                "clim_ref_period": clim_ref,
                "t2m_stdanom":     round(float(stdanom[i]), 3),
                "blob":            1 if int(blob_id[i]) > 0 else 0,
            })

        ds_a.close()
        ds_b.close()

    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)
    # Report the actual snapped grid point using the first file found
    first_anom = os.path.join(anom_dir, f"stdanom_djf_{yr_start}_{yr_start+1}.nc")
    with xr.open_dataset(first_anom) as ds_check:
        snap_lat = float(ds_check.lat.sel(lat=lat, method="nearest").values)
        snap_lon = float(ds_check.lon.sel(lon=lon, method="nearest").values)

    print(f"Requested: ({lat:.4f}°N, {args.lon:.4f}°)  →  snapped to grid point ({snap_lat}°N, {snap_lon}°E)")
    print(f"Wrote {len(df)} rows to {out_path}")
    print(f"  Days with blob: {df['blob'].sum()}  |  Days without blob: {(df['blob'] == 0).sum()}")

if __name__ == "__main__":
    main()
