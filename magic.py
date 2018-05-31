#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import sys
import csv
import operator
from ast import literal_eval
import multiprocessing as mp
from time import strftime, time

inputDir = sys.argv[1]
modelDir = sys.argv[2]
outputDir  = sys.argv[3]
if len(sys.argv) > 4:
    param = sys.argv[4]
    if param != 'all':
        if '[' in param:
            tables = literal_eval(param)
        elif len(param) == 4:
            tables = []
            tables.append(param)
if len(sys.argv) > 5:
    param = sys.argv[5]
    if '[' in param:
        depList = literal_eval(param)
    elif len(param) == 2:
        depList = []
        depList.append(param)
if not os.path.exists(outputDir):
    os.makedirs(outputDir)

# Pour affichage dynamique de la progression
def printer(string):
	sys.stdout.write("\r\x1b[K" + string)
	sys.stdout.flush()

# Fonctions
def writeHeaders(prefix, tab):
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

def getTuple(l, tab):
    i = 0
    tuple = ''
    for field in modelSorted[tab]:
        i += 1
        deb = int(model[tab][field][0])
        fin = int(model[tab][field][1])
        if fin <= len(l):
            v = l[deb:fin]
            if '\n' in v:
                v = v.replace('\n','')
        else:
            v = 'NULL'
        if i < len(modelSorted[tab]):
            v += ','
        tuple += v
    return tuple + '\n'

def writeLine(prefix, tab, line, minLen, eCutList):
    res = None
    e = line[eCutList[0]:eCutList[1]]
    res = re.search('[0-9]{2}', e)
    if res and e in eDic[tab]:
        with open(prefix + tab + e + '.csv', 'a') as w:
            w.write(getTuple(line, tab + e))

def parseTable(prefix, tab, dep):
    minLen = minLenDic[tab]
    with open(inputDir + 'ART.DC21.W17' + dep + '0.' + tab + '.A2017.N000671', 'r') as r:
        if tab in eCutDic.keys():
            eCutList = eCutDic[tab]
            for line in r:
                if len(line) >= minLen:
                    writeLine(prefix, tab, line, minLen, eCutList)
        else:
            with open(prefix + tab + '.csv', 'a') as w:
                for line in r:
                    if len(line) >= minLen:
                        w.write(getTuple(line, tab))
                        
try:
    # Variables globales
    model = {}
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

    start_time = time()
    print("Commencé à " + strftime('%H:%M:%S'))

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

    # Variables pour multithreading
    pool = mp.Pool()
    jobs = []
    # Itération dans les départements
    for dep in depList:
        prefix = outputDir + dep + '/'
        if not os.path.exists(prefix):
            os.makedirs(prefix)
        for tab in tables:
            jobs.append(pool.apply_async(parseTable,(prefix, tab, dep)))
            if tab not in eDic.keys():
                writeHeaders(prefix, tab)
            else:
                for e in eDic[tab]:
                    writeHeaders(prefix, tab + e)
    c = 0
    for j in jobs:
        j.get()
        c += 1
        progres = "Tâches terminées : %i/%i" %(c, len(jobs))
        printer(progres)
    pool.close()
    pool.join()

    end_time = time()
    execTime = end_time - start_time
    execMin = round(execTime // 60)
    execSec = round(execTime % 60)
    print("\nTemps d'execution : %im %is" %(execMin, execSec))

except:
    print sys.exc_info()
    sys.exit()
