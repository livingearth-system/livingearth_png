from datacube.virtual import construct, Transformation, Measurement
import xarray as xr
import datacube
from datacube.utils import masking

from fc.fractional_cover import fractional_cover as f_cover

class fractional_cover(Transformation):
    '''
    Load in Landsat SR to generate fraction cover summary for PNG on EASI ASIA                 
    '''

    def compute(self, data):
    
        # Rename the data variables to match the fractional cover function's requirements
        data = data.rename({
            "nir08": "nir",
            "swir16": "swir1",
            "swir22": "swir2",
            "qa_pixel": "fmask"
        })   
        
        # Make a mask array for the nodata value
        valid_mask = masking.valid_data_mask(data)
        
        # Make a cloud mask (landsat8_c2l2_sr)
        # Multiple flags are combined as logical AND (bitwise)
        cloud_mask = masking.make_mask(data['fmask'], clear='clear')

        # Apply each of the masks
        filtered_data = data.where(valid_mask & cloud_mask)
        
        # create ds_fc for each time step and concatenate them along time dimension
        ds_fc_list = []
        for t in filtered_data.time:
            ds_t = filtered_data.sel(time=t)
            ds_fc_t = f_cover(ds_t)
            ds_fc_list.append(ds_fc_t)

        ds_fc = xr.concat(ds_fc_list, dim='time').transpose('time', 'y', 'x')
        # correct times added back in
        ds_fc['time'] = filtered_data.time

        # replace negative values with NaN
        ds_fc = ds_fc.where(ds_fc >= 0)  

        # Resample to annual frequency and skip NaN values
        ds_fc = ds_fc.resample(time='A').mean(skipna=True)

        # Calculate percentiles
        fc_percentile = ds_fc.quantile(q=[0.9], dim='time')

        # Convert to percentages and rename variables
        # fc_percentile_annual = fc_percentile_annual * 100
        fc_percentile = fc_percentile.rename({'PV': 'PV_PC_90',
                                                            'NPV': 'NPV_PC_90',
                                                            'BS': 'BS_PC_90',
                                                            'UE': 'UE_PC_90'})
        # remove 'quantile' dim
        fc_percentile = fc_percentile.squeeze()

        return fc_percentile

    def measurements(self, input_measurements):
        return {'fc_percentile': Measurement(name='fc_percentile', dtype='float32', nodata=float('nan'), units='1')}
