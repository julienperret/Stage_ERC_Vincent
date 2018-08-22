#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import sys
import csv
import gdal
import decimal
import logging
import traceback
import subprocess
import numpy as np
from pathlib import Path
from ast import literal_eval
from time import strftime, time
from shutil import rmtree, copyfile
from toolbox import printer, getDone, getTime, to_array, to_tif

# Chercher les chemins de QGIS sur Linux, Windows ou MacOS
qgsRoot = None
if sys.platform == 'linux':
    for d in ['/usr', '/usr/local', '/opt/qgis']:
        if Path(d + '/lib/qgis').exists():
            qgsRoot = Path(d)
            sys.path.append(str(qgsRoot/'share/qgis/python'))
elif sys.platform == 'win32':
    for d in Path('C:/Program Files').iterdir():
        if 'QGIS 3' in str(d) or 'OSGeo4W64' in str(d):
            qgsRoot = d
    if not qgsRoot :
        for d in Path('C:/').iterdir():
            if 'OSGeo4W64' in str(d):
                qgsRoot = d
    if qgsRoot:
        sys.path.append(str(qgsRoot/'apps/qgis/python'))
elif sys.platform == 'darwin':
    if Path('/Applications/QGIS.app').exists():
        qgsRoot = Path('/Applications/QGIS.app')
        sys.path.append(str(qgsRoot/'Contents/Resources/python/'))

if not qgsRoot:
    print('Unable to locate QGIS 3. Exiting now...')
    sys.exit()

from qgis.core import (
    QgsApplication,
    QgsCoordinateTransform,
    QgsCoordinateTransformContext,
    QgsCoordinateReferenceSystem,
    QgsField,
    QgsProcessingFeedback,
    QgsRectangle,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsVectorLayerJoinInfo
)
from qgis.analysis import QgsNativeAlgorithms
from qgis.PyQt.QtCore import QVariant

qgs = QgsApplication([], GUIenabled=False)
if sys.platform == 'linux':
    qgs.setPrefixPath(str(qgsRoot), True)
    sys.path.append(str(qgsRoot/'share/qgis/python/plugins'))
elif sys.platform == 'win32':
    qgs.setPrefixPath(str(qgsRoot/'apps/qgis'))
    sys.path.append(str(qgsRoot/'apps/qgis/python/plugins'))
elif sys.platform == 'darwin':
    qgs.setPrefixPath(str(qgsRoot/'Contents/MacOS'))
    sys.path.append(str(qgsRoot/'Resources/python/plugins'))
qgs.initQgis()

import processing
from processing.core.Processing import Processing
Processing.initialize()

qgs.processingRegistry().addProvider(QgsNativeAlgorithms())

# Ignorer les erreurs de numpy lors d'une division par 0
np.seterr(divide='ignore', invalid='ignore')
# Utilisation d'un arrondi au supérieur avec les objet Decimal()
# decimal.getcontext().rounding='ROUND_HALF_UP'

# Import des paramètres d'entrée
globalData = Path(sys.argv[1])
dpt = sys.argv[2]
localData = Path(sys.argv[3])
outputDir = Path(sys.argv[4])
if len(sys.argv) > 5:
    argList = sys.argv[5].split()
    # Interprétation de la chaîne de paramètres
    for arg in argList :
        # Résolution de la grille / des rasters
        if 'pixRes' in arg:
            pixRes = int(arg.split("=")[1])
            pixResStr = str(pixRes) + 'm'
        # Mots magiques !
        elif 'force' in arg:
            force = True
        elif 'speed' in arg:
            speed = True
        elif 'truth' in arg:
            truth = True
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
        elif 'maxOverlapRatio' in arg:
            maxOverlapRatio = float(arg.split('=')[1])
        # Paramètres variables pour la création des rasters de distance
        elif 'roadDist' in arg:
            roadDist = int(arg.split('=')[1])
        elif 'transDist' in arg:
            transDist = int(arg.split('=')[1])
        # Seuil de pente en % pour interdiction à la construction
        elif 'maxSlope' in arg:
            maxSlope = int(arg.split('=')[1])

# Valeurs de paramètres par défaut
if 'pixRes' not in globals():
    pixRes = 50
    pixResStr= str(pixRes) + 'm'
if 'bufferDistance' not in globals():
    bufferDistance = 1000
if 'minSurf' not in globals():
    minSurf = 50
if 'maxSurf' not in globals():
    maxSurf = 10000
if 'usrTxrp' not in globals():
    useTxrp = True
if 'levelHeight' not in globals():
    levelHeight = 3
if 'maxOverlapRatio' not in globals():
    maxOverlapRatio = 0.3
if 'roadDist' not in globals():
    roadDist = 300
if 'transDist' not in globals():
    transDist = 200
if 'maxSlope' not in globals():
    maxSlope = 30
if 'force' not in globals():
    force = False
if 'speed' not in globals():
    speed = False
if 'truth' not in globals():
    truth = False

if dpt in ['11','30','34','48','66']:
    reg = 'R91'
elif dpt in ['09','12','31','32','46','65','81','82']:
    reg = 'R73'
else:
    print("Department " + dpt + " isn't part of the current study area !")
    sys.exit()

if not 100 >= pixRes >= 20:
    print('Pixel size should be between 20m and 100m')
    sys.exit()

if force and outputDir.exists():
    rmtree(str(outputDir))

if truth:
    workspace = outputDir/'tmp'
    if workspace.exists() :
        rmtree(str(workspace))
    project = outputDir
    studyAreaName = ''
else:
    studyAreaName = localData.parts[len(localData.parts)-1]
    workspace = outputDir/dpt/studyAreaName
    project = workspace/'simulation'/pixResStr
    if project.exists():
        rmtree(str(project))
    os.makedirs(str(project))
if not workspace.exists():
    os.makedirs(str(workspace))

class QgsLoggingFeedback(QgsProcessingFeedback):
    def __init__(self):
        super().__init__()
        # self.handler = logging.StreamHandler(sys.stdout)
        self.handler = logging.FileHandler(str(project/(strftime('%Y%m%d%H%M') + '_qgsLog.txt')))
        self.handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(self.handler)
    def reportError(self, msg, fatalError=False):
        logging.log(logging.ERROR, msg)
    def setProgressText(self, text):
        logging.log(logging.INFO, msg)
    def pushInfo(self, info):
        super().pushInfo(info)
    def pushCommandInfo(self, info):
        super().pushCommandInfo(info)
    def pushDebugInfo(self, info):
        super().pushDebugInfo(info)
    def pushConsoleInfo(self, info):
        super().pushConsoleInfo(info)

feedback = QgsLoggingFeedback()

statBlacklist = ['count', 'unique', 'min', 'max', 'range', 'sum', 'mean',
                 'median', 'stddev', 'minority', 'majority', 'q1', 'q3', 'iqr']

print('Started at ' + strftime('%H:%M:%S'))

# Découpe une couche avec gestion de l'encodage pour la BDTOPO
def clip(file, overlay, outdir='memory:'):
    if type(file) == QgsVectorLayer:
        name = file.name()
        params = {
            'INPUT': file,
            'OVERLAY': overlay
        }
    else:
        path = str(file)
        name = os.path.basename(path).split('.')[0].lower()
        layer = QgsVectorLayer(path, name)
        layer.dataProvider().createSpatialIndex()
        if 'bdtopo_2016' in path:
            layer.setProviderEncoding('ISO-8859-14')
        if 'PAI_' in path:
            name = name.replace('pai_', '')
        params = {
            'INPUT': layer,
            'OVERLAY': overlay
        }
    if outdir == 'memory:':
        params['OUTPUT'] = outdir + name
    else:
        params['OUTPUT'] = str(outdir/(name + '.shp'))
    res = processing.run('native:clip', params, feedback=feedback)
    return res['OUTPUT']

# Reprojection en laea par défaut
def reproj(file, outdir='memory:', crs='EPSG:3035'):
    if type(file) == QgsVectorLayer:
        name = file.name()
        params = {
            'INPUT': file,
            'TARGET_CRS': crs
        }
    else:
        path = str(file)
        name = os.path.basename(path).split('.')[0].lower()
        layer = QgsVectorLayer(path, name)
        params = {
            'INPUT': layer,
            'TARGET_CRS': crs
        }
    if outdir == 'memory:':
        params['OUTPUT'] = outdir + name
    else:
        params['OUTPUT'] = str(outdir/(name + '.shp'))
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
def to_shp(layer, path):
    writer = QgsVectorFileWriter(
        str(path),
        'utf-8',
        layer.fields(),
        layer.wkbType(),
        layer.sourceCrs(),
        'ESRI Shapefile'
    )
    writer.addFeatures(layer.getFeatures())

# Rasterisation d'un fichier vecteur
def rasterize(vector, output, dtype, field=None, burn=None, inverse=False, touch=False, resolution=pixRes):
    opt = gdal.RasterizeOptions(
        format='GTiff',
        outputSRS='EPSG:3035',
        xRes=resolution,
        yRes=resolution,
        initValues=0,
        burnValues=burn,
        attribute=field,
        allTouched=touch,
        outputBounds=(xMin, yMin, xMax, yMax),
        inverse=inverse,
        options=['-ot', dtype, '-tr', str(pixRes), str(pixRes)]
    )
    gdal.Rasterize(str(output), str(vector), options=opt)

# Nettoye une couche de bâtiments et génère les champs utiles à l'estimation de population
def buildingCleaner(buildings, sMin, sMax, lvlHeight, polygons, points, cleanedOut, removedOut):
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
        ELSE floor("HAUTEUR"/""" + str(lvlHeight) + """) END
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
    processing.run('native:saveselectedfeatures', params, feedback=feedback)
    del buildings, polygons, points, layer

# Génère les statistiques de construction entre deux dates pour la grille et les IRIS
def urbGridStat(name, path, iris, grid, outCsvDir):
    res = re.search('.*20([0-9]{2})_bati.*\.shp', path)
    year = res.group(1)
    hasId = False
    buildings = QgsVectorLayer(path, name)
    buildings.dataProvider().createSpatialIndex()
    params = {
        'INPUT': buildings,
        'OUTPUT': 'memory:' + name
    }
    res = processing.run('native:fixgeometries', params, feedback=feedback)
    buildings = res['OUTPUT']

    for field in buildings.fields():
        if field.name() == 'ID' or field.name() == 'id':
            hasId = True
    if not hasId:
        buildings.addExpressionField('$id', QgsField('ID', QVariant.Int))

    params = {
        'INPUT': buildings,
        'OVERLAY': iris,
        'INPUT_FIELDS': [],
        'OVERLAY_FIELDS': ['CODE_IRIS'],
        'OUTPUT': 'memory:' + name
    }
    res = processing.run('native:intersection', params, feedback=feedback)
    buildings = res['OUTPUT']
    buildings.dataProvider().createSpatialIndex()
    if year == '14':
        params = {
            'INPUT': buildings,
            'OVERLAY': grid,
            'INPUT_FIELDS': [],
            'OVERLAY_FIELDS': ['id'],
            'OUTPUT': 'memory:' + name
        }
        res = processing.run('native:intersection', params, feedback=feedback)
        buildings = res['OUTPUT']
        buildings.dataProvider().createSpatialIndex()

    buildings.addExpressionField('$area', QgsField('AIRE', QVariant.Double))
    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'AIRE',
        'CATEGORIES_FIELD_NAME': 'CODE_IRIS',
        'OUTPUT': str(outCsvDir/(year + '_' + name + '_ssol_iris.csv'))
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)
    if year == '14':
        params = {
            'INPUT': buildings,
            'VALUES_FIELD_NAME': 'AIRE',
            'CATEGORIES_FIELD_NAME': 'id_2',
            'OUTPUT': str(outCsvDir/(year + '_' + name + '_ssol_grid.csv'))
        }
        processing.run('qgis:statisticsbycategories', params, feedback=feedback)

    del buildings

# Intersection entre la couche de bâti nettoyée jointe aux iris et la grille avec calcul et jointure des statistiques
def popGridStat(buildings, grid, iris, outdir, csvDir):
    csvGrid = []
    csvIris = []
    grid.dataProvider().createSpatialIndex()
    buildings.dataProvider().createSpatialIndex()
    buildings.addExpressionField('$area', QgsField('area_i', QVariant.Double))
    expr = ' "area_i" * "NB_NIV" '
    if useTxrp :
        expr +=  ' * IF("TXRP14" IS NOT NULL, "TXRP14", 0) '
    buildings.addExpressionField(expr, QgsField('planch', QVariant.Double))
    buildings.addExpressionField('concat("CODE_IRIS", "ID")', QgsField('pkey_iris', QVariant.String, len=50))

    dicPop = {}
    dicSumBuilds = {}
    dicBuilds = {}
    dicWeightedPop = {}
    for feat in iris.getFeatures():
        dicSumBuilds[feat.attribute('CODE_IRIS')] = 0.0
        dicBuilds[feat.attribute('CODE_IRIS')] = {}
        dicWeightedPop[feat.attribute('CODE_IRIS')] = {}
        dicPop[feat.attribute('CODE_IRIS')] = feat['POP14']

    for feat in buildings.getFeatures():
        dicSumBuilds[feat.attribute('CODE_IRIS')] += float(feat.attribute('planch'))
    for feat in buildings.getFeatures():
        dicWeightedPop[feat.attribute('CODE_IRIS')][feat.attribute('ID')] = 0
        try:
            dicBuilds[feat.attribute('CODE_IRIS')][feat.attribute('ID')] = feat.attribute('planch') / dicSumBuilds[feat.attribute('CODE_IRIS')]
        except ZeroDivisionError:
            dicBuilds[feat.attribute('CODE_IRIS')][feat.attribute('ID')] = 0


    with (outdir/'csv/pop_bati_pkey.csv').open('w') as w:
        w.write('pkey_iris, pop\n')
        for quartier, builds in dicBuilds.items():
            keyList = list(builds.keys())
            valueList = list(builds.values())
            irisPop = dicPop[quartier]
            reste = decimal.Decimal(0)
            i = 0
            for weight in valueList:
                idBati = keyList[i]
                popInt = int(weight * irisPop)
                popFloat = decimal.Decimal(weight * irisPop)
                reste += popFloat - popInt
                dicWeightedPop[quartier][idBati] += popInt
                i += 1
            valuesArray = np.array(valueList)
            for _ in range(round(reste)):
                i = np.random.choice(valuesArray.size, 1, p=valuesArray/valuesArray.sum())[0]
                idBati = keyList[i]
                dicWeightedPop[quartier][idBati] += 1
            for idBati, value in dicWeightedPop[quartier].items():
                w.write(quartier + idBati + ',' + str(value) + '\n')

    csvPop = QgsVectorLayer(str(outdir/'csv/pop_bati_pkey.csv'))
    csvPop.addExpressionField('to_int("pop")', QgsField('pop_bati', QVariant.Int))
    join(buildings, 'pkey_iris', csvPop, 'pkey_iris', ['pop'])

    dicPop = {}
    dicBuilds = {}
    for feat in buildings.getFeatures():
        dicPop[feat.attribute('pkey_iris')] = feat.attribute('pop_bati')
        dicBuilds[feat.attribute('pkey_iris')] = {}

    params = {
        'INPUT': buildings,
        'OVERLAY': grid,
        'INPUT_FIELDS': ['ID', 'HAUTEUR', 'NB_NIV', 'CODE_IRIS', 'ID_IRIS', 'NOM_IRIS', 'TYP_IRIS',
                          'POP14', 'TXRP14', 'area_i', 'planch', 'pkey_iris', 'pop_bati'],
        'OVERLAY_FIELDS': ['id'],
        'OUTPUT': 'memory:bati_inter_grid'
    }
    res = processing.run('native:intersection', params, feedback=feedback)
    buildings = res['OUTPUT']
    buildings.dataProvider().createSpatialIndex()
    buildings.addExpressionField('concat("CODE_IRIS", "ID", "id_2")', QgsField('pkey_grid', QVariant.String, len=50))

    buildings.addExpressionField('$area', QgsField('area_g', QVariant.Double))
    expr = ' "area_g" * "NB_NIV" '
    if useTxrp:
        expr += ' * "TXRP14"'
    buildings.addExpressionField(expr, QgsField('planch_g', QVariant.Double))

    for feat in buildings.getFeatures():
        if feat.attribute('area_i') > 0:
            dicBuilds[feat.attribute('pkey_iris')][feat.attribute('id_2')] = feat.attribute('area_g') / feat.attribute('area_i')
        else:
            dicBuilds[feat.attribute('pkey_iris')][feat.attribute('id_2')] = 0

    dicWeightedPop = {}
    for build, parts in dicBuilds.items():
        dicWeightedPop[build] = {}
        reste = decimal.Decimal(0)
        for gid, weight in parts.items():
            pop = dicPop[build]
            popInt = int(weight * pop)
            popFloat = decimal.Decimal(weight * pop)
            dicWeightedPop[build][gid] = popInt
            reste += popFloat - popInt
        if reste > 0:
            keyList = list(parts.keys())
            valueList = list(parts.values())
            valueArray = np.array(valueList)
            for _ in range(round(reste)):
                i = np.random.choice(valueArray.size, 1, p=valueArray/valueArray.sum())[0]
                gid = keyList[i]
                dicWeightedPop[build][gid] += 1

    with (outdir/'csv/pop_grid_pkey.csv').open('w') as w:
        w.write('pkey_grid, pop\n')
        for build, parts in dicWeightedPop.items():
            for gid, pop in parts.items():
                w.write(build + str(gid) + ', ' + str(pop) + '\n')

    csvPop = QgsVectorLayer(str(outdir/'csv/pop_grid_pkey.csv'))
    csvPop.addExpressionField('to_int("pop")', QgsField('pop_g', QVariant.Int))
    join(buildings, 'pkey_grid', csvPop, 'pkey_grid', ['pop'])
    expr = ' "planch_g" / "pop_g" '
    buildings.addExpressionField(expr, QgsField('nb_m2_hab', QVariant.Double))

    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'pop_g',
        'CATEGORIES_FIELD_NAME': 'id_2',
        'OUTPUT': str(outdir/'csv/grid_pop.csv')
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)
    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'nb_m2_hab',
        'CATEGORIES_FIELD_NAME': 'CODE_IRIS',
        'OUTPUT': str(outdir/'csv/iris_m2_hab.csv')
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)
    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'area_g',
        'CATEGORIES_FIELD_NAME': 'id_2',
        'OUTPUT': str(outdir/'csv/grid_ssr.csv')
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)
    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'area_g',
        'CATEGORIES_FIELD_NAME': 'CODE_IRIS',
        'OUTPUT': str(outdir/'csv/iris_ssr.csv')
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)
    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'planch_g',
        'CATEGORIES_FIELD_NAME': 'id_2',
        'OUTPUT': str(outdir/'csv/grid_srf_pla.csv')
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)
    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'NB_NIV',
        'CATEGORIES_FIELD_NAME': 'CODE_IRIS',
        'OUTPUT': str(outdir/'csv/iris_nb_niv.csv')
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)

    # Création des CSV de distribution des étages et surface au sol, utilisés pour le fitting avec R
    dicFloors, dicAreas = {}, {}
    for i in iris.getFeatures():
        id = str(i.attribute('ID_IRIS'))
        dicFloors[id] = []
        dicAreas[id] = []

    for feat in buildings.getFeatures():
        id = str(feat.attribute('ID_IRIS'))
        dicAreas[id].append(feat.attribute('area_g'))
        dicFloors[id].append(feat.attribute('NB_NIV'))

    with (outdir/'distrib_floors.csv').open('w') as csvFloors, (outdir/'distrib_surf.csv').open('w') as csvSurf:
        csvSurf.write('ID_IRIS, SURF\n')
        csvFloors.write('ID_IRIS, FLOOR\n')
        for id, values in dicAreas.items():
            for area in values:
                csvSurf.write(id + ', ' + str(area) + '\n')
        for id, values in dicFloors.items():
            for niv in values:
                csvFloors.write(id + ', ' + str(niv) + '\n')

    to_shp(buildings, outdir/'bati_inter_grid.shp')
    del buildings, res

    # Conversion des champs statistiques et attribution d'un nom
    csvGplanch = QgsVectorLayer(str(outdir/'csv/grid_srf_pla.csv'))
    csvGplanch.addExpressionField('round(to_real("sum"))', QgsField('srf_pla', QVariant.Int))
    csvGrid.append(csvGplanch)

    csvIssolR = QgsVectorLayer(str(outdir/'csv/iris_ssr.csv'))
    csvIssolR.addExpressionField('round(to_real("sum"))', QgsField('ssr_sum', QVariant.Int))
    csvIssolR.addExpressionField('round(to_real("median"))', QgsField('ssr_med', QVariant.Int))
    csvIris.append(csvIssolR)

    csvGssol = QgsVectorLayer(str(outdir/'csv/grid_ssr.csv'))
    csvGssol.addExpressionField('round(to_real("sum"))', QgsField('ssol_res', QVariant.Int))
    csvGrid.append(csvGssol)

    csvIm2 = QgsVectorLayer(str(outdir/'csv/iris_m2_hab.csv'))
    csvIm2.addExpressionField('round(to_real("mean"))', QgsField('m2_hab', QVariant.Int))
    csvIris.append(csvIm2)

    csvGpop = QgsVectorLayer(str(outdir/'csv/grid_pop.csv'))
    csvGpop.addExpressionField('to_int("sum")', QgsField('pop', QVariant.Int))
    csvGrid.append(csvGpop)

    csvIniv = QgsVectorLayer(str(outdir/'csv/iris_nb_niv.csv'), 'nb_niv')
    csvIniv.addExpressionField('to_int("max")', QgsField('nbniv_max', QVariant.Int))
    csvIris.append(csvIniv)

    gridBlacklist = ['left', 'right', 'top', 'bottom']
    irisFields1 = []
    irisFields2 = []
    gridFields = []
    for path in os.listdir(str(csvDir)):
        res = re.search('([0-9]{2})_([a-z]*)_ssol_([a-z]{4})\.csv', path)
        if res:
            year = res.group(1)
            name = res.group(2)
            idType = res.group(3)
            path = str(csvDir/path)
            csvLayer = QgsVectorLayer(path, name)
            csvLayer.addExpressionField('to_real("sum")', QgsField(year + '_' + name, QVariant.Double))
            if idType == 'grid':
                csvGrid.append(csvLayer)
                gridFields.append(year + '_' + name)
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
    for field in gridFields:
        cpt += 1
        if cpt != len(gridFields):
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

    iris.addExpressionField('"ssr_sum" / "ssol_14"', QgsField('tx_ssr', QVariant.Double))

    params = {
        'INPUT': grid,
        'COLUMN': gridBlacklist + gridFields,
        'OUTPUT': str(outdir/'stat_grid.shp')
    }
    processing.run('qgis:deletecolumn', params, feedback=feedback)
    params = {
        'INPUT': iris,
        'COLUMN': irisFields1 + irisFields2,
        'OUTPUT': str(outdir/'stat_iris.shp')
    }
    processing.run('qgis:deletecolumn', params, feedback=feedback)

    ssol09 = 0
    ssol14 = 0
    for feat in iris.getFeatures():
        ssol09 += feat.attribute('ssol_09')
        ssol14 += feat.attribute('ssol_14')
    with (outdir/'evo_surface_sol.csv').open('w') as w:
        w.write('annee, surface\n')
        w.write('2009, ' + str(ssol09) + '\n')
        w.write('2014, ' + str(ssol14) + '\n')

# Crée une grille avec des statistiques par cellule sur la surface couverte pour chaque couche en entrée
def restrictGrid(layerList, grid, ratio, outdir):
    csvList = []
    fieldList = []
    for layer in layerList:
        name = layer.name()
        fieldList.append(name)
        layer.dataProvider().createSpatialIndex()
        params = {
            'INPUT': layer,
            'OUTPUT': 'memory:' + layer.name()
        }
        res = processing.run('native:fixgeometries', params, feedback=feedback)
        layer = res['OUTPUT']
        params = {
            'INPUT': layer,
            'OVERLAY': grid,
            'INPUT_FIELDS': [],
            'OVERLAY_FIELDS': ['id'],
            'OUTPUT': 'memory:' + name
        }
        res = processing.run('native:intersection', params, feedback=feedback)
        layer = res['OUTPUT']
        layer.addExpressionField('$area', QgsField(
            'area_g', QVariant.Double, len=10, prec=2))
        params = {
            'INPUT': layer,
            'VALUES_FIELD_NAME': 'area_g',
            'CATEGORIES_FIELD_NAME': 'id_2',
            'OUTPUT': str(outdir/(name + '.csv'))
        }
        processing.run('qgis:statisticsbycategories',
                       params, feedback=feedback)
        csvLayer = QgsVectorLayer(str(outdir/(name + '.csv')))
        csvLayer.addExpressionField('to_real("sum")', QgsField(name, QVariant.Double))
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
    to_shp(grid, outdir/'restrict_grid.shp')
    del fieldList, csvList, csvLayer

# Selection des tuiles MNT dans la zone d'étude sous forme de liste
def demExtractor(directory, bbox):
    tileList = []
    for tile in os.listdir(str(directory)):
        if os.path.splitext(tile)[1] == '.asc':
            path = str(directory/tile)
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
        if 'PARCS_NATIONAUX_OCCITANIE_L93.shp' in file:
            name = name.replace('_occitanie_l93', '')
            layer = QgsVectorLayer(str(file), name)
            layer.setProviderEncoding('ISO-8859-14')
            params = {
                'INPUT': layer,
                'EXPRESSION': """ "CODE_R_ENP" = 'CPN' """,
                'OUTPUT': 'memory:coeur_parcs_nationaux',
                'FAIL_OUTPUT': 'memory:'
            }
            res = processing.run('native:extractbyexpression', params, feedback=feedback)
            layer = res['OUTPUT']
        elif '_OCCITANIE_L93' in file:
            name = name.replace('_occitanie_l93', '')
            layer = QgsVectorLayer(str(file), name)
            layer.setProviderEncoding('ISO-8859-14')
        elif '_OCC_L93' in file:
            name = name.replace('_occ_l93', '')
            layer = QgsVectorLayer(str(file), name)
            layer.setProviderEncoding('ISO-8859-14')
        elif '_s_r76' in file:
            name = name.replace('_s_r76', '')
            layer = QgsVectorLayer(str(file), name)
            layer.setProviderEncoding('UTF-8')
        elif '_r73' in file:
            name = name.replace('_r73', '')
            layer = QgsVectorLayer(str(file), name)
            layer.setProviderEncoding('ISO-8859-14')

        layer.dataProvider().createSpatialIndex()
        i = 0
        while i < layer.featureCount() and not intersects:
            if layer.getFeature(i).geometry().intersects(overlay.getFeature(0).geometry()):
                intersects = True
            i += 1

        if intersects:
                reproj(clip(layer, overlay), outdir)

# Jointure avec données INSEE et extraction des IRIS dans la zone
def irisExtractor(iris, overlay, csvdir, outdir):
    # Conversion des chaînes en nombre
    csvPop09 = QgsVectorLayer(str(csvdir/'inseePop09.csv'))
    csvPop09.addExpressionField('to_int("P09_POP")', QgsField('POP09', QVariant.Int))
    csvPop12 = QgsVectorLayer(str(csvdir/'inseePop12.csv'))
    csvPop12.addExpressionField('to_int("P12_POP")', QgsField('POP12', QVariant.Int))
    csvPop14 = QgsVectorLayer(str(csvdir/'inseePop14.csv'))
    csvPop14.addExpressionField('to_int("P14_POP")', QgsField('POP14', QVariant.Int))
    csvLog14 = QgsVectorLayer(str(csvdir/'inseeLog14.csv'))
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

# Aggrégation de classes et attribution d'une valeur d'intérêt
def ocsExtractor(ocsPath, oso=False):
    params = {
        'INPUT': str(ocsPath),
        'OUTPUT': 'memory:ocsol'
    }
    res = processing.run('native:fixgeometries', params, feedback=feedback)
    ocsol = res['OUTPUT']
    ocsol.dataProvider().createSpatialIndex()
    if oso:
        osoBlacklist = [ 'Hiver', 'Ete', 'Feuillus', 'Coniferes', 'Pelouse', 'Landes', 'UrbainDens', 'UrbainDiff', 'ZoneIndCom',
                         'Route', 'PlageDune', 'SurfMin', 'Eau', 'GlaceNeige', 'Prairie', 'Vergers', 'Vignes', 'Aire']
        params = {
            'INPUT': ocsol,
            'COLUMN': osoBlacklist,
            'OUTPUT':'memory:ocsol'
        }
        res = processing.run('qgis:deletecolumn', params, feedback=feedback)
        ocsol = res['OUTPUT']
        expr = """
            CASE
                WHEN to_string("Classe") LIKE '1%' or to_string("Classe") LIKE '2%' THEN 'ESPACE AGRICOLE'
                WHEN to_string("Classe") LIKE '3%' or "Classe"=45 or "Classe"=46 or "Classe"=53 THEN 'ESPACE NATUREL'
                WHEN "Classe"=41 or "Classe"=42 or "Classe"=43 or "Classe"=44 THEN 'ESPACE URBANISE'
                WHEN "Classe"=53 THEN 'SURFACE EN EAU'
                ELSE NULL
            END
        """
        ocsol.addExpressionField(expr, QgsField('classe_2', QVariant.String, len=30))
        ocsol.addExpressionField('"Classe"', QgsField('code_orig', QVariant.Int))
    else:
        if studyAreaName == 'mtp' or studyAreaName == 'montpellier':
            expr = """
                CASE
                    WHEN "lib15_niv1" = 'EAU' THEN 'SURFACE EN EAU'
                    WHEN "lib15_niv1" = 'ESPACES AGRICOLES' THEN 'ESPACE AGRICOLE'
                    WHEN "lib15_niv1" = 'ESPACES BOISES' THEN 'ESPACE NATUREL'
                    WHEN "lib15_niv1" = 'ESPACES NATURELS NON BOISES' THEN 'ESPACE NATUREL'
                    WHEN "lib15_niv1" = 'ESPACES RECREATIFS' THEN 'AUTRE'
                    WHEN "lib15_niv1" = 'ESPACES URBANISES' THEN 'ESPACE URBANISE'
                    WHEN "lib15_niv1" = 'EXTRACTION DE MATERIAUX, DECHARGES, CHANTIERS' THEN 'AUTRE'
                    WHEN "lib15_niv1" = 'SURFACES INDUSTRIELLES OU COMMERCIALES ET INFRASTRUCTURES DE COMMUNICATION' THEN 'ESPACE URBANISE'
                    ELSE 0
                END
            """
            ocsol.addExpressionField(expr, QgsField('classe_2', QVariant.String, len=30))
            ocsol.addExpressionField('"c2015_niv1"', QgsField('code_orig', QVariant.Int))

        elif studyAreaName == 'nim' or studyAreaName == 'nimes':
            # 1 = Urbain, 2 = Agricole, 3 = Espace naturel, 4 = Zone humide, 5 = Surface en eau
            expr = """
                CASE
                    WHEN "NIV1_12" = 1 THEN 'ESPACE URBANISE'
                    WHEN "NIV1_12" = 2 THEN 'ESPACE AGRICOLE'
                    WHEN "NIV1_12" = 3 THEN 'ESPACE NATUREL'
                    WHEN "NIV1_12" = 4 THEN 'ESPACE NATUREL'
                    WHEN "NIV1_12" = 5 THEN 'SURFACE EN EAU'
                    ELSE 0
                END
            """
            ocsol.addExpressionField(expr, QgsField('classe_2', QVariant.String, len=30))
            ocsol.addExpressionField('"NIV1_12"', QgsField('code_orig', QVariant.Int))

    expr = """
        CASE
            WHEN "classe_2" = 'ESPACE URBANISE' THEN 1
            WHEN "classe_2" = 'ESPACE AGRICOLE' THEN 0.6
            WHEN "classe_2" = 'ESPACE NATUREL' THEN 0.3
            WHEN "classe_2" = 'SURFACE EN EAU' THEN 0
            WHEN "classe_2" = 'AUTRE' THEN 0
            ELSE 0
        END
    """
    ocsol.addExpressionField(expr, QgsField('interet', QVariant.Double))
    return ocsol

# Corrige les géometries et reclasse un PLU
def pluFixer(plu, overlay, outdir, encoding='utf-8'):
    plu.setProviderEncoding(encoding)
    plu.dataProvider().createSpatialIndex()
    fields = list(f.name() for f in plu.fields())
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

    if studyAreaName == 'mtp' or studyAreaName == 'montpellier':
        expr = """
                IF ("coment" LIKE '%à protéger%'
                OR "coment" LIKE 'Coupures%'
                OR "coment" LIKE 'périmètre protection %'
                OR "coment" LIKE 'protection forte %'
                OR "coment" LIKE 'sauvegarde de sites naturels, paysages ou écosystèmes'
                OR "coment" LIKE '% terrains réservés %'
                OR "coment" LIKE '% protégée'
                OR "coment" LIKE '% construction nouvelle est interdite %'
                OR "coment" LIKE '% protection contre risques naturels', 1, 0)
            """
        plu.addExpressionField(expr, QgsField('restrict', QVariant.Int, len=1))
        expr = """
                IF ("type" LIKE '%AU%'
                OR "coment" LIKE '%urbanisation future%'
                OR "coment" LIKE '%ouvert_ à l_urbanisation%'
                OR "coment" LIKE '% destinée à l_urbanisation%', 1, 0)
            """
        plu.addExpressionField(expr, QgsField('priority', QVariant.Int, len=1))
    else:
        expr = """
                CASE
                    WHEN "classe" = 'N' THEN 1
                    WHEN "classe" = 'A' THEN 1
                    WHEN "classe" = 'ZAC' THEN 1
                    ELSE 0
                END
            """
        plu.addExpressionField(expr, QgsField('restrict', QVariant.Int, len=1))

        expr = """
                CASE
                    WHEN "classe" = 'AU' THEN 1
                    ELSE 0
                END
            """
        plu.addExpressionField(expr, QgsField('priority', QVariant.Int, len=1))

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

    params = {'INPUT': geosirene, 'FIELD': 'type', 'OUTPUT': str(outpath) }
    processing.run('qgis:splitvectorlayer', params, feedback=feedback)

with (project/(strftime('%Y%m%d%H%M') + '_log.txt')).open('w') as log:
    try:
        # Découpe et reprojection de la donnée en l'absence du dossier ./data
        if not (workspace/'data').exists():
            mkdirList = [
                workspace/'data',
                workspace/'data/2009_bati',
                workspace/'data/2014_bati',
                workspace/'data/pai',
                workspace/'data/transport',
                workspace/'data/geosirene',
                workspace/'data/restriction',
                workspace/'data/zonage'
            ]
            for path in mkdirList:
                os.mkdir(str(path))

            etape = 1
            description = 'extracting and reprojecting data '
            progres = "%i/8 : %s" %(etape, description)
            printer(progres)
            start_time = time()
            log.write(description + ': ')

            # Tampon de 1000m autour de la zone pour extractions des quartiers et des PAI
            zone = QgsVectorLayer(str(localData/'zone.shp'), 'zone')
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
            iris = QgsVectorLayer(str(globalData/'rge/IRIS_GE.SHP'), 'iris')
            iris.dataProvider().createSpatialIndex()
            irisExtractor(iris, zone_buffer, globalData/'insee/csv', workspace/'data')
            # Extractions et reprojections
            clipBati = [
                globalData/'rge'/dpt/'bdtopo_2016/BATI_INDIFFERENCIE.SHP',
                globalData/'rge'/dpt/'bdtopo_2016/BATI_INDUSTRIEL.SHP',
                globalData/'rge'/dpt/'bdtopo_2016/BATI_REMARQUABLE.SHP',
                globalData/'rge'/dpt/'bdtopo_2016/CIMETIERE.SHP',
                globalData/'rge'/dpt/'bdtopo_2016/CONSTRUCTION_SURFACIQUE.SHP',
                globalData/'rge'/dpt/'bdtopo_2016/PISTE_AERODROME.SHP',
                globalData/'rge'/dpt/'bdtopo_2016/RESERVOIR.SHP',
                globalData/'rge'/dpt/'bdtopo_2016/TERRAIN_SPORT.SHP'
            ]
            clipPai = [
                globalData/'rge'/dpt/'bdtopo_2016/PAI_ADMINISTRATIF_MILITAIRE.SHP',
                globalData/'rge'/dpt/'bdtopo_2016/PAI_CULTURE_LOISIRS.SHP',
                globalData/'rge'/dpt/'bdtopo_2016/PAI_ESPACE_NATUREL.SHP',
                globalData/'rge'/dpt/'bdtopo_2016/PAI_INDUSTRIEL_COMMERCIAL.SHP',
                globalData/'rge'/dpt/'bdtopo_2016/PAI_RELIGIEUX.SHP',
                globalData/'rge'/dpt/'bdtopo_2016/PAI_SANTE.SHP',
                globalData/'rge'/dpt/'bdtopo_2016/PAI_SCIENCE_ENSEIGNEMENT.SHP',
                globalData/'rge'/dpt/'bdtopo_2016/PAI_SPORT.SHP',
                globalData/'rge'/dpt/'bdtopo_2016/PAI_TRANSPORT.SHP'
            ]
            clipRes = [
                globalData/'rge'/dpt/'bdtopo_2016/ROUTE_PRIMAIRE.SHP',
                globalData/'rge'/dpt/'bdtopo_2016/ROUTE_SECONDAIRE.SHP',
                globalData/'rge'/dpt/'bdtopo_2016/TRONCON_VOIE_FERREE.SHP'
            ]

            argList = []
            for path in clipBati:
                argList.append((clip(path, zone), workspace/'data/2014_bati/'))
                argList.append((clip(Path(str(path).replace('2016', '2009')), zone), workspace/'data/2009_bati/'))
            for path in clipPai:
                argList.append((clip(path, zone_buffer), workspace/'data/pai/'))
            for path in clipRes:
                argList.append((clip(path, zone_buffer), workspace/'data/transport/'))
            argList.append((clip(globalData/'rge'/dpt/'bdtopo_2016/SURFACE_ACTIVITE.SHP', zone), workspace/'data/pai/'))

            if speed:
                getDone(reproj, argList)
            else:
                for a in argList:
                    reproj(*a)

            del clipBati, clipRes, clipPai

            # Zone tampon de 10m de part et d'autre des voies ferrées
            params = {
                'INPUT': str(workspace/'data/transport/troncon_voie_ferree.shp'),
                'EXPRESSION': """ "NATURE" != 'Transport urbain' """,
                'OUTPUT': 'memory:voies_ferrees',
                'FAIL_OUTPUT': 'memory:'
            }
            res = processing.run('native:extractbyexpression', params, feedback=feedback)
            voiesFerrees = res['OUTPUT']
            params = {
                'INPUT': voiesFerrees,
                'DISTANCE': 10,
                'SEGMENTS': 5,
                'END_CAP_STYLE': 0,
                'JOIN_STYLE': 0,
                'MITER_LIMIT': 2,
                'DISSOLVE': True,
                'OUTPUT': str(workspace/'data/restriction/tampon_voies_ferrees.shp')
            }
            processing.run('native:buffer', params, feedback=feedback)
            del voiesFerrees

            # Préparation de la couche arrêts de transport en commun
            transList = []
            if (localData/'bus.shp').exists():
                reproj(clip(localData/'bus.shp', zone_buffer), workspace/'data/transport/')
                bus = QgsVectorLayer(str(workspace/'data/transport/bus.shp'), 'bus')
                transList.append(bus)
                del bus

            params = {
                'INPUT': str(workspace/'data/pai/transport.shp'),
                'EXPRESSION': """ "NATURE" = 'Station de métro' """,
                'OUTPUT': str(workspace/'data/transport/transport_pai.shp'),
                'FAIL_OUTPUT': 'memory:'
            }
            res = processing.run('native:extractbyexpression', params, feedback=feedback)
            transList.append(res['OUTPUT'])

            params = {
                'INPUT': str(workspace/'data/pai/transport.shp'),
                'EXPRESSION': """ "NATURE" LIKE 'Gare voyageurs %' """,
                'OUTPUT': str(workspace/'data/transport/gare.shp'),
                'FAIL_OUTPUT': 'memory:'
            }
            res = processing.run('native:extractbyexpression', params, feedback=feedback)
            transList.append(res['OUTPUT'])

            params = {
                'LAYERS': transList,
                'CRS': 'EPSG:3035',
                'OUTPUT': str(workspace/'data/transport/arrets_transport.shp')
            }
            processing.run('native:mergevectorlayers', params, feedback=feedback)
            del transList

            # Traitement du PLU
            if (localData/'plu.shp').exists():
                plu = QgsVectorLayer(str(localData/'plu.shp'), 'plu')
                pluFixer(plu, zone, workspace/'data/', 'windows-1258')
                del plu

            # Extraction et classification des points geosirene
            sirene = reproj(clip(globalData/'sirene/geosirene.shp', zone_buffer))
            sireneSplitter(sirene, workspace/'data/geosirene/')

            argList = []
            argList.append((clip(globalData/'rge'/dpt/'bdtopo_2016/SURFACE_EAU.SHP', zone), workspace/'data/restriction/'))

            # Correction de l'OCS ou extraction de l'OSO CESBIO si besoin (penser à ajouter les valeurs d'intérêt !)
            if not (localData/'ocsol.shp').exists():
                ocsol = ocsExtractor(globalData/('oso/departement_' + dpt + '.shp'), True)
            else :
                ocsol = ocsExtractor(localData/'ocsol.shp')

            argList.append((clip(ocsol, zone), workspace/'data/'))

            # Traitement de la couche d'intérêt écologique
            if (localData/'ecologie.tif').exists():
                gdal.Warp(
                    str(workspace/'data/ecologie.tif'), str(localData/'ecologie.tif'),
                    format='GTiff', outputType=gdal.GDT_Float32,
                    xRes=pixRes, yRes=pixRes,
                    resampleAlg='cubicspline',
                    srcSRS='EPSG:2154', dstSRS='EPSG:3035'
                )

            elif (localData/'ecologie.shp').exists():
                ecologie = QgsVectorLayer(str(localData/'ecologie.shp'), 'ecologie')
                fields = list(f.name() for f in ecologie.fields())
                if 'importance' not in fields:
                    error = "Attribut requis 'importance' manquant ou mal nomme dans la couche d'importance ecologique"
                    print(error)
                    log.write('Erreur : ' + error)
                    sys.exit()
                ecologie.addExpressionField('"importance"/100', QgsField('taux', QVariant.Double))

                params = {'INPUT': ecologie, 'OUTPUT': 'memory:ecologie'}
                res = processing.run('native:fixgeometries', params, feedback=feedback)
                ecologie = res['OUTPUT']
                del fields
                argList.append((clip(ecologie, zone), workspace/'data/'))


            # Traitement d'une couche facultative du PPRI local : extraction des zones de restriction
            if (localData/'ppri.shp').exists():
                params = {
                    'INPUT': str(localData/'ppri.shp'),
                    'OUTPUT': 'memory:ppri'
                }
                res = processing.run('native:fixgeometries', params, feedback=feedback)
                ppri = res['OUTPUT']
                # Attention, le zonage varie : ici on cherche R zone rouge mais R peut signifier résiduel...
                expr = """ "CODEZONE" LIKE 'R%' """
                params = {
                    'INPUT': ppri,
                    'EXPRESSION': expr,
                    'OUTPUT': 'memory:ppri',
                    'FAIL_OUTPUT': 'memory:'
                }
                res = processing.run('native:extractbyexpression', params, feedback=feedback)
                ppri = res['OUTPUT']
                argList.append((clip(ppri, zone), workspace/'data/restriction/'))

            # Sinon on cherche une couche PPRI du département
            elif (globalData/'ppri').exists() and dpt in ['30', '34']:
                if dpt == '30':
                    expr = """ "CODEZONE" LIKE 'TF%' OR "CODEZONE" LIKE '%-NU' OR "CODEZONE" = 'F-U'"""
                    ppri = QgsVectorLayer(str(globalData/('ppri/L_ZONE_REG_PPRI_S_030.shp')), 'ppri')
                elif dpt == '34':
                    expr = """ "CODEZONE" LIKE 'R%' """
                    ppri = QgsVectorLayer(str(globalData/('ppri/N_ZONE_REG_PPRI_S_034.shp')), 'ppri')
                params = {
                    'INPUT': ppri,
                    'OUTPUT':'memory:ppri'
                }
                res = processing.run('native:fixgeometries', params, feedback=feedback)
                ppri = res['OUTPUT']
                params = {
                    'INPUT': ppri,
                    'EXPRESSION': expr,
                    'OUTPUT': 'memory:ppri',
                    'FAIL_OUTPUT': 'memory:'
                }
                res = processing.run('native:extractbyexpression', params, feedback=feedback)
                ppri = res['OUTPUT']
                argList.append((clip(ppri, zone), workspace/'data/restriction/'))

            # Utilisation des parcelles DGFIP pour exclure des bâtiments lors du calcul de densité
            if (globalData/('majic/exclusion_parcelles_' + dpt + '.shp')).exists():
                parcelles = QgsVectorLayer(str(globalData/('majic/exclusion_parcelles_' + dpt + '.shp')), 'exclusion_parcelles')
                argList.append((clip(parcelles, zone), workspace/'data/restriction/'))

            # + Traitement d'une couche facultative pour exclusion de zones bâties lors du calcul et inclusion dans les restrictions
            if (localData/'exclusion_manuelle.shp').exists():
                argList.append((clip(localData/'exclusion_manuelle.shp', zone), workspace/'data/restriction/'))

            # Traitement de la couche des mesures comensatoires
            if reg == 'R91' and (globalData/'comp').exists():
                comp = QgsVectorLayer(str(globalData/'comp/MesuresCompensatoires_R91.shp'), 'compensation')
                argList.append((clip(comp, zone), workspace/'data/restriction/'))

            if speed:
                getDone(reproj, argList)
            else:
                for a in argList:
                    reproj(*a)

            del ocsol
            if 'ecologie' in globals():
                del ecologie
            if 'ppri' in globals():
                del ppri
            if 'comp' in globals():
                del comp

            # Traitement des couches de zonage de protection
            zonagesEnv = []
            for file in os.listdir(str(globalData/'zonage/')):
                if os.path.splitext(file)[1] == '.shp':
                    zonagesEnv.append(str(globalData/('zonage/' + file)))
            envRestrict(zonagesEnv, zone, workspace/'data/zonage/')

            zonagesEnv = []
            for file in os.listdir(str(workspace/'data/zonage/')):
                if os.path.splitext(file)[1] == '.shp':
                    zonagesEnv.append(str(workspace/('data/zonage/' + file)))
            params = {
                'LAYERS': zonagesEnv,
                'CRS': 'EPSG:3035',
                'OUTPUT': str(workspace/'data/restriction/zonages_protection.shp')
            }
            processing.run('native:mergevectorlayers', params, feedback=feedback)
            del zonagesEnv

            # Traitement des autoroutes : bande de 100m de part et d'autre
            params = {
                'INPUT': str(workspace/'data/transport/route_primaire.shp'),
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
                'OUTPUT': str(workspace/'data/restriction/tampon_autoroutes.shp')
            }
            processing.run('native:buffer', params, feedback=feedback)
            # Traitement des autres routes : bande de 75m ===> voir Loi Barnier
            params = {
                'INPUT': str(workspace/'data/transport/route_primaire.shp'),
                'EXPRESSION': """ "NATURE" != 'Autoroute' """,
                'OUTPUT': 'memory:routes_primaires',
                'FAIL_OUTPUT': 'memory:'
            }
            res = processing.run('native:extractbyexpression', params, feedback=feedback)
            params = {
                'INPUT': res['OUTPUT'],
                'DISTANCE': 75,
                'SEGMENTS': 5,
                'END_CAP_STYLE': 0,
                'JOIN_STYLE': 0,
                'MITER_LIMIT': 2,
                'DISSOLVE': True,
                'OUTPUT': str(workspace/'data/restriction/tampon_routes_importantes.shp')
            }
            processing.run('native:buffer', params, feedback=feedback)

            reproj(zone, workspace/'data/')
            reproj(zone_buffer, workspace/'data/')
            del zone, zone_buffer

            # Fusion des routes primaires et secondaires
            mergeRoads = [str(workspace/'data/transport/route_primaire.shp'), str(workspace/'data/transport/route_secondaire.shp')]
            params = {
                'LAYERS': mergeRoads,
                'CRS': 'EPSG:3035',
                'OUTPUT': str(workspace/'data/transport/routes.shp')
            }
            processing.run('native:mergevectorlayers', params, feedback=feedback)

            # Fusion des couches PAI
            mergePai = [
                str(workspace/'data/pai/administratif_militaire.shp'),
                str(workspace/'data/pai/culture_loisirs.shp'),
                str(workspace/'data/pai/industriel_commercial.shp'),
                str(workspace/'data/pai/religieux.shp'),
                str(workspace/'data/pai/sante.shp'),
                str(workspace/'data/pai/science_enseignement.shp'),
                str(workspace/'data/pai/sport.shp')
            ]
            params = {
                'LAYERS': mergePai,
                'CRS': 'EPSG:3035',
                'OUTPUT': str(workspace/'data/pai/pai_merged.shp')
            }
            processing.run('native:mergevectorlayers', params, feedback=feedback)
            log.write(getTime(start_time) + '\n')

            start_time = time()
            etape = 2
            description = "cleaning buildings to estimate the population "
            progres = "%i/8 : %s" %(etape, description)
            printer(progres)
            log.write(description + ': ')

            # Nettoyage dans la couche de bâti indifferencié
            bati_indif = QgsVectorLayer(str(workspace/'data/2014_bati/bati_indifferencie.shp'), 'bati_indif_2014')
            bati_indif.dataProvider().createSpatialIndex()
            cleanPolygons = []
            cleanPoints = []
            # On inclut les surfaces d'activités (autres que commerciales et industrielles) dans la couche de restriction
            surf_activ = QgsVectorLayer(str(workspace/'data/pai/surface_activite.shp'), 'surf_activ')
            params = {
                'INPUT': str(workspace/'data/pai/surface_activite.shp'),
                'OUTPUT': 'memory:surf_activ'
            }
            res = processing.run('native:fixgeometries', params, feedback=feedback)
            surf_activ = res['OUTPUT']
            params = {
                'INPUT': surf_activ,
                'EXPRESSION': """ "CATEGORIE" != 'Industriel ou commercial' """,
                'OUTPUT': str(workspace/'data/pai/surf_activ_non_com.shp'),
                'FAIL_OUTPUT': 'memory:'
            }
            processing.run('native:extractbyexpression', params, feedback=feedback)
            del surf_activ

            # Si possible, on utilise les parcelles non résidentilles DGFIP fusionnées avec un tampon de 2m
            if (workspace/'data/restriction/exclusion_parcelles.shp').exists():
                parcelles = QgsVectorLayer(str(workspace/'data/restriction/exclusion_parcelles.shp'), 'parcelles')
                parcelles.dataProvider().createSpatialIndex()
                params = {
                    'INPUT': parcelles,
                    'DISTANCE': 2,
                    'SEGMENTS': 5,
                    'END_CAP_STYLE': 0,
                    'JOIN_STYLE': 0,
                    'MITER_LIMIT': 2,
                    'DISSOLVE': True,
                    'OUTPUT': 'memory:exclusion_parcelles'
                }
                processing.run('native:buffer', params, feedback=feedback)
                parcelles = res['OUTPUT']
                cleanPolygons.append(parcelles)
                del parcelles

            # Sinon, on utliser les surfaces d'activité et les PAI
            else:
                cleanPoints.append(str(workspace/'data/pai/pai_merged.shp'))
                # Fusion des polygones de zones d'activité pour éviter les oublis avec le prédicat WITHIN
                params = {
                    'INPUT': str(workspace/'data/pai/surf_activ_non_com.shp'),
                    'FIELD': [],
                    'OUTPUT': 'memory:'
                }
                res = processing.run('native:dissolve', params, feedback=feedback)
                cleanPolygons.append(res['OUTPUT'])

            # Couche pour zone supplémentaires à exclure du calcul de pop à inclure dans les restrictions
            if (workspace/'data/restriction/exclusion_manuelle.shp').exists():
                cleanPolygons.append(str(workspace/'data/restriction/exclusion_manuelle.shp'))

            buildingCleaner(bati_indif, minSurf, maxSurf, levelHeight, cleanPolygons, cleanPoints,
                            str(workspace/'data/2014_bati/bati_clean.shp'), str(workspace/'data/restriction/bati_removed.shp'))
            del bati_indif, cleanPolygons, cleanPoints

            # Intersection du bâti résidentiel avec les quartiers IRIS
            bati_clean = QgsVectorLayer(str(workspace/'data/2014_bati/bati_clean.shp'))
            bati_clean.dataProvider().createSpatialIndex()
            iris = QgsVectorLayer(str(workspace/'data/iris.shp'), 'iris')
            iris.addExpressionField('$id + 1', QgsField('ID_IRIS', QVariant.Int, len=4))
            params = {
                'INPUT': str(workspace/'data/2014_bati/bati_clean.shp'),
                'OVERLAY': iris,
                'INPUT_FIELDS': ['ID', 'HAUTEUR', 'NB_NIV'],
                'OVERLAY_FIELDS': ['CODE_IRIS', 'ID_IRIS', 'NOM_IRIS', 'TYP_IRIS', 'POP14', 'TXRP14'],
                'OUTPUT': str(workspace/'data/2014_bati/bati_inter_iris.shp')
            }
            processing.run('native:intersection', params, feedback=feedback)
            log.write(getTime(start_time) + '\n')
            del iris

        if not (workspace/'data'/pixResStr).exists():
            os.mkdir(str(workspace/'data'/pixResStr))
            start_time = time()
            etape = 3
            description =  "creating a grid with resolution " + pixResStr
            progres = "%i/8 : %s" %(etape, description)
            printer(progres)
            log.write(description + ': ')

            # Création d'une grille régulière
            zone_buffer = QgsVectorLayer(str(workspace/'data/zone_buffer.shp'), 'zone_buffer')
            extent = zone_buffer.extent()
            extentStr = str(extent.xMinimum()) + ',' + str(extent.xMaximum()) + ',' + str(extent.yMinimum()) + ',' + str(extent.yMaximum()) + ' [EPSG:3035]'
            params = {
                'TYPE': 2,
                'EXTENT': extentStr,
                'HSPACING': pixRes,
                'VSPACING': pixRes,
                'HOVERLAY': 0,
                'VOVERLAY': 0,
                'CRS': 'EPSG:3035',
                'OUTPUT': str(workspace/'data'/pixResStr/'grid.shp')
            }
            processing.run('qgis:creategrid', params, feedback=feedback)
            del zone_buffer, extent, extentStr
            log.write(getTime(start_time) + '\n')

        if not (workspace/'data'/pixResStr/'urb_csv').exists():
            os.mkdir(str(workspace/'data'/pixResStr/'urb_csv'))
            start_time = time()
            etape = 4
            description = "analysing the evolution of built areas "
            progres = "%i/8 : %s" %(etape, description)
            printer(progres)
            log.write(description + ': ')

            grid = QgsVectorLayer(str(workspace/'data'/pixResStr/'grid.shp'), 'grid')
            grid.dataProvider().createSpatialIndex()
            iris = QgsVectorLayer(str(workspace/'data/iris.shp'))
            iris.addExpressionField('$id + 1', QgsField('ID_IRIS', QVariant.Int, len=4))
            iris.dataProvider().createSpatialIndex()

            buildStatDic = {
                'indif': workspace/'data/2014_bati/bati_indifferencie.shp',
                'indus': workspace/'data/2014_bati/bati_industriel.shp',
                'remarq': workspace/'data/2014_bati/bati_remarquable.shp',
                'surfac': workspace/'data/2014_bati/construction_surfacique.shp',
                'aerodr': workspace/'data/2014_bati/piste_aerodrome.shp',
                'sport': workspace/'data/2014_bati/terrain_sport.shp'
            }
            argList = []
            for k, v in buildStatDic.items():
                argList.append((k, str(v), iris, grid, workspace/'data'/pixResStr/'urb_csv/'))
            for k, v in buildStatDic.items():
                argList.append((k, str(v).replace('2014','2009'), iris, grid, workspace/'data'/pixResStr/'urb_csv/'))
            del buildStatDic

            if speed:
                getDone(urbGridStat, argList)
            else:
                for a in argList:
                    urbGridStat(*a)
            log.write(getTime(start_time) + '\n')

        if not (workspace/'data'/pixResStr/'csv').exists():
            os.mkdir(str(workspace/'data'/pixResStr/'csv'))
            start_time = time()
            etape = 5
            description = "estimating the population in the grid "
            progres = "%i/8 : %s" %(etape, description)
            printer(progres)
            log.write(description + ': ')

            grid = QgsVectorLayer(str(workspace/'data'/pixResStr/'grid.shp'), 'grid')
            iris = QgsVectorLayer(str(workspace/'data/iris.shp'))
            iris.addExpressionField('$id + 1', QgsField('ID_IRIS', QVariant.Int, len=4))
            batiInterIris = QgsVectorLayer(str(workspace/'data/2014_bati/bati_inter_iris.shp'))
            popGridStat(batiInterIris, grid, iris, workspace/'data'/pixResStr, workspace/'data'/pixResStr/'urb_csv/')
            del grid, iris
            log.write(getTime(start_time) + '\n')

        if not (workspace/'data'/pixResStr/'restrict').exists():
            os.mkdir(str(workspace/'data'/pixResStr/'restrict'))
            start_time = time()
            etape = 6
            description = "computing restriction and interest rasters "
            progres = "%i/8 : %s" %(etape, description)
            printer(progres)
            log.write(description + ': ')

            # Création de la grille de restriction
            grid = QgsVectorLayer(str(workspace/'data'/pixResStr/'grid.shp'), 'grid')
            b_removed = QgsVectorLayer(str(workspace/'data/restriction/bati_removed.shp'), 'b_removed')
            cimetiere = QgsVectorLayer(str(workspace/'data/2014_bati/cimetiere.shp'), 'cimetiere')
            s_eau = QgsVectorLayer(str(workspace/'data/restriction/surface_eau.shp'), 's_eau')

            restrictList = [b_removed, cimetiere, s_eau]
            restrictGrid(restrictList, grid, maxOverlapRatio, workspace/'data'/pixResStr/'restrict')
            del b_removed, cimetiere, s_eau, restrictList, grid

        # if not (workspace/'data'/pixResStr/'tif').exists():
        #     start_time = time()
        #     description = "computing interest rasters "
        #     progres = "6.5/8 : %s"%(description)
        #     printer(progres)
            os.mkdir(str(workspace/'data'/pixResStr/'tif'))
            os.mkdir(str(workspace/'data'/pixResStr/'tif/tmp'))
            # Objet pour transformation de coordonées
            l93 = QgsCoordinateReferenceSystem()
            l93.createFromString('EPSG:2154')
            laea = QgsCoordinateReferenceSystem()
            laea.createFromString('EPSG:3035')
            trCxt = QgsCoordinateTransformContext()
            coordTr = QgsCoordinateTransform(l93, laea, trCxt)
            # BBOX pour extraction du MNT
            grid = QgsVectorLayer(str(workspace/'data'/pixResStr/'stat_grid.shp'), 'grid')
            extent = grid.extent()
            extentL93 = coordTr.transform(extent, coordTr.ReverseTransform)
            # Extraction des tuiles MNT dans la zone d'étude
            demList = demExtractor(globalData/'rge'/dpt/'bdalti', extentL93)
            xMin = extent.xMinimum()
            yMin = extent.yMinimum()
            xMax = extent.xMaximum()
            yMax = extent.yMaximum()

            # Fusion des tuiles et reprojection
            gdal.Warp(
                str(workspace/'data'/pixResStr/'tif/mnt.tif'), demList,
                format='GTiff', outputType=gdal.GDT_Float32,
                xRes=pixRes, yRes=pixRes,
                resampleAlg='cubicspline',
                srcSRS='EPSG:2154', dstSRS='EPSG:3035',
                outputBounds=(xMin, yMin, xMax, yMax),
                srcNodata=-99999
            )
            # Calcul de pente en %
            gdal.DEMProcessing(
                str(workspace/'data'/pixResStr/'tif/slope.tif'),
                str(workspace/'data'/pixResStr/'tif/mnt.tif'),
                'slope', format='GTiff',
                slopeFormat='percent'
            )

            # Chaîne à passer à QGIS pour l'étendue des rasterisations
            extentStr = str(xMin) + ',' + str(xMax) + ',' + str(yMin) + ',' + str(yMax) + ' [EPSG:3035]'

            # Rasterisations
            argList = [
                (workspace/'data/transport/routes.shp', workspace/'data'/pixResStr/'tif/routes.tif', 'Byte', None, 1),
                (workspace/'data/transport/arrets_transport.shp', workspace/'data'/pixResStr/'tif/arrets_transport.tif', 'Byte', None, 1),
                (workspace/'data'/pixResStr/'restrict/restrict_grid.shp', workspace/'data'/pixResStr/'tif/restrict_grid.tif', 'Byte', 'restrict'),
                (workspace/'data'/pixResStr/'stat_iris.shp', workspace/'data'/pixResStr/'tif/masque.tif', 'Byte', None, 1, True),
                (workspace/'data/restriction/tampon_voies_ferrees.shp', workspace/'data'/pixResStr/'tif/tampon_voies_ferrees.tif', 'Byte', None, 1),
                (workspace/'data/restriction/tampon_autoroutes.shp', workspace/'data'/pixResStr/'tif/tampon_autoroutes.tif', 'Byte', None, 1),
                (workspace/'data/restriction/tampon_routes_importantes.shp', workspace/'data'/pixResStr/'tif/tampon_routes_importantes.tif', 'Byte', None, 1),
                (workspace/'data/restriction/zonages_protection.shp', workspace/'data'/pixResStr/'tif/zonages_protection.tif', 'Byte', None, 1),
                (workspace/'data/pai/surf_activ_non_com.shp', workspace/'data'/pixResStr/'tif/surf_activ_non_com.tif', 'Byte', None, 1)
            ]

            if (workspace/'data/restriction/exclusion_parcelles.shp').exists():
                argList.append((workspace/'data/restriction/exclusion_parcelles.shp', workspace/'data'/pixResStr/'tif/exclusion_parcelles.tif', 'Byte', None, 1))
            if (workspace/'data/restriction/exclusion_manuelle.shp').exists():
                argList.append((workspace/'data/restriction/exclusion_manuelle.shp', workspace/'data'/pixResStr/'tif/exclusion_manuelle.tif', 'Byte', None, 1))

            if (workspace/'data/restriction/ppri.shp').exists():
                argList.append((workspace/'data/restriction/ppri.shp', workspace/'data'/pixResStr/'tif/ppri.tif', 'Byte', None, 1))

            # Solution de repli si on a les zonnes PPRI dans le PLU
            elif (workspace/'data/plu.shp').exists():
                layer = QgsVectorLayer(str(workspace/'data/plu.shp'), 'plu')
                fields = list(f.name() for f in layer.fields())
                if 'ppri' in fields:
                    argList.append((workspace/'data/plu.shp', workspace/'data'/pixResStr/'tif/ppri.tif', 'Byte', 'ppri'))
                del layer, fields

            if (workspace/'data/restriction/compensation.shp').exists():
                argList.append((workspace/'data/restriction/compensation.shp', workspace/'data'/pixResStr/'tif/compensation.tif', 'Byte', None, 1))

            # Découpe du tif d'intérêt écologique si il a été traité lors de l'étape 1
            if (workspace/'data/ecologie.tif').exists():
                gdal.Warp(
                    str(workspace/'data'/pixResStr/'tif/ecologie.tif'), str(workspace/'data/ecologie.tif'),
                    format='GTiff', outputType=gdal.GDT_Float32,
                    xRes=pixRes, yRes=pixRes,
                    outputBounds=(xMin, yMin, xMax, yMax)
                )
            elif (workspace/'data/ecologie.shp').exists():
                argList.append((workspace/'data/ecologie.shp', workspace/'data'/pixResStr/'tif/ecologie.tif', 'Float32', 'taux'))

            if speed:
                getDone(rasterize, argList)
            else:
                for a in argList:
                    rasterize(*a)

            # Calcul des rasters de distance
            params = {
                'INPUT': str(workspace/'data'/pixResStr/'tif/routes.tif'),
                'BAND': 1,
                'VALUES': 1,
                'UNITS': 0,
                'NODATA': -1,
                'MAX_DISTANCE': roadDist,
                'DATA_TYPE': 5,
                'OUTPUT': str(workspace/'data'/pixResStr/'tif/distance_routes.tif')
            }
            processing.run('gdal:proximity', params, feedback=feedback)

            params['INPUT'] = str(workspace/'data'/pixResStr/'tif/arrets_transport.tif')
            params['MAX_DISTANCE'] = transDist
            params['OUTPUT'] = str(workspace/'data'/pixResStr/'tif/distance_arrets_transport.tif')
            processing.run('gdal:proximity', params, feedback=feedback)

            # Calcul des rasters de densité
            projwin = str(xMin) + ',' + str(xMax) + ',' + str(yMin) + ',' + str(yMax)
            with (globalData/'sirene/distances.csv').open('r') as csvFile:
                reader = csv.reader(csvFile)
                next(reader, None)
                distancesSirene = {rows[0]:int(rows[1]) for rows in reader}

            for k, v in distancesSirene.items():
                layer = QgsVectorLayer(str(workspace/('data/geosirene/type_' + k + '.shp')), k)
                layer.setExtent(extent)
                params = {
                    'INPUT': layer,
                    'RADIUS': v,
                    'PIXEL_SIZE': pixRes,
                    'KERNEL': 0,
                    'OUTPUT_VALUE': 0,
                    'OUTPUT': str(workspace/'data'/pixResStr/('tif/tmp/densite_' + k + '.tif'))
                }
                processing.run('qgis:heatmapkerneldensityestimation', params, feedback=feedback)

                params = {
                    'INPUT': str(workspace/'data'/pixResStr/('tif/tmp/densite_' + k + '.tif')),
                    'PROJWIN': projwin,
                    'NODATA': -9999,
                    'DATA_TYPE': 5,
                    'OUTPUT': str(workspace/'data'/pixResStr/('tif/densite_' + k + '.tif'))
                }
                processing.run('gdal:cliprasterbyextent', params, feedback=feedback)

            del projwin, distancesSirene
            rmtree(str(workspace/'data'/pixResStr/'tif/tmp'))
            log.write(getTime(start_time) + '\n')

        if not (workspace/'data'/pixResStr/'fitting').exists():
            start_time = time()
            etape = 7
            description = "trying to fit floors and surfaces distributions "
            progres = "%i/8 : %s" %(etape, description)
            printer(progres)
            log.write(description + ': ')

            argList = []
            os.mkdir(str(workspace/'data'/pixResStr/'fitting'))
            scriptDir = Path(__file__).absolute().parent

            subprocess.run('Rscript ' + str(scriptDir/'fitting/fit_floors.R') + ' ' + str(workspace/'data'/pixResStr)
                        +  ' > ' + str(workspace/'data'/pixResStr/'fitting/Rlog_floors.txt'), shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run('Rscript ' + str(scriptDir/'fitting/fit_surf.R') + ' ' + str(workspace/'data'/pixResStr)
                        +  ' > ' + str(workspace/'data'/pixResStr/'fitting/Rlog_surf.txt'), shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log.write(getTime(start_time) + '\n')

        else:
            fitResults = os.listdir(str(workspace/'data'/pixResStr/'fitting'))
            if 'floors_weights.csv' not in fitResults or 'surf_weights.csv' not in fitResults:
                start_time = time()
                etape = 7
                description = "trying to fit floors and surfaces distributions "
                progres = "%i/8 : %s" %(etape, description)
                printer(progres)
                log.write(description + ': ')

                scriptDir = Path(__file__).absolute().parent
                if 'floors_weights.csv' not in fitResults:
                    subprocess.run('Rscript ' + str(scriptDir/'fitting/fit_floors.R') + ' ' + str(workspace/'data'/pixResStr)
                                +  ' > ' + str(workspace/'data'/pixResStr/'fitting/Rlog_floors.txt'), shell=True)

                if 'surf_weights.csv' not in fitResults:
                    subprocess.run('Rscript ' + str(scriptDir/'fitting/fit_surf.R') + ' ' + str(workspace/'data'/pixResStr)
                                +  ' > ' + str(workspace/'data'/pixResStr/'fitting/Rlog_surf.txt'), shell=True)
                    log.write(getTime(start_time) + '\n')

                log.write(getTime(start_time) + '\n')

        start_time = time()
        etape = 8
        description = "finalizing... "
        progres = "%i/8 : %s" %(etape, description)
        printer(progres)
        log.write(description + ': ')

        try:
            copyfile(str(workspace/'data'/pixResStr/'fitting/surf_weights.csv'), str(project/'poids_surfaces.csv'))
            copyfile(str(workspace/'data'/pixResStr/'fitting/floors_weights.csv'), str(project/'poids_etages.csv'))
            copyfile(str(workspace/'data'/pixResStr/'fitting/surf_weights_nofit.csv'), str(project/'poids_surfaces_nofit.csv'))
            copyfile(str(workspace/'data'/pixResStr/'fitting/floors_weights_nofit.csv'), str(project/'poids_etages_nofit.csv'))
        except FileNotFoundError:
            print('\nFitted distributions are missing, please check the R scripts logfiles in ' + str(workspace/'data'/pixResStr/'fitting'))
            sys.exit()

        # Calcul de la population totale de la zone pour export en csv
        pop09 = 0
        pop12 = 0
        pop14 = 0
        iris = QgsVectorLayer(str(workspace/'data'/pixResStr/'stat_iris.shp'))
        for feat in iris.getFeatures():
            pop09 += feat.attribute('POP09')
            pop12 += feat.attribute('POP12')
            pop14 += feat.attribute('POP14')
        with (project/'population.csv').open('w') as w:
            w.write('annee, demographie\n')
            w.write('2009, ' + str(pop09) + '\n')
            w.write('2012, ' + str(pop12) + '\n')
            w.write('2014, ' + str(pop14) + '\n')
        del iris

        grid = QgsVectorLayer(str(workspace/'data'/pixResStr/'stat_grid.shp'), 'grid')
        extent = grid.extent()
        xMin = extent.xMinimum()
        yMin = extent.yMinimum()
        xMax = extent.xMaximum()
        yMax = extent.yMaximum()
        extentStr = str(xMin) + ',' + str(xMax) + ',' + str(yMin) + ',' + str(yMax) + ' [EPSG:3035]'

        os.mkdir(str(project/'interet'))
        # Rasterisations
        argList = [
            (workspace/'data'/pixResStr/'stat_iris.shp', project/'iris_id.tif', 'UInt8', 'ID_IRIS'),
            (workspace/'data'/pixResStr/'stat_iris.shp', project/'iris_ssr_med.tif', 'UInt16', 'ssr_med'),
            (workspace/'data'/pixResStr/'stat_iris.shp', project/'iris_tx_ssr.tif', 'Float32', 'tx_ssr'),
            (workspace/'data'/pixResStr/'stat_iris.shp', project/'iris_m2_hab.tif', 'UInt16', 'm2_hab'),
            (workspace/'data'/pixResStr/'stat_grid.shp', project/'demographie.tif', 'UInt16', 'pop'),
            (workspace/'data'/pixResStr/'stat_grid.shp', project/'srf_pla.tif', 'UInt32', 'srf_pla'),
            (workspace/'data'/pixResStr/'stat_grid.shp', project/'srf_sol_res.tif', 'UInt16', 'ssol_res'),
            (workspace/'data'/pixResStr/'stat_grid.shp', project/'srf_sol.tif', 'UInt16', 'ssol_14'),
            (workspace/'data/ocsol.shp', project/'classes_ocsol.tif', 'UInt16', 'code_orig')
        ]
        if (workspace/'data/plu.shp').exists():
            argList.append((workspace/'data/plu.shp', project/'interet/plu_restriction.tif', 'Byte', 'restrict'))
            argList.append((workspace/'data/plu.shp', project/'interet/plu_priorite.tif', 'Byte', 'priority'))

        if speed :
            getDone(rasterize, argList)
        else:
            for a in argList:
                rasterize(*a)

        # Création des variables GDAL indispensables pour la fonction to_tif()
        ds = gdal.Open(str(project/'demographie.tif'))
        proj = ds.GetProjection()
        geot = ds.GetGeoTransform()
        ds = None

        # Conversion des rasters de distance
        distance_routes = to_array(workspace/'data'/pixResStr/'tif/distance_routes.tif', np.float32)
        routes = np.where(distance_routes > -1, 1 - (distance_routes / np.amax(distance_routes)), 0)
        distance_transport = to_array(workspace/'data'/pixResStr/'tif/distance_arrets_transport.tif', np.float32)
        transport = np.where(distance_transport > -1, 1 - (distance_transport / np.amax(distance_transport)), 0)
        # Conversion et aggrégation des rasters de densité SIRENE
        with (globalData/'sirene/poids.csv').open('r') as csvFile:
            reader = csv.reader(csvFile)
            next(reader, None)
            poidsSirene = {rows[0]:int(rows[1]) for rows in reader}
        administratif = to_array(workspace/'data'/pixResStr/'tif/densite_administratif.tif', np.float32)
        commercial = to_array(workspace/'data'/pixResStr/'tif/densite_commercial.tif', np.float32)
        enseignement = to_array(workspace/'data'/pixResStr/'tif/densite_enseignement.tif', np.float32)
        medical = to_array(workspace/'data'/pixResStr/'tif/densite_medical.tif', np.float32)
        recreatif = to_array(workspace/'data'/pixResStr/'tif/densite_recreatif.tif', np.float32)
        # Normalisation des valeurs entre 0 et 1
        administratif = np.where(administratif != -9999, administratif / np.amax(administratif), 0)
        commercial = np.where(commercial != -9999, commercial / np.amax(commercial), 0)
        enseignement = np.where(enseignement != -9999, enseignement / np.amax(enseignement), 0)
        medical = np.where(medical != -9999, medical / np.amax(medical), 0)
        recreatif = np.where(recreatif != -9999, recreatif / np.amax(recreatif), 0)
        # Pondération
        sirene = ((administratif * poidsSirene['administratif']) + (commercial * poidsSirene['commercial']) + (enseignement * poidsSirene['enseignement']) +
                  (medical * poidsSirene['medical']) + (recreatif * poidsSirene['recreatif'])) / sum(poidsSirene.values())
        sirene = (sirene / np.amax(sirene)).astype(np.float32)

        # Création du raster de restriction (sans PLU)
        irisMask = to_array(workspace/'data'/pixResStr/'tif/masque.tif', np.byte)
        surfActivMask = to_array(workspace/'data'/pixResStr/'tif/surf_activ_non_com.tif', np.byte)
        gridMask = to_array(workspace/'data'/pixResStr/'tif/restrict_grid.tif', np.byte)
        zonageMask = to_array(workspace/'data'/pixResStr/'tif/zonages_protection.tif', np.byte)
        highwayMask = to_array(workspace/'data'/pixResStr/'tif/tampon_autoroutes.tif', np.byte)
        roadsMask = to_array(workspace/'data'/pixResStr/'tif/tampon_routes_importantes.tif', np.byte)
        railsMask = to_array(workspace/'data'/pixResStr/'tif/tampon_voies_ferrees.tif', np.byte)
        slope = to_array(str(workspace/'data'/pixResStr/'tif/slope.tif'))
        slopeMask = np.where(slope > maxSlope, 1, 0).astype(np.byte)
        # Fusion
        restriction = np.where((irisMask == 1) | (surfActivMask == 1) | (gridMask == 1) | (roadsMask == 1) |
                               (railsMask == 1) | (zonageMask == 1) | (highwayMask == 1) | (slopeMask == 1), 1, 0)

        if (workspace/'data'/pixResStr/'tif/ppri.tif').exists():
            ppriMask = to_array(workspace/'data'/pixResStr/'tif/ppri.tif', np.byte)
            restriction = np.where(ppriMask == 1, 1, restriction)

        if (workspace/'data'/pixResStr/'tif/exclusion_manuelle.tif').exists():
            exclusionManuelle = to_array(workspace/'data'/pixResStr/'tif/exclusion_manuelle.tif', np.byte)
            restriction = np.where(exclusionManuelle == 1, 1, restriction)

        if (workspace/'data'/pixResStr/'tif/compensation.tif').exists():
            compMask = to_array(workspace/'data'/pixResStr/'tif/compensation.tif', np.byte)
            restriction = np.where(compMask == 1, 1, restriction)

        # Traitement de l'intérêt écologique
        if (workspace/'data'/pixResStr/'tif/ecologie.tif').exists():
            ecologie = to_array(workspace/'data'/pixResStr/'tif/ecologie.tif', np.float32)
            ecologie = np.where((ecologie == 0), 1, 1 - ecologie)
            to_tif(ecologie, 'float32', proj, geot, project/'interet/non-importance_ecologique.tif')
        else:
            rasterize(workspace/'data/ocsol.shp', project/'interet/non-importance_ecologique.tif', 'Float32', 'interet')

        # Utilisation de l'OCSOL pour la restriction si la résolution le permet (ici spécifique à MTP)
        if pixRes == 20:
            if studyAreaName == 'mtp':
                ocs = to_array(project/'classes_ocsol.tif', np.uint16)
                ocsMask = np.where((ocs == 2) | (ocs == 4) | (ocs == 8), 1, 0)
                restriction = np.where(ocsMask == 1, 1, restriction)

        to_tif(restriction, 'byte', proj, geot, project/'interet/restriction_totale.tif')
        to_tif(sirene, 'float32', proj, geot, project/'interet/densite_sirene.tif')
        to_tif(routes, 'float32', proj, geot, project/'interet/proximite_routes.tif')
        to_tif(transport, 'float32', proj, geot, project/'interet/proximite_transport.tif')

        copyfile(str(localData/'poids.csv'), str(project/'interet/poids.csv'))
        copyfile(str(workspace/'data'/pixResStr/'evo_surface_sol.csv'), str(project/'evo_surface_sol.csv'))

        print('\nFinished at ' + strftime('%H:%M:%S'))
        log.write(getTime(start_time) + '\n')
        if truth:
            print('Removing temporary data!')
            rmtree(str(workspace))

    except:
        exc = sys.exc_info()
        print("\n*** Error :")
        traceback.print_exception(*exc, limit=5, file=sys.stdout)
        traceback.print_exception(*exc, limit=5, file=log)
        sys.exit()

qgs.exitQgis()
