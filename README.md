**N.B.** Après modif de Julien, il faut conserver - réécrire les headers dans les CSV !
******** Tous les répertoires passés en arguments doivent désormais contenir le '/' final  

**./prepare.py**  
Ce script doit être lancé en ligne de commande avec au moins 2 arguments :  
    1 : répertoire des données globales  
    2 : n° de département dans lequel la zone d'étude est située  
    3 : répertoire des données locales (situé au même niveau que la donnée régionale)  
    4 : répertoire des résultats (créé si besoin)  
    5 : chaîne de paramètres séparés d'un espace, dans n'importe quel ordre (optionnel)  

Mots magiques :  
force = suppression du répertoire de sortie si il existe  
wisdom = écriture des .tif directement dans le répertoire de sortie sans conserver les données intermédiaires  

Exemple :  
python3 prepare.py ./global_data/ 34 ./mtp/ ./results/ "gridSize=50 useTxrp=True levelHeight=3 force"  

Dépendances pour python3 :  
    PyQt5.QtCore.QVariant, qgis, gdal, numpy  

**./simulate.py**  
Deux paramètres au minimum :  
    1 : répertoire contenant la donnée  
    2 : répertoire des résultats (créé si besoin)  
    3 : taille des cellules de la grille  
    4 : le taux annuel d'évolution de la population (en %)  
    5 : chaîne de paramètres séparés d'un espace, dans n'importe quel ordre (optionnel)  

Exemple :  
    ./simulate.py ./workspace/mtp/simulation_50m/ ./results/ 50 0.5 "mode=souple saturateFirst=True pluPriority=False"  

Dépendances pour python3 :  
    gdal, numpy  

Commande CARE qui semble marcher  

care -o ./prepare.tgz.bin  -p ./mtp -p ./global_data ./prepare.py ./global_data/ 34  ./mtp/ ./results/ "gridSize=50 useTxrp=True levelHeight=3 force"  

care -o /my/care/output/dir/simulation.tgz.bin -p /my/global/data/ -p /my/local/data/ -p /my/prepared/data/ ./simulation.py /my/prepared/data/ /my/output/dir/ 50 0.5 "mode=souple saturateFirst=True pluPriority=False"  

**./insee_to_csv.py**  
Convertir les données XLS de l'INSEE en CSV en supprimant les champs inutiles, à lancer une seule fois pour toute la région  
Dépendances pour python3 :  
    pandas + xlrd (pour manipuler les .xls)  

Usage :  
./insee_to_csv.py ../global_data/insee/  

**./tif_to_gif.py**  
Génère un GIF à partir des tifs de population générés pour chaque année de la simulation.  

Usage :  
    ./tif_to_gif.py ./results/souple_tx0.5/snapshots/ ./output/ 'delay=10 maxValue=500' (facultatif)  
