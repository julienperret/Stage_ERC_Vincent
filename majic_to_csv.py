#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import sys
import csv
import time
import operator

inputDir = sys.argv[1]
modelDir = sys.argv[2]
outputDir  = sys.argv[3]
if not os.path.exists(outputDir):
    os.makedirs(outputDir)

start_time = time.time()
print("Commencé à " + time.strftime('%H:%M:%S'))

model = {}
tabList=os.listdir(modelDir)
tabList.sort()
for tab in tabList:
    with open(modelDir + tab) as file:
        reader = csv.reader(file)
        next(reader, None)
        tab = tab.replace('.csv','')
        model[tab]={str(row[4]):[int(row[0])-1,int(row[1])] for row in reader}

tmpModel = {}
for tab in model.keys():
    tmpModel[tab] = sorted(model[tab].items(), key=operator.itemgetter(1))
modelSorted = {tab:[field[0] for field in tmpModel[tab]] for tab in tmpModel.keys()}
del tmpModel

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

tables = ['BATI','LLOC','NBAT','PDLL','PROP']
countLines = 0
countDep = 0

for dep in depList:
    countDep += 1
    print("Traitement " + str(countDep) + "/" + str(len(depList)) + " : département n°" + dep)
    path = outputDir + dep + '/'
    if not os.path.exists(path):
        os.makedirs(path)
    for tab in model.keys():
        with open(path + tab + '.csv', 'w') as w:
            i = 0
            for field in modelSorted[tab]:
                i += 1
                v = field
                if i < len(modelSorted[tab]):
                    v += ','
                else:
                    v += '\n'
                w.write(v)

    for tab in tables :
        with open(inputDir + 'ART.DC21.W17' + dep + '0.' + tab + '.A2017.N000671', 'r') as r:
            if tab == 'BATI' :
                eList = ['00','10','30','36','40','50','60']
                for l in r:
                    countLines += 1
                    if len(l) >= 82:
                        e = l[30:32]
                        if e in eList:
                            i = 0
                            with open(path + tab + e + '.csv', 'a') as w:
                                for field in modelSorted[tab + e]:
                                    i += 1
                                    deb = int(model[tab + e][field][0])
                                    fin = int(model[tab + e][field][1])
                                    if len(l) >= fin:
                                        v = l[deb:fin]
                                        if '\n' in v:
                                            v = v.replace('\n','')
                                    else:
                                        v = 'NULL'
                                    if i < len(modelSorted[tab + e]):
                                        v += ','
                                    else:
                                        v += '\n'
                                    w.write(v)

            if tab == 'LLOC':
                for l in r:
                    countLines += 1
                    if len(l) >= 61:
                        i = 0
                        with open(path + tab + '.csv', 'a') as w:
                            for field in modelSorted[tab]:
                                i += 1
                                deb = int(model[tab][field][0])
                                fin = int(model[tab][field][1])
                                if len(l) >= fin:
                                    v = l[deb:fin]
                                    if '\n' in v:
                                        v = v.replace('\n','')
                                else:
                                    v = 'NULL'
                                if i < len(modelSorted[tab]):
                                    v += ','
                                else:
                                    v += '\n'
                                w.write(v)

            if tab == 'NBAT':
                eList = ['10','21','30','36']
                for l in r:
                    countLines += 1
                    if len(l) >= 89:
                        e = l[19:21]
                        if e in eList:
                            i = 0
                            with open(path + tab + e + '.csv', 'a') as w:
                                for field in modelSorted[tab + e]:
                                    i += 1
                                    deb = int(model[tab + e][field][0])
                                    fin = int(model[tab + e][field][1])
                                    if len(l) >= fin:
                                        v = l[deb:fin]
                                        if '\n' in v:
                                            v = v.replace('\n','')
                                    else:
                                        v = 'NULL'
                                    if i < len(modelSorted[tab + e]):
                                        v += ','
                                    else:
                                        v += '\n'
                                    w.write(v)

            if tab == 'PDLL':
                eList = ['10','20','30']
                for l in r:
                    countLines += 1
                    if len(l) >= 98:
                        e = l[25:27]
                        if e in eList:
                            i = 0
                            with open(path + tab + e + '.csv', 'a') as w:
                                for field in modelSorted[tab + e]:
                                    i += 1
                                    deb = int(model[tab + e][field][0])
                                    fin = int(model[tab + e][field][1])
                                    if len(l) >= fin:
                                        v = l[deb:fin]
                                        if '\n' in v:
                                            v = v.replace('\n','')
                                    else:
                                        v = 'NULL'
                                    if i < len(modelSorted[tab + e]):
                                        v += ','
                                    else:
                                        v += '\n'
                                    w.write(v)

            if tab == 'PROP':
                for l in r:
                    countLines += 1
                    if len(l) >= 121:
                        i = 0
                        with open(path + tab + '.csv', 'a') as w:
                            for field in modelSorted[tab]:
                                i += 1
                                deb = int(model[tab][field][0])
                                fin = int(model[tab][field][1])
                                if len(l) >= fin:
                                    v = l[deb:fin]
                                    if '\n' in v:
                                        v = v.replace('\n','')
                                else:
                                    v = 'NULL'
                                if i < len(modelSorted[tab]):
                                    v += ','
                                else:
                                    v += '\n'
                                w.write(v)

print('Terminé  à ' + time.strftime('%H:%M:%S'))
end_time = time.time()
execTime = end_time - start_time
execMin = round(execTime // 60)
execSec = round(execTime % 60)
nbLineSec = round(countLines // execTime)

print("Temps d'execution : " + str(round(execMin)) + "m " + str(execSec) + "s")
print(str(countLines) + ' lignes traitées')
print(str(nbLineSec) + ' lignes par secondes')
