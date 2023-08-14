#!/usr/bin/env bash

source ~/venvs/WOfS_Environment/bin/activate
export GDAL_HTTP_PROXY=easi-caching-proxy.caching-proxy:80
export AWS_HTTPS=NO
TILES_LIST=$1
if [ "$#" -ne 1 ]; then
    echo "Must provide list of tiles to process."
    exit
fi
cat $TILES_LIST | cut -d ',' -f 1 | parallel --resume --joblog all_tiles_run.log --eta --bar time ~/code/livingearth_png/scripts/le_lccs_png_level4.py -o ~/classification_out/ -t {}

