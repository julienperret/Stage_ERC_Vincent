# Fitting des distributions d'étages et de surfaces


Pour la zone étudiée , on dispose des données suivantes : par IRIS , et à une certaine date (2012 ? ) on connaît : 

1. les surfaces construites
2. le nombre d'étages des bâtiments

Pour la simulation des constructions futures, il est pertinent de choisir le nombre d'étages et les surfaces construites de telle façon qu'ils soient relativement similaires aux constructions présentes, par IRIS.


Une méthode pour y arriver est de trouver le modèle des distributions observées, en sélectionnant parmi des modèles de distributions candidats, ceux qui "collent" le mieux aux données.

C'est ce que propose la lib `fitdistrplus ` , qui propose de "fitter" (en français on dit "ajuster") une distribution observée, empirique, à des modèles de distribution (e.g. binomiale, lognormale, exponentielle, etc). Ces modèles sont paramétriques (e.g. pourune gaussienne : moyenne et écart type)
La librairie  procède par optimisation des paramètres des modèles de distributions candidats, suivant une fonction qui évalue la qualité du fitting, la plupart du temps la vraisemblance (cf. MLE : Maximum Likelihood Estimation)


La qualité de l' ajustement / le degré de confiance dans le fitting est évaluée par plusieurs indicateurs, ce qui nous permettra de sélectionner automatiquement, pour chacun de ceux-ci  le meilleur candidat. Comme il n'y a pas d'indicateur absolu de la qualité d'un fit, nous pourrons proposer plusieurs distributions candidates, et il faudra trancher.

**N.B.** Avoir le meilleur score dans les indicateurs de fitting ne signifie pas forcément que le modèle de distribution est le plus adapté. Au cas par cas il faudrait observer l'allure des distributions observées et modélisées pour valider qualitativement le modèle (notamment en cas de distributions multi-modales, souvent observées dans les distributions d'étages,  qu'ici l'on modélise par une distribution unimodale ,  et donc forcément imprécise, faute d'avoir trouvé une façon simple et automatique de fitter une telle distribution par un modèle mixte de distribution du genre a * D1 + b* D2)

Pour un IRIS particulier dont le fitting poserait problème, on pourra utiliser les graphiques de comparaisons de distributions observée/simulée : PP plot , QQplot , et comparaisons des distributions cumulées. (cf. l'exemple dans le code R, utilisant la fonction `cdfcomp` )


Les distributions candidates utilisées dans le code de ce répertoire proviennent des packages `fitdistrplus ` et `actuar ` 


## Limites de l'approche bourrine 


Nous avons 160 IRIS dans la zone, on ne peut pas fitter chacune de ces distributions à la main , patiemment , en faisant varier les paramètres de la dizaine de distributions candidates possibles, et en paramétrant finement les algorithmes d'optimisation utilisés: 
E.g. pour des distributions continues, il y a quatre méthodes d'optimisation: 

 * méthode du maximum  de vraisemblance (MLE),
 * méthode des moments (MME),
 * méthode des quantiles (QME),
 * méthode de minimisation d’une statistique d’ajustement (MGE )


(plus de détails dans la doc de `fitdistrplus` , et par exemple [https://r2013-lyon.sciencesconf.org/file/41245] )




Auxquels s'ajoutent certaines valeurs d'initialisation pour le "préchauffage" des algorithmes, et des paramètres additionnels de "forme" des distributions candidates (par exemple la possibilité de définir une échelle logarithmique pour faciliter l'ajustement, donner des poids , etc.)
On ne peut pas choisir aveuglément ces multiples paramètres,  on a donc retenu les distributions avec leur valeurs initiales de leurs paramètres par défaut, le paramétrage par défaut des algorithmes d'optimisation.

En faisant ce choix, on abandonne :
* la qualité d'un ajustement "à la main" , qualitativement optimale 
* la comparaison fine des candidats suivant plusieurs indicateurs de qualité d'ajustement : il est impossible dans le cas général de sélectionner un candidat optimal unique  lorsqu'il y a plusieurs critères d'optimisation : certains sont optimaux  selon un indicateur, d'autres selon d'autres indicateurs.


En revanche, on peut *automatiser le traitement à l'ensemble des IRIS*, et obtenir des modèles de distributions candidats certes moins sophistiqués (paramètres de formes additionnels des candidats non renseignés) et moins soigneusement ajustés (algorithmes d'optimisation non "tunés"), mais calculables en quelques heures.
On sacrifie donc la qualité à la quantité et à la vitesse. Le capitalisme se niche dans les moindres recoins.




## Pourquoi ajuster et pas simplement échantillonner dans la distribution observée ? 


Les distributions observées comportent des "trous": toutes les valeurs possibles ne sont pas présente dans la distribution observée. 
Par exemple pour les étages d'un IRIS, on peut trouver des bâtiments de 1,2,3,4 étages puis de 8,9 ou 10 étages. 


Si on échantillonne les futures bâtiments dans la distribution observée, il sera impossible de tirer un nombre d'étages de 5,6,7 ou 8, car les probabilités associées à ces scores dans la distribution observée sont nulles. 


Trouver un modèle de distribution, c'est s'assurer d'obtenir une distribution définie en tout point (pour toutes les valeurs de nombre d'étages), ou chaque valeur pourra avoir une chance d'être tirée lors de l'échantillonnage.


## Étages : fitting d'une distribution discrète



Fitter une distribution discrète est plus compliquée que fitter une distribution continue. 
Il y a moins de modèles candidats, et le fait qu'on observe beaucoup de distribution bi-modales (un groupe en 1 et 3-4 étages pour le résidentiel individuel, et un groupe de 7+ étages pour les barres et les résidences) complique la tâche 


### Code et fichiers

`fitDist_etages.R` contient du code pour afficher les distributions d'étages du fichier donné en entrée (ici `nb_niv.csv`), produire le fichier des distributions observées (`poidsNormalises_parIRIS.csv`), ajuster les modèles de distributions candidats

*Input* : un fichier CSV qui liste pour chaque IRIS, le nombre d'étages des bâtiments qu'il contient

*Output* : 
* les dessins ggplot 
* le fichier `poidsNormalises_parIRIS.csv` qui contient la distribution observée du nombre d'étages et les probas associées (obsolète puisque qu'on fitte désormais les distributions d'étages observées) 
* le fichier `distributionsEtagesFitted.csv`, qui contient , pour chaque IRIS, les distributions de probabilités des distributions qu'on a fittées de chaque valeurs de nombre d'étages: 

Format du fichier `distributionsEtagesFitted.csv`: 

|        |X |CODE_IRIS| NB_NIV |  n | poidsFitAIC| poidsFitCHI2|
|--------|--|---------|--------|----|------------|-------------|
|1       |1 |340570104|      1 |485 |6.296143e-01| 2.402186e-01|
|2       |2 |340570104|      2 |359 |2.718473e-01| 1.438672e-01|
|3       |3 |340570104|      3 | 25 |7.824999e-02| 8.616220e-02|
|4       |4 |340570104|      4 |  6 |1.689292e-02| 5.160264e-02|
|5       |5 |340570104|      5 |  0 |2.917529e-03| 3.090488e-02|
|6       |6 |340570104|      6 |  1 |4.198986e-04| 1.850896e-02|


* *X* :  numérode la ligne , inutile
* *CODE_IRIS* : le code de l'IRIS (si si) 
* *NB_NIV* : le nombre d'étages
* *n* : l'effectif dans l'IRIS de NB_NIV, le nombre de bâtiments de cette hauteur 
* *poidsFitAIC* : la distribution optimale selon le critère AIC 
* *poidsFitCHI2* : la distribution optimale suivant la statistique du Chi² 




Les modèles de distributions candidats sont : logarithmique, géométrique, Poisson, zero-truncated Poisson , zero-truncated géométrique, négative binomiale


Lors de l'éxécution du code, il y a beaucoup de messages d'erreurs lorsque l'optimisation échoue à produire un candidat non nul, ou quand le paramétrage par défaut ne suffit pas, il faut pas s'en inquiéter , on vérifie à la fin de l'algo qu'il y a bien un modèle pour chaque IRIS.

**N.B.** un IRIS est particulièrement récalcitrant car aucun modèle de distribution ne fitte dessus. Dans ce cas particulier , on met la distribution observée , celles des effectifs à la place. Il est detecté dans le code.





## Surfaces : fitting d'une distribution continue



L'ajustement des modèles de distributions continues est plus aisé (il y aussi plus de candidats possibles ), mais plus long en temps de calcul (approx 2h mono coeur pour les 160 IRIS)
Avec un peu de bidouille fonctionnelle et de parallélisation on peut faire beaucoup mieux, mais je n 'ai pas pris le temps de le faire.


### Code et Fichiers


`fitDistSurface.R` affiche quelques distributions des surfaces et réalise l'ajustement des modèles de distribution selon 3 méthodes d'optimisation (MQE demande des paramètres que je ne peux pas fournir automatiquement pour le moment) :



 * méthode du maximum  de vraisemblance (MLE),
 * méthode des moments (MME),
 * méthode de minimisation d’une statistique d’ajustement (MGE )


et 9 modèles candidats :

 * distribution  gamma
 * distribution normale 
 * distribution lognormale 
 * distribution de Poisson 
 * distribution exponentielle
 * distribution de Cauchy 
 * distribution géométrique
 * distribution béta
 * distribution logistique 



la qualité de l'ajustement (goodness of fit) est obtenu par la fonction `gofstat` et on retient 4 indicateurs de la qualité de cet ajustement , dont on cherche le minimum :


* Aikake Information Criterion (tient compte de la complexité du modèle et favorise les modèles parcimonieux)
* Kolmogorov Smirnov : genre de distance entre distribution (basée sur l'entropie, avec un nom de vodka, donc forcément cool)
* CVM : Cramér-von Mises , aucune idée , mais les auteurs du packages disent que c'est bien 
* AD :  Anderson-Darling , idem , inconnue


Il y a deuxs fonctions et une boucle principale 

la fonction `fitter` retourne les meilleurs candidats, la fonction `fittedDistgenerator` génère une distribution pour les surface de 10 m² à la surface maximale de l'IRIS, par tranches de 20m² . Le maximum et la taille de la tranche pour la distribution générée sont ajustables.



**input** : le fichier des surfaces observées par IRIS 

**output** : le fichier `poidsSurface_fittes_by_IRIS.csv` qui donne les poids par surfaces, tous les 20m²



Exemple de contenu du fichier `poidsSurface_fittes_by_IRIS.csv`


|   	| X |surface|  dBestAD     |dBestCVM     | dBestKS     |  dBestAIC 	 |CODE_IRIS|
|-------|---|-------|--------------|-------------|-------------|-------------|---------|
|1      | 1 |     10| 8.783533e-03 |8.783533e-03 |9.073314e-03 |9.073314e-03 |340570104|
|2      | 2 |     30| 7.230560e-03 |7.230560e-03 |7.424051e-03 |7.424051e-03 |340570104|
|3      | 3 |     50| 5.952160e-03 |5.952160e-03 |6.074576e-03 |6.074576e-03 |340570104|
|4      | 4 |     70| 4.899788e-03 |4.899788e-03 |4.970396e-03 |4.970396e-03 |340570104|
|5      | 5 |     90| 4.033481e-03 |4.033481e-03 |4.066923e-03 |4.066923e-03 |340570104|
|6      | 6 |    110| 3.320341e-03 |3.320341e-03 |3.327676e-03 |3.327676e-03 |340570104|
|7      | 7 |    130| 2.733288e-03 |2.733288e-03 |2.722802e-03 |2.722802e-03 |340570104|
|8      | 8 |    150| 2.250029e-03 |2.250029e-03 |2.227876e-03 |2.227876e-03 |340570104|
|9      | 9 |    170| 1.852212e-03 |1.852212e-03 |1.822913e-03 |1.822913e-03 |340570104|
|10     |10 |    190| 1.524732e-03 |1.524732e-03 |1.491561e-03 |1.491561e-03 |340570104|
|11     |11 |    210| 1.255151e-03 |1.255151e-03 |1.220439e-03 |1.220439e-03 |340570104|
|12     |12 |    230| 1.033234e-03 |1.033234e-03 |9.985988e-04 |9.985988e-04 |340570104|
|13     |13 |    250| 8.505531e-04 |8.505531e-04 |8.170828e-04 |8.170828e-04 |340570104|
|14     |14 |    270| 7.001710e-04 |7.001710e-04 |6.685610e-04 |6.685610e-04 |340570104|
|15     |15 |    290| 5.763772e-04 |5.763772e-04 |5.470362e-04 |5.470362e-04 |340570104|
|16     |16 |    310| 4.744708e-04 |4.744708e-04 |4.476010e-04 |4.476010e-04 |340570104|
|17     |17 |    330| 3.905820e-04 |3.905820e-04 |3.662403e-04 |3.662403e-04 |340570104|
|18     |18 |    350| 3.215251e-04 |3.215251e-04 |2.996685e-04 |2.996685e-04 |340570104|
|19     |19 |    370| 2.646778e-04 |2.646778e-04 |2.451975e-04 |2.451975e-04 |340570104|
|20     |20 |    390| 2.178814e-04 |2.178814e-04 |2.006278e-04 |2.006278e-04 |340570104|
|21     |21 |    410| 1.793589e-04 |1.793589e-04 |1.641595e-04 |1.641595e-04 |340570104|
|22     |22 |    430| 1.476473e-04 |1.476473e-04 |1.343201e-04 |1.343201e-04 |340570104|
|23     |23 |    450| 1.215425e-04 |1.215425e-04 |1.099047e-04 |1.099047e-04 |340570104|
|24     |24 |    470| 1.000532e-04 |1.000532e-04 |8.992722e-05 |8.992722e-05 |340570104|


* CODE_IRIS : code de l'IRIS 
* dBestAIC : poids obtenus avec la meilleure distribution candidate selon le critère AD
* dBestKS : idem avec Kolmogorov Smirnov
* dBestCVM : Cramér-von Mises
* dBestAD : Anderson-Darling 	

# Perspectives

un problème certainement intéressant et pas du tout traité ici, est de considérer *conjointement* les distributions d'étages et de surfaces . 
les petites surfaces ne sont pas hautes , et les grandes surfaces ne sont pas *nécessairement* très hautes.
Il faudrait donc échantillonner surfaces et étages des bâtiments simulés en tenant compte de cette dépendance.

Je n'ai aucune idée de la façon d'attaquer ce problème, mais il fallait le mentionner.






