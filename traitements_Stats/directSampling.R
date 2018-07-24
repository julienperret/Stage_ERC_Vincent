library(ggplot2)




#################################
# A partir du fichier agrégé
###################################

dd <-  read.csv("directSamplingfulldataframe.csv")

#distribution des impacts 
pniv <-  ggplot(dd, aes(impact))+
  geom_histogram( fill="darkolivegreen2", colour="darkgrey", binwidth = 100000 )
pniv


dd$densifyGround

# dynamiques cohérentes avec maxBuilt Ratio et densifyGround


#on change le booelan densifyGround en facteurs
# attention à l'ordre des levels de facteurs : levels(factor(dd$densifyGround))
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



# pour un taux de croissance variant dans une petite fenètre 
ddd <-  dd %>% filter(between(taux, 2.5, 3))

pImpByTaux2 <-  ggplot(ddd, aes(impact))+
  geom_histogram(aes(fill=factor(taux)), color="gray", binwidth = 200000)+
  facet_grid(rows = vars(densifyGround))+
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


names(dd)
ppp <-  ggplot(dd, aes(PopNotPutUp, UnbuiltArea,AvgCellPop,AreaExpansion,,BuiltFloorArea,CellesOpenTiUrb,AvgArtifRate,impact,GrndDensifiedCells))+
  geom_point()
ppp

mes <-  dd[,7:15]

plot(mes)

