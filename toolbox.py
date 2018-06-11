import sys
import gdal
import numpy as np
from time import time
from multiprocessing import Process

# Pour la gestion des slashs en fin de chemin
def slashify(path):
    if path[len(path)-1] != '/':
        return path + '/'
    else:
        return path

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
    elif dtype == 'int16':
        dtype = gdal.GDT_Int16
    else :
        dtype = gdal.GDT_Unknown
    ds_out = driver.Create(path, cols, rows, 1, dtype)
    ds_out.SetProjection(proj)
    ds_out.SetGeoTransform(geot)
    ds_out.GetRasterBand(1).WriteArray(array)
    ds_out = None

# Convertit un tif en numpy array
def to_array(tif, dtype=None):
    ds = gdal.Open(tif)
    if dtype == 'byte':
        return ds.ReadAsArray().astype(np.byte)
    elif dtype == 'float32':
        return ds.ReadAsArray().astype(np.float32)
    elif dtype == 'uint16':
        return ds.ReadAsArray().astype(np.uint16)
    elif dtype == 'int16':
        return ds.ReadAsArray().astype(np.int16)
    else:
        return ds.ReadAsArray()
    ds = None
