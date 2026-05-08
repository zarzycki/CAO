#!/bin/bash -l

#PBS -N cao-step1
#PBS -A P93300042
#PBS -l select=1:ncpus=16:mem=200GB
#PBS -l walltime=02:00:00
#PBS -q casper@casper-pbs
#PBS -j oe

module load conda
conda activate npl

NUMCORES=16

SCRIPT_DIR=/glade/u/home/zarzycki/CAO
LOG_DIR=/glade/derecho/scratch/zarzycki/CAO/logs/step1
mkdir -p "${LOG_DIR}"

# Build command list: one python call per calendar month
# Range 1979-01 through 2021-03 covers full years 1979-2020 (stone_orig)
# plus Nov/Mar shoulder months for NDJFM running mean
CMDFILE=$(mktemp)
for year in $(seq 1979 2024); do
    end_month=12
    #[[ $year -eq 2021 ]] && end_month=3
    for month in $(seq 1 $end_month); do
        echo "python3 ${SCRIPT_DIR}/01_era5_daily_means.py ${year} ${month} > ${LOG_DIR}/${year}_$(printf '%02d' ${month}).log 2>&1" >> "${CMDFILE}"
    done
done

echo "Submitting $(wc -l < ${CMDFILE}) months across $NUMCORES parallel workers ..."
parallel -j $NUMCORES < "${CMDFILE}"

rm -f "${CMDFILE}"
echo "Step 1 done."
