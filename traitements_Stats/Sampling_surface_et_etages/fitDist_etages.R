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



#########################################################
# fit des distributions 

#########################################################

library(fitdistrplus)


dd <- dfniv %>% filter(CODE_IRIS==IRISvarious) 


qplot(dd$NB_NIV)




library(actuar)






# fonction à part pour la distrib logarithmique 

logfitter <-  function(dd) {
  AICmin <-  Inf
  pvalmin <- Inf
  bestfit <-  NULL
  pbestfit <- NULL
  
  for (p in seq(from = 0.01, to = 0.99 , by = 0.01)) {
    tryCatch({
      
      #cat("p=", p, "-----------\n")
      lolog <- fitdist(
        data = dd$NB_NIV,
        discrete = T ,
        start = list(prob =p ),
        distr = "logarithmic",
        control = list(trace = 0, REPORT = 1)
      )
      
      xx <- gofstat(lolog)
      
      if (xx$aic < AICmin & xx$chisqpvalue< pvalmin) {
        AICmin <-  xx$aic
        pvalmin <- xx$chisqpvalue
        bestfit  <-  lolog
        pbestfit <- p
      }
    }, error=function(e){cat("ERROR :",conditionMessage(e), "\n")})
    
  }
  #cat ("logarithmic : AIC meilleur avec p = " , pbestfit , "\n")
  
  return(bestfit)
}




fitter <- function(dd, criterion ) {
  #  "binom", "nbinom", "geom", "hyper" or "pois"

  # celles qui marchent sans paramètres supplementaires

  poiss <- fitdist(dd$NB_NIV, discrete = T, "pois")
  negbin <- fitdist(dd$NB_NIV,
    discrete = T,
    "nbinom",
    control = list(trace = 0, REPORT = 1)
  )

  geo <- fitdist(dd$NB_NIV, discrete = T, "geom")


  # celles qui marchent avec des params
  ztpoiss <- fitdist(
    data = dd$NB_NIV,
    discrete = T,
    start = list(lambda = 1),
    distr = "ztpois",
    control = list(trace = 0, REPORT = 1)
  )


  ztgeom <- fitdist(
    data = dd$NB_NIV,
    discrete = T,
    start = list(prob = 0.5),
    distr = "ztgeom",
    control = list(trace = 0, REPORT = 1)
  )




  lolog <- logfitter(dd)
  candidats <- list(poiss, negbin, geo, ztpoiss, ztgeom, lolog)
  gofs <- list()
  minKipval <- Inf
  minAic <- Inf
  bestCandidateKipval <- NULL
  bestCandidateAic <- NULL
  for (c in candidats) {
    #cat("candidat :", c$distname, "\n")
    gof <- NULL
    tryCatch({
      gof <- gofstat(c)
    }, error = function(e) {
      cat("ERROR :", conditionMessage(e), "\n")
    })

    if (!is.null(gof)) {
      if (gof$chisqpvalue < 0.05 & gof$chisqpvalue < minKipval) {
        minKipval <- gof$chisqpvalue
        bestCandidateKipval <- c
       # cat("======> meilleur candidat v/v chi pval" , bestCandidateKipval$distname, "\n")
      }
      if (gof$aic < minAic & gof$chisqpvalue < 0.05) {
        minAic <- gof$aic
        bestCandidateAic <- c
      #  cat("======> meilleur candidat v/v  AIC" , bestCandidateAic$distname, "\n")
      }
      
    }
  }


  if (criterion=="AIC") {
    return(bestCandidateAic)
  }
  if(criterion=="chi2pval"){
    return(bestCandidateKipval)
  }
}



fittedDistGenerator <-  function(nEtagesMax, meilleureDist) {
  distrib <- NULL
  
  if (meilleureDist$distname == "pois") {
    #cat(" distribution de Poisson\n")
    
    lambda <-  meilleureDist$estimate
    distrib <-  dpois(1:max(nEtagesMax), lambda = lambda)
    
  }
  if (meilleureDist$distname == "ztpois") {
    #cat("distribution zero truncated Poisson\n")
    lambda <-  meilleureDist$estimate
    distrib <-  dztpois(1:max(nEtagesMax), lambda = lambda)
    
  }
  if (meilleureDist$distname == "geom") {
    #cat("distribution géométrique \n")
    prob <-  meilleureDist$estimate
    distrib <-  dgeom(1:max(nEtagesMax), prob = prob)
  }
  if (meilleureDist$distname == "ztgeom") {
    #cat("distribution zero truncated geometrique\n")
    prob <- meilleureDist$estimate
    distrib <- dztgeom(1:max(nEtagesMax), prob = prob)
  }
  if (meilleureDist$distname == "nbinom") {
    #cat("distribution negative binomiale\n")
    mu <-  meilleureDist$estimate[2]
    size <-  meilleureDist$estimate[1]
    distrib <- dnbinom(1:max(nEtagesMax), size = size, prob = 0.5)
  }
  if (meilleureDist$distname == "logarithmic") {
    #cat("distribution logarihtmique\n")
    probn <-  meilleureDist$estimate
    distrib <-  dlogarithmic(1:max(nEtagesMax), prob =probn)
  }
  return(distrib)
  
}




distribsResults <-  data.frame(
    CODE_IRIS = factor(),
    NB_NIV  = integer(),
    n = integer(),
    poidsFitAIC = numeric(),
    poidsFitCHI2 = numeric()
)
bckupNames <-  names(distribsResults)

i <- 0
for (c in unique(dfniv$CODE_IRIS)){
 # cat("###########IRIS ", c , "###################\n")
  distribObservee <-  dfniv %>% filter(CODE_IRIS==c) 
  netagesmax <-  max(distribObservee$NB_NIV)
    distModelAIC <-  fitter(distribObservee, "AIC")
    distModelchi2pval <-  fitter(distribObservee, "chi2pval")
  if(!is.null(distModelAIC)){  
  distSimuleeAIC <-  fittedDistGenerator( netagesmax, distModelAIC)
  }
  if(!is.null(distModelchi2pval)){
  distSimuleechi2pval <-  fittedDistGenerator( netagesmax, distModelchi2pval)
  }
  if(is.null(distModelchi2pval) & is.null(distModelAIC)){
    cat("=#=#=#=#=# pas de fitting pour IRIS ", c, "=#=#=#=#=#\n")
  }  
  
    i <-  i +1 
    cat(i,"/",length(unique(dfniv$CODE_IRIS)),"\n")
  if(!is.null(distModelAIC) & !is.null(distModelchi2pval)){

  currentIrisResult <-  table(distribObservee  %>% group_by(CODE_IRIS) %>%  count(NB_NIV))
  currentIrisResult <-  cbind(rep(c,netagesmax), table(distribObservee$NB_NIV))
  currentIrisResult <-  cbind(currentIrisResult, distSimuleeAIC, distSimuleechi2pval)
  names(currentIrisResult) <-  bckupNames
  distribsResults <-  rbind (distribsResults, currentIrisResult)
  
  
  
  
  
  intersect(etages, distribObservee$NB_NIV)
  
  distribObservee  %>% group_by(CODE_IRIS) %>%  count(NB_NIV %in% 1:netagesmax) 
  match(distribObservee$NB_NIV, etages) %>% group_by(etages)
  
   distribObservee$NB_NIV %in% 1:netagesmax
  1:netagesmax %in% distribObservee$NB_NIV
   
   
  intersect(distribObservee$NB_NIV, etages)
  
  
  }
}








# dataframe avec les poids de chaque hauteur, normalisés par rapport à l'existant, pour chaque IRIS 
distribByIris  <- dfniv  %>% group_by(CODE_IRIS) %>%  count(NB_NIV)  %>% mutate(distribAIC = fittedDistGenerator(max(n),meilleureDist = fitter(dfniv %>% filter(CODE_IRIS==c) ,criterion = "AIC")) )

names(dPoidsNormExist) <-  c("CODE_IRIS", "NB_NIV", "effectif", "poidsNormalise_a_l_IRIS" )

# ecriture du fichier de poids
write_csv(dPoidsNormExist,path = "poidsNormalises_parIRIS.csv")







meilleureDistAIC <- fitter(dd,"AIC")
meilleureDistchipval <- fitter(dd,"chi2pval")


meilleureDistAIC
meilleureDistchipval


#dessin comparant la distrib fittée et la distrib observée
cdfcomp(list(meilleureDistAIC, meilleureDistchipval))

meilleureDist$distname
#générer les valeurs à partir de la meileure fonction candidate





#### RIRS recalcitrant : impossible de fitter automatiquement 
unique(dfniv$CODE_IRIS)
ddd <- dfniv %>% filter(CODE_IRIS==343270104) 
qplot(ddd$NB_NIV)
fitter(ddd, "chi2pval")
warnings()











#celles qui marchent pas toutes seules ------------------------------------------------------------------------------------
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





