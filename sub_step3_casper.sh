#!/bin/bash -l

#PBS -N cao-step3
#PBS -A P93300042
#PBS -l select=1:ncpus=24:mpiprocs=24:mem=160GB:cpu_type=genoa
#PBS -l walltime=02:00:00
#PBS -q casper@casper-pbs
#PBS -j oe

module load ncarenv
module load ncarcompilers
module load intel
module load openmpi
module load netcdf
#export LD_LIBRARY_PATH=${NCAR_LDFLAGS_NETCDF}64:${NCAR_LDFLAGS_NETCDF}:${LD_LIBRARY_PATH}

TE_BIN=/glade/work/zarzycki/tempestextremes_casper/bin/DetectBlobs
IN_DIR=/glade/derecho/scratch/zarzycki/CAO/std_anom
OUT_DIR=/glade/derecho/scratch/zarzycki/CAO/binary_masks
LOG_DIR=/glade/derecho/scratch/zarzycki/CAO/logs/step3
mkdir -p "${OUT_DIR}" "${LOG_DIR}"

# Build file lists (one line per season)
IN_LIST=$(mktemp)
OUT_LIST=$(mktemp)
for dec_year in $(seq 1979 2023); do
    jan_year=$((dec_year + 1))
    echo "${IN_DIR}/stdanom_djf_${dec_year}_${jan_year}.nc" >> "${IN_LIST}"
    echo "${OUT_DIR}/mask_djf_${dec_year}_${jan_year}.nc"   >> "${OUT_LIST}"
done

echo "Running DetectBlobs on $(wc -l < ${IN_LIST}) files across 42 MPI ranks ..."

mpiexec ${TE_BIN} \
    --in_data_list "${IN_LIST}" \
    --out_list     "${OUT_LIST}" \
    --thresholdcmd "t2m_stdanom,<=,-2,1" \
    --latname lat \
    --lonname lon \
    --tagvar binary_tag \
    --verbosity 0

rm -f "${IN_LIST}" "${OUT_LIST}"
echo "Step 3 complete."
