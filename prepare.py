#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import re
import time
import gdal
import numpy
import pandas
import csv

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
    QgsVectorLayerJoinInfo
)
from qgis.analysis import QgsNativeAlgorithms
from PyQt5.QtCore import QVariant

QgsApplication.setPrefixPath('/usr', True)
qgs = QgsApplication([], GUIenabled=False)
qgs.initQgis()
qgs.setMaxThreads(-1)

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
    elif mode == 'simple':
        gridSize = '50'
    else:
        print('Deux valeurs possibles pour le mode de seuillage : simple - strict ')
        sys.exit()
else :
    mode = 'simple'
    gridSize = '50'

# Découpe un ensemble de layers avec gestion de l'encodage
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

# Enregistre un objet QgsVectorLayer sur le disque
def to_shp(layer, path):
    writer = QgsVectorFileWriter(
        path, 'utf-8', layer.fields(), layer.wkbType(), layer.sourceCrs(), 'ESRI Shapefile')
    writer.addFeatures(layer.getFeatures())

# Enregistre un fichier .tif à partir d'un array et de variables GDAL stockée au préalable
def to_tif(array, cols, rows, dtype, proj, geot, path):
    ds_out = driver.Create(path, cols, rows, 1, dtype)
    ds_out.SetProjection(proj)
    ds_out.SetGeoTransform(geot)
    ds_out.GetRasterBand(1).WriteArray(array)
    ds_out = None

print('Commencé à ' + time.strftime('%H:%M:%S'))

# Gestion des XLS de l'INSEE, à faire une seule fois
if not os.path.exists('../global_data/insee/csv'):
    os.mkdir('../global_data/insee/csv')
    inseePop09 = pandas.read_excel(
        '../global_data/insee/BTX_IC_POP_2009.xls', skiprows=(0, 1, 2, 3, 4))
    inseePop09.to_csv('../global_data/insee/csv/inseePop09.csv',
                      index=0, columns=['IRIS', 'P09_POP'])
    del inseePop09
    inseePop14 = pandas.read_excel(
        '../global_data/insee/base-ic-evol-struct-pop-2014.xls', skiprows=(0, 1, 2, 3, 4))
    inseePop14.to_csv('../global_data/insee/csv/inseePop14.csv',
                      index=0, columns=['IRIS', 'P14_POP'])
    del inseePop14
    inseeLog14 = pandas.read_excel(
        '../global_data/insee/base-ic-logement-2014.xls', skiprows=(0, 1, 2, 3, 4))
    inseeLog14['P14_TXRP'] = inseeLog14['P14_RP'] / inseeLog14['P14_LOG']
    inseeLog14.to_csv('../global_data/insee/csv/inseeLog14.csv',
                      index=0, columns=['IRIS', 'P14_RP', 'P14_TXRP'])
    del inseeLog14

# Découpe et reprojection de la donnée en l'absence du dossier ./temp + fusion de PAI et du bâti
if not os.path.exists('data'):
    os.mkdir('data')

    # Traitement de l'XLS de population
    csvPop09 = QgsVectorLayer(
        '../global_data/insee/csv/inseePop09.csv', 'delimitedtext')
    csvPop09.startEditing()
    csvPop09.addExpressionField(
        'round(to_real("P09_POP"))', QgsField('POP09', QVariant.Int))
    csvPop09.commitChanges()

    csvPop14 = QgsVectorLayer(
        '../global_data/insee/csv/inseePop14.csv', 'delimitedtext')
    csvPop14.startEditing()
    csvPop14.addExpressionField(
        'round(to_real("P14_POP"))', QgsField('POP14', QVariant.Int))
    csvPop14.commitChanges()

    # Traitement de l'XLS de logement
    csvLog14 = QgsVectorLayer(
        '../global_data/insee/csv/inseeLog14.csv', 'delimitedtext')
    csvLog14.startEditing()
    csvLog14.addExpressionField(
        'round(to_real("P14_RP"))', QgsField('RP14', QVariant.Int))
    csvLog14.addExpressionField(
        'to_real("P14_TXRP")', QgsField('TXRP14', QVariant.Double))
    csvLog14.commitChanges()

    # Jointure avec données INSEE et extraction des IRIS dans la zone
    zone = QgsVectorLayer('zone.shp', 'zone')
    zone.dataProvider().createSpatialIndex()
    iris = QgsVectorLayer('../global_data/rge/IRIS_GE.SHP', 'iris')
    join(iris, 'CODE_IRIS', csvPop09, 'IRIS', ['P09_POP'])
    join(iris, 'CODE_IRIS', csvPop14, 'IRIS', ['P14_POP'])
    join(iris, 'CODE_IRIS', csvLog14, 'IRIS', ['P14_RP', 'P14_TXRP'])
    expr = '("POP14"-"POP09")/"POP09"/5*100'
    iris.addExpressionField(expr, QgsField('EVO_0914', QVariant.Double))

    # Tampon de 1000m autour de la zone pour extrations des quartiers et des PAI
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

    # Extraction des quartiers IRIS avec jointures
    params = {
        'INPUT': iris,
        'PREDICATE': 6,
        'INTERSECT': zone_buffer,
        'OUTPUT': 'memory:iris'
    }
    res = processing.run('native:extractbylocation', params, feedback=feedback)
    reproj(res['OUTPUT'], 'data/')
    del csvPop09, csvPop14, csvLog14, iris

    # Extraction des données dans la zone d'étude
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

    # Préparation de la couche transport
    transports = []
    if os.path.exists('transport_commun.shp'):
        reproj(clip('transport_commun.shp', zone_buffer), '/data/transport/')
        layer = QgsVectorLayer('/data/transport/transport_commun.shp', 'transport_commun')
        transports.append(layer)

    params = {
        'INPUT': 'data/pai/transport.shp',
        'EXPRESSION': """ "NATURE" = 'Station de métro' """,
        'OUTPUT': 'memory:transport_commun_pai',
        'FAIL_OUTPUT': 'memory:fail'
    }
    res = processing.run('native:extractbyexpression', params, feedback=feedback)
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

    # Classification des points geosirene
    os.mkdir('data/geosirene')
    geosirene = QgsVectorLayer(
        '../global_data/sirene/geosirene.shp', 'geosirene')
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
    sireneLayer = reproj(clip(geosirene, zone_buffer))

    params = {
        'INPUT': sireneLayer,
        'FIELD': 'type',
        'OUTPUT': 'data/geosirene/'
    }
    processing.run('qgis:splitvectorlayer', params, feedback=feedback)

    # Correction de l'OCS
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

    # Correction du PLU
    if os.path.exists('plu.shp'):
        plu = QgsVectorLayer('plu.shp', 'plu')
        plu.setProviderEncoding('windows-1258')
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
        reproj(res['OUTPUT'], 'data/')
        del plu

    # Traitement d'une couche facultative pour exclusion de zones bâties lors du calcul de densité
    os.mkdir('data/restrict')
    if os.path.exists('exclusion.shp'):
        reproj(clip('exclusion.shp', zone), 'data/restrict/')

    # Reprojection en LAEA
    reproj(zone, 'data/')
    reproj(zone_buffer, 'data/')
    del zone, zone_buffer

    # Fusion des couches PAI
    cleanPai = [
        'data/pai/administratif_militaire.shp',
        'data/pai/culture_loisirs.shp',
        'data/pai/industriel_commercial.shp',
        'data/pai/religieux.shp',
        'data/pai/sante.shp',
        'data/pai/science_enseignement.shp'
    ]
    params = {
        'LAYERS': cleanPai,
        'CRS': 'EPSG:3035',
        'OUTPUT': 'data/pai/pai_merged.shp'
    }
    processing.run('native:mergevectorlayers', params, feedback=feedback)

    # Fusion des routes primaires et secondaires
    routes = ['data/transport/route_primaire.shp', 'data/transport/route_secondaire.shp']
    params = {
        'LAYERS': routes,
        'CRS': 'EPSG:3035',
        'OUTPUT': 'data/transport/routes.shp'
    }
    processing.run('native:mergevectorlayers', params, feedback=feedback)

    # Empaquetage de tout le bâti
    batiPkg = []
    for path in os.listdir('data/bati'):
        if os.path.splitext(path)[1] == '.shp':
            layer = QgsVectorLayer('data/bati/' + path)
            layer.dataProvider().createSpatialIndex()
            layer.addExpressionField('$area', QgsField(
                'AIRE', QVariant.Double, len=10, prec=2))
            batiPkg.append(layer)
    params = {
        'LAYERS': batiPkg,
        'CRS': 'EPSG:3035',
        'OUTPUT': 'data/bati/bati_merged.shp'
    }
    processing.run('native:mergevectorlayers', params, feedback=feedback)
    del cleanPai, routes, batiPkg, layer

    # ---! Nettoyage dans la couche de bâti indif. avec les PAI et surfaces d'activité
    bati_indif = QgsVectorLayer(
        'data/bati/bati_indifferencie.shp', 'bati_indif')
    bati_indif.dataProvider().createSpatialIndex()

    # Selection avec la couche facultative 'exclusion.shp'
    if os.path.exists('data/restrict/exclusion.shp'):
        params = {
            'INPUT': bati_indif,
            'PREDICATE': 6,
            'INTERSECT': 'data/restrict/exclusion.shp',
            'METHOD': 0
        }
        processing.run('native:selectbylocation', params, feedback=feedback)

    # On ignore les zones industrielles et commerciales
    params = {
        'INPUT': 'data/surface_activite.shp',
        'EXPRESSION': """ "CATEGORIE" != 'Industriel ou commercial' """,
        'OUTPUT': 'data/restrict/surf_activ_non_com.shp',
        'FAIL_OUTPUT': 'memory:'
    }
    processing.run('native:extractbyexpression', params, feedback=feedback)

    # Fusion des polygones pour éviter les résidus avec le prédicat WITHIN
    params = {
        'INPUT': 'data/restrict/surf_activ_non_com.shp',
        'FIELD': [],
        'OUTPUT': 'memory:'
    }
    res = processing.run('native:dissolve', params, feedback=feedback)
    surfActivNonCom = res['OUTPUT']

    # Selection si le bâtiment est situé dans une zone d'activité
    params = {
        'INPUT': bati_indif,
        'PREDICATE': 6,
        'INTERSECT': surfActivNonCom,
        'METHOD': 1
    }
    processing.run('native:selectbylocation', params, feedback=feedback)
    del surfActivNonCom

    # Selection si la bâtiment intersecte PAI
    params = {
        'INPUT': bati_indif,
        'PREDICATE': 0,
        'INTERSECT': 'data/pai/pai_merged.shp',
        'METHOD': 1
    }
    processing.run('native:selectbylocation', params, feedback=feedback)

    # Estimation du nombre d'étages
    expr = """ CASE
        WHEN "HAUTEUR" = 0 THEN 1
        WHEN "HAUTEUR" < 5 THEN 1
        ELSE "HAUTEUR"/3 END
    """
    bati_indif.addExpressionField(
        expr, QgsField('NB_NIV', QVariant.Int, len=2))

    # Nettoyage des bâtiments supposés trop grand ou trop petit pour être habités
    params = {
        'INPUT': bati_indif,
        'EXPRESSION': ' $area < 50 OR $area > 10000 ',
        'METHOD': 1
    }
    processing.run('qgis:selectbyexpression', params, feedback=feedback)

    # Inversion de la selection pour export final
    bati_indif.invertSelection()
    params = {
        'INPUT': bati_indif,
        'OUTPUT': 'data/bati/bati_clean.shp'
    }
    processing.run('native:saveselectedfeatures', params, feedback=feedback)
    del bati_indif

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
        'OUTPUT': 'data/' + mode + '/grid.shp'
    }
    processing.run('qgis:creategrid', params, feedback=feedback)
    del zone_buffer, extent, extentStr
    grid = QgsVectorLayer('data/' + mode + '/grid.shp', 'grid')

    bati_inter_iris = QgsVectorLayer('data/bati/bati_inter_iris.shp')
    bati_inter_iris.dataProvider().createSpatialIndex()
    bati_inter_iris.addExpressionField('$area', QgsField(
        'area_i', QVariant.Double, len=10, prec=2))
    expr = ' "area_i" * "NB_NIV" * "TXRP14" '
    bati_inter_iris.addExpressionField(expr, QgsField(
        'planch', QVariant.Double, len=10, prec=2))
    expr = ' ("planch" / sum("planch", group_by:="CODE_IRIS")) * "POP14" '
    bati_inter_iris.addExpressionField(expr, QgsField(
        'pop_bati', QVariant.Double, len=10, prec=2))

    params = {
        'INPUT': bati_inter_iris,
        'OVERLAY': 'data/' + mode + '/grid.shp',
        'INPUT_FIELDS': ['ID', 'HAUTEUR', 'NB_NIV', 'CODE_IRIS', 'NOM_IRIS', 'TYP_IRIS', 'POP14', 'TXRP14', 'area_i', 'planch', 'pop_bati'],
        'OVERLAY_FIELDS': ['id'],
        'OUTPUT': 'data/' + mode + '/bati_inter_grid.shp'
    }
    processing.run('qgis:intersection', params, feedback=feedback)
    del bati_inter_iris

    bati_inter_grid = QgsVectorLayer(
        'data/' + mode + '/bati_inter_grid.shp', 'bati_inter_grid')
    bati_inter_grid.addExpressionField('$area', QgsField(
        'area_g', QVariant.Double, len=10, prec=2))
    expr = ' "area_g" / "area_i" * "pop_bati" '
    bati_inter_grid.addExpressionField(expr, QgsField(
        'pop_cell', QVariant.Double, len=10, prec=2))
    expr = ' "area_g" * "NB_NIV" * "TXRP14" '
    bati_inter_grid.addExpressionField(expr, QgsField(
        'planch_g', QVariant.Double, len=10, prec=2))
    expr = ' "planch_g" / "pop_cell" '
    bati_inter_grid.addExpressionField(expr, QgsField(
        'nb_m2_hab', QVariant.Double, len=10, prec=2))

    params = {
        'INPUT': bati_inter_grid,
        'VALUES_FIELD_NAME': 'pop_cell',
        'CATEGORIES_FIELD_NAME': 'id_2',
        'OUTPUT': 'data/' + mode + '/stat_pop_grid.csv'
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)

    params = {
        'INPUT': bati_inter_grid,
        'VALUES_FIELD_NAME': 'planch_g',
        'CATEGORIES_FIELD_NAME': 'id_2',
        'OUTPUT': 'data/' + mode + '/stat_planch_grid.csv'
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)

    params = {
        'INPUT': bati_inter_grid,
        'VALUES_FIELD_NAME': 'nb_m2_hab',
        'CATEGORIES_FIELD_NAME': 'CODE_IRIS',
        'OUTPUT': 'data/' + mode + '/stat_nb_m2_iris.csv'
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)

    params = {
        'INPUT': bati_inter_grid,
        'VALUES_FIELD_NAME': 'planch_g',
        'CATEGORIES_FIELD_NAME': 'CODE_IRIS',
        'OUTPUT': 'data/' + mode + '/stat_planch_iris.csv'
    }
    processing.run('qgis:statisticsbycategories', params, feedback=feedback)

    to_shp(bati_inter_grid, 'data/' + mode + '/bati_inter_grid.shp')
    del bati_inter_grid

    csvPopG = QgsVectorLayer(
        'data/' + mode + '/stat_pop_grid.csv', 'delimitedtext')
    csvPopG.addExpressionField(
        'to_real("sum")', QgsField('pop', QVariant.Double))

    csvPlanchG = QgsVectorLayer(
        'data/' + mode + '/stat_planch_grid.csv', 'delimitedtext')
    csvPlanchG.addExpressionField(
        'to_real("sum")', QgsField('s_planch', QVariant.Double))

    csvM2I = QgsVectorLayer(
        'data/' + mode + '/stat_nb_m2_iris.csv', 'delimitedtext')
    csvM2I.addExpressionField(
        'to_real("mean")', QgsField('nb_m2_hab', QVariant.Double))

    csvPlanchI = QgsVectorLayer(
        'data/' + mode + '/stat_planch_iris.csv', 'delimitedtext')
    csvPlanchI.addExpressionField(
        'to_real("q3")', QgsField('planch_q3', QVariant.Double))

    statBlackList = ['count','unique','min','max','range','sum','mean','median','stddev','minority','majority','q1','q3','iqr']

    join(grid, 'id', csvPopG, 'id_2', statBlackList)
    join(grid, 'id', csvPlanchG, 'id_2', statBlackList)
    to_shp(grid, 'data/' + mode + '/grid_stat.shp')
    del csvPopG, csvPlanchG

    iris = QgsVectorLayer('data/iris.shp', 'iris')
    join(iris, 'CODE_IRIS', csvPlanchI, 'CODE_IRIS', statBlackList)
    join(iris, 'CODE_IRIS', csvM2I, 'CODE_IRIS', statBlackList)
    iris.addExpressionField('$id + 1', QgsField('id', QVariant.Int, len=4))
    to_shp(iris, 'data/' + mode + '/iris_stat.shp')
    del csvPlanchI, csvM2I, statBlackList

    iris = QgsVectorLayer('data/' + mode + '/iris_stat.shp')
    irisDF = pandas.DataFrame(None,[i for i in range(iris.featureCount())],['id','code','nom','population','contiguite'])
    for i in range(iris.featureCount()):
        feat = iris.getFeature(i)
        irisDF.id[i] = feat.attribute(13)
        irisDF.code[i] = feat.attribute(3)
        irisDF.nom[i] = feat.attribute(4)
        irisDF.population[i] = feat.attribute(7)
        irisDF.contiguite[i] = []
        for poly in iris.getFeatures():
            if feat.geometry().touches(poly.geometry()):
                irisDF.contiguite[i].append(poly.attribute(13))
    irisDF.to_csv('data/' + mode + '/iris_id.csv', index=0)

    # Objet pour transformation de coordonées
    l93 = QgsCoordinateReferenceSystem()
    l93.createFromString('EPSG:2154')
    laea = QgsCoordinateReferenceSystem()
    laea.createFromString('EPSG:3035')
    trCxt = QgsCoordinateTransformContext()
    coordTr = QgsCoordinateTransform(l93, laea, trCxt)

    # BBOX pour extraction du MNT
    extent3035 = grid.extent()
    extent2154 = coordTr.transform(extent3035, coordTr.ReverseTransform)

    # Préparation du MNT
    tileList = []
    for tile in os.listdir('../global_data/rge/' + dept + '/bdalti/'):
        if os.path.splitext(tile)[1] == '.asc':
            path = '../global_data/rge/' + dept + '/bdalti/' + tile
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
            if extent2154.intersects(tileExtent):
                tileList.append(path)

    xMin = extent3035.xMinimum()
    yMin = extent3035.yMinimum()
    xMax = extent3035.xMaximum()
    yMax = extent3035.yMaximum()

    gdal.Warp(
        'data/' + mode + '/mnt.tif', tileList,
        format='GTiff', outputType=gdal.GDT_Float32,
        xRes=int(gridSize), yRes=int(gridSize),
        resampleAlg='cubicspline',
        srcSRS='EPSG:2154', dstSRS='EPSG:3035',
        outputBounds=(xMin, yMin, xMax, yMax),
        srcNodata=-99999
    )
    del tileList

    gdal.DEMProcessing(
        'data/' + mode + '/slope.tif',
        'data/' + mode + '/mnt.tif',
        'slope',
        format='GTiff',
        slopeFormat='percent'
    )

qgs.exitQgis()

print('Terminé à  ' + time.strftime('%H:%M:%S'))
