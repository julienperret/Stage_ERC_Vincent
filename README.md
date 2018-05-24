./prepare.py  
Ce script doit être lancé en ligne de commande avec au moins 2 arguments :  
    1 : répertoire des données globales  
    2 : n° de département dans lequel la zone d'étude est située  
    3 : répertoire des données locales (situé au même niveau que la donnée régionale)  
    4 : répertoire des résultats (créé si besoin)  
    5 : chaîne de paramètres séparés d'un espace, dans n'importe quel ordre (optionnel)  

Exemple :  
python3 prepare.py ./global_data 34 ./mtp ./results "gridSize=50 useTxrp=True levelHeight=3 force"   

Dépendances pour python3 :  
    PyQt5.QtCore.QVariant, qgis, gdal, numpy, pandas + xlrd (pour manipuler les .xls)  

./simulation.py  
Deux paramètres au minimum :  
    1 : répertoire contenant la donnée  
    2 : répertoire des résultats (créé si besoin)  
    3 : taille des cellules de la grille  
    4 : le taux annuel d'évolution de la population (en %)  
    5 : chaîne de paramètres séparés d'un espace, dans n'importe quel ordre (optionnel)  

Exemple :  
    ./simulation.py ./workspace/mtp/simulation_50m ./results 50 0.5 "mode=souple saturateFirst=True pluPriority=False"  

Dépendances pour python3 :  
    gdal, numpy, pandas  

Commande CARE qui semble marcher  

care -o ./prepare.tgz.bin  -p ./mtp -p ./global_data ./prepare.py ./global_data 34  ./mtp ./results "gridSize=50 useTxrp=True levelHeight=3 force"
