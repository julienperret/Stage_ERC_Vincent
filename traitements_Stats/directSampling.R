library(ggplot2)





#################################
# A partir du fichier agrégé
###################################

dd <-  read.csv("directSamplingfulldataframe.csv")

summary(dd)

#distribution des impacts 
pniv <-  ggplot(dd, aes(impact))+
  geom_histogram( fill="darkolivegreen2", colour="darkgrey", binwidth = 100000 )
pniv



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

# on prend les impacts positifs
impPos <-  dd %>%  filter(impact >0 )

#AvgCellpop par Area Expansion coloré en impact
names(impPos)
impCellPop <-  ggplot(impPos, aes(AvgCellPop,AreaExpansion))+
    geom_point(aes(color= impact), size=0.6)+
  facet_grid(rows=vars(scenario))

impCellPop

#impact par AreaExpansion coloré par AvgCellPop
names(impPos)
impAreaExp <-  ggplot(impPos, aes(impact,AreaExpansion))+
  geom_point(aes(color= AvgCellPop), size=0.6)+
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

#version plotly avec affichage des valeurs au survol


