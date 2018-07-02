#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import gdal
import traceback
import numpy as np
from shutil import rmtree

# Pour la gestion des slashs en fin de chemin
def slashify(path):
    if path[len(path)-1] != '/':
        return path + '/'
    else:
        return path

inDir = slashify(sys.argv[1])
outDir = slashify(sys.argv[2])
dType = sys.argv[3]
if len(sys.argv) > 4:
    argStr = sys.argv[4].split()
    for arg in argStr:
        if 'maxValue' in arg:
            maxValue = int(arg.split('=')[1])
        if 'delay' in arg:
            delay = arg.split('=')[1]

if dType == 'byte':
    npType = np.int8
    highValue = 2 ** 8 - 1
elif dType == 'uint16':
    npType = np.uint16
    highValue = 2 ** 16 - 1
elif dType == 'uint32':
    npType = np.uint32
    highValue = 2 ** 32 - 1
elif dType == 'float32':
    npType = np.float32
    highValue = (2 - 2 ** -23) * 2 ** 127

# Convertit un tif en numpy array
def to_array(tif, dtype=None):
    ds = gdal.Open(tif)
    if dtype :
        return ds.ReadAsArray().astype(dtype)
    else:
        return ds.ReadAsArray()
    ds = None

# Version modifiée de to_tif sans géoréférencement
def to_tif(array, dtype, path):
    cols, rows = array.shape[1], array.shape[0] # x, y
    driver = gdal.GetDriverByName('GTiff')
    if dtype == 'byte':
        dtype = gdal.GDT_Byte
    elif dtype == 'float32':
        dtype = gdal.GDT_Float32
    elif dtype == 'uint16':
        dtype = gdal.GDT_UInt16
    elif dtype == 'uint32':
        dtype = gdal.GDT_UInt32
    else :
        dtype = gdal.GDT_Unknown
    ds_out = driver.Create(path, cols, rows, 1, dtype)
    ds_out.GetRasterBand(1).WriteArray(array)
    ds_out = None

try:
    # Création des variables GDAL pour écriture de raster, indispensables pour la fonction to_tif()
    ds = gdal.Open(inDir + os.listdir(inDir)[len(os.listdir())-1])
    tif = ds.GetRasterBand(1).ReadAsArray().astype(npType)
    driver = gdal.GetDriverByName('GTiff')
    ds = None

    if 'delay' not in globals():
        delay = str(len(os.listdir(inDir)))
    if 'maxValue' not in globals():
        maxValue = tif.max()

    os.makedirs(outDir + 'tmp')
    for tif in os.listdir(inDir):
        if os.path.splitext(tif)[1] == '.tif':
            basename = os.path.splitext(tif.split('/')[len(tif.split('/'))-1])[0]
            if dType == 'float32':
                array = to_array(inDir + '/' + tif, np.float64)
                array = (array * highValue / maxValue).astype(npType)
            elif 'uint' in dType:
                array = to_array(inDir + '/' + tif, np.uint64)
                array = (array * highValue / maxValue).astype(npType)
            elif dType == 'byte':
                array = to_array(inDir + '/' + tif, np.uint8)
                array = (array * highValue / maxValue).astype(npType)
            to_tif(array, dType, outDir + '/tmp/' + basename + '.tif')

    os.system('convert -delay ' + delay + ' -loop 0 ' + outDir + 'tmp/*.tif ' + outDir + 'evo_' + basename.split('_')[0] + '.gif')
    rmtree(outDir + 'tmp')

except:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    print("\n*** Error :")
    traceback.print_exception(exc_type, exc_value, exc_traceback, limit=2, file=sys.stdout)
    sys.exit()
