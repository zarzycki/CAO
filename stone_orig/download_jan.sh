





#!/bin/bash
#PBS -N t2mJan
#PBS -A P93300313
#PBS -l select=1:ncpus=9:mem=55GB
#PBS -l walltime=22:00:00
#PBS -q casper
#PBS -j oe


module load cdo
for year in {1980..2021}
do
cdo -L -cat -daymean /glade/collections/rda/data/ds633.0/e5.oper.an.sfc/$year"01"/e5.oper.an.sfc.128_167_2t*.nc  /glade/scratch/jackstone/DATA_SUMMER23_PRESENT/ERA5/ERA5_dailyavg_t2m/$year"01".nc
done

