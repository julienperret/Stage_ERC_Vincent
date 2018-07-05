#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import traceback
import pandas as pd
from pathlib import Path
from shutil import rmtree

inseeDataPath = Path(sys.argv[1])
try:
    if (inseeDataPath/'csv').exists():
        rmtree(str(inseeDataPath/'csv'))
    os.mkdir(str(inseeDataPath/'csv'))

    inseePop09 = pd.read_excel(str(inseeDataPath/'BTX_IC_POP_2009.xls'), skiprows=(0, 1, 2, 3, 4))
    inseePop09['P09_POP'] = inseePop09['P09_POP'].fillna(0).round().astype(int)
    inseePop09.to_csv(str(inseeDataPath/'csv/inseePop09.csv'), index=0, columns=['IRIS', 'P09_POP'])

    inseePop12 = pd.read_excel(str(inseeDataPath/'base-ic-evol-struct-pop-2012.xls'), skiprows=(0, 1, 2, 3, 4))
    inseePop12['P12_POP'] = inseePop12['P12_POP'].fillna(0).round().astype(int)
    inseePop12.to_csv(str(inseeDataPath/'csv/inseePop12.csv'), index=0, columns=['IRIS', 'P12_POP'])

    inseePop14 = pd.read_excel(str(inseeDataPath/'base-ic-evol-struct-pop-2014.xls'), skiprows=(0, 1, 2, 3, 4))
    inseePop14['P14_POP'] = inseePop14['P14_POP'].fillna(0).round().astype(int)
    inseePop14.to_csv(str(inseeDataPath/'csv/inseePop14.csv'), index=0, columns=['IRIS', 'P14_POP'])

    inseeLog14 = pd.read_excel(str(inseeDataPath/'base-ic-logement-2014.xls'), skiprows=(0, 1, 2, 3, 4))
    inseeLog14['P14_TXRP'] = inseeLog14['P14_RP'] / inseeLog14['P14_LOG']
    inseeLog14.to_csv(str(inseeDataPath/'csv/inseeLog14.csv'), index=0, columns=['IRIS', 'P14_TXRP'])

except:
    exc = sys.exc_info()
    traceback.print_exception(*exc, limit=3, file=sys.stdout)
    sys.exit()
