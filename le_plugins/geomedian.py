from datacube.virtual import construct, Transformation, Measurement
import xarray as xr
import datacube
from datacube.utils import masking
from odc.algo import to_f32, xr_geomedian, int_geomedian

class geomedian(Transformation):
    '''
    Load in Landsat SR for PNG on EASI ASIA           
    '''

    def compute(self, data):
        # rename bands, needed for rgb function and for xr_geomedian
        data = data.rename({
            "blue": "nbart_blue",
            "green": "nbart_green",
            "red": "nbart_red",
            "nir08": "nbart_nir",
            "swir16": "nbart_swir_1",
            "swir22": "nbart_swir_2",
            "qa_pixel": "fmask"
        })
        
        # Make a mask array for the nodata value
        valid_mask = masking.valid_data_mask(data)

        # Define the scaling values (landsat8_c2l2_sr)
        scale_factor = 0.0000275
        add_offset = -0.2

        # Make a scaled data array
        # scaled_data = ds * scale_factor + add_offset
        scaled_data = to_f32(data,
                             scale=scale_factor,
                             offset=add_offset)
        
        # Make a cloud mask (landsat8_c2l2_sr)
        # Multiple flags are combined as logical AND (bitwise)
        cloud_mask = masking.make_mask(data['fmask'],
                                       clear='clear')
        # Apply each of the masks
        filtered_data = scaled_data.where(valid_mask & cloud_mask)

        geomedian = xr_geomedian(filtered_data,
                                 num_threads=1, # Setting num_thread=1 will disable the internal threading and instead allow parallelisation with dask.
                                 eps=1e-7, # The eps parameter controls the number of iterations to conduct; a good default is 1e-7.
                                )
        return geomedian

    def measurements(self, input_measurements):
        return {'geomedian': Measurement(name='geomedian', dtype='float32', nodata=float('nan'), units='1')}
