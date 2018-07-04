library(ggplot2)
library(dplyr)
library(readr)


setwd("/home/paulchapron/encadrement/Stage_ERC_Vincent/traitements_Stats/")

dfniv <- read_csv("nb_niv.csv")

#les codes iris sont des facteurs
dfniv$CODE_IRIS <- factor(dfniv$CODE_IRIS)


head(dfniv)


#plot global de la distribution du nombre  d'étages
pniv <-  ggplot(dfniv, aes(NB_NIV))+
  geom_histogram( fill="darkolivegreen2", colour="darkgrey", binwidth = 1 )+
  labs(x="nombre d'étages", y="effectif")+
  ggtitle("Distribution du nombre d'étages")
pniv


#données correspondantes  au plot de la distribution 
distribNB_NIV <-  dfniv %>% count(NB_NIV)




  
#group by IRIS + nombre de lignes
dfnivByIRIS <- dfniv %>% group_by(CODE_IRIS) %>% summarize(count=n()) %>% arrange(desc(count))

# réordonne les niveaux de facteurs   
dfnivByIRIS$CODE_IRIS <- factor(dfnivByIRIS$CODE_IRIS, levels = dfnivByIRIS$CODE_IRIS[order(-dfnivByIRIS$count)])



#allure de la distribution globale 

p<- ggplot(dfnivByIRIS, aes( CODE_IRIS,count))+
  geom_bar(fill="darkolivegreen2", colour="darkgrey", stat = "identity")+
  ggtitle("nombre de données (=lignes du fichier=nombre de batiments?) par IRIS , ordonnées par nombre décroissant")+ 
  labs(x="Code IRIS", y="nombre de lignes")+
  theme(axis.text.x=element_text(angle = -90, hjust = 0))

p

#30+gros

ppp<- ggplot(head(dfnivByIRIS,30), aes( CODE_IRIS,count))+
  geom_bar(fill="darkolivegreen2", colour="darkgrey", stat = "identity")+
  ggtitle("nombre de données (=lignes du fichier=nombre de batiments?) des 30 plus gros IRIS")+ 
  labs(x="Code IRIS", y="nombre de lignes")+
  theme(axis.text.x=element_text(angle = -90, hjust = 0))

ppp



#30+ petits

pp<- ggplot(tail(dfnivByIRIS,30), aes( CODE_IRIS,count))+
  geom_bar(fill="darkolivegreen2", colour="darkgrey", stat = "identity")+
  ggtitle("nombre de données (=lignes du fichier=nombre de batiments?) des 30 plus petits IRIS")+ 
  labs(x="Code IRIS", y="nombre de lignes")+
  theme(axis.text.x=element_text(angle = -90, hjust = 0))

pp

ppp<- ggplot(head(dfnivByIRIS,30), aes( CODE_IRIS,count))+
  geom_bar(fill="darkolivegreen2", colour="darkgrey", stat = "identity")+
  ggtitle("nombre de données (=lignes du fichier=nombre de batiments?) des 30 plus gros IRIS")+ 
  labs(x="Code IRIS", y="nombre de lignes")+
  theme(axis.text.x=element_text(angle = -90, hjust = 0))

ppp



# détail plus gros IRIS 
IRISmaousse <-  dfnivByIRIS$CODE_IRIS[1]
dbig <-  dfniv %>% filter(CODE_IRIS== IRISmaousse)

pmaousse <-  ggplot(dbig, aes(NB_NIV))+
  geom_histogram( fill="darkolivegreen2", colour="darkgrey", binwidth = 1)+
  labs(x="nombre d'étages ", y="effectif")+
  scale_x_continuous(breaks = seq(1,max(dbig$NB_NIV), by = 1))+
  ggtitle(paste("Distribution du nombre d'étages moyen de l'IRIS", IRISmaousse, "(le plus représenté dans le fichier)"))
pmaousse





# Variété de hauteurs distinctes par IRIS
dfnivDistinctByIRIS <- dfniv %>% group_by(CODE_IRIS) %>% summarize(count= n(),distcount=n_distinct(NB_NIV)) %>% arrange(desc(distcount))

# réordonne les niveaux de facteurs   par nombre de hauteurs distinctes
dfnivDistinctByIRIS$CODE_IRIS <- factor(dfnivDistinctByIRIS$CODE_IRIS, levels = dfnivDistinctByIRIS$CODE_IRIS[order(-dfnivDistinctByIRIS$distcount)])





library(scales)
ddmike <-  dfniv %>% group_by(CODE_IRIS) %>% summarize(count= n(),distcount=n_distinct(NB_NIV))  


ddmike$indicMike <-  rescale(ddmike$count, to =c(0.0 , 1.0)) / rescale(ddmike$distcount, to =c(0.0 , 1.0))

ddmike$CODE_IRIS <- factor(ddmike$CODE_IRIS, levels = ddmike$CODE_IRIS[order(-ddmike$count)])

ddmike <-  ddmike %>% arrange(desc(count))



pindicMike<- ggplot(ddmike, aes( CODE_IRIS,indicMike))+
  geom_bar(aes(fill=distcount) , colour="darkgrey", stat = "identity")+
  ggtitle("ratio nombre d'étages distincts / nombre de bâtiments, par IRIS , ordonnées par ratio décroissant")+ 
  labs(x="Code IRIS illisible, sauf si on étend l'image à 1800px de large", y="nombre d'étages distincts / nombre de batiments")+
  theme(axis.text.x=element_text(angle = -90, hjust = 0))
pindicMike



pdistinct<- ggplot(dfnivDistinctByIRIS, aes( CODE_IRIS,distcount))+
  geom_bar(fill="darkolivegreen2", colour="darkgrey", stat = "identity")+
  ggtitle("nombre de hauteurs d'étages distinctes par IRIS , ordonnées par nombre décroissant")+ 
  labs(x="Code IRIS illisible, sauf si on étend l'image à 1800px de large", y="nombre d'étages distincts")+
  theme(axis.text.x=element_text(angle = -90, hjust = 0))
pdistinct




# c'est ANTIGONE 
IRISvarious <- dfnivDistinctByIRIS$CODE_IRIS[2]

dvarious <- dfniv %>% filter(CODE_IRIS==IRISvarious) 

pvarious <-  ggplot(dvarious, aes(NB_NIV))+
  geom_histogram( fill="darkolivegreen2", colour="darkgrey", binwidth = 1)+
  labs(x="nombre d'étages ", y="effectif")+
  scale_x_continuous(breaks = seq(1,max(dvarious$NB_NIV), by = 1))+
  ggtitle(paste("Distribution du nombre d'étages de l'IRIS", IRISvarious, "(contient le plus de hauteurs distinctes)"))
pvarious








#compte les hauteurs (nb niv) distinctes, et le poids ormalisé associé 
# ATTENTION , ces poids ne sont calculés que pour  des hauteurs déjà présentes dans l'IRIS
# Si une hauteur est absente, elle ne sera pas comptabilisée lors du count()  et il n'y aura pas de poids correspondant

# exemple individuel avec l'IRIS le plus varié
dvarious <- dfniv %>% filter(CODE_IRIS==IRISvarious) %>% count(NB_NIV) %>% mutate(poidsNorm = n / sum(n) )



# dataframe avec les poids de chaque hauteur, normalisés par rapport à l'existant, pour chaque IRIS 
dPoidsNormExist  <- dfniv  %>% group_by(CODE_IRIS) %>%  count(NB_NIV)  %>% mutate(poidsNorm = n / sum(n) )
names(dPoidsNormExist) <-  c("CODE_IRIS", "NB_NIV", "effectif", "poidsNormalise_a_l_IRIS" )

# ecriture du fichier de poids
write_csv(dPoidsNormExist,path = "poidsNormalises_parIRIS.csv")




# fit des distributions 
library(fitdistrplus)


dd <- dfniv %>% filter(CODE_IRIS==IRISmaousse) 

min(dd$NB_NIV)

ddmike %>% filter(indicMike == max(ddmike$indicMike))



library(actuar)

#"binom", "nbinom", "geom", "hyper" or "pois"

#celles qui marchent sans paramètres supplementaires 

poiss <-  fitdist(dd$NB_NIV, discrete = T , "pois" )
negbin <- fitdist(dd$NB_NIV, discrete = T , "nbinom" ,
                  control=list(trace=1, REPORT=1))

geo <-  fitdist(dd$NB_NIV, discrete = T , "geom" )





#celles qui marchent avec des params 
ztpoiss <-  fitdist(data = dd$NB_NIV, discrete = T ,
                    start=list(lambda=1),
                    distr = dztpois,
                    control=list(trace=1, REPORT=1))

ztgeom <-  fitdist(data = dd$NB_NIV, discrete = T ,
                   start=list(prob= 0.5 ),
                   distr = "ztgeom",
                   control=list(trace=1, REPORT=1))



AICmin <-  Inf
bestfit <-  NULL
pbestfit <- NULL
for (p in seq(from=0.01, to = 0.99 , by=0.01 )){
  cat("p=", p,"-----------\n")
  lolog <- fitdist(data = dd$NB_NIV, discrete = T ,
                   start=list(prob= 0.84 ),
                   distr = "logarithmic")
  
  xx <- gofstat(lolog)
  
  if(xx$aic < AICmin){
    cat ("AIC meilleur avec p = " , p ,"\n")
    AICmin <-  xx$aic
    bestfit  <-  lolog
    pbestfit <- p
  }
  
}



optimMethods <-  c("Nelder-Mead", "BFGS", "CG", "L-BFGS-B", "SANN","Brent")
for (m in optimMethods) {

  cat("METHODE", m ,"==========\n")
  tryCatch({
    zmpois <- fitdist(data = dd$NB_NIV, discrete = T ,
                      start=list(lambda = (c(1,2,3) )),
                      distr = "zmpois")
    
    
    },error=function(e){cat("ERROR :",conditionMessage(e), "\n")})
  
}





for (m in optimMethods) {
  
  cat("METHODE", m ,"==========\n")
  tryCatch({
    zmpois <- fitdist(data = dd$NB_NIV, discrete = T ,
                      start=list( size = 800 ,prob = 0.5 , p0=0),
                      distr = "zmbinom")
  },error=function(e){cat("ERROR :",conditionMessage(e), "\n")})
  
}




plot(bestfit)




pzmbinom
pzmlogarithmic





#celles qui marchent pas 
bin <-  fitdist(dd$NB_NIV, discrete = T , 
                method = "mle",
                start=list( size=100, prob= 0.75),
                distr = dztbinom )

hyp <-  fitdist(dd$NB_NIV, discrete = T , 
                start=list(p=0.75),
                "hyper" ,
                control=list(trace=1, REPORT=1))


hyp <-  fitdist(dd$NB_NIV, discrete = T , 
                start=list(p=0.75),
                "hyper" ,
                control=list(trace=1, REPORT=1))


optimMethods <-  c("Nelder-Mead", "BFGS", "CG", "L-BFGS-B", "SANN","Brent")
for (m in optimMethods) {
  
  cat("METHODE", m ,"==========\n")
  tryCatch({
    
    ztbinom <- fitdist(data = dd$NB_NIV, discrete = T ,
                       optim.method= m,
                       start=list(size=800,prob= 0.5 ),
                       distr = "ztbinom"
    )
  },error=function(e){cat("ERROR :",conditionMessage(e), "\n")})
  
}

for (m in optimMethods) {
  
  cat("METHODE", m ,"==========\n")
  tryCatch({
    ztnbinom <- fitdist(data = dd$NB_NIV, discrete = T ,
                        start=list(size= 800, prob= 0.5 ),
                        distr = "ztnbinom")
    
  },error=function(e){cat("ERROR :",conditionMessage(e), "\n")})
  
}


for (m in optimMethods) {
  
  cat("METHODE", m ,"==========\n")
  tryCatch({
    zmpois <- fitdist(data = dd$NB_NIV, discrete = T ,
                      start=list(lambda = 1 , p0=0.2),
                      distr = "zmpois")
    
    
  },error=function(e){cat("ERROR :",conditionMessage(e), "\n")})
  
}


for (m in optimMethods) {
  
  cat("METHODE", m ,"==========\n")
  tryCatch({
    zmpois <- fitdist(data = dd$NB_NIV, discrete = T ,
                      start=list(size=200, prob = 0.5 , p0=0),
                      distr = "zmbinom")
    
    
  },error=function(e){cat("ERROR :",conditionMessage(e), "\n")})
  
}


