#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import gdal
import numpy as np
import pandas as pd
from time import strftime
from shutil import rmtree
from ast import literal_eval

# Stockage et contrôle de la validité des paramètres utilisateur
workspace = sys.argv[1]
os.chdir(workspace)
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

projectPath = mode + '_' + str(taux) + 'pct/'
if os.path.exists(projectPath):
    rmtree(projectPath)
os.mkdir(projectPath)

log = open(projectPath + 'log.txt', 'x')

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

# Fonction de tirage pondéré avec gestion des résultats multiples
def weightedChoice(weight):
    weightRowSum = np.sum(weight, 1)
    row = np.where(weightRowSum == np.random.choice(
        weightRowSum, p=weightRowSum / sum(weightRowSum)))[0]
    if row.size > 1 :
        row = row[np.random.choice([i for i in range(row.size)], 1)[0]]
    else :
        row = row[0]
    col = np.where(weight[row] == np.random.choice(
        weight[row], p=weight[row] / sum(weight[row])))[0]
    if col.size > 1 :
        col = col[np.random.choice([i for i in range(col.size)], 1)[0]]
    else :
        col = col[0]
    return row, col

# Fonction de peuplement d'une cellule avec mise à jour des variables globales
def populate(row, col, nb):
    global capacite, population, capaIris, popLogee, weight
    if capaIris[row][col] > 0 and (row != 0 and col != 0):
        population[row][col] += nb
        capacite[row][col] -= nb
        capaIris[row][col] -= nb
        if capaIris[row][col] == 0:
            weight[row][col] = 0
        popLogee += nb

# Fonction de répartition de la population
def urbanize(mode, irisId, popALoger, saturateFirst=True, pluPriority=False):
    global capaIris, popLogee, weight
    popLogee = 0
    capaIris = np.where(iris == irisId, capacite, 0)
    if pluPriority:
        capaIris = np.where(plu_priorite == 1, capaIris, 0)
    if mode == 'souple':
        if saturateFirst:
            capaIris = np.where(population > 0, capaIris, 0)
        weight = np.where(capaIris > 0, interet, 0)
        if np.sum(weight) > 0:
            while popLogee < popALoger:
                row, col = weightedChoice(weight)
                populate(row, col, 1)
                if np.sum(weight) == 0:
                    break

        # Si on a pas pu loger tout le monde dans des cellules déjà urbanisées => expansion
        if saturateFirst and popALoger - popLogee > 0:
            capaIris = np.where( (iris == irisId) & (population == 0), capacite, 0)
            if pluPriority:
                capaIris = np.where(plu_priorite == 1, capaIris, 0)
            weight = np.where(capaIris > 0, interet, 0)
            if np.sum(weight) > 0:
                while popLogee < popALoger:
                    row, col = weightedChoice(weight)
                    populate(row, col, 1)
                    # Condition de sortie en cas de saturation du quartier
                    if np.sum(weight) == 0:
                        break

    elif mode == 'strict' :
        capaIris = np.where(population == 0, capaIris, 0)
        weight = np.where(capaIris > 0, interet, 0)
        if np.sum(weight) > 0:
            while popLogee < popALoger:
                row, col = weightedChoice(weight)
                if capaIris[row][col] > 0 and (row != 0 and col != 0):
                    cellCapa = capaIris[row][col]
                    if cellCapa <= popALoger - popLogee :
                        populate(row, col, cellCapa)
                    else :
                        cellCapa = cellCapa - (cellCapa - (popALoger - popLogee))
                        populate(row, col, cellCapa)
                # Condition de sortie en cas de saturation du quartier
                if np.sum(weight) == 0:
                    break

    return popALoger - popLogee

log.write('Commencé à ' + strftime('%H:%M:%S') + '\n')

# Création des dataframes contenant les informations par IRIS
irisDf = pd.read_csv('iris.csv')
nbIris = len(irisDf)
dicContig = {row[0]: row[4] for _, row in irisDf.iterrows()}

# Projections démograhpiques
irisDf['population'] = irisDf['population'].astype(int)
popDf = pd.DataFrame()
popDf['id'] = [i + 1 for i in range(nbIris)]
for year in range(2014, finalYear + 1):
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
popDf.to_csv(projectPath + 'demographie.csv', index=0)

# Nombre total de personnes à loger - permet de vérifier si le raster capacité pourra tout contenir
sumPopALoger = sum(popDf.sum()) - sum(range(nbIris + 1)) - sum(popDf[2014])
log.write('Population à loger d\'ici à ' +
          str(finalYear) + ' : ' + str(sumPopALoger) + '\n')

# Calcul des coefficients de pondération de chaque raster d'intérêt, csv des poids dans le répertoire des données locales
if not os.path.exists('poids.csv') :
    poids = pd.read_csv('../../poids.csv')
poids['coef'] = poids['poids'] / sum(poids['poids'])
poids.to_csv(projectPath + 'coefficients.csv',
             index=0, columns=['raster', 'coef'])
dicCoef = {row[0]: row[2] for _, row in poids.iterrows()}
del poids

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

# Préparation du raster de capacité, nettoyage des cellules interdites à la construction
capacite = np.where(restriction != 1, capacite, 0)
if os.path.exists('plu_restriction.tif') and os.path.exists('plu_priorite.tif') :
    hasPlu = True
    plu_priorite = to_array('plu_priorite.tif')
    plu_restriction = to_array('plu_restriction.tif')
    capacite = np.where(plu_restriction != 1, capacite, 0)
else :
    hasPlu = False

# On vérifie que la capcité d'accueil est suffisante, ici on pourrait modifier la couche de restriction pour augmenter la capacité
capaciteAccueil = np.sum(capacite)
log.write("Capacité d'accueil du territoire : " + str(capaciteAccueil) + '\n')
if capaciteAccueil < sumPopALoger:
    if hasPlu:
        print("La capacité d'accueil étant insuffisante, on retire les restrictions issues du PLU.")
        capacite = to_array('capacite.tif', 'uint16')
        capacite = np.where(restriction != 1, capacite, 0)
        capaciteAccueil = np.sum(capacite)
        log.write("Capacité d'accueil du territoire sans la restriction PLU : " + str(capaciteAccueil) + '\n')
        if capaciteAccueil < sumPopALoger:
            print("La capacité d'accueil ne suffit pas pour de telles projections démographiques.")
            rmtree(projectPath)
            sys.exit()
    else:
        # Ici on peut éventuellement augmenter les valeurs du raster de capacité
        print("La capacité d'accueil ne suffit pas pour de telles projections démographiques.")
        rmtree(projectPath)
        sys.exit()

capaciteDepart = capacite.copy()
populationDepart = population.copy()

# Création du raster final d'intérêt avec pondération
interet = np.where((restriction != 1), ((ecologie * dicCoef['ecologie']) + (ocsol * dicCoef['ocsol']) + (routes * dicCoef['routes']) + (transport * dicCoef['transport']) + (
    administratif * dicCoef['administratif']) + (commercial * dicCoef['commercial']) + (recreatif * dicCoef['recreatif']) + (medical * dicCoef['medical']) + (enseignement * dicCoef['enseignement'])), 0)

to_tif(interet, gdal.GDT_Float32, projectPath + 'interet.tif')
del dicCoef, restriction, ecologie, ocsol, routes, transport, administratif, commercial, recreatif, medical, enseignement

filledList = []
for year in range(2015, finalYear + 1):
    print(str(year))
    dicPop = {row[0]: row[year] for _, row in popDf.iterrows()}
    for irisId in dicPop.keys():
        popALoger = dicPop[irisId]
        if irisId not in filledList:
            if hasPlu:
                popRestante = urbanize(mode, irisId, popALoger, pluPriority=True)
                if popRestante > 0:
                    popRestante = urbanize(mode, irisId, popRestante)
            else:
                popRestante = urbanize(mode, irisId, popALoger)
        else:
            popRestante = popALoger
        # Si population restante, tirage pour peupler un quartier contigu
        if popRestante > 0:
            if irisId not in filledList:
                filledList.append(irisId)
            contigList = literal_eval(dicContig[irisId])
            testedList = []
            while len(testedList) < len(contigList):
                contigId = int(np.random.choice(contigList, 1)[0])
                if contigId not in testedList:
                    testedList.append(contigId)
                    if contigId not in filledList:
                        if hasPlu:
                            popRestante = urbanize(mode, contigId, popRestante, pluPriority=True)
                            if popRestante > 0:
                                popRestante = urbanize(mode, contigId, popRestante)
                        else:
                            popRestante = urbanize(mode, contigId, popRestante)
            # Si capacité des IRIS voisins insuffisante, tirage pour peupler n'importe quel quartier
            testedList = []
            while popRestante > 0:
                anyId = np.random.choice([i + 1 for i in range(nbIris)], 1)[0]
                if anyId not in testedList:
                    testedList.append(anyId)
                    if anyId not in filledList:
                        if hasPlu:
                            popRestante = urbanize(mode, anyId, popRestante, pluPriority=True)
                            if popRestante > 0:
                                popRestante = urbanize(mode, anyId, popRestante)
                        else:
                            popRestante = urbanize(mode, anyId, popRestante)

log.write(str(len(filledList)) + ' IRIS saturés : \n' + str(filledList) + '\n')

popNouvelle = population - populationDepart
expansion = np.where((populationDepart == 0) & (population > 0), 1, 0)
capaSaturee = np.where((capaciteDepart > 0) & (capacite == 0), 1, 0)

to_tif(capacite, gdal.GDT_UInt16, projectPath + 'capacite_future.tif')
to_tif(population, gdal.GDT_UInt16, projectPath + 'population_future.tif')
to_tif(expansion, gdal.GDT_Byte, projectPath + 'expansion.tif')
to_tif(popNouvelle, gdal.GDT_UInt16, projectPath + 'population_nouvelle.tif')
to_tif(capaSaturee, gdal.GDT_Byte, projectPath + 'capacite_saturee')

log.write('Terminé  à ' + strftime('%H:%M:%S') + '\n')
