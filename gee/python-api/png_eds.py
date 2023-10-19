#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Version: v1.0
Date: 2023-05-22
Author: Carole Planque
Description: Generate a woody/building (i.e., height layer) from Sentinel-1 GEE ImageCollection.
"""

import ee

BACKSCATTER_LIM = -19.0;
MONTHS_CUM = 10.8;

def threshold(image):
    thresholding = image.gt(BACKSCATTER_LIM)
    return thresholding

def summarize(MyImageCollection):
    datasetVH = MyImageCollection.select('VH');
    thresholded_datasetVH = datasetVH.map(threshold);
    sumVH = thresholded_datasetVH.sum();
    sumVH_months = sumVH.divide(datasetVH.count()).multiply(12);
    return sumVH_months

def woodyarti(S1_ImageCollection):
    sumVH_months = summarize(S1_ImageCollection);
    woody = sumVH_months.gt(MONTHS_CUM);
    woody_10m = woody.setDefaultProjection(woody.projection()).reproject(
        crs= S1_ImageCollection.select('VH').first().projection(), scale= 10);
    return woody_10m
