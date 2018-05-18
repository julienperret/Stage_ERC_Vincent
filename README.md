./prepare.py  
Ce script doit être lancé en ligne de commande avec au moins 2 arguments :  
    1 : n° de département dans lequel la zone d'étude est située  
    2 : répertoire des données locales (situé au même niveau que la donnée régionale)  
    3 : chaîne de paramètres séparés d'un espace, dans n'importe quel ordre (optionnel)  

Exemple :  
    ./prepare.py 34 ~/workspace/local_data/ "gridSize=50 useTxrp=True levelHeight=3"

Dépendances pour python3 :  
    PyQt5.QtCore.QVariant, qgis, gdal, numpy, pandas + xlrd (pour manipuler les .xls)  

./simulation.py  
Deux paramètre au minimum :  
    1 : le dossier contenant la donnée  
    2 : le taux annuel d'évolution de la population (en %)  
    3 : chaîne de paramètres séparés d'un espace, dans n'importe quel ordre (optionnel)  

Exemple :  
    ./simulation.py ~/workspace/mtp/simulation_50m/ 0.5 "mode=souple saturateFirst=True pluPriority=False"  

Dépendances pour python3 :  
    gdal, numpy, pandas  
