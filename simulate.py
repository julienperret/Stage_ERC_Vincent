#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import csv
import gdal
import traceback
import numpy as np
from time import time
from pathlib import Path
from shutil import rmtree
from ast import literal_eval
from toolbox import to_tif, printer, to_array

# Ignorer les erreurs de numpy lors d'une division par 0
np.seterr(divide='ignore', invalid='ignore')

# Convertit les réels en booléen
# def to_bool(r):
#     b = True if r > 0.5 else False
#     return b

# Stockage et contrôle de la validité des paramètres utilisateur
dataDir = Path(sys.argv[1])
outputDir = Path(sys.argv[2])
growth = float(sys.argv[3])
if len(sys.argv) == 5:
    argList = sys.argv[4].split()
    for arg in argList:
        if 'scenario' in arg:
            scenario = arg.split('=')[1]
            if scenario not in ['tendanciel', 'stable', 'reduction']:
                print('Error: scenario value must be tendanciel, stable or reduction.')
                sys.exit()
        elif 'finalYear' in arg:
            finalYear = int(arg.split('=')[1])
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
        elif 'winSize' in arg:
            winSize = int(arg.split('=')[1])
        elif 'minContig' in arg:
            minContig = float(arg.split('=')[1])
        elif 'maxContig' in arg:
            maxContig = float(arg.split('=')[1])
        elif 'writingTifs' in arg:
            writingTifs = literal_eval(arg.split('=')[1])
        elif 'writingSnapshots' in arg:
            writingSnapshots = literal_eval(arg.split('=')[1])

# *** Ici, ajouter les paramètres pour openMole
elif len(sys.argv) > 5:
    print('Nombre de paramètres incorrect.')
    sys.exit()

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
# Paramètres pour les règles de contiguïtés
if 'winSize' not in globals():
    winSize = 3
if 'minContig' not in globals():
    minContig = 0.2
if 'maxContig' not in globals():
    maxContig = 0.8
if 'writingTifs' not in globals():
    writingTifs = True
if 'writingSnapshots' not in globals():
    writingSnapshots = False

# Contrôle des paramètres
if growth > 3:
    print("Maximum evolution rate fixed at: 3 %")
    sys.exit()
if maxContig > 1 or minContig > 1:
    print("Error : minContig and maxContig should be float numbers < 1 !")
    sys.exit()
if minContig > maxContig:
    print("Error : maxContig should be higher than minContig !")
    sys.exit()

# Tirage pondéré qui retourne un index par défaut ou une liste de tuples (row, col)
def chooseCell(weight, size=1):
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

def chooseArea(id, row, col):
    ss = 0
    surf = np.array(list(poidsSurfaces[id].keys()))
    pds = np.array(list(poidsSurfaces[id].values()))
    if len(surf) > 0 or len(pds) > 0 :
        c = np.random.choice(surf, 1, p=pds/pds.sum())
        ss = c[0]
    else:
        surf = np.array(list(poidsSurfacesNoFit[id].keys()))
        pds = np.array(list(poidsSurfacesNoFit[id].values()))
        if len(surf) > 0 or len(pds) > 0 :
            c = np.random.choice(surf, 1, p=pds/pds.sum())
            ss = c[0]
    return ss

def chooseFloors(id, row, col):
    nbNiv = 0
    etages = np.array(list(poidsEtages[id].keys()))
    pds = np.array(list(poidsEtages[id].values()))
    if len(etages) > 0 or len(pds) > 0:
        c = np.random.choice(etages, 1, p=pds/pds.sum())
        nbNiv = c[0]
    else:
        etages = np.array(list(poidsEtagesNoFit[id].keys()))
        pds = np.array(list(poidsEtagesNoFit[id].values()))
        if len(etages) > 0 or len(pds) > 0:
            c = np.random.choice(etages, 1, p=pds/pds.sum())
            nbNiv = c[0]
    return nbNiv

# Fenêtre glissante pour statistique dans le voisinage d'un pixel
def winMean(array, row, col, size=3):
    if (row > size - 1 and row + size-1 < rows) and (col > size - 1 and col + size-1 < cols):
        s = 0
        pos = [i + 1 for i in range(- size//2, size//2)]
        for r in pos:
            for c in pos:
                s += array[row + r][col + c]
        return s / (size * size)
    else:
        return None

# Artificialisation d'une surface tirée comprise entre la taille moyenne d'un bâtiment (IRIS) et la capacité max de la cellule
def expand(row, col):
    ss = 0
    global capaSol, urb
    contig = winMean(urb, row, col, winSize)
    if contig and minContig < contig <= maxContig:
        id = irisId[row][col]
        ss = chooseArea(id, row, col)
        if ss > 0:
            maxSrf = capaSol[row][col]
            if ss > maxSrf :
                ss = maxSrf
            capaSol[row][col] -= ss
            urb[row][col] = 1
    return ss

# Pour urbaniser verticalement à partir d'une surface au sol donnée et d'un nombre de niveaux tiré aléatoirement entre 1 et le nbNiv max par IRIS
def build(ss, row, col):
    id = irisId[row][col]
    nbNiv = chooseFloors(id, row, col)
    if nbNiv > 0:
        sp = ss * nbNiv
    else:
        sp = 0
    return sp

# Densification d'une surface tirée comprise entre la taille moyenne d'un bâtiment (IRIS) et la capacité max de la cellule
def densify(mode, row, col):
    global capaSol
    if mode == 'ground':
        id = irisId[row][col]
        maxSrf = capaSol[row][col]
        ss = chooseArea(id, row, col)
        if ss > 0:
            if ss > maxSrf :
                ss = maxSrf
            capaSol[row][col] -= ss
        return ss
    elif mode == 'height':
        ssol = srfSolRes[row][col]
        id = irisId[row][col]
        nbNiv = chooseFloors(id, row, col)
        if nbNiv > 0:
            sp = ssol * nbNiv
            sp -= srfPla[row][col]
            if sp < m2PlaHab[row][col]:
                sp = 0
        else:
            sp = 0
        return sp

# Fonction principale pour gérer etalement puis densification,
def urbanize(pop, srfMax=0, zau=False):
    global demographie, capaSol, srfSol, srfSolRes, srfPla
    tmpSrfPla = np.zeros([rows, cols], np.uint32)
    tmpSrfSol = np.zeros([rows, cols], np.uint16)
    artif = 0
    count = 0
    # Expansion par ouverture de nouvelles cellules ou densification au sol de cellules déja urbanisées
    if srfMax > 0:
        tmpInteret = np.where(urb == 0, interet, 0)
        if zau:
            tmpInteret = np.where(pluPrio == 1, tmpInteret, 0)
        while artif < srfMax and count < pop and tmpInteret.sum() > 0:
            ss = 0
            sp = 0
            row, col = chooseCell(tmpInteret)
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
        if artif < srfMax and count < pop and densifyGround:
            tmpInteret = np.where((capaSol >= ssrMed) & (urb == 1), interet, 0)
            if zau:
                tmpInteret = np.where(pluPrio == 1, tmpInteret, 0)
            while artif < srfMax and count < pop and tmpInteret.sum() > 0:
                ss = 0
                sp = 0
                row, col = chooseCell(tmpInteret)
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
    elif count < pop and densifyOld:
        tmpInteret = np.where(srfSolRes14 > 0, interet, 0)
        while count < pop and tmpInteret.sum() > 0:
            sp = 0
            row, col = chooseCell(tmpInteret)
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

    return (pop - count, srfMax - artif)

# Création des variables GDAL pour écriture de raster, indispensables pour la fonction to_tif()
ds = gdal.Open(str(dataDir/'iris_id.tif'))
irisId = ds.GetRasterBand(1).ReadAsArray().astype(np.uint8)
cols, rows = irisId.shape[1], irisId.shape[0] # x, y
proj = ds.GetProjection()
geot = ds.GetGeoTransform()
pixSize = int(geot[1])
srfCell = pixSize * pixSize
ds = None

projectStr = '%im_tx%s_%s_winSize%i_minContig%s_maxContig%s'%(pixSize, str(growth), scenario, winSize, str(minContig), str(maxContig))
if pluPriority:
    projectStr += '_pluPrio'
if buildNonRes:
    projectStr += '_buildNonRes'
if densifyGround:
    projectStr += '_densifyGround'
if densifyOld:
    projectStr += '_densifyOld'
if maximumDensity:
    projectStr += '_maximumDensity'
if finalYear != 2040:
    projectStr += '_' + str(finalYear)
project = outputDir/projectStr

if project.exists():
    rmtree(str(project))
os.makedirs(str(project/'output'))

if writingTifs and writingSnapshots:
    mkdirList = [
        'snapshots',
        'snapshots/demographie',
        'snapshots/urbanisation',
        'snapshots/surface_sol',
        'snapshots/surface_plancher'
    ]
    for d in mkdirList:
        os.mkdir(str(project/d))

with (project/'log.txt').open('w') as log, (project/'output/mesures.csv').open('w') as mesures:
    try:
        # Création des dictionnaires contenant la population par année
        with (dataDir/'population.csv').open('r') as csvFile:
            reader = csv.reader(csvFile)
            next(reader, None)
            histPop = {rows[0]:rows[1] for rows in reader}

        pop09 = int(histPop['2009'])
        pop14 = int(histPop['2014'])
        evoPop = (pop14 - pop09) / pop09 / 5
        if growth == -1.0:
            growth = evoPop * 100

        popDic = {}
        year = 2015
        pop = pop14
        while year <= finalYear:
            popDic[year] = round(pop * (growth / 100))
            pop += round(pop * (growth / 100))
            year += 1

        # Nombre total de personnes à loger - permet de vérifier si le raster capacité permet d'accueillir tout le monde
        sumPopALoger = sum(popDic.values())
        log.write("Population to put up until " + str(finalYear) + " : " + str(sumPopALoger) + "\n")

        # Calcul des coefficients de pondération de chaque raster d'intérêt, csv des poids dans le répertoire des données locales
        with (dataDir/'interet/poids.csv').open('r') as r:
            reader = csv.reader(r)
            next(reader, None)
            poidsInteret = {rows[0]:int(rows[1]) for rows in reader}

        coef = {}
        with (project/'coefficients_interet.csv').open('w') as w:
            for key in poidsInteret:
                coef[key] = poidsInteret[key] / sum(poidsInteret.values())
                w.write(key + ', ' + str(coef[key]) + '\n')

        # Enregistrements des poids pour le tirage des étages et surface !!! temporairement adapté à Montpellier
        poidsEtages = {}
        for i in range(160):
            poidsEtages[i+1] = {}
        with (dataDir/'poids_etages.csv').open('r') as r:
            r.readline()
            for l in r.readlines():
                values = l.split(',')
                id = int(values[1].replace('"',''))
                etages = int(values[2].replace('"',''))
                # AIC=[4] ; Chi²=[5]
                poidsEtages[id][etages] = float(values[4])

        poidsSurfaces = {}
        for i in range(160):
            poidsSurfaces[i+1] = {}
        with (dataDir/'poids_surfaces.csv').open('r') as r:
            r.readline()
            for l in r.readlines():
                values = l.split(',')
                id = int(values[6].replace('"','').replace('\n',''))
                surf = int(values[1].replace('"',''))
                # AD=[2] ; CVM=[3] ; KS=[4] ; AIC=[5] ;
                poidsSurfaces[id][surf] = float(values[5])

        poidsEtagesNoFit = {}
        for i in range(160):
            poidsEtagesNoFit[i+1] = {}
        with (dataDir/'poids_etages_nofit.csv').open('r') as r:
            r.readline()
            for l in r.readlines():
                values = l.split(',')
                id = int(values[0])
                etages = int(values[1])
                poidsEtagesNoFit[id][etages] = float(values[3])

        poidsSurfacesNoFit = {}
        for i in range(160):
            poidsSurfacesNoFit[i+1] = {}
        with (dataDir/'poids_surfaces_nofit.csv').open('r') as r:
            r.readline()
            for l in r.readlines():
                values = l.split(',')
                id = int(values[0])
                surf = int(values[1])
                poidsSurfacesNoFit[id][surf] = float(values[3])

        # Préparation des restrictions et gestion du PLU
        restriction = to_array(dataDir/'interet/restriction_totale.tif')
        if (dataDir/'interet/plu_restriction.tif').exists() and (dataDir/'interet/plu_priorite.tif').exists():
            skipZau = False
            pluPrio = to_array(dataDir/'interet/plu_priorite.tif')
            pluRest = to_array(dataDir/'interet/plu_restriction.tif')
            restrictionNonPlu = restriction.copy()
            restriction = np.where(pluRest != 1, restriction, 1)
        else:
            skipZau = True
            pluPriority = False

        # Déclaration des matrices
        demographie14 = to_array(dataDir/'demographie.tif', np.uint16)
        srfSol14 = to_array(dataDir/'srf_sol.tif', np.uint16)
        srfSolRes14 = to_array(dataDir/'srf_sol_res.tif', np.uint16)
        ssrMed = to_array(dataDir/'iris_ssr_med.tif', np.uint16)
        m2PlaHab = to_array(dataDir/'iris_m2_hab.tif', np.uint16)
        srfPla14 = to_array(dataDir/'srf_pla.tif', np.uint32)
        nbNivMax = to_array(dataDir/'iris_nbniv_max.tif')
        if buildNonRes:
            txSsr = to_array(dataDir/'iris_tx_ssr.tif', np.float32)
        # Amenités
        eco = to_array(dataDir/'interet/non-importance_ecologique.tif', np.float32)
        rou = to_array(dataDir/'interet/proximite_routes.tif', np.float32)
        tra = to_array(dataDir/'interet/proximite_transport.tif', np.float32)
        sir = to_array(dataDir/'interet/densite_sirene.tif', np.float32)
        # Création du raster final d'intérêt avec pondération
        interet = np.where((restriction != 1), (eco * coef['ecologie']) + (rou * coef['routes']) + (tra * coef['transport']) + (sir * coef['sirene']), 0)
        interet = (interet / np.amax(interet)).astype(np.float32)

        # Création des rasters de capacité en surfaces sol et plancher
        capaSol = np.zeros([rows, cols], np.uint32) + srfCell
        capaSol = np.where((restriction != 1) & (srfSol14 < capaSol), capaSol - srfSol14, 0).astype(np.uint16)
        # Statistiques sur l'évolution du bâti
        urb14 = np.where(srfSol14 > 0, 1, 0).astype(np.byte)
        srfSolNonRes = srfSol14 - srfSolRes14
        ratioPlaSol14 = np.where(srfSol14 != 0, srfPla14 / srfSol14, 0).astype(np.float32)
        txArtif = (srfSol14 / srfCell).astype(np.float32)

        # Création du dictionnaire pour nombre de m2 ouverts à l'urbanisation par année
        with (dataDir/'evo_surface_sol.csv').open('r') as r:
            reader = csv.reader(r)
            next(reader, None)
            dicSsol = {rows[0]:int(rows[1]) for rows in reader}

        m2SolHab09 = dicSsol['2009'] / pop09
        m2SolHab14 = dicSsol['2014'] / pop14
        m2SolHabEvo = (m2SolHab14 - m2SolHab09) / m2SolHab09 / 5

        dicSrf = {}
        year = 2015
        if scenario == 'tendanciel':
            srfMax = m2SolHab14
            while year <= finalYear :
                srfMax += srfMax * m2SolHabEvo
                dicSrf[year] = int(round(srfMax) * popDic[year])
                year += 1
        elif scenario == 'stable':
            srfMax = m2SolHab14
            while year <= finalYear :
                dicSrf[year] = int(round(srfMax) * popDic[year])
                year += 1
        elif scenario == 'reduction':
            srfMax = m2SolHab14
            totalYears = finalYear - year
            while year <= finalYear :
                dicSrf[year] = int(round(srfMax) * popDic[year])
                srfMax -= m2SolHab14 * (0.75 / totalYears)
                year += 1

        log.write('Area consumption per person in 2014: ' + str(int(round(m2SolHab14))) + ' m2\n')
        log.write('Average annual evolution of area consumption per person: ' + str(round(m2SolHabEvo * 100, 4)) + ' %\n')
        log.write('Computed threshold for area consumption per person: ' + str(int(round(srfMax))) + ' m2\n')

        # Instantanés de la situation à t0
        if writingTifs:
            to_tif(urb14, 'byte', proj, geot, project/'urbanisation.tif')
            to_tif(capaSol, 'uint16', proj, geot, project/'capacite_sol.tif')
            to_tif(txArtif, 'float32', proj, geot, project/'taux_artif.tif')
            to_tif(interet, 'float32', proj, geot, project/'interet.tif')
            to_tif(ratioPlaSol14, 'float32', proj, geot, project/'ratio_plancher_sol.tif')

        start_time = time()
        ##### Boucle principale #####
        countChoices = 0
        demographie = demographie14.copy()
        srfSol = srfSol14.copy()
        srfSolRes = srfSolRes14.copy()
        srfPla = srfPla14.copy()
        urb = urb14.copy()
        preBuilt = 0
        nonBuilt = 0
        preLogee = 0
        nonLogee = 0
        for year in range(2015, finalYear + 1):
            progres = "Year %i/%i" %(year, finalYear)
            printer(progres)
            srfMax = dicSrf[year]
            popALoger = popDic[year]
            if pluPriority and not skipZau:
                restePop, resteSrf = urbanize(popALoger - preLogee, srfMax - preBuilt,  True)
                if restePop > 0 and resteSrf > 0:
                    skipZau = True
                    restePop, resteSrf = urbanize(restePop, resteSrf, False)
                if restePop > 0 :
                    restePop, _ = urbanize(restePop)
            else:
                restePop, resteSrf = urbanize(popALoger - preLogee, srfMax - preBuilt)
                if restePop > 0 :
                    restePop, _ = urbanize(restePop)
            preBuilt = -resteSrf
            preLogee = -restePop

            # Snapshots
            if writingTifs and writingSnapshots:
                to_tif(demographie, 'uint16', proj, geot, project/('snapshots/demographie/demo_' + str(year) + '.tif'))
                to_tif(urb, 'byte', proj, geot, project/('snapshots/urbanisation/urb_' + str(year) + '.tif'))
                to_tif(srfSol, 'uint16', proj, geot, project/('snapshots/surface_sol/sol_' + str(year) + '.tif'))
                to_tif(srfPla, 'uint32', proj, geot, project/('snapshots/surface_plancher/plancher_' + str(year) + '.tif'))

        if restePop > 0:
            nonLogee = int(round(restePop))
        if resteSrf > 0:
            nonBuilt = int(round(resteSrf))

        end_time = time()
        execTime = round(end_time - start_time, 2)
        print('\nDuration of the simulation: ' + str(execTime) + ' seconds')

        # Calcul et export des résultats
        popNouv = demographie - demographie14
        popNouvCount = popNouv.sum()
        peuplementMoyen = round(np.nanmean(np.where(popNouv == 0, np.nan, popNouv)), 3)
        srfSolNouv = srfSol - srfSol14
        srfPlaNouv = srfPla - srfPla14
        txArtifNouv = (srfSolNouv / srfCell).astype(np.float32)
        txArtifMoyen = round(np.nanmean(np.where(txArtifNouv == 0, np.nan, txArtifNouv)) * 100, 3)
        ratioPlaSol = np.where(srfSol != 0, srfPla / srfSol, 0).astype(np.float32)
        expansion = np.where((urb14 == 0) & (urb == 1), 1, 0)
        expansionSum = expansion.sum()
        impactEnv = round((srfSolNouv * (1 - eco)).sum())
        if writingTifs :
            to_tif(urb, 'uint16', proj, geot, project/('output/urbanisation_' + str(finalYear) + '.tif'))
            to_tif(srfSol, 'uint16', proj, geot, project/('output/surface_sol_' + str(finalYear) + '.tif'))
            to_tif(srfPla, 'uint32', proj, geot, project/('output/surface_plancher_' + str(finalYear) + '.tif'))
            to_tif(demographie, 'uint16', proj, geot, project/('output/demographie_' + str(finalYear) + '.tif'))
            to_tif(ratioPlaSol, 'float32', proj, geot, project/('output/ratio_plancher_sol_' + str(finalYear) + '.tif'))
            to_tif(txArtifNouv, 'float32', proj, geot, project/('output/taux_artif_' + str(finalYear) + '.tif'))
            to_tif(expansion, 'byte', proj, geot, project/'output/expansion.tif')
            to_tif(srfSolNouv, 'uint16', proj, geot, project/'output/surface_sol_construite.tif')
            to_tif(srfPlaNouv, 'uint32', proj, geot, project/'output/surface_plancher_construite.tif')
            to_tif(popNouv, 'uint16', proj, geot, project/'output/population_nouvelle.tif')

        ocs = to_array(dataDir/'classes_ocsol.tif', np.float32)
        with (project/'output/conso_ocs.csv').open('w') as w:
            w.write('classe, surface\n')
            for c in np.unique(ocs):
                if int(c) != 0:
                    w.write(str(int(c)) +', ' + str( ((ocs == c) * srfSolNouv).sum()) + '\n')

        mesures.write("Population not put up, " + str(nonLogee) + '\n')
        mesures.write("Unbuilt area, " + str(nonBuilt) + '\n')
        mesures.write("Average cell populating, " + str(peuplementMoyen) + "\n")
        mesures.write("Area expansion, " + str(srfSolNouv.sum()) + "\n")
        mesures.write("Built floor area, " + str(srfPlaNouv.sum()) + "\n")
        mesures.write("Cells open to urbanisation, " + str(expansion.sum()) + "\n")
        mesures.write("Average artificialisation rate, " + str(txArtifMoyen) + "\n")
        mesures.write("Cumulated environnemental impact, " + str(int(impactEnv)) + "\n")
        #print("Cumulated environnemental impact = " + str(int(impactEnv)) + "\n")
        log.write("Unbuilt area: " + str(nonBuilt) + '\n')
        log.write("Population not put up: " + str(nonLogee) + '\n')
        log.write("Population put up: " + str(popNouvCount) + '\n')
        log.write("Final demography: " + str(demographie.sum()) + '\n')
        log.write("Total number of randomly chosen cells: " + str(countChoices) + '\n')
        log.write("Execution time: " + str(execTime) + '\n')

        if densifyGround:
            densifSol = np.where((srfSol > srfSol14) & (srfSolRes14 > 0), 1, 0)
            if writingTifs:
                to_tif(densifSol, 'byte', proj, geot, project/'output/densification_sol.tif')
            mesures.write("Ground-densified cells count, " + str(densifSol.sum()) + "\n")
        else:
            mesures.write("Ground-densified cells count, NA\n")

        if densifyOld:
            densifPla = np.where((srfPla > srfPla14) & (srfSolRes14 > 0), 1, 0)
            if writingTifs:
                to_tif(densifPla, 'byte', proj, geot, project/'output/densification_plancher.tif')
            mesures.write("Floor-densified cells count, " + str(densifPla.sum()) + "\n")
        else:
            mesures.write("Floor-densified cells count, NA\n")

    except:
        print("\n*** Error :")
        exc = sys.exc_info()
        traceback.print_exception(*exc, limit=5, file=sys.stdout)
        traceback.print_exception(*exc, limit=5, file=log)
        sys.exit()
