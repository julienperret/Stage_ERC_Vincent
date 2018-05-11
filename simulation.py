#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import ast
import sys
import gdal
import time
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
def peupler(irisId, pop):
    # Création d'arrays d'intérêt et de capacité masqués autour de l'IRIS
    capaIris = np.where((iris == irisId) & (population > 0), capacite, 0)
    weight = np.where(capaIris > 0, interet, 0)
    weightRowSum = np.sum(weight, 1)
    popIris = np.zeros([rows, cols], dtype=np.uint16)
    popLogee = 0
    # Boucle de réparition de la population, en priorité dans des cellules où population > 0
    if sum(sum(capaIris)) > 0:
        while popLogee < pop:
            # Tirage pondéré selon l'intérêt à urbaniser
            row = np.where(weightRowSum == np.random.choice(
                weightRowSum, p=weightRowSum / sum(weightRowSum)))[0][0]
            col = np.where(weight[row] == np.random.choice(
                weight[row], p=weight[row] / sum(weight[row])))[0][0]
            if row != 0 and col != 0:
                # Peuplement de la cellule tirée + mise à jour des arrays population et capacité
                popLogee += 1
                population[row][col] += 1
                capacite[row][col] -= 1
                capaIris[row][col] -= 1
                # Mise à jour de l'intérêt à zéro quand la capcité d'accueil est dépasée
                if capaIris[row][col] == 0 :
                    weight[row][col] = 0
                    weightRowSum = np.sum(weight, 1)
            if sum(sum(capaIris)) == 0:
                break
    # Si on a pas pu loger tout le monde dans des cellules déjà urbanisées => expansion
    if pop - popLogee > 0:
        capaIris = np.where((iris == irisId) & (population == 0), capacite, 0)
        weight = np.where(capaIris > 0, interet, 0)
        weightRowSum = np.sum(weight, 1)
        if sum(sum(capaIris)) > 0 :
            while popLogee < pop:
                row = np.where(weightRowSum == np.random.choice(
                    weightRowSum, p=weightRowSum / sum(weightRowSum)))[0][0]
                col = np.where(weight[row] == np.random.choice(
                    weight[row], p=weight[row] / sum(weight[row])))[0][0]
                if row != 0 and col != 0:
                    popLogee += 1
                    population[row][col] += 1
                    capacite[row][col] -= 1
                    capaIris[row][col] -= 1
                    if capaIris[row][col] == 0 :
                        weight[row][col] = 0
                        weightRowSum = np.sum(weight, 1)
                # Condition de sortie en cas de saturation du quartier
                if sum(sum(capaIris)) == 0:
                    break
    return pop - popLogee

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

print('Commencé à ' + time.strftime('%H:%M:%S'))

# Création des dataframes contenant les informations par IRIS
irisDf = pd.read_csv('iris.csv')
nbIris = len(irisDf)
dicContig = {row[0]: row[4] for _, row in irisDf.iterrows()}

# Projections démograhpiques
irisDf['population'] = irisDf['population'].astype(int)
popDf = pd.DataFrame()
popDf['id'] = [i + 1 for i in range(nbIris)]
for year in range(2014, 2041):
    popDf[year] = 0
for irisId in range(nbIris):
    year = 2014
    pop = irisDf['population'][irisId]
    popDf[year][irisId] = pop
    year += 1
    while year <= finalYear:
        popDf[year][irisId] = pop * (taux / 100)
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

# On vérifie que la capcité d'accueil est suffisante, ici on pourrait modifier la couche de restriction pour augmenter la capacité
capaciteAccueil = sum(sum(capacite))
print("Capacité d'accueil du territoire : " + str(capaciteAccueil))
if capaciteAccueil < sumPopALoger:
    print("La capacité d'accueil ne suffit pas pour de telles projections démographiques !")
    sys.exit()

# Création du raster final d'intérêt avec pondération
interet = np.where((restriction != 1), ((ecologie * dicCoef['ecologie']) + (ocsol * dicCoef['ocsol']) + (routes * dicCoef['routes']) + (transport * dicCoef['transport']) + (
    administratif * dicCoef['administratif']) + (commercial * dicCoef['commercial']) + (recreatif * dicCoef['recreatif']) + (medical * dicCoef['medical']) + (enseignement * dicCoef['enseignement'])), 0)
to_tif(interet, gdal.GDT_Float32, 'output/interet.tif')
del restriction, ecologie, ocsol, routes, transport, administratif, commercial, recreatif, medical, enseignement

# Itération au pas de temps annuel sur toute la période
for year in range(2015, finalYear + 1):
    print(str(year) + '/' + str(finalYear))
    dicPop = {row[0]: row[year] for _, row in popDf.iterrows()}
    for irisId in dicPop.keys() :
        contigList = ast.literal_eval(dicContig[irisId])
        popALoger = dicPop[irisId]
        popRestante = peupler(irisId, popALoger)
        # Si population restante, tirage aléatoire trouver un quartier contigu
        if popRestante > 0 :
            testedId = []
            while len(testedId) < len(contigList):
                contigId = int(np.random.choice(contigList, 1)[0])
                popRestante = peupler(contigId, popRestante)
                if contigId not in testedId :
                    testedId.append(contigId)
                print(str(len(testedId)) + '/' + str(len(contigList)))
            while popRestante > 0 :
                anyId = np.random.choice([i+1 for i in range(nbIris)], 1)[0]
                popRestante = peupler(anyId, popRestante)

capaciteDepart = to_array('capacite.tif')
populationDepart = to_array('population.tif')
popNouvelle = population - populationDepart

to_tif(capacite, gdal.GDT_UInt16, 'output/capacite_future.tif')
to_tif(population, gdal.GDT_UInt16, 'output/population_future.tif')
to_tif(popNouvelle, gdal.GDT_UInt16, 'output/population_nouvelle.tif')
expansion = np.where((populationDepart == 0) & (population > 0), 1, 0)
to_tif(expansion, gdal.GDT_Byte, 'output/expansion.tif')
capaSaturee = np.where((capaciteDepart > 0) & (capacite == 0), 1, 0)
to_tif(capaSaturee, gdal.GDT_Byte, 'output/capacite_saturee')

print('Terminé  à ' + time.strftime('%H:%M:%S'))
