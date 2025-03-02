import matplotlib.pyplot as plt  # Make sure to import pyplot as plt
from matplotlib.ticker import FuncFormatter
from matplotlib.colors import ListedColormap, BoundaryNorm
import matplotlib.patches as mpatches
from colourschemes import vegetated_colours, vegetated_labels  # Import colour scheme

def plot_vegetated_areas(vegetat_veg_cat_ds, vegetated_colours, vegetated_labels, title="Collation of Vegetated Areas", output_file="../figures/collated_vegetated.png"):

    # Extract colors and values
    colors, values = zip(*vegetated_colours.items())

    # Colour map and normalization
    vegetated_cmap = ListedColormap(colors)
    vegetated_norm = BoundaryNorm([v[0] for v in values] + [max(v[0] for v in values) + 1], len(values))

    # Create figure and axis
    fig, ax = plt.subplots()

    # Plot the xarray dataset without auto colorbar
    im = vegetat_veg_cat_ds.vegetat_veg_cat.plot(cmap=vegetated_cmap, norm=vegetated_norm, ax=ax, add_colorbar=False)

    # Set aspect ratio to equal
    ax.set_aspect("equal")  # Ensures x and y tick distances are the same

    # Remove axis labels
    ax.set_xlabel("")  # Remove X-axis label
    ax.set_ylabel("")  # Remove Y-axis label

    # Format axis labels as full numbers (no decimals)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{int(x)}"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{int(y)}"))  # Y-axis as full numbers

    # Manually create legend patches with black outlines
    legend_patches = [mpatches.Patch(facecolor=color, edgecolor="black", label=label) for color, label in zip(colors, vegetated_labels)]

    # Add legend at the bottom of the figure
    ax.legend(handles=legend_patches, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=len(legend_patches), frameon=False)

    # Set a custom title
    ax.set_title(title)

    # Save the figure as a PNG file
    plt.savefig(output_file, dpi=300, bbox_inches="tight")

    # Display the plot
    plt.show()
    

    
    
def plot_areas(input, colours, labels, title, output_file):

    # Extract colors and values
    colors, values = zip(*colours.items())

    # Colour map and normalization
    cmap = ListedColormap(colors)
    norm = BoundaryNorm([v[0] for v in values] + [max(v[0] for v in values) + 1], len(values))

    # Create figure and axis
    fig, ax = plt.subplots()

    # Plot the xarray dataset without auto colorbar
    im = input.plot(cmap=cmap, norm=norm, ax=ax, add_colorbar=False)

    # Set aspect ratio to equal
    ax.set_aspect("equal")  # Ensures x and y tick distances are the same

    # Remove axis labels
    ax.set_xlabel("")  # Remove X-axis label
    ax.set_ylabel("")  # Remove Y-axis label

    # Format axis labels as full numbers (no decimals)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{int(x)}"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{int(y)}"))  # Y-axis as full numbers

    # Manually create legend patches with black outlines
    legend_patches = [mpatches.Patch(facecolor=color, edgecolor="black", label=label) for color, label in zip(colors, labels)]

    # Add legend at the bottom of the figure
    ax.legend(handles=legend_patches, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=len(legend_patches), frameon=False)

    # Set a custom title
    ax.set_title(title)

    # Save the figure as a PNG file
    plt.savefig(output_file, dpi=300, bbox_inches="tight")

    # Display the plot
    plt.show()    
    
    
def stat_summary(xarr, scheme):
    """
    A function to perform summary statistics on an xarray object and return as a pandas
    dataframe.
    """
    # Search habitat types in farm
    lc_types = np.unique(xarr, return_counts=True)

    # Create dictionary to store outputs. Will convert this to a pandas data frame
    out_stat_dict = {"CATEGORY": [], "HECTARE": []}

    for color, label in scheme.items():
        if (label[0] in lc_types[0]) & (label[0] != 0):
            out_stat_dict["CATEGORY"].append(label[1])
            area_ha = (lc_types[1][list(farm_types[0]).index(label[0])] * 100) / 10000
            out_stat_dict["HECTARE"].append(area_ha)

    # Convert to a pandas dataframe
    out_stat_df = pd.DataFrame.from_dict(out_stat_dict)

    # Calculate percentage
    out_stat_df["PERCENT"] = 100*out_stat_df["HECTARE"] / out_stat_df["HECTARE"].sum()
    return out_stat_df


import xarray as xr  # Make sure to import xarray
import rasterio
from rasterio.transform import from_bounds
import numpy as np

import xarray as xr  # Make sure to import xarray
import rasterio
from rasterio.transform import from_bounds
import numpy as np

import xarray as xr  # Make sure to import xarray
import rasterio
from rasterio.transform import from_bounds
import numpy as np

def export_to_geotiff(dataset, output_path, band_name=None):
    """
    Exports a DataArray or Dataset to a GeoTIFF.
    
    Parameters:
    - dataset: xarray.DataArray or xarray.Dataset (Loaded from Open Data Cube or similar)
    - output_path: str (Path to save the GeoTIFF)
    - band_name: str (Optional, band name to extract if the input is a Dataset)
    """
    # If dataset is a Dataset (contains multiple variables)
    if isinstance(dataset, xr.Dataset):
        if band_name is None:
            raise ValueError("You must specify a band_name when using a Dataset.")
        if band_name not in dataset:
            raise ValueError(f"Band '{band_name}' not found in dataset. Available bands: {list(dataset.data_vars)}")
        data_array = dataset[band_name].values
    # If dataset is a DataArray (a single variable)
    elif isinstance(dataset, xr.DataArray):
        data_array = dataset.values
    else:
        raise ValueError("Input dataset must be either an xarray.DataArray or an xarray.Dataset.")
    
    # Convert boolean values to integers (True -> 1, False -> 0)
    if data_array.dtype == np.bool_:
        data_array = data_array.astype(np.int8)

    # Squeeze any unnecessary dimensions
    data_array = np.squeeze(data_array)
    
    # Extract CRS and transformation
    crs = dataset.geobox.crs
    transform = dataset.geobox.transform
    
    # Save as GeoTIFF
    with rasterio.open(
        output_path,
        "w",
        driver="GTiff",
        height=data_array.shape[0],  # The first dimension is typically height
        width=data_array.shape[1],   # The second dimension is typically width
        count=1,  # Single band
        dtype=data_array.dtype,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(data_array, 1)  # Write first band
    
    print(f"GeoTIFF saved to: {output_path}")
