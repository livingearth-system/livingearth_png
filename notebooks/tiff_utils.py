import rasterio
import numpy as np
import matplotlib.pyplot as plt
from rasterio.windows import from_bounds

def get_tiff_bounds(tiff_file):
    """Retrieve the geographical bounds of a GeoTIFF file."""
    with rasterio.open(tiff_file) as src:
        transform = src.transform

        lon_min = transform.c  # Longitude of top-left corner
        lat_max = transform.f  # Latitude of top-left corner
        pixel_width = abs(transform.a)
        pixel_height = abs(transform.e)

        lon_max = lon_min + (src.width * pixel_width)
        lat_min = lat_max - (src.height * pixel_height)

    return lon_min, lon_max, lat_min, lat_max


def check_selection(lat_range, lon_range, tiff_bounds):
    """Check if the selected range falls within the TIFF file bounds."""
    lon_min, lon_max, lat_min, lat_max = tiff_bounds

    if (lat_range[0] >= lat_min and lat_range[1] <= lat_max and 
        lon_range[0] >= lon_min and lon_range[1] <= lon_max):
        return True
    else:
        print(f"Selected range is out of bounds.")
        print(f"Valid Longitude Range: {lon_min:.4f} to {lon_max:.4f}")
        print(f"Valid Latitude Range: {lat_min:.4f} to {lat_max:.4f}")
        print("Please select a region within this range.")
        return False


def clip_tiff(tiff_file, lat_range, lon_range, output_file):
    """Clip a GeoTIFF file to the given latitude/longitude range and save it."""
    with rasterio.open(tiff_file) as src:
        # Define the clipping window
        window = from_bounds(lon_range[0], lat_range[0], lon_range[1], lat_range[1], src.transform)
        
        # Read the clipped data
        clipped_data = src.read(1, window=window)
        
        # Update metadata for the clipped image
        out_meta = src.meta.copy()
        out_meta.update({
            "height": window.height,
            "width": window.width,
            "transform": src.window_transform(window)
        })
        
        # Save the clipped TIFF file
        with rasterio.open(output_file, "w", **out_meta) as dest:
            dest.write(clipped_data, 1)

    return output_file


def plot_tiff(tiff_file):
    """Plot the given TIFF file."""
    with rasterio.open(tiff_file) as src:
        data = src.read(1)
        extent = [src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top]

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.imshow(data, cmap='Greens_r', origin='upper', extent=extent)

        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        plt.show()


def main(tiff_file, lat_range, lon_range, output_file="clipped_output.tif"):
    """Main function to clip the TIFF file and plot it."""
    tiff_bounds = get_tiff_bounds(tiff_file)
    
    if check_selection(lat_range, lon_range, tiff_bounds):
        clipped_tiff = clip_tiff(tiff_file, lat_range, lon_range, output_file)
        plot_tiff(clipped_tiff)
