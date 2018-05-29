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
        i = 0
        writer = open(path + tab + '.csv', 'w')
        for field in modelSorted[tab]:
            i += 1
            val = field
            if i < len(modelSorted[tab]):
                val += ','
            else:
                val += '\n'
            writer.write(val)
        writer.close()

    for tab in tables :
        with open(inputDir + 'ART.DC21.W17' + dep + '0.' + tab + '.A2017.N000671', 'r') as file:
            if tab == 'BATI' :
                enreg = ['00','10','30','36','40','50','60']
                for line in file.readlines():
                    countLines += 1
                    if len(line) >= 82:
                        e = line[30:32]
                        if e in enreg:
                            i = 0
                            with open(path + tab + e + '.csv', 'a') as writer:
                                for field in modelSorted[tab + e]:
                                    i += 1
                                    deb = int(model[tab + e][field][0])
                                    fin = int(model[tab + e][field][1])
                                    if len(line) >= fin:
                                        val = line[deb:fin]
                                        if '\n' in val:
                                            val = val.replace('\n','')
                                    else:
                                        val = 'NULL'
                                    if i < len(modelSorted[tab + e]):
                                        val += ','
                                    else:
                                        val += '\n'
                                    writer.write(val)

            if tab == 'LLOC':
                for line in file.readlines():
                    countLines += 1
                    if len(line) >= 61:
                        i = 0
                        with open(path + tab + '.csv', 'a') as writer:
                            for field in modelSorted[tab]:
                                i += 1
                                deb = int(model[tab][field][0])
                                fin = int(model[tab][field][1])
                                if len(line) >= fin:
                                    val = line[deb:fin]
                                    if '\n' in val:
                                        val = val.replace('\n','')
                                else:
                                    val = 'NULL'
                                if i < len(modelSorted[tab]):
                                    val += ','
                                else:
                                    val += '\n'
                                writer.write(val)

            if tab == 'NBAT':
                enreg = ['10','21','30','36']
                for line in file.readlines():
                    countLines += 1
                    if len(line) >= 89:
                        e = line[19:21]
                        if e in enreg:
                            i = 0
                            with open(path + tab + e + '.csv', 'a') as writer:
                                for field in modelSorted[tab + e]:
                                    i += 1
                                    deb = int(model[tab + e][field][0])
                                    fin = int(model[tab + e][field][1])
                                    if len(line) >= fin:
                                        val = line[deb:fin]
                                        if '\n' in val:
                                            val = val.replace('\n','')
                                    else:
                                        val = 'NULL'
                                    if i < len(modelSorted[tab + e]):
                                        val += ','
                                    else:
                                        val += '\n'
                                    writer.write(val)

            if tab == 'PDLL':
                enreg = ['10','20','30']
                for line in file.readlines():
                    countLines += 1
                    if len(line) >= 98:
                        e = line[25:27]
                        if e in enreg:
                            i = 0
                            with open(path + tab + e + '.csv', 'a') as writer:
                                for field in modelSorted[tab + e]:
                                    i += 1
                                    deb = int(model[tab + e][field][0])
                                    fin = int(model[tab + e][field][1])
                                    if len(line) >= fin:
                                        val = line[deb:fin]
                                        if '\n' in val:
                                            val = val.replace('\n','')
                                    else:
                                        val = 'NULL'
                                    if i < len(modelSorted[tab + e]):
                                        val += ','
                                    else:
                                        val += '\n'
                                    writer.write(val)

            if tab == 'PROP':
                for line in file.readlines():
                    countLines += 1
                    if len(line) >= 121:
                        i = 0
                        with open(path + tab + '.csv', 'a') as writer:
                            for field in modelSorted[tab]:
                                i += 1
                                deb = int(model[tab][field][0])
                                fin = int(model[tab][field][1])
                                if len(line) >= fin:
                                    val = line[deb:fin]
                                    if '\n' in val:
                                        val = val.replace('\n','')
                                else:
                                    val = 'NULL'
                                if i < len(modelSorted[tab]):
                                    val += ','
                                else:
                                    val += '\n'
                                writer.write(val)

print('Terminé  à ' + time.strftime('%H:%M:%S'))
end_time = time.time()
execTime = end_time - start_time
execMin = round(execTime // 60)
execSec = round(execTime % 60)
nbLineSec = round(countLines // execTime)

print("Temps d'execution : " + str(round(execMin)) + "m " + str(execSec) + "s")
print(str(countLines) + ' lignes traitées')
print(str(nbLineSec) + ' lignes par secondes')
