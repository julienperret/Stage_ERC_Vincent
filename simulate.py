#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import sys
import csv
import gdal
import traceback
import numpy as np
from tools import *
from shutil import rmtree
from ast import literal_eval
from time import strftime, time

# Ignorer les erreurs de numpy lors d'une division par 0
np.seterr(divide='ignore', invalid='ignore')

# Stockage et contrôle de la validité des paramètres utilisateur
dataDir = slashify(sys.argv[1])
outputDir = slashify(sys.argv[2])
gridSize = int(sys.argv[3])
rate = float(sys.argv[4])
if rate > 4:
    print("Taux d'évolution trop élevé, valeur max acceptée : 3 %")
    sys.exit()
if len(sys.argv) > 5:
    argList = sys.argv[5].split()
    for arg in argList:
        if 'mode' in arg:
            mode = arg.split('=')[1]
            if mode not in {'souple', 'strict'}:
                print("Mode de seuillage invalide \nValeurs possibles : souple ou strict")
                sys.exit()
        if 'saturateFirst' in arg:
            saturateFirst = literal_eval(arg.split('=')[1])
        if 'pluPriority' in arg:
            pluPriority = literal_eval(arg.split('=')[1])
        if 'finalYear' in arg:
            finalYear = int(arg.split('=')[1])
        if 'adjustCapa' in arg:
            adjustCapa = int(arg.split('=')[1])
        if 'silent' in arg:
            silent = True

# Valeurs de paramètres par défaut
if 'mode' not in globals():
    mode = 'souple'
if 'saturateFirst' not in globals():
    saturateFirst = True
if 'pluPriority' not in globals():
    pluPriority = True
if 'finalYear' not in globals():
    finalYear = 2040
if 'adjustCapa' not in globals():
    adjustCapa = 100
if 'silent' not in globals():
    silent = False

cellSurf = gridSize * gridSize
projectPath = outputDir + str(gridSize) + 'm_' + mode + '_tx' + str(rate)
if adjustCapa != 100:
    projectPath += '_adjust' + str(adjustCapa)
if saturateFirst:
    projectPath += '_satFirst'
if pluPriority:
    projectPath += '_pluPrio'
if finalYear != 2040:
    projectPath += '_' + str(finalYear)
projectPath += '/'

if os.path.exists(projectPath):
    rmtree(projectPath)
os.makedirs(projectPath + 'snapshots')

# Fonction de répartition de la population
def urbanize(mode, popALoger, saturateFirst=True, pluPriority=False):
    global population, capacite
    popLogee = 0
    capaciteTmp = capacite.copy()
    cols, rows = population.shape[1], population.shape[0]
    populationTmp = np.zeros([rows, cols], np.uint16)

    if mode == 'souple':
        if saturateFirst:
            capaciteTmp = np.where(population > 0, capaciteTmp, 0)
        if pluPriority:
            capaciteTmp = np.where(plu_priorite == 1, capaciteTmp, 0)
        while popLogee < popALoger and capaciteTmp.sum() > 0:
            weight = np.where(capaciteTmp > 0, interet, 0)
            flatWeight = weight.flatten()
            choices = np.random.choice(flatWeight.size, popALoger - popLogee, p=flatWeight / flatWeight.sum())
            i = 0
            while i < choices.size :
                row = choices[i] // weight.shape[1]
                col = choices[i] % weight.shape[1]
                if capaciteTmp[row][col] > 0:
                    populationTmp[row][col] += 1
                    popLogee += 1
                    capaciteTmp[row][col] -= 1
                i += 1
        # Si on a pas pu loger tout le monde dans des cellules déjà urbanisées => expansion
        if saturateFirst and popALoger - popLogee > 0:
            capaciteTmp = np.where(population == 0, capacite - populationTmp, 0)
            if pluPriority:
                capaciteTmp = np.where(plu_priorite == 1, capaciteTmp, 0)
            while popLogee < popALoger and capaciteTmp.sum() > 0:
                weight = np.where(capaciteTmp > 0, interet, 0)
                flatWeight = weight.flatten()
                choices = np.random.choice(flatWeight.size, popALoger - popLogee, p=flatWeight / flatWeight.sum())
                i = 0
                while i < choices.size :
                    row = choices[i] // weight.shape[1]
                    col = choices[i] % weight.shape[1]
                    if capaciteTmp[row][col] > 0:
                        populationTmp[row][col] += 1
                        popLogee += 1
                        capaciteTmp[row][col] -= 1
                    i += 1

    elif mode == 'strict':
        if pluPriority:
            capaciteTmp = np.where(plu_priorite == 1, capaciteTmp, 0)
        while popLogee < popALoger and capaciteTmp.sum() > 0:
            weight = np.where(capaciteTmp > 0, interet, 0)
            flatWeight = weight.flatten()
            choices = np.random.choice(flatWeight.size, popALoger - popLogee, p=flatWeight / flatWeight.sum())
            i = 0
            while i < choices.size:
                row = choices[i] // weight.shape[1]
                col = choices[i] % weight.shape[1]
                if capaciteTmp[row][col] > 0:
                    cellCapa = capaciteTmp[row][col]
                    if cellCapa <= popALoger - popLogee:
                        populationTmp[row][col] += cellCapa
                        popLogee += cellCapa
                        capaciteTmp[row][col] -= cellCapa
                    else:
                        cellCapa = cellCapa - (cellCapa - (popALoger - popLogee))
                        populationTmp[row][col] += cellCapa
                        popLogee += cellCapa
                        capaciteTmp[row][col] -= cellCapa
                i += 1

    capacite -= populationTmp
    population += populationTmp
    to_tif(population, 'uint16', proj, geot, projectPath + 'snapshots/pop_' + str(year) + '.tif')
    return popALoger - popLogee

# Création d'un fichier journal
log = open(projectPath + 'log.csv', 'x')
mesures = open(projectPath + 'mesures.csv', 'x')
start_time = time()

try:
    # Création des dataframes contenant les informations par IRIS
    with open(dataDir + 'population.csv') as csvFile:
        reader = csv.reader(csvFile)
        pop = {rows[0]:rows[1] for rows in reader}
    pop = int(pop['population'])

    dicPop = {}
    year = 2015
    while year <= finalYear:
        dicPop[year] = round(pop * (rate / 100))
        pop += round(pop * (rate / 100))
        year += 1

    # Nombre total de personnes à loger - permet de vérifier si le raster capacité permet d'accueillir tout le monde
    sumPopALoger = sum(dicPop.values())
    log.write("Population à loger d'ici à " + str(finalYear) + ", " + str(sumPopALoger) + "\n")

    # Calcul des coefficients de pondération de chaque raster d'intérêt, csv des poids dans le répertoire des données locales
    with open(dataDir + 'poids.csv') as csvFile:
        reader = csv.reader(csvFile)
        next(reader, None)
        poids = {rows[0]:int(rows[1]) for rows in reader}

    coefficients = open(projectPath + 'coefficients.csv', 'x')
    for key in poids:
        poids[key] = poids[key] / sum(poids.values())
        coefficients.write(key + ', ' + str(poids[key]))

    # Création des variables GDAL pour écriture de raster, indispensables pour la fonction to_tif()
    ds = gdal.Open(dataDir + 'population.tif')
    population = ds.GetRasterBand(1).ReadAsArray().astype(np.uint16)
    proj = ds.GetProjection()
    geot = ds.GetGeoTransform()
    ds = None

    urb14 = np.where(population > 0, 1, 65535)
    to_tif(urb14, 'uint16', proj, geot, projectPath + 'urbain_2014.tif' )
    del urb14

    # Préparation du raster de capacité, nettoyage des cellules interdites à la construction
    restriction = to_array(dataDir + 'restriction.tif')
    capacite = to_array(dataDir + 'capacite.tif', 'uint16')
    capacite = np.where(restriction != 1, capacite, 0)
    if os.path.exists(dataDir + 'plu_restriction.tif') and os.path.exists(dataDir + 'plu_priorite.tif'):
        hasPlu = True
        plu_priorite = to_array(dataDir + 'plu_priorite.tif')
        plu_restriction = to_array(dataDir + 'plu_restriction.tif')
        capacite = np.where(plu_restriction != 1, capacite, 0)
    else:
        hasPlu = False

    # Modification de la capacité selon une valeur utilisateur en %
    if adjustCapa > 0:
        capacite = (capacite * (adjustCapa/100)).astype(np.uint16)

    # On vérifie que la capcité d'accueil est suffisante, ici on pourrait modifier la couche de restriction pour augmenter la capacité
    f = 0
    capaciteAccueil = capacite.sum()
    log.write("Capacité d'accueil originale du territoire, " + str(capaciteAccueil) + '\n')
    if capaciteAccueil < sumPopALoger:
        f += 100
        if hasPlu:
            if not silent:
                print("La capacité d'accueil étant insuffisante, on retire les restrictions issues du PLU.")
            capacite = to_array(dataDir + 'capacite.tif', 'uint16')
            capacite = np.where(restriction != 1, capacite, 0)
            capaciteAccueil = capacite.sum()
            if capaciteAccueil < sumPopALoger:
                while capaciteAccueil < sumPopALoger:
                    f += 5
                    capacite = to_array(dataDir + 'capacite.tif', 'uint16')
                    capacite = np.where(restriction != 1, capacite, 0)
                    capacite = capacite * (f/100)
                    capaciteAccueil = capacite.sum()
                if not silent:
                    print("Afin de loger tout le monde, la capacite est augmentée de " + str(f) + ' %')
        # Ici on augmente les valeurs du raster de capacité avec un pas de 5 %
        else:
            while capaciteAccueil < sumPopALoger:
                f += 5
                if not silent:
                    print("Capacite  " + str(f) + ' %')
                capacite = to_array(dataDir + 'capacite.tif', 'uint16')
                capacite = np.where(restriction != 1, capacite, 0)
                capacite = capacite * (f/100)
                capaciteAccueil = capacite.sum()
            if not silent:
                print("Afin de loger tout le monde, la capacite est augmentée de " + str(f) + ' %')

    log.write("Nouvelle capacité d'accueil du territoire, " + str(capaciteAccueil) + "\n")
    log.write("Pourcentage d'augmentation de la capacite, " + str(f) + "\n")
    log.write("Objectif démographique pour 2040, " + str(int(population.sum()) + sumPopALoger ) + "\n")

    capaciteDepart = capacite.copy()
    populationDepart = population.copy()
    to_tif(capacite, 'uint16', proj, geot, projectPath + 'capacite_depart.tif')

    # Conversion des autres raster d'entrée en numpy array
    ecologie = to_array(dataDir + 'ecologie.tif', 'float32')
    ocsol = to_array(dataDir + 'ocsol.tif', 'float32')
    routes = to_array(dataDir + 'routes.tif', 'float32')
    transport = to_array(dataDir + 'transport.tif', 'float32')
    sirene = to_array(dataDir + 'sirene.tif', 'float32')

    # Création du raster final d'intérêt avec pondération
    interet = np.where((restriction != 1), (ecologie * poids['ecologie']) + (ocsol * poids['ocsol']) +
     (routes * poids['routes']) + (transport * poids['transport']) + (sirene * poids['sirene']), 0)
    to_tif(interet, 'float32', proj, geot, projectPath + 'interet.tif')
    del poids, restriction, ocsol, routes, transport, sirene

    for year in range(2015, finalYear + 1):
        progress = "Année %i/%i" %(year, finalYear)
        if not silent:
            printer(progress)
        popALoger = dicPop[year]
        if hasPlu:
            popRestante = urbanize(mode, popALoger, saturateFirst, pluPriority)
            if popRestante > 0:
                urbanize(mode, popRestante, saturateFirst)
        else:
            urbanize(mode, popALoger, saturateFirst)

    # Calcul et export des résultats
    urb40 = np.where(population > 0, 1, 65535)
    popNouvelle = population - populationDepart
    capaSaturee = np.where((capaciteDepart > 0) & (capacite == 0), 1, 0)
    expansion = np.where((populationDepart == 0) & (population > 0), 1, 0)
    peuplementMoyen = np.nanmean(np.where(popNouvelle == 0, np.nan, popNouvelle))
    impactEnvironnemental = int(np.where(expansion == 1, 1 - ecologie, 0).sum() * cellSurf)
    expansionSum = expansion.sum()

    to_tif(capacite, 'uint16', proj, geot, projectPath + 'capacite_future.tif')
    to_tif(population, 'uint16', proj, geot, projectPath + 'population_future.tif')
    to_tif(expansion, 'byte', proj, geot, projectPath + 'expansion.tif')
    to_tif(popNouvelle, 'uint16', proj, geot, projectPath + 'population_nouvelle.tif')
    to_tif(capaSaturee, 'byte', proj, geot, projectPath + 'capacite_saturee')
    to_tif(urb40, 'uint16', proj, geot, projectPath + 'urbain_2040.tif' )

    nbCapaCell = np.where(capaciteDepart != 0, 1, 0).sum()
    mesures.write("Peuplement moyen des cellules, " + str(peuplementMoyen) + "\n")
    mesures.write("Taux d'expansion, " + str(expansionSum / nbCapaCell) + "\n")
    mesures.write("Taux de saturation, " + str(capaSaturee.sum() / nbCapaCell) + "\n")
    mesures.write("Expansion totale en m2, " + str(expansionSum * cellSurf) + "\n")
    mesures.write("Impact environnemental cumulé, " + str(impactEnvironnemental) + "\n")
    log.write("Nombre de personnes final, " + str(population.sum()) + '\n')

    end_time = time()
    execTime = round(end_time - start_time, 2)
    log.write("Temps d'execution, " + str(execTime))
    if not silent:
        print("\nTemps d'execution : " + str(execTime) + ' secondes')

except:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    if not silent:
        print("\n*** Error :")
        traceback.print_exception(exc_type, exc_value, exc_traceback, limit=2, file=sys.stdout)
    else:
        log.write('\n*** Error :\n' + str(sys.exc_info()))
    log.close()
    sys.exit()

mesures.close()
log.close()
