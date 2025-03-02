import folium
import rasterio
import numpy as np
from folium import raster_layers
from matplotlib import cm
from matplotlib.colors import Normalize
from IPython.display import display

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

def apply_colormap_to_tiff(tiff_file, colormap='Greens_r', lat_range=None, lon_range=None):
    """Apply a reversed colormap (e.g., 'Greens_r') to the TIFF data."""
    with rasterio.open(tiff_file) as src:
        # Read the data from the TIFF
        data = src.read(1)
        
        # Mask out white areas (no data) by setting them to NaN
        nodata_value = src.nodata
        if nodata_value is not None:
            data = np.ma.masked_equal(data, nodata_value)

        # Get the geographical bounds and transform to pixel coordinates
        lon_min, lon_max, lat_min, lat_max = get_tiff_bounds(tiff_file)
        
        # Print the bounds of the TIFF file for debugging
        print(f"TIFF bounds: lon_min={lon_min}, lon_max={lon_max}, lat_min={lat_min}, lat_max={lat_max}")
        
        # Calculate pixel coordinates for lat_range and lon_range
        if lat_range and lon_range:
            try:
                row_min, col_min = src.index(lon_range[0], lat_range[1])  # Top-left corner
                row_max, col_max = src.index(lon_range[1], lat_range[0])  # Bottom-right corner
                
                # Print pixel coordinates to check clipping
                print(f"Clip region (rows, cols): ({row_min}, {col_min}) to ({row_max}, {col_max})")
                
                # Clip the data to the specified region
                data = data[row_min:row_max, col_min:col_max]

                # Ensure that we don't end up with an empty array after clipping
                if data.size == 0:
                    raise ValueError("Clipped data is empty. Check the lat/lon range and TIFF bounds.")
                
                # Adjust the geographical bounds to the selected range
                lon_min = lon_range[0]
                lon_max = lon_range[1]
                lat_min = lat_range[0]
                lat_max = lat_range[1]
            except ValueError as e:
                print(f"Error clipping data: {e}")
                return None, None, None, None, None
        
        # Check if data is empty after clipping
        if data.size == 0:
            raise ValueError("No valid data in the clipped region.")

        # Normalize the data to [0, 1] for colormap processing
        norm = Normalize(vmin=np.min(data), vmax=np.max(data))
        
        # Apply the reversed colormap
        cmap = cm.get_cmap(colormap)
        rgba_data = cmap(norm(data))
        
        # Convert RGBA data to an 8-bit format (0-255)
        rgba_data = (rgba_data * 255).astype(np.uint8)
    
    return rgba_data, lon_min, lon_max, lat_min, lat_max

def overlay_tiff_on_map(tiff_file, lat_range, lon_range, save_path="tiff_overlay_map.html"):
    """Overlay a TIFF image on a Folium map with 50% transparency, custom reversed colormap, and a legend."""
    # Create a Folium map centered at the midpoint of the lat/lon range
    map_center = [(lat_range[0] + lat_range[1]) / 2, (lon_range[0] + lon_range[1]) / 2]
    folium_map = folium.Map(location=map_center, zoom_start=12)  # Increased zoom level for more detail

    # Get bounds of the TIFF file
    lon_min, lon_max, lat_min, lat_max = get_tiff_bounds(tiff_file)
    
    # Check if selected lat/lon range is valid
    if not (lat_range[0] >= lat_min and lat_range[1] <= lat_max and
            lon_range[0] >= lon_min and lon_range[1] <= lon_max):
        print(f"Selected range is out of bounds.")
        return

    # Apply the reversed green colormap ('Greens_r') to the TIFF image and remove white areas (NaN)
    rgba_data, lon_min, lon_max, lat_min, lat_max = apply_colormap_to_tiff(tiff_file, colormap='Greens_r', lat_range=lat_range, lon_range=lon_range)

    if rgba_data is None:
        print("No valid data to overlay.")
        return

    # Add the TIFF as an overlay to the map
    overlay = raster_layers.ImageOverlay(
        rgba_data, 
        bounds=[[lat_min, lon_min], [lat_max, lon_max]], 
        opacity=0.5,  # 50% opacity for the overlay
        interactive=True,
        cross_origin=True,
        zindex=1
    )
    overlay.add_to(folium_map)

    # Add a custom legend for the Seagrass color (green)
    legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 70px; height: 50px; 
                    background-color: white; border: 2px solid black; z-index: 9999;
                    font-size: 14px;">
            <b>Seagrass</b><br>
            <i style="background: #006400; width: 68px; height: 30px; display: inline-block;"></i> 
        </div>
    '''
    folium_map.get_root().html.add_child(folium.Element(legend_html))

    # Save the map as an HTML file
    folium_map.save(save_path)
    print(f"Map with overlay and legend saved as {save_path}")

    # Display the map directly in the Jupyter notebook
    display(folium_map)
