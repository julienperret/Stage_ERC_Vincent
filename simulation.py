#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import gdal
import numpy
import pandas

# ignorer les erreurs de numpy lors d'une division par 0
numpy.seterr(divide='ignore', invalid='ignore')

# modifie le répertoire de travail de python selon le choix utilisateur
if(len(sys.argv) > 3):
    workspace = sys.argv[3]
    os.chdir(workspace)

if not os.path.exists('output'):
    os.mkdir('output')

# stockage et contrôle de la validité des paramètres utilisateur
taux = float(sys.argv[1])
seuil = sys.argv[2]
if taux > 3:
    print('Taux d''évolution trop élevé, valeur max acceptée : 3 %')
    sys.exit()
if seuil not in {'max', 'mean', 'q3'}:
    print('Argument de seuil invalide.\nValeurs possibles : max, mean, q3')
    sys.exit()

# écrit un fichier .tif à partir d'un array et de variables GDAL stockée au préalable


def to_tif(array, path, dtype):
    ds_out = driver.Create(path, cols, rows, 1, dtype)
    ds_out.SetProjection(projection)
    ds_out.SetGeoTransform(geotransform)
    ds_out.GetRasterBand(1).WriteArray(array)
    ds_out = None

# algorithme de tirage pour répartition de la population


def peupler(id, pop):
    # création d'arrays d'intérêt et de capacité masqués autour de l'IRIS
    weight = numpy.where((iris == id) & (capacite > 0), interet, 0)
    weightRowSum = numpy.sum(weight, 1)
    capaIris = numpy.where((iris == id), capacite, 0)
    popIris = numpy.zeros([rows, cols], dtype=numpy.uint16)
    popLogee = 0

    # boucle de réparition de la population
    while popLogee < pop:
        # tirage pondéré selon l'intérêt à urbaniser
        row = numpy.where(weightRowSum == numpy.random.choice(
            weightRowSum, p=weightRowSum / sum(weightRowSum)))[0][0]
        col = numpy.where(weight[row] == numpy.random.choice(
            weight[row], p=weight[row] / sum(weight[row])))[0][0]
        # peuplement de la cellule tirée + mise à jour des arrays population et capacité
        if capaIris[row][col] > 0:
            popIris[row][col] += 1
            capaIris[row][col] -= 1
            popLogee += 1
            # mise à jour de l'intérêt à zéro quand la capcité d'accueil est dépasée
            if capaIris[row][col] == 0:
                weight[row][col] = 0
                weightRowSum = numpy.sum(weight, 1)
        # condition de sortie en cas de saturation du quartier
        if sum(sum(capaIris)) == 0:
            break
    # écriture des populations et capacités futures
    global popNouvelle
    popNouvelle += popIris
    global capaFuture
    capaFuture += capaIris
    reste = pop - popLogee
    return reste


# calcul des projections démographiques
demographie = pandas.read_csv('demo.csv')
i = 0
while i < 26:
    if i != 0:
        demographie['pal40'] = demographie['pal40'] + \
            ((demographie['pal40'] + demographie['p14']) * (taux / 100))
    else:
        demographie['pal40'] = demographie['p14'] * (taux / 100)
    i += 1

# création du CSV des projections démographiques
demographie['pal40'] = demographie['pal40'].astype(int)
demographie.to_csv('output/proj.csv', index=0)
del demographie
dicIris = {row[0]: row[5]
           for _, row in pandas.read_csv('output/proj.csv').iterrows()}

# création du CSV des coefficients de pondération de l'intérêt à urbaniser
poids = pandas.read_csv('poids.csv')
poids['coef'] = poids['poids'] / sum(poids['poids'])
poids.to_csv('output/coef.csv', index=0, columns=['bande', 'coef'])
del poids
dicCoef = {row[0]: row[1]
           for _, row in pandas.read_csv('output/coef.csv').iterrows()}

# création des variables GDAL pour écriture de raster
ds = gdal.Open('pop.tif')
population = ds.GetRasterBand(1).ReadAsArray().astype(numpy.uint16)
cols = ds.RasterXSize
rows = ds.RasterYSize
projection = ds.GetProjection()
geotransform = ds.GetGeoTransform()
driver = gdal.GetDriverByName('GTiff')

# conversion des autres raster d'entrée en numpy array
ds = gdal.Open('capa_' + seuil + '.tif')
capacite = ds.GetRasterBand(1).ReadAsArray().astype(numpy.uint16)
ds = gdal.Open('iris.tif')
iris = ds.GetRasterBand(1).ReadAsArray().astype(numpy.uint16)
ds = gdal.Open('mask.tif')
mask = ds.GetRasterBand(1).ReadAsArray()
ds = gdal.Open('rest.tif')
restriction = ds.GetRasterBand(1).ReadAsArray()
ds = gdal.Open('eco.tif')
nonImpEco = ds.GetRasterBand(1).ReadAsArray().astype(numpy.float32)
ds = gdal.Open('ocs.tif')
ocsol = ds.GetRasterBand(1).ReadAsArray().astype(numpy.float32)
ds = gdal.Open('rout.tif')
routes = ds.GetRasterBand(1).ReadAsArray().astype(numpy.float32)

ds = gdal.Open('amen.tif')
administratif = ds.GetRasterBand(1).ReadAsArray().astype(numpy.float32)
commerces = ds.GetRasterBand(2).ReadAsArray().astype(numpy.float32)
loisirs = ds.GetRasterBand(3).ReadAsArray().astype(numpy.float32)
sante = ds.GetRasterBand(4).ReadAsArray().astype(numpy.float32)
scolaire = ds.GetRasterBand(5).ReadAsArray().astype(numpy.float32)
transport = ds.GetRasterBand(6).ReadAsArray().astype(numpy.float32)

# mise en place du masque sur la capacité d'accueil
capacite = numpy.where((restriction != 1) & (mask != 1), capacite, 0)
ds = None
to_tif(capacite, 'output/capa.tif', gdal.GDT_UInt16)

# création du raster final d'intérêt avec pondération
interet = numpy.where((mask != 1), ((nonImpEco * dicCoef['eco']) + (routes * dicCoef['rout']) + (ocsol * dicCoef['ocs']) + (administratif * dicCoef['admin']) + (
    commerces * dicCoef['comm']) + (loisirs * dicCoef['lois']) + (sante * dicCoef['sant']) + (scolaire * dicCoef['scol']) + (transport * dicCoef['trans'])), 0)
to_tif(interet, 'output/interet.tif', gdal.GDT_Float32)

# nettoyage des variables inutiles en mémoire
del restriction, nonImpEco, ocsol, routes, administratif, commerces, loisirs, sante, scolaire, transport

# création de tableaux vides pour écriture des raster de sortie
popNouvelle = numpy.zeros([rows, cols], dtype=numpy.uint16)
capaFuture = numpy.zeros([rows, cols], dtype=numpy.uint16)

# boucle dans les IRIS pour répartir la population
first = True
for id in dicIris.keys():
    print('IRIS n° ' + str(id) + '/' + str(len(dicIris)))
    popALoger = dicIris[id]
    if not first:
        popRestante = peupler(id, popALoger + popRestante)
    else:
        popRestante = peupler(id, popALoger)
        first = False
    print('Population à reloger : ' + str(popRestante))

# écriture des résultats
to_tif(popNouvelle, 'output/population_nouvelle.tif', gdal.GDT_UInt16)
to_tif(capaFuture, 'output/capacite_future.tif', gdal.GDT_UInt16)
popFuture = population + popNouvelle
to_tif(popFuture, 'output/population_future.tif', gdal.GDT_UInt16)
expansion = numpy.where((population == 0) & (popFuture > 0), 1, 0)
to_tif(expansion, 'output/expansion.tif', gdal.GDT_Byte)
capaSaturee = numpy.where((capacite > 0) & (capaFuture == 0), 1, 0)
to_tif(capaSaturee, 'output/capacite_saturee', gdal.GDT_Byte)
