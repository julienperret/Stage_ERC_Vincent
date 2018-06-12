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
from ast import literal_eval
from time import strftime, time
from shutil import rmtree, copyfile

from qgis.core import (
    QgsApplication,
    QgsCoordinateTransform,
    QgsCoordinateTransformContext,
    QgsCoordinateReferenceSystem,
    QgsField,
    QgsFields,
    QgsProcessingFeedback,
    QgsRectangle,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsVectorLayerJoinInfo
)
from qgis.analysis import QgsNativeAlgorithms
from PyQt5.QtCore import QVariant

QgsApplication.setPrefixPath('/usr', True)
qgs = QgsApplication([], GUIenabled=False)
qgs.initQgis()

sys.path.append('/usr/share/qgis/python/plugins')
import processing
from processing.core.Processing import Processing
Processing.initialize()

QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
feedback = QgsProcessingFeedback()

# Ignorer les erreurs de numpy lors d'une division par 0
np.seterr(divide='ignore', invalid='ignore')

# Import des paramètres d'entrée
globalData = slashify(sys.argv[1])
codeDept = sys.argv[2]
localData = slashify(sys.argv[3])
outputDir = slashify(sys.argv[4])
if len(sys.argv) > 5:
    argList = sys.argv[5].split()
    # Interprétation de la chaîne de paramètres
    for arg in argList :
        # Taille de la grille / résolution des rasters
        if 'gridSize' in arg:
            gridSize = arg.split("=")[1]
            if not 200 >= int(gridSize) >= 20:
                error = 'La taille de la grille doit être comprise entre 20m et 200m'
                if not silent:
                    print(error)
                else:
                    log.write('Erreur : ' + error)
                sys.exit()
        # Taille du tampon utilisé pour extraire les iris et pour extraire la donnée utile au delà des limites de la zone (comme les points SIRENE)
        elif 'bufferDistance' in arg:
            bufferDistance = int(arg.split('=')[1])
        # Surfaces au sol minimales et maximales pour considérer un bâtiment comme habité
        elif 'minSurf' in arg:
            minSurf = int(arg.split('=')[1])
        elif 'maxSurf' in arg:
            maxSurf = int(arg.split('=')[1])
        # Utilisation du taux de résidence principales pour réduire la surface plancher estimée
        elif 'useTxrp' in arg:
            useTxrp = literal_eval(arg.split('=')[1])
        # Hauteur théorique d'un étage pour l'estimation du nombre de niveaux
        elif 'levelHeight' in arg:
            levelHeight = int(arg.split('=')[1])
        # Taux maximum de chevauchement entre les cellules et des couches à exclure (ex: bati industriel)
        elif 'maxOverlapRes' in arg:
            maxOverlapRatio = float(arg.split('=')[1])
        # Paramètres variables pour la création des rasters de distance
        elif 'roadDist' in arg:
            roadDist = int(arg.split('=')[1])
        elif 'transDist' in arg:
            transDist = int(arg.split('=')[1])
        # Seuil de pente en % pour interdiction à la construction
        elif 'maxSlope' in arg:
            maxSlope = int(arg.split('=')[1])
        elif 'force' in arg:
            force = True
        elif 'speed' in arg:
            speed = True
        elif 'truth' in arg:
            truth = True
        elif 'silent' in arg:
            silent = True

# Valeurs de paramètres par défaut
if 'gridSize' not in globals():
    gridSize = '50'
if 'bufferDistance' not in globals():
    bufferDistance = 1000
if 'minSurf' not in globals():
    minSurf = 50
if 'maxSurf' not in globals():
    maxSurf = 10000
if 'usrTxrp' not in globals():
    useTxrp = False
if 'levelHeight' not in globals():
    levelHeight = 3
if 'maxOverlapRatio' not in globals():
    maxOverlapRatio = 0.2
if 'roadDist' not in globals():
    roadDist = 200
if 'transDist' not in globals():
    transDist = 300
if 'maxSlope' not in globals():
    maxSlope = 30
if 'force' not in globals():
    force = False
if 'speed' not in globals():
    speed = False
if 'truth' not in globals():
    truth = False
if 'silent' not in globals():
    silent = False

if force and os.path.exists(outputDir):
    rmtree(outputDir)
studyAreaName = localData.split('/')[len(localData.split('/'))-2]

if truth:
    workspacePath = outputDir  + 'tmp/'
    if os.path.exists(workspacePath) :
        rmtree(workspacePath)
    projectPath = outputDir
else:
    workspacePath = outputDir + codeDept + '/' + studyAreaName + '/'
    projectPath = workspacePath + 'simulation/' + gridSize + 'm/'
    if os.path.exists(projectPath):
        rmtree(projectPath)
    os.makedirs(projectPath)
if not os.path.exists(workspacePath):
    os.makedirs(workspacePath)

statBlacklist = ['count', 'unique', 'min', 'max', 'range', 'sum', 'mean',
                 'median', 'stddev', 'minority', 'majority', 'q1', 'q3', 'iqr']

if not silent:
    print('Commencé à ' + strftime('%H:%M:%S'))
log = open(projectPath + strftime('%Y%m%d%H%M') + '_log.txt', 'x')

# Découpe une couche avec gestion de l'encodage pour la BDTOPO
def clip(file, overlay, outdir='memory:'):
    if type(file) == QgsVectorLayer:
        name = file.name()
        params = {
            'INPUT': file,
            'OVERLAY': overlay,
            'OUTPUT': outdir + name
        }
    elif type(file) == str:
        name = os.path.basename(file).split('.')[0].lower()
        layer = QgsVectorLayer(file, name)
        layer.dataProvider().createSpatialIndex()
        if 'bdtopo_2016' in file:
            layer.setProviderEncoding('ISO-8859-14')
        if 'PAI_' in file:
            name = name.replace('pai_', '')
        params = {
            'INPUT': layer,
            'OVERLAY': overlay,
            'OUTPUT': outdir + name
        }
    if outdir != 'memory:':
        params['OUTPUT'] += '.shp'
    res = processing.run('native:clip', params, feedback=feedback)
    return res['OUTPUT']

# Reprojection en laea par défaut
def reproj(file, outdir='memory:', crs='EPSG:3035'):
    if type(file) == QgsVectorLayer:
        name = file.name()
        params = {
            'INPUT': file,
            'TARGET_CRS': crs,
            'OUTPUT': outdir + name
        }
    elif type(file) == str:
        name = os.path.basename(file).split('.')[0].lower()
        layer = QgsVectorLayer(file, name)
        params = {
            'INPUT': layer,
            'TARGET_CRS': crs,
            'OUTPUT': outdir + name
        }
    if outdir != 'memory:':
        params['OUTPUT'] += '.shp'
    res = processing.run('native:reprojectlayer', params, feedback=feedback)
    return res['OUTPUT']

# Réalise une jointure entre deux QgsVectorLayer
def join(layer, field, joinLayer, joinField, blacklist=[], prefix=''):
    j = QgsVectorLayerJoinInfo()
    j.setTargetFieldName(field)
    j.setJoinLayerId(joinLayer.id())
    j.setJoinFieldName(joinField)
    j.setJoinFieldNamesBlackList(blacklist)
    j.setUsingMemoryCache(True)
    j.setPrefix(prefix)
    j.setJoinLayer(joinLayer)
    layer.addJoin(j)

# Enregistre un objet QgsVectorLayer sur le disque
def to_shp(layer, path, blacklist=None):
    writer = QgsVectorFileWriter(path, 'utf-8', layer.fields(), layer.wkbType(), layer.sourceCrs(), 'ESRI Shapefile')
    writer.addFeatures(layer.getFeatures())

# Rasterisation d'un fichier vecteur
def rasterize(vector, output, field=None, burn=None, inverse=False, touch=False):
    gdal.Rasterize(
        output, vector,
        format='GTiff',
        outputSRS='EPSG:3035',
        xRes=int(gridSize),
        yRes=int(gridSize),
        initValues=0,
        burnValues=burn,
        attribute=field,
        allTouched=touch,
        outputBounds=(xMin, yMin, xMax, yMax),
        inverse=inverse
    )

# Nettoye une couche de bâtiments et génère les champs utiles à l'estimation de population
def buildingCleaner(buildings, sMin, sMax, hEtage, polygons, points, cleanedOut, removedOut):
    # Selection des bâtiments situés dans polygones
    for layer in polygons:
        params = {
            'INPUT': buildings,
            'PREDICATE': 6,
            'INTERSECT': layer,
            'METHOD': 1
        }
        processing.run('native:selectbylocation', params, feedback=feedback)
    # Selection si la bâtiment intersecte des points
    for layer in points:
        params = {
            'INPUT': buildings,
            'PREDICATE': 0,
            'INTERSECT': layer,
            'METHOD': 1
        }
        processing.run('native:selectbylocation', params, feedback=feedback)
    # Estimation du nombre d'étages
    expr = """ CASE
        WHEN "HAUTEUR" = 0 THEN 1
        WHEN "HAUTEUR" < 5 THEN 1
        ELSE floor("HAUTEUR"/""" + str(hEtage) + """) END
    """
    buildings.addExpressionField(expr, QgsField('NB_NIV', QVariant.Int, len=2))
    # Nettoyage des bâtiments supposés trop grand ou trop petit pour être habités
    params = {
        'INPUT': buildings,
        'EXPRESSION': ' $area < ' + str(sMin) + ' OR $area > ' + str(sMax),
        'METHOD': 1
    }
    processing.run('qgis:selectbyexpression', params, feedback=feedback)
    params = {
        'INPUT': buildings,
        'OUTPUT': removedOut
    }
    processing.run('native:saveselectedfeatures', params, feedback=feedback)
    # Inversion de la selection pour export final
    buildings.invertSelection()
    params = {
        'INPUT': buildings,
        'OUTPUT': cleanedOut
    }
    res = processing.run('native:saveselectedfeatures', params, feedback=feedback)
    del buildings, polygons, points, layer

# Génère les statistiques de construction entre deux dates pour la grille et les IRIS
def buildCsvGrid(name, path, iris, grid, outCsvDir):
    res = re.search('.*/20([0-9]{2})_bati/.*\.shp', path)
    year = res.group(1)
    hasId = False
    buildings = QgsVectorLayer(path, name)
    buildings.dataProvider().createSpatialIndex()

    for field in buildings.fields():
        if field.name() == 'ID' or field.name() == 'id':
            hasId=True
    if not hasId:
        buildings.addExpressionField('$id', QgsField('ID', QVariant.Int))

    params = {
        'INPUT': buildings,
        'OVERLAY': iris,
        'INPUT_FIELDS': [],
        'OVERLAY_FIELDS': ['CODE_IRIS'],
        'OUTPUT': 'memory:' + name
    }
    res = processing.run('qgis:intersection', params, feedback=feedback)
    buildings = res['OUTPUT']
    buildings.dataProvider().createSpatialIndex()
    params = {
        'INPUT': buildings,
        'OVERLAY': grid,
        'INPUT_FIELDS': [],
        'OVERLAY_FIELDS': ['id'],
        'OUTPUT': 'memory:' + name
    }
    res = processing.run('qgis:intersection', params, feedback=feedback)
    buildings = res['OUTPUT']
    buildings.dataProvider().createSpatialIndex()
    buildings.addExpressionField('$area', QgsField('AIRE', QVariant.Double))
    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'AIRE',
        'CATEGORIES_FIELD_NAME': 'CODE_IRIS',
        'OUTPUT': outCsvDir + year + '_' + name + '_ssol_iris.csv'
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)
    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'AIRE',
        'CATEGORIES_FIELD_NAME': 'id_2',
        'OUTPUT': outCsvDir + year + '_' + name + '_ssol_grid.csv'
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)

# Intersection entre la couche de bâti nettoyée jointe aux iris et la grille avec calcul et jointure des statistiques
def statGridIris(buildings, grid, iris, outdir, csvDir):
    csvGrid = []
    csvIris = []
    grid.dataProvider().createSpatialIndex()
    buildings.dataProvider().createSpatialIndex()
    buildings.addExpressionField('$area', QgsField('area_i', QVariant.Double))
    expr = ' ("area_i" * "NB_NIV") '
    if useTxrp :
        expr +=  '* "TXRP14"'
    buildings.addExpressionField(expr, QgsField('planch', QVariant.Double))
    expr = ' ("planch" / sum("planch", group_by:="CODE_IRIS")) * "POP14" '
    buildings.addExpressionField(expr, QgsField('pop_bati', QVariant.Double))
    params = {
        'INPUT': buildings,
        'OVERLAY': grid,
        'INPUT_FIELDS': ['ID', 'HAUTEUR', 'NB_NIV', 'CODE_IRIS', 'NOM_IRIS', 'TYP_IRIS', 'POP14', 'TXRP14', 'area_i', 'planch', 'pop_bati'],
        'OVERLAY_FIELDS': ['id'],
        'OUTPUT': 'memory:bati_inter_grid'
    }
    res = processing.run('qgis:intersection', params, feedback=feedback)
    buildings = res['OUTPUT']

    # Calcul de stat sur la bâti dans la grille
    buildings.addExpressionField('$area', QgsField('area_g', QVariant.Double))
    expr = 'round("area_g" * "NB_NIV") '
    if useTxrp:
        expr = 'round(("area_g" * "NB_NIV") * "TXRP14")'
    buildings.addExpressionField(expr, QgsField('planch_g', QVariant.Int))
    expr = ' round("area_g" / "area_i" * "pop_bati") '
    buildings.addExpressionField(expr, QgsField('pop_g', QVariant.Int))
    expr = ' round("planch_g" / "pop_g") '
    buildings.addExpressionField(expr, QgsField('nb_m2_hab', QVariant.Int))

    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'pop_g',
        'CATEGORIES_FIELD_NAME': 'id_2',
        'OUTPUT': outdir + 'csv/grid_pop.csv'
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)
    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'NB_NIV',
        'CATEGORIES_FIELD_NAME': 'CODE_IRIS',
        'OUTPUT': outdir + 'csv/iris_nb_niv.csv'
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)
    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'nb_m2_hab',
        'CATEGORIES_FIELD_NAME': 'CODE_IRIS',
        'OUTPUT': outdir + 'csv/iris_m2_hab.csv'
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)
    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'area_g',
        'CATEGORIES_FIELD_NAME': 'id_2',
        'OUTPUT': outdir + 'csv/grid_ssr.csv'
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)
    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'area_g',
        'CATEGORIES_FIELD_NAME': 'CODE_IRIS',
        'OUTPUT': outdir + 'csv/iris_ssr.csv'
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)
    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'planch_g',
        'CATEGORIES_FIELD_NAME': 'id_2',
        'OUTPUT': outdir + 'csv/grid_srf_pla.csv'
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)
    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'planch_g',
        'CATEGORIES_FIELD_NAME': 'CODE_IRIS',
        'OUTPUT': outdir + 'csv/iris_srf_pla.csv'
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)

    to_shp(buildings, outdir + 'bati_inter_grid.shp')
    del buildings, res

    # Correction et changement de nom pour jointure des stat sur la grille et les IRIS
    csvIplanch = QgsVectorLayer(outdir + 'csv/iris_srf_pla.csv')
    csvIplanch.addExpressionField('round(to_real("q3"))', QgsField('spl_q3', QVariant.Int))
    csvIplanch.addExpressionField('round(to_real("max"))', QgsField('spl_max', QVariant.Int))
    csvIplanch.addExpressionField('round(to_real("sum"))', QgsField('spl_sum', QVariant.Int))
    csvIris.append(csvIplanch)

    csvGplanch = QgsVectorLayer(outdir + 'csv/grid_srf_pla.csv')
    csvGplanch.addExpressionField('round(to_real("sum"))', QgsField('srf_pla', QVariant.Int))
    csvGrid.append(csvGplanch)

    csvIssolR = QgsVectorLayer(outdir + 'csv/iris_ssr.csv')
    csvIssolR.addExpressionField('round(to_real("sum"))', QgsField('ssr_sum', QVariant.Int))
    csvIssolR.addExpressionField('round(to_real("min"))', QgsField('ssr_min', QVariant.Int))
    csvIssolR.addExpressionField('round(to_real("mean"))', QgsField('ssr_mean', QVariant.Int))
    csvIssolR.addExpressionField('round(to_real("median"))', QgsField('ssr_med', QVariant.Int))
    csvIris.append(csvIssolR)

    csvGssol = QgsVectorLayer(outdir + 'csv/grid_ssr.csv')
    csvGssol.addExpressionField('round(to_real("sum"))', QgsField('ssol_res', QVariant.Int))
    csvGrid.append(csvGssol)

    csvIniv = QgsVectorLayer(outdir + 'csv/iris_nb_niv.csv')
    csvIniv.addExpressionField('to_real("mean")', QgsField('niv_mean', QVariant.Double))
    csvIniv.addExpressionField('to_int("median")', QgsField('niv_med', QVariant.Int))
    csvIniv.addExpressionField('to_real("q3")', QgsField('niv_q3', QVariant.Double))
    csvIniv.addExpressionField('to_int("max")', QgsField('niv_max', QVariant.Int))
    csvIris.append(csvIniv)

    csvIm2 = QgsVectorLayer(outdir + 'csv/iris_m2_hab.csv')
    csvIm2.addExpressionField('round(to_real("mean"))', QgsField('m2_hab', QVariant.Int))
    csvIris.append(csvIm2)

    csvGpop = QgsVectorLayer(outdir + 'csv/grid_pop.csv')
    csvGpop.addExpressionField('to_int("sum")', QgsField('pop', QVariant.Int))
    csvGrid.append(csvGpop)

    gridBlacklist = ['left', 'right', 'top', 'bottom']
    irisFields1 = []
    gridFields1 = []
    irisFields2 = []
    gridFields2 = []
    for path in os.listdir(csvDir):
        res = re.search('([0-9]{2})_([a-z]*)_ssol_([a-z]{4})\.csv', path)
        if res:
            year = res.group(1)
            name = res.group(2)
            idType = res.group(3)
            path = csvDir + path
            csvLayer = QgsVectorLayer(path, name)
            csvLayer.addExpressionField('to_real("sum")', QgsField(year + '_' + name, QVariant.Double))
            if idType == 'grid':
                csvGrid.append(csvLayer)
                if year == '09':
                    gridFields1.append(year + '_' + name)
                elif year == '14':
                    gridFields2.append(year + '_' + name)
            elif idType == 'iris':
                csvIris.append(csvLayer)
                if year == '09':
                    irisFields1.append(year + '_' + name)
                elif year == '14':
                    irisFields2.append(year + '_' + name)

    for csvLayer in csvGrid:
        join(grid, 'id', csvLayer, 'id_2', statBlacklist)
    for csvLayer in csvIris:
        join(iris, 'CODE_IRIS', csvLayer, 'CODE_IRIS', statBlacklist)

    cpt = 0
    expr = ''
    for field in gridFields1:
        cpt += 1
        if cpt != len(gridFields1):
            expr += 'IF("' + field + '" IS NULL, 0, "' + field + '") + '
        else:
            expr += 'IF("' + field + '" IS NULL, 0, "' + field + '")'
    grid.addExpressionField('round(' + expr + ')', QgsField('ssol_09', QVariant.Int))

    cpt = 0
    expr = ''
    for field in gridFields2:
        cpt += 1
        if cpt != len(gridFields2):
            expr += 'IF("' + field + '" IS NULL, 0, "' + field + '") + '
        else:
            expr += 'IF("' + field + '" IS NULL, 0, "' + field + '")'
    grid.addExpressionField('round(' + expr + ')', QgsField('ssol_14', QVariant.Int))

    cpt = 0
    expr = ''
    for field in irisFields1:
        cpt += 1
        if cpt != len(irisFields1):
            expr += 'IF("' + field + '" IS NULL, 0, "' + field + '") + '
        else:
            expr += 'IF("' + field + '" IS NULL, 0, "' + field + '")'
    iris.addExpressionField('round(' + expr + ')', QgsField('ssol_09', QVariant.Int))

    cpt = 0
    expr = ''
    for field in irisFields2:
        cpt += 1
        if cpt != len(irisFields2):
            expr += 'IF("' + field + '" IS NULL, 0, "' + field + '") + '
        else:
            expr += 'IF("' + field + '" IS NULL, 0, "' + field + '")'
    iris.addExpressionField('round(' + expr + ')', QgsField('ssol_14', QVariant.Int))

    iris.addExpressionField('"SSR_SUM" / "ssol_14"', QgsField('TX_SSR', QVariant.Double))
    iris.addExpressionField('$id + 1', QgsField('ID', QVariant.Int, len=4))

    params = {
        'INPUT': grid,
        'COLUMN': gridBlacklist + gridFields1 + gridFields2,
        'OUTPUT': outdir + '/stat_grid.shp'
    }
    processing.run('qgis:deletecolumn', params, feedback=feedback)
    params = {
        'INPUT': iris,
        'COLUMN': irisFields1 + irisFields2,
        'OUTPUT': outdir + '/stat_iris.shp'
    }
    processing.run('qgis:deletecolumn', params, feedback=feedback)

# Crée une grille avec des statistiques par cellule sur la surface couverte pour chaque couche en entrée
def restrictGrid(layerList, grid, ratio, outdir):
    grid.dataProvider().createSpatialIndex()
    csvList = []
    fieldList = []

    for layer in layerList:
        name = layer.name()
        fieldList.append(name)
        layer.dataProvider().createSpatialIndex()
        params = {
            'INPUT': layer,
            'OVERLAY': grid,
            'INPUT_FIELDS': [],
            'OVERLAY_FIELDS': ['id'],
            'OUTPUT': 'memory:' + name
        }
        res = processing.run('qgis:intersection', params, feedback=feedback)
        layer = res['OUTPUT']
        layer.addExpressionField('$area', QgsField(
            'area_g', QVariant.Double, len=10, prec=2))
        params = {
            'INPUT': layer,
            'VALUES_FIELD_NAME': 'area_g',
            'CATEGORIES_FIELD_NAME': 'id_2',
            'OUTPUT': outdir + 'csv/restriction_' + name + '.csv'
        }
        processing.run('qgis:statisticsbycategories',
                       params, feedback=feedback)
        csvLayer = QgsVectorLayer(
            outdir + 'csv/restriction_' + name + '.csv')
        csvLayer.addExpressionField(
            'to_real("sum")', QgsField(name, QVariant.Double))
        csvList.append(csvLayer)
        del layer, res

    for csvLayer in csvList:
        join(grid, 'id', csvLayer, 'id_2', statBlacklist)
    cpt = 0
    # Expression pour écarter complètement les cellules qui intersectent
    if ratio == 0:
        expr = 'IF ('
        for field in fieldList:
            cpt += 1
            if cpt != len(fieldList):
                expr += '"' + field + '" IS NOT NULL OR '
            else:
                expr += '"' + field + '" IS NOT NULL, 1, 0)'
    # Expression pour écarter les cellules à partir d'un certain seuil de chevauchement
    else:
        expr = 'IF ('
        for field in fieldList:
            cpt += 1
            if cpt != len(fieldList):
                expr += '"' + field + '" >= ($area * ' + str(ratio) + ')  OR '
            else:
                expr += '"' + field + '" >= ($area * ' + str(ratio) + '), 1, 0)'

    grid.addExpressionField(expr, QgsField('restrict', QVariant.Int))
    to_shp(grid, outdir + 'restrict_grid.shp')
    del fieldList, csvList, csvLayer

# Selection des tuiles MNT dans la zone d'étude sous forme de liste
def demExtractor(directory, bbox):
    tileList = []
    for tile in os.listdir(directory):
        if os.path.splitext(tile)[1] == '.asc':
            path = directory + tile
            with open(path) as file:
                for i in range(5):
                    line = file.readline()
                    res = re.search('[a-z]*\s*([0-9.]*)', line)
                    if i == 0:
                        xSize = int(res.group(1))
                    elif i == 1:
                        ySize = int(res.group(1))
                    elif i == 2:
                        xMin = float(res.group(1))
                    elif i == 3:
                        yMin = float(res.group(1))
                    elif i == 4:
                        cellSize = float(res.group(1))
            xMax = xMin + xSize * cellSize
            yMax = yMin + ySize * cellSize
            tileExtent = QgsRectangle(xMin, yMin, xMax, yMax)
            if bbox.intersects(tileExtent):
                tileList.append(path)
    return tileList

# Traitement des zonages reglementaires pour la couche de restrictions
def envRestrict(layerList, overlay, outdir):
    for file in layerList:
        intersects = False
        name = os.path.basename(file).split('.')[0].lower()
        if '_OCCITANIE_L93' in file:
            name = name.replace('_occitanie_l93', '')
            layer = QgsVectorLayer(file, name)
            layer.setProviderEncoding('ISO-8859-14')
        if '_OCC_L93' in file:
            name = name.replace('_occ_l93', '')
            layer = QgsVectorLayer(file, name)
            layer.setProviderEncoding('ISO-8859-14')
        if '_s_r76' in file:
            name = name.replace('_s_r76', '')
            layer = QgsVectorLayer(file, name)
            layer.setProviderEncoding('UTF-8')
        if '_r73' in file:
            name = name.replace('_r73', '')
            layer = QgsVectorLayer(file, name)
            layer.setProviderEncoding('ISO-8859-14')

        layer.dataProvider().createSpatialIndex()
        i = 0
        while i < layer.featureCount() and not intersects:
            if layer.getFeature(i).geometry().intersects(overlay.getFeature(0).geometry()):
                intersects = True
            i += 1

        if intersects:
            if 'PARCS_NATIONAUX_OCCITANIE_L93.shp' in file:
                params = {
                    'INPUT': layer,
                    'EXPRESSION': """ "CODE_R_ENP" = 'CPN' """,
                    'OUTPUT': 'memory:coeur_parcs_nationaux',
                    'FAIL_OUTPUT': 'memory:'
                }
                res = processing.run('native:extractbyexpression', params, feedback=feedback)
                reproj(clip(res['OUTPUT'], overlay), outdir)
            else:
                reproj(clip(layer, overlay), outdir)

# Jointure avec données INSEE et extraction des IRIS dans la zone
def irisExtractor(iris, overlay, csvdir, outdir):
    # Conversion des chaînes en nombre
    csvPop09 = QgsVectorLayer(csvdir + 'inseePop09.csv')
    csvPop09.addExpressionField('to_int("P09_POP")', QgsField('POP09', QVariant.Int))
    csvPop12 = QgsVectorLayer(csvdir + 'inseePop12.csv')
    csvPop12.addExpressionField('to_int("P12_POP")', QgsField('POP12', QVariant.Int))
    csvPop14 = QgsVectorLayer(csvdir + 'inseePop14.csv')
    csvPop14.addExpressionField('to_int("P14_POP")', QgsField('POP14', QVariant.Int))
    csvLog14 = QgsVectorLayer(csvdir + 'inseeLog14.csv')
    csvLog14.addExpressionField('to_real("P14_TXRP")', QgsField('TXRP14', QVariant.Double))

    # Jointure avec données INSEE et extraction des IRIS dans la zone
    join(iris, 'CODE_IRIS', csvPop09, 'IRIS', ['P09_POP'])
    join(iris, 'CODE_IRIS', csvPop12, 'IRIS', ['P12_POP'])
    join(iris, 'CODE_IRIS', csvPop14, 'IRIS', ['P14_POP'])
    join(iris, 'CODE_IRIS', csvLog14, 'IRIS', ['P14_TXRP'])
    expr = '("POP12"-"POP09") / "POP09" / 3 * 100'
    iris.addExpressionField(expr, QgsField('EVPOP0912', QVariant.Double))
    expr = '("POP14"-"POP12") / "POP12" / 2 * 100'
    iris.addExpressionField(expr, QgsField('EVPOP1214', QVariant.Double))
    expr = '("POP14"-"POP09") / "POP09" / 5 * 100'
    iris.addExpressionField(expr, QgsField('EVPOP0914', QVariant.Double))

    # Extraction des quartiers IRIS avec jointures
    params = {
        'INPUT': iris,
        'PREDICATE': 6,
        'INTERSECT': overlay,
        'OUTPUT': 'memory:iris'
    }
    res = processing.run('native:extractbylocation', params, feedback=feedback)
    return reproj(res['OUTPUT'], outdir)
    del csvPop09, csvPop12, csvPop14, csvLog14

# Corrige les géometries et reclasse un PLU
def pluFixer(plu, overlay, outdir, encoding='utf-8'):
    plu.setProviderEncoding(encoding)
    plu.dataProvider().createSpatialIndex()
    fields = []
    for f in plu.fields():
        fields.append(f.name())
    if 'type' in fields:
        expr = """ CASE
            WHEN "type" LIKE '%AU%' THEN 'AU'
            WHEN "type" LIKE '%N%' THEN 'N'
            WHEN "type" LIKE '%U%' AND "type" NOT LIKE '%AU%' THEN 'U'
            WHEN "type" LIKE 'A%' AND "type" NOT LIKE 'AU%' THEN 'A'
            WHEN "type" = 'ZAC' THEN 'ZAC'
            ELSE '0' END
        """
        plu.addExpressionField(expr, QgsField('classe', QVariant.String, len=3))
    if 'coment' in fields and 'coment' in fields:
        expr = """
                IF ("coment" LIKE '%à protéger%'
                OR "coment" LIKE 'Coupures%'
                OR "coment" LIKE 'périmètre protection %'
                OR "coment" LIKE 'protection forte %'
                OR "coment" LIKE 'sauvegarde de sites naturels, paysages ou écosystèmes'
                OR "coment" LIKE '% terrains réservés %'
                OR "coment" LIKE '% protégée'
                OR "coment" LIKE '% construction nouvelle est interdite %', 1, 0)
            """
        plu.addExpressionField(expr, QgsField('restrict', QVariant.Int, len=1))
        expr = """
                IF ("type" LIKE '%AU%'
                OR "coment" LIKE '%urbanisation future%'
                OR "coment" LIKE '%ouvert_ à l_urbanisation%'
                OR "coment" LIKE '% destinée à l_urbanisation%', 1, 0)
            """
        plu.addExpressionField(expr, QgsField('priority', QVariant.Int, len=1))
        expr = """ IF ("coment" LIKE '% protection contre risques naturels', 1, 0) """
        plu.addExpressionField(expr, QgsField('ppr', QVariant.Int, len=1))

    params = {'INPUT': plu, 'OUTPUT': 'memory:plu' }
    res = processing.run('native:fixgeometries', params, feedback=feedback)
    return reproj(clip(res['OUTPUT'], overlay), outdir)

# Classement et séparation des points de la couche geosirene
def sireneSplitter(geosirene, outpath):
    geosirene.dataProvider().createSpatialIndex()
    expr = """ CASE
        WHEN "CODE_NAF1" = 'O' THEN 'administratif'
        WHEN
            "CODE_NAF1" = 'G'
            OR "CODE_NAF1" = 'I'
            OR "CODE_NAF1" = 'J'
            OR "CODE_NAF1" = 'K'
            OR "CODE_NAF1" = 'L'
            OR "CODE_NAF1" = 'S'
        THEN 'commercial'
        WHEN "CODE_NAF1" = 'P' THEN 'enseignement'
        WHEN "CODE_NAF1" = 'R' THEN 'recreatif'
        WHEN "CODE_NAF1" = 'Q' THEN 'medical'
        ELSE 'autre' END
    """
    geosirene.addExpressionField(expr, QgsField('type', QVariant.String, len=20))

    params = {'INPUT': geosirene, 'FIELD': 'type', 'OUTPUT': outpath }
    processing.run('qgis:splitvectorlayer', params, feedback=feedback)

try:
    # Découpe et reprojection de la donnée en l'absence du dossier ./data
    if not os.path.exists(workspacePath + 'data'):
        os.mkdir(workspacePath + 'data')
        os.mkdir(workspacePath + 'data/2009_bati')
        os.mkdir(workspacePath + 'data/2014_bati')
        os.mkdir(workspacePath + 'data/pai')
        os.mkdir(workspacePath + 'data/transport')
        os.mkdir(workspacePath + 'data/geosirene')
        os.mkdir(workspacePath + 'data/restriction')

        etape = 1
        description = 'extraction et reprojection des données '
        progres = "Etape %i sur 8 : %s" %(etape, description)
        if not silent:
            printer(progres)
        start_time = time()
        log.write(description + ': ')

        # Tampon de 1000m autour de la zone pour extractions des quartiers et des PAI
        zone = QgsVectorLayer(localData + 'zone.shp', 'zone')
        zone.dataProvider().createSpatialIndex()
        params = {
            'INPUT': zone,
            'DISTANCE': bufferDistance,
            'SEGMENTS': 5,
            'END_CAP_STYLE': 0,
            'JOIN_STYLE': 0,
            'MITER_LIMIT': 2,
            'DISSOLVE': True,
            'OUTPUT': 'memory:zone_buffer'
        }
        res = processing.run('native:buffer', params, feedback=feedback)
        zone_buffer = res['OUTPUT']
        # Extraction des quartiers IRIS avec jointures
        iris = QgsVectorLayer(globalData + 'rge/IRIS_GE.SHP', 'iris')
        iris.dataProvider().createSpatialIndex()
        irisExtractor(iris, zone_buffer, globalData + 'insee/csv/', workspacePath + 'data/')
        # Extractions et reprojections
        clipBati = [
            globalData + 'rge/' + codeDept + '/bdtopo_2016/BATI_INDIFFERENCIE.SHP',
            globalData + 'rge/' + codeDept + '/bdtopo_2016/BATI_INDUSTRIEL.SHP',
            globalData + 'rge/' + codeDept + '/bdtopo_2016/BATI_REMARQUABLE.SHP',
            globalData + 'rge/' + codeDept + '/bdtopo_2016/CIMETIERE.SHP',
            globalData + 'rge/' + codeDept + '/bdtopo_2016/CONSTRUCTION_LEGERE.SHP',
            globalData + 'rge/' + codeDept + '/bdtopo_2016/CONSTRUCTION_SURFACIQUE.SHP',
            globalData + 'rge/' + codeDept + '/bdtopo_2016/PISTE_AERODROME.SHP',
            globalData + 'rge/' + codeDept + '/bdtopo_2016/RESERVOIR.SHP',
            globalData + 'rge/' + codeDept + '/bdtopo_2016/TERRAIN_SPORT.SHP'
        ]
        clipPai = [
            globalData + 'rge/' + codeDept + '/bdtopo_2016/PAI_ADMINISTRATIF_MILITAIRE.SHP',
            globalData + 'rge/' + codeDept + '/bdtopo_2016/PAI_CULTURE_LOISIRS.SHP',
            globalData + 'rge/' + codeDept + '/bdtopo_2016/PAI_ESPACE_NATUREL.SHP',
            globalData + 'rge/' + codeDept + '/bdtopo_2016/PAI_INDUSTRIEL_COMMERCIAL.SHP',
            globalData + 'rge/' + codeDept + '/bdtopo_2016/PAI_RELIGIEUX.SHP',
            globalData + 'rge/' + codeDept + '/bdtopo_2016/PAI_SANTE.SHP',
            globalData + 'rge/' + codeDept + '/bdtopo_2016/PAI_SCIENCE_ENSEIGNEMENT.SHP',
            globalData + 'rge/' + codeDept + '/bdtopo_2016/PAI_SPORT.SHP',
            globalData + 'rge/' + codeDept + '/bdtopo_2016/PAI_TRANSPORT.SHP'
        ]
        clipRes = [
            globalData + 'rge/' + codeDept + '/bdtopo_2016/ROUTE_PRIMAIRE.SHP',
            globalData + 'rge/' + codeDept + '/bdtopo_2016/ROUTE_SECONDAIRE.SHP',
            globalData + 'rge/' + codeDept + '/bdtopo_2016/TRONCON_VOIE_FERREE.SHP',
            globalData + 'rge/' + codeDept + '/bdtopo_2016/GARE.SHP'
        ]

        argList = []
        for path in clipBati:
            argList.append((clip(path, zone), workspacePath + 'data/2014_bati/'))
            argList.append((clip(path.replace('2016', '2009'), zone), workspacePath + 'data/2009_bati/'))
        for path in clipPai:
            argList.append((clip(path, zone_buffer), workspacePath + 'data/pai/'))
        for path in clipRes:
            argList.append((clip(path, zone_buffer), workspacePath + 'data/transport/'))
        argList.append((clip(globalData + 'rge/' + codeDept + '/bdtopo_2016/SURFACE_ACTIVITE.SHP', zone), workspacePath + 'data/pai/'))

        if speed:
            getDone(reproj, argList)
        else:
            for a in argList:
                reproj(*a)

        del clipBati, clipRes, clipPai

        # Préparation de la couche arrêts de transport en commun
        transports = []
        if os.path.exists(localData + 'bus.shp'):
            reproj(clip(localData + 'bus.shp', zone_buffer), workspacePath + 'data/transport/')
            bus = QgsVectorLayer(workspacePath + 'data/transport/bus.shp', 'bus')
            transports.append(bus)
            del bus

        params = {
            'INPUT': workspacePath + 'data/pai/transport.shp',
            'EXPRESSION': """ "NATURE" = 'Station de métro' """,
            'OUTPUT': workspacePath + 'data/transport/transport_pai.shp',
            'FAIL_OUTPUT': 'memory:'
        }
        res = processing.run('native:extractbyexpression', params, feedback=feedback)
        transports.append(res['OUTPUT'])

        gare = QgsVectorLayer(workspacePath + 'data/transport/gare.shp', 'gare')
        params = {'INPUT': gare, 'OUTPUT': 'memory:gare'}
        res = processing.run('native:centroids', params, feedback=feedback)
        transports.append(res['OUTPUT'])

        params = {
            'LAYERS': transports,
            'CRS': 'EPSG:3035',
            'OUTPUT': workspacePath + 'data/transport/arrets_transport.shp'
        }
        processing.run('native:mergevectorlayers', params, feedback=feedback)
        del transports, gare

        # Traitement du PLU
        if os.path.exists(localData + 'plu.shp'):
            plu = QgsVectorLayer(localData + 'plu.shp', 'plu')
            pluFixer(plu, zone, workspacePath + 'data/', 'windows-1258')
            del plu

        # Extraction et classification des points geosirene
        sirene = reproj(clip(globalData + 'sirene/geosirene.shp', zone_buffer))
        sireneSplitter(sirene, workspacePath + 'data/geosirene/')

        argList = []
        # Correction de l'OCS ou extraction de l'OSO CESBIO si besoin
        if not os.path.exists(localData + 'ocsol.shp'):
            ocsol = QgsVectorLayer( globalData + 'oso/departement_' + codeDept + '.shp', 'ocsol')
            ocsol.dataProvider().createSpatialIndex()
        else:
            params = {
                'INPUT': localData + 'ocsol.shp',
                'OUTPUT': 'memory:ocsol'
            }
            res = processing.run('native:fixgeometries', params, feedback=feedback)
            ocsol = res['OUTPUT']
            expr = """
                CASE
                    WHEN "lib15_niv1" = 'EAU' THEN 0
                    WHEN "lib15_niv1" = 'ESPACES AGRICOLES' THEN 0.9
                    WHEN "lib15_niv1" = 'ESPACES BOISES' THEN 0.3
                    WHEN "lib15_niv1" = 'ESPACES NATURELS NON BOISES' THEN 0.6
                    WHEN "lib15_niv1" = 'ESPACES RECREATIFS' THEN 0.1
                    WHEN "lib15_niv1" = 'ESPACES URBANISES' THEN 1
                    WHEN "lib15_niv1" = 'EXTRACTION DE MATERIAUX, DECHARGES, CHANTIERS' THEN 0
                    WHEN "lib15_niv1" = 'SURFACES INDUSTRIELLES OU COMMERCIALES ET INFRASTRUCTURES DE COMMUNICATION' THEN 0
                    ELSE 0
                END
            """
            ocsol.addExpressionField(expr, QgsField('interet', QVariant.Double))
        argList.append((clip(ocsol, zone), workspacePath + 'data/'))

        # Traitement du shape de l'intérêt écologique
        if os.path.exists(localData + 'ecologie.shp'):
            ecologie = QgsVectorLayer(localData + 'ecologie.shp', 'ecologie')
            ecoFields = []
            for field in ecologie.fields():
                ecoFields.append(field.name())
            if 'importance' not in ecoFields:
                error = "Attribut requis 'importance' manquant ou mal nommé dans la couche d'importance écologique"
                if not silent:
                    print(error)
                else:
                    log.write('Erreur : ' + error)
                sys.exit()
            ecologie.addExpressionField('"importance"/100', QgsField('taux', QVariant.Double))

            params = {'INPUT': ecologie, 'OUTPUT': 'memory:ecologie'}
            res = processing.run('native:fixgeometries', params, feedback=feedback)
            ecologie = res['OUTPUT']
            del ecoFields, field
        # Autrement déterminer l'intérêt écologique grâce à l'ocsol ?
        else:
            pass

        argList.append((clip(ecologie, zone), workspacePath + 'data/'))
        argList.append((clip(globalData + 'rge/' + codeDept + '/bdtopo_2016/SURFACE_EAU.SHP', zone), workspacePath + 'data/restriction/'))

        # Traitement d'une couche facultative du PPR
        if os.path.exists('ppr.shp'):
            argList.append((clip('ppr.shp', zone), workspacePath + 'data/restriction'))

        # Traitement d'une couche facultative pour exclusion de zones bâties lors du calcul de densité
        if os.path.exists(localData + 'exclusion.shp'):
            argList.append((clip(localData + 'exclusion.shp', zone), workspacePath + 'data/restriction/'))

        if speed:
            getDone(reproj, argList)
        else:
            for a in argList:
                reproj(*a)

        del ecologie, ocsol

        # Traitement des couches de zonage de protection
        zonagesEnv = []
        os.mkdir(workspacePath + 'data/zonages')
        for file in os.listdir(globalData + 'env/'):
            if os.path.splitext(file)[1] == '.shp':
                zonagesEnv.append(globalData + 'env/' + file)
        envRestrict(zonagesEnv, zone, workspacePath + 'data/zonages/')

        zonagesEnv = []
        for file in os.listdir(workspacePath + 'data/zonages/'):
            if os.path.splitext(file)[1] == '.shp':
                zonagesEnv.append(workspacePath + 'data/zonages/' + file)
        params = {
            'LAYERS': zonagesEnv,
            'CRS': 'EPSG:3035',
            'OUTPUT': workspacePath + 'data/restriction/zonages_protection.shp'
        }
        processing.run('native:mergevectorlayers', params, feedback=feedback)
        del zonagesEnv

        # Traitement des autoroutes
        params = {
            'INPUT': workspacePath + 'data/transport/route_primaire.shp',
            'EXPRESSION': """ "NATURE" = 'Autoroute' """,
            'OUTPUT': 'memory:autoroutes',
            'FAIL_OUTPUT': 'memory:'
        }
        res = processing.run('native:extractbyexpression', params, feedback=feedback)
        params = {
            'INPUT': res['OUTPUT'],
            'DISTANCE': 100,
            'SEGMENTS': 5,
            'END_CAP_STYLE': 0,
            'JOIN_STYLE': 0,
            'MITER_LIMIT': 2,
            'DISSOLVE': True,
            'OUTPUT': workspacePath + 'data/restriction/tampon_autoroutes.shp'
        }
        processing.run('native:buffer', params, feedback=feedback)

        reproj(zone, workspacePath + 'data/')
        reproj(zone_buffer, workspacePath + 'data/')
        del zone, zone_buffer

        # Fusion des routes primaires et secondaires
        mergeRoads = [workspacePath + 'data/transport/route_primaire.shp', workspacePath + 'data/transport/route_secondaire.shp']
        params = {
            'LAYERS': mergeRoads,
            'CRS': 'EPSG:3035',
            'OUTPUT': workspacePath + 'data/transport/routes.shp'
        }
        processing.run('native:mergevectorlayers', params, feedback=feedback)

        # Fusion des couches PAI
        mergePai = [
            workspacePath + 'data/pai/administratif_militaire.shp',
            workspacePath + 'data/pai/culture_loisirs.shp',
            workspacePath + 'data/pai/industriel_commercial.shp',
            workspacePath + 'data/pai/religieux.shp',
            workspacePath + 'data/pai/sante.shp',
            workspacePath + 'data/pai/science_enseignement.shp',
            workspacePath + 'data/pai/sport.shp'
        ]
        params = {
            'LAYERS': mergePai,
            'CRS': 'EPSG:3035',
            'OUTPUT': workspacePath + 'data/pai/pai_merged.shp'
        }
        processing.run('native:mergevectorlayers', params, feedback=feedback)
        log.write(getTime(start_time) + '\n')

        start_time = time()
        etape = 2
        description = "nettoyage du bâti pour l'estimation de la population "
        progres = "Etape %i sur 8 : %s" %(etape, description)
        if not silent:
            printer(progres)
        log.write(description + ': ')

        # Nettoyage dans la couche de bâti indif. avec les PAI et surfaces d'activité
        bati_indif = QgsVectorLayer(workspacePath + 'data/2014_bati/bati_indifferencie.shp', 'bati_indif_2014')
        bati_indif.dataProvider().createSpatialIndex()
        cleanPolygons = []
        cleanPoints = [workspacePath + 'data/pai/pai_merged.shp']
        # On ignore les zones industrielles et commerciales
        params = {
            'INPUT': workspacePath + 'data/pai/surface_activite.shp',
            'EXPRESSION': """ "CATEGORIE" != 'Industriel ou commercial' """,
            'OUTPUT': workspacePath + 'data/pai/surf_activ_non_com.shp',
            'FAIL_OUTPUT': 'memory:'
        }
        processing.run('native:extractbyexpression', params, feedback=feedback)
        # Fusion des polygones pour éviter les résidus avec le prédicat WITHIN
        params = {
            'INPUT': workspacePath + 'data/pai/surf_activ_non_com.shp',
            'FIELD': [],
            'OUTPUT': 'memory:'
        }
        res = processing.run('native:dissolve', params, feedback=feedback)
        cleanPolygons.append(res['OUTPUT'])
        if os.path.exists(workspacePath + 'data/restriction/exclusion.shp'):
            cleanPolygons.append(workspacePath + 'data/restriction/exclusion.shp')
        buildingCleaner(bati_indif, minSurf, maxSurf, levelHeight, cleanPolygons, cleanPoints,
                        workspacePath + 'data/2014_bati/bati_clean.shp', workspacePath + 'data/restriction/bati_removed.shp')
        del bati_indif, cleanPolygons, cleanPoints

        # Intersection du bâti résidentiel avec les quartiers IRIS
        bati_clean = QgsVectorLayer(workspacePath + 'data/2014_bati/bati_clean.shp')
        bati_clean.dataProvider().createSpatialIndex()
        params = {
            'INPUT': workspacePath + 'data/2014_bati/bati_clean.shp',
            'OVERLAY': workspacePath + 'data/iris.shp',
            'INPUT_FIELDS': ['ID', 'HAUTEUR', 'NB_NIV'],
            'OVERLAY_FIELDS': ['CODE_IRIS', 'NOM_IRIS', 'TYP_IRIS', 'POP14', 'TXRP14'],
            'OUTPUT': workspacePath + 'data/2014_bati/bati_inter_iris.shp'
        }
        processing.run('qgis:intersection', params, feedback=feedback)
        log.write(getTime(start_time) + '\n')

    if not os.path.exists(workspacePath + 'data/' + gridSize + 'm/'):
        os.mkdir(workspacePath + 'data/' + gridSize + 'm/')
        os.mkdir(workspacePath + 'data/' + gridSize + 'm/tif')
        os.mkdir(workspacePath + 'data/' + gridSize + 'm/csv')

        start_time = time()
        etape = 3
        description =  "création d'une grille de " + gridSize + "m de côté "
        progres = "Etape %i sur 8 : %s" %(etape, description)
        if not silent:
            printer(progres)
        log.write(description + ': ')

        # Création d'une grille régulière
        zone_buffer = QgsVectorLayer(workspacePath + 'data/zone_buffer.shp', 'zone_buffer')
        extent = zone_buffer.extent()
        extentStr = str(extent.xMinimum()) + ',' + str(extent.xMaximum()) + ',' + str(extent.yMinimum()) + ',' + str(extent.yMaximum()) + ' [EPSG:3035]'
        params = {
            'TYPE': 2,
            'EXTENT': extentStr,
            'HSPACING': int(gridSize),
            'VSPACING': int(gridSize),
            'HOVERLAY': 0,
            'VOVERLAY': 0,
            'CRS': 'EPSG:3035',
            'OUTPUT': workspacePath + 'data/' + gridSize + 'm/grid.shp'
        }
        processing.run('qgis:creategrid', params, feedback=feedback)
        del zone_buffer, extent, extentStr
        log.write(getTime(start_time) + '\n')

        start_time = time()
        etape = 4
        description = "analyse de l'évolution des zones bâties "
        progres = "Etape %i sur 8 : %s" %(etape, description)
        if not silent:
            printer(progres)
        log.write(description + ': ')

        grid = QgsVectorLayer(workspacePath + 'data/' + gridSize + 'm/grid.shp', 'grid')
        grid.dataProvider().createSpatialIndex()
        iris = QgsVectorLayer(workspacePath + 'data/iris.shp')
        iris.dataProvider().createSpatialIndex()

        buildStatDic = {
            'indif': workspacePath + 'data/2014_bati/bati_indifferencie.shp',
            'indus': workspacePath + 'data/2014_bati/bati_industriel.shp',
            'remarq': workspacePath + 'data/2014_bati/bati_remarquable.shp',
            'surfac': workspacePath + 'data/2014_bati/construction_surfacique.shp',
            'aerodr': workspacePath + 'data/2014_bati/piste_aerodrome.shp',
            'sport': workspacePath + 'data/2014_bati/terrain_sport.shp'
        }
        argList = []
        for k, v in buildStatDic.items():
            argList.append((k, v, iris, grid, workspacePath + 'data/' + gridSize + 'm/csv/'))
        for k, v in buildStatDic.items():
            argList.append((k, v.replace('2014','2009'), iris, grid, workspacePath + 'data/' + gridSize + 'm/csv/'))

        if speed:
            getDone(buildCsvGrid, argList)
        else:
            for a in argList:
                buildCsvGrid(*a)
        log.write(getTime(start_time) + '\n')

        start_time = time()
        etape = 5
        description = "estimation de la population dans la grille "
        progres = "Etape %i sur 8 : %s" %(etape, description)
        if not silent:
            printer(progres)
        log.write(description + ': ')

        batiInterIris = QgsVectorLayer(workspacePath + 'data/2014_bati/bati_inter_iris.shp')
        statGridIris(batiInterIris, grid, iris, workspacePath + 'data/' + gridSize + 'm/', workspacePath + 'data/' + gridSize + 'm/csv/')
        del grid, iris
        log.write(getTime(start_time) + '\n')

        start_time = time()
        etape = 6
        description = "calcul des restrictions "
        progres = "Etape %i sur 8 : %s" %(etape, description)
        if not silent:
            printer(progres)
        log.write(description + ': ')

        # Création de la grille de restriction
        grid = QgsVectorLayer(workspacePath + 'data/' + gridSize + 'm/grid.shp', 'grid')
        b_removed = QgsVectorLayer(workspacePath + 'data/restriction/bati_removed.shp', 'b_removed')
        cimetiere = QgsVectorLayer(workspacePath + 'data/2014_bati/cimetiere.shp', 'cimetiere')
        s_eau = QgsVectorLayer(workspacePath + 'data/restriction/surface_eau.shp', 's_eau')

        restrictList = [b_removed, cimetiere, s_eau]
        restrictGrid(restrictList, grid, maxOverlapRatio, workspacePath + 'data/' + gridSize + 'm/')
        del b_removed, cimetiere, s_eau, restrictList, grid

        # Objet pour transformation de coordonées
        l93 = QgsCoordinateReferenceSystem()
        l93.createFromString('EPSG:2154')
        laea = QgsCoordinateReferenceSystem()
        laea.createFromString('EPSG:3035')
        trCxt = QgsCoordinateTransformContext()
        coordTr = QgsCoordinateTransform(l93, laea, trCxt)
        # BBOX pour extraction du MNT
        grid = QgsVectorLayer(workspacePath + 'data/' + gridSize + 'm/stat_grid.shp', 'grid')
        extent = grid.extent()
        extentL93 = coordTr.transform(extent, coordTr.ReverseTransform)
        # Extraction des tuiles MNT dans la zone d'étude
        demList = demExtractor(globalData + 'rge/' + codeDept + '/bdalti/', extentL93)
        xMin = extent.xMinimum()
        yMin = extent.yMinimum()
        xMax = extent.xMaximum()
        yMax = extent.yMaximum()

        # Fusion des tuiles et reprojection
        gdal.Warp(
            workspacePath + 'data/' + gridSize + 'm/tif/mnt.tif', demList,
            format='GTiff', outputType=gdal.GDT_Float32,
            xRes=int(gridSize), yRes=int(gridSize),
            resampleAlg='cubicspline',
            srcSRS='EPSG:2154', dstSRS='EPSG:3035',
            outputBounds=(xMin, yMin, xMax, yMax),
            srcNodata=-99999
        )
        # Calcul de pente en %
        gdal.DEMProcessing(
            workspacePath + 'data/' + gridSize + 'm/tif/slope.tif',
            workspacePath + 'data/' + gridSize + 'm/tif/mnt.tif',
            'slope', format='GTiff',
            slopeFormat='percent'
        )
        log.write(getTime(start_time) + '\n')

        start_time = time()
        etape = 7
        description = "création des rasters de restriction et d'intérêt "
        progres = "Etape %i sur 8 : %s" %(etape, description)
        if not silent:
            printer(progres)
        log.write(description + ': ')
        # Chaîne à passer à QGIS pour l'étendue des rasterisations
        extentStr = str(xMin) + ',' + str(xMax) + ',' + str(yMin) + ',' + str(yMax) + ' [EPSG:3035]'

        # Rasterisations
        argList = [
            (workspacePath + 'data/ecologie.shp', workspacePath + 'data/' + gridSize + 'm/tif/ecologie.tif', 'taux'),
            (workspacePath + 'data/transport/routes.shp', workspacePath + 'data/' + gridSize + 'm/tif/routes.tif', None, 1),
            (workspacePath + 'data/transport/arrets_transport.shp', workspacePath + 'data/' + gridSize + 'm/tif/arrets_transport.tif', None, 1),
            (workspacePath + 'data/' + gridSize + 'm/restrict_grid.shp', workspacePath + 'data/' + gridSize + 'm/tif/restrict_grid.tif', 'restrict'),
            (workspacePath + 'data/' + gridSize + 'm/stat_iris.shp', workspacePath + 'data/' + gridSize + 'm/tif/masque.tif', None, 1, True),
            (workspacePath + 'data/restriction/zonages_protection.shp', workspacePath + 'data/' + gridSize + 'm/tif/zonages_protection.tif', None, 1),
            (workspacePath + 'data/restriction/tampon_autoroutes.shp', workspacePath + 'data/' + gridSize + 'm/tif/tampon_autoroutes.tif', None, 1),
            (workspacePath + 'data/restriction/exclusion.shp', workspacePath + 'data/' + gridSize + 'm/tif/exclusion.tif', None, 1),
            (workspacePath + 'data/pai/surf_activ_non_com.shp', workspacePath + 'data/' + gridSize + 'm/tif/surf_activ_non_com.tif', None, 1)
        ]
        if os.path.exists(workspacePath + 'data/restriction/ppr.shp'):
            argList.append((workspacePath + 'data/restriction/ppr.shp', workspacePath + 'data/' + gridSize + 'm/tif/ppr.tif', None, 1))
        elif os.path.exists(workspacePath + 'data/plu.shp'):
            argList.append((workspacePath + 'data/plu.shp', workspacePath + 'data/' + gridSize + 'm/tif/ppr.tif', 'ppr'))

        if speed:
            getDone(rasterize, argList)
        else:
            for a in argList:
                rasterize(*a)

        # Calcul des rasters de distance
        params = {
            'INPUT': workspacePath + 'data/' + gridSize + 'm/tif/routes.tif',
            'BAND': 1,
            'VALUES': 1,
            'UNITS': 0,
            'NODATA': -1,
            'MAX_DISTANCE': roadDist,
            'DATA_TYPE': 5,
            'OUTPUT': workspacePath + 'data/' + gridSize + 'm/tif/distance_routes.tif'
        }
        processing.run('gdal:proximity', params, feedback=feedback)

        params['INPUT'] = workspacePath + 'data/' + gridSize + 'm/tif/arrets_transport.tif'
        params['MAX_DISTANCE'] = transDist
        params['OUTPUT'] = workspacePath + 'data/' + gridSize + 'm/tif/distance_arrets_transport.tif'
        processing.run('gdal:proximity', params, feedback=feedback)

        # Calcul des rasters de densité
        os.mkdir(workspacePath + 'data/' + gridSize + 'm/tif/tmp')
        projwin = str(xMin) + ',' + str(xMax) + ',' + str(yMin) + ',' + str(yMax)
        with open(globalData + 'sirene/distances.csv') as csvFile:
            reader = csv.reader(csvFile)
            next(reader, None)
            distancesSirene = {rows[0]:int(rows[1]) for rows in reader}

        for k, v in distancesSirene.items():
            layer = QgsVectorLayer(workspacePath + 'data/geosirene/type_' + k + '.shp', k)
            layer.setExtent(extent)
            params = {
                'INPUT': layer,
                'RADIUS': v,
                'PIXEL_SIZE': int(gridSize),
                'KERNEL': 0,
                'OUTPUT_VALUE': 0,
                'OUTPUT': workspacePath + 'data/' + gridSize + 'm/tif/tmp/densite_' + k + '.tif'
            }
            processing.run('qgis:heatmapkerneldensityestimation', params, feedback=feedback)

            params = {
                'INPUT': workspacePath + 'data/' + gridSize + 'm/tif/tmp/densite_' + k + '.tif',
                'PROJWIN': projwin,
                'NODATA': -9999,
                'DATA_TYPE': 5,
                'OUTPUT': workspacePath + 'data/' + gridSize + 'm/tif/densite_' + k + '.tif'
            }
            processing.run('gdal:cliprasterbyextent', params, feedback=feedback)

        del projwin, distancesSirene
        log.write(getTime(start_time) + '\n')

    start_time = time()
    etape = 8
    description = "finalisation "
    progres = "Etape %i sur 8 : %s" %(etape, description)
    if not silent:
        printer(progres)
    log.write(description + ': ')

    # Préparation du fichier des IRIS - création des ID et de la matrice de contiguïté
    pop09 = 0
    pop12 = 0
    pop14 = 0
    iris = QgsVectorLayer(workspacePath + 'data/' + gridSize + 'm/stat_iris.shp')
    for feat in iris.getFeatures():
        pop09 += int(feat.attribute('POP09'))
        pop12 += int(feat.attribute('POP12'))
        pop14 += int(feat.attribute('POP14'))
    with open(projectPath + 'population.csv', 'x') as w:
        w.write('annee, demographie\n')
        w.write('2009, ' + str(pop09) + '\n')
        w.write('2012, ' + str(pop12) + '\n')
        w.write('2014, ' + str(pop14) + '\n')
    del iris

    grid = QgsVectorLayer(workspacePath + 'data/' + gridSize + 'm/stat_grid.shp', 'grid')
    extent = grid.extent()
    xMin = extent.xMinimum()
    yMin = extent.yMinimum()
    xMax = extent.xMaximum()
    yMax = extent.yMaximum()
    extentStr = str(xMin) + ',' + str(xMax) + ',' + str(yMin) + ',' + str(yMax) + ' [EPSG:3035]'

    # Rasterisations
    argList = [
        (workspacePath + 'data/' + gridSize + 'm/stat_grid.shp', projectPath + 'demographie_14.tif', 'pop'),
        (workspacePath + 'data/' + gridSize + 'm/stat_grid.shp', projectPath + 'srf_pla.tif', 'srf_pla'),
        (workspacePath + 'data/' + gridSize + 'm/stat_grid.shp', projectPath + 'srf_sol_res.tif', 'ssol_res'),
        (workspacePath + 'data/' + gridSize + 'm/stat_grid.shp', projectPath + 'srf_sol_09.tif', 'ssol_09'),
        (workspacePath + 'data/' + gridSize + 'm/stat_grid.shp', projectPath + 'srf_sol_14.tif', 'ssol_14'),
        (workspacePath + 'data/' + gridSize + 'm/stat_iris.shp', projectPath + 'iris_tx_ssr.tif', 'tx_ssr'),
        # (workspacePath + 'data/' + gridSize + 'm/stat_iris.shp', projectPath + 'iris_niv_q3.tif', 'niv_q3'),
        # (workspacePath + 'data/' + gridSize + 'm/stat_iris.shp', projectPath + 'iris_niv_med.tif', 'niv_med'),
        # (workspacePath + 'data/' + gridSize + 'm/stat_iris.shp', projectPath + 'iris_niv_max.tif', 'niv_max'),
        # (workspacePath + 'data/' + gridSize + 'm/stat_iris.shp', projectPath + 'iris_srf_pla_q3.tif', 'spl_q3'),
        (workspacePath + 'data/' + gridSize + 'm/stat_iris.shp', projectPath + 'iris_srf_pla_max.tif', 'spl_max'),
        (workspacePath + 'data/' + gridSize + 'm/stat_iris.shp', projectPath + 'iris_srf_pla_max.tif', 'spl_max'),
        (workspacePath + 'data/' + gridSize + 'm/stat_iris.shp', projectPath + 'iris_m2_hab.tif', 'm2_hab'),
        (workspacePath + 'data/ocsol.shp', projectPath + 'occupation_sol.tif', 'interet')
    ]
    if os.path.exists(workspacePath + 'data/plu.shp'):
        argList.append((workspacePath + 'data/plu.shp', projectPath + 'plu_restriction.tif', 'restrict'))
        argList.append((workspacePath + 'data/plu.shp', projectPath +'plu_priorite.tif', 'priority'))

    if speed :
        getDone(rasterize, argList)
    else:
        for a in argList:
            rasterize(*a)

    # Création des variables GDAL indispensables pour la fonction to_tif()
    ds = gdal.Open(projectPath + 'demographie_14.tif')
    proj = ds.GetProjection()
    geot = ds.GetGeoTransform()
    ds = None

    # Conversion des raster de distance
    distance_routes = to_array(workspacePath + 'data/' + gridSize + 'm/tif/distance_routes.tif', np.float32)
    routes = np.where(distance_routes > -1, 1 - (distance_routes / np.amax(distance_routes)), 0)
    to_tif(routes, 'float32', proj, geot, projectPath + 'proximite_routes.tif')
    distance_transport = to_array(workspacePath + 'data/' + gridSize + 'm/tif/distance_arrets_transport.tif', np.float32)
    transport = np.where(distance_transport > -1, 1 - (distance_transport / np.amax(distance_transport)), 0)
    to_tif(transport, 'float32', proj, geot, projectPath + 'proximite_transport.tif')

    # Conversion et aggrégation des rasters de densité SIRENE
    with open(globalData + 'sirene/poids.csv') as csvFile:
        reader = csv.reader(csvFile)
        next(reader, None)
        poidsSirene = {rows[0]:int(rows[1]) for rows in reader}

    administratif = to_array(workspacePath + 'data/' + gridSize + 'm/tif/densite_administratif.tif', np.float32)
    commercial = to_array(workspacePath + 'data/' + gridSize + 'm/tif/densite_commercial.tif', np.float32)
    enseignement = to_array(workspacePath + 'data/' + gridSize + 'm/tif/densite_enseignement.tif', np.float32)
    medical = to_array(workspacePath + 'data/' + gridSize + 'm/tif/densite_medical.tif', np.float32)
    recreatif = to_array(workspacePath + 'data/' + gridSize + 'm/tif/densite_recreatif.tif', np.float32)
    # Normalisation des valeurs entre 0 et 1
    administratif = np.where(administratif != -9999, administratif / np.amax(administratif), 0)
    commercial = np.where(commercial != -9999, commercial / np.amax(commercial), 0)
    enseignement = np.where(enseignement != -9999, enseignement / np.amax(enseignement), 0)
    medical = np.where(medical != -9999, medical / np.amax(medical), 0)
    recreatif = np.where(recreatif != -9999, recreatif / np.amax(recreatif), 0)

    sirene = ((administratif * poidsSirene['administratif']) + (commercial * poidsSirene['commercial']) + (enseignement * poidsSirene['enseignement']) +
              (medical * poidsSirene['medical']) + (recreatif * poidsSirene['recreatif'])) / sum(poidsSirene.values())
    sirene = (sirene / np.amax(sirene)).astype(np.float32)
    to_tif(sirene, 'float32', proj, geot, projectPath + 'densite_sirene.tif')
    del poidsSirene, administratif, commercial, enseignement, medical, recreatif, sirene

    # Création du raster de restriction (sans PLU)
    irisMask = to_array(workspacePath + 'data/' + gridSize + 'm/tif/masque.tif', np.byte)
    exclusionMask = to_array(workspacePath + 'data/' + gridSize + 'm/tif/exclusion.tif', np.byte)
    surfActivMask = to_array(workspacePath + 'data/' + gridSize + 'm/tif/surf_activ_non_com.tif', np.byte)
    gridMask = to_array(workspacePath + 'data/' + gridSize + 'm/tif/restrict_grid.tif', np.byte)
    zonageMask = to_array(workspacePath + 'data/' + gridSize + 'm/tif/zonages_protection.tif', np.byte)
    highwayMask = to_array(workspacePath + 'data/' + gridSize + 'm/tif/tampon_autoroutes.tif', np.byte)
    pprMask = to_array(workspacePath + 'data/' + gridSize + 'm/tif/ppr.tif', np.byte)
    slope = to_array(workspacePath + 'data/' + gridSize + 'm/tif/slope.tif')
    slopeMask = np.where(slope > maxSlope, 1, 0).astype(np.byte)

    restriction = np.where((irisMask == 1) | (exclusionMask == 1) | (surfActivMask == 1) | (gridMask == 1) |
                            (zonageMask == 1) | (highwayMask == 1) | (pprMask == 1) | (slopeMask == 1), 1, 0)
    to_tif(restriction, 'byte', proj, geot, projectPath + 'restriction_totale.tif')
    del surfActivMask, exclusionMask, gridMask, zonageMask, highwayMask, pprMask, slope, slopeMask, restriction

    ecologie = to_array(workspacePath + 'data/' + gridSize + 'm/tif/ecologie.tif', np.float32)
    ecologie = np.where((ecologie == 0), 1, 1 - ecologie)
    ecologie = np.where((irisMask != 1), ecologie, 0)
    to_tif(ecologie, 'float32', proj, geot, projectPath + 'non-importance_ecologique.tif')
    del ecologie

    copyfile(localData + 'poids.csv', projectPath + 'poids.csv')

    if not silent:
        print('\nTerminée à ' + strftime('%H:%M:%S'))
    log.write(getTime(start_time) + '\n')

    if truth:
        rmtree(workspacePath)
        if not silent:
            print('Suppression des données temporaires !')

except:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    if not silent:
        print("\n*** Error :")
        traceback.print_exception(exc_type, exc_value, exc_traceback, limit=2, file=sys.stdout)
    else:
        log.write('\n*** Error :\n' + str(sys.exc_info()))
    qgs.exitQgis()
    log.close()
    sys.exit()

qgs.exitQgis()
log.close()
