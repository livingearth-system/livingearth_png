/* File: Sentinel1_woodyarti.js
This script was written by Carole Planque (Aberystwyth University).
Last update: 28.05.2023
The script uses the s1_ard.js file for Sentinel-1 pre-processing from users/adugnagirma/gee_s1_ard/: 
    Version: v1.2
    Date: 2021-03-10
    Authors: Mullissa A., Vollrath A., Braun, C., Slagter B., Balling J., Gou Y., Gorelick N.,  Reiche J.
    Description: This script creates an analysis ready S1 image collection.
    License: This code is distributed under the MIT License.

    Parameter:
        START_DATE: The earliest date to include images for (inclusive).
        END_DATE: The latest date to include images for (exclusive).
        POLARIZATION: The Sentinel-1 image polarization to select for processing.
            'VV' - selects the VV polarization.
            'VH' - selects the VH polarization.
            "VVVH' - selects both the VV and VH polarization for processing.
        ORBIT:  The orbits to include. (string: BOTH, ASCENDING or DESCENDING)
        GEOMETRY: The region to include imagery within.
                  The user can interactively draw a bounding box within the map window or define the edge coordinates.
        APPLY_BORDER_NOISE_CORRECTION: (Optional) true or false options to apply additional Border noise correction:
        APPLY_SPECKLE_FILTERING: (Optional) true or false options to apply speckle filter
        SPECKLE_FILTER: Type of speckle filtering to apply (String). If the APPLY_SPECKLE_FILTERING parameter is true then the selected speckle filter type will be used.
            'BOXCAR' - Applies a boxcar filter on each individual image in the collection
            'LEE' - Applies a Lee filter on each individual image in the collection based on [1]
            'GAMMA MAP' - Applies a Gamma maximum a-posterior speckle filter on each individual image in the collection based on [2] & [3]
            'REFINED LEE' - Applies the Refined Lee speckle filter on each individual image in the collection
                                  based on [4]
            'LEE SIGMA' - Applies the improved Lee sigma speckle filter on each individual image in the collection
                                  based on [5]
        SPECKLE_FILTER_FRAMEWORK: is the framework where filtering is applied (String). It can be 'MONO' or 'MULTI'. In the MONO case
                                  the filtering is applied to each image in the collection individually. Whereas, in the MULTI case,
                                  the Multitemporal Speckle filter is applied based on  [6] with any of the above mentioned speckle filters.
        SPECKLE_FILTER_KERNEL_SIZE: is the size of the filter spatial window applied in speckle filtering. It must be a positive odd integer.
        SPECKLE_FILTER_NR_OF_IMAGES: is the number of images to use in the multi-temporal speckle filter framework. All images are selected before the date of image to be filtered.
                                    However, if there are not enough images before it then images after the date are selected.
        TERRAIN_FLATTENING : (Optional) true or false option to apply Terrain correction based on [7] & [8]. 
        TERRAIN_FLATTENING_MODEL : model to use for radiometric terrain normalization (DIRECT, or VOLUME)
        DEM : digital elevation model (DEM) to use (as EE asset)
        TERRAIN_FLATTENING_ADDITIONAL_LAYOVER_SHADOW_BUFFER : additional buffer parameter for passive layover/shadow mask in meters
        FORMAT : the output format for the processed collection. this can be 'LINEAR' or 'DB'.
        CLIP_TO_ROI: (Optional) Clip the processed image to the region of interest.
        SAVE_ASSETS : (Optional) Exports the processed collection to an asset.
        
    Returns:
        An ee.ImageCollection with an analysis ready Sentinel 1 imagery with the specified polarization images and angle band.
        
    References
  [1]  J. S. Lee, “Digital image enhancement and noise filtering by use of local statistics,” 
    IEEE Pattern Anal. Machine Intell., vol. PAMI-2, pp. 165–168, Mar. 1980. 
  [2]  A. Lopes, R. Touzi, and E. Nezry, “Adaptative speckle filters and scene heterogeneity,
    IEEE Trans. Geosci. Remote Sensing, vol. 28, pp. 992–1000, Nov. 1990 
  [3]  Lopes, A.; Nezry, E.; Touzi, R.; Laur, H.  Maximum a posteriori speckle filtering and first204order texture models in SAR images.  
    10th annual international symposium on geoscience205and remote sensing. Ieee, 1990, pp. 2409–2412.
  [4] J.-S. Lee, M.R. Grunes, G. De Grandi. Polarimetric SAR speckle filtering and its implication for classification
    IEEE Trans. Geosci. Remote Sens., 37 (5) (1999), pp. 2363-2373.
  [5] Lee, J.-S.; Wen, J.-H.; Ainsworth, T.L.; Chen, K.-S.; Chen, A.J. Improved sigma filter for speckle filtering of SAR imagery. 
    IEEE Trans. Geosci. Remote Sens. 2009, 47, 202–213.
  [6] S. Quegan and J. J. Yu, “Filtering of multichannel SAR images, IEEE Trans Geosci. Remote Sensing, vol. 39, Nov. 2001.
  [7] Vollrath, A., Mullissa, A., & Reiche, J. (2020). Angular-Based Radiometric Slope Correction for Sentinel-1 on Google Earth Engine. 
    Remote Sensing, 12(11), [1867]. https://doi.org/10.3390/rs12111867
  [8] Hoekman, D.H.;  Reiche, J.   Multi-model radiometric slope correction of SAR images of complex terrain using a two-stage semi-empirical approach.
    Remote Sensing of Environment2222015,156, 1–10.
**/

var wrapper = require('users/adugnagirma/gee_s1_ard:wrapper');
var helper = require('users/adugnagirma/gee_s1_ard:utilities');

//---------------------------------------------------------------------------//
// DEFINE PARAMETERS
//---------------------------------------------------------------------------//
// var site_name = 'Sankian'
// var site = ee.Geometry.Rectangle([145.778479, -5.992290, 145.847265, -5.919063]);
// var site_name = 'Wowobo'
// var site = ee.Geometry.Rectangle([144.4, -7.4, 144.5, -7.3]);
// var site_name = 'AruAru'
// var site = ee.Geometry.Rectangle([146.388830, -8.602075, 146.411613, -8.573093]);
// var site_name = 'Bendoroda'
// var site = ee.Geometry.Rectangle([148.718626, -9.175858, 148.807852, -9.091956]);
// var site_name = 'PemMission'
// var site = ee.Geometry.Rectangle([149.757799, -9.633513, 149.801038, -9.590819]);
// var site_name = 'BogaBoga'
// var site = ee.Geometry.Rectangle([149.997712, -9.649198, 150.024834, -9.627239]);
// var site_name = 'PortMoresby'
// var site = ee.Geometry.Rectangle([147.145253, -9.472685, 147.172001, -9.445830]);

// var site = ee.Geometry.Rectangle([144.2, -7.5, 144.4, -7.3]);
var site = geometry;
var listCoords = ee.Array.cat(site.coordinates(), 1); 
var xCoords = listCoords.slice(1, 0, 1); 
var yCoords = listCoords.slice(1, 1, 2); 
var xMin = xCoords.reduce('min', [0]).get([0,0]); print('xMin',xMin.abs());
var yMin = yCoords.reduce('min', [0]).get([0,0]); print('yMin',yMin.abs());
var site_name = xMin.abs().multiply(10).format('%04d');
// print(site_name)
var parameter = {//1. Data Selection
              START_DATE: "2020-01-01",
              STOP_DATE: "2020-12-31",
              POLARIZATION:'VVVH',
              ORBIT : 'ASCENDING',
              GEOMETRY: site, //uncomment if interactively selecting a region of interest
              //2. Additional Border noise correction
              APPLY_ADDITIONAL_BORDER_NOISE_CORRECTION: true,
              //3.Speckle filter
              APPLY_SPECKLE_FILTERING: false,
              // SPECKLE_FILTER_FRAMEWORK: 'MULTI',
              // SPECKLE_FILTER: 'LEE',
              // SPECKLE_FILTER_KERNEL_SIZE: 1,
              // SPECKLE_FILTER_NR_OF_IMAGES: 1,
              // SPECKLE_FILTER_NR_OF_IMAGES: 10,
              //4. Radiometric terrain normalization
              APPLY_TERRAIN_FLATTENING: true,
              DEM: ee.Image('USGS/SRTMGL1_003'),
              TERRAIN_FLATTENING_MODEL: 'VOLUME',
              TERRAIN_FLATTENING_ADDITIONAL_LAYOVER_SHADOW_BUFFER: 0,
              //5. Output
              FORMAT : 'DB',
              CLIP_TO_ROI: false,
              SAVE_ASSETS: false
}

var saveTiff = false
var backscatter_lim = -19.0;
var months_cum = 10.8;
Map.centerObject(parameter.GEOMETRY, 11);
Map.addLayer(parameter.GEOMETRY, {color: 'FF0000'}, 'Site');
//---------------------------------------------------------------------------//
// DO THE JOB
//---------------------------------------------------------------------------//
      

//Preprocess the S1 collection
var s1_preprocces = wrapper.s1_preproc(parameter);

var s1 = s1_preprocces[0]
s1_preprocces = s1_preprocces[1]

//---------------------------------------------------------------------------//
// VISUALIZE
//---------------------------------------------------------------------------//

//Visulaization of the first image in the collection in RGB for VV, VH, images
var visparam = {}
if (parameter.POLARIZATION=='VVVH'){
     if (parameter.FORMAT=='DB'){
    var s1_preprocces_view = s1_preprocces.map(helper.add_ratio_lin).map(helper.lin_to_db2);
    var s1_view = s1.map(helper.add_ratio_lin).map(helper.lin_to_db2);
    visparam = {bands:['VV','VH','VVVH_ratio'],min: [-20, -25, 1],max: [0, -5, 15]}
    }
    else {
    var s1_preprocces_view = s1_preprocces.map(helper.add_ratio_lin);
    var s1_view = s1.map(helper.add_ratio_lin);
    visparam = {bands:['VV','VH','VVVH_ratio'], min: [0.01, 0.0032, 1.25],max: [1, 0.31, 31.62]}
    }
}
else {
    if (parameter.FORMAT=='DB') {
    s1_preprocces_view = s1_preprocces.map(helper.lin_to_db);
    s1_view = s1.map(helper.lin_to_db);
    visparam = {bands:[parameter.POLARIZATION],min: -25,max: 0}   
    }
    else {
    s1_preprocces_view = s1_preprocces;
    s1_view = s1;
    visparam = {bands:[parameter.POLARIZATION],min: 0,max: 0.2}
    }
}

// Map.addLayer(s1_view.first(), visparam, 'First image in the input S1 collection', true);
Map.addLayer(s1_preprocces_view.first(), visparam, 'First image in the processed S1 collection', true);


//---------------------------------------------------------------------------//
// FORMAT
//---------------------------------------------------------------------------//

//Convert format for export
if (parameter.FORMAT=='DB'){
  s1_preprocces = s1_preprocces.map(helper.lin_to_db);
}

print('PRE-PROCESSING DONE')
// print('This is returned', s1_preprocces.getInfo());


//---------------------------------------------------------------------------//
// EXTRACT
//---------------------------------------------------------------------------//

var datasetVH = s1_preprocces.select('VH');
// print('This is returned VH dataset', datasetVH.getInfo());

var threshold = function(image){
  var thresholding = image.gt(backscatter_lim);
  return thresholding;
};

// Thresholding VH
var thresholded_datasetVH = datasetVH.map(threshold);

// Duration
var sumVH = thresholded_datasetVH.sum();
var sumVH_months = sumVH.divide(datasetVH.count()).multiply(12);
// print('This is returned sum', sumVH.getInfo());
// Map.addLayer(sumVH_months, {min: 0, max: 12, palette: [
//     '440154', '481e70', '443a83', '3a528b', '31688e', '287c8e', '20908d',
//     '20a486', '35b779', '5dc962', '8fd744', 'c7e120', 'fde725']}, 'Scene sum Image'); 

// WoodyArti
var woody = sumVH_months.gt(months_cum);
// Map.addLayer(woody, {min: 0, max: 1, palette: [
//     'ffffff', '56b454']}, 'Woody'); 
// print('This is woody', woody.getInfo());


var woody_10m = woody.setDefaultProjection(woody.projection())
    // Request the data at original 10m scale and UTM projection.
    .reproject({
      crs: datasetVH.first().projection(),
      scale: 10,
    });


print('This is woody after reproj', woody_10m.getInfo());
Map.addLayer(woody_10m, {min: 0, max: 1, palette: [
    'ffffff', '56b454']}, 'Woody_10m'); 

// Define the chart and print it to the console.
var chart =
    ui.Chart.image.histogram({image: s1_preprocces_view.first().select('VH'), region: site, scale: 10})
        .setOptions({
          title: 'Duration Histogram',
          hAxis: {
            title: 'Number images',
            titleTextStyle: {italic: false, bold: true},
          },
          vAxis:
              {title: 'Count', titleTextStyle: {italic: false, bold: true}},
          colors: ['cf513e', '1d6b99', 'f0af07']
        });
print(chart);


// //---------------------------------------------------------------------------//
// // EXPORT
// //---------------------------------------------------------------------------//

//Save processed collection to asset
if(parameter.SAVE_ASSETS) {
helper.Download.ImageCollection.toAsset(s1_preprocces, '', 
              {scale: 10, 
              region: s1_preprocces.geometry(),
                type: 'float'})
}

//Export processed layer to geotiff
if(saveTiff) {
Export.image.toDrive({
  image: woody_10m,
  description: 'Woodyarti_30m_' + site_name,
  folder: 'GEE_Geotiffs',
  crs: 'EPSG:32755',
  scale: 30,
  region: site})
};
