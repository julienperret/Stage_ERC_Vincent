#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import sys
import csv
import gdal
import random
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
                print("Mode invalide; valeurs possibles : densification ou etalement")
                sys.exit()
        if 'pluPriority' in arg:
            pluPriority = literal_eval(arg.split('=')[1])
        if 'finalYear' in arg:
            finalYear = int(arg.split('=')[1])
        if 'buildNonRes' in arg:
            buildNonRes = literal_eval(arg.split('=')[1])
        if 'maxBuiltRatio' in arg:
            maxBuiltRatio = float(arg.split('=')[1])
        if 'maxContig' in arg:
            maxContig = int(arg.split('=')[1])
        if 'strict' in arg:
            strict = True

# Valeurs de paramètres par défaut
if 'mode' not in globals():
    mode = 'densification'
if 'finalYear' not in globals():
    finalYear = 2040
if 'pluPriority' not in globals():
    pluPriority = True
if 'buildNonRes' not in globals():
    buildNonRes = True
if 'maxBuiltRatio' not in globals():
    maxBuiltRatio = 90
if 'maxContig' not in globals():
    maxContig = 7
if 'strict' not in globals():
    strict = False

def slidingSum(array, row, col):
    s = 0
    pos = [-1, 0, 1]
    if row != 0 and col != 0 :
        for r in pos:
            for c in pos:
                s += array[row + r][col + c]
    return s

def build(row, col):
    global urb, srfSol, capaSol
    srf = 0
    if slidingSum(urba, row, col) <= maxContig:
        maxV = capaSol[row][col]
        srf += random.randint(0, maxV)
        srfSol[row][col] += srf
        capaSol[row][col] -= srf
    return s

def densify(row, col):
    global srfSol, srfPla, capaSol, capaPla
    srf = 0
    maxV = capaSol[row][col]
    if maxV > 0:
        s += random.randint(0, maxV)
        srfSol[row][col] += srf
        capaSol[row][col] -= srf
        return ('sol', srf)
    else:
        maxV = capaPla[row][col]
        srf += random.randint(0, maxV)
        srfPla += srf
        capaPla -= srf
        return ('pla', srf)

def populate(row, col):
    global tmpSrfPla
    p = round(tmpSrfPla[row][col] / m2PlaHab[row][col])
    return p

def choose(weight, size=1):
    cells = []
    flatWeight = weight.flatten()
    choices = np.random.choice(flatWeight.size, size, p=flatWeight / flatWeight.sum())
    i = 0
    while i < choices.size :
        row = choices[i] // weight.shape[1]
        col = choices[i] % weight.shape[1]
        cells.append((row, col))
        i += 1
    if size > 1:
        return cells
    else:
        return cells[0]

# Fonction de répartition de la population
def urbanize(pop, srf):
    popLog = 0
    tmpSrfPla = np.zeros([rows, cols], np.uint16)
    tmpSrfSol = np.zeros([rows, cols], np.uint16)
    tmpInteret = interet.copy()

    if mode == 'densification':
        tmpInteret = np.where(urb == 1, tmpInteret, 0)
        if pluPriority:
            tmpInteret = np.where(pluPrio == 1, tmpInteret, 0)
        if tmpInteret.sum() > 0:
            builtSrf = 0
            while builtSrf < srf and popLog < pop :
                row, col = choose(np.where(srfSol > 0, tmpInteret, 0))
                place, built = densify(row, col)
                if place == 'sol':
                    tmpSrfSol[row][col] += built
                    tmpSrfPla[row][col] += built
                    builtSrf += s
                elif place == 'pla':
                    tmpSrfPla[row][col] += built


    elif mode == 'etalement':
        pass

    return pop - popLog

try:
    # Création des variables GDAL pour écriture de raster, indispensables pour la fonction to_tif()
    ds = gdal.Open(dataDir + 'demographie_14.tif')
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
    if maxBuiltRatio != 90:
        projectPath + '_build' + str(maxBuiltRatio)
    if buildNonRes :
        projectPath += '_buildNonRes'
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

    # Création du raster final d'intérêt avec pondération
    eco = to_array(dataDir + 'non-importance_ecologique.tif', 'float32')
    ocs = to_array(dataDir + 'occupation_sol.tif', 'float32')
    rou = to_array(dataDir + 'proximite_routes.tif', 'float32')
    tra = to_array(dataDir + 'proximite_transport.tif', 'float32')
    sir = to_array(dataDir + 'densite_sirene.tif', 'float32')

    interet = np.where((restriction != 1), (eco * coef['ecologie']) + (ocs * coef['ocsol']) +
                       (rou * coef['routes']) + (tra * coef['transport']) + (sir * poids['sirene']), 0)
    interet = (interet / np.amax(interet)).astype(np.float32)
    to_tif(interet, 'float32', proj, geot, projectPath + 'interet.tif')

    # Traitement des raster et calcul des statistiques sur l'évolution des surfaces bâties
    srfSol09 = to_array(dataDir + 'srf_sol_09.tif', 'uint16')
    srfSol14 = to_array(dataDir + 'srf_sol_14.tif', 'uint16')
    urb09 = np.where(srfSol09 > 0, 1, 0).astype(np.byte)
    urb14 = np.where(srfSol14 > 0, 1, 0).astype(np.byte)
    m2SolHab09 = srfSol09.sum() / pop09
    m2SolHab14 = srfSol14.sum() / pop14
    m2SolHabEvo = (m2SolHab14 - m2SolHab09) / m2SolHab09 / 5

    srfPla14 = to_array(dataDir  + 'srf_pla.tif', 'uint16')
    srfSolRes = to_array(dataDir + 'srf_sol_res.tif', 'uint16')
    ratioPlaSol = np.where(srfSolRes != 0, srfPla14 / srfSolRes, 0).astype(np.float32)

    to_tif(urb14, 'byte', proj, geot, projectPath + 'construit_2014.tif')

    # Création du raster de capacité en surface constructible
    capaSol = np.zeros([rows, cols], np.int16)
    capaSol += int(cellSurf * (maxBuiltRatio / 100))
    capaSol -= srfSol14
    capaSol = np.where((capaSol > 0) & (restriction != 1), capaSol, 0).astype(np.uint16)

    # Variables utilisées par la fonction urbanize
    urb = urb14.copy()
    demo = demoDep.copy()
    srfPla = srfPla14.copy()
    srfSol = srfSol14.copy()

    for year in range(2015, finalYear + 1):
        progress = "Année %i/%i" %(year, finalYear)
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
    peuplementMoyen = np.nanmean(np.where(popNouv == 0, np.nan, popNouv))
    impactEnv = int(np.where(expansion == 1, 1 - eco, 0).sum() * cellSurf)
    expansionSum = expansion.sum()

    to_tif(demo, 'uint16', proj, geot, projectPath + 'demographie_' + str(finalYear) + '.tif')
    to_tif(expansion, 'byte', proj, geot, projectPath + 'expansion.tif')
    to_tif(popNouv, 'uint16', proj, geot, projectPath + 'population_nouvelle.tif')

    mesures.write("Peuplement moyen des cellules, " + str(peuplementMoyen) + "\n")
    mesures.write("Expansion totale en m2, " + str(expansionSum * cellSurf) + "\n")
    mesures.write("Impact environnemental cumulé, " + str(impactEnv) + "\n")
    log.write("Nombre de personnes final, " + str(pop.sum()) + '\n')

    end_time = time()
    execTime = round(end_time - start_time, 2)
    log.write("Temps d'execution, " + str(execTime))
    print("\nTemps d'execution : " + str(execTime) + ' secondes')

except:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    print("\n*** Error :")
    traceback.print_exception(exc_type, exc_value, exc_traceback, limit=2, file=sys.stdout)
    log.write('\n*** Error :\n' + str(sys.exc_info()))
    log.close()
    sys.exit()

mesures.close()
log.close()
