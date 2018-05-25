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

tifList = []
for tif in os.listdir(inDir):
    array = to_array(inDir + '/' + tif)
    array = array * 65535 / np.amax(array)
    to_tif(outDir + '/' + tif + '.tif')
