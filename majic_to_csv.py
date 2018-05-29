#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import sys
import time
import operator
import pandas as pd

inputDir = sys.argv[1]
outputDir = sys.argv[2]
modelDir = sys.argv[3]
if not os.path.exists(outputDir):
    os.makedirs(outputDir)

start_time = time.time()
print("Commencé à " + time.strftime('%H:%M:%S'))

model = {}
tabList=os.listdir(modelDir)
tabList.sort()
for tab in tabList:
    df = pd.read_csv(modelDir + tab)
    tab = tab.replace('.csv','')
    model[tab]={str(row[4]):[row[0]-1,row[1]] for _, row in df.iterrows()}

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

done = 0
tables = ['BATI','LLOC','NBAT','PDLL','PROP']

for dep in depList:
    path = outputDir + dep + '/'
    if not os.path.exists(path):
        os.makedirs(path)
    for tab in model.keys():
        writer = open(path + tab + '.csv', 'w')
        i = 1
        for field in modelSorted[tab]:
            val = field
            if i < len(modelSorted[tab]):
                val += ','
            else:
                val += '\n'
            writer.write(val)
            i += 1
        writer.close()

    for tab in tables :
        with open(inputDir + 'ART.DC21.W17' + dep + '0.' + tab + '.A2017.N000671') as file:
            if tab == 'BATI' :
                enreg = ['00','10','30','36','40','50','60']
                for line in file.readlines():
                    e = line[30:32]
                    if e in enreg:
                        done += 1
                        writer = open(path + tab + e + '.csv', 'a')
                        i = 1
                        for field in modelSorted[tab + e]:
                            deb = int(model[tab + e][field][0])
                            fin = int(model[tab + e][field][1])
                            if len(line) >= fin:
                                val = line[deb:fin]
                            else:
                                val = 'NULL'
                            if i < len(modelSorted[tab + e]):
                                val += ','
                            else:
                                val += '\n'
                            writer.write(val)
                            i += 1
                        writer.close()
            if tab == 'LLOC':
                for line in file.readlines():
                    if len(line) >= 60:
                        done += 1
                        writer = open(path + tab + '.csv', 'a')
                        i = 1
                        for field in modelSorted[tab]:
                            deb = int(model[tab][field][0])
                            fin = int(model[tab][field][1])
                            if len(line) >= fin:
                                val = line[deb:fin]
                            else:
                                val = 'NULL'
                            if i < len(modelSorted[tab]):
                                val += ','
                            else:
                                val += '\n'
                            writer.write(val)
                            i += 1
                        writer.close()
            if tab == 'NBAT':
                enreg = ['10','21','30','36']
                for line in file.readlines():
                    e = line[30:32]
                    if e in enreg:
                        done += 1
                        writer = open(path + tab + e + '.csv', 'a')
                        i = 1
                        for field in modelSorted[tab + e]:
                            deb = int(model[tab + e][field][0])
                            fin = int(model[tab + e][field][1])
                            if len(line) >= fin:
                                val = line[deb:fin]
                            else:
                                val = 'NULL'
                            if i < len(modelSorted[tab + e]):
                                val += ','
                            else:
                                val += '\n'
                            writer.write(val)
                            i += 1
                        writer.close()
            if tab == 'PDLL':
                enreg = ['10','20','30']
                for line in file.readlines():
                    e = line[30:32]
                    if e in enreg:
                        done += 1
                        writer = open(path + tab + e + '.csv', 'a')
                        i = 1
                        for field in modelSorted[tab + e]:
                            deb = int(model[tab + e][field][0])
                            fin = int(model[tab + e][field][1])
                            if len(line) >= fin:
                                val = line[deb:fin]
                            else:
                                val = 'NULL'
                            if i < len(modelSorted[tab + e]):
                                val += ','
                            else:
                                val += '\n'
                            writer.write(val)
                            i += 1
                        writer.close()
            if tab == 'PROP':
                for line in file.readlines():
                    if len(line) >= 55:
                        done += 1
                        writer = open(path + tab + '.csv', 'a')
                        i = 1
                        for field in modelSorted[tab]:
                            deb = int(model[tab][field][0])
                            fin = int(model[tab][field][1])
                            if len(line) >= fin:
                                val = line[deb:fin]
                            else:
                                val = 'NULL'
                            if i < len(modelSorted[tab]):
                                val += ','
                            else:
                                val += '\n'
                            writer.write(val)
                            i += 1
                        writer.close()

print('Terminé  à ' + time.strftime('%H:%M:%S'))
print("Temps d'execution : " + str(round(time.time() - start_time, 2)))
print(str(done) + ' lignes traitées')
