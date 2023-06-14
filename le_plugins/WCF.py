from datacube.virtual import construct, Transformation, Measurement
import xarray as xr
import datacube
import pickle
import sys
sys.path.append("/home/jovyan/code/dea-notebooks/Tools")
from dea_tools.classification import sklearn_unflatten
from dea_tools.classification import sklearn_flatten

class WCF(Transformation):
    '''
    Load in Geomedian and combine with WCF model to generate Woody Cover Fraction (WCF)           
    '''
    def __init__(self, model_pickle, **settings):
        """
        Takes an existing model saved out as a pickle file.
        """
        # Unpickle model
        with open(model_pickle, "rb") as f:
            self.ml_model_dict = pickle.load(f)

    def compute(self, data):
        # rename bands, needed for model predict
        data = data.rename({
            "nbart_blue": "blue",
            "nbart_green": "green",
            "nbart_red": "red",
            "nbart_nir": "nir",
            "nbart_swir_1": "swir1",
            "nbart_swir_2": "swir2"
        })
        
        # apply the model and rebuild structure of xarray to same as input
        data = data.drop_vars(['fmask'])
        flat = sklearn_flatten(data)
        results = self.ml_model_dict.predict(flat)
        predicted_wcf = (sklearn_unflatten(results,data).transpose())

        return predicted_wcf.to_dataset(name='WCF')

    def measurements(self, input_measurements):
        return {'WCF': Measurement(name='WCF', dtype='float32', nodata=float('nan'), units='1')}
