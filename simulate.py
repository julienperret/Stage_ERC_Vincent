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
        elif 'pluPriority' in arg:
            pluPriority = literal_eval(arg.split('=')[1])
        elif 'buildNonRes' in arg:
            buildNonRes = literal_eval(arg.split('=')[1])
        elif 'densifyGround' in arg:
            densifyGround = literal_eval(arg.split('=')[1])
        elif 'densifyOld' in arg:
            densifyOld = literal_eval(arg.split('=')[1])
        elif 'maximumDensity' in arg:
            maximumDensity = literal_eval(arg.split('=')[1])
        elif 'maxBuiltRatio' in arg:
            maxBuiltRatio = float(arg.split('=')[1])
        elif 'winSize' in arg:
            winSize = int(arg.split('=')[1])
        elif 'minContig' in arg:
            minContig = int(arg.split('=')[1])
        elif 'maxContig' in arg:
            maxContig = int(arg.split('=')[1])
        elif 'finalYear' in arg:
            finalYear = int(arg.split('=')[1])

### Valeurs de paramètres par défaut ###
if 'finalYear' not in globals():
    finalYear = 2040
# Scénarios concernants l'étalement : tendanciel, stable, reduction
if 'scenario' not in globals():
    scenario = 'tendanciel'
# Priorité aux ZAU
if 'pluPriority' not in globals():
    pluPriority = True
# Pour simuler également la construction des surfaces non résidentielles
if 'buildNonRes' not in globals():
    buildNonRes = True
# Pour autoriser à construire de nouveaux bâtiments dans des cellules déjà urbanisées
if 'densifyGround' not in globals():
    densifyGround = False
# Pour autoriser à densifier la surface plancher pré-éxistante
if 'densifyOld' not in globals():
    densifyOld = False
# Pour toujours densifier la cellule au maximum de sa capacité plancher
if 'maximumDensity' not in globals():
    maximumDensity = False
# Taux d'artificialisation maximum d'une cellule
if 'maxBuiltRatio' not in globals():
    maxBuiltRatio = 80
# Paramètres pour les règles de contiguïtés
if 'winSize' not in globals():
    winSize = 3
if 'minContig' not in globals():
    minContig = 1
if 'maxContig' not in globals():
    maxContig = 5

# Tirage pondéré qui retourne un index par défaut ou une liste de tuples (row, col)
def choose(weight, size=1):
    global countChoices
    countChoices += size
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
    if (row > size - 1 and row + size-1 < rows) and (col > size - 1 and col + size-1 < cols):
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
        return None

# Artificialisation d'une surface tirée comprise entre la taille moyenne d'un bâtiment (IRIS) et la capacité max de la cellule
def expand(row, col):
    global capaSol, urb
    minV = ssrMed[row][col]
    maxV = capaSol[row][col]
    ss = 0
    if maxV > minV:
        sumContig = slidingWin(urb, row, col, winSize, 'sum')
        if sumContig:
            if minContig < sumContig <= maxContig:
                if maximumDensity:
                    ss = maxV
                else:
                    ss = np.random.randint(minV, maxV + 1)
                capaSol[row][col] -= ss
                urb[row][col] = 1
    return ss

# Pour urbaniser verticalement à partir d'une surface au sol donnée et d'un nombre de niveaux tirés aléatoirement entre 1 et le nbNiv max par IRIS
def build(ss, row, col):
    sp = 0
    nivMin = 1
    nivMax = nbNivMax[row][col]
    nbNiv = np.random.randint(nivMin, nivMax + 1)
    sp = ss * nbNiv
    return sp

# Densification d'une surface tirée comprise entre la taille moyenne d'un bâtiment (IRIS) et la capacité max de la cellule
def densify(mode, row, col):
    global capaSol
    if mode == 'ground':
        ss = 0
        minV = ssrMed[row][col]
        maxV = capaSol[row][col]
        if maxV > minV:
            if maximumDensity:
                ss = maxV
            else:
                ss = np.random.randint(minV, maxV + 1)
            capaSol[row][col] -= ss
        return ss
    elif mode == 'height':
        sp = 0
        nivMin = int(srfPla[row][col] / srfSolRes[row][col]) + 1
        nivMax = nbNivMax[row][col]
        ssol = srfSolRes[row][col]
        if nivMin < nivMax:
            nbNiv = np.random.randint(nivMin, nivMax + 1)
        else:
            nbNiv = nivMax
        sp = ssol * nbNiv
        sp -= srfPla[row][col]
        if sp < m2PlaHab[row][col]:
            sp = 0
        return sp

# Fonction principale pour gérer etalement puis densification,
def urbanize(pop, maxSrf=0, zau=False):
    global demographie, capaSol, srfSol, srfSolRes, srfPla
    tmpSrfPla = np.zeros([rows, cols], np.uint32)
    tmpSrfSol = np.zeros([rows, cols], np.uint16)
    artif = 0
    count = 0
    # Expansion par ouverture de nouvelles cellules ou densification au sol de cellules déja urbanisées
    if maxSrf > 0:
        tmpInteret = np.where((capaSol >= ssrMed) & (urb == 0), interet, 0)
        if zau:
            tmpInteret = np.where(pluPrio == 1, tmpInteret, 0)
        while artif < maxSrf and count < pop and tmpInteret.sum() > 0:
            ss = 0
            sp = 0
            row, col = choose(tmpInteret)
            if urb[row][col] == 0:
                ss = expand(row, col)
            if ss > 0 :
                artif += ss
                tmpSrfSol[row][col] += ss
                sp = build(ss, row, col)
                if sp > 0:
                    tmpSrfPla[row][col] += sp
                    count = np.where(m2PlaHab != 0, (tmpSrfPla / m2PlaHab).round(), 0).astype(np.uint16).sum()
                else:
                    tmpInteret[row][col] = 0
            else:
                tmpInteret[row][col] = 0

        # On densifie l'existant si les cellules vides sont déjà saturées
        if artif < maxSrf and count < pop and densifyGround:
            tmpInteret = np.where((capaSol >= ssrMed) & (urb == 1), interet, 0)
            if zau:
                tmpInteret = np.where(pluPrio == 1, tmpInteret, 0)
            while artif < maxSrf and count < pop and tmpInteret.sum() > 0:
                ss = 0
                sp = 0
                row, col = choose(tmpInteret)
                ss = densify('ground', row, col)
                if ss > 0 :
                    artif += ss
                    tmpSrfSol[row][col] += ss
                    sp = build(ss, row, col)
                    if sp > 0:
                        tmpSrfPla[row][col] += sp
                        count = np.where(m2PlaHab != 0, (tmpSrfPla / m2PlaHab).round(), 0).astype(np.uint16).sum()
                    else:
                        tmpInteret[row][col] = 0
                else:
                    tmpInteret[row][col] = 0

    # Densification du bâti existant si on n'a pas pu loger tout le monde
    if count < pop and densifyOld:
        tmpInteret = np.where(srfSolRes14 > 0, interet, 0)
        while count < pop and tmpInteret.sum() > 0:
            sp = 0
            row, col = choose(tmpInteret)
            sp = densify('height', row, col)
            if sp > 0:
                tmpSrfPla[row][col] += sp
                count = np.where(m2PlaHab != 0, (tmpSrfPla / m2PlaHab).round(), 0).astype(np.uint16).sum()
            else:
                tmpInteret[row][col] = 0

    srfSol += tmpSrfSol
    if buildNonRes:
        tmpSrfSol = (tmpSrfSol * txSsr).round().astype(np.uint16)
    srfSolRes += tmpSrfSol
    srfPla += tmpSrfPla
    demographie += np.where(m2PlaHab != 0, (tmpSrfPla / m2PlaHab).round(), 0).astype(np.uint16)

    return (pop - count, maxSrf - artif)

# Création des variables GDAL pour écriture de raster, indispensables pour la fonction to_tif()
ds = gdal.Open(dataDir + 'demographie_2014.tif')
demographieDep = ds.GetRasterBand(1).ReadAsArray().astype(np.uint16)
cols, rows = demographieDep.shape[1], demographieDep.shape[0] # x, y
proj = ds.GetProjection()
geot = ds.GetGeoTransform()
pixSize = int(geot[1])
srfCell = pixSize * pixSize
ds = None

project = outputDir + str(pixSize) + 'm' + '_tx' + str(rate) + '_' + scenario + '_buildRatio' + str(maxBuiltRatio)
if pluPriority:
    project += '_pluPrio'
if buildNonRes :
    project += '_buildNonRes'
if densifyGround :
    project += '_densifyGround'
if densifyOld :
    project += '_densifyOld'
if maximumDensity :
    project += '_maximumDensity'
if finalYear != 2040:
    project += '_' + str(finalYear)
project += '/'

if os.path.exists(project):
    rmtree(project)
os.makedirs(project + 'output')
os.mkdir(project + 'snapshots')
os.mkdir(project + 'snapshots/demographie')
os.mkdir(project + 'snapshots/urbanisation')
os.mkdir(project + 'snapshots/surface_sol')
os.mkdir(project + 'snapshots/surface_plancher')

with open(project + 'log.txt', 'w') as log, open(project + 'output/mesures.csv', 'w') as mesures:
    try:
        # Création des dictionnaires contenant la population par année
        with open(dataDir + 'population.csv') as csvFile:
            reader = csv.reader(csvFile)
            next(reader, None)
            histPop = {rows[0]:rows[1] for rows in reader}

        pop09 = int(histPop['2009'])
        pop14 = int(histPop['2014'])
        evoPop = (pop14 - pop09) / pop09 / 5
        if rate == -1.0:
            rate = evoPop * 100

        popDic = {}
        year = 2015
        pop = pop14
        while year <= finalYear:
            popDic[year] = round(pop * (rate / 100))
            pop += round(pop * (rate / 100))
            year += 1

        # Nombre total de personnes à loger - permet de vérifier si le raster capacité permet d'accueillir tout le monde
        sumPopALoger = sum(popDic.values())
        log.write("Population à loger d'ici à " + str(finalYear) + " : " + str(sumPopALoger) + "\n")

        # Calcul des coefficients de pondération de chaque raster d'intérêt, csv des poids dans le répertoire des données locales
        with open(dataDir + 'interet/poids.csv') as r:
            reader = csv.reader(r)
            next(reader, None)
            poids = {rows[0]:int(rows[1]) for rows in reader}

        coef = {}
        with open(project + 'coefficients_interet.csv', 'x') as w:
            for key in poids:
                coef[key] = poids[key] / sum(poids.values())
                w.write(key + ', ' + str(coef[key]) + '\n')

        # Préparation des restrictions et gestion du PLU
        restriction = to_array(dataDir + 'interet/restriction_totale.tif')
        if os.path.exists(dataDir + 'interet/plu_restriction.tif') and os.path.exists(dataDir + 'interet/plu_priorite.tif'):
            skipZau = False
            pluPrio = to_array(dataDir + 'interet/plu_priorite.tif')
            pluRest = to_array(dataDir + 'interet/plu_restriction.tif')
            restrictionNonPlu = restriction.copy()
            restriction = np.where(pluRest != 1, restriction, 1)
        else:
            skipZau = True
            pluPriority = False

        # Déclaration des matrices
        demographie14 = to_array(dataDir + 'demographie_2014.tif', np.uint16)
        srfSol09 = to_array(dataDir + 'srf_sol_2009.tif', np.uint16)
        srfSol14 = to_array(dataDir + 'srf_sol_2014.tif', np.uint16)
        srfSolRes14 = to_array(dataDir + 'srf_sol_res.tif', np.uint16)
        ssrMed = to_array(dataDir + 'iris_ssr_med.tif', np.uint16)
        m2PlaHab = to_array(dataDir + 'iris_m2_hab.tif', np.uint16)
        srfPla14 = to_array(dataDir  + 'srf_pla.tif', np.uint32)
        nbNivMax = to_array(dataDir + 'iris_nbniv_max.tif')
        if buildNonRes:
            txSsr = to_array(dataDir + 'iris_tx_ssr.tif', np.float32)
        # Amenités
        eco = to_array(dataDir + 'interet/non-importance_ecologique.tif', np.float32)
        ocs = to_array(dataDir + 'interet/occupation_sol.tif', np.float32)
        rou = to_array(dataDir + 'interet/proximite_routes.tif', np.float32)
        tra = to_array(dataDir + 'interet/proximite_transport.tif', np.float32)
        sir = to_array(dataDir + 'interet/densite_sirene.tif', np.float32)
        # Création du raster final d'intérêt avec pondération
        interet = np.where((restriction != 1), (eco * coef['ecologie']) + (ocs * coef['ocsol']) +
                           (rou * coef['routes']) + (tra * coef['transport']) + (sir * poids['sirene']), 0)
        interet = (interet / np.amax(interet)).astype(np.float32)

        # Création des rasters de capacité en surfaces sol et plancher
        capaSol = np.zeros([rows, cols], np.uint32) + int(srfCell * (maxBuiltRatio / 100))
        capaSol = np.where((restriction != 1) & (srfSol14 < capaSol), capaSol - srfSol14, 0).astype(np.uint16)
        # Statistiques sur l'évolution du bâti
        urb09 = np.where(srfSol09 > 0, 1, 0).astype(np.byte)
        urb14 = np.where(srfSol14 > 0, 1, 0).astype(np.byte)
        m2SolHab09 = srfSol09.sum() / pop09
        m2SolHab14 = srfSol14.sum() / pop14
        m2SolHabEvo = (m2SolHab14 - m2SolHab09) / m2SolHab09 / 5
        srfSolNonRes = srfSol14 - srfSolRes14
        ratioPlaSol14 = np.where(srfSol14 != 0, srfPla14 / srfSol14, 0).astype(np.float32)
        txArtif = (srfSol14 / srfCell).astype(np.float32)

        # Création du dictionnaire pour nombre de m² ouverts à l'urbanisation par année
        dicSrf = {}
        year = 2015
        if scenario == 'tendanciel':
            maxSrf = m2SolHab14
            while year <= finalYear :
                maxSrf += maxSrf * m2SolHabEvo
                dicSrf[year] = int(round(maxSrf) * popDic[year])
                year += 1
        elif scenario == 'stable':
            maxSrf = m2SolHab14
            while year <= finalYear :
                dicSrf[year] = int(round(maxSrf) * popDic[year])
                year += 1
        elif scenario == 'reduction':
            maxSrf = m2SolHab14
            totalYears = finalYear - year
            while year <= finalYear :
                dicSrf[year] = int(round(maxSrf) * popDic[year])
                maxSrf -= m2SolHab14 * (0.75 / totalYears)
                year += 1

        log.write('Consommation de surface au sol par habitant en 2014 : ' + str(int(round(m2SolHab14))) + ' m²\n')
        log.write('Evolution annuelle moyenne de la surface au sol par habitant : ' + str(round(m2SolHabEvo * 100, 4)) + ' %\n')
        log.write('Seuil en surface au sol par habitant calculé : ' + str(int(round(maxSrf))) + ' m²\n')

        # Instantanés de la situation à t0
        to_tif(urb14, 'byte', proj, geot, project + 'urbanisation_2014.tif')
        to_tif(capaSol, 'uint16', proj, geot, project + 'capacite_sol_2014.tif')
        to_tif(txArtif, 'float32', proj, geot, project + 'taux_artif_2014.tif')
        to_tif(interet, 'float32', proj, geot, project + 'interet_2014.tif')
        to_tif(ratioPlaSol14, 'float32', proj, geot, project + 'ratio_plancher_sol_2014.tif')

        start_time = time()
        ##### Boucle principale #####
        demographie = demographie14.copy()
        srfSol = srfSol14.copy()
        srfSolRes = srfSolRes14.copy()
        srfPla = srfPla14.copy()
        urb = urb14.copy()
        preBuilt = 0
        nonBuilt = 0
        preLogee = 0
        nonLogee = 0
        countChoices = 0
        removedZau = False
        for year in range(2015, finalYear + 1):
            progres = "Année %i/%i" %(year, finalYear)
            printer(progres)
            maxSrf = dicSrf[year]
            popALoger = popDic[year]
            if pluPriority and not skipZau:
                restePop, resteSrf = urbanize(popALoger - preLogee, maxSrf - preBuilt,  True)
                if restePop > 0 and resteSrf > 0:
                    skipZau = True
                    print('\nSKIPPING ZAU FROM NOW ON')
                    restePop, resteSrf = urbanize(restePop, resteSrf, False)
            else:
                restePop, resteSrf = urbanize(popALoger - preLogee, maxSrf - preBuilt)
            preBuilt = -resteSrf
            preLogee = -restePop

            # Snapshots
            to_tif(demographie, 'uint16', proj, geot, project + 'snapshots/demographie/demo_' + str(year) + '.tif')
            to_tif(urb, 'byte', proj, geot, project + 'snapshots/urbanisation/urb_' + str(year) + '.tif')
            to_tif(srfSol, 'uint16', proj, geot, project + 'snapshots/surface_sol/sol_' + str(year) + '.tif')
            to_tif(srfPla, 'uint32', proj, geot, project + 'snapshots/surface_plancher/plancher_' + str(year) + '.tif')

        if restePop > 0:
            nonLogee = int(round(restePop))
        if resteSrf > 0:
            nonBuilt = int(round(resteSrf))

        end_time = time()
        execTime = round(end_time - start_time, 2)
        print('\nDurée de la simulation : ' + str(execTime) + ' secondes')

        # Calcul et export des résultats
        popNouv = demographie - demographieDep
        popNouvCount = popNouv.sum()
        peuplementMoyen = round(np.nanmean(np.where(popNouv == 0, np.nan, popNouv)), 3)
        srfSolNouv = srfSol - srfSol14
        srfPlaNouv = srfPla - srfPla14
        txArtifNouv = (srfSolNouv / srfCell).astype(np.float32)
        txArtifMoyen = round(np.nanmean(np.where(txArtifNouv == 0, np.nan, txArtifNouv)) * 100, 3)
        ratioPlaSol = np.where(srfSol != 0, srfPla / srfSol, 0).astype(np.float32)
        expansion = np.where((urb14 == 0) & (urb == 1), 1, 0)
        expansionSum = expansion.sum()
        impactEnv = (txArtifNouv * eco).sum()

        to_tif(urb, 'uint16', proj, geot, project + 'output/urbanisation_' + str(finalYear) + '.tif')
        to_tif(srfSol, 'uint16', proj, geot, project + 'output/surface_sol_' + str(finalYear) + '.tif')
        to_tif(srfPla, 'uint32', proj, geot, project + 'output/surface_plancher_' + str(finalYear) + '.tif')
        to_tif(demographie, 'uint16', proj, geot, project + 'output/demographie_' + str(finalYear) + '.tif')
        to_tif(ratioPlaSol, 'float32', proj, geot, project + 'output/ratio_plancher_sol_' + str(finalYear) + '.tif')
        to_tif(txArtifNouv, 'float32', proj, geot, project + 'output/taux_artificialisation.tif')
        to_tif(expansion, 'byte', proj, geot, project + 'output/expansion.tif')
        to_tif(srfSolNouv, 'uint16', proj, geot, project + 'output/surface_sol_construite.tif')
        to_tif(srfPlaNouv, 'uint32', proj, geot, project + 'output/surface_plancher_construite.tif')
        to_tif(popNouv, 'uint16', proj, geot, project + 'output/population_nouvelle.tif')

        mesures.write("Population non logée, " + str(nonLogee) + '\n')
        mesures.write("Surface au sol non construite, " + str(nonBuilt) + '\n')
        mesures.write("Peuplement moyen des cellules, " + str(peuplementMoyen) + "\n")
        mesures.write("Expansion au sol, " + str(srfSolNouv.sum()) + "\n")
        mesures.write("Surface plancher construite, " + str(srfPlaNouv.sum()) + "\n")
        mesures.write("Cellules ouvertes à l'urbanisation, " + str(expansion.sum()) + "\n")
        mesures.write("Taux moyen d'artificialisation, " + str(txArtifMoyen) + "\n")
        mesures.write("Impact environnemental cumulé, " + str(impactEnv) + "\n")
        log.write("Surface au sol non construite : " + str(nonBuilt) + '\n')
        log.write("Population non logée : " + str(nonLogee) + '\n')
        log.write("Population logée : " + str(popNouvCount) + '\n')
        log.write("Démographie définitive : " + str(demographie.sum()) + '\n')
        log.write("Nombre total de cellules tirées aléatoirement : " + str(countChoices) + '\n')
        log.write("Temps d'execution : " + str(execTime) + '\n')

        if densifyGround:
            densifSol = np.where((srfSol > srfSol14) & (srfSolRes14 > 0), 1, 0)
            to_tif(densifSol, 'byte', proj, geot, project + 'output/densification_sol.tif')
            mesures.write("Cellules densifiées au sol, " + str(densifSol.sum()) + "\n")

        if densifyOld:
            densifPla = np.where((srfPla > srfPla14) & (srfSolRes14 > 0), 1, 0)
            to_tif(densifPla, 'byte', proj, geot, project + 'output/densification_plancher.tif')
            mesures.write("Cellules densifiées au plancher, " + str(densifPla.sum()) + "\n")

    except:
        print("\n*** Error :")
        exc = sys.exc_info()
        traceback.print_exception(*exc, limit=3, file=sys.stdout)
        traceback.print_exception(*exc, limit=3, file=log)
        sys.exit()
