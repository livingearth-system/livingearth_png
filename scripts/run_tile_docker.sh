#!/usr/bin/env bash

# Set environmental variables for GDAL
export GDAL_HTTP_PROXY=easi-caching-proxy.caching-proxy:80
export AWS_HTTPS=NO

if [ "$#" -ne 1 ]; then
    echo "Must provide tile ID to process."
    exit
fi
TILE_ID=$1

# Make temporary directory
temp_classification_out=`mktemp --directory --suffix=_le_lccs_png`

# Copy required layers from S3 Bucket. Need to have local copies else will run into problems with cache
mkdir -p /home/jovyan/data/
cd /home/jovyan/data/
aws s3 cp s3://oa-bluecarbon-work-easi/livingearth-png/png_0_25_deg_tiles_coast_edit_anet.gpkg .
aws s3 cp s3://oa-bluecarbon-work-easi/livingearth-png/gmw_v3_2020_vec_png.gpkg .
aws s3 cp s3://oa-bluecarbon-work-easi/livingearth-png/Tidal_wetland_Murray_20172019_30m_PNG.tif .
aws s3 cp s3://oa-bluecarbon-work-easi/livingearth-png/papua-new-guinea.gpkg .
aws s3 cp s3://oa-bluecarbon-work-easi/livingearth-png/Woodyarti_30m_PNG.tif .

# Run through classification
time /code/scripts/le_lccs_png_level4.py -o $temp_classification_out -t $TILE_ID

# Upload files to AWS bucket
for out_tiff in `ls $temp_classification_out/*tif`
do
	aws s3 cp $out_tiff s3://oa-bluecarbon-work-easi/livingearth-png/classification_out
done

# Remove temporary directory
rm -fr $temp_classification_out
