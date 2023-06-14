#!/usr/bin/env python
"""
A script to run through the LCCS classification system for PNG.
Notebook written by Chris Owers (Chris.Owers@newcastle.edu.au), converted to script by Dan Clewley (dac@pml.ac.uk)
"""
import argparse
import os
import sys
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import xarray as xr
import geopandas as gpd
import rasterio
from dask.diagnostics import ProgressBar

import datacube
from datacube.utils import masking
from dea_tools.spatial import xr_rasterize

# import le_lccs modules (assumes these have been installed)
from le_lccs.le_classification import lccs_l3
from le_lccs.le_classification import lccs_l4

# for virtual products
sys.path.insert(1, os.path.abspath("../le_plugins"))
import importlib
from datacube.virtual import catalog_from_file
from datacube.virtual import DEFAULT_RESOLVER

# outputs
from datacube.utils.cog import write_cog

# AWS access
from datacube.utils.aws import configure_s3_access

# Check for local versions of files, if not use S3 buckets
PNG_COASTAL_TILES_S3 = "/home/jovyan/data/png_0_5_deg_tiles_coast.gpkg"
GMW_2020_S3 = "/home/jovyan/data/gmw_v3_2020_vec_png.gpkg"
if not os.path.isfile(PNG_COASTAL_TILES_S3):
    PNG_COASTAL_TILES_S3 = "s3://easi-asia-user-scratch/AROA4YF43ZWIU6TNXUYDM:danclewley/png_0_5_deg_tiles_coast.gpkg"
if not os.path.isfile(GMW_2020_S3):
    GMW_2020_S3 = "s3://easi-asia-user-scratch/AROA4YF43ZWIU6TNXUYDM:danclewley/gmw_v3_2020_vec_png.gpkg"


print(f'Will use caching proxy at: {os.environ.get("GDAL_HTTP_PROXY")}')


def write_rgb_cog(classification_data, red, green, blue, out_filename):
    """ "
    Write out an RGB image as a cloud optimised GeoTiff
    """
    min_x = classification_data.coords["x"].min().values
    max_x = classification_data.coords["x"].max().values
    min_y = classification_data.coords["y"].min().values
    max_y = classification_data.coords["y"].max().values

    res_x = 30
    res_y = -30
    crs = "EPSG:32755"
    # Write out
    out_file_transform = [res_x, 0, min_x, 0, res_y, max_y]
    output_x_size = int((max_x - min_x) / res_x)
    output_y_size = int((min_y - max_y) / res_y)

    # Write RGB colour scheme out
    rgb_dataset = rasterio.open(
        out_filename,
        "w",
        driver="COG",
        height=output_y_size,
        width=output_x_size,
        count=3,
        dtype=np.uint8,
        crs=crs,
        transform=out_file_transform,
    )
    # Rotate arrays by 180 degrees before writing out
    rgb_dataset.write(np.rot90(red, 2), 1)
    rgb_dataset.write(np.rot90(green, 2), 2)
    rgb_dataset.write(np.rot90(blue, 2), 3)
    rgb_dataset.close()


parser = argparse.ArgumentParser(
    description="Run PNG LCCS Classification for a specified tile "
)
parser.add_argument(
    "-o", "--outdir", required=True, help="Output directory for classification outputs"
)
parser.add_argument(
    "-t",
    "--tile_id",
    type=int,
    help=f"ID of tile to select from {PNG_COASTAL_TILES_S3}",
    required=True,
    default=None,
)

args = parser.parse_args()

dc = datacube.Datacube(app="level3")

# virtual product catalog
catalog = catalog_from_file(os.path.abspath("../le_plugins/virtual_product_cat.yaml"))

# Configure AWS access
configure_s3_access(aws_unsigned=False, requester_pays=True)

# Set up progress bar for dask and register so is used as needed
pbar = ProgressBar()
pbar.register()

# Read in bounds tiles
bounds_gdf = data = gpd.read_file(PNG_COASTAL_TILES_S3)

# Get polygon for specified tile
tile_gdf = bounds_gdf[bounds_gdf.id == args.tile_id]

# Set output paths
out_level3_rgb_file = os.path.join(
    args.outdir, f"png_lccs_classification_v0_1_level3_rgb_tile_{args.tile_id:03}.tif"
)
out_level4_rgb_file = os.path.join(
    args.outdir, f"png_lccs_classification_v0_1_level4_rgb_tile_{args.tile_id:03}.tif"
)
out_bce_file = os.path.join(
    args.outdir, f"png_lccs_classification_v0_1_bce_tile_{args.tile_id:03}.tif"
)


# Get bounds for tile
latitude = (float(tile_gdf.bounds.maxy), float(tile_gdf.bounds.miny))
longitude = (float(tile_gdf.bounds.minx), float(tile_gdf.bounds.maxx))

# Set up time
# TODO: read this from the command line
time = ("2020-01-01", "2020-07-31")

crs = "EPSG:32755"
res = (30, -30)

query = {
    "time": time,
    "latitude": latitude,
    "longitude": longitude,
    "output_crs": crs,
    "resolution": res,
    "dask_chunks": {"x": 512, "y": 512},
}

# ### 1. Vegetated / Non-Vegetated

#    * **Primarily Vegetated Areas**:
#    This class applies to areas that have a vegetative cover of at least 4% for at least two months of the year, consisting of Woody (Trees, Shrubs) and/or Herbaceous (Forbs, Graminoids) lifeforms, or at least 25% cover of Lichens/Mosses when other life forms are absent.
#
#    * **Primarily Non-Vegetated Areas**:
#    Areas which are not primarily vegetated.
#
#
# Fractional cover (FC) is used to distinguish between vegetated and not vegetated.
# http://data.auscover.org.au/xwiki/bin/view/Product+pages/Landsat+Fractional+Cover
# <br>We are using the 90th annual percentile for both Photosyntheic (PV) and Non-photosynthetic (NPV) vegetation. This removes noise and outliers and gives a robust maximum annual value. A threshold is then applied where PV or NPV is greater than 50%, the rationale being that if a pixel is greater than 50% PV or NPV we can be confident that it is likely to be vegetated. In addition, a maximum threshold value is given to NPV as non-photosynthetic vegetation and bare soil (BS) fractions can be unreliable at maximum values due to inherent issues with unmixing NPV and BS signatures.
#
# <font color=red>**TODO:**</font> need to calculate number of observations for annual time series to define vegetation correctly as in FAO guidelines. This will likely be similar to WOfS wet/clear obervations but for FC where PV or NPV is greater than 50% for 60 days per year

# Load Fractional Cover

# Need to add any transformations for the VP you're using
# Get location of transformation
print("Loading fractional cover...")
transformation = "fractional_cover"
trans_loc = importlib.import_module(transformation)
trans_class = transformation.split(".")[-1]

DEFAULT_RESOLVER.register("transform", trans_class, getattr(trans_loc, trans_class))

product = catalog["fractional_cover"]
fractional_cover = product.load(dc, **query)
fractional_cover = masking.mask_invalid_data(fractional_cover)

# Load WOfS

# Need to add any transformations for the VP you're using
# Get location of transformation
print("Loading WOfS...")
transformation = "WOfS"
trans_loc = importlib.import_module(transformation)
trans_class = transformation.split(".")[-1]

DEFAULT_RESOLVER.register("transform", trans_class, getattr(trans_loc, trans_class))

product = catalog["WOfS"]
wofs = product.load(dc, **query)
wofs = masking.mask_invalid_data(wofs)

wofs_mask = wofs["frequency"] >= 0.2

# Create binary layer representing vegetated (1) and non-vegetated (0)
vegetat = (fractional_cover["PV_PC_90"] >= 50) | (
    (fractional_cover["NPV_PC_90"] >= 50) & (fractional_cover["NPV_PC_90"] <= 80)
)

# mask out water here
vegetat = vegetat.where(wofs_mask == 0, 0, 1)

# Convert to Dataset and add name
vegetat_veg_cat_ds = vegetat.to_dataset(
    name="vegetat_veg_cat"
)  # .squeeze().drop('time')

vegetat_veg_cat_ds.vegetat_veg_cat.plot()


# ### 2. Aquatic / Terrestrial

#    * **Primarily Vegetated, Terrestrial**: The vegetation is influenced by the edaphic substratum
#    * **Primarily Non-Vegetated, Terrestrial**: The cover is influenced by the edaphic substratum
#    * **Primarily Vegetated, Aquatic or regularly flooded**: The environment is significantly influenced by the presence of water over extensive periods of time. The water is the dominant factor determining natural soil development and the type of plant communities living on its surface
#    * **Primarily Non-Vegetated, Aquatic or regularly flooded**: Permanent or regularly flood aquatic areas
#
#
# Water Observations from Space (WOfS) is used to distinguish aquatic and terrestrial areas.
# https://www.sciencedirect.com/science/article/pii/S0034425715301929?via%3Dihub
# * A threshold of 20% is applied for the annual summary dataset to remove flood events not indicative of the landscape.
# *i The Mangrove layer are also used for relevant coastal landscapes.
#

# note: wofs (loaded in level 1 as wofs_mask)

# load mangroves as mask
print("Loading GMW...")
gmw_2020 = "s3://easi-asia-user-scratch/AROA4YF43ZWIU6TNXUYDM:danclewley/gmw_v3_2020_vec_png.gpkg"

# load in mangrove vector data just for AOI extent
bbox = [longitude[0], latitude[1], longitude[1], latitude[0]]

# Load the mangrove vector data within the AOI extent
gmw = gpd.read_file(gmw_2020, bbox=bbox)

# Check if the mangrove vector dataset is empty
if gmw.empty:
    # If the mangrove vector dataset is empty, create a raster of zeros matching the shape of the WOfS mask
    mangrove = xr.DataArray(
        np.zeros_like(wofs_mask),
        coords=wofs_mask.coords,
        dims=wofs_mask.dims,
        attrs=wofs_mask.attrs,
    )
else:
    # If the mangrove vector dataset is not empty, rasterize it to match the shape of the WOfS mask
    # Get the bounding box coordinates
    xmin, ymin, xmax, ymax = bbox

    # Get the mangrove vector data within the AOI extent
    gmw_aoi = gmw.cx[xmin:xmax, ymin:ymax]

    # Rasterize the mangrove vector data to match the shape of the WOfS mask
    mangrove = xr_rasterize(gdf=gmw_aoi, da=wofs_mask)

# Create binary layer representing aquatic (1) and terrestrial (0)
# For coastal landscapes use the following
aquatic_wat = wofs_mask | mangrove

# Convert to Dataset and add name
aquatic_wat_cat_ds = aquatic_wat.to_dataset(
    name="aquatic_wat_cat"
)  # .squeeze().drop('time')

# ### 3. Natural Vegetation / Crop or Managed Vegetation

#    * **Primarily Vegetated, Terrestrial, Artificial/Managed**: Cultivated and Managed Terrestrial Areas
#    * **Primarily Vegetated, Terrestrial, (Semi-)natural**: Natural and Semi-Natural Vegetation
#    * **Primarily Vegetated, Aquatic or Regularly Flooded, Artificial/Managed**: Cultivated Aquatic or Regularly Flooded Areas
#    * **Primarily Vegetated, Aquatic or Regularly Flooded, (Semi-)natural**: Natural and Semi-Natural Aquatic or Regularly Flooded Vegetation
#
# <font color=red>**TODO:** Carole and Annette exploring sentinel-1 options here </font>
print("Calculating natural vegetation...")
# Need to add any transformations for the VP you're using
# Get location of transformation
transformation = "geomedian"
trans_loc = importlib.import_module(transformation)
trans_class = transformation.split(".")[-1]

DEFAULT_RESOLVER.register("transform", trans_class, getattr(trans_loc, trans_class))

# load geomedian
product = catalog["geomedian"]
geomedian = product.load(dc, **query)

# Create binary layer representing cultivated (1) and natural (0)
# calculate NDVI (PLACEHOLDER)
NDVI = (geomedian.nbart_nir - geomedian.nbart_red) / (
    geomedian.nbart_nir + geomedian.nbart_red
)
cultman = (NDVI >= 0.4) & (NDVI <= 0.7)

# Convert to Dataset and add name
cultman_agr_cat_ds = cultman.to_dataset(
    name="cultman_agr_cat"
)  # .squeeze().drop('time')

# ### 4. Natural Surfaces / Artificial Surfaces

# NONE

# ### 5. Natural Water / Artificial Water

# NONE

# ### **Collect environmental variables into array for passing to classification system**

variables_xarray_list = []
variables_xarray_list.append(vegetat_veg_cat_ds)
variables_xarray_list.append(aquatic_wat_cat_ds)
variables_xarray_list.append(cultman_agr_cat_ds)
# variables_xarray_list.append(artific_urb_cat_ds)
# variables_xarray_list.append(artwatr_wat_cat_ds)

# **The LCCS classification is hierarchical. The 8 classes are shown below**
#
# | Class name                       | Code|     |
# |----------------------------------|-----|-----|
# | Cultivated Terrestrial Vegetated | A11 | 111 |
# | Natural Terrestrial Vegetated    | A12 | 112 |
# | Cultivated Aquatic Vegetated     | A23 | 123 |
# | Natural Aquatic Vegetated        | A24 | 124 |
# | Artificial Surface               | B15 | 215 |
# | Natural Surface                  | B16 | 216 |
# | Artificial Water                 | B27 | 227 |
# | Natural Water                    | B28 | 228 |
#

print("Running Level 3 Classification...")
# Merge to a single dataframe
classification_data = xr.merge(variables_xarray_list)

# Apply Level 3 classification using separate function. Works through in three stages
level1, level2, level3 = lccs_l3.classify_lccs_level3(classification_data)

# Save classification values back to xarray
out_class_xarray = xr.Dataset(
    {
        "level1": (classification_data["vegetat_veg_cat"].dims, level1),
        "level2": (classification_data["vegetat_veg_cat"].dims, level2),
        "level3": (classification_data["vegetat_veg_cat"].dims, level3),
    }
)
classification_data = xr.merge([classification_data, out_class_xarray])

red, green, blue, alpha = lccs_l3.colour_lccs_level3(level3)
write_rgb_cog(classification_data, red, green, blue, out_level3_rgb_file)
print(f"Saved Level 3 RGB to {out_level3_rgb_file}")

# Convert level3 to Dataset and add name
level3_ds = classification_data.level3.to_dataset(name="level3")

# ### 1. Water state
# <font color=red>**TODO:** could do this using wofs if we wanted </font>

# ### 2. Water persistence
# <font color=red>**TODO:** could do this using wofs if we wanted </font>

# ### 3. Lifeform
# Describes the detail of vegetated classes, separating woody from herbaceous
# 0: Not applicable (such as in water areas)
# 1: Woody (trees, shrubs)
# 2: Herbaceous (grasses, forbs)

# Load woody cover fraction

# Need to add any transformations for the VP you're using
# Get location of transformation
print("Loading Woody Cover Fraction...")
transformation = "WCF"
trans_loc = importlib.import_module(transformation)
trans_class = transformation.split(".")[-1]

DEFAULT_RESOLVER.register("transform", trans_class, getattr(trans_loc, trans_class))

# load WCF
product = catalog["WCF"]
wcf = product.load(dc, **query)
wcf_da = wcf.WCF

lifeform = wcf_da.copy()
# threshold of woody and non woody vegetation
lifeform.values = np.where(lifeform >= 0.2, 1, 2)

# Convert to Dataset and add name
lifeform_veg_cat_ds = lifeform.to_dataset(
    name="lifeform_veg_cat"
).squeeze()  # .drop('time')

lifeform_veg_cat_ds.lifeform_veg_cat.plot()


# ### 4. Canopy cover
# <font color=red>**TODO:** could do this using fractional cover if we wanted </font>

# ## <font color=blue>Level 4 classification</font>

print("Running Level 4 Classification...")
variables_xarray_list = []
variables_xarray_list.append(level3_ds)
# variables_xarray_list.append(waterstt_wat_cat_ds)
# variables_xarray_list.append(waterper_wat_cin_ds)
variables_xarray_list.append(lifeform_veg_cat_ds)
# variables_xarray_list.append(canopyco_veg_con_ds)

# Merge to a single dataframe
l4_classification_data = xr.merge(variables_xarray_list)

# Apply Level 4 classification
classification_array = lccs_l4.classify_lccs_level4(l4_classification_data)

pixel_id, red, green, blue, alpha = lccs_l4.get_combined_level4(classification_array)

write_rgb_cog(classification_data, red, green, blue, out_level4_rgb_file)
print(f"Saved Level 4 RGB to {out_level4_rgb_file}")

## Select out blue carbon ecosystems (mangrove, saltmarsh, supratidal forests) from level 3 and 4 ##

print("Selecting out Blue Carbon Ecosystems")
# ### 1. Mangrove
# - level 3 == 124

mangrove = level3_ds.level3 == 124

# ### 2. Saltmarsh
# - level 3 == 112
# - DEM < 10m
# - WCF < 0.5

# level 3
naturalveg = level3_ds.level3 == 112

# load DEM
product = catalog["DEM"]
# don't need time in the query for loading DEM
DEM = product.load(dc, **{k: v for k, v in query.items() if k != "time"})

elevation = DEM.elevation.squeeze()

# greater than 1m AHD and less than 20m AHD == True
elev_min = 1
elev_max = 20

lessthan10m = elevation <= elev_max
greaterthan1m = elevation >= elev_min
elev_threshold = lessthan10m & greaterthan1m

# WCF
lifeform = wcf_da.copy()
# threshold of woody and non woody vegetation
lifeform.values = np.where(lifeform < 0.5, 1, 0)

saltmarsh = xr.where(
    (naturalveg == False) + (elev_threshold == False) + (lifeform == False), 0, 2
).astype("int8")

# ### 3. Supratidal forests
# - level 3 == 112 (from saltmarsh)
# - DEM < 10m (from saltmarsh)
# - WCF > 0.5

# WCF
lifeform = wcf_da.copy()
# threshold of woody and non woody vegetation
lifeform.values = np.where(lifeform > 0.5, 1, 0)

stf = xr.where(
    (naturalveg == False) + (elev_threshold == False) + (lifeform == False), 0, 3
).astype("int8")

# ## <font color=blue>Blue carbon ecosystems</font>

# combine
bce = mangrove + saltmarsh + stf
bce = bce.where(bce != 0, np.nan)


write_cog(bce, out_bce_file)
print(f"Saved Blue Carbon Ecosystems to {out_bce_file}")

print("Classification finished")
