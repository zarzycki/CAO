#!/bin/bash -l

#PBS -N cao-step4
#PBS -A P93300042
#PBS -l select=1:ncpus=1:mem=50GB
#PBS -l walltime=01:00:00
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

TE_BIN="${TE_BIN_DIR}/StitchBlobs"
IN_DIR="${SCRATCH_ROOT}/binary_masks"
OUT_DIR="${SCRATCH_ROOT}/blobs"
mkdir -p "${OUT_DIR}"

IN_LIST=$(mktemp)
OUT_LIST=$(mktemp)
for dec_year in $(seq ${DEC_YEAR_START} ${DEC_YEAR_END}); do
    jan_year=$((dec_year + 1))
    echo "${IN_DIR}/mask_djf_${dec_year}_${jan_year}.nc" >> "${IN_LIST}"
    echo "${OUT_DIR}/blobs_${dec_year}_${jan_year}.nc"   >> "${OUT_LIST}"
done

echo "Running StitchBlobs on $(wc -l < ${IN_LIST}) seasons ..."

${TE_BIN} \
    --in_list          "${IN_LIST}" \
    --out_list         "${OUT_LIST}" \
    --var              binary_tag \
    --outvar           BLOB_t2m_stdanom \
    --minsize          ${MIN_SIZE} \
    --mintime          ${MIN_TIME} \
    --min_overlap_prev ${MIN_OVERLAP_PREV} \
    --latname          lat \
    --lonname          lon

rm -f "${IN_LIST}" "${OUT_LIST}"
echo "Step 4 complete."
