import datetime
import datacube
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from pyproj import Proj
import rasterio
from rasterio.transform import from_origin
from rasterio.crs import CRS
from PIL import Image
import os

def plot_s2_true_color_and_ssii(lon_range, lat_range, time_range, product="s2_l2a", measurements=None):
    if measurements is None:
        measurements = [
            "coastal", "blue", "green", "red", "rededge1", "rededge2", "rededge3",
            "nir", "nir08", "swir16", "swir22", "scl"
        ]

    dc = datacube.Datacube(app='sentinel2_bands_plot')
    crs = "EPSG:4326"
    resolution = (-0.0001, 0.0001)

    ds = dc.load(
        product=product,
        x=lon_range,
        y=lat_range,
        time=time_range,
        measurements=measurements,
        output_crs=crs,
        resolution=resolution
    )

    if ds.time.size == 0:
        print("No data found")
        return

    ds_time = ds.isel(time=0)
    print("Data time:", ds_time.time.values)

    cloud_mask = ds_time['scl'].isin([8, 9, 10, 11, 12])
    masked_ds = ds_time.where(~cloud_mask)

    greens = ds['green']
    nirs = ds['nir']
    ndwi = (greens - nirs) / (greens + nirs)
    water_mask = ndwi.isel(time=0).squeeze() < 1

    red = masked_ds['red']
    vre = masked_ds['rededge1']
    a = 0.000001
    ssii = (vre - red) / (red + vre + a)
    ssii = ssii.where(water_mask)

    save_ssii_as_png(ssii, lon_range, lat_range, resolution, water_mask)

    def normalize_band_min_max(band_data):
        return np.clip((band_data - 0) / (2000 - 0), 0, 1)

    true_color = np.stack([
        normalize_band_min_max(ds_time['red']),
        normalize_band_min_max(ds_time['green']),
        normalize_band_min_max(ds_time['blue'])
    ], axis=-1)

    ssii_values = ssii.values
    ssii_values[~water_mask.values] = np.nan
    ssii_colored = np.zeros((*ssii.shape, 3))
    ssii_colored[water_mask.values] = plt.cm.YlGn(ssii_values[water_mask.values])[:, :3]

    fig = plt.figure(figsize=(14, 8))
    gs = GridSpec(1, 2)

    ax0 = fig.add_subplot(gs[0, 0])
    ax0.imshow(true_color)
    ax0.set_title('True Color Composite')
    ax0.axis('off')

    ax2 = fig.add_subplot(gs[0, 1])
    ax2.imshow(ssii_colored)
    ax2.set_title('Submerged Seagrass Index (SSI)')
    ax2.axis('off')

    plt.tight_layout()
    plt.show()

def save_ssii_as_png(ssii, lon_range, lat_range, resolution, water_mask):
    ssii_values = ssii.values
    ssii_values[~water_mask.values] = np.nan  # Ensure water mask is applied correctly
    
    # Normalize SSII values to range 0-1 for colormap application
    ssii_values_normalized = np.clip((ssii_values - np.nanmin(ssii_values)) / 
                                     (np.nanmax(ssii_values) - np.nanmin(ssii_values)), 0, 1)

    ssii_colored = np.zeros((*ssii.shape, 3))
    valid_mask = ~np.isnan(ssii_values_normalized)
    ssii_colored[valid_mask] = plt.cm.YlGn(ssii_values_normalized[valid_mask])[:, :3]

    # Convert black areas to white (RGB=(255, 255, 255))
    ssii_colored[ssii_colored == 0] = 1  # Convert black to white (set to 1 for normalized color)

    # Scale to 0-255 range for saving as PNG
    ssii_colored_255 = (ssii_colored * 255).astype(np.uint8)

    output_png = f"SSII_{datetime.datetime.now().date()}_{lon_range[0]}_{lon_range[1]}_{lat_range[0]}_{lat_range[1]}.png"
    plt.imsave(output_png, ssii_colored_255)

    #print(f"SSII saved as PNG at {output_png}")
    convert_png_to_geotiff(output_png, lon_range, lat_range, resolution)

def convert_png_to_geotiff(png_file, lon_range, lat_range, resolution):
    img = Image.open(png_file).convert("RGB")  # Preserve RGB color
    img_data = np.array(img)
    height, width, _ = img_data.shape  # Now it's RGB, so 3 channels

    # Convert black areas to white in the image data
    img_data[img_data == 0] = 255  # Change black (0, 0, 0) to white (255, 255, 255)

    # Clip the image data to be between 0 and 130 for each channel
    img_data = np.clip(img_data, 0, 130)

    lat_res = (lat_range[1] - lat_range[0]) / height
    lon_res = (lon_range[1] - lon_range[0]) / width
    transform = from_origin(lon_range[0], lat_range[1], lon_res, lat_res)
    crs = CRS.from_epsg(4326)

    output_geotiff = png_file.replace(".png", ".tif")

    with rasterio.open(
        output_geotiff,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=3,  # ✅ Save as RGB
        dtype="uint8",  # ✅ Use uint8 (0-255) for colors
        crs=crs,
        transform=transform
    ) as dst:
        for band in range(3):  # Write R, G, B separately
            dst.write(img_data[:, :, band], band + 1)

    #print(f"GeoTIFF file saved as {output_geotiff}")
    convert_to_one_band(output_geotiff, png_file)

def convert_to_one_band(input_tif, png_file):
    output_tif = input_tif.replace(".tif", "_band1.tif")

    with rasterio.open(input_tif) as src:
        band1 = src.read(1)  # Read only Band 1
        profile = src.profile  # Get metadata

        # Modify profile for single-band output
        profile.update(count=1, dtype=rasterio.uint8, nodata=255)

        # Save new single-band TIFF
        with rasterio.open(output_tif, "w", **profile) as dst:
            dst.write(band1, 1)

    print(f"Single-band TIFF saved as {output_tif}")
    
    # Now, remove the PNG and 3-band GeoTIFF
    os.remove(png_file)
    os.remove(input_tif)
    #print(f"Deleted PNG and 3-band GeoTIFF")
