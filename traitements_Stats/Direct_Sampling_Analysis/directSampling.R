library(ggplot2)
library(dplyr)



setwd("~/encadrement/repoJulienERC/erc/traitements_Stats/Direct_Sampling_Analysis/")
#################################
# A partir du fichier agrégé et structuré 
###################################

#dd <-  read.csv("directSamplingfulldataframe.csv")

dd <-  read.csv("simudataframe_13Aout_616klines.csv")


#distribution des impacts 
pniv <-  ggplot(dd, aes(impact))+
  geom_histogram( fill="darkolivegreen2", colour="darkgrey", binwidth = 100000 )
pniv



# dynamiques cohérentes avec maxBuilt Ratio et densifyGround


#on change le booelan densifyGround en facteurs  SI ET SEULEMENT SI la colonne n'est pas que TRUE ou que FALSE
#attention à l'ordre des levels de facteurs : levels(factor(dd$densifyGround))
dd$densifyGround <- factor(dd$densifyGround, labels=c("Not DensifyGround", "DensifyGround"))


pp <-  ggplot(dd, aes(taux,  impact,scenario,maxBuiltRatio,densifyGround))+
geom_jitter(aes( color=maxBuiltRatio), height = 0.4, size = 0.4 )+
  facet_grid(rows = vars(scenario), cols = vars(densifyGround))+
  ggtitle("Impacts par scénarios et choix de densification", subtitle = "valeurs de taux et de maxBuiltRatio uniformément échantillonnées")
pp




# pour un taux de croissance variant dans une petite fenètre 
ddd <-  dd %>% filter(between(taux, 1.0, 1.5))
  
#histogramme des impacts par taux
pImpByTaux <-  ggplot(dd, aes(impact))+
  geom_histogram(aes(fill=factor(taux)), color="gray", binwidth = 200000)+
  facet_grid(rows = vars(densifyGround))+
  labs(y="effectif")+
  scale_fill_discrete("taux")

pImpByTaux




# pour un taux de croissance variant dans une petite fenètre , 
#n'affiche rien si les taux n'existente pas ! 
ddd <-  dd %>% filter(between(taux, 2.5, 3))

pImpByTaux2 <-  ggplot(ddd, aes(impact))+
  geom_histogram(aes(fill=factor(taux)), color="gray", binwidth = 200000)+
  labs(y="effectif")+
  scale_fill_discrete("taux")

pImpByTaux2



#pour un quartile d'impact 
dddd <-  dd %>%  filter(impact > quantile(dd$impact, probs = 0.75))


ppQ4 <-  ggplot(dddd, aes(taux,  impact,scenario,maxBuiltRatio,densifyGround))+
  geom_jitter(aes( color=maxBuiltRatio), height = 0.4, size = 0.4 )+
  facet_grid(rows = vars(scenario), cols = vars(densifyGround))+
  ggtitle("Quatrième quartile des Impacts, par scénarios et choix de densification", subtitle = "valeurs de taux et de maxBuiltRatio uniformément échantillonnées")
ppQ4





# on ajoute des variables artificielles
dd$below75 <-  dd$maxBuiltRatio < 75


#on change le booelan densifyGround en facteurs
# attention à l'ordre des levels de facteurs : 
dd$below75 <- factor(dd$below75, labels=c("maxBuiltRatio above 75%", "maxBuiltRatio below 75%"))

ppMBR75 <-  ggplot(dd, aes(taux, impact,scenario,below75,densifyGround))+
      geom_jitter(aes( color=scenario  ), height = 0.2, size=0.4)+
      facet_grid(rows = vars((below75)), cols = vars(densifyGround))+
  ggtitle("Régimes d'impact, par choix de densification et maxBuiltRatio ", subtitle = "valeurs de taux et de scénarios uniformément échantillonnées")
ppMBR75
    
    
#autres mesures de sorties : comment se répartit l'impact

# on prend les impacts positifs
impPos <-  dd %>%  filter(impact >0 )


names(dd)
#AvgCellpop par Area Expansion coloré en impact
names(impPos)
impCellPop <-  ggplot(impPos, aes(Average.cell.populating,Area.expansion))+
    geom_point(aes(color= impact), size=0.6)+
  facet_grid(rows=vars(scenario))

impCellPop

#impact par AreaExpansion coloré par AvgCellPop
names(impPos)
impAreaExp <-  ggplot(impPos, aes(impact,Area.expansion))+
  geom_point(aes(color= Average.cell.populating), size=0.6)+
  facet_grid(rows=vars(scenario))

impAreaExp



#ACP sur les résultats

library(ade4)
library(factoextra)


summary(dd)

# on retire les colonnes qui ne sont pas des sorties
ddACP <-  dd[, -c(1:6)]

ddACP <-  na.omit(ddACP)

# ACP de base
mypca <- prcomp(ddACP, scale. = T)
#ACP avec le package ADE4
mypca2 <-  dudi.pca(ddACP, center=F, scannf = F, nf= 5 )

#dessin
# variance expliquée par les composantes
fviz_eig(mypca)
# graphe des variables dans l'espace des deux premières composantes
#la couleur indique comment la colonne  est bien décrite par CP1 et CP2
fviz_pca_var(mypca,
             col.var = "cos2",
             gradient.cols = c("#00AFBB", "#E7B800", "#FC4E07"),
             repel = TRUE    
)


#inidividus projetés dans le plan CP1,CP2
#colorés suivant l'impact
fviz_pca_ind(
  mypca,
  geom="point",
  geom.size= 0.02,
  col.ind = ddACP$impact,
  gradient.cols = c("#00AFBB", "#E7B800", "#FC4E07")
)




##Effet de winSize/minContig/maxContig  sur les impacts ------------------------------------------


names(dd)
summary(dd$winSize)


ws3 <- dd %>%  filter(winSize==3)

minContig_ws3_by_impact <-  ggplot(ws3, aes(minContig, impact))+
  geom_jitter(aes( color=buildNonRes), width=0.02)+
  ggtitle("Impact en fonction de minContig pour winsize = 3,, pour minContig variant de 0 à 0.3 par pas de 0.1", subtitle = "scenario tendanciel, pluPriority, densifyGround, densifyOld  valent TRUE,\n les points sont étirés autour des valeurs  pour favoriser la visibilité")
minContig_ws3_by_impact



ws5 <- dd %>%  filter(winSize==5)

minContig_ws5_by_impact <-  ggplot(ws5, aes(minContig, impact))+
  geom_jitter(aes( color=buildNonRes), width=0.02)+
  ggtitle("Impact en fonction de minContig pour winsize = 5, pour minContig variant de 0 à 0.3 par pas de 0.1", subtitle = "scenario tendanciel, pluPriority, densifyGround, densifyOld  valent TRUE\n les points sont étirés autour des valeurs  pour favoriser la visibilité")
minContig_ws5_by_impact


ws3_impacts_positifs <-  ws3 %>%  filter(impact >0) %>% group_by(minContig, maxContig) %>% mutate(impactMoyen=mean(impact))


heatmap_ws3 <-  ggplot(ws3_impacts_positifs, aes(minContig, maxContig))+
  geom_tile(aes(fill=impactMoyen))+
  ggtitle("Moyenne des impacts  positifs par valeurs de minContig et maxContig, pour winSize=3")
heatmap_ws3




ws5_impacts_positifs <-  ws5 %>%  filter(impact >0) %>% group_by(minContig, maxContig) %>% mutate(impactMoyen=mean(impact))


heatmap_ws5 <-  ggplot(ws5_impacts_positifs, aes(minContig, maxContig))+
  geom_tile(aes(fill=impactMoyen))+
  ggtitle("Moyenne des impacts  positifs par valeurs de minContig et maxContig, pour winSize=5")
heatmap_ws5


rm(ddd, dddd, heatmap_w5, heatmap_ws3, heatmap_ws5)
rm(ws3_impacts_positifs, ws5_impacts_positifs)
rm(ws3, ws5)
rm(minContig_ws3_by_impact,minContig_ws5_by_impact)



##Effets des poids----------------------------------------------------------


dd <-  dd %>% filter(impact >0) %>%  mutate(sirene=factor(sirene), transport = factor(transport), ocsol = factor(ocsol), routes = factor(routes), ecologie = factor(ecologie))


 ImpactdensityPlotbyX <-  function(x, name) {
     pImpByX <-  ggplot(dd, aes(impact))+
     geom_density(aes(fill=x, color= x),  alpha=0.1)+
     labs(y="densité")+
     scale_fill_discrete(guide="none")+
     scale_color_discrete(paste0("Poids ", name))+
     ggtitle(paste0("Distribution des impacts obtenues selon le poids de la couche ",name))

     return(pImpByX)
        
 }
   
print(ImpactdensityPlotbyX(dd$transport, "transport"))
print(ImpactdensityPlotbyX(dd$sirene, "sirene"))
print(ImpactdensityPlotbyX(dd$routes, "routes"))
print(ImpactdensityPlotbyX(dd$ecologie, "ecologie"))
print(ImpactdensityPlotbyX(dd$ocsol, "ocsol"))

 
CellsOpenDensitybyX <-  function(x, name) {
    pImpByX <-  ggplot(dd, aes(Cells.open.to.urbanisation))+
      geom_density(aes(fill=x, color= x),  alpha=0.1)+
      labs(y="densité")+
      scale_fill_discrete(guide="none")+
      scale_color_discrete(paste0("Poids ", name))+
      ggtitle(paste0("Distribution du nombre de cellules ouvertes à l'urbanisation obtenues selon le poids de la couche ",name))
    
    return(pImpByX)
    
  }


print(CellsOpenDensitybyX(dd$sirene, "sirene"))
print(CellsOpenDensitybyX(dd$routes, "routes"))
print(CellsOpenDensitybyX(dd$ecologie, "ecologie"))
print(CellsOpenDensitybyX(dd$transport, "transport"))
print(CellsOpenDensitybyX(dd$ocsol, "ocsol"))






