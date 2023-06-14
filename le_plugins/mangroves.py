from datacube.virtual import construct, Transformation, Measurement
import xarray as xr
import datacube
from datacube.utils import masking
from odc.algo import to_f32, xr_geomedian, int_geomedian

class geomedian(Transformation):
    '''
    Load in GMW layers based on time query (TODO: put these layers in an S3 bucket and call from there)    
    '''

    def get_gmw_layer(year):
        gmw_layers = {
            1996: '../data/GMW/gmw_v3_1996_vec.shp',
            2007: '../data/GMW/gmw_v3_2007_vec.shp',
            2008: '../data/GMW/gmw_v3_2008_vec.shp',
            2009: '../data/GMW/gmw_v3_2009_vec.shp',
            2010: '../data/GMW/gmw_v3_2010_vec.shp',
            2015: '../data/GMW/gmw_v3_2015_vec.shp',
            2016: '../data/GMW/gmw_v3_2016_vec.shp',
            2017: '../data/GMW/gmw_v3_2017_vec.shp',
            2018: '../data/GMW/gmw_v3_2018_vec.shp',
            2019: '../data/GMW/gmw_v3_2019_vec.shp',
            2020: '../data/GMW/gmw_v3_2020_vec.shp'
        }
        year_int = int(year)
        closest_year = min(gmw_layers.keys(), key=lambda y: abs(y - year_int))
        return gmw_layers[closest_year]
    
    
    def compute(self, data):
        
        
        return mangroves

    def measurements(self, input_measurements):
        return {'mangroves': Measurement(name='mangroves', dtype='float32', nodata=float('nan'), units='1')}
