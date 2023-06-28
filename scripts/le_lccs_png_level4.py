#!/usr/bin/env python
"""
A script to run through the LCCS classification system for PNG.
Notebook written by Chris Owers (Chris.Owers@newcastle.edu.au) and Carole Planque (cap33@aber.ac.uk)
Converted to script by Dan Clewley (dac@pml.ac.uk) and Carole Planque (cap33@aber.ac.uk)
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

import datacube
from datacube.utils import masking
from dea_tools.spatial import xr_rasterize
from datacube.testutils.io import rio_slurp_xarray

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
PNG_COASTAL_TILES_S3 = "/home/jovyan/data/png_0_25_deg_tiles_coast.gpkg"
GMW_2020_S3 = "/home/jovyan/data/gmw_v3_2020_vec_png.gpkg"
TIDAL_WETLAND_S3 = "/home/jovyan/data/Tidal_wetland_Murray_20172019_30m_PNG.tif"
OSM_S3 = "/home/jovyan/data/papua-new-guinea.gpkg"
WOODY_S3 = "/home/jovyan/data/Woodyarti_30m_PNG.tif"

# Force using S3 (e.g., for testing)
FORCE_S3 = False
if not os.path.isfile(PNG_COASTAL_TILES_S3) or FORCE_S3:
    PNG_COASTAL_TILES_S3 = (
        "s3://oa-bluecarbon-work-easi/livingearth-png/png_0_25_deg_tiles_coast.gpkg"
    )
if not os.path.isfile(GMW_2020_S3) or FORCE_S3:
    GMW_2020_S3 = (
        "s3://oa-bluecarbon-work-easi/livingearth-png/gmw_v3_2020_vec_png.gpkg"
    )
if not os.path.isfile(TIDAL_WETLAND_S3) or FORCE_S3:
    TIDAL_WETLAND_S3 = (
        "s3://oa-bluecarbon-work-easi/livingearth-png/Tidal_wetland_Murray_20172019_30m_PNG.tif"
    )
if not os.path.isfile(OSM_S3) or FORCE_S3:
    OSM_S3 = (
        "s3://oa-bluecarbon-work-easi/livingearth-png/papua-new-guinea.gpkg"
    )
if not os.path.isfile(WOODY_S3) or FORCE_S3:
    WOODY_S3 = (
        "s3://oa-bluecarbon-work-easi/livingearth-png/Woodyarti_30m_PNG.tif"
    )

print(f"Loading tiles from {PNG_COASTAL_TILES_S3}")
print(f"Loading GMW from {GMW_2020_S3}")
print(f"Loading Tidal Wetlands from {TIDAL_WETLAND_S3}")

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
time = ("2020-01-01", "2020-12-31")

crs = "EPSG:32755"
res = (30, -30)

query = {
    "time": time,
    "latitude": latitude,
    "longitude": longitude,
    "output_crs": crs,
    "resolution": res,
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
vegetat = ((fractional_cover["PV_PC_90"] > 25).fillna(0) - (fractional_cover["NPV_PC_90"] > 25).fillna(0))
vegetat = (vegetat.where(vegetat>0)*0+1).fillna(0)

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

# load in mangrove vector data just for AOI extent
bbox = [longitude[0], latitude[1], longitude[1], latitude[0]]

# Load the mangrove vector data within the AOI extent
gmw = gpd.read_file(GMW_2020_S3, bbox=bbox)

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

# Open Murray's tidal wetland probability (2017-2019) file as xarray
tidal_wetland = rio_slurp_xarray(TIDAL_WETLAND_S3, gbox=vegetat_veg_cat_ds.geobox)

# Threshold probability layer to 50%
tidal_wetland_extent = ((tidal_wetland.where(tidal_wetland>50))*0+1).fillna(0)

# Remove mudflats from Murray's layer
tidal_wetland_veg = vegetat_veg_cat_ds.vegetat_veg_cat * tidal_wetland_extent

# Create binary layer representing aquatic (1) and terrestrial (0)
# For coastal landscapes use the following
aquatic_wat = (wofs_mask + mangrove + tidal_wetland_veg)
aquatic_wat = (aquatic_wat.where(aquatic_wat > 0)*0+1).fillna(0)

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
print("Calculating natural vegetation...")
# Create a raster of zeros
cultman = xr.DataArray(np.zeros_like(wofs_mask), 
                       coords=wofs_mask.coords, dims=wofs_mask.dims, attrs=wofs_mask.attrs)

# Convert to Dataset and add name
cultman_agr_cat_ds = cultman.to_dataset(
    name="cultman_agr_cat"
)  # .squeeze().drop('time')

# ### 4. Natural Surfaces / Artificial Surfaces

# load in OSM vector data just for AOI extent
OSM_blds = gpd.read_file(OSM_S3, layer='buildings', bbox=bbox)
OSM_airports = gpd.read_file(OSM_S3, layer='aeroway_ln', bbox=bbox)
OSM_roads = gpd.read_file(OSM_S3, layer='highway_ln', bbox=bbox)

# get bbox to get geom of gdf
xmin, ymin, xmax, ymax = bbox

# Check if the vector dataset is empty
if OSM_blds.empty:
    # If the vector dataset is empty, create a raster of zeros matching the shape of the geomedians
    OSM_blds_xr = xr.DataArray(
        np.zeros_like(wofs_mask),
        coords=wofs_mask.coords,
        dims=wofs_mask.dims,
        attrs=wofs_mask.attrs,
    )
else:
    OSM_blds_AOI = OSM_blds.cx[xmin:xmax, ymin:ymax]
    OSM_blds_xr = xr_rasterize(gdf=OSM_blds_AOI, da=wofs_mask)

# Check if the vector dataset is empty
if OSM_airports.empty:
    # If the vector dataset is empty, create a raster of zeros matching the shape of the geomedians
    OSM_airports_xr = xr.DataArray(
        np.zeros_like(wofs_mask),
        coords=wofs_mask.coords,
        dims=wofs_mask.dims,
        attrs=wofs_mask.attrs,
    )
else:
    OSM_airports_AOI = OSM_airports.cx[xmin:xmax, ymin:ymax]
    OSM_airports_xr = xr_rasterize(gdf=OSM_airports_AOI, da=wofs_mask)

    # Check if the vector dataset is empty
if OSM_roads.empty:
    # If the vector dataset is empty, create a raster of zeros matching the shape of the geomedians
    OSM_roads_xr = xr.DataArray(
        np.zeros_like(wofs_mask),
        coords=wofs_mask.coords,
        dims=wofs_mask.dims,
        attrs=wofs_mask.attrs,
    )
else:
    # only selecting out roads that are sealed and fit the taxonomy of artificial surfaces
    OSM_roads_filtered = OSM_roads[OSM_roads['highway'].isin(['primary', 'primary_link', 'secondary', 'secondary_link', 'trunk', 'trunk_link'])]
    OSM_roads_AOI = OSM_roads.cx[xmin:xmax, ymin:ymax]
    OSM_roads_xr = xr_rasterize(gdf=OSM_roads_AOI, da=wofs_mask)

# combine OSM xarrays
OSM_xr = xr.where((OSM_blds_xr == 1) | (OSM_airports_xr == 1) | (OSM_roads_xr == 1), 1, 0)

# Convert to Dataset and add name
artific_urb_cat_ds = OSM_xr.to_dataset(
    name="artific_urb_cat")

# ### 5. Natural Water / Artificial Water

# NONE

# ### **Collect environmental variables into array for passing to classification system**

variables_xarray_list = []
variables_xarray_list.append(vegetat_veg_cat_ds)
variables_xarray_list.append(aquatic_wat_cat_ds)
variables_xarray_list.append(cultman_agr_cat_ds)
variables_xarray_list.append(artific_urb_cat_ds)
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

# Creating an array of non-valid bare surface because of the wofs' nan issue
classification_nan = ((classification_data.level3.where(
                            (classification_data.level3==216) & 
                            (wofs.frequency.isnull())))*0).fillna(1)

# Filtering non-valid bare surface (i.e, due to NaN in WOFs) out of level 2 and level 3
# Level2 set to zero where WOFs is NaN (i.e., info on water/terrestrial in non-veg areas isn't valid)
classification_data["level2"] = classification_data.level2 * classification_nan

# Set Level3 to Level1 value where Level2 is zero
classification_data["level3"] = ((classification_data.level3.where((classification_data.level1==200) & (
                                    classification_data.level2==0))*0+200).fillna(0) + (
                                classification_data.level3.where(classification_data.level2!=0).fillna(0)))

red, green, blue, alpha = lccs_l3.colour_lccs_level3(classification_data.level3.values)
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

# Open woodyarti tif file as xarray
woody_s1_layer = rio_slurp_xarray(WOODY_S3, gbox=vegetat_veg_cat_ds.geobox)

# Merge S1-derived Woody layer and GMW
woody_layer = (mangrove + woody_s1_layer)

# Convert binary woodyarti layer to lifeform lccs classes
lifeform = woody_layer.where(woody_layer > 0)*0+1
lifeform = lifeform.fillna(2)

# Convert to Dataset and add name
lifeform_veg_cat_ds = lifeform.to_dataset(
    name="lifeform_veg_cat"
).squeeze()  # .drop('time')

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

classification_level4 = (classification_array.level3*10.)+(
                       classification_array.lifeform_veg_cat_l4a)

# The following code lines were not working in .ipynb, so commented in script as well
# TO DO: Need to be fixed
# pixel_id, red, green, blue, alpha = lccs_l4.get_combined_level4(classification_array)
# write_rgb_cog(classification_data, red, green, blue, out_level4_rgb_file)
# print(f"Saved Level 4 RGB to {out_level4_rgb_file}")

## Select out blue carbon ecosystems (mangrove, saltmarsh, tidal woody area) from level 3 and 4 ##

print("Selecting out Blue Carbon Ecosystems")
# ### 1. Mangrove ecosystem
# - level 3 == 124
# - lifeform == 1
# - GMW == 1

mangrove_class = (level3_ds.level3.where((classification_array.level3 == 124) & (
                    classification_array.lifeform_veg_cat_l4a == 1) & (
                    mangrove == 1))*0+1).fillna(0)

# ### 2. Tidal woody ecosystem
# - level 3 == 124
# - lifeform == 1
# - GMW == 0

tidal_woody_class = (level3_ds.level3.where((classification_array.level3 == 124) & (
                    classification_array.lifeform_veg_cat_l4a == 1) & (
                    mangrove != 1))*0+2).fillna(0)

# ### 3. Saltmarsh ecosystem
# - level 3 == 124
# - lifeform == 2

saltmarsh_class = (level3_ds.level3.where((classification_array.level3 == 124) & (
                    classification_array.lifeform_veg_cat_l4a == 2))*0+3).fillna(0)

# ## <font color=blue>Blue carbon ecosystems</font>

# combine
bce = mangrove_class + saltmarsh_class + tidal_woody_class
bce = BCE.where(bce !=0, classification_level4)


write_cog(bce, out_bce_file)
print(f"Saved Blue Carbon Ecosystems to {out_bce_file}")

print("Classification finished")
