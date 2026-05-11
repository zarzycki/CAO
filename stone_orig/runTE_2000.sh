






#!/bin/bash
#PBS -N TE2000..2001
#PBS -A P93300313
#PBS -l select=1:ncpus=9:mem=55GB
#PBS -l walltime=01:30:00
#PBS -q casper
#PBS -j oe


for djf in {2000..2001}
do

#!/bin/bash
#To run on login nodes you can just
#$ ./drive-tracking.sh
#To submit to compute nodes
#$ qsub drive-tracking.sh
################################################################
##>PBS -N tempest.par
##>PBS -A P93300313 
##>PBS -l walltime=0:59:00
##>PBS -q premium
##>PBS -j oe
##>PBS -l select=1:ncpus=36:mpiprocs=36
################################################################
#PBS -N tempest.casper
#PBS -A P93300313
#PBS -l select=1:ncpus=9:mem=55GB
#PBS -l walltime=10:00:00
#PBS -q casper
#PBS -j oe
# USER SETTINGS BY FILE
djf2=djf+1
YEAR=$djf"_"$((djf + 1))
VAR="t2m_stdanom" # Var to be tracked
THRESHOLD=-2 # minimum threshold of $VAR for cell to be flagged as being of interest
RADIUS=1     # radius of "influence" of a given cell in GC degrees (i.e., if radius = 1.0deg, all cells within 1deg of a cell with VAR>THRESHOLD also flagged)
MINSIZE=1500    # required contiguous gridboxes, based on native resolution (rough rule of thumb: (cos(cen_lat) * 111 * RES)^2 * MINSIZE = KM^2 where RES is grid spacing in deg)
MINTIME=3       # number of consecutive data timesteps to be considered a blob (so if daily data, 7 = 7 days... if hourly data, 168 = 7 days, etc.)
OVERLAP=50      # percent area overlap required between successive timesteps (for slow moving features, this should probably be 50-90% but depends on temporal resolution)
##----- If running on login nodes
module load nco
TEMPESTEXTREMESDIR=/glade/work/zarzycki/tempestextremes_noMPI/
PARCMD=""
##*******
##----- If running on Cheyenne
#TEMPESTEXTREMESDIR=/glade/work/zarzycki/tempestextremes/
#PARCMD="mpiexec_mpt"  # Use this on Cheyenne
##*******
#----- If running on Casper
#module load nco
#TEMPESTEXTREMESDIR=/glade/work/zarzycki/tempestextremes_casper/
#PARCMD="mpirun"       # Use this on Casper
#*******
# Directory to write intermediate files + final netcdf files
SCRATCHDIR=/glade/scratch/$LOGNAME/DATA_SUMMER23_PRESENT/NCEP-TS/blobs_${YEAR}/
# Generate scratch data working dir if it doesn't exist and move there
mkdir -p $SCRATCHDIR
cd $SCRATCHDIR
# get unique date string for temp filelist file
DATESTRING=`date +"%s%N"`
FILELISTNAME=filelist.txt.${DATESTRING}
touch $FILELISTNAME
# Generate parallel file
for f in /glade/scratch/jackstone/DATA_SUMMER23_PRESENT/ERA5/ERA5_dailyavg_t2m/t2m_stdanoms/${YEAR}.nc;
do
  echo "${f}" >> $FILELISTNAME
done
rm mask_${RADIUS}.nc
# First, find candidate blobs at each timestep, store in tmp mask files and concatenate
${PARCMD} ${TEMPESTEXTREMESDIR}/bin/DetectBlobs --in_data_list $FILELISTNAME --out mask.tmp --thresholdcmd "${VAR},<=,${THRESHOLD},${RADIUS}" --verbosity 3
ncrcat -O mask.tmp* mask.nc
rm mask.tmp*
mv mask.nc mask_${RADIUS}.nc
# Then stitch blobs and filter by min requirements to be considered a trackable entity
${TEMPESTEXTREMESDIR}/bin/StitchBlobs --in mask_${RADIUS}.nc --out blobs_${YEAR}.nc --var binary_tag --outvar BLOB_${VAR} --regional --minsize ${MINSIZE} --mintime ${MINTIME} --min_overlap_prev ${OVERLAP}

mv blobs_${YEAR}.nc ..
cd ..
rm -r blobs_${YEAR}
# remove parallel file
rm core*
rm $FILELISTNAME
rm log0*txt
echo "DONE"

done



