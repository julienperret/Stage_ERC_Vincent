#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import gdal
import traceback
import numpy as np
from shutil import rmtree
from ast import literal_eval

if sys.platform != 'linux':
    print('Ce script fonctionne sur Linux uniquement.')
    sys.exit()

# Pour la gestion des slashs en fin de chemin
def slashify(path):
    if path[len(path)-1] != '/':
        return path + '/'
    else:
        return path

inDir = slashify(sys.argv[1])
if len(sys.argv) > 2:
    argStr = sys.argv[2].split()
    for arg in argStr:
        if 'maxValues' in arg:
            maxValues = literal_eval(arg.split('=')[1])
        elif 'delay' in arg:
            delay = arg.split('=')[1]
        elif 'outDir' in arg:
            outDir = slashify(sys.argv[2])

def getHighValue(dType):
    if dType == 'byte':
        npType = np.int8
        v = 2 ** 8 - 1
    elif dType == 'uint16':
        npType = np.uint16
        v = 2 ** 16 - 1
    elif dType == 'uint32':
        npType = np.uint32
        v = 2 ** 32 - 1
    elif dType == 'float32':
        npType = np.float32
        v = (2 - 2 ** -23) * 2 ** 127
    return (v, npType)

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

if 'outDir' not in globals():
    oneOutDir = False

try:
    # Création des variables GDAL pour écriture de raster, indispensables pour la fonction to_tif()
    snapsType = os.listdir(inDir)
    c = 0
    for basename in snapsType:
        print('Processing "' + basename + '"' )
        if basename == 'urbanisation':
            maxV = 1
            highValue, npType = getHighValue('byte')
            dataType = 'byte'
        else:
            highValue, npType = getHighValue('uint16')
            dataType = 'uint16'

        d = inDir + basename + '/'
        lastFile = d + os.listdir(d)[len(os.listdir(d)) - 1]
        ds = gdal.Open(lastFile)
        geot = ds.GetGeoTransform()
        pixSize = int(geot[1])
        srfCell = pixSize * pixSize
        tif = ds.GetRasterBand(1).ReadAsArray().astype(npType)
        driver = gdal.GetDriverByName('GTiff')
        ds = None
        if os.path.exists(d + 'tmp'):
            rmtree(d + 'tmp')
        os.makedirs(d + 'tmp')

        if 'delay' not in globals():
            delay = str(round(len(os.listdir(d))/2))

        for file in os.listdir(d):
            if os.path.splitext(file)[1] == '.tif':
                if basename == 'urbanisation':
                    array = to_array(d + file, np.uint8)
                    array = (array * highValue / maxV).astype(npType)
                elif basename == 'surface_sol':
                    maxV = srfCell
                    array = to_array(d + file, np.uint32)
                    array = (array * highValue / maxV).astype(npType)
                else:
                    if 'maxValues' in globals():
                        maxV = maxValues[c]
                        if maxV == 0:
                            maxV = tif.max()
                    else:
                        maxV = tif.max()
                    array = to_array(d + file, np.uint32)
                    array = (array * highValue / maxV).astype(npType)

                to_tif(array, dataType, d + 'tmp/' + basename + file.replace('.tif','').split('_')[1] + '.tif')

        if not oneOutDir:
            outDir = d
        os.system('convert -delay ' + delay + ' -loop 0 ' + d + 'tmp/*.tif ' + outDir + 'evo_' + basename + '.gif')
        rmtree(d + 'tmp')

        c += 1

    print('Done.')

except:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    print("\n*** Error :")
    traceback.print_exception(exc_type, exc_value, exc_traceback, limit=2, file=sys.stdout)
    sys.exit()
