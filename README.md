Ce script doit être lancé en ligne de commande avec au moins 2 arguments :  
1 : répertoire des données locales (situé au même niveau que la donnée régionale)  
2 : n° de département dans lequel la zone d'étude est située  
3 : mode de seuillage (strict ou souple); souple par défaut  
4 : taille de la grille (entre 10 et 100m); 50m par défaut  

Exemple :  
./prepare.py ~/workspace/mtp 34 souple 50

Dépendances pour python3 :
gdal, numpy, pandas, xlrd (pour manipuler les .xls)
