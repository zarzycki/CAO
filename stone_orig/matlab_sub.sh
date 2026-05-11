#!/bin/bash -l

#PBS -N cao-step2
#PBS -A P93300042
#PBS -l select=1:ncpus=1:mem=200GB
#PBS -l walltime=06:00:00
#PBS -q casper@casper-pbs
#PBS -j oe

module load matlab
matlab -batch t2m_stdanoms_ERA5_21dayRM_101123


