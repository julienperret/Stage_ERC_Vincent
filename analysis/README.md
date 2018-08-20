
# Traitements et visus des données de simulations


Dans ce répertoire se trouves les scripts R utilisés pour traiter les données issues de simulations du modèles. 
Tant que les données ne sont pas trop grosses , je les mets aussi en brut.

Ça devrait marcher directement , je recommande chaudement l'utilisation de Rstudio , et d'exécuter ligne à ligne le code des scripts.



## Données et Traitements


### Sampling

Les données issues d'un sampling sont constituées d'un grand nombre de répertoire, dont le nom est constitué des paramètres utilisés pour la simulation dont il contient les résultats, selon un pattern du genre  : 
`sim_${taux}_${scenario}_${pluPriority}_${buildNonRes}_${densifyGround}_${maxBuiltRatio}_${densifyOld}_${maximumDensity}_${winSize}_${minContig}_${maxContig}_${seed}_${sirene}_${transport}_${routes}_${ecologie}_${ocsol}")
 ` 

 A l'intérieur de ces répertoires, on trouve un fichier `mesures.csv`, écrit par simulate.py.


Le fichier  `Parse_and_Aggregate_SimuResults.R` se charge de:

	1. parcourir les répertoires récursivement 
	2. parser le nom du répertoire pour extraire les valeurs des paramètres
	3. lire le fichier mesures.csv pour extraire les valeurs des sorties
	4. rassembler le tout dans une ligne formée par les valeurs des paramètres et des sorties
	5. écrire le fichier contenant toutes ces lignes


Exemple de fichier qui rassemble ces résultats : `directSamplingfulldataframe.csv` 



#### En cas de changement du format des résultats

Il faut adapter le code pour ajouter ou retirer les paramètres et/ou sorties.
C'est très rapide, y a qu'à demander, hésite pas !


### Profiles

les résultats d'un profil de calibration sont des fichiers nommés `populationXXX.csv`
Il faut toujours considérer, pour une même série de résultats, le fichiers le plus récent, avec XXX le plus élevé : les profils de calibrations sont obtenus à partir d'une méthode "open-ended" , sans critère d'arrêt , donc plus elle a tourné longtemps , mieux c'est.

La lecture du fichier est directe et ne demande pas de traitements particuliers.

### Morris 

RAS : le fichier est tout petit, les valeurs sont directement interprétables, sans traitements ni visus.




## Visus

### Sampling


Le fichier `directSampling.R` contient plusieurs instructions pour afficher les résultats du sampling de différentes manières.

A la fin il y a une ACP qui pourra être  assez intéressante (cf images)

### Profiles

la visualisation du profil de calibration est directe.



