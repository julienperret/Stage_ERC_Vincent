#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import gdal
import numpy as np

inDir = sys.argv[1]
outDir = sys.argv[2]

# Convertit un tif en numpy array
def to_array(tif, dtype=None):
    ds = gdal.Open(tif)
    if dtype == 'float32':
        return ds.ReadAsArray().astype(np.float32)
    elif dtype == 'uint16':
        return ds.ReadAsArray().astype(np.uint16)
    else:
        return ds.ReadAsArray()
    ds = None

# Enregistre un fichier .tif à partir d'un array et de variables GDAL stockée au préalable
def to_tif(array, dtype, path):
    ds_out = driver.Create(path, cols, rows, 1, dtype)
    ds_out.SetProjection(proj)
    ds_out.SetGeoTransform(geot)
    ds_out.GetRasterBand(1).WriteArray(array)
    ds_out = None

# Création des variables GDAL pour écriture de raster, indispensables pour la fonction to_tif()
ds = gdal.Open(inDir + '/pop_2015.tif')
population = ds.GetRasterBand(1).ReadAsArray().astype(np.uint16)
cols = ds.RasterXSize
rows = ds.RasterYSize
proj = ds.GetProjection()
geot = ds.GetGeoTransform()
driver = gdal.GetDriverByName('GTiff')
ds = None
del population

tifList = []
for tifFile in os.listdir(inDir):
    array = to_array(inDir + '/' + tifFile)
    array = array * 65535 / np.amax(array)
    to_tif(array, gdal.GDT_UInt16, outDir + '/' + tifFile)
