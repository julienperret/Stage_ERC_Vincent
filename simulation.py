#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import gdal
import numpy as np
import pandas as pd

# Ignorer les erreurs de numpy lors d'une division par 0
np.seterr(divide='ignore', invalid='ignore')

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

# Fonction de répartition de la population
def peupler(id, pop, mode='souple'):
    # Création d'arrays d'intérêt et de capacité masqués autour de l'IRIS
    weight = np.where((iris == id) & (capacite > 0), interet, 0)
    weightRowSum = np.sum(weight, 1)
    capaIris = np.where((iris == id), capacite, 0)
    popIris = np.zeros([rows, cols], dtype=np.uint16)
    popLogee = 0

    # Boucle de réparition de la population
    while popLogee < pop:
        # Tirage pondéré selon l'intérêt à urbaniser
        row = np.where(weightRowSum == np.random.choice(
            weightRowSum, p=weightRowSum / sum(weightRowSum)))[0][0]
        col = np.where(weight[row] == np.random.choice(
            weight[row], p=weight[row] / sum(weight[row])))[0][0]
        # Peuplement de la cellule tirée + mise à jour des arrays population et capacité
        if capaIris[row][col] > 0:
            popIris[row][col] += 1
            capaIris[row][col] -= 1
            popLogee += 1
            # Mise à jour de l'intérêt à zéro quand la capcité d'accueil est dépasée
            if capaIris[row][col] == 0:
                weight[row][col] = 0
                weightRowSum = np.sum(weight, 1)
        # Condition de sortie en cas de saturation du quartier
        if sum(sum(capaIris)) == 0:
            break
    # Ecriture des populations et capacités futures
    global popNouvelle
    popNouvelle += popIris
    global capaFuture
    capaFuture += capaIris
    reste = pop - popLogee
    return reste

# Stockage et contrôle de la validité des paramètres utilisateur
workspace = sys.argv[1]
os.chdir(workspace)
if not os.path.exists('output'):
    os.mkdir('output')
taux = float(sys.argv[2])
if taux > 3:
    print('Taux d''évolution trop élevé, valeur max acceptée : 3 %')
    sys.exit()
if len(sys.argv) > 3:
    mode = sys.argv[3]
    if mode not in {'souple', 'strict'}:
        print('Mode de seuillage invalide\nValeurs possibles : souple ou strict')
        sys.exit()
else:
    mode = 'souple'

finalYear = 2040

# Création des dataframes contenant les informations par IRIS
irisDf = pd.read_csv('iris.csv')
nbIris = len(irisDf)
contigDic = {row[0]: row[4] for _, row in irisDf.iterrows()}

# Projections démograhpiques
irisDf['population'] = irisDf['population'].astype(int)
popDf = pd.DataFrame()
popDf['id'] = [i + 1 for i in range(nbIris)]
for year in range(2014, 2041):
    popDf[year] = 0
for id in range(nbIris):
    year = 2014
    pop = irisDf['population'][id]
    popDf[year][id] = pop
    year += 1
    while year <= finalYear:
        popDf[year][id] = pop * (taux / 100)
        pop += pop * (taux / 100)
        year += 1
popDf.to_csv('output/demographie.csv', index=0)

# Nombre total de personnes à loger - permet de vérifier si le raster capacité pourra tout contenir
sumPopALoger = sum(popDf.sum()) - sum(range(nbIris + 1)) - sum(popDf[2014])
print('Population à loger d\'ici à ' +
      str(finalYear) + ' : ' + str(sumPopALoger))

# Calcul des coefficients de pondération de chaque raster d'intérêt, csv des poids dans le répertoire des données locales
poids = pd.read_csv('../poids.csv')
poids['coef'] = poids['poids'] / sum(poids['poids'])
poids.to_csv('output/coefficients.csv', index=0, columns=['raster', 'coef'])
del poids
dicCoef = {row[0]: row[1]
           for _, row in pd.read_csv('output/coefficients.csv').iterrows()}

# Création des variables GDAL pour écriture de raster
ds = gdal.Open('population.tif')
population = ds.GetRasterBand(1).ReadAsArray().astype(np.uint16)
cols = ds.RasterXSize
rows = ds.RasterYSize
proj = ds.GetProjection()
geot = ds.GetGeoTransform()
driver = gdal.GetDriverByName('GTiff')
ds = None

# Conversion des autres raster d'entrée en numpy array
capacite = to_array('capacite.tif', 'uint16')
iris = to_array('iris_id.tif', 'uint16')
restriction = to_array('restriction.tif')
ecologie = to_array('ecologie.tif', 'float32')
ocsol = to_array('ocsol.tif', 'float32')
routes = to_array('routes.tif', 'float32')
transport = to_array('transport.tif', 'float32')
administratif = to_array('administratif.tif', 'float32')
commercial = to_array('commercial.tif', 'float32')
recreatif = to_array('recreatif.tif', 'float32')
medical = to_array('medical.tif', 'float32')
enseignement = to_array('enseignement.tif', 'float32')

# Création du raster final d'intérêt avec pondération
interet = np.where((restriction != 1), ((ecologie * dicCoef['ecologie']) + (ocsol * dicCoef['ocsol']) + (routes * dicCoef['routes']) + (transport * dicCoef['transport']) + (
    administratif * dicCoef['administratif']) + (commercial * dicCoef['commercial']) + (recreatif * dicCoef['recreatif']) + (medical * dicCoef['medical']) + (enseignement * dicCoef['enseignement'])), 0)
to_tif(interet, gdal.GDT_Float32, 'output/interet.tif')

# On vérifie que la capcité d'accueil est suffisante, ici on pourrait modifier la couche de restriction pour augmenter la capacité
capaciteAccueil = sum(sum(capacite))
print("Capacité d'accueil du territoire : " + str(capaciteAccueil))
if capaciteAccueil < sumPopALoger:
    print("La capacité d'accueil ne suffit pas pour de telles projections démographiques !")
    sys.exit()

# Itération au pas annuel sur toute la période :
for year in range(2015, finalYear + 1):
    popDic = {row[0]: row[year] for _, row in popDf.iterrows()}
