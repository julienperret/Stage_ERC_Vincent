import sys
import gdal
import numpy as np
from time import time
from multiprocessing import Process

# Pour affichage dynamique de la progression
def printer(string):
	sys.stdout.write("\r\x1b[K" + string)
	sys.stdout.flush()

def getDone(function, argList):
    c = 0
    jobs = []
    for a in argList:
        jobs.append(Process(target=function, args=a))
    for j in jobs:
        j.start()
    for j in jobs:
        j.join()

# Calcul le temps d'exécution d'une étape
def getTime(start):
    execTime = time() - start
    execMin = round(execTime // 60)
    execSec = round(execTime % 60)
    return '%im %is' %(execMin, execSec)

# Enregistre un fichier .tif à partir d'un array et de variables GDAL stockées au préalable
def to_tif(array, dtype, proj, geot, path):
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
    ds = driver.Create(str(path), cols, rows, 1, dtype)
    ds.SetProjection(proj)
    ds.SetGeoTransform(geot)
    ds.GetRasterBand(1).WriteArray(array)
    ds = None

# Convertit un tif en numpy array
def to_array(tif, dtype=None):
    ds = gdal.Open(str(tif))
    if dtype :
        return ds.ReadAsArray().astype(dtype)
    else:
        return ds.ReadAsArray()
    ds = None
