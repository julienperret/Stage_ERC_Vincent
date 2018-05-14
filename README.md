./prepare.py  
Ce script doit être lancé en ligne de commande avec au moins 2 arguments :  
    1 : n° de département dans lequel la zone d'étude est située  
    2 : répertoire des données locales (situé au même niveau que la donnée régionale)  
    3 : taille de la grille (entre 10 et 100m); 50m par défaut  
   
Exemple :  
    ./prepare.py 34 ~/workspace/mtp/ 50  
    
Dépendances pour python3 :  
    PyQt5.QtCore.QVariant, qgis, gdal, numpy, pandas + xlrd (pour manipuler les .xls)  

*  
*  
*  

./simulation.py  
Deux paramètre au minimum :  
    1 : le dossier contenant la donnée  
    2 : le taux annuel d'évolution de la population (en %)  
    3 : le mode de seuillage (souple ou strict)  
    
Exemple :  
    ./simulation.py ~/workspace/mtp/simulation_50m/ 0.5 souple  
    
Dépendances pour python3 :  
    gdal, numpy, pandas  

    
