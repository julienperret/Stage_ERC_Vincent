#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import csv
import gdal
import traceback
import numpy as np
from time import time, strftime
from pathlib import Path
from shutil import rmtree
from ast import literal_eval
from toolbox import to_tif, printer, to_array

# Ignorer les erreurs de numpy lors d'une division par 0
np.seterr(divide='ignore', invalid='ignore')

# Stockage et contrôle de la validité des arguments passés au script
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
        elif 'pluPriority' in arg:
            pluPriority = literal_eval(arg.split('=')[1])
        elif 'buildNonRes' in arg:
            buildNonRes = literal_eval(arg.split('=')[1])
        elif 'densifyOld' in arg:
            densifyOld = literal_eval(arg.split('=')[1])
        elif 'forceEachYear' in arg:
            forceEachYear = literal_eval(arg.split('=')[1])
        elif 'maxBuiltRatio' in arg:
            maxBuiltRatio = int(arg.split('=')[1])
        elif 'exclusionRatio' in arg:
            exclusionRatio = float(arg.split('=')[1])
        elif 'maxUsedSrfPla' in arg:
            maxUsedSrfPla = int(arg.split('=')[1])
        elif 'winSize' in arg:
            winSize = int(arg.split('=')[1])
        elif 'minContig' in arg:
            minContig = float(arg.split('=')[1])
        elif 'maxContig' in arg:
            maxContig = float(arg.split('=')[1])
        elif 'tiffs' in arg:
            tiffs = True
        elif 'snaps' in arg:
            snaps = True
        elif 'verboose' in arg:
            verboose = True
        elif 'finalYear' in arg:
            finalYear = int(arg.split('=')[1])

########### Paramètres pour openMole
elif len(sys.argv) > 5:
    scenario = float(sys.argv[4])
    if (scenario >=0) & (scenario < 1) :
        tmpscenario = "tendanciel"
    if (scenario >= 1) & (scenario < 2) :
        tmpscenario = "stable"
    if (scenario >= 2) & (scenario <= 3) :
        tmpscenario = "reduction"
    scenario = tmpscenario

    def to_bool(r):
        b = True if r > 0.5 else False
        return b

    pluPriority = to_bool(float(sys.argv[5]))
    buildNonRes = to_bool(float(sys.argv[6]))
    #densifyGround = to_bool(float(sys.argv[7]))
    maxBuiltRatio = float(sys.argv[8])
    densifyOld = to_bool(float(sys.argv[9]))
    maximumDensity = to_bool(float(sys.argv[10]))
    winSize = round(float(sys.argv[11]))
    minContig = float(sys.argv[12])
    maxContig = float(sys.argv[13])
    writingTifs = to_bool(float(sys.argv[14]))
    seed = round(float(sys.argv[15]))
    sirene =  round(float(sys.argv[16]))
    transport =  round(float(sys.argv[17]))
    routes =  round(float(sys.argv[18]))
    ecologie =  round(float(sys.argv[19]))

### Valeurs de paramètres par défaut ###
if 'finalYear' not in globals():
    finalYear = 2040
# Scénarios concernants l'étalement : tendanciel, stable, reduction
if 'scenario' not in globals():
    scenario = 'tendanciel'
# Priorité aux ZAU
if 'pluPriority' not in globals():
    pluPriority = True
# Pour seuiller l'artificialisation d'une cellule dans le raster de capacité au sol
if 'maxBuiltRatio' not in globals():
    maxBuiltRatio = 80
# Taux pour exclure de la couche d'intérêt les cellules déjà artificialisées
if 'exclusionRatio' not in globals():
    exclusionRatio = 0.5
# Pour seuiller le nombre de mêtres carrés utilisés par habitants et par iris
if 'maxUsedSrfPla' not in globals():
    maxUsedSrfPla = 200
# Pour simuler également la construction des surfaces non résidentielles
if 'buildNonRes' not in globals():
    buildNonRes = True
if 'forceEachYear' not in globals():
    forceEachYear = True
# Pour autoriser à densifier la surface plancher pré-éxistante
if 'densifyOld' not in globals():
    densifyOld = False
# Paramètres pour les règles de contiguïtés """fractales""" -_-
if 'winSize' not in globals():
    winSize = 3
if 'minContig' not in globals():
    minContig = 0.1
if 'maxContig' not in globals():
    maxContig = 0.8
if 'tiffs' not in globals():
    tiffs = True
if 'snaps' not in globals():
    snaps = False
if 'verboose' not in globals():
    verboose = False

# Contrôle de la validité des paramètres
if growth > 3:
    print("Maximum evolution rate fixed at: 3 %")
    sys.exit()
if maxContig > 1 or minContig > 1:
    print("Error : minContig and maxContig should be float numbers < 1 !")
    sys.exit()
if minContig > maxContig:
    print("Error : maxContig should be higher than minContig !")
    sys.exit()

def parseDistrib(file, type=None, fit=True):
    poids = {}
    for i in range(nbIris):
        poids[i+1] = {}
    file.readline()
    for l in file.readlines():
        values = l.split(',')
        if fit:
            if type == 'floors':
                id = int(values[1].replace('"',''))
                etages = int(values[2].replace('"',''))
                # AIC=[4] ; Chi²=[5]
                poids[id][etages] = float(values[5].replace('\n','')) if 'NA' not in values[5] else 0
            elif type == 'surf':
                id = int(values[6].replace('"','').replace('\n',''))
                surf = float(values[1])
                # AD=[2] ; CVM=[3] ; KS=[4] ; AIC=[5] ;
                poids[id][surf] = float(values[4])
        else:
            id = int(values[0])
            dist = int(values[1])
            poids[id][dist] = float(values[3])
    return poids

# Tirage pondéré qui retourne un tuple d'index (row, col)
def chooseCell(weight):
    global heatMap
    i = 0
    cells = (0, 0)
    if weight.sum() > 0:
        flatWeight = weight.flatten()
        choices = np.random.choice(flatWeight.size, 1, p=flatWeight / flatWeight.sum())
        row = choices[i] // weight.shape[1]
        col = choices[i] % weight.shape[1]
        if row > 0 and col > 0:
            cells  = (row, col)
            heatMap[row][col] += 1
        elif verboose:
                print("Error : can't choose a cell with those weights.")
    elif verboose:
            print("Error : it seems like interest raster sums to 0.")
    return cells

def chooseArea(id, row, col):
    ss = 0
    surf = np.array(list(poidsSurfaces[id].keys()))
    pds = np.array(list(poidsSurfaces[id].values()))
    if len(surf) > 0 and sum(pds) > 0 :
        c = np.random.choice(surf, 1, p=pds/pds.sum())
        if c[0] > 0:
            ss = float(c[0])
    else:
        surf = np.array(list(poidsSurfacesNoFit[id].keys()))
        pds = np.array(list(poidsSurfacesNoFit[id].values()))
        if len(surf) > 0 and sum(pds) > 0 :
            c = np.random.choice(surf, 1, p=pds/pds.sum())
            if c[0] > 0:
                ss = float(c[0])
    return ss

def chooseFloors(id, row, col):
    nbNiv = 0
    etages = np.array(list(poidsEtages[id].keys()))
    pds = np.array(list(poidsEtages[id].values()))
    if len(etages) > 0 and sum(pds) > 0:
        c = np.random.choice(etages, 1, p=pds/pds.sum())
        nbNiv = c[0]
    else:
        etages = np.array(list(poidsEtagesNoFit[id].keys()))
        pds = np.array(list(poidsEtagesNoFit[id].values()))
        if len(etages) > 0 and sum(pds) > 0:
            c = np.random.choice(etages, 1, p=pds/pds.sum())
            nbNiv = c[0]
    return nbNiv

# Fenêtre glissante pour statistique dans le voisinage d'un pixel
def winMean(array, row, col, size=3):
    value = None
    if (row >= size//2 and row + size//2 < rows) and (col >= size//2 and col + size//2 < cols):
        s = 0
        pos = [i + 1 for i in range(-size//2, size//2)]
        for r in pos:
            for c in pos:
                s += array[row + r][col + c]
        value = s / (size * size)
    return value

# Artificialisation d'une surface cellule vide ou déjà urbanisée (dans ce cas on ne vérifie pas la contiguité)
def expand(row, col, new=True):
    ss = 0
    id = irisId[row][col]
    if new:
        contig = winMean(urb, row, col, winSize)
        if contig and minContig < contig <= maxContig:
            ss = chooseArea(id, row, col)
            if ss > 0:
                maxSrf = capaSol[row][col]
                if ss > maxSrf :
                    ss = maxSrf
    else:
        maxSrf = capaSol[row][col]
        ss = chooseArea(id, row, col)
        if ss > 0:
            if ss > maxSrf :
                ss = maxSrf
    return ss

# Pour urbaniser ou densifier verticalement une surface au sol donnée à partir du fitting "floors"
def build(row, col, ss=None):
    sp = 0
    nbNiv = 0
    id = irisId[row][col]
    if type(ss) == np.float64:
        nbNiv = chooseFloors(id, row, col)
        if nbNiv > 0:
            sp = ss * nbNiv
    elif ss == 'reshape':
        etages = np.array(list(poidsEtages[id].keys()))
        ssol = srfSolRes[row][col]
        spla = srfPla[row][col]
        nivMoy = float(spla / ssol) if ssol != 0 else 0
        nivMax = int(etages.max()) if len(etages) > 0 else 0
        if int(nivMax) > round(nivMoy) :
            # On cherche à tirer un nombre d'étage spérieur à l'existant
            nbNiv = chooseFloors(id, row, col)
            if nbNiv > nivMoy:
                sp = ssol * nbNiv
                # On enlève l'existant pour connaîte la surface nouvelle
                if sp > srfPla[row][col]:
                    sp -= srfPla[row][col]
                    # On vérifie que la surface finale suffit à loger au moins une personne
                    if sp < m2PlaHab[row][col]:
                        sp = 0
                else:
                    sp = 0
    return sp

# Fonction principale pour gérer artificialisation puis densification
def urbanize(pop, srfMax, zau=False):
    if verboose:
        print('\n')
    global demographie, capaSol, srfSol, srfSolRes, srfSolNonRes, srfPla, urb, skipZau, skipZauYear

    artif = 0
    count = 0
    tmpUrb = np.zeros([rows, cols], np.byte)
    tmpSrfPla = np.zeros([rows, cols], np.uint16)
    tmpSrfSol = np.zeros([rows, cols], np.uint16)
    tmpInteret = np.where(capaSol > 0, interet, 0)
    if zau:
        # On limite l'urbanisation aux ZAU (if pluPriority)
        tmpInteret = np.where(pluPrio == 1, tmpInteret, 0)
    # Expansion par ouverture de nouvelles cellules ou densification au sol de cellules déja urbanisées
    while artif < srfMax and count < pop and tmpInteret.sum() > 0:
        # Tant qu'il reste des gens à loger et de la surface à construire
        ss = 0
        sp = 0
        row, col = chooseCell(tmpInteret)
        if row > 0 and col > 0:
            if capaSol[row][col] > 0:
                if urb[row][col] == 0 and tmpUrb[row][col] == 0:
                    # Pour ouvrir une nouvelle cellule à l'urbanisation
                    ss = expand(row, col)
                else:
                    # Sinon on construit à côté d'autres bâtiments
                    ss = expand(row, col, new=False)
                if ss > 0 :
                    # Les fonctions retournent 0 si quelque chose empêche d'urbaniser la cellule
                    if buildNonRes:
                        # On réduit la surface construite à une part de résidentiel avant de calculer la surface plancher
                        ssr = ss * txSsr[row][col] if txSsr[row][col] > 0 else ss
                        ssnr = ss - ssr
                        sp = build(row, col, ssr)
                    else:
                        sp = build(row, col, ss)
                    if sp > 0:
                        # On met à jour les rasters uniquement si on la construction sol et plancher s'est déroulée correctement
                        tmpUrb[row][col] = 1
                        capaSol[row][col] -= ss
                        tmpSrfSol[row][col] += ss
                        tmpSrfPla[row][col] += sp
                        count = np.where(m2PlaHab != 0, (tmpSrfPla / m2PlaHab).round(), 0).astype(np.uint16).sum()
                        artif += ss
                    # Sinon on ajuste l'intérêt à 0 pour que la cellule ne soit plus tirée (pour l'année en cours)
                    else:
                        tmpInteret[row][col] = 0
                else:
                    tmpInteret[row][col] = 0
            else:
                tmpInteret[row][col] = 0
        else:
            tmpInteret[row][col] = 0

    if tmpInteret.sum() == 0 and zau:
        skipZau = True
        skipZauYear = year
        if verboose:
                print("pluPriority : interest sum == 0 ; skipping ZAU from now on.")

    if count < pop and (forceEachYear or (densifyOld and year == finalYear)):
        ignoredCells = 0
        chosenCells = 0
        # Densification du bâti existant en fin de simu si on n'a pas pu loger tout le monde
        if year == finalYear and densifyOld:
            srfMax = 0
            tmpInteret = np.where(srfSolRes14 > 0, interet, 0)
            if verboose:
                    print("densifyOld : trying to densify old buildings because " + str(int(pop - count)) + " peoples are still homeless.")
        elif forceEachYear and (artif >= srfMax or tmpInteret.sum() == 0):
            # Ici on force à densifier l'existant en hauteur pour loger tout le monde (à chaque itération)
            if verboose:
                    print("forceEachYear : trying to densify and get " + str(int(pop-count)) + " people under a roof.")
            if tmpUrb.sum() > 0:
                tmpInteret = np.where((tmpUrb == 1) & (srfSolRes > 0), interet, 0)
            else:
                tmpInteret = np.zeros([rows, cols], np.byte)
        else:
            tmpInteret = np.zeros([rows, cols], np.byte)

        choosableCells = (np.where(tmpInteret > 0, 1, 0)).sum()
        if verboose:
            print(str(choosableCells) + ' available cells for the densification process...')
        # On tente de loger les personnes restantes

        while count < pop and tmpInteret.sum() > 0:
            sp = 0
            row, col = chooseCell(tmpInteret)
            sp = build(row, col, 'reshape')
            if sp > 0:
                chosenCells += 1
                tmpSrfPla[row][col] += sp
                count = np.where(m2PlaHab != 0, (tmpSrfPla / m2PlaHab).round(), 0).astype(np.uint16).sum()
            else:
                tmpInteret[row][col] = 0

        if verboose:
            print(str(chosenCells) + " cells were successfully rebuilt.")

    # Mise à jour des variables globales
    urb = np.where(tmpUrb == 1, 1, urb)
    srfSol += tmpSrfSol
    if buildNonRes:
        tmpSrfSol = (tmpSrfSol * txSsr).round().astype(np.uint16)
    srfSolRes += tmpSrfSol
    srfPla += tmpSrfPla
    demographie += np.where(m2PlaHab != 0, (tmpSrfPla / m2PlaHab).round(), 0).astype(np.uint16)
    # Retourne le trop ou le manque pour itération suivante
    return (pop - count, srfMax - artif)

# Création des variables GDAL pour écriture de raster, indispensables pour la fonction to_tif()
ds = gdal.Open(str(dataDir/'iris_id.tif'))
irisId = ds.GetRasterBand(1).ReadAsArray().astype(np.uint8)
cols, rows = irisId.shape[1], irisId.shape[0] # x, y
proj = ds.GetProjection()
geot = ds.GetGeoTransform()
pixSize = int(geot[1])
srfCell = pixSize * pixSize
nbIris = int(irisId.max())
ds = None

projectStr = '%im_tx%s_%s_winSize%i_minContig%s_maxContig%s_maxBuiltRatio%i_exclusionRatio%s'%(pixSize, str(growth), scenario, winSize, str(minContig), str(maxContig), maxBuiltRatio, str(exclusionRatio))
if pluPriority:
    projectStr += '_pluPrio'
# if buildNonRes:
#     projectStr += '_buildNonRes'
if forceEachYear:
    projectStr += '_forceEachYear'
# if densifyOld:
#     projectStr += '_densifyOld'
if finalYear != 2040:
    projectStr += '_' + str(finalYear)
project = outputDir/projectStr

if project.exists():
    rmtree(str(project))
os.makedirs(str(project/'output'))

if tiffs and snaps:
    mkdirList = [
        'snapshots',
        'snapshots/demographie',
        'snapshots/urbanisation',
        'snapshots/surface_sol',
        'snapshots/surface_plancher'
    ]
    for d in mkdirList:
        dir = project/d
        os.mkdir(str(dir))

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

        sumPopALoger = sum(popDic.values())

        # Statistiques sur l'évolution du bâti
        with (dataDir/'evo_surface_sol.csv').open('r') as r:
            reader = csv.reader(r)
            next(reader, None)
            dicSsol = {rows[0]:int(rows[1]) for rows in reader}
        m2SolHab09 = dicSsol['2009'] / pop09
        m2SolHab14 = dicSsol['2014'] / pop14
        m2SolHabEvo = (m2SolHab14 - m2SolHab09) / m2SolHab09 / 5

        # Création du dictionnaire pour nombre de m2 ouverts à l'urbanisation par année, selon le scénario
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

        log.write("Population to put up until " + str(finalYear) + " : " + str(sumPopALoger) + "\n")
        log.write('Area consumption per person in 2014: ' + str(int(round(m2SolHab14))) + ' m2\n')
        log.write('Average annual evolution of area consumption per person: ' + str(round(m2SolHabEvo * 100, 4)) + ' %\n')
        log.write('Computed threshold for area consumption per person: ' + str(int(round(srfMax))) + ' m2\n')
        if verboose:
            print(("\nPopulation to put up until " + str(finalYear) + " : " + str(sumPopALoger)))
            print(('Computed threshold for area consumption per person: ' + str(int(round(srfMax))) + ' m2'))

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

        # Enregistrements des poids pour le tirage des étages et surface
        with (dataDir/'poids_etages.csv').open('r') as r:
            poidsEtages = parseDistrib(r, 'floors')
        with (dataDir/'poids_surfaces.csv').open('r') as r:
            poidsSurfaces = parseDistrib(r, 'surf')
        with (dataDir/'poids_etages_nofit.csv').open('r') as r:
            poidsEtagesNoFit = parseDistrib(r, fit = False)
        with (dataDir/'poids_surfaces_nofit.csv').open('r') as r:
            poidsSurfacesNoFit = parseDistrib(r, fit=False)

        # Préparation des restrictions et gestion du PLU
        restriction = to_array(dataDir/'interet/restriction_totale.tif')
        if (dataDir/'interet/plu_restriction.tif').exists() and (dataDir/'interet/plu_priorite.tif').exists():
            skipZau = False
            pluPrio = to_array(dataDir/'interet/plu_priorite.tif')
            pluRest = to_array(dataDir/'interet/plu_restriction.tif')
            restrictionNonPlu = restriction.copy()
            restriction = np.where(pluRest == 1, 1, restriction)
        else:
            skipZau = True
            pluPriority = False

        # Déclaration des matrices
        heatMap = np.zeros([rows, cols], np.uint16)
        demographie14 = to_array(dataDir/'demographie.tif', np.uint16)
        srfSol14 = to_array(dataDir/'srf_sol.tif', np.uint16)
        srfSolRes14 = to_array(dataDir/'srf_sol_res.tif', np.uint16)
        ssrMed = to_array(dataDir/'iris_ssr_med.tif', np.uint16)
        m2PlaHab = to_array(dataDir/'iris_m2_hab.tif', np.uint16)
        m2PlaHab = np.where(m2PlaHab > maxUsedSrfPla, maxUsedSrfPla, m2PlaHab)
        srfPla14 = to_array(dataDir/'srf_pla.tif', np.uint16)
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

        srfSolNonRes14 = srfSol14 - srfSolRes14
        # Création des rasters de capacité en surfaces sol et plancher
        capaSol = np.zeros([rows, cols], np.uint16) + srfCell * maxBuiltRatio / 100
        capaSol = np.where((restriction != 1) & (srfSol14 < capaSol), capaSol - srfSol14, 0).astype(np.uint16)
        totalCapacity = int(np.where(capaSol > 0, 1, 0).sum())
        # Cellules urbanisées (tout bâti inclu)
        urb14 = np.where(srfSol14 > 0, 1, 0).astype(np.byte)
        txArtif = (srfSol14 / srfCell).astype(np.float32)
        # Nombre moyen d'étages dans la cellule
        ratioPlaSol14 = np.where(srfSol14 != 0, srfPla14 / srfSol14, 0).astype(np.float32)
        # On filtre les cellules d'intéret pour limiter les tirages inutiles
        interet = np.where(txArtif <= exclusionRatio, interet, 0)
        interet = np.where(m2PlaHab > 0, interet, 0)

        # Instantanés de la situation à t0
        if tiffs:
            to_tif(srfSolNonRes14, 'uint16', proj, geot, project/'surface_sol_non_residentielle.tif')
            to_tif(urb14, 'byte', proj, geot, project/'urbanisation.tif')
            to_tif(capaSol, 'uint16', proj, geot, project/'capacite_sol.tif')
            to_tif(txArtif, 'float32', proj, geot, project/'taux_artif.tif')
            to_tif(interet, 'float32', proj, geot, project/'interet.tif')
            to_tif(ratioPlaSol14, 'float32', proj, geot, project/'ratio_plancher_sol.tif')

        # Début de la simulation
        start_time = time()
        preLog = 0
        preBuilt = 0
        skipZauYear = None
        urb = urb14.copy()
        srfSol = srfSol14.copy()
        srfPla = srfPla14.copy()
        srfSolRes = srfSolRes14.copy()
        demographie = demographie14.copy()
        # Boucle principale pour itération annuelle
        for year in range(2015, finalYear + 1):
            if verboose:
                print('\n\n')
            progres = "Year %i/%i" %(year, finalYear)
            printer(progres)
            srfMax = dicSrf[year]
            popALoger = popDic[year]
            restePop, resteSrf = urbanize(popALoger - preLog, srfMax - preBuilt, zau=not skipZau)
            preBuilt = -resteSrf
            preLog = -restePop

            if verboose:
                print('Remaining population : '  + str(restePop))
                print('Remaining surface to build : ' + str(resteSrf))

            # Snapshots
            if tiffs and snaps:
                to_tif(demographie, 'uint16', proj, geot, project/('snapshots/demographie/demo_' + str(year) + '.tif'))
                to_tif(urb, 'byte', proj, geot, project/('snapshots/urbanisation/urb_' + str(year) + '.tif'))
                to_tif(srfSol, 'uint16', proj, geot, project/('snapshots/surface_sol/sol_' + str(year) + '.tif'))
                to_tif(srfPla, 'uint16', proj, geot, project/('snapshots/surface_plancher/plancher_' + str(year) + '.tif'))

        resteSrf = str(int(round(resteSrf if resteSrf > 0 else 0)))
        restePop = str(int(round(restePop if restePop > 0 else 0)))

        end_time = time()
        execTime = round(end_time - start_time, 2)
        print('\nDuration of the simulation: ' + str(execTime) + ' seconds')

        # Calcul et export des résultats
        popNouv = demographie - demographie14
        peuplementMoyen = round(np.nanmean(np.where(popNouv == 0, np.nan, popNouv)), 3)
        ratioPlaSol = np.where(srfSol != 0, srfPla / srfSol, 0).astype(np.float32)
        srfSolNouv = srfSol - srfSol14
        srfPlaNouv = srfPla - srfPla14
        densifSol = np.where((srfSol > srfSol14) & (urb14 == 1), 1, 0)
        densifPla = np.where((srfPla > srfPla14) & (urb14 == 1), 1, 0)
        txArtifNouv = (srfSolNouv / srfCell).astype(np.float32)
        txArtifMoyen = round(np.nanmean(np.where(txArtifNouv == 0, np.nan, txArtifNouv)) * 100, 3)
        txArtifFinal = (srfSol / srfCell).astype(np.float32)
        expansion = np.where((urb14 == 0) & (urb == 1), 1, 0)
        srfSolNonRes = srfSol - srfSolRes
        dsfSol = densifSol.sum() if densifSol.sum() > 0 else 'NA'
        dsfPla = densifPla.sum() if densifPla.sum() > 0 else 'NA'
        countChoices = heatMap.sum()
        popNouvCount = popNouv.sum()
        expansionSum = expansion.sum()
        builtCellsRatio = expansionSum / totalCapacity
        impactEnv = round((srfSolNouv * (1 - eco)).sum() * builtCellsRatio)
        if tiffs :
            to_tif(heatMap, 'byte', proj, geot, project/'output/choices_heatmap.tif')
            to_tif(urb, 'uint16', proj, geot, project/('output/urbanisation_' + str(finalYear) + '.tif'))
            to_tif(srfSol, 'uint16', proj, geot, project/('output/surface_sol_' + str(finalYear) + '.tif'))
            to_tif(srfPla, 'uint16', proj, geot, project/('output/surface_plancher_' + str(finalYear) + '.tif'))
            to_tif(demographie, 'uint16', proj, geot, project/('output/demographie_' + str(finalYear) + '.tif'))
            to_tif(ratioPlaSol, 'float32', proj, geot, project/('output/ratio_plancher_sol_' + str(finalYear) + '.tif'))
            to_tif(txArtifFinal, 'float32', proj, geot, project/('output/taux_artif_' + str(finalYear) + '.tif'))
            to_tif(expansion, 'byte', proj, geot, project/'output/expansion.tif')
            to_tif(srfSolNouv, 'uint16', proj, geot, project/'output/surface_sol_construite.tif')
            to_tif(srfPlaNouv, 'uint16', proj, geot, project/'output/surface_plancher_construite.tif')
            to_tif(popNouv, 'uint16', proj, geot, project/'output/population_nouvelle.tif')
            to_tif(srfSolNonRes, 'uint16', proj, geot, project/('surface_sol_non_residentielle_' + str(finalYear) + '.tif'))

        ocs = to_array(dataDir/'classes_ocsol.tif', np.float32)
        with (project/'output/conso_ocs.csv').open('w') as w:
            w.write('classe, surface\n')
            for c in np.unique(ocs):
                if int(c) != 0:
                    w.write(str(int(c)) +', ' + str( ((ocs == c) * srfSolNouv).sum()) + '\n')

        mesures.write("Population not put up, " + restePop + '\n')
        mesures.write("Unbuilt area, " + resteSrf + '\n')
        mesures.write("Average cell populating, " + str(peuplementMoyen) + "\n")
        mesures.write("Area expansion, " + str(srfSolNouv.sum()) + "\n")
        mesures.write("Built floor area, " + str(srfPlaNouv.sum()) + "\n")
        mesures.write("Cells open to urbanisation, " + str(expansionSum) + "\n")
        mesures.write("Average artificialisation rate, " + str(txArtifMoyen) + "\n")
        mesures.write("Cumulated environnemental impact, " + str(int(impactEnv)) + "\n")
        mesures.write("Ground-densified cells count, " + str(dsfSol) + "\n")
        mesures.write("Floor-densified cells count, " + str(dsfPla) + "\n")

        log.write("Unbuilt area: " + restePop + '\n')
        log.write("Population not put up: " + resteSrf + '\n')
        log.write("Population put up: " + str(popNouvCount) + '\n')
        log.write("Final demography: " + str(demographie.sum()) + '\n')
        log.write("ZAU saturation year: " + str(skipZauYear) + '\n')
        log.write("Total number of randomly chosen cells: " + str(countChoices) + '\n')
        log.write("Execution time: " + str(execTime) + '\n')

        if tiffs :
            if exclusionRatio > 0:
                to_tif(densifSol, 'byte', proj, geot, project/'output/densification_sol.tif')
            if densifyOld:
                to_tif(densifPla, 'byte', proj, geot, project/'output/densification_plancher.tif')

    except:
        print("\n*** Error :")
        exc = sys.exc_info()
        traceback.print_exception(*exc, limit=5, file=sys.stdout)
        traceback.print_exception(*exc, limit=5, file=log)
        sys.exit()
