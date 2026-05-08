#!/bin/bash -l

#PBS -N cao-step2
#PBS -A P93300042
#PBS -l select=1:ncpus=1:mem=200GB
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

module load conda
conda activate npl

python3 "${SCRIPT_DIR}/02_compute_std_anom.py" --overwrite

echo "Step 2 done."
