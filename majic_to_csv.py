#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import sys
import csv
import time
import operator
from ast import literal_eval

inputDir = sys.argv[1]
modelDir = sys.argv[2]
outputDir  = sys.argv[3]
if len(sys.argv) > 4:
    param = sys.argv[4]
    if param != 'all':
        if '[' in param:
            tables = literal_eval(param)
        else:
            tables = []
            tables.append(param)
if len(sys.argv) > 5:
    param = sys.argv[5]
    if '[' in param:
        depList = literal_eval(param)
    else:
        depList = []
        depList.append(param)
if not os.path.exists(outputDir):
    os.makedirs(outputDir)

start_time = time.time()
print("Commencé à " + time.strftime('%H:%M:%S'))

if 'depList' not in globals():
    depList = []
    fileList = os.listdir(inputDir)
    fileList.sort()
    for f in fileList:
        res = None
        res = re.search('ART\.DC21\.W17([0-9]{2})0\.BATI\.A([0-9]{4})\.N000671', f)
        if res:
            dep = res.group(1)
            if dep not in depList:
                depList.append(dep)

def getTuple(l, tab):
    i = 0
    tuple = ''
    for field in modelSorted[tab]:
        i += 1
        deb = int(model[tab][field][0])
        fin = int(model[tab][field][1])
        if fin <= len(line):
            v = l[deb:fin]
            if '\n' in v:
                v = v.replace('\n','')
        else:
            v = 'NULL'
        if i < len(modelSorted[tab]):
            v += ','
        tuple += v
    return tuple + '\n'

# Lecture d'une table t depuis un flux open() r, écriture d'une table w
def wLine(line, tab, minLen, w=None, eCutList=None):
    if eCutList and not w:
        res = None
        if len(line) >= minLen:
            e = line[eCutList[0]:eCutList[1]]
            res = re.search('[0-9]{2}', e)
            if res and e in eDic[tab]:
                with open(prefix + tab + e + '.csv', 'a', 65536) as w:
                    t = getTuple(line, tab + e)
                    w.write(t)
    elif w:
        if len(line) >= minLen:
            t = getTuple(line, tab)
            w.write(t)

# Variables globales
model = {}
countDep = 0
countLines = 0
eDic = {
    'BATI': ['00','10','30','36','40','50','60'],
    'NBAT': ['10','21','30','36'],
    'PDLL': ['10','20','30']
}
eCutDic = {
    'BATI': [30, 32],
    'NBAT': [19, 21],
    'PDLL': [25,27]
}
minLenDic = { 'BATI': 82, 'LLOC': 61, 'NBAT': 89, 'PDLL': 98, 'PROP': 121 }
modList = os.listdir(modelDir)
modList.sort()
if 'tables' not in globals():
    tables = ['BATI','LLOC','NBAT','PDLL','PROP']
else:
    tables.append(uTable)

# Création de la structure de recherche des valeurs de découpe {'':{'':[]}}
for tab in modList:
    with open(modelDir + tab) as file:
        reader = csv.reader(file)
        next(reader, None)
        tab = tab.replace('.csv','')
        model[tab]={str(row[4]):[int(row[0])-1,int(row[1])] for row in reader}

# Tri du dictionnaire en fonction de la première valeur début de getTuple, utilisée pour créer la ligne dans le bon ordre
tmpModel = {}
for tab in model.keys():
    tmpModel[tab] = sorted(model[tab].items(), key=operator.itemgetter(1))
modelSorted = {tab:[field[0] for field in tmpModel[tab]] for tab in tmpModel.keys()}
del tmpModel

# Boucle centrale
for dep in depList:
    countDep += 1
    print("Traitement " + str(countDep) + "/" + str(len(depList)) + " : département n°" + dep)
    prefix = outputDir + dep + '/'
    if not os.path.exists(prefix):
        os.makedirs(prefix)

    # Ecriture des fichiers avec headers dans le dossier outputDir + dep
    for tab in model.keys():
        with open(prefix + tab + '.csv', 'w') as w:
            i = 0
            for field in modelSorted[tab]:
                i += 1
                h = field
                if i < len(modelSorted[tab]):
                    h += ','
                else:
                    h += '\n'
                w.write(h)

    for tab in tables:
        with open(inputDir + 'ART.DC21.W17' + dep + '0.' + tab + '.A2017.N000671', 'r', 65536) as r:
            minLen = minLenDic[tab]
            if tab in eCutDic.keys():
                eCutList = eCutDic[tab]
                for line in r:
                    countLines += 1
                    wLine(line, tab, minLen, None, eCutList)
            else:
                with open(prefix + tab + '.csv', 'a', 65536) as w:
                    for line in r:
                        countLines += 1
                        wLine(line, tab, minLen, w, None)

end_time = time.time()
execTime = end_time - start_time
execMin = round(execTime // 60)
execSec = round(execTime % 60)
nbLineSec = round(countLines // execTime)

print('Terminé  à ' + time.strftime('%H:%M:%S'))
print("Temps d'execution : " + str(round(execMin)) + "m " + str(execSec) + "s")
print(str(countLines) + ' lignes traitées')
print(str(nbLineSec) + ' lignes par secondes')

sys.exit()
