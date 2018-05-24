#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import sys
import gdal
import numpy as np
import pandas as pd
from time import strftime
from ast import literal_eval
from shutil import rmtree, copyfile

# Ignorer les erreurs de numpy lors d'une division par 0
np.seterr(divide='ignore', invalid='ignore')

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

# Import des paramètres d'entrée
globalDataPath = os.path.abspath(sys.argv[1])
codeDept = sys.argv[2]
localDataPath = os.path.abspath(sys.argv[3])
outputDataPath = os.path.abspath(sys.argv[4])
if len(sys.argv) > 5:
    argList = sys.argv[5].split()
    # Interprétation de la chaîne de paramètres
    for arg in argList :
        # Taille de la grille / résolution des rasters
        if 'gridSize' in arg:
            gridSize = arg.split("=")[1]
            if not 200 >= int(gridSize) >= 20:
                print('La taille de la grille doit être comprise entre 10m et 100m')
                sys.exit()
        # Taille du tampon utilisé pour extraire les iris et pour extraire la donnée utile au delà des limites de la zone (comme les points SIRENE)
        if 'bufferDistance' in arg:
            bufferDistance = int(arg.split('=')[1])
        # Surfaces au sol minimales et maximales pour considérer un bâtiment comme habitable
        if 'minSurf' in arg:
            minSurf = int(arg.split('=')[1])
        if 'maxSurf' in arg:
            maxSurf = int(arg.split('=')[1])
        # Utilisation du taux de résidence principales pour réduire la surface plancher estimée
        if 'useTxrp' in arg:
            useTxrp = literal_eval(arg.split('=')[1])
        # Hauteur théorique d'un étage pour l'estimation du nombre de niveaux
        if 'levelHeight' in arg:
            levelHeight = int(arg.split('=')[1])
        # Taux maximum de chevauchement entre les cellules et des couches à exclure (ex: bati industriel)
        if 'maxOverlapRatio' in arg:
            maxOverlapRatio = float(arg.split('=')[1])
        # Paramètres variables pour la création des rasters de distance
        if 'roadDist' in arg:
            roadDist = int(arg.split('=')[1])
        if 'transDist' in arg:
            transDist = int(arg.split('=')[1])
        # Seuil de pente en % pour interdiction à la construction
        if 'maxSlope' in arg:
            maxSlope = int(arg.split('=')[1])
        if 'force' in arg:
            force = True

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
    useTxrp = True
if 'levelHeight' not in globals():
    levelHeight = 3
if 'maxOverlapRatio' not in globals():
    maxOverlapRatio = 0.1
if 'roadDist' not in globals():
    roadDist = 200
if 'transDist' not in globals():
    transDist = 300
if 'maxSlope' not in globals():
    maxSlope = 30
if 'force' not in globals():
    force = False

if force and os.path.exists(outputDataPath):
    rmtree(outputDataPath)
studyAreaName = localDataPath.split('/')[len(localDataPath.split('/'))-1]
workspacePath = outputDataPath  + '/' + codeDept + '/' + studyAreaName + '/'
projectPath = 'simulation/' + gridSize + 'm/'
if not os.path.exists(workspacePath):
    os.makedirs(workspacePath)
os.chdir(workspacePath)

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
def to_shp(layer, path):
    writer = QgsVectorFileWriter(
        path, 'utf-8', layer.fields(), layer.wkbType(), layer.sourceCrs(), 'ESRI Shapefile')
    writer.addFeatures(layer.getFeatures())

# Enregistre un fichier .tif à partir d'un array et de variables GDAL stockée au préalable
def to_tif(array, dtype, path):
    ds_out = driver.Create(path, cols, rows, 1, dtype)
    ds_out.SetProjection(proj)
    ds_out.SetGeoTransform(geot)
    ds_out.GetRasterBand(1).WriteArray(array)
    ds_out = None

# Convertit un tif en numpy array
def to_array(tif, dtype=None):
    ds = gdal.Open(tif)
    if dtype == 'float32':
        return ds.ReadAsArray().astype(np.float32)
    elif dtype == 'uint16':
        return ds.ReadAsArray().astype(np.uint16)
    else:
        return ds.ReadAsArray()
    ds = None

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
    return res['OUTPUT']
    del buildings, polygons, points, layer

# Génère un csv contenant la matrice de contiguïté par ID et la population de départ
def contiguityMatrix(iris, outcsv=None):
    irisDf = pd.DataFrame(None, [i for i in range(iris.featureCount())], [
        'id', 'code', 'nom', 'population', 'contiguite'])
    for i in range(iris.featureCount()):
        feat = iris.getFeature(i)
        irisDf.id[i] = feat.attribute('ID')
        irisDf.code[i] = feat.attribute('CODE_IRIS')
        irisDf.nom[i] = feat.attribute('NOM_IRIS')
        irisDf.population[i] = feat.attribute('POP14')
        irisDf.contiguite[i] = []
        for poly in iris.getFeatures():
            if feat.geometry().touches(poly.geometry()):
                irisDf.contiguite[i].append(poly.attribute('ID'))
    if outcsv:
        irisDf.to_csv(outcsv, index=0)
    else:
        return irisDf

# Selection des tuiles MNT dans la zone d'étude sous forme de liste
def demExtractor(directory, bbox):
    tileList = []
    for tile in os.listdir(directory):
        if os.path.splitext(tile)[1] == '.asc':
            path = directory + tile
            with open(path) as file:
                for i in range(5):
                    line = file.readline()
                    if i == 0:
                        res = re.search('[a-z]*\s*([0-9]*)', line)
                        xSize = int(res.group(1))
                    if i == 1:
                        res = re.search('[a-z]*\s*([0-9]*)', line)
                        ySize = int(res.group(1))
                    if i == 2:
                        res = re.search('[a-z]*\s*([0-9.]*)', line)
                        xMin = float(res.group(1))
                    if i == 3:
                        res = re.search('[a-z]*\s*([0-9.]*)', line)
                        yMin = float(res.group(1))
                    if i == 4:
                        res = re.search('[a-z]*\s*([0-9.]*)', line)
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

# Intersection entre la couche de bâti nettoyée jointe aux iris et la grille avec calcul et jointure des statistiques
#def statGridIris(buildings, csvList, grid, iris, outdir):
def statGridIris(buildings, grid, iris, outdir):
    csvGrid = []
    csvIris = []
    grid.dataProvider().createSpatialIndex()
    buildings.dataProvider().createSpatialIndex()
    buildings.addExpressionField('$area', QgsField(
        'area_i', QVariant.Double, len=10, prec=2))
    expr = ' ("area_i" * "NB_NIV") '
    if useTxrp :
        expr +=  '* "TXRP14"'
    buildings.addExpressionField(expr, QgsField(
        'planch', QVariant.Double, len=10, prec=2))
    expr = ' ("planch" / sum("planch", group_by:="CODE_IRIS")) * "POP14" '
    buildings.addExpressionField(expr, QgsField(
        'pop_bati', QVariant.Double, len=10, prec=2))
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
    buildings.addExpressionField('$area', QgsField(
        'area_g', QVariant.Double, len=10, prec=2))
    expr = ' ("area_g" * "NB_NIV") '
    if useTxrp:
        expr += '* "TXRP14"'
    buildings.addExpressionField(expr, QgsField(
        'planch_g', QVariant.Double, len=10, prec=2))
    expr = ' "area_g" / "area_i" * "pop_bati" '
    buildings.addExpressionField(expr, QgsField(
        'pop_cell', QVariant.Double, len=10, prec=2))
    expr = ' "planch_g" / "pop_cell" '
    buildings.addExpressionField(expr, QgsField(
        'nb_m2_hab', QVariant.Double, len=10, prec=2))

    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'pop_cell',
        'CATEGORIES_FIELD_NAME': 'id_2',
        'OUTPUT': outdir + 'csv/pop_grid.csv'
    }
    processing.run('qgis:statisticsbycategories',
                   params, feedback=feedback)
    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'nb_m2_hab',
        'CATEGORIES_FIELD_NAME': 'CODE_IRIS',
        'OUTPUT': outdir + 'csv/nb_m2_iris.csv'
    }
    processing.run('qgis:statisticsbycategories',
                   params, feedback=feedback)
    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'planch_g',
        'CATEGORIES_FIELD_NAME': 'id_2',
        'OUTPUT': outdir + 'csv/srf_pl_grid.csv'
    }
    processing.run('qgis:statisticsbycategories',
                   params, feedback=feedback)
    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'planch_g',
        'CATEGORIES_FIELD_NAME': 'CODE_IRIS',
        'OUTPUT': outdir + 'csv/srf_pl_iris.csv'
    }
    processing.run('qgis:statisticsbycategories',
                   params, feedback=feedback)

    to_shp(buildings, outdir + 'bati_inter_grid.shp')
    del buildings, res

    # Correction et changement de nom pour jointure des stat sur la grille et les IRIS
    csvPlanchI = QgsVectorLayer(
        outdir + 'csv/srf_pl_iris.csv')
    csvPlanchI.addExpressionField(
        'to_real("q3")', QgsField('SP_Q3', QVariant.Double))
    csvPlanchI.addExpressionField(
        'to_real("max")', QgsField('SP_MAX', QVariant.Double))
    csvPlanchI.addExpressionField(
        'to_real("sum")', QgsField('SP_SUM', QVariant.Double))
    csvIris.append(csvPlanchI)

    csvPlanchG = QgsVectorLayer(
        outdir + 'csv/srf_pl_grid.csv')
    csvPlanchG.addExpressionField(
        'to_real("sum")', QgsField('srf_p', QVariant.Double))
    csvGrid.append(csvPlanchG)

    csvM2I = QgsVectorLayer(
        outdir + 'csv/nb_m2_iris.csv')
    csvM2I.addExpressionField(
        'to_real("mean")', QgsField('M2_HAB', QVariant.Double))
    csvIris.append(csvM2I)

    csvPopG = QgsVectorLayer(
        outdir + 'csv/pop_grid.csv')
    csvPopG.addExpressionField(
        'to_real("sum")', QgsField('pop', QVariant.Double))
    csvGrid.append(csvPopG)

    # for csv in csvList:
    #     year = csv.name()
    #     csv.addExpressionField('to_real("sum")', QgsField(year + '_SB_SOL', QVariant.Double))
    #     csvIris.append(csv)

    statBlackList = ['count', 'unique', 'min', 'max', 'range', 'sum',
                     'mean', 'median', 'stddev', 'minority', 'majority', 'q1', 'q3', 'iqr']

    for csv in csvGrid:
        join(grid, 'id', csv, 'id_2', statBlackList)
    for csv in csvIris:
        join(iris, 'CODE_IRIS', csv, 'CODE_IRIS', statBlackList)

    to_shp(grid, outdir + '/stat_grid.shp')

    # iris.addExpressionField(' "09_SB_SOL" / "POP09"',
    #                         QgsField('M2S_H_09', QVariant.Double))
    # iris.addExpressionField(' "14_SB_SOL" / "POP14"',
    #                         QgsField('M2S_H_14', QVariant.Double))
    # iris.addExpressionField(
    #     ' ("M2S_H_14" - "M2S_H_09") / "M2S_H_09" / 5 * 100 ', QgsField('EVM2H0914', QVariant.Double))
    iris.addExpressionField('$id + 1', QgsField('ID', QVariant.Int, len=4))
    to_shp(iris, outdir + '/stat_iris.shp')

# Crée une grille avec des statistiques par cellule sur la surface couverte pour chaque couche en entrée
def restrictGrid(layerList, grid, ratio, outdir):
    grid.dataProvider().createSpatialIndex()
    csvList = []
    fieldList = []
    statBlackList = ['count', 'unique', 'min', 'max', 'range', 'sum',
                     'mean', 'median', 'stddev', 'minority', 'majority', 'q1', 'q3', 'iqr']

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
        csv = QgsVectorLayer(
            outdir + 'csv/restriction_' + name + '.csv')
        csv.addExpressionField(
            'to_real("sum")', QgsField(name, QVariant.Double))
        csvList.append(csv)
        del layer, res

    for csv in csvList:
        join(grid, 'id', csv, 'id_2', statBlackList)
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
                expr += '"' + field + \
                    '" >= ($area * ' + str(ratio) + '), 1, 0)'

    grid.addExpressionField(expr, QgsField('restrict', QVariant.Int))
    to_shp(grid, outdir + 'restrict_grid.shp')
    del fieldList, csvList

# Jointure avec données INSEE et extraction des IRIS dans la zone
def irisExtractor(iris, overlay, csvdir, outdir):
    # Conversion des chaînes en nombre
    csvPop09 = QgsVectorLayer(
        csvdir + 'inseePop09.csv')
    csvPop09.addExpressionField(
        'round(to_real("P09_POP"))', QgsField('POP09', QVariant.Int))
    csvPop12 = QgsVectorLayer(
        csvdir + 'inseePop12.csv')
    csvPop12.addExpressionField(
        'round(to_real("P12_POP"))', QgsField('POP12', QVariant.Int))
    csvPop14 = QgsVectorLayer(
        csvdir + 'inseePop14.csv')
    csvPop14.addExpressionField(
        'round(to_real("P14_POP"))', QgsField('POP14', QVariant.Int))
    csvLog14 = QgsVectorLayer(
        csvdir + 'inseeLog14.csv')
    csvLog14.addExpressionField(
        'to_real("P14_TXRP")', QgsField('TXRP14', QVariant.Double))

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
        plu.addExpressionField(expr, QgsField(
            'classe', QVariant.String, len=3))
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
        plu.addExpressionField(expr, QgsField(
            'restrict', QVariant.Int, len=1))
        expr = """
                IF ("type" LIKE '%AU%'
                OR "coment" LIKE '%urbanisation future%'
                OR "coment" LIKE '%ouvert_ à l_urbanisation%'
                OR "coment" LIKE '% destinée à l_urbanisation%', 1, 0)
            """
        plu.addExpressionField(expr, QgsField(
            'priority', QVariant.Int, len=1))
        expr = """ IF ("coment" LIKE '% protection contre risques naturels', 1, 0) """
        plu.addExpressionField(expr, QgsField(
            'ppr', QVariant.Int, len=1))

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
    geosirene.addExpressionField(
        expr, QgsField('type', QVariant.String, len=20))

    params = {'INPUT': geosirene, 'FIELD': 'type', 'OUTPUT': outpath }
    processing.run('qgis:splitvectorlayer', params, feedback=feedback)

print('Commencé à ' + strftime('%H:%M:%S'))

# Découpe et reprojection de la donnée en l'absence du dossier ./data
if not os.path.exists('data'):
    os.mkdir('data')
    # Tampon de 1000m autour de la zone pour extractions des quartiers et des PAI
    zone = QgsVectorLayer(localDataPath + '/zone.shp', 'zone')
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
    iris = QgsVectorLayer(globalDataPath + '/rge/IRIS_GE.SHP', 'iris')
    iris.dataProvider().createSpatialIndex()
    irisExtractor(iris, zone_buffer, globalDataPath + '/insee/csv/', 'data/')
    # Extractions et reprojections
    os.mkdir('data/2016_bati')
    clipBati = [
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/BATI_INDIFFERENCIE.SHP',
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/BATI_INDUSTRIEL.SHP',
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/BATI_REMARQUABLE.SHP',
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/CIMETIERE.SHP',
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/CONSTRUCTION_LEGERE.SHP',
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/CONSTRUCTION_SURFACIQUE.SHP',
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/PISTE_AERODROME.SHP',
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/RESERVOIR.SHP',
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/TERRAIN_SPORT.SHP'
    ]
    for path in clipBati:
        reproj(clip(path, zone), 'data/2016_bati/')

    os.mkdir('data/2009_bati')
    i = 0
    for path in clipBati:
        path = path.replace('2016', '2009')
        clipBati[i] = path
        i += 1
    for path in clipBati:
        reproj(clip(path, zone), 'data/2009_bati/')

    os.mkdir('data/pai')
    clipPai = [
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/PAI_ADMINISTRATIF_MILITAIRE.SHP',
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/PAI_CULTURE_LOISIRS.SHP',
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/PAI_ESPACE_NATUREL.SHP',
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/PAI_INDUSTRIEL_COMMERCIAL.SHP',
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/PAI_RELIGIEUX.SHP',
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/PAI_SANTE.SHP',
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/PAI_SCIENCE_ENSEIGNEMENT.SHP',
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/PAI_SPORT.SHP',
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/PAI_TRANSPORT.SHP'
    ]
    for path in clipPai:
        reproj(clip(path, zone_buffer), 'data/pai/')
    reproj(clip(globalDataPath + '/rge/' + codeDept +
                '/bdtopo_2016/SURFACE_ACTIVITE.SHP', zone), 'data/pai/')

    os.mkdir('data/transport')
    clipRes = [
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/ROUTE_PRIMAIRE.SHP',
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/ROUTE_SECONDAIRE.SHP',
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/TRONCON_VOIE_FERREE.SHP',
        globalDataPath + '/rge/' + codeDept + '/bdtopo_2016/GARE.SHP'
    ]
    for path in clipRes:
        reproj(clip(path, zone_buffer), 'data/transport/')
    del clipBati, clipRes, clipPai

    # Préparation de la couche arrêts de transport en commun
    transports = []
    if os.path.exists(localDataPath + '/bus.shp'):
        reproj(clip(localDataPath + '/bus.shp', zone_buffer), 'data/transport/')
        bus = QgsVectorLayer('data/transport/bus.shp', 'bus')
        transports.append(bus)
        del bus

    params = {
        'INPUT': 'data/pai/transport.shp',
        'EXPRESSION': """ "NATURE" = 'Station de métro' """,
        'OUTPUT': 'data/transport/transport_pai.shp',
        'FAIL_OUTPUT': 'memory:'
    }
    res = processing.run('native:extractbyexpression',
                         params, feedback=feedback)
    transports.append(res['OUTPUT'])

    gare = QgsVectorLayer('data/transport/gare.shp', 'gare')
    params = {'INPUT': gare, 'OUTPUT': 'memory:gare'}
    res = processing.run('native:centroids', params, feedback=feedback)
    transports.append(res['OUTPUT'])

    params = {
        'LAYERS': transports,
        'CRS': 'EPSG:3035',
        'OUTPUT': 'data/transport/arrets_transport.shp'
    }
    processing.run('native:mergevectorlayers', params, feedback=feedback)
    del transports, gare

    # Traitement du PLU
    if os.path.exists(localDataPath + '/plu.shp'):
        plu = QgsVectorLayer(localDataPath + '/plu.shp', 'plu')
        pluFixer(plu, zone, 'data/', 'windows-1258')
        del plu

    # Extraction et classification des points geosirene
    os.mkdir('data/geosirene')
    sirene = reproj(clip(globalDataPath + '/sirene/geosirene.shp', zone_buffer))
    sireneSplitter(sirene, 'data/geosirene/')

    # Correction de l'OCS ou extraction de l'OSO CESBIO si besoin
    if not os.path.exists(localDataPath + '/ocsol.shp'):
        ocsol = QgsVectorLayer(
            globalDataPath + '/oso/departement_' + codeDept + '.shp', 'ocsol')
        oso.dataProvider().createSpatialIndex()
        reproj(clip(ocsol, zone), 'data/')
    else:
        params = {
            'INPUT': localDataPath + '/ocsol.shp',
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
        reproj(clip(ocsol, zone), 'data/')
    del ocsol

    # Traitement du shape de l'intérêt écologique
    if os.path.exists(localDataPath + '/ecologie.shp'):
        ecologie = QgsVectorLayer(localDataPath + '/ecologie.shp', 'ecologie')
        ecoFields = []
        for field in ecologie.fields():
            ecoFields.append(field.name())
        if 'importance' not in ecoFields:
            print("Attribut requis 'importance' manquant ou mal nommé dans la couche d'importance écologique")
            sys.exit()
        ecologie.addExpressionField(
            '1 - ("importance"/100)', QgsField('interet', QVariant.Double))

        params = {'INPUT': ecologie, 'OUTPUT': 'memory:ecologie'}
        res = processing.run('native:fixgeometries', params, feedback=feedback)
        reproj(clip(res['OUTPUT'], zone), 'data/')
        del ecologie, ecoFields, field
    # Autrement déterminer l'intérêt écologique grâce à l'ocsol ?
    else:
        pass

    os.mkdir('data/restriction')
    reproj(clip(globalDataPath + '/rge/' + codeDept +
                '/bdtopo_2016/SURFACE_EAU.SHP', zone), 'data/restriction/')

    # Traitement d'une couche facultative du PPR
    if os.path.exists('ppr.shp'):
        reproj(clip('ppr.shp', zone), 'data/restriction')

    # Traitement d'une couche facultative pour exclusion de zones bâties lors du calcul de densité
    if os.path.exists(localDataPath + '/exclusion.shp'):
        reproj(clip(localDataPath + '/exclusion.shp', zone), 'data/restriction/')

    # Traitement des couches de zonage de protection
    zonagesEnv = []
    os.mkdir('data/zonages')
    for file in os.listdir(globalDataPath + '/env/'):
        if os.path.splitext(file)[1] == '.shp':
            zonagesEnv.append(globalDataPath + '/env/' + file)
    envRestrict(zonagesEnv, zone, 'data/zonages/')

    zonagesEnv = []
    for file in os.listdir('data/zonages/'):
        if os.path.splitext(file)[1] == '.shp':
            zonagesEnv.append('data/zonages/' + file)
    params = {
        'LAYERS': zonagesEnv,
        'CRS': 'EPSG:3035',
        'OUTPUT': 'data/restriction/zonages_protection.shp'
    }
    processing.run('native:mergevectorlayers', params, feedback=feedback)
    del zonagesEnv

    # Traitement des autoroutes
    params = {
        'INPUT': 'data/transport/route_primaire.shp',
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
        'OUTPUT': 'data/restriction/tampon_autoroutes.shp'
    }
    processing.run('native:buffer', params, feedback=feedback)

    reproj(zone, 'data/')
    reproj(zone_buffer, 'data/')
    del zone, zone_buffer

    # Fusion des routes primaires et secondaires
    mergeRoads = ['data/transport/route_primaire.shp', 'data/transport/route_secondaire.shp']
    params = {
        'LAYERS': mergeRoads,
        'CRS': 'EPSG:3035',
        'OUTPUT': 'data/transport/routes.shp'
    }
    processing.run('native:mergevectorlayers', params, feedback=feedback)

    # Fusion des couches PAI
    mergePai = [
        'data/pai/administratif_militaire.shp',
        'data/pai/culture_loisirs.shp',
        'data/pai/industriel_commercial.shp',
        'data/pai/religieux.shp',
        'data/pai/sante.shp',
        'data/pai/science_enseignement.shp',
        'data/pai/sport.shp'
    ]
    params = {
        'LAYERS': mergePai,
        'CRS': 'EPSG:3035',
        'OUTPUT': 'data/pai/pai_merged.shp'
    }
    processing.run('native:mergevectorlayers', params, feedback=feedback)

    # Empaquetage de tout le bâti, calcul de surfaces et intersection avec les IRIS
    # mergeBuildings = []
    # for file in os.listdir('data/2016_bati'):
    #     if os.path.splitext(file)[1] == '.shp' and 'cimetiere' not in file:
    #         path = 'data/2016_bati/' + file
    #         mergeBuildings.append(path)
    # params = {
    #     'LAYERS': mergeBuildings,
    #     'CRS': 'EPSG:3035',
    #     'OUTPUT': 'memory:bati_merged'
    # }
    # res = processing.run('native:mergevectorlayers', params, feedback=feedback)
    # layer = res['OUTPUT']
    # layer.dataProvider().createSpatialIndex()
    # layer.addExpressionField('$area', QgsField('AIRE', QVariant.Double))
    # params = {
    #     'INPUT': layer,
    #     'OVERLAY': 'data/iris.shp',
    #     'INPUT_FIELDS': ['ID', 'AIRE', 'layer'],
    #     'OVERLAY_FIELDS': ['CODE_IRIS', 'NOM_IRIS', 'TYP_IRIS', 'POP14'],
    #     'OUTPUT': 'memory:'
    # }
    # res = processing.run('qgis:intersection', params, feedback=feedback)
    # layer = res['OUTPUT']
    # params = {
    #     'INPUT': layer,
    #     'VALUES_FIELD_NAME': 'AIRE',
    #     'CATEGORIES_FIELD_NAME': 'CODE_IRIS',
    #     'OUTPUT': 'data/2016_bati/stat_surf_sol.csv'
    # }
    # processing.run('qgis:statisticsbycategories',
    #                params, feedback=feedback)
    #
    # i = 0
    # for path in mergeBuildings:
    #     path = path.replace('2016', '2009')
    #     mergeBuildings[i] = path
    #     i += 1
    # params = {
    #     'LAYERS': mergeBuildings,
    #     'CRS': 'EPSG:3035',
    #     'OUTPUT': 'memory:bati_merged'
    # }
    # res = processing.run('native:mergevectorlayers', params, feedback=feedback)
    # layer = res['OUTPUT']
    # layer.dataProvider().createSpatialIndex()
    # layer.addExpressionField('$area', QgsField('AIRE', QVariant.Double))
    # params = {
    #     'INPUT': layer,
    #     'OVERLAY': 'data/iris.shp',
    #     'INPUT_FIELDS': ['ID', 'AIRE', 'layer'],
    #     'OVERLAY_FIELDS': ['CODE_IRIS', 'NOM_IRIS', 'TYP_IRIS', 'POP09'],
    #     'OUTPUT': 'memory:'
    # }
    # res = processing.run('qgis:intersection', params, feedback=feedback)
    # layer = res['OUTPUT']
    # params = {
    #     'INPUT': layer,
    #     'VALUES_FIELD_NAME': 'AIRE',
    #     'CATEGORIES_FIELD_NAME': 'CODE_IRIS',
    #     'OUTPUT': 'data/2009_bati/stat_surf_sol.csv'
    # }
    # processing.run('qgis:statisticsbycategories',
    #                params, feedback=feedback)
    #
    # del mergePai, mergeRoads, mergeBuildings, layer

    # Nettoyage dans la couche de bâti indif. avec les PAI et surfaces d'activité
    bati_indif = QgsVectorLayer('data/2016_bati/bati_indifferencie.shp', 'bati_indif_2016')
    bati_indif.dataProvider().createSpatialIndex()
    cleanPolygons = []
    cleanPoints = ['data/pai/pai_merged.shp']
    # On ignore les zones industrielles et commerciales
    params = {
        'INPUT': 'data/pai/surface_activite.shp',
        'EXPRESSION': """ "CATEGORIE" != 'Industriel ou commercial' """,
        'OUTPUT': 'data/pai/surf_activ_non_com.shp',
        'FAIL_OUTPUT': 'memory:'
    }
    processing.run('native:extractbyexpression', params, feedback=feedback)
    # Fusion des polygones pour éviter les résidus avec le prédicat WITHIN
    params = {
        'INPUT': 'data/pai/surf_activ_non_com.shp',
        'FIELD': [],
        'OUTPUT': 'memory:'
    }
    res = processing.run('native:dissolve', params, feedback=feedback)
    cleanPolygons.append(res['OUTPUT'])
    if os.path.exists('data/restriction/exclusion.shp'):
        cleanPolygons.append('data/restriction/exclusion.shp')
    buildingCleaner(bati_indif, minSurf, maxSurf, levelHeight, cleanPolygons, cleanPoints,
                    'data/2016_bati/bati_clean.shp', 'data/restriction/bati_removed.shp')

    del bati_indif, cleanPolygons, cleanPoints

    # Intersection du bâti résidentiel avec les quartiers IRIS
    bati_clean = QgsVectorLayer('data/2016_bati/bati_clean.shp')
    bati_clean.dataProvider().createSpatialIndex()
    params = {
        'INPUT': 'data/2016_bati/bati_clean.shp',
        'OVERLAY': 'data/iris.shp',
        'INPUT_FIELDS': ['ID', 'HAUTEUR', 'NB_NIV'],
        'OVERLAY_FIELDS': ['CODE_IRIS', 'NOM_IRIS', 'TYP_IRIS', 'POP14', 'TXRP14'],
        'OUTPUT': 'data/2016_bati/bati_inter_iris.shp'
    }
    processing.run('qgis:intersection', params, feedback=feedback)

if not os.path.exists('data/' + gridSize + 'm/'):
    os.mkdir('data/' + gridSize + 'm/')
    os.mkdir('data/' + gridSize + 'm/tif')
    os.mkdir('data/' + gridSize + 'm/csv')

    # Création d'une grille régulière
    zone_buffer = QgsVectorLayer('data/zone_buffer.shp', 'zone_buffer')
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
        'OUTPUT': 'data/' + gridSize + 'm/grid.shp'
    }
    processing.run('qgis:creategrid', params, feedback=feedback)
    del zone_buffer, extent, extentStr

    # Intersection entre le couche de bâti nettoyée et la grille
    batiIndif = QgsVectorLayer('data/2016_bati/bati_inter_iris.shp')
    # stat09 = QgsVectorLayer('data/2009_bati/stat_surf_sol.csv', '09')
    # stat14 = QgsVectorLayer('data/2016_bati/stat_surf_sol.csv', '14')
    # statCsvList = [stat09, stat14]
    grid = QgsVectorLayer('data/' + gridSize + 'm/grid.shp', 'grid')
    iris = QgsVectorLayer('data/iris.shp')
    # statGridIris(batiIndif, statCsvList, grid, iris, 'data/' + gridSize + 'm/')
    statGridIris(batiIndif, grid, iris, 'data/' + gridSize + 'm/')
    del batiIndif, iris
    # del stat09, stat14, statCsvList

    # Création de la grille de restriction
    b_removed = QgsVectorLayer('data/restriction/bati_removed.shp', 'b_removed')
    b_indus = QgsVectorLayer('data/2016_bati/bati_industriel.shp', 'b_indus')
    b_remarq = QgsVectorLayer('data/2016_bati/bati_remarquable.shp', 'b_remarq')
    cimetiere = QgsVectorLayer('data/2016_bati/cimetiere.shp', 'cimetiere')
    c_surfa = QgsVectorLayer('data/2016_bati/construction_surfacique.shp', 'c_surfa')
    p_aero = QgsVectorLayer('data/2016_bati/piste_aerodrome.shp', 'p_aero')
    s_eau = QgsVectorLayer('data/restriction/surface_eau.shp', 's_eau')
    t_sport = QgsVectorLayer('data/2016_bati/terrain_sport.shp', 't_sport')

    restrictList = [b_indus, b_removed, b_remarq, cimetiere, c_surfa, p_aero, s_eau, t_sport]
    restrictGrid(restrictList, grid, maxOverlapRatio, 'data/' + gridSize + 'm/')
    del b_removed, b_indus, b_remarq, cimetiere, c_surfa, p_aero, s_eau, t_sport, restrictList, grid

    # Objet pour transformation de coordonées
    l93 = QgsCoordinateReferenceSystem()
    l93.createFromString('EPSG:2154')
    laea = QgsCoordinateReferenceSystem()
    laea.createFromString('EPSG:3035')
    trCxt = QgsCoordinateTransformContext()
    coordTr = QgsCoordinateTransform(l93, laea, trCxt)

    # BBOX pour extraction du MNT
    grid = QgsVectorLayer('data/' + gridSize + 'm/stat_grid.shp', 'grid')
    extent = grid.extent()
    extentL93 = coordTr.transform(extent, coordTr.ReverseTransform)

    # Extraction des tuiles MNT dans la zone d'étude
    demList = demExtractor(globalDataPath + '/rge/' + codeDept + '/bdalti/', extentL93)

    xMin = extent.xMinimum()
    yMin = extent.yMinimum()
    xMax = extent.xMaximum()
    yMax = extent.yMaximum()

    # Fusion des tuiles et reprojection
    gdal.Warp(
        'data/' + gridSize + 'm/tif/mnt.tif', demList,
        format='GTiff', outputType=gdal.GDT_Float32,
        xRes=int(gridSize), yRes=int(gridSize),
        resampleAlg='cubicspline',
        srcSRS='EPSG:2154', dstSRS='EPSG:3035',
        outputBounds=(xMin, yMin, xMax, yMax),
        srcNodata=-99999)

    # Calcul de pente en %
    gdal.DEMProcessing(
        'data/' + gridSize + 'm/tif/slope.tif',
        'data/' + gridSize + 'm/tif/mnt.tif',
        'slope', format='GTiff',
        slopeFormat='percent')

    # Chaîne à passer à QGIS pour l'étendue des rasterisations
    extentStr = str(xMin) + ',' + str(xMax) + ',' + str(yMin) + ',' + str(yMax) + ' [EPSG:3035]'

    # Rasterisations
    rasterize('data/ecologie.shp', 'data/' + gridSize + 'm/tif/ecologie.tif', 'interet')
    rasterize('data/' + gridSize + 'm/stat_grid.shp', 'data/' + gridSize + 'm/tif/s_planch_grid.tif', 'srf_p')
    rasterize('data/' + gridSize + 'm/restrict_grid.shp', 'data/' + gridSize + 'm/tif/restrict_grid.tif', 'restrict')
    rasterize('data/' + gridSize + 'm/stat_iris.shp', 'data/' + gridSize + 'm/tif/seuil_q3_iris.tif', 'SP_Q3')
    rasterize('data/' + gridSize + 'm/stat_iris.shp', 'data/' + gridSize + 'm/tif/seuil_max_iris.tif', 'SP_MAX')
    rasterize('data/' + gridSize + 'm/stat_iris.shp', 'data/' + gridSize + 'm/tif/nb_m2_iris.tif', 'M2_HAB')
    rasterize('data/' + gridSize + 'm/stat_iris.shp', 'data/' + gridSize + 'm/tif/masque.tif', burn=1, inverse=True)

    rasterize('data/restriction/zonages_protection.shp', 'data/' + gridSize + 'm/tif/zonages_protection.tif', burn=1)
    rasterize('data/restriction/tampon_autoroutes.shp', 'data/' + gridSize + 'm/tif/tampon_autoroutes.tif', burn=1)
    rasterize('data/restriction/exclusion.shp', 'data/' + gridSize + 'm/tif/exclusion.tif', burn=1)
    rasterize('data/pai/surf_activ_non_com.shp', 'data/' + gridSize + 'm/tif/surf_activ_non_com.tif', burn=1)

    if os.path.exists('data/restriction/ppr.shp'):
        rasterize('data/restriction/ppr.shp', 'data/' + gridSize + 'm/tif/ppr.tif', burn=1)
    elif os.path.exists('data/plu.shp'):
        rasterize('data/plu.shp', 'data/' + gridSize + 'm/tif/ppr.tif', 'ppr')

    if os.path.exists('data/plu.shp'):
        rasterize('data/plu.shp', 'data/' + gridSize + 'm/tif/plu_rest.tif', 'restrict')
        rasterize('data/plu.shp', 'data/' + gridSize + 'm/tif/plu_prio.tif', 'priority')

    # Calcul des rasters de distance
    rasterize('data/transport/routes.shp', 'data/' + gridSize + 'm/tif/routes.tif', burn=1)
    params = {
        'INPUT': 'data/' + gridSize + 'm/tif/routes.tif',
        'BAND': 1,
        'VALUES': 1,
        'UNITS': 0,
        'NODATA': -1,
        'MAX_DISTANCE': roadDist,
        'DATA_TYPE': 5,
        'OUTPUT': 'data/' + gridSize + 'm/tif/distance_routes.tif'
    }
    processing.run('gdal:proximity', params, feedback=feedback)

    rasterize('data/transport/arrets_transport.shp', 'data/' + gridSize + 'm/tif/arrets_transport.tif', burn=1)
    params['INPUT'] = 'data/' + gridSize + 'm/tif/arrets_transport.tif'
    params['MAX_DISTANCE'] = transDist
    params['OUTPUT'] = 'data/' + gridSize + 'm/tif/distance_arrets_transport.tif'
    processing.run('gdal:proximity', params, feedback=feedback)

    # Calcul des rasters de densité
    os.mkdir('data/' + gridSize + 'm/tif/tmp')
    projwin = str(xMin) + ',' + str(xMax) + ',' + str(yMin) + ',' + str(yMax)
    dicSirene = {row[0]: row[1] for _, row in pd.read_csv(globalDataPath + '/sirene/distances.csv').iterrows()}

    for key in dicSirene.keys():
        layer = QgsVectorLayer('data/geosirene/type_' + key + '.shp', key)
        layer.setExtent(extent)
        params = {
            'INPUT': layer,
            'RADIUS': dicSirene[key],
            'PIXEL_SIZE': int(gridSize),
            'KERNEL': 0,
            'OUTPUT_VALUE': 0,
            'OUTPUT': 'data/' + gridSize + 'm/tif/tmp/densite_' + key + '.tif'
        }
        processing.run('qgis:heatmapkerneldensityestimation', params, feedback=feedback)

        params = {
            'INPUT': 'data/' + gridSize + 'm/tif/tmp/densite_' + key + '.tif',
            'PROJWIN': projwin,
            'NODATA': -9999,
            'DATA_TYPE': 5,
            'OUTPUT': 'data/' + gridSize + 'm/tif/densite_' + key + '.tif'
        }
        processing.run('gdal:cliprasterbyextent', params, feedback=feedback)
    del projwin, dicSirene

# Mise en forme finale des données raster pour le modèle
if not os.path.exists(projectPath):
    os.makedirs(projectPath)
    # Préparation du fichier des IRIS - création des ID et de la matrice de contiguïté
    iris = QgsVectorLayer('data/' + gridSize + 'm/stat_iris.shp')
    contiguityMatrix(iris, projectPath + 'iris.csv')
    del iris

    grid = QgsVectorLayer('data/' + gridSize + 'm/stat_grid.shp', 'grid')
    extent = grid.extent()
    xMin = extent.xMinimum()
    yMin = extent.yMinimum()
    xMax = extent.xMaximum()
    yMax = extent.yMaximum()
    extentStr = str(xMin) + ',' + str(xMax) + ',' + str(yMin) + ',' + str(yMax) + ' [EPSG:3035]'

    # Rasterisations
    rasterize('data/' + gridSize + 'm/stat_grid.shp', projectPath + 'population.tif', 'pop')
    rasterize('data/' + gridSize + 'm/stat_iris.shp', projectPath + 'iris_id.tif', 'ID')
    rasterize('data/ocsol.shp', projectPath + 'ocsol.tif', 'interet')

    # Création des variables GDAL indispensables pour la fonction to_tif()
    ds = gdal.Open(projectPath + 'population.tif')
    cols = ds.RasterXSize
    rows = ds.RasterYSize
    proj = ds.GetProjection()
    geot = ds.GetGeoTransform()
    driver = gdal.GetDriverByName('GTiff')
    population = ds.ReadAsArray()
    ds = None

    # Conversion des raster de distance
    distance_routes = to_array('data/' + gridSize + 'm/tif/distance_routes.tif', 'float32')
    routes = np.where(distance_routes > -1, 1 - (distance_routes / np.amax(distance_routes)), 0)
    to_tif(routes, gdal.GDT_Float32, projectPath + 'routes.tif')

    distance_transport = to_array('data/' + gridSize + 'm/tif/distance_arrets_transport.tif', 'float32')
    transport = np.where(distance_transport > -1, 1 - (distance_transport / np.amax(distance_transport)), 0)
    to_tif(transport, gdal.GDT_Float32, projectPath + 'transport.tif')

    # Conversion et aggrégation des rasters de densité SIRENE
    dicSirene = {row[0]: row[1] for _, row in pd.read_csv(globalDataPath + '/sirene/poids.csv').iterrows()}

    administratif = to_array('data/' + gridSize + 'm/tif/densite_administratif.tif', 'float32')
    commercial = to_array('data/' + gridSize + 'm/tif/densite_commercial.tif', 'float32')
    enseignement = to_array('data/' + gridSize + 'm/tif/densite_enseignement.tif', 'float32')
    medical = to_array('data/' + gridSize + 'm/tif/densite_medical.tif', 'float32')
    recreatif = to_array('data/' + gridSize + 'm/tif/densite_recreatif.tif', 'float32')

    # Normalisation des valeurs entre 0 et 1
    administratif = np.where(administratif != -9999, administratif / np.amax(administratif), 0)
    commercial = np.where(commercial != -9999, commercial / np.amax(commercial), 0)
    enseignement = np.where(enseignement != -9999, enseignement / np.amax(enseignement), 0)
    medical = np.where(medical != -9999, medical / np.amax(medical), 0)
    recreatif = np.where(recreatif != -9999, recreatif / np.amax(recreatif), 0)

    sirene = ((administratif * dicSirene['administratif']) + (commercial * dicSirene['commercial']) +
               (enseignement * dicSirene['enseignement']) + (medical * dicSirene['medical']) +
               (recreatif * dicSirene['recreatif'])) / sum(dicSirene.values())
    sirene = sirene / np.amax(sirene)
    to_tif(sirene, gdal.GDT_Float32, projectPath + 'sirene.tif')
    del dicSirene, administratif, commercial, enseignement, medical, recreatif, sirene
    copyfile(localDataPath + '/poids.csv', projectPath + '/poids.csv')

    # Création du raster de restriction (sans PLU)
    irisMask = to_array('data/' + gridSize + 'm/tif/masque.tif')
    exclusionMask = to_array('data/' + gridSize + 'm/tif/exclusion.tif')
    surfActivMask = to_array('data/' + gridSize + 'm/tif/surf_activ_non_com.tif')
    gridMask = to_array('data/' + gridSize + 'm/tif/restrict_grid.tif')
    zonageMask = to_array('data/' + gridSize + 'm/tif/zonages_protection.tif')
    highwayMask = to_array('data/' + gridSize + 'm/tif/tampon_autoroutes.tif')
    pprMask = to_array('data/' + gridSize + 'm/tif/ppr.tif')
    slope = to_array('data/' + gridSize + 'm/tif/slope.tif')
    slopeMask = np.where(slope > maxSlope, 1, 0)

    restriction = np.where((irisMask == 1) | (exclusionMask == 1) | (surfActivMask == 1) | (gridMask == 1) | (
        zonageMask == 1) | (highwayMask == 1) | (pprMask == 1) | (slopeMask == 1), 1, 0)
    to_tif(restriction, gdal.GDT_Byte, projectPath + 'restriction.tif')
    del surfActivMask, exclusionMask, gridMask, zonageMask, highwayMask, pprMask, slope, slopeMask, restriction

    if os.path.exists('data/plu.shp'):
        pluRestrict = to_array('data/' + gridSize + 'm/tif/plu_rest.tif')
        pluPriority = to_array('data/' + gridSize + 'm/tif/plu_prio.tif')
        to_tif(pluRestrict, gdal.GDT_Byte, projectPath + 'plu_restriction.tif')
        to_tif(pluPriority, gdal.GDT_Byte, projectPath + 'plu_priorite.tif')
        del pluRestrict, pluPriority

    ecologie = to_array('data/' + gridSize + 'm/tif/ecologie.tif')
    ecologie = np.where((ecologie == 0) & (irisMask != 1), 1, ecologie)
    to_tif(ecologie, gdal.GDT_Float32, projectPath + 'ecologie.tif')
    del ecologie

    nb_m2 = to_array('data/' + gridSize + 'm/tif/nb_m2_iris.tif')
    s_planch = to_array('data/' + gridSize + 'm/tif/s_planch_grid.tif')
    seuil = to_array('data/' + gridSize + 'm/tif/seuil_q3_iris.tif')
    capa_m2 = np.where(seuil - s_planch >= 0, seuil - s_planch, 0)
    capacite = np.where((irisMask != 1) & (nb_m2 != 0), capa_m2 / nb_m2, 0)
    to_tif(capacite, gdal.GDT_UInt16, projectPath + 'capacite.tif')

print('Terminé  à ' + strftime('%H:%M:%S'))
qgs.exitQgis()
