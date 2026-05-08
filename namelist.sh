#!/usr/bin/env false
# CAO pipeline user namelist.
# Only keys that differ from namelist_defaults.sh need to be listed here.
# Scripts load namelist_defaults.sh first, then this file on top — last value wins.
# Format: KEY=VALUE  (no spaces around =, bash-sourceable)

# ── Paths (required — update for your system) ──────────────────────────────
ERA5_SFC=/glade/campaign/collections/rda/data/d633000/e5.oper.an.sfc
SCRATCH_ROOT=/glade/derecho/scratch/zarzycki/CAO
SCRIPT_DIR=/glade/u/home/zarzycki/CAO
TE_BIN_DIR=/glade/work/zarzycki/tempestextremes_casper/bin

# ── Add overrides below this line ──────────────────────────────────────────
# DEC_YEAR_START / DEC_YEAR_END: December-year of each DJF season, inclusive.
# e.g. DEC_YEAR_START=1979 → DJF 1979-80;  DEC_YEAR_END=2020 → DJF 2020-21
DEC_YEAR_START=1979
DEC_YEAR_END=2024
#
# Example: change detrend method
# DETREND=per_doy
#
# Example: set a reference period for the climatology
REF_PERIOD_START=1979
REF_PERIOD_END=2020

