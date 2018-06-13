**__Les chemins peuvent être passés en argument avec ou sans slash final__**  

## ./prepare.py
Ce script doit être lancé en ligne de commande avec au moins 2 arguments :  
    1 : répertoire des données globales  
    2 : n° de département dans lequel la zone d'étude est située  
    3 : répertoire des données locales
    4 : répertoire des résultats (créé si besoin)  
    5 : chaîne de paramètres séparés d'un espace, dans n'importe quel ordre (optionnel)  

*Mots magiques :*  
* force = suppression du répertoire de sortie si il existe  
* speed = utilisation de plusieurs threads (peut coûter cher en RAM !)  
* truth = écriture des .tif directement dans le répertoire de sortie sans conserver les données intermédiaires  
* silent = aucun 'print' durant l'exécution  

En cas de problème avec les "distance_trucmuche.tif", vérifier qu'il y a un header dans les fichiers csv.  

Usage :  
python3 prepare.py ./global_data/ 34 ./mtp/ ./results/ "gridSize=50 speed"  

Dépendances pour python3 :  
    PyQt5, qgis, gdal, numpy  

## ./simulate.py  
Deux paramètres au minimum :  
    1 : répertoire contenant la donnée  
    2 : répertoire des résultats (créé si besoin)  
    3 : le taux annuel d'évolution de la population (en %), -1 pour utiliser le taux moyen 2009 - 2014  
    4 : chaîne de paramètres séparés d'un espace, dans n'importe quel ordre (optionnelle)  

Usage :  
    ./simulate.py ./workspace/mtp/simulation_50m/ ./results/ 0.5 'scenario=tendanciel buildNonRes=True'

Dépendances pour python3 :  
    gdal, numpy  

## Commandes CARE qui semblent marcher :  

care -o ./prepare.tgz.bin  -p ./mtp -p ./global_data ./prepare.py ./global_data/ 34  ./mtp/ ./results/ "gridSize=50 useTxrp=True levelHeight=3 force"  

care -o /my/care/output/dir/simulation.tgz.bin -p /my/global/data/ -p /my/local/data/ -p /my/prepared/data/ ./simulation.py /my/prepared/data/ /my/output/dir/ 50 0.5 "mode=souple saturateFirst=True pluPriority=False"  

ATTENTION : derrière -p : mettre les chemins en absolu

### ./toolbox.py   
Contient les fonctions communes; à déplacer avec tout script sorti du dépôt.  

### ./insee_to_csv.py   
Convertir les données XLS de l'INSEE en CSV en supprimant les champs inutiles, à lancer une seule fois pour toute la région  
Dépendances pour python3 :  
    pandas + xlrd (pour manipuler les .xls)  

Usage :  
./insee_to_csv.py ../global_data/insee/  

### ./tif_to_gif.py  
Génère un GIF à partir des tifs de population générés pour chaque année de la simulation.  
Trois paramètres au minimum:  
    1 : dossier contenant les images pour chaque année  
    2 : dossier de sortie
    3 : type de donnée des images (byte, uint16, uint32, float32)  
    4 : chaîne contenant la durée du GIF et la valeur max à utiliser (delay=n , maxValue=n)  

Usage :  
./tif_to_gif.py ./results/snapshots/surface_sol ./output/ uint16

### ./magic.py  
Convertit les fichiers positionnels MAJIC III en CSV avec création de tables PSQL  
