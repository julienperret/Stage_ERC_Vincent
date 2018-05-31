#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import gdal
import traceback
import numpy as np
from shutil import rmtree

inDir = sys.argv[1]
outDir = sys.argv[2]
if len(sys.argv) > 3:
    argStr = sys.argv[3].split()
    for arg in argStr:
        if 'maxValue' in arg:
            maxValue = int(arg.split('=')[1])
        if 'delay' in arg:
            delay = arg.split('=')[1]

if 'delay' not in globals():
    delay = str(len(os.listdir(inDir)))

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

# Enregistre un fichier .png à partir d'un array et de variables GDAL stockée au préalable
def to_tif(array, dtype, path):
    ds_out = driver.Create(path, cols, rows, 1, dtype)
    ds_out.GetRasterBand(1).WriteArray(array)
    ds_out = None

try:
    # Création des variables GDAL pour écriture de raster, indispensables pour la fonction to_tif()
    ds = gdal.Open(inDir + 'pop_2040.tif')
    population = ds.GetRasterBand(1).ReadAsArray().astype(np.uint16)
    cols = ds.RasterXSize
    rows = ds.RasterYSize
    driver = gdal.GetDriverByName('GTiff')
    ds = None

    if 'maxValue' not in globals():
        maxValue = population.max()
    del population

    os.mkdir(outDir + 'tmp')
    for tifPath in os.listdir(inDir):
        if os.path.splitext(tifPath)[1] == '.tif':
            basename = os.path.splitext(tifPath.split('/')[len(tifPath.split('/'))-1])[0]
            array = to_array(inDir + '/' + tifPath).astype(np.uint32)
            array = (array * 65535 / maxValue).astype(np.uint16)
            to_tif(array, gdal.GDT_UInt16, outDir + '/tmp/' + basename + '.tif')

    os.system('convert -delay ' + delay + ' -loop 0 ' + outDir + 'tmp/*.tif ' + outDir + 'evo_demo.gif')
    rmtree(outDir + 'tmp')

except:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    print("\n*** Error :")
    traceback.print_exception(exc_type, exc_value, exc_traceback, limit=2, file=sys.stdout)
    sys.exit()
