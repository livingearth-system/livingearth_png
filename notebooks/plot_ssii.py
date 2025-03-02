import matplotlib.pyplot as plt
import rasterio
import numpy as np

def plot_saved_ssii_tif(tif_file, threshold=0.5):
    """Plot the saved SSII GeoTIFF file with latitude and longitude on the axes and a threshold filter."""
    with rasterio.open(tif_file) as src:
        ssii_data = src.read(1)  # Read the first band (SSII data)
        transform = src.transform
        crs = src.crs  # Coordinate Reference System
        bounds = src.bounds  # Geographical bounds of the image

    # Apply the threshold filter (set values below threshold to NaN or zero)
    ssii_data_thresholded = np.where(ssii_data > threshold, ssii_data, np.nan)

    # Calculate latitude and longitude values for the axes
    lon_min, lat_max, lon_max, lat_min = bounds
    width, height = ssii_data.shape
    lon_range = [lon_min, lon_max]
    lat_range = [lat_min, lat_max]

    # Calculate the corresponding latitude and longitude tick labels
    lon_ticks = np.linspace(lon_range[0], lon_range[1], width)
    lat_ticks = np.linspace(lat_range[0], lat_range[1], height)

    # Create the plot
    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot the thresholded SSII map
    im = ax.imshow(ssii_data_thresholded, cmap='Greens_r', origin='upper')

    # Add latitude and longitude ticks with two-digit precision
    lon_ticks_labels = [f"{x:.2f}" for x in np.linspace(lon_range[0], lon_range[1], 5)]
    lat_ticks_labels = [f"{x:.2f}" for x in np.linspace(lat_range[0], lat_range[1], 5)]

    ax.set_xticks(np.linspace(0, width, 5))
    ax.set_xticklabels(lon_ticks_labels)
    ax.set_yticks(np.linspace(0, height, 5))
    ax.set_yticklabels(lat_ticks_labels)

    # Set labels and title
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.set_title(f'Submerged Seagrass Index (SSI) Map (Threshold > {threshold})')

    # Show the plot
    plt.tight_layout()
    plt.show()


