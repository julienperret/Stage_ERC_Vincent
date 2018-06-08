#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import sys
import csv
import gdal
import traceback
import numpy as np
from toolbox import *
from shutil import rmtree
from ast import literal_eval
from time import strftime, time

# Ignorer les erreurs de numpy lors d'une division par 0
np.seterr(divide='ignore', invalid='ignore')

# Stockage et contrôle de la validité des paramètres utilisateur
dataDir = slashify(sys.argv[1])
outputDir = slashify(sys.argv[2])
rate = float(sys.argv[3])
if rate > 3:
    print("Taux d'évolution trop élevé, valeur max acceptée : 3 %")
    sys.exit()
if len(sys.argv) > 4:
    argList = sys.argv[4].split()
    for arg in argList:
        if 'mode' in arg:
            mode = arg.split('=')[1]
            if mode not in {'densification', 'etalement'}:
                print("Mode de seuillage invalide \nValeurs possibles : densification ou etalement")
                sys.exit()
        if 'pluPriority' in arg:
            pluPriority = literal_eval(arg.split('=')[1])
        if 'finalYear' in arg:
            finalYear = int(arg.split('=')[1])
        if 'maxBuiltRatio' in arg:
            maxBuiltRatio = float(arg.split('=')[1]) / 100
        if 'silent' in arg:
            silent = True

# Valeurs de paramètres par défaut
if 'mode' not in globals():
    mode = 'densification'
if 'pluPriority' not in globals():
    pluPriority = True
if 'finalYear' not in globals():
    finalYear = 2040
if 'maxBuiltRatio' not in globals():
    maxBuiltRatio = 0.9
if 'silent' not in globals():
    silent = False

def choose(weight, size):
    cells = []
    flatWeight = weight.flatten()
    choices = np.random.choice(flatWeight.size, size, p=flatWeight / flatWeight.sum())
    i = 0
    while i < choices.size :
        row = choices[i] // weight.shape[1]
        col = choices[i] % weight.shape[1]
        cells.append((row, col))
        i += 1
    return cells

# Fonction de répartition de la population
def urbanize(popALoger, pluPriority=False):
    global mode, interet, demo, spla, ssol
    popLog = 0
    splaTmp = np.zeros([rows, cols], np.uint16)
    ssolTmp = np.zeros([rows, cols], np.uint16)

    if mode == 'densification':
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
    elif mode == 'etalement'
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

try:
    # Création des variables GDAL pour écriture de raster, indispensables pour la fonction to_tif()
    ds = gdal.Open(dataDir + 'demographie_2014.tif')
    demoDep = ds.GetRasterBand(1).ReadAsArray().astype(np.uint16)
    cols, rows = demoDep.shape[1], demoDep.shape[0] # x, y
    proj = ds.GetProjection()
    geot = ds.GetGeoTransform()
    pixSize = int(geot[1])
    cellSurf = pixSize * pixSize
    ds = None

    projectPath = outputDir + str(pixSize) + 'm_' + mode + '_tx' + str(rate)
    if pluPriority:
        projectPath += '_pluPrio'
    if finalYear != 2040:
        projectPath += '_' + str(finalYear)
    projectPath += '/'

    if os.path.exists(projectPath):
        rmtree(projectPath)
    os.makedirs(projectPath + 'snapshots')

    # Création d'un fichier journal
    log = open(projectPath + 'log.csv', 'x')
    mesures = open(projectPath + 'mesures.csv', 'x')
    start_time = time()

    # Création des dataframes contenant les informations par IRIS
    with open(dataDir + 'population.csv') as csvFile:
        reader = csv.reader(csvFile)
        next(reader, None)
        histPop = {rows[0]:rows[1] for rows in reader}

    pop09 = int(histPop['2009'])
    pop14 = int(histPop['2014'])
    evoPop = (pop14 - pop09) / pop09 / 5

    dicPop = {}
    year = 2015
    pop = pop14
    while year <= finalYear:
        dicPop[year] = round(pop * (rate / 100))
        pop += round(pop * (rate / 100))
        year += 1

    # Nombre total de personnes à loger - permet de vérifier si le raster capacité permet d'accueillir tout le monde
    sumPopALoger = sum(dicPop.values())
    log.write("Population à loger d'ici à " + str(finalYear) + ", " + str(sumPopALoger) + "\n")

    # Traitement des raster et calcul des statistiques sur l'évolution des surfaces bâties
    ssol09 = to_array(dataDir + 'surface_sol_2009.tif', 'uint16')
    urba09 = np.where(ssol09 > 0, 1, 0).astype(np.byte)
    ssol14 = to_array(dataDir + 'surface_sol_2014.tif', 'uint16')
    urba14 = np.where(ssol14 > 0, 1, 0).astype(np.byte)
    m2SolHab09 = ssol09.sum() / pop09
    m2SolHab14 = ssol14.sum() / pop14
    m2SolEvo = (m2SolHab14 - m2SolHab09) / m2SolHab09

    spla14 = to_array(dataDir  + 'surface_plancher.tif', 'uint16')
    ssolRes = to_array(dataDir + 'surface_sol_residentiel.tif', 'uint16')
    ratioPlaSol = np.where(ssolRes != 0, spla14 / ssolRes14, 0).astype(np.float32)
    nbNibMoy = np.nanmean(np.where(ratioPlaSol == 0, np.nan, ratioPlaSol))

    to_tif(urba14, 'byte', proj, geot, projectPath + 'construit_2014.tif')

    # Variables utilisées par la fonction urbanize
    demo = demoDep.copy()
    spla = spla14.copy()
    ssol = ssol14.copy()

    # Calcul des coefficients de pondération de chaque raster d'intérêt, csv des poids dans le répertoire des données locales
    with open(dataDir + 'poids.csv') as r:
        reader = csv.reader(r)
        next(reader, None)
        poids = {rows[0]:int(rows[1]) for rows in reader}

    coef = {}
    with open(projectPath + 'coefficients.csv', 'x') as w:
        for key in poids:
            coef[key] = poids[key] / sum(poids.values())
            w.write(key + ', ' + str(coef[key]))

    # Préparation des restrictions
    restriction = to_array(dataDir + 'restriction_totale.tif')
    if os.path.exists(dataDir + 'plu_restriction.tif') and os.path.exists(dataDir + 'plu_priorite.tif'):
        hasPlu = True
        pluPrio = to_array(dataDir + 'plu_priorite.tif')
        pluRest = to_array(dataDir + 'plu_restriction.tif')
    else:
        hasPlu = False

    # Conversion des autres raster d'entrée en numpy array
    eco = to_array(dataDir + 'non-importance_ecologique.tif', 'float32')
    ocs = to_array(dataDir + 'occupation_sol.tif', 'float32')
    rou = to_array(dataDir + 'proximite_routes.tif', 'float32')
    tra = to_array(dataDir + 'proximite_transport.tif', 'float32')
    sir = to_array(dataDir + 'densite_sirene.tif', 'float32')

    # Création du raster final d'intérêt avec pondération
    interet = np.where((restriction != 1), (eco * coef['ecologie']) + (ocs * coef['ocsol']) +
                       (rou * coef['routes']) + (tra * coef['transport']) + (sir * poids['sirene']), 0)
    interet = (interet / np.amax(interet)).astype(np.float32)
    to_tif(interet, 'float32', proj, geot, projectPath + 'interet.tif')

    for year in range(2015, finalYear + 1):
        progress = "Année %i/%i" %(year, finalYear)
        if not silent:
            printer(progress)
        popALoger = dicPop[year]
        if hasPlu:
            popRestante = urbanize(popALoger, pluPriority)
            if popRestante > 0:
                urbanize(popRestante)
        else:
            urbanize(popALoger)

    # Calcul et export des résultats
    popNouv = demo - demoDep
    expansion = np.where((demoDep == 0) & (demo > 0), 1, 0)
    peuplementMoyen = np.nanmean(np.where(demoNouv == 0, np.nan, demoNouv))
    impact = int(np.where(expansion == 1, 1 - eco, 0).sum() * cellSurf)
    expansionSum = expansion.sum()

    to_tif(demo, 'uint16', proj, geot, projectPath + 'demographie_' + str(finalYear) + '.tif')
    to_tif(expansion, 'byte', proj, geot, projectPath + 'expansion.tif')
    to_tif(popNouv, 'uint16', proj, geot, projectPath + 'population_nouvelle.tif')

    mesures.write("Peuplement moyen des cellules, " + str(peuplementMoyen) + "\n")
    mesures.write("Expansion totale en m2, " + str(expansionSum * cellSurf) + "\n")
    mesures.write("Impact environnemental cumulé, " + str(impactEnvironnemental) + "\n")
    log.write("Nombre de personnes final, " + str(pop.sum()) + '\n')

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
