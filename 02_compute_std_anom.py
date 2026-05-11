"""
Step 2: Compute standardized T2m anomalies for each DJF season.

Method (Stone et al. 2025 / Grumm & Hart 2001):
  1. Load all 42 NDJFM seasons (Nov + DJF + Mar) to provide shoulder months
  2. Detrend: remove linear trend across years at each grid point / calendar day
  3. Compute raw climatological mean and stddev across years for each calendar day
  4. Apply 21-day running mean to both — using actual Nov/Mar values at the edges
     instead of a circular DJF wrap, so Dec 1-10 and Feb 18-28 see real neighbors
  5. Standardize DJF portion: (T2m_detrended − clim_mean) / clim_std
  6. Save one DJF-only file per season

Input:  /glade/derecho/scratch/zarzycki/CAO/daily_t2m/t2m_{YYYY}_{MM}.nc  (individual monthly files)
Output: /glade/derecho/scratch/zarzycki/CAO/std_anom/stdanom_djf_{Y}_{Y+1}.nc
"""

import argparse
import xarray as xr
import numpy as np
import os

from cao_utils import load_namelist, ensure_ascending_lat

NL = load_namelist()

parser = argparse.ArgumentParser()
parser.add_argument(
    "--detrend",
    choices=["per_doy", "single_slope"],
    default=NL.get("DETREND", "single_slope"),
    help=(
        "single_slope: one OLS trend across the full concatenated DJF series per grid cell (default); "
        "per_doy: separate OLS trend for each calendar-day position across years per grid cell"
    ),
)
parser.add_argument(
    "--overwrite",
    action="store_true",
    default=False,
    help="Overwrite existing output files instead of skipping them.",
)
parser.add_argument(
    "--ref_period",
    nargs=2,
    type=int,
    metavar=("START", "END"),
    default=([int(NL["REF_PERIOD_START"]), int(NL["REF_PERIOD_END"])]
             if NL.get("REF_PERIOD_START") and NL.get("REF_PERIOD_END") else None),
    help=(
        "Dec-year range (inclusive) used to compute the climatological mean and std. "
        "Example: --ref_period 1980 2010 uses DJF 1980-81 through DJF 2010-11. "
        "Defaults to all available years."
    ),
)
args = parser.parse_args()
print(f"Detrend method: {args.detrend}")

MON_DIR  = os.path.join(NL["SCRATCH_ROOT"], "daily_t2m")
OUT_DIR  = os.path.join(NL["SCRATCH_ROOT"], "std_anom")
DIAG_DIR = os.path.join(NL["SCRATCH_ROOT"], "diagnostics")
os.makedirs(OUT_DIR,  exist_ok=True)
os.makedirs(DIAG_DIR, exist_ok=True)

# lat subsetting
LAT_MIN = float(NL["LAT_MIN"])
LAT_MAX = float(NL["LAT_MAX"])

DEC_YEARS = list(range(int(NL["DEC_YEAR_START"]), int(NL["DEC_YEAR_END"]) + 1))
N_YEARS   = len(DEC_YEARS)
HALF_WIN  = int(NL["HALF_WIN"])
NOV_DAYS  = 30                       # November always has 30 days (used to slice DJF from NDJFM)
MAR_DAYS  = 31                       # March always has 31 days (used to slice DJF from NDJFM)

def load_months(year_month_list):
    """Load monthly files for the given (year, month) pairs, subset to analysis
    domain, and return a concatenated (days, lat, lon) float32 array."""
    arrays = []
    for yr, mo in year_month_list:
        f = f"{MON_DIR}/t2m_{yr:04d}_{mo:02d}.nc"
        ds = ensure_ascending_lat(xr.open_dataset(f))
        da = ds["T2m"].sel(lat=slice(LAT_MIN, LAT_MAX))  # ascending lat: low→high
        arrays.append(da.values.astype(np.float32))
        ds.close()
    return np.concatenate(arrays, axis=0)   # (days, lat, lon)

# ── 1. Load all NDJFM seasons into (year × day × lat × lon) ───────────────
print("Loading all NDJFM seasons from monthly files ...")
seasons = []
for dec_year in DEC_YEARS:
    jan_year = dec_year + 1
    season = load_months([
        (dec_year, 11), (dec_year, 12),
        (jan_year,  1), (jan_year,  2), (jan_year,  3),
    ])
    seasons.append(season)
    if dec_year % 10 == 9:
        print(f"  Loaded through {dec_year}-{jan_year} ({season.shape[0]} days)")

n_days_per = [s.shape[0] for s in seasons]  # 151 non-leap, 152 leap
N_DAYS = max(n_days_per)  # pad all seasons to this length so they stack into a regular array
print(f"  NDJFM day counts: {min(n_days_per)} – {max(n_days_per)}, max={N_DAYS}")

# DJF length for each year (total minus Nov and Mar shoulders)
n_djf_per = [nd - NOV_DAYS - MAR_DAYS for nd in n_days_per]  # 90 or 91

# Read lat/lon from the first monthly file after applying the lat subset
ds0 = ensure_ascending_lat(xr.open_dataset(f"{MON_DIR}/t2m_1979_01.nc"))
ds0_sub = ds0.sel(lat=slice(LAT_MIN, LAT_MAX))  # ascending lat: low→high
lats = ds0_sub["lat"].values
lons = ds0_sub["lon"].values
ds0.close()
NLAT, NLON = len(lats), len(lons)

# Allocate with NaN; non-leap years have NaN at the Feb-29 index
data = np.full((N_YEARS, N_DAYS, NLAT, NLON), np.nan, dtype=np.float32)
for i, s in enumerate(seasons):
    nd = s.shape[0]
    data[i, :nd, :, :] = s

# ── 2. Detrend ────────────────────────────────────────────────────────────
print("Detrending ...")
data_detrended = data.copy()

if args.detrend == "per_doy":
    # Per-calendar-day: fit a separate trend across the N_YEARS same-day values at each
    # grid point.  Trend is centered at the mean year so ~year 2000 is unchanged.
    years = np.array(DEC_YEARS, dtype=np.float64)

    # Flatten to nyr, nday, ncol
    flat  = data.reshape(N_YEARS, N_DAYS, NLAT * NLON)

    # Accumulate per-day slopes for diagnostics (K/year per grid cell)
    all_slopes_gh = np.full((N_DAYS, NLAT * NLON), np.nan, dtype=np.float64)

    # Loop over all days
    for d in range(N_DAYS):

        # Get nyrs x ncol for a given day
        col = flat[:, d, :]

        # Only use years that have data at this day (non-leap years lack Feb 29)
        yr_ok = ~np.isnan(col[:, 0])

        # If we have less than 2 valid years, can't fit a line
        if yr_ok.sum() < 2:
            continue
        # Keep only grid cells with valid data across all selected years
        valid = ~np.any(np.isnan(col[yr_ok, :]), axis=0)
        n_invalid = np.sum(~valid)
        if n_invalid > 0:
            print(
                f"  Warning: day {d+1} excluded {n_invalid} grid cells "
                f"with NaNs across years"
            )
        if not np.any(valid):
            continue

        # Remove any invalid years
        yrs_sub = years[yr_ok]
        Y       = col[yr_ok, :][:, valid]

        # OLS slope: cov(year, T) / var(year), vectorized over all grid cells at once
        slopes  = (np.dot((yrs_sub - yrs_sub.mean()), Y - Y.mean(axis=0)) /
                   np.sum((yrs_sub - yrs_sub.mean())**2))
        trend   = np.outer(yrs_sub - yrs_sub.mean(), slopes)
        all_slopes_gh[d, valid] = slopes  # save for diagnostics (K/year)

        # Clone the OG flattened array for this calendar day
        flat_d = flat[:, d, :].copy()
        # Takes only the years with data
        tmp = flat_d[yr_ok, :]
        # Remove trend
        tmp[:, valid] = tmp[:, valid] - trend
        # Stick tmp back into relevant years of the OG array (leaving in place raw data not detrended)
        flat_d[yr_ok, :] = tmp
        # Repackage back to data_detrended
        data_detrended[:, d, :, :] = flat_d.reshape(N_YEARS, NLAT, NLON)

        if d % 10 == 0:
            print(f"  Detrended day {d+1}/{N_DAYS}")

elif args.detrend == "single_slope":
    # Single OLS linear trend fitted across the full concatenated DJF time series
    # (~N_YEARS × 90 days) at each grid cell simultaneously, matching MATLAB's
    # permute/detrend/ipermute temporal detrend.  Removes both slope and grand mean
    # (zero-mean result).  Nov/Mar shoulder months are left as raw data (running-mean
    # buffers only).

    # Concatenate DJF portions across all seasons in chronological order
    djf_parts = [
        data[i, NOV_DAYS:NOV_DAYS + n_djf_per[i], :, :].astype(np.float64)
        for i in range(N_YEARS)
    ]
    djf_cat     = np.concatenate(djf_parts, axis=0)  # (N_djf_total, NLAT, NLON)
    N_djf_total = djf_cat.shape[0]
    flat_djf    = djf_cat.reshape(N_djf_total, NLAT * NLON)

    t = np.arange(N_djf_total, dtype=np.float64)
    t -= t.mean()   # center; mid-series values unchanged

    djf_grand_mean = flat_djf.mean(axis=0).reshape(NLAT, NLON)  # (NLAT, NLON)
    slopes = np.dot(t, flat_djf - djf_grand_mean.ravel()) / np.dot(t, t)
    # slopes[g]: K per DJF-day at grid cell g

    # Remove trend only (not the grand mean) from the DJF portion of each season.
    # Keeping the grand mean intact ensures Nov/Mar shoulders and DJF are on the
    # same temperature scale, so the 21-day running-mean climatology is smooth
    # across the Nov/Dec and Feb/Mar boundaries.  clim_mean_smooth absorbs the
    # mean in the anomaly calculation regardless, so the final standardized
    # anomalies are identical either way.
    data_detrended = data.copy().astype(np.float64)
    djf_pos = 0
    for i in range(N_YEARS):
        n_djf = n_djf_per[i]
        t_c   = t[djf_pos:djf_pos + n_djf]
        data_detrended[i, NOV_DAYS:NOV_DAYS + n_djf, :, :] -= (
            np.outer(t_c, slopes).reshape(n_djf, NLAT, NLON)
        )
        djf_pos += n_djf

    # Keep float64 through clim_std computation; cast to float32 at output time.
    print(f"  Stone DJF-series detrend complete "
          f"({N_djf_total} DJF days across {N_YEARS} seasons)")


# ── 2b. Trend diagnostic ──────────────────────────────────────────────────
# Express trend as K/decade so the two methods are directly comparable.
#
# grumm_hart slopes: K/year     → × 10
# stone slopes:      K/DJF-day  → × (N_djf_total/N_YEARS) × 10
#
# NOTE: only the slope is removed (not the grand mean), so Nov/Mar shoulders
# and DJF data stay on the same temperature scale for the running-mean clim step.
print("Computing trend diagnostics ...")

if args.detrend == "per_doy":
    # Mean slope across all calendar day positions (K/year → K/decade)
    trend_kperdecade = np.nanmean(all_slopes_gh, axis=0).reshape(NLAT, NLON) * 10.0
    trend_note = "mean across calendar-day slopes (K/decade)"

elif args.detrend == "single_slope":
    # slopes is K/DJF-day; mean DJF season length ≈ N_djf_total/N_YEARS days/yr
    djf_days_per_yr = N_djf_total / N_YEARS
    trend_kperdecade = slopes.reshape(NLAT, NLON) * djf_days_per_yr * 10.0
    trend_note = f"single DJF-series slope scaled to K/decade (~{djf_days_per_yr:.2f} DJF days/yr)"

flat_t = trend_kperdecade[np.isfinite(trend_kperdecade)]
print(f"  Method: {args.detrend} — {trend_note}")
print(f"  Trend removed (K/decade) over {N_YEARS}-yr record:")
print(f"    Mean   : {flat_t.mean():.4f}")
print(f"    Median : {np.median(flat_t):.4f}")
print(f"    Std    : {flat_t.std():.4f}")
print(f"    P5–P95 : {np.percentile(flat_t,  5):.4f}  to  {np.percentile(flat_t, 95):.4f}")
print(f"    Min/Max: {flat_t.min():.4f}  /  {flat_t.max():.4f}")

da_trend = xr.DataArray(
    trend_kperdecade.astype(np.float32),
    dims=["lat", "lon"],
    coords={"lat": lats, "lon": lons},
    name="trend_kperdecade",
)
da_trend.attrs["long_name"] = f"Linear trend removed ({args.detrend}) in K/decade"
da_trend.attrs["units"] = "K/decade"
da_trend.attrs["detrend_method"] = args.detrend
trend_fname = f"{DIAG_DIR}/trend_removed_{args.detrend}.nc"
da_trend.to_dataset().to_netcdf(
    trend_fname,
    encoding={"trend_kperdecade": {"dtype": "float32", "zlib": True, "complevel": 4}},
)
print(f"  Saved: {trend_fname}")


# ── 3. Climatological mean and stddev across years for every calendar day ──
print("Computing climatology ...")
print("data_detrended shape:", data_detrended.shape)

if args.ref_period is not None:
    ref_start, ref_end = args.ref_period
    ref_mask = np.array([ref_start <= y <= ref_end for y in DEC_YEARS])
    if ref_mask.sum() < 2:
        raise ValueError(
            f"--ref_period {ref_start}–{ref_end} matches only {ref_mask.sum()} year(s); need at least 2"
        )
    clim_data = data_detrended[ref_mask]
    print(f"  Climatology reference period: {ref_start}–{ref_end} ({ref_mask.sum()} of {N_YEARS} years)")
else:
    clim_data = data_detrended
    print(f"  Climatology reference period: all {N_YEARS} years")

# nanmean/nanstd handles the NaN at Feb 29 for non-leap years gracefully
clim_mean = np.nanmean(clim_data, axis=0)  # (N_DAYS, lat, lon)
clim_std  = np.nanstd(clim_data, axis=0, ddof=1)
print("clim_mean shape:", clim_mean.shape)
print("clim_std shape:", clim_std.shape)

# ── 4. 21-day running mean — non-circular, uses actual Nov/Mar at edges ────
print("Applying 21-day running mean to climatology ...")

def running_mean(arr, half_win):
    # No circular wrap: at the array edges the window is simply truncated.
    # Because arr spans NDJFM, the DJF interior days always have a full 21-day
    # window of real Nov/Mar data; only the outermost Nov/Mar days are truncated,
    # and those are never used in the final DJF output.
    n = arr.shape[0]
    result = np.zeros_like(arr)
    for i in range(n):
        lo = max(0, i - half_win)
        hi = min(n, i + half_win + 1)
        result[i] = np.nanmean(arr[lo:hi], axis=0)
    return result

clim_mean_smooth = running_mean(clim_mean, HALF_WIN)
clim_std_smooth  = running_mean(clim_std,  HALF_WIN)

# Identify where smoothed std falls below floor before clipping (diagnostic mask)
std_clip_mask = (clim_std_smooth < 0.01).astype(np.int8)  # 1 = was clipped to NaN; rare over open ocean

# Prevent division by near-zero std at any isolated grid cells
clim_std_smooth = np.where(clim_std_smooth < 0.01, np.nan, clim_std_smooth)


# ── 4b. Save climatology diagnostics ──────────────────────────────────────
print("Saving climatology diagnostics ...")

# Day coordinate spans the full NDJFM array (0-based index)
ndjfm_day = np.arange(N_DAYS, dtype=np.int32)

def _save_clim(arr, name, long_name, units, fname):
    da = xr.DataArray(
        arr.astype(np.float32),
        dims=["ndjfm_day", "lat", "lon"],
        coords={"ndjfm_day": ndjfm_day, "lat": lats, "lon": lons},
        name=name,
    )
    da.attrs["long_name"] = long_name
    da.attrs["units"] = units
    da.attrs["ndjfm_day_note"] = "day index 0=Nov 1; DJF starts at index 30"
    enc = {name: {"dtype": "float32", "zlib": True, "complevel": 4}}
    da.to_dataset().to_netcdf(f"{DIAG_DIR}/{fname}", encoding=enc)
    print(f"  Saved: {DIAG_DIR}/{fname}")

_save_clim(clim_mean,        "clim_mean",        "Raw climatological mean (detrended)",            "K",     "clim_mean_raw.nc")
_save_clim(clim_std,         "clim_std",         "Raw climatological std (detrended)",             "K",     "clim_std_raw.nc")
_save_clim(clim_mean_smooth, "clim_mean_smooth", "21-day smoothed climatological mean",            "K",     "clim_mean_smooth.nc")
_save_clim(clim_std_smooth,  "clim_std_smooth",  "21-day smoothed climatological std (clipped)",  "K",     "clim_std_smooth.nc")

# Mask file uses int8; save separately so encoding matches
da_mask = xr.DataArray(
    std_clip_mask,
    dims=["ndjfm_day", "lat", "lon"],
    coords={"ndjfm_day": ndjfm_day, "lat": lats, "lon": lons},
    name="std_clip_mask",
)
da_mask.attrs["long_name"] = "1 where smoothed std < 0.01 K and was set to NaN"
da_mask.attrs["units"] = "1"
da_mask.attrs["ndjfm_day_note"] = "day index 0=Nov 1; DJF starts at index 30"
da_mask.to_dataset().to_netcdf(
    f"{DIAG_DIR}/std_clip_mask.nc",
    encoding={"std_clip_mask": {"dtype": "int8", "zlib": True, "complevel": 4}},
)
print(f"  Saved: {DIAG_DIR}/std_clip_mask.nc")


# ── 5. Standardize and save — DJF portion only ────────────────────────────
print("Computing and saving standardized anomalies ...")
for i, dec_year in enumerate(DEC_YEARS):
    outfile = f"{OUT_DIR}/stdanom_djf_{dec_year}_{dec_year+1}.nc"
    if os.path.exists(outfile):
        if args.overwrite:
            os.remove(outfile)
            print(f"  Exists, overwriting: {outfile}")
        else:
            print(f"  Exists, skipping: {outfile}")
            continue

    jan_year = dec_year + 1
    nd_djf = n_djf_per[i]
    # DJF sits after November in the extended array
    djf_start = NOV_DAYS
    djf_end   = djf_start + nd_djf

    clim_mean_djf = clim_mean_smooth[djf_start:djf_end]   # (nd_djf, lat, lon)
    clim_std_djf  = clim_std_smooth[djf_start:djf_end]    # (nd_djf, lat, lon)

    anom = (data_detrended[i, djf_start:djf_end] - clim_mean_djf) / clim_std_djf

    # Build DJF time coordinate by reading timestamps directly from the monthly files
    times = np.concatenate([
        xr.open_dataset(f"{MON_DIR}/t2m_{dec_year:04d}_12.nc")["time"].values,
        xr.open_dataset(f"{MON_DIR}/t2m_{jan_year:04d}_01.nc")["time"].values,
        xr.open_dataset(f"{MON_DIR}/t2m_{jan_year:04d}_02.nc")["time"].values,
    ])

    coords = {"time": times, "lat": lats, "lon": lons}
    dims   = ["time", "lat", "lon"]
    enc_f32 = {"dtype": "float32", "zlib": True, "complevel": 4}

    def _da(arr, name, long_name, units):
        da = xr.DataArray(arr.astype(np.float32), dims=dims, coords=coords, name=name)
        da.attrs.update({"long_name": long_name, "units": units})
        return da

    clim_ref_start = args.ref_period[0] if args.ref_period else int(NL["DEC_YEAR_START"])
    clim_ref_end   = args.ref_period[1] if args.ref_period else int(NL["DEC_YEAR_END"])

    ds = xr.Dataset({
        "t2m_stdanom":   _da(anom,
                             "t2m_stdanom",   "Standardized 2m temperature anomaly",         "sigma"),
        "t2m_raw":       _da(data[i, djf_start:djf_end],
                             "t2m_raw",       "Raw daily 2m temperature",                    "K"),
        "t2m_detrended": _da(data_detrended[i, djf_start:djf_end],
                             "t2m_detrended", "Detrended 2m temperature", "K"),
        "clim_mean":     _da(clim_mean_djf,
                             "clim_mean",     "Smoothed climatological mean (detrended)",    "K"),
        "clim_std":      _da(clim_std_djf,
                             "clim_std",      "Smoothed climatological std (detrended)",     "K"),
    })
    ds.attrs["clim_ref_period"]    = f"{clim_ref_start}-{clim_ref_end}"
    ds.attrs["clim_ref_dec_start"] = clim_ref_start
    ds.attrs["clim_ref_dec_end"]   = clim_ref_end
    ds.attrs["detrend_method"]     = args.detrend
    ds.attrs["clim_smooth_halfwin"]= HALF_WIN
    ds.attrs["lat_bounds"]         = f"{LAT_MIN}-{LAT_MAX}N"
    ds.attrs["record_dec_years"]   = f"{DEC_YEARS[0]}-{DEC_YEARS[-1]}"

    enc = {v: enc_f32 for v in ds.data_vars}
    ds.to_netcdf(outfile, encoding=enc)
    print(f"  Saved: {outfile}")

print("Step 2 complete.")
