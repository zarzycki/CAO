#!/bin/bash -l

#PBS -N cao-step2
#PBS -A P93300042
#PBS -l select=1:ncpus=1:mem=200GB
#PBS -l walltime=01:00:00
#PBS -q casper@casper-pbs
#PBS -j oe

module load conda
conda activate npl

python3 ~/CAO/02_compute_std_anom.py --detrend single_slope --overwrite

echo "Step 2 done."
