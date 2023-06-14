import tempfile
import os
from datacube.virtual import construct, Transformation, Measurement
import xarray as xr
import datacube
from pathlib import Path
import rioxarray

# WOfS classifier
from wofs.virtualproduct import WOfSClassifier
from odc.algo import safe_div, apply_numexpr, keep_good_only

dc = datacube.Datacube()

class WOfS(Transformation):
    '''
    Load in Landsat SR and DEM to generate wofs summary for PNG on EASI ASIA 
                
    '''
    # Helper frunction from https://github.com/opendatacube/odc-stats/blob/develop/odc/stats/plugins/wofs.py
    def reduce(self, xx: xr.Dataset) -> xr.Dataset:
        nodata = -999
        count_some = xx.some.sum(axis=0, dtype="int16")
        count_wet = xx.wet.sum(axis=0, dtype="int16")
        count_dry = xx.dry.sum(axis=0, dtype="int16")
        count_clear = count_wet + count_dry
        frequency = safe_div(count_wet, count_clear, dtype="float32")
        
        count_wet.attrs["nodata"] = nodata
        count_clear.attrs["nodata"] = nodata
        
        is_ok = count_some > 0
        count_wet = keep_good_only(count_wet, is_ok)
        count_clear = keep_good_only(count_clear, is_ok)
        
        return xr.Dataset(
            dict(
                count_wet=count_wet,
                count_clear=count_clear,
                frequency=frequency,
            )
        )
    
    
    def compute(self, data):
        
        # rename bands, needed for xr_geomedian function
        data = data.rename({
            "blue": "nbart_blue",
            "green": "nbart_green",
            "red": "nbart_red",
            "nir08": "nbart_nir",
            "swir16": "nbart_swir_1",
            "swir22": "nbart_swir_2",
            "qa_pixel": "fmask"
        })

        # need a ODC dataset to use for a like call in the load DEM
        data_time_drop = data.isel(time=0)
        data_time_drop = data_time_drop.drop('time')
        
        # load DEM
        dem = dc.load(product="copernicus_dem_30", like=data_time_drop)
        elevation = dem.elevation
        
        # Need to save out DEM (fetched in WOfS function) - create a temp file to store this
        temp_dem_file = tempfile.mkstemp(prefix="le_lccs_dem_", suffix=".tif")[1]

        dem_path = Path(temp_dem_file)
        dem_path.parent.mkdir(parents=True, exist_ok=True)
        elevation.rio.to_raster(dem_path)        
        
        # run the WOfS classifier
        transform = WOfSClassifier(c2_scaling=True, dsm_path=temp_dem_file)

        # Compute the WOFS layer
        wofl = transform.compute(data)
        
        # Rename dimensions as required
        wofl = wofl.rename({"x": "longitude", "y": "latitude"})
        
        wofl["bad"] = (wofl.water & 0b0111_1110) > 0
        wofl["some"] = apply_numexpr("((water<<30)>>30)==0", wofl, name="some")
        wofl["dry"] = wofl.water == 0
        wofl["wet"] = wofl.water == 128
        wofl = wofl.drop_vars("water")
        for dv in wofl.data_vars.values():
            dv.attrs.pop("nodata", None)

        summary = self.reduce(wofl)
        # drop count data variables (leaving on wofs frequency)
        wofs = summary.drop_vars(['count_wet', 'count_clear'])

        # Re-rename dimensions as required
        wofs = wofs.rename({"longitude": "x", "latitude": "y"})
        
        # Remove temp DEM file
        os.remove(temp_dem_file)
        
        return wofs

    def measurements(self, input_measurements):
        return {'wofs': Measurement(name='frequency', dtype='float32', nodata=float('nan'), units='1')}
