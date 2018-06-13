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
        if 'scenario' in arg:
            scenario = arg.split('=')[1]
            if scenario not in ['tendanciel', 'stable', 'reduction']:
                print('Erreur : le scénario doit être tendanciel, stable ou reduction.')
                sys.exit()
        if 'seuilPla' in arg:
            seuilPla = arg.split('=')[1]
        if 'maximumDensity' in arg:
            maximumDensity = literal_eval(arg.split('=')[1])
        if 'pluPriority' in arg:
            pluPriority = literal_eval(arg.split('=')[1])
        if 'finalYear' in arg:
            finalYear = int(arg.split('=')[1])
        if 'buildNonRes' in arg:
            buildNonRes = literal_eval(arg.split('=')[1])
        if 'densifyNonRes' in arg:
            densifyNonRes = literal_eval(arg.split('=')[1])
        if 'maxBuiltRatio' in arg:
            maxBuiltRatio = float(arg.split('=')[1])
        if 'winSize' in arg:
            winSize = int(arg.split('=')[1])
        if 'maxContig' in arg:
            maxContig = int(arg.split('=')[1])

### Valeurs de paramètres par défaut ###
if 'finalYear' not in globals():
    finalYear = 2040
# Scénarios concernants l'étalement : tendanciel, stable, reduction
if 'scenario' not in globals():
    scenario = 'tendanciel'
# Seuil utilisé pour limiter la surface plancher par IRIS lors de la densification : 'q3' ou 'max'
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
# Pour densifier le plancher partout, même si ce n'est pas du bâti résidentiel
if 'densifyNonRes' not in globals():
    densifyNonRes = False
# Taux d'artificialisation maximum d'une cellule
if 'maxBuiltRatio' not in globals():
    maxBuiltRatio = 80
# Paramètres pour les règles de contiguïtés : maxContig <= winSize²
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
    nivMin = 1
    nivMax = nbNivMax[row][col]
    minV = ssrMed[row][col]
    maxV = capaSol[row][col]
    sS = 0
    sP = 0
    if maxV > minV:
        if slidingWin(urb, row, col, winSize, 'sum') <= maxContig:
            if maximumDensity :
                sS = maxV
            else:
                sS = np.random.randint(minV, maxV + 1)
            capaSol[row][col] -= sS
            urb[row][col] = 1
            sP = sS
            if buildNonRes:
                sP *= txSsr[row][col]
            nbNiv = np.random.randint(nivMin, nivMax + 1)
            sP *= nbNiv
            if capaPla[row][col] > sP:
                capaPla[row][col] -= sP
            else:
                capaPla[row][col] = 0
    return (sS, sP)

# Densification d'une surface tirée comprise entre la taille moyenne d'un bâtiment (IRIS) et la capacité max de la cellule
def densify(mode, row, col):
    global capaSol, capaPla
    sS = 0
    sP = 0
    if mode == 'sol':
        nivMin = 1
        nivMax = nbNivMax[row][col]
        minV = m2PlaHab[row][col]
        maxV = capaSol[row][col]
        if maxV > minV:
            sS = np.random.randint(minV, maxV + 1)
            capaSol[row][col] -= sS
            sP = sS
            if buildNonRes:
                sP *= txSsr[row][col]
            nbNiv = np.random.randint(nivMin, nivMax + 1)
            sP *= nbNiv
            if capaPla[row][col] > sP:
                capaPla[row][col] -= sP
            else:
                capaPla[row][col] = 0
    elif mode == 'pla':
        minV = m2PlaHab[row][col]
        maxV = capaPla[row][col]
        if maxV > minV:
            if maximumDensity:
                sP = maxV
            else:
                sP = np.random.randint(minV, maxV + 1)
            capaPla[row][col] -= sP
    return (sS, sP)

# Fonction principale pour gérer etalement puis densification,
def urbanize(pop, maxSrf=0, zau=False, ):
    global demographie, capaSol, srfSol, capaPla, srfPla, srfSolRes
    tmpDemog = np.zeros([rows, cols], np.uint16)
    tmpSrfPla = np.zeros([rows, cols], np.uint32)
    tmpSrfSol = np.zeros([rows, cols], np.uint16)
    count = 0
    built = 0
    # Expansion pas ouverture de nouvelles cellules ou densification au sol de cellules déja urbanisées
    if maxSrf > 0:
        tmpInteret = np.where((capaSol >= ssrMed) | (capaSol >= m2PlaHab), interet, 0)
        if zau:
            tmpInteret = np.where(pluPrio == 1, tmpInteret, 0)
        while built < maxSrf and count < pop and tmpInteret.sum() > 0:
            sS = 0
            sP = 0
            row, col = choose(tmpInteret)
            if urb[row][col] == 0:
                sS, sP = expand(row, col)
            else:
                sS, sP = densify('sol', row, col)
            if sS > 0 and sP > 0:
                built += sS
                tmpSrfSol[row][col] += sS
                tmpSrfPla[row][col] += sP
                count = np.where(m2PlaHab != 0, (tmpSrfPla / m2PlaHab).round(), 0).astype(np.uint16).sum()
            else:
                tmpInteret[row][col] = 0
        srfSol += tmpSrfSol
        srfSolRes += tmpSrfSol
    # Densification de l'existant lorsque la surface construite au sol max est atteinte
    if count < pop:
        if densifyNonRes :
            tmpInteret = np.where((urb == 1) & (capaPla >= m2PlaHab), interet, 0)
        else:
            tmpInteret = np.where((srfSolRes > 0) & (capaPla >= m2PlaHab), interet, 0)
        if zau:
            tmpInteret = np.where(pluPrio == 1, tmpInteret, 0)
        while count < pop and tmpInteret.sum() > 0:
            row, col = choose(tmpInteret)
            _, sP = densify('pla', row, col)
            if sP > 0:
                tmpSrfPla[row][col] += sP
                count = np.where(m2PlaHab != 0, (tmpSrfPla / m2PlaHab).round(), 0).astype(np.uint16).sum()
            else:
                tmpInteret[row][col] = 0

        srfPla += tmpSrfPla
        demographie += np.where(m2PlaHab != 0, (tmpSrfPla / m2PlaHab).round(), 0).astype(np.uint16)
    return (pop - count, maxSrf - built)

try:
    # Création des variables GDAL pour écriture de raster, indispensables pour la fonction to_tif()
    ds = gdal.Open(dataDir + 'demographie_2014.tif')
    demographieDep = ds.GetRasterBand(1).ReadAsArray().astype(np.uint16)
    cols, rows = demographieDep.shape[1], demographieDep.shape[0] # x, y
    proj = ds.GetProjection()
    geot = ds.GetGeoTransform()
    pixSize = int(geot[1])
    cellSurf = pixSize * pixSize
    ds = None

    projectPath = outputDir + str(pixSize) + 'm' + '_tx' + str(rate) + '_' + scenario + '_buildRatio' + str(maxBuiltRatio)
    if pluPriority:
        projectPath += '_pluPrio'
    if buildNonRes :
        projectPath += '_buildNonRes'
    if densifyNonRes :
        projectPath += '_densifyNonRes'
    if maximumDensity :
        projectPath += '_maximumDensity'
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
    log = open(projectPath + 'log.txt', 'x')
    mesures = open(projectPath + 'mesures.csv', 'x')

    # Création des dataframes contenant les informations par IRIS
    with open(dataDir + 'population.csv') as csvFile:
        reader = csv.reader(csvFile)
        next(reader, None)
        histPop = {rows[0]:rows[1] for rows in reader}

    pop09 = int(histPop['2009'])
    pop14 = int(histPop['2014'])
    evoPop = (pop14 - pop09) / pop09 / 5
    if rate == -1.0:
        rate = evoPop * 100

    dicPop = {}
    year = 2015
    pop = pop14
    while year <= finalYear:
        dicPop[year] = round(pop * (rate / 100))
        pop += round(pop * (rate / 100))
        year += 1

    # Nombre total de personnes à loger - permet de vérifier si le raster capacité permet d'accueillir tout le monde
    sumPopALoger = sum(dicPop.values())
    log.write("Population à loger d'ici à " + str(finalYear) + " : " + str(sumPopALoger) + "\n")

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

    # Préparation des restrictions et gestion du PLU
    restriction = to_array(dataDir + 'restriction_totale.tif')

    if os.path.exists(dataDir + 'plu_restriction.tif') and os.path.exists(dataDir + 'plu_priorite.tif'):
        hasPlu = True
        removedPlu = False
        pluPrio = to_array(dataDir + 'plu_priorite.tif')
        pluRest = to_array(dataDir + 'plu_restriction.tif')
        restrictionNonPlu = restriction.copy()
        restriction = np.where(pluRest != 1, restriction, 1)
    else:
        hasPlu = False

    # Déclaration des matrices
    demographie14 = to_array(dataDir + 'demographie_2014.tif', np.uint16)
    srfSol09 = to_array(dataDir + 'srf_sol_2009.tif', np.uint16)
    srfSol14 = to_array(dataDir + 'srf_sol_2014.tif', np.uint16)
    srfSolRes = to_array(dataDir + 'srf_sol_res.tif', np.uint16)
    ssrMed = to_array(dataDir + 'iris_ssr_med.tif', np.uint16)
    m2PlaHab = to_array(dataDir + 'iris_m2_hab.tif', np.uint16)
    srfPla14 = to_array(dataDir  + 'srf_pla.tif', np.uint32)
    nbNivMax = to_array(dataDir + 'iris_niv_max.tif', np.uint8)
    maxPla = to_array(dataDir + 'iris_srf_pla_' + seuilPla + '.tif', np.uint32)
    if buildNonRes:
        txSsr = to_array(dataDir + 'iris_tx_ssr.tif', np.float32)
    # Interets
    eco = to_array(dataDir + 'non-importance_ecologique.tif', np.float32)
    ocs = to_array(dataDir + 'occupation_sol.tif', np.float32)
    rou = to_array(dataDir + 'proximite_routes.tif', np.float32)
    tra = to_array(dataDir + 'proximite_transport.tif', np.float32)
    sir = to_array(dataDir + 'densite_sirene.tif', np.float32)
    # Création du raster final d'intérêt avec pondération
    interet = np.where((restriction != 1), (eco * coef['ecologie']) + (ocs * coef['ocsol']) +
                       (rou * coef['routes']) + (tra * coef['transport']) + (sir * poids['sirene']), 0)
    interet = (interet / np.amax(interet)).astype(np.float32)

    # Création des rasters de capacité en surfaces sol et plancher
    capaSol = np.zeros([rows, cols], np.uint32) + int(cellSurf * (maxBuiltRatio / 100))
    capaSol = np.where((restriction != 1) & (srfSol14 < capaSol), capaSol - srfSol14, 0).astype(np.uint16)
    capaPla = np.where(srfPla14 <= maxPla, maxPla - srfPla14, 0).astype(np.uint32)
    capaPla = np.where((restriction != 1) & (srfSolRes > 0), capaPla, 0)
    # Statistiques sur l'évolution du bâti
    urb09 = np.where(srfSol09 > 0, 1, 0).astype(np.byte)
    urb14 = np.where(srfSol14 > 0, 1, 0).astype(np.byte)
    m2SolHab09 = srfSol09.sum() / pop09
    m2SolHab14 = srfSol14.sum() / pop14
    m2SolHabEvo = (m2SolHab14 - m2SolHab09) / m2SolHab09 / 5
    srfSolNonRes = srfSol14 - srfSolRes
    ratioPlaSol14 = np.where(srfSolRes != 0, srfPla14 / srfSolRes, 0).astype(np.float32)
    txArtif = (srfSol14 / cellSurf).astype(np.float32)
    # Création du dictionnaire pour nombre de m² ouverts à l'urbanisation par année
    dicSrf = {}

    year = 2015
    if scenario == 'tendanciel':
        maxSrf = m2SolHab14
        while year <= finalYear :
            maxSrf += maxSrf * m2SolHabEvo
            dicSrf[year] = int(round(maxSrf) * dicPop[year])
            year += 1
    elif scenario == 'stable':
        maxSrf = m2SolHab14
        while year <= finalYear :
            dicSrf[year] = int(round(maxSrf) * dicPop[year])
            year += 1
    elif scenario == 'reduction':
        maxSrf = m2SolHab14
        totalYears = finalYear - year
        while year <= finalYear :
            dicSrf[year] = int(round(maxSrf) * dicPop[year])
            maxSrf -= m2SolHab14 * (0.75 / totalYears)
            year += 1

    log.write('Consommation de surface au sol par habitant en 2014 : ' + str(int(round(m2SolHab14))) + ' m²\n')
    log.write('Evolution annuelle moyenne de la surface au sol par habitant : ' + str(round(m2SolHabEvo * 100, 4)) + ' %\n')
    log.write('Seuil en surface au sol par habitant calculé : ' + str(int(round(maxSrf))) + ' m²\n')

    # Instantanés de la situation à t0
    to_tif(urb14, 'byte', proj, geot, projectPath + 'urbanisation_2014.tif')
    to_tif(capaSol, 'uint16', proj, geot, projectPath + 'capacite_sol_2014.tif')
    to_tif(capaPla, 'uint32', proj, geot, projectPath + 'capacite_plancher_2014.tif')
    to_tif(txArtif, 'float32', proj, geot, projectPath + 'taux_artif_2014.tif')
    to_tif(interet, 'float32', proj, geot, projectPath + 'interet_2014.tif')
    to_tif(ratioPlaSol14, 'float32', proj, geot, projectPath + 'ratio_pla_sol_2014.tif')

    start_time = time()
    ##### Boucle principale #####
    demographie = demographie14.copy()
    srfSol = srfSol14.copy()
    srfPla = srfPla14.copy()
    urb = urb14.copy()
    preConstruit = 0
    nonConstruit = 0
    preLogee = 0
    nonLogee = 0

    for year in range(2015, finalYear + 1):
        progres = "Année %i/%i" %(year, finalYear)
        printer(progres)
        popALoger = dicPop[year]
        maxSrf = dicSrf[year]
        if hasPlu and pluPriority:
            restePop, resteSrf = urbanize(popALoger - preLogee, maxSrf - preConstruit,  True)
            if resteSrf > 0 and restePop > 0:
                restePop, resteSrf = urbanize(restePop, resteSrf)
            elif restePop > 0:
                restePop, _ = urbanize(restePop)
        else:
            restePop, resteSrf = urbanize(popALoger - preLogee, maxSrf - preConstruit)
        preConstruit = -resteSrf
        preLogee = -restePop

        # Snapshots
        to_tif(demographie, 'uint16', proj, geot, projectPath + 'snapshots/demographie/demo_' + str(year) + '.tif')
        to_tif(urb, 'byte', proj, geot, projectPath + 'snapshots/urbanisation/urb_' + str(year) + '.tif')
        to_tif(srfSol, 'uint16', proj, geot, projectPath + 'snapshots/surface_sol/sol_' + str(year) + '.tif')
        to_tif(srfPla, 'uint32', proj, geot, projectPath + 'snapshots/surface_plancher/plancher_' + str(year) + '.tif')

    if restePop > 0:
        nonLogee = int(round(restePop))
    if resteSrf > 0:
        nonConstruit = int(round(resteSrf))

    if nonLogee > 0 and hasPlu:
        removedPlu = True
        print('\n' + str(nonLogee) + ' personnes non logées, on retire les restriction du PLU pour une dernière passe...')
        log.write('Surface au sol non construite avant retrait du PLU : ' + str(nonConstruit) + ' m²\n')
        log.write('Population non logée avant retrait du PLU : ' + str(nonLogee) + '\n')
        restriction = restrictionNonPlu.copy()
        capaSol = np.zeros([rows, cols], np.uint32) + int(cellSurf * (maxBuiltRatio / 100))
        capaSol = np.where((restriction != 1) & (srfSol < capaSol), capaSol - srfSol, 0).astype(np.uint16)
        capaPla = np.where(srfPla <= maxPla, maxPla - srfPla, 0).astype(np.uint32)
        capaPla = np.where((restriction != 1) & (srfSolRes > 0), capaPla, 0)
        restePop, resteSrf = urbanize(nonLogee, nonConstruit, False)
        if restePop > 0:
            nonLogee = int(round(restePop))
        if resteSrf > 0:
            nonConstruit = int(round(resteSrf))

    end_time = time()
    execTime = round(end_time - start_time, 2)
    print('\nTerminé en ' + str(execTime) + ' secondes')

    # Calcul et export des résultats
    popNouv = demographie - demographieDep
    popNouvCount = popNouv.sum()
    peuplementMoyen = round(np.nanmean(np.where(popNouv == 0, np.nan, popNouv)), 3)
    srfSolNouv = srfSol - srfSol14
    srfPlaNouv = srfPla - srfPla14
    txArtifNouv = (srfSol / cellSurf).astype(np.float32)
    txArtifMoyen = round(np.nanmean(np.where(txArtifNouv == 0, np.nan, txArtifNouv)) * 100, 3)
    ratioPlaSol = np.where(srfSolRes != 0, srfPla / srfSolRes, 0).astype(np.float32)
    expansion = np.where((urb14 == 0) & (urb == 1), 1, 0)
    expansionSum = expansion.sum()
    impactEnv = (txArtifNouv * eco).sum()

    to_tif(urb, 'uint16', proj, geot, projectPath + 'urbanisation_' + str(finalYear) + '.tif')
    to_tif(srfSol, 'uint16', proj, geot, projectPath + 'surface_sol_' + str(finalYear) + '.tif')
    to_tif(srfPla, 'uint32', proj, geot, projectPath + 'surface_plancher_' + str(finalYear) + '.tif')
    to_tif(demographie, 'uint16', proj, geot, projectPath + 'demographie_' + str(finalYear) + '.tif')
    to_tif(txArtifNouv, 'float32', proj, geot, projectPath + 'taux_artif_' + str(finalYear) + '.tif')
    to_tif(ratioPlaSol, 'float32', proj, geot, projectPath + 'ratio_pla_sol_' + str(finalYear) + '.tif')
    to_tif(expansion, 'byte', proj, geot, projectPath + 'expansion.tif')
    to_tif(srfSolNouv, 'uint16', proj, geot, projectPath + 'surface_sol_construite.tif')
    to_tif(srfPlaNouv, 'uint32', proj, geot, projectPath + 'surface_plancher_construite.tif')
    to_tif(popNouv, 'uint16', proj, geot, projectPath + 'population_nouvelle.tif')

    if hasPlu:
        mesures.write("Suppression du PLU, " + str(removedPlu) + '\n')
    mesures.write("Population non logée, " + str(nonLogee) + '\n')
    mesures.write("Surface au sol non construite, " + str(nonConstruit) + '\n')
    mesures.write("Peuplement moyen des cellules, " + str(peuplementMoyen) + "\n")
    mesures.write("Expansion au sol, " + str(srfSolNouv.sum()) + "\n")
    mesures.write("Surface plancher construite, " + str(srfPlaNouv.sum()) + "\n")
    mesures.write("Taux moyen d'artificialisation, " + str(txArtifMoyen) + "\n")
    mesures.write("Impact environnemental cumulé, " + str(impactEnv) + "\n")
    log.write("Surface au sol non construite finale : " + str(nonConstruit) + '\n')
    log.write("Population non logée finale : " + str(nonLogee) + '\n')
    log.write("Population logée : " + str(popNouvCount) + '\n')
    log.write("Démographie définitive : " + str(demographie.sum()) + '\n')
    log.write("Temps d'execution : " + str(execTime))

except:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    print("\n*** Error :")
    traceback.print_exception(exc_type, exc_value, exc_traceback, limit=2, file=sys.stdout)
    log.write('\n*** Error :\n' + str(sys.exc_info()[0]) + '\n' + str(sys.exc_info()[1]) + '\n' + str(sys.exc_info()[2]))
    log.close()
    sys.exit()

mesures.close()
log.close()
