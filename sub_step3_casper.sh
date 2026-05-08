#!/bin/bash -l

#PBS -N cao-step3
#PBS -A P93300042
#PBS -l select=1:ncpus=24:mpiprocs=24:mem=160GB:cpu_type=genoa
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

module load ncarenv
module load ncarcompilers
module load intel
module load openmpi
module load netcdf

TE_BIN="${TE_BIN_DIR}/DetectBlobs"
IN_DIR="${SCRATCH_ROOT}/std_anom"
OUT_DIR="${SCRATCH_ROOT}/binary_masks"
LOG_DIR="${SCRATCH_ROOT}/logs/step3"
mkdir -p "${OUT_DIR}" "${LOG_DIR}"

IN_LIST=$(mktemp)
OUT_LIST=$(mktemp)
for dec_year in $(seq ${DEC_YEAR_START} ${DEC_YEAR_END}); do
    jan_year=$((dec_year + 1))
    echo "${IN_DIR}/stdanom_djf_${dec_year}_${jan_year}.nc" >> "${IN_LIST}"
    echo "${OUT_DIR}/mask_djf_${dec_year}_${jan_year}.nc"   >> "${OUT_LIST}"
done

echo "Running DetectBlobs on $(wc -l < ${IN_LIST}) files across 24 MPI ranks ..."

mpiexec ${TE_BIN} \
    --in_data_list "${IN_LIST}" \
    --out_list     "${OUT_LIST}" \
    --thresholdcmd "t2m_stdanom,<=,${THRESHOLD},${RADIUS}" \
    --latname lat \
    --lonname lon \
    --tagvar binary_tag \
    --verbosity 0

rm -f "${IN_LIST}" "${OUT_LIST}"

rm -v log*.txt

echo "Step 3 complete."
