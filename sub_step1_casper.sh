#!/bin/bash -l

#PBS -N cao-step1
#PBS -A P93300042
#PBS -l select=1:ncpus=16:mem=200GB
#PBS -l walltime=02:00:00
#PBS -q casper@casper-pbs
#PBS -j oe

# PBS copies this script to a spool directory before running it, so BASH_SOURCE[0]
# is not useful for locating sibling files.  PBS_O_HOME is always set to the
# submitter's home directory — use it to find the namelists in ~/CAO/.
_CAO_DIR="${PBS_O_HOME}/CAO"
# Load Stone et al. defaults first, then user overrides on top (last value wins)
source "${_CAO_DIR}/namelist_defaults.sh"
source "${_CAO_DIR}/namelist.sh"

module load conda
conda activate npl

LOG_DIR="${SCRATCH_ROOT}/logs/step1"
mkdir -p "${LOG_DIR}"

# Build command list: one python call per calendar month.
# Loop through DEC_YEAR_START to DEC_YEAR_END+1 to include the March shoulder month
# of the final season (e.g. March 2021 for the DJF 2020-21 season).
CMDFILE=$(mktemp)
for year in $(seq ${DEC_YEAR_START} $((DEC_YEAR_END + 1))); do
    for month in $(seq 1 12); do
        echo "python3 ${SCRIPT_DIR}/01_era5_daily_means.py ${year} ${month} > ${LOG_DIR}/${year}_$(printf '%02d' ${month}).log 2>&1" >> "${CMDFILE}"
    done
done

echo "Submitting $(wc -l < ${CMDFILE}) months across ${NUMCORES} parallel workers ..."
parallel -j ${NUMCORES} < "${CMDFILE}"

rm -f "${CMDFILE}"
echo "Step 1 done."
