# North American Cold Air Outbreak (CAO) Detection

Reproducing the CAO detection pipeline from:

> Stone, J., M. Gervais, K. A. Bowley, and C. Zarzycki, 2025: Identifying, Tracking, and Evaluating Mechanisms of North American Cold Air Outbreaks (CAOs) Using a Feature Tracking Approach. *Mon. Wea. Rev.*, **153**, 153–168.

---

## Quick-start workflow

If you're picking this up after a break, run steps in order. Each step has a skip-if-exists check so partial runs are safe to resume.

```bash
# Step 1 — ERA5 daily means (Casper, ~30 min)
qsub ~/CAO/sub_step1_casper.sh

# Step 2 — Standardized anomalies (Casper, ~30 min, needs ~12 GB RAM)
# Wait for step 1 to finish first
qsub ~/CAO/sub_step2_casper.sh

# Step 3 — DetectBlobs binary masks (Casper, ~10 min, 42 MPI ranks)
# Wait for step 2 to finish first
qsub ~/CAO/sub_step3_casper.sh

# Step 4 — StitchBlobs tracked events (Casper, ~5 min, serial)
# Wait for step 3 to finish first
qsub ~/CAO/sub_step4_casper.sh
```

**To start completely from scratch**, delete all intermediate outputs first:
```bash
rm /glade/derecho/scratch/zarzycki/CAO/daily_t2m/t2m_*.nc
rm /glade/derecho/scratch/zarzycki/CAO/std_anom/stdanom_djf_*.nc
rm /glade/derecho/scratch/zarzycki/CAO/binary_masks/mask_djf_*.nc
rm /glade/derecho/scratch/zarzycki/CAO/blobs_reproduced/blobs_*.nc
```

Check job status with `qstat -u $USER`.

---

## Directory layout

| Location | Contents |
|---|---|
| `~/CAO/` | Scripts and Python code (git-backed) |
| `/glade/derecho/scratch/zarzycki/CAO/daily_t2m/` | ERA5 daily means (step 1 output) |
| `/glade/derecho/scratch/zarzycki/CAO/std_anom/` | Standardized anomalies (step 2 output) |
| `/glade/derecho/scratch/zarzycki/CAO/binary_masks/` | Binary cold-air masks (step 3 output) |
| `/glade/derecho/scratch/zarzycki/CAO/blobs_reproduced/` | Tracked CAO blobs (step 4 output) |
| `/glade/derecho/scratch/zarzycki/CAO/logs/` | PBS job logs (steps 1 and 3) |
| `/glade/derecho/scratch/zarzycki/CAO/diagnostics/` | Trend and climatology diagnostics (step 2 output) |
| `/glade/campaign/collections/rda/data/d633000/` | ERA5 source data (RDA ds633.0) |
| `/glade/work/zarzycki/tempestextremes_casper/bin/` | TempestExtremes binaries (Casper build) |
| `/glade/work/zarzycki/tempestextremes/bin/` | TempestExtremes binaries (Derecho build) |

Reference blobs from paper authors: `/glade/derecho/scratch/zarzycki/CAO/blobs-2-1-1500-3-50/`

The filename encodes the final Stone et al. parameters: threshold=−2σ, radius=1°, minsize=1500, mintime=3 days, min_overlap=50%. The "50" is the **stitching overlap** parameter, not a land-fraction post-filter.

---

## Pipeline overview

```
ERA5 hourly T2m  →  [Step 1]  →  daily_t2m/t2m_{YYYY}_{MM}.nc  (one file per month)
daily_t2m/       →  [Step 2]  →  std_anom/stdanom_djf_*.nc  +  diagnostics/
std_anom/        →  [Step 3]  →  binary_masks/mask_djf_*.nc
binary_masks/    →  [Step 4]  →  blobs_reproduced/blobs_*.nc
```

---

## Step 1 — ERA5 daily means

**Script:** `01_era5_daily_means.py`  
**Submit:** `sub_step1_casper.sh` (Casper, 16 CPUs / 200 GB, GNU parallel)  
**Output:** `daily_t2m/t2m_{YYYY}_{MM}.nc` — one file per calendar month

Reads ERA5 hourly 2-m temperature (`VAR_2T`, ECMWF parameter 128_167) for each calendar month,
computes daily means, and writes a global (no lat clipping) compressed netCDF. Lat subsetting
is applied in step 2. Existing files are skipped. The submit script loops 1979–2024; step 2
only consumes months within DJF seasons 1979–80 through 2020–21 plus the Nov 1979 and Mar 2021
shoulder months.

To process a single month:
```bash
python3 ~/CAO/01_era5_daily_means.py 1984 12   # regenerates December 1984
```

---

## Step 2 — Detrend and standardize

**Script:** `02_compute_std_anom.py`  
**Submit:** `sub_step2_casper.sh` (Casper, 1 CPU / 200 GB)  
**Input:** `daily_t2m/t2m_ndjfm_*.nc`  
**Output:** `std_anom/stdanom_djf_{Y}_{Y+1}.nc`

Implements the Grumm & Hart (2001) standardization as adapted by Stone et al. (2025):

1. Load all 42 NDJFM seasons into memory as a `(year × day × lat × lon)` array
2. **Detrend** — at each grid point and calendar day, fit a linear regression across the 42 years and subtract the trend (removes the anthropogenic warming signal; trend is centered at ~year 2000 so values there are unchanged)
3. **Climatology** — compute mean and standard deviation across years for each calendar day
4. **Smooth** — apply a 21-day running mean to both, using actual Nov/Mar shoulder data at the DJF edges (no circular wrap)
5. **Standardize** — `(T2m_detrended − clim_mean_smooth) / clim_std_smooth`, output DJF days only

### Command-line options

| Flag | Arguments | Default | Description |
|---|---|---|---|
| `--detrend` | `single_slope` \| `per_doy` | `single_slope` | Detrending method applied before climatology (see below) |
| `--ref_period` | `START END` (Dec-years, inclusive) | all 42 years | Restrict climatological mean and std to this year range; detrending still uses all years |
| `--overwrite` | _(flag)_ | off | Recompute and overwrite existing output files; by default existing files are skipped |

The `START` and `END` values for `--ref_period` are **Dec-years**: `--ref_period 1980 2010` covers DJF 1980–81 through DJF 2010–11 (31 seasons). The full available range is 1979–2020.

```bash
# Default run (single_slope detrend, all-year climatology)
python3 ~/CAO/02_compute_std_anom.py

# Fixed 1981–2010 reference period
python3 ~/CAO/02_compute_std_anom.py --ref_period 1981 2010

# per_doy detrend with a custom reference period, overwriting any existing output
python3 ~/CAO/02_compute_std_anom.py --detrend per_doy --ref_period 1981 2010 --overwrite
```

> **Bug fixed (2025-04):** The original detrend loop used `col[0]` (DJF 1979–80, a leap year)
> to build the spatial validity mask. For day index 90 (Feb 29), this caused NaN rows from
> non-leap years to poison the regression via `Y.mean()`, setting all years at d=90 to NaN.
> That NaN then propagated through the circular running-mean padding into Dec 1–10 and
> Feb 18–28 (~23% of the season), producing no standardized anomalies for those dates.
> Fix: the detrend loop now subsets to years that have data at each day (`yr_ok` mask);
> the running-mean function uses `np.nanmean`. Shoulder months (step 1 NDJFM files) replaced
> the circular DJF wrap, giving correct edge behavior.

### Detrending options (`--detrend`)

Both options fit an ordinary least-squares (OLS) linear trend at each grid cell and subtract it, centering the fit so that mid-record values are unchanged. They differ in how the time axis is defined.

**`single_slope` (default)**

Concatenates all DJF days from every season into one continuous time series (~42 × 90 ≈ 3,780 days) and fits a single slope per grid cell. The time index is centered at its mean so values near the middle of the record are unchanged; the grand DJF mean is also removed, matching MATLAB's `detrend()` (`permute`/`detrend`/`ipermute`) behavior and producing a zero-mean result. Because the slope is estimated from ~3,780 samples the estimate is low-noise, but it assumes the warming rate is uniform across December, January, and February.

**`per_doy`**

Fits a separate OLS trend for each of the 152 NDJFM calendar-day positions using only the ≤42 year-values that contain that day (non-leap years lack Feb 29). The time axis is the decimal year, centered at its mean (~2000), so the per-season mean is preserved. Each slope is estimated from only ~42 samples, making individual day-position estimates noisier than `single_slope`; the 21-day running-mean smoothing applied to the climatology in step 4 partially mitigates this. This formulation allows the warming rate to vary by calendar day, which matters if December and February are not warming at the same rate.

The removed trend field (K/decade, scaled from the raw OLS slope) is written to `diagnostics/trend_removed_{method}.nc` for both options.

---

## Step 3 — DetectBlobs

**Script:** `sub_step3_casper.sh` (Casper, 1 node / 24 CPUs / 160 GB, Genoa)  
**Binary:** `/glade/work/zarzycki/tempestextremes_casper/bin/DetectBlobs`  
**Input:** `std_anom/stdanom_djf_*.nc`  
**Output:** `binary_masks/mask_djf_{Y}_{Y+1}.nc`

Runs TempestExtremes `DetectBlobs` via MPI (24 ranks) using file lists. The submit script loops
1979–2023 but only the 42 seasons produced by step 2 (1979–2020) will have input files present.
Parameters follow Stone et al. (2025):

| Parameter | Value | How specified |
|---|---|---|
| Threshold | ≤ −2σ | `--thresholdcmd "t2m_stdanom,<=,-2,1"` |
| Radius of influence | 1° | `dist=1` in thresholdcmd (last field) |
| Tag variable | `binary_tag` | `--tagvar binary_tag` |

The `dist=1` in the thresholdcmd flags all cells within 1 great-circle degree of any cell
meeting the −2σ threshold, effectively dilating the detected regions outward by 1°.

> Derecho alternative: `sub_step3_derecho.sh` — uses `cray-mpich` and the Derecho build
> at `/glade/work/zarzycki/tempestextremes/bin/`.

---

## Step 4 — StitchBlobs

**Script:** `sub_step4_casper.sh` (Casper, 1 CPU / 10 GB, serial)  
**Binary:** `/glade/work/zarzycki/tempestextremes_casper/bin/StitchBlobs`  
**Input:** `binary_masks/mask_djf_*.nc`  
**Output:** `blobs_reproduced/blobs_{Y}_{Y+1}.nc`

Runs TempestExtremes `StitchBlobs` serially, passing all 42 seasons via `--in_list` /
`--out_list` in a single call. Parameters follow Stone et al. (2025):

| Parameter | Value |
|---|---|
| Regional domain | `--regional` |
| Input variable | `binary_tag` |
| Output variable | `BLOB_t2m_stdanom` |
| Min size | 1500 grid cells per day |
| Min duration | 3 days |
| Min overlap (prev) | 50% |

> **Important:** The compiled `StitchBlobs` source defaults `min_overlap_prev` to **0%**.
> The 50% overlap **must be passed explicitly** or results will not match the paper.
> `--min_overlap_next` is intentionally **not** set (reference script only uses `min_overlap_prev`).
> `--regional` is required because the ERA5 input is a 25–90°N latitude subset, not a full global grid.

> Derecho alternative: `sub_step4_derecho.sh` — uses the Derecho build and `cray-mpich`.

---

## Environment

### Python (steps 1–2)

**On NCAR systems (Casper/Derecho)** — the `npl` environment already has everything needed:
```bash
module load conda
conda activate npl
```

**Anywhere else** — create a minimal environment from the provided YAML:
```bash
conda env create -f environment.yml   # creates the 'cao' environment
conda activate cao
```

To update an existing `cao` environment after pulling changes:
```bash
conda env update -f environment.yml --prune
```

Python dependencies (see `environment.yml`):

| Package | Role |
|---|---|
| `numpy` | Array operations and OLS detrending in step 2 |
| `xarray` | Reading/writing netCDF; daily-mean computation in step 1 |
| `netcdf4` | Primary netCDF I/O backend for xarray |
| `h5netcdf` | HDF5/netCDF4 alternative backend; required for some ERA5 files |

### TempestExtremes (steps 3–4)

Pre-built binaries are at `/glade/work/zarzycki/tempestextremes_casper/bin/` (Casper) and
`/glade/work/zarzycki/tempestextremes/bin/` (Derecho). The submit scripts load the required
module stack automatically:
```
ncarenv / ncarcompilers / intel / openmpi / netcdf
```

TempestExtremes source: `/glade/work/zarzycki/tempestextremes_casper/` (Casper build)  
TempestExtremes docs: https://climate.ucdavis.edu/tempestextremes.php  
Reference paper: `~/CAO/mwre-MWR-D-23-0265.1.pdf`  
Grumm & Hart 2001 (standardization method): `~/CAO/grumm2001.pdf`
