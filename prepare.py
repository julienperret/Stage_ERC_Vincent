#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import sys
import csv
import time
import gdal
import numpy as np
import pandas as pd

# sys.path.append('/usr/share/qgis/python')
from qgis.core import (
    QgsApplication,
    QgsCoordinateTransform,
    QgsCoordinateTransformContext,
    QgsCoordinateReferenceSystem,
    QgsExpression,
    QgsField,
    QgsProcessingFeedback,
    QgsRectangle,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsVectorLayerJoinInfo)
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

# Vérification des paramètres d'entrée
if(len(sys.argv) < 4):
    print("""Le scipt prend au moins 3 paramètres en entrée :
    dossier de travail (spécifique à la zone), le numéro du département
    et le taux d'accroissement démograpique.""")
    sys.exit()
workspace = sys.argv[1]
dept = sys.argv[2]
os.chdir(workspace)
if not os.path.exists('../global_data'):
    print('La donnée régionale est manquante ou n''est pas dans le dossier approprié -> ../global_data)')
    sys.exit()
if not os.path.exists('zone.shp'):
    print('Le shapefile de la zone d''étude (zone.shp) doit être placé dans le répertoire de travail.')
    sys.exit()
tauxEvo = sys.argv[3]
if(len(sys.argv) > 4):
    mode = sys.argv[4]
    if mode == 'strict':
        gridSize = '20'
    elif mode == 'souple':
        gridSize = '50'
    else:
        print('Deux valeurs possibles pour le mode de seuillage : souple - strict ')
        sys.exit()
else:
    mode = 'souple'
    gridSize = '50'

# Découpe une couche avec gestion de l'encodage pour la BDTOPO
def clip(file, overlay, outdir='memory:'):
    if type(file) == QgsVectorLayer:
        params = {
            'INPUT': file,
            'OVERLAY': overlay,
            'OUTPUT': outdir + file.name()
        }
    elif type(file) == str:
        name = os.path.basename(file).split('.')[0].lower()
        layer = QgsVectorLayer(file, name)
        layer.dataProvider().createSpatialIndex()
        if 'bdtopo' in file:
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
def rasterize(file, outfile, field=None, dtype=5, init=0, invert=False):
    if dtype == 'byte':
        dtype = 0
    elif dtype == 'uint16':
        dtype = 2
    params = {
        'INPUT': file,
        'FIELD': field,
        'UNITS': 1,
        'WIDTH': int(gridSize),
        'HEIGHT': int(gridSize),
        'EXTENT': extentStr,
        'DATA_TYPE': dtype,
        'INIT': init,
        'INVERT': invert,
        'OUTPUT': outfile}
    if not field :
        params['BURN'] = 1
    processing.run('gdal:rasterize', params, feedback=feedback)

# Reprojection en laea par défaut
def reproj(file, outdir='memory:', crs='EPSG:3035'):
    if type(file) == QgsVectorLayer:
        name = file.name()
    elif type(file) == str:
        name = os.path.basename(file).split('.')[0].lower()
    params = {
        'INPUT': file,
        'TARGET_CRS': crs,
        'OUTPUT': outdir + name
    }
    if outdir != 'memory:':
        params['OUTPUT'] += '.shp'
    res = processing.run('native:reprojectlayer', params, feedback=feedback)
    return res['OUTPUT']

# Réalise une jointure entre deux QgsVectorLayer
def join(layer, field, joinLayer, joinField, blacklist=[]):
    j = QgsVectorLayerJoinInfo()
    j.setTargetFieldName(field)
    j.setJoinLayerId(joinLayer.id())
    j.setJoinFieldName(joinField)
    j.setJoinFieldNamesBlackList(blacklist)
    j.setUsingMemoryCache(True)
    j.setPrefix('')
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

# Nettoye une couche de bâtiments et génère les champs utiles à l'estimation de population
def buildingCleaner(buildings, polygons, points, outpath, surfMin=50, surfMax=10000):
    # Selection des bâtiments situés dans polygones
    for layer in polygons :
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
        ELSE "HAUTEUR"/3 END
    """
    buildings.addExpressionField(
        expr, QgsField('NB_NIV', QVariant.Int, len=2))

    # Nettoyage des bâtiments supposés trop grand ou trop petit pour être habités
    params = {
        'INPUT': buildings,
        'EXPRESSION': ' $area < ' + str(surfMin) + ' OR $area > ' + str(surfMax),
        'METHOD': 1
    }
    processing.run('qgis:selectbyexpression', params, feedback=feedback)

    # Inversion de la selection pour export final
    buildings.invertSelection()
    params = {
        'INPUT': buildings,
        'OUTPUT': outpath
    }
    res = processing.run('native:saveselectedfeatures', params, feedback=feedback)
    return res['OUTPUT']
    del buildings, polygons, points, layer, surfMin, surfMax, outpath

# Génère un csv contenant la matrice de contiguïté par ID et la population de départ
def contiguityMatrix(iris, outcsv):
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
    irisDf.to_csv(outcsv, index=0)
    return irisDf

# Selection des tuiles MNT dans la zone d'étude sous forme de liste
def demExtractor(directory, bbox):
    tileList = []
    for tile in os.listdir(directory):
        if os.path.splitext(tile)[1] == '.asc':
            path = directory + tile
            with open(path) as file:
                for i in range(4):
                    line = file.readline()
                    if i == 2:
                        res = re.search('[a-z]*\s*([0-9.]*)', line)
                        xMin = float(res.group(1))
                    if i == 3:
                        res = re.search('[a-z]*\s*([0-9.]*)', line)
                        yMin = float(res.group(1))
            xMax = xMin + 5000
            yMax = yMin + 5000
            tileExtent = QgsRectangle(xMin, yMin, xMax, yMax)
            if bbox.intersects(tileExtent):
                tileList.append(path)
    return tileList

# Intersection entre la couche de bâti nettoyée jointe aux iris et la grille avec calcul et jointure des statistiques
def popGrid(buildings, grid, iris, outdir):
    if not os.path.exists(outdir + 'csv'):
        os.mkdir(outdir + 'csv')

    buildings.dataProvider().createSpatialIndex()
    grid.dataProvider().createSpatialIndex()
    buildings.addExpressionField('$area', QgsField(
        'area_i', QVariant.Double, len=10, prec=2))
    expr = ' "area_i" * "NB_NIV" * "TXRP14" '
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
        'OUTPUT': 'memory:bati_inter_grid'}
    res = processing.run('qgis:intersection', params, feedback=feedback)
    buildings = res['OUTPUT']

    # Calcul de stat sur la bâti dans la grille
    buildings.addExpressionField('$area', QgsField(
        'area_g', QVariant.Double, len=10, prec=2))
    expr = ' "area_g" / "area_i" * "pop_bati" '
    buildings.addExpressionField(expr, QgsField(
        'pop_cell', QVariant.Double, len=10, prec=2))
    expr = ' "area_g" * "NB_NIV" * "TXRP14" '
    buildings.addExpressionField(expr, QgsField(
        'planch_g', QVariant.Double, len=10, prec=2))
    expr = ' "planch_g" / "pop_cell" '
    buildings.addExpressionField(expr, QgsField(
        'nb_m2_hab', QVariant.Double, len=10, prec=2))

    # Aggrégation de statistiques dans des fichiers CSV
    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'pop_cell',
        'CATEGORIES_FIELD_NAME': 'id_2',
        'OUTPUT': outdir + '/csv/stat_pop_grid.csv'}
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)

    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'planch_g',
        'CATEGORIES_FIELD_NAME': 'id_2',
        'OUTPUT': outdir + '/csv/stat_planch_grid.csv'}
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)

    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'nb_m2_hab',
        'CATEGORIES_FIELD_NAME': 'CODE_IRIS',
        'OUTPUT': outdir + '/csv/stat_nb_m2_iris.csv'}
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)

    params = {
        'INPUT': buildings,
        'VALUES_FIELD_NAME': 'planch_g',
        'CATEGORIES_FIELD_NAME': 'CODE_IRIS',
        'OUTPUT': outdir + '/csv/stat_planch_iris.csv'
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)

    to_shp(buildings, outdir + 'bati_inter_grid.shp')
    del buildings

    # Correction et changement de nom pour jointure des stat sur la grille et le IRIS
    csvPopG = QgsVectorLayer(
        outdir + '/csv/stat_pop_grid.csv', 'delimitedtext')
    csvPopG.addExpressionField(
        'to_real("sum")', QgsField('pop', QVariant.Double))

    csvPlanchG = QgsVectorLayer(
        outdir + '/csv/stat_planch_grid.csv', 'delimitedtext')
    csvPlanchG.addExpressionField(
        'to_real("sum")', QgsField('s_planch', QVariant.Double))

    csvM2I = QgsVectorLayer(
        outdir + '/csv/stat_nb_m2_iris.csv', 'delimitedtext')
    csvM2I.addExpressionField(
        'to_real("mean")', QgsField('NB_M2_HAB', QVariant.Double))

    csvPlanchI = QgsVectorLayer(
        outdir + '/csv/stat_planch_iris.csv', 'delimitedtext')
    csvPlanchI.addExpressionField(
        'to_real("q3")', QgsField('PLANCH_Q3', QVariant.Double))

    statBlackList = ['count', 'unique', 'min', 'max', 'range', 'sum',
                     'mean', 'median', 'stddev', 'minority', 'majority', 'q1', 'q3', 'iqr']

    join(grid, 'id', csvPopG, 'id_2', statBlackList)
    join(grid, 'id', csvPlanchG, 'id_2', statBlackList)
    to_shp(grid, outdir + '/grid_stat.shp')
    del csvPopG, csvPlanchG

    join(iris, 'CODE_IRIS', csvPlanchI, 'CODE_IRIS', statBlackList)
    join(iris, 'CODE_IRIS', csvM2I, 'CODE_IRIS', statBlackList)
    iris.addExpressionField('$id + 1', QgsField('ID', QVariant.Int, len=4))
    to_shp(iris, outdir + '/iris_stat.shp')
    del csvPlanchI, csvM2I, statBlackList

# Intersection entre la couche de bâti nettoyée jointe aux iris et la grille avec calcul et jointure des statistiques
def restrictGrid(list, grid, outdir):
    if not os.path.exists(outdir + 'csv'):
        os.mkdir(outdir + 'csv')

    grid.dataProvider().createSpatialIndex()
    statBlackList = ['count', 'unique', 'min', 'max', 'range', 'sum',
                     'mean', 'median', 'stddev', 'minority', 'majority', 'q1', 'q3', 'iqr']
    csvList = []

    for layer in list:
        name = layer.name()
        layer.dataProvider().createSpatialIndex()

        params = {
            'INPUT': layer,
            'OVERLAY': grid,
            'INPUT_FIELDS': [],
            'OVERLAY_FIELDS': ['id'],
            'OUTPUT': 'memory:' + name }
        res = processing.run('qgis:intersection', params, feedback=feedback)
        layer = res['OUTPUT']

        # Calcul de stat sur la bâti dans la grille
        layer.addExpressionField('$area', QgsField(
            'area_g', QVariant.Double, len=10, prec=2))

        # Aggrégation de statistiques dans des fichiers CSV
        params = {
            'INPUT': layer,
            'VALUES_FIELD_NAME': 'area_g',
            'CATEGORIES_FIELD_NAME': 'id_2',
            'OUTPUT': outdir + 'csv/stat_restriction_' + name + '.csv'}
        processing.run('qgis:statisticsbycategories', params, feedback=feedback)

        csv = QgsVectorLayer(
            outdir + 'csv/stat_restriction_' + name + '.csv', 'delimitedtext')
        csv.addExpressionField(
            'to_real("sum")', QgsField('s_' + name, QVariant.Double))
        csvList.append(csv)

    for layer in csvList :
        join(grid, 'id', layer, 'id_2', statBlackList)
    to_shp(grid, outdir + 'restrict_grid.shp')
    del list, csvList, layer

# Création d'un tampon de 100m autour des autouroutes pour restriction
def highwayBuffer(roads, outfile, distance=100):
    params = {
        'INPUT': roads,
        'EXPRESSION': """ "NATURE" = 'Autoroute' """,
        'OUTPUT': 'memory:autoroutes',
        'FAIL_OUTPUT': 'memory:'
    }
    res = processing.run('native:extractbyexpression', params, feedback=feedback)
    params = {
        'INPUT': res['OUTPUT'],
        'DISTANCE': distance,
        'SEGMENTS': 5,
        'END_CAP_STYLE': 0,
        'JOIN_STYLE': 0,
        'MITER_LIMIT': 2,
        'DISSOLVE': True,
        'OUTPUT': outfile
    }
    res = processing.run('native:buffer', params, feedback=feedback)
    return res['OUTPUT']

# Jointure avec données INSEE et extraction des IRIS dans la zone
def irisExtractor(iris, overlay, csvdir, outdir):
    # Traitement des csv de population
    csvPop09 = QgsVectorLayer(
        csvdir + 'inseePop09.csv', 'delimitedtext')
    csvPop09.addExpressionField(
        'round(to_real("P09_POP"))', QgsField('POP09', QVariant.Int))

    csvPop14 = QgsVectorLayer(
        csvdir + 'inseePop14.csv', 'delimitedtext')
    csvPop14.addExpressionField(
        'round(to_real("P14_POP"))', QgsField('POP14', QVariant.Int))

    # Traitement du csv des logements
    csvLog14 = QgsVectorLayer(
        csvdir + 'inseeLog14.csv', 'delimitedtext')
    csvLog14.addExpressionField(
        'round(to_real("P14_RP"))', QgsField('RP14', QVariant.Int))
    csvLog14.addExpressionField(
        'to_real("P14_TXRP")', QgsField('TXRP14', QVariant.Double))

    # Jointure avec données INSEE et extraction des IRIS dans la zone
    join(iris, 'CODE_IRIS', csvPop09, 'IRIS', ['P09_POP'])
    join(iris, 'CODE_IRIS', csvPop14, 'IRIS', ['P14_POP'])
    join(iris, 'CODE_IRIS', csvLog14, 'IRIS', ['P14_RP', 'P14_TXRP'])
    expr = '("POP14"-"POP09")/"POP09"/5*100'
    iris.addExpressionField(expr, QgsField('EVO_0914', QVariant.Double))

    # Extraction des quartiers IRIS avec jointures
    params = {
        'INPUT': iris,
        'PREDICATE': 6,
        'INTERSECT': overlay,
        'OUTPUT': 'memory:iris'
    }
    res = processing.run('native:extractbylocation', params, feedback=feedback)
    return reproj(res['OUTPUT'], outdir)
    del csvPop09, csvPop14, csvLog14, iris

# Corrige les géometries et reclasse un PLU
def pluFixer(plu, overlay, outdir, encoding='windows-1258'):
    plu.setProviderEncoding(encoding)
    plu.dataProvider().createSpatialIndex()
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
    params = {
        'INPUT': plu,
        'OUTPUT': 'memory:plu'
    }
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

    params = {
        'INPUT': geosirene,
        'FIELD': 'type',
        'OUTPUT': outpath
    }
    processing.run('qgis:splitvectorlayer', params, feedback=feedback)

print('Commencé à ' + time.strftime('%H:%M:%S'))

# Gestion des XLS de l'INSEE, à faire une seule fois
if not os.path.exists('../global_data/insee/csv'):
    os.mkdir('../global_data/insee/csv')
    inseePop09 = pd.read_excel(
        '../global_data/insee/BTX_IC_POP_2009.xls', skiprows=(0, 1, 2, 3, 4))
    inseePop09.to_csv('../global_data/insee/csv/inseePop09.csv',
                      index=0, columns=['IRIS', 'P09_POP'])
    del inseePop09
    inseePop14 = pd.read_excel(
        '../global_data/insee/base-ic-evol-struct-pop-2014.xls', skiprows=(0, 1, 2, 3, 4))
    inseePop14.to_csv('../global_data/insee/csv/inseePop14.csv',
                      index=0, columns=['IRIS', 'P14_POP'])
    del inseePop14
    inseeLog14 = pd.read_excel(
        '../global_data/insee/base-ic-logement-2014.xls', skiprows=(0, 1, 2, 3, 4))
    inseeLog14['P14_TXRP'] = inseeLog14['P14_RP'] / inseeLog14['P14_LOG']
    inseeLog14.to_csv('../global_data/insee/csv/inseeLog14.csv',
                      index=0, columns=['IRIS', 'P14_RP', 'P14_TXRP'])
    del inseeLog14

# Découpe et reprojection de la donnée en l'absence du dossier ./data
if not os.path.exists('data'):
    os.mkdir('data')

    # Tampon de 1000m autour de la zone pour extrations des quartiers et des PAI
    zone = QgsVectorLayer('zone.shp', 'zone')
    zone.dataProvider().createSpatialIndex()
    params = {
        'INPUT': zone,
        'DISTANCE': 1000,
        'SEGMENTS': 5,
        'END_CAP_STYLE': 0,
        'JOIN_STYLE': 0,
        'MITER_LIMIT': 2,
        'DISSOLVE': True,
        'OUTPUT': 'memory:zone_buffer'
    }
    res = processing.run('native:buffer', params, feedback=feedback)
    zone_buffer = res['OUTPUT']
    zone_buffer.dataProvider().createSpatialIndex()

    # Extraction des quartiers IRIS avec jointures
    iris = QgsVectorLayer('../global_data/rge/IRIS_GE.SHP', 'iris')
    iris.dataProvider().createSpatialIndex()
    irisExtractor(iris, zone_buffer, '../global_data/insee/csv/', 'data/')

    # Extractions et reprojections
    reproj(clip('../global_data/rge/' + dept +
                '/bdtopo/SURFACE_ACTIVITE.SHP', zone), 'data/')

    os.mkdir('data/bati')
    clipBati = [
        '../global_data/rge/' + dept + '/bdtopo/BATI_INDIFFERENCIE.SHP',
        '../global_data/rge/' + dept + '/bdtopo/BATI_INDUSTRIEL.SHP',
        '../global_data/rge/' + dept + '/bdtopo/BATI_REMARQUABLE.SHP',
        '../global_data/rge/' + dept + '/bdtopo/CIMETIERE.SHP',
        '../global_data/rge/' + dept + '/bdtopo/CONSTRUCTION_LEGERE.SHP',
        '../global_data/rge/' + dept + '/bdtopo/CONSTRUCTION_SURFACIQUE.SHP',
        '../global_data/rge/' + dept + '/bdtopo/PISTE_AERODROME.SHP',
        '../global_data/rge/' + dept + '/bdtopo/RESERVOIR.SHP',
        '../global_data/rge/' + dept + '/bdtopo/TERRAIN_SPORT.SHP'
    ]
    for path in clipBati:
        reproj(clip(path, zone), 'data/bati/')

    os.mkdir('data/transport')
    clipRes = [
        '../global_data/rge/' + dept + '/bdtopo/ROUTE_PRIMAIRE.SHP',
        '../global_data/rge/' + dept + '/bdtopo/ROUTE_SECONDAIRE.SHP',
        '../global_data/rge/' + dept + '/bdtopo/TRONCON_VOIE_FERREE.SHP',
        '../global_data/rge/' + dept + '/bdtopo/GARE.SHP'
    ]
    for path in clipRes:
        reproj(clip(path, zone_buffer), 'data/transport/')

    os.mkdir('data/pai')
    clipPai = [
        '../global_data/rge/' + dept + '/bdtopo/PAI_ADMINISTRATIF_MILITAIRE.SHP',
        '../global_data/rge/' + dept + '/bdtopo/PAI_CULTURE_LOISIRS.SHP',
        '../global_data/rge/' + dept + '/bdtopo/PAI_ESPACE_NATUREL.SHP',
        '../global_data/rge/' + dept + '/bdtopo/PAI_INDUSTRIEL_COMMERCIAL.SHP',
        '../global_data/rge/' + dept + '/bdtopo/PAI_RELIGIEUX.SHP',
        '../global_data/rge/' + dept + '/bdtopo/PAI_SANTE.SHP',
        '../global_data/rge/' + dept + '/bdtopo/PAI_SCIENCE_ENSEIGNEMENT.SHP',
        '../global_data/rge/' + dept + '/bdtopo/PAI_TRANSPORT.SHP'
    ]
    for path in clipPai:
        reproj(clip(path, zone_buffer), 'data/pai/')
    del clipBati, clipRes, clipPai, path

    # Préparation de la couche arrêts de transport en commun
    transports = []
    if os.path.exists('bus.shp'):
        reproj(clip('bus.shp', zone_buffer), 'data/transport/')
        bus = QgsVectorLayer('data/transport/bus.shp', 'bus')
        transports.append(bus)
        del bus

    params = {
        'INPUT': 'data/pai/transport.shp',
        'EXPRESSION': """ "NATURE" = 'Station de métro' """,
        'OUTPUT': 'data/transport/transport_pai.shp',
        'FAIL_OUTPUT': 'memory:fail'
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
    if os.path.exists('plu.shp'):
        plu = QgsVectorLayer('plu.shp', 'plu')
        pluFixer(plu, zone, 'data/')
        del plu

    # Extraction et classification des points geosirene
    os.mkdir('data/geosirene')
    sirene = reproj(clip('../global_data/sirene/geosirene.shp', zone_buffer))
    sireneSplitter(sirene, 'data/geosirene/')

    # Correction de l'OCS ou extraction de l'OSO CESBIO si besoin
    if os.path.exists('ocsol.shp'):
        params = {
            'INPUT': 'ocsol.shp',
            'OUTPUT': 'memory:ocsol'
        }
        res = processing.run('native:fixgeometries', params, feedback=feedback)
        reproj(clip(res['OUTPUT'], zone), 'data/')
    else:
        oso = QgsVectorLayer(
            '../global_data/oso/departement_' + dept + '.shp', 'oso')
        oso.dataProvider().createSpatialIndex()
        reproj(clip(oso, zone), 'data/')
        del oso

    # Traitement du shape de l'intérêt écologique
    if os.path.exists('ecologie.shp'):
        ecologie = QgsVectorLayer('ecologie.shp', 'ecologie')
        ecoFields = []
        for field in ecologie.fields() :
            ecoFields.append(field.name())
        if 'importance' not in ecoFields :
            print("Attribut requis 'importance' manquant ou mal nommé dans la couche d'importance écologique")
            sys.exit()
        ecologie.addExpressionField('1 - ("importance"/100)', QgsField('interet', QVariant.Double))
        params = {
            'INPUT': ecologie,
            'OUTPUT': 'memory:ecologie'
        }
        res = processing.run('native:fixgeometries', params, feedback=feedback)
        reproj(clip(res['OUTPUT'],zone), 'data/')
        del ecologie, ecoFields, field

    # Traitement d'une couche facultative pour exclusion de zones bâties lors du calcul de densité
    os.mkdir('data/restriction')
    if os.path.exists('exclusion.shp'):
        reproj(clip('exclusion.shp', zone), 'data/restriction/')

    # Traitement des autoroutes
    highwayBuffer('data/transport/route_primaire.shp', 'data/restriction/tampon_autoroutes.shp')

    # Reprojection en LAEA
    reproj(zone, 'data/')
    reproj(zone_buffer, 'data/')
    del zone, zone_buffer

    # Fusion des couches PAI
    mergePai = [
        'data/pai/administratif_militaire.shp',
        'data/pai/culture_loisirs.shp',
        'data/pai/industriel_commercial.shp',
        'data/pai/religieux.shp',
        'data/pai/sante.shp',
        'data/pai/science_enseignement.shp'
    ]
    params = {
        'LAYERS': mergePai,
        'CRS': 'EPSG:3035',
        'OUTPUT': 'data/pai/pai_merged.shp'
    }
    processing.run('native:mergevectorlayers', params, feedback=feedback)

    # Fusion des routes primaires et secondaires
    mergeRoads = ['data/transport/route_primaire.shp',
              'data/transport/route_secondaire.shp']
    params = {
        'LAYERS': mergeRoads,
        'CRS': 'EPSG:3035',
        'OUTPUT': 'data/transport/routes.shp'
    }
    processing.run('native:mergevectorlayers', params, feedback=feedback)

    # Empaquetage de tout le bâti
    mergeBuildings = []
    for path in os.listdir('data/bati'):
        if os.path.splitext(path)[1] == '.shp':
            layer = QgsVectorLayer('data/bati/' + path)
            layer.dataProvider().createSpatialIndex()
            layer.addExpressionField('$area', QgsField(
                'AIRE', QVariant.Double, len=10, prec=2))
            mergeBuildings.append(layer)
    params = {
        'LAYERS': mergeBuildings,
        'CRS': 'EPSG:3035',
        'OUTPUT': 'data/bati/bati_merged.shp'
    }
    processing.run('native:mergevectorlayers', params, feedback=feedback)
    del mergePai, mergeRoads, mergeBuildings, layer

    # Nettoyage dans la couche de bâti indif. avec les PAI et surfaces d'activité
    bati_indif = QgsVectorLayer(
        'data/bati/bati_indifferencie.shp', 'bati_indif')
    bati_indif.dataProvider().createSpatialIndex()
    cleanPolygons = []
    cleanPoints = ['data/pai/pai_merged.shp']

    ## On ignore les zones industrielles et commerciales
    params = {
        'INPUT': 'data/surface_activite.shp',
        'EXPRESSION': """ "CATEGORIE" != 'Industriel ou commercial' """,
        'OUTPUT': 'data/restriction/surf_activ_non_com.shp',
        'FAIL_OUTPUT': 'memory:'
    }
    processing.run('native:extractbyexpression', params, feedback=feedback)

    ## Fusion des polygones pour éviter les résidus avec le prédicat WITHIN
    params = {
        'INPUT': 'data/restriction/surf_activ_non_com.shp',
        'FIELD': [],
        'OUTPUT': 'memory:'
    }
    res = processing.run('native:dissolve', params, feedback=feedback)
    cleanPolygons.append(res['OUTPUT'])

    if os.path.exists('data/restriction/exclusion.shp'):
        cleanPolygons.append('data/restriction/exclusion.shp')

    buildingCleaner(bati_indif, cleanPolygons, cleanPoints, 'data/bati/bati_clean.shp')

    # Intersection du bâti résidentiel avec les quartiers IRIS
    params = {
        'INPUT': 'data/bati/bati_clean.shp',
        'OVERLAY': 'data/iris.shp',
        'INPUT_FIELDS': ['ID', 'HAUTEUR', 'NB_NIV'],
        'OVERLAY_FIELDS': ['CODE_IRIS', 'NOM_IRIS', 'TYP_IRIS', 'POP14', 'TXRP14'],
        'OUTPUT': 'data/bati/bati_inter_iris.shp'
    }
    processing.run('qgis:intersection', params, feedback=feedback)

if not os.path.exists('data/' + mode):
    os.mkdir('data/' + mode)

    # Création d'une grille régulière
    zone_buffer = QgsVectorLayer('data/zone_buffer.shp', 'zone_buffer')
    extent = zone_buffer.extent()
    extentStr = str(extent.xMinimum()) + ',' + str(extent.xMaximum()) + ',' + \
        str(extent.yMinimum()) + ',' + str(extent.yMaximum()) + ' [EPSG:3035]'
    params = {
        'TYPE': 2,
        'EXTENT': extentStr,
        'HSPACING': int(gridSize),
        'VSPACING': int(gridSize),
        'HOVERLAY': 0,
        'VOVERLAY': 0,
        'CRS': 'EPSG:3035',
        'OUTPUT': 'data/' + mode + '/grid.shp'}
    processing.run('qgis:creategrid', params, feedback=feedback)
    del zone_buffer, extent, extentStr

    # Intersection entre le couche de bâti nettoyée et la grille
    buildings = QgsVectorLayer('data/bati/bati_inter_iris.shp', 'bati_inter_iris')
    grid = QgsVectorLayer('data/' + mode + '/grid.shp', 'grid')
    iris = QgsVectorLayer('data/iris.shp')
    popGrid(buildings, grid, iris, 'data/' + mode + '/')

    bati_industriel = QgsVectorLayer('data/bati/bati_industriel.shp', 'indus')
    bati_remarquable = QgsVectorLayer('data/bati/bati_industriel.shp', 'remarq')
    listeBati = [bati_industriel, bati_remarquable]
    restrictGrid(listeBati, grid, 'data/' + mode + '/')
    del listeBati, bati_industriel, bati_remarquable,

    # Préparation du fichier des IRIS - création des ID et de la matrice de contiguïté
    iris = QgsVectorLayer('data/' + mode + '/iris_stat.shp')
    contiguityMatrix(iris, 'data/' + mode + '/iris_id.csv')

    # Objet pour transformation de coordonées
    l93 = QgsCoordinateReferenceSystem()
    l93.createFromString('EPSG:2154')
    laea = QgsCoordinateReferenceSystem()
    laea.createFromString('EPSG:3035')
    trCxt = QgsCoordinateTransformContext()
    coordTr = QgsCoordinateTransform(l93, laea, trCxt)

    # BBOX pour extraction du MNT
    grid = QgsVectorLayer('data/' + mode + '/grid_stat.shp', 'grid')
    extent = grid.extent()
    extentL93 = coordTr.transform(extent, coordTr.ReverseTransform)

    # Fusion des tuiles MNT dans la zone d'étude
    os.mkdir('data/' + mode + '/tif')
    demList = demExtractor('../global_data/rge/' + dept + '/bdalti/', extentL93)

    xMin = extent.xMinimum()
    yMin = extent.yMinimum()
    xMax = extent.xMaximum()
    yMax = extent.yMaximum()
    gdal.Warp(
        'data/' + mode + '/tif/mnt.tif', demList,
        format='GTiff', outputType=gdal.GDT_Float32,
        xRes=int(gridSize), yRes=int(gridSize),
        resampleAlg='cubicspline',
        srcSRS='EPSG:2154', dstSRS='EPSG:3035',
        outputBounds=(xMin, yMin, xMax, yMax),
        srcNodata=-99999)

    # Calcul de pente en %
    gdal.DEMProcessing(
        'data/' + mode + '/tif/slope.tif',
        'data/' + mode + '/tif/mnt.tif',
        'slope', format='GTiff',
        slopeFormat='percent')

    # Mise en forme finale des données raster pour le modèle
    if not os.path.exists(mode):
        os.mkdir(mode)
    extentStr = str(xMin) + ',' + str(xMax) + ',' + str(yMin) + ',' + str(yMax) + ' [EPSG:3035]'

    # Rasterisations
    rasterize('data/' + mode + '/grid_stat.shp', mode + '/population.tif', 'pop', 'uint16')
    rasterize('data/' + mode + '/grid_stat.shp', 'data/' + mode + '/tif/s_planch_grid.tif', 's_planch')
    rasterize('data/' + mode + '/iris_stat.shp', mode + '/iris_id.tif', 'ID', 'uint16')
    rasterize('data/' + mode + '/iris_stat.shp', 'data/' + mode + '/tif/seuil_q3_iris.tif', 'PLANCH_Q3')
    rasterize('data/' + mode + '/iris_stat.shp', 'data/' + mode + '/tif/nb_m2_iris.tif', 'NB_M2_HAB')
    rasterize('data/' + mode + '/iris_stat.shp', mode + '/masque.tif', dtype='byte', invert=True)
    rasterize('data/ecologie.shp', mode + '/ecologie.tif', 'interet')

    ds = gdal.Open(mode + '/population.tif')
    cols = ds.RasterXSize
    rows = ds.RasterYSize
    proj = ds.GetProjection()
    geot = ds.GetGeoTransform()
    driver = gdal.GetDriverByName('GTiff')

    ds = gdal.Open( mode + '/masque.tif')
    irisMask = ds.ReadAsArray()
    ds = gdal.Open('data/' + mode + '/tif/slope.tif')
    slope = ds.ReadAsArray()
    slopeMask = np.where(slope >= 30, 1, 0)

    ds = None

qgs.exitQgis()
print('Terminé à  ' + time.strftime('%H:%M:%S'))
