#!/bin/bash -l

#PBS -N cao-step4
#PBS -A P93300042
#PBS -l select=1:ncpus=1:mem=10GB
#PBS -l walltime=01:00:00
#PBS -q casper@casper-pbs
#PBS -j oe

module load ncarenv
module load ncarcompilers
module load intel
module load openmpi
module load netcdf

TE_BIN=/glade/work/zarzycki/tempestextremes_casper/bin/StitchBlobs
IN_DIR=/glade/derecho/scratch/zarzycki/CAO/binary_masks
OUT_DIR=/glade/derecho/scratch/zarzycki/CAO/blobs_reproduced
mkdir -p "${OUT_DIR}"

IN_LIST=$(mktemp)
OUT_LIST=$(mktemp)
for dec_year in $(seq 1979 2020); do
    jan_year=$((dec_year + 1))
    echo "${IN_DIR}/mask_djf_${dec_year}_${jan_year}.nc" >> "${IN_LIST}"
    echo "${OUT_DIR}/blobs_${dec_year}_${jan_year}.nc"   >> "${OUT_LIST}"
done

echo "Running StitchBlobs on $(wc -l < ${IN_LIST}) seasons ..."

${TE_BIN} \
    --in_list          "${IN_LIST}" \
    --out_list         "${OUT_LIST}" \
    --var              binary_tag \
    --regional \
    --outvar           BLOB_t2m_stdanom \
    --minsize          1500 \
    --mintime          3 \
    --min_overlap_prev 50 \
    --latname          lat \
    --lonname          lon

rm -f "${IN_LIST}" "${OUT_LIST}"
echo "Step 4 complete."

#    --out_list         "${OUT_LIST}" \
#    --out              "${OUT_DIR}/blobs_ALL.nc" \

