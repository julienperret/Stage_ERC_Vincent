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
        if 'seuilPla' in arg:
            seuilPla = arg.split('=')
        if 'maximumDensity' in arg:
            maximumDensity = literal_eval(arg.split('=')[1])
        if 'pluPriority' in arg:
            pluPriority = literal_eval(arg.split('=')[1])
        if 'finalYear' in arg:
            finalYear = int(arg.split('=')[1])
        if 'buildNonRes' in arg:
            buildNonRes = literal_eval(arg.split('=')[1])
        if 'maxBuiltRatio' in arg:
            maxBuiltRatio = float(arg.split('=')[1])
        if 'winSize' in arg:
            winSize = int(arg.split('=')[1])
        if 'maxContig' in arg:
            maxContig = int(arg.split('=')[1])

# *** Valeurs de paramètres par défaut
if 'finalYear' not in globals():
    finalYear = 2040
# Seuil utilisé pour limiter la surface plancher construite, par IRIS. 'q3' ou 'max'
if 'seuilPla' not in globals():
    seuilPla = 'q3'
# Pour artificialiser ou densifier la cellule au maximum de sa capacité
if 'maximumDensity' not in globals():
    maximumDensity = False
# Priorité aux ZAU
if 'pluPriority' not in globals():
    pluPriority = True
# Pour simuler également la construction des surfaces non résidentielles
if 'buildNonRes' not in globals():
    buildNonRes = True
# Taux d'artificialisation maximum des cellules
if 'maxBuiltRatio' not in globals():
    maxBuiltRatio = 90
# Paramètres pour les règles de contiguïtés; maxContig <= winSize²
if 'winSize' not in globals():
    winSize = 3
if 'maxContig' not in globals():
    maxContig = 7

# Tirage pondéré qui retourne un index par défaut ou une liste de tuples (row, col)
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
    if size == 1:
        return cells[0]
    elif size > 1:
        return cells
    else:
        return None

# Fenêtre glissante pour statistique dans le voisinage d'un pixel
def slidingWin(array, row, col, size=3, calc='sum'):
    if row > size - 1 and col > size - 1 :
        s = 0
        pos = [i + 1 for i in range(- size//2, size//2)]
        for r in pos:
            for c in pos:
                s += array[row + r][col + c]
        if calc == 'sum':
            return s
        elif calc == 'mean':
            return s / (size * size)
    else:
        return False

# Artificialisation d'une surface tirée comprise entre la taille moyenne d'un bâtiment (IRIS) et la capacité max de la cellule
def expand(row, col):
    global capaSol, capaPla, urb
    maxV = capaSol[row][col]
    srf = 0
    if slidingWin(urb, row, col, winSize, 'sum') <= maxContig:
        unitV = ssrMed[row][col]
        if maximumDensity or unitV > maxV:
            unitV = maxV
        srf = np.random.randint(0, unitV + 1)
        if srf > 0:
            urb[row][col] = 1
            capaSol[row][col] -= srf
            if buildNonRes:
                capaPla[row][col] -= srf * txSsr[row][col]
            else:
                capaPla[row][col] -= srf
    return srf

# Densification d'une surface tirée comprise entre la taille moyenne d'un bâtiment (IRIS) et la capacité max de la cellule
def densify(mode, row, col):
    srf = 0
    global capaSol, capaPla
    if mode == 'sol':
        maxV = capaSol[row][col]
        unitV = ssrMed[row][col]
        if maximumDensity or unitV > maxV:
            unitV = maxV
        srf = np.random.randint(0, unitV + 1)
        capaSol[row][col] -= srf
    elif mode == 'pla':
        maxV = capaPla[row][col]
        unitV = ssrMed[row][col]
        if maximumDensity or unitV > maxV:
            unitV = maxV
        srf = np.random.randint(0, unitV + 1)
    capaPla[row][col] -= srf
    return srf

# Fonction principale pour gérer etalement puis densification,
def urbanize(maxSrf, pop, zau=False):
    global demographie, capaSol, srfSol, capaPla, srfPla, srfSolRes
    tmpDemog = np.zeros([rows, cols], np.uint16)
    tmpSrfPla = np.zeros([rows, cols], np.uint16)
    tmpSrfSol = np.zeros([rows, cols], np.uint16)
    tmpInteret = np.where(srfSolRes == 0, interet, 0)
    if zau:
        tmpInteret = np.where(pluPrio == 1, tmpInteret, 0)
    count = 0
    built = 0
    while built < maxSrf and count < pop and tmpInteret.sum() > 0:
        srf = 0
        row, col = choose(tmpInteret)
        if urb[row][col] == 0:
            srf = expand(row, col)
        elif urb[row][col] == 1 and capaSol[row][col] > 0:
            srf = densify('sol', row, col)
        if srf > 0:
            built += srf
            tmpSrfSol[row][col] += srf
            if buildNonRes:
                srf = srf * txSsr[row][col]
            tmpSrfPla[row][col] += srf
            count = np.where(m2PlaHab != 0, tmpSrfPla / m2PlaHab, 0).sum().astype(np.uint16)

    if built >= maxSrf:
        tmpInteret = np.where(urb == 1, interet, 0)
        if zau:
            tmpInteret = np.where(pluPrio == 1, tmpInteret, 0)
        while count < pop and tmpInteret.sum() > 0 :
            row, col = choose(tmpInteret)
            if capaPla[row][col] > 0:
                srf = densify('pla', row, col)
                tmpSrfPla[row][col] += srf
                count = np.where(m2PlaHab != 0, tmpSrfPla / m2PlaHab, 0).sum().astype(np.uint16)

    srfSol += tmpSrfSol
    srfSolRes += tmpSrfSol
    srfPla += tmpSrfPla
    demographie += np.where(m2PlaHab != 0, tmpSrfPla / m2PlaHab, 0).astype(np.uint16)
    return (maxSrf - built, pop - count)

try:
    # Création des variables GDAL pour écriture de raster, indispensables pour la fonction to_tif()
    ds = gdal.Open(dataDir + 'demographie_14.tif')
    demographieDep = ds.GetRasterBand(1).ReadAsArray().astype(np.uint16)
    cols, rows = demographieDep.shape[1], demographieDep.shape[0] # x, y
    proj = ds.GetProjection()
    geot = ds.GetGeoTransform()
    pixSize = int(geot[1])
    cellSurf = pixSize * pixSize
    ds = None

    projectPath = outputDir + str(pixSize) + 'm' + '_tx' + str(rate)
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
    os.mkdir(projectPath + 'snapshots/demographie')
    os.mkdir(projectPath + 'snapshots/urbanisation')
    os.mkdir(projectPath + 'snapshots/surface_sol')
    os.mkdir(projectPath + 'snapshots/surface_plancher')

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
    eco = to_array(dataDir + 'non-importance_ecologique.tif', np.float32)
    ocs = to_array(dataDir + 'occupation_sol.tif', np.float32)
    rou = to_array(dataDir + 'proximite_routes.tif', np.float32)
    tra = to_array(dataDir + 'proximite_transport.tif', np.float32)
    sir = to_array(dataDir + 'densite_sirene.tif', np.float32)

    interet = np.where((restriction != 1), (eco * coef['ecologie']) + (ocs * coef['ocsol']) +
                       (rou * coef['routes']) + (tra * coef['transport']) + (sir * poids['sirene']), 0)
    interet = (interet / np.amax(interet)).astype(np.float32)
    to_tif(interet, 'float32', proj, geot, projectPath + 'interet.tif')

    # Traitement des raster et calcul des statistiques sur l'évolution des surfaces bâties
    srfSol09 = to_array(dataDir + 'srf_sol_09.tif', np.uint16)
    srfSol14 = to_array(dataDir + 'srf_sol_14.tif', np.uint16)
    urb09 = np.where(srfSol09 > 0, 1, 0).astype(np.byte)
    urb14 = np.where(srfSol14 > 0, 1, 0).astype(np.byte)
    m2SolHab09 = srfSol09.sum() / pop09
    m2SolHab14 = srfSol14.sum() / pop14
    m2SolHabEvo = (m2SolHab14 - m2SolHab09) / m2SolHab09 / 5

    # Création du dictionnaire pour nombre de m² ouverts à l'urbanisation par année
    dicSrf = {}
    maxSrf = m2SolHab14
    year = 2015
    while year <= finalYear:
        maxSrf += maxSrf * m2SolHabEvo
        dicSrf[year] = int(round(maxSrf * dicPop[year]))
        year += 1

    # Statistiques sur le nombre moyen d'étage dans la cellule, et sur les taux de surface plancher residentiel if buildNonRes
    m2PlaHab = to_array(dataDir + 'iris_m2_hab.tif', np.uint16)
    srfPla14 = to_array(dataDir  + 'srf_pla.tif', np.uint32)
    srfSolRes = to_array(dataDir + 'srf_sol_res.tif', np.uint32)
    srfSolNonRes = srfSol14 - srfSolRes
    ratioPlaSol = np.where(srfSolRes != 0, srfPla14 / srfSolRes, 0).astype(np.float32)
    ssrMed = to_array(dataDir + 'iris_ssr_med.tif', np.uint16)
    if buildNonRes:
        txSsr = to_array(dataDir + 'iris_tx_ssr.tif', np.float32)

    to_tif(urb14, 'byte', proj, geot, projectPath + 'urbanisation_2014.tif')

    # Création du raster de capacité en surface constructible à partir du ratio utilisateur et des surfaces actuelles
    # ===> ici, prendre en compte le reste de l'artificialisation (routes ?)
    capaSol = ( np.zeros([rows, cols], np.int32) + int(cellSurf * (maxBuiltRatio / 100)) ) - srfSol14
    capaSol = np.where((capaSol > 0) & (restriction != 1), capaSol, 0).astype(np.uint32)
    # Raster pour seuillage de le surface plancher : max ou q3 de la srfPla dans l'IRIS ?
    maxPla = to_array(dataDir + 'iris_srf_pla_' + seuilPla + '.tif', np.uint32)
    capaPla = np.where(restriction != 1, maxPla - srfPla14, 0).astype(np.uint32)

    # Variables utilisées par la fonction urbanize
    urb = urb14.copy()
    demographie = demographieDep.copy()
    srfPla = srfPla14.copy()
    srfSol = srfSol14.copy()


    preConstruit = 0
    preLogee = 0
    nonLogee = 0
    for year in range(2015, finalYear + 1):
        progres = "Année %i/%i" %(year, finalYear)
        printer(progres)
        popALoger = dicPop[year]
        maxSrf = dicSrf[year]
        if hasPlu and pluPriority:
            resteSrf, restePop = urbanize(maxSrf - preConstruit, popALoger - preLogee, True)
            while resteSrf > 0:
                resteSrf, restePop = urbanize(resteSrf, restePop, False)
            if restePop > 0:
                _, restePop = urbanize(0, restePop, False)
        else:
            resteSrf, restePop = urbanize(maxSrf - preConstruit, popALoger - preLogee, False)
        preConstruit = -resteSrf
        preLogee = -restePop
        if restePop > 0 and year == finalYear:
            nonLogee = restePop
        to_tif(demographie, 'uint16', proj, geot, projectPath + 'snapshots/demographie/demo_' + str(year) + '.tif')
        to_tif(urb, 'byte', proj, geot, projectPath + 'snapshots/urbanisation/urb_' + str(year) + '.tif')
        to_tif(srfSol, 'uint16', proj, geot, projectPath + 'snapshots/surface_sol/srf_sol_' + str(year) + '.tif')
        to_tif(srfPla, 'uint32', proj, geot, projectPath + 'snapshots/surface_plancher/srf_pla_' + str(year) + '.tif')


    # Calcul et export des résultats
    popNouv = demographie - demographieDep
    srfSolNouv = srfSol - srfSol14
    to_tif(srfSolNouv, 'uint16', proj, geot, projectPath + 'surface_sol_construite.tif')
    srfPlaNouv = srfPla - srfPla14
    to_tif(srfPlaNouv, 'uint32', proj, geot, projectPath + 'surface_plancher_construite.tif')
    expansion = np.where((urb14 == 0) & (urb ==1), 1, 0)
    peuplementMoyen = np.nanmean(np.where(popNouv == 0, np.nan, popNouv))
    impactEnv = int(np.where(expansion == 1, 1 - eco, 0).sum() * cellSurf)
    expansionSum = expansion.sum()

    to_tif(urb, 'uint16', proj, geot, projectPath + 'urbanisation_' + str(finalYear) + '.tif')
    to_tif(demographie, 'uint16', proj, geot, projectPath + 'demographie_' + str(finalYear) + '.tif')
    to_tif(expansion, 'byte', proj, geot, projectPath + 'expansion.tif')
    expansionSum = expansion.sum()
    to_tif(popNouv, 'uint16', proj, geot, projectPath + 'population_nouvelle.tif')
    popNouvCount = popNouv.sum()

    mesures.write("Peuplement moyen des cellules, " + str(peuplementMoyen) + "\n")
    mesures.write("Expansion totale en m2, " + str(expansionSum * cellSurf) + "\n")
    mesures.write("Impact environnemental cumulé, " + str(impactEnv) + "\n")
    mesures.write("Nombre de personnes final, " + str(demographie.sum()) + '\n')
    mesures.write('Population non logée, ' + str(nonLogee))

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
