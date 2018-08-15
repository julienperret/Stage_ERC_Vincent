library(ggplot2)
library(dplyr)
library(readr)
library(fitdistrplus)
library(actuar)


setwd("/home/delbarvi/Geomatique/simulation/prepared/34/mtp/data/20m")
#setwd("/home/vins/Geomatique/stage/simulation/prepared/34/mtp/data/20m")


dfniv <- read_csv("distrib_floors.csv")

#les codes iris sont des facteurs
dfniv$ID_IRIS <- factor(dfniv$ID_IRIS)


head(dfniv)


#plot global de la distribution du nombre  d'étages
pniv <-  ggplot(dfniv, aes(FLOOR))+
  geom_histogram( fill="darkolivegreen2", colour="darkgrey", binwidth = 1 )+
  labs(x="nombre d'étages", y="effectif")+
  ggtitle("Distribution du nombre d'étages")
pniv


#données correspondantes  au plot de la distribution
distribFLOOR <-  dfniv %>% count(FLOOR)


#group by IRIS + nombre de lignes
dfnivByIRIS <- dfniv %>% group_by(ID_IRIS) %>% summarize(count=n()) %>% arrange(desc(count))

# réordonne les niveaux de facteurs
dfnivByIRIS$ID_IRIS <- factor(dfnivByIRIS$ID_IRIS, levels = dfnivByIRIS$ID_IRIS[order(-dfnivByIRIS$count)])



#allure de la distribution globale

p<- ggplot(dfnivByIRIS, aes( ID_IRIS,count))+
  geom_bar(fill="darkolivegreen2", colour="darkgrey", stat = "identity")+
  ggtitle("nombre de données (=lignes du fichier=nombre de batiments?) par IRIS , ordonnées par nombre décroissant")+
  labs(x="Code IRIS", y="nombre de lignes")+
  theme(axis.text.x=element_text(angle = -90, hjust = 0))

p

#30+gros

ppp<- ggplot(head(dfnivByIRIS,30), aes( ID_IRIS,count))+
  geom_bar(fill="darkolivegreen2", colour="darkgrey", stat = "identity")+
  ggtitle("nombre de données (=lignes du fichier=nombre de batiments?) des 30 plus gros IRIS")+
  labs(x="Code IRIS", y="nombre de lignes")+
  theme(axis.text.x=element_text(angle = -90, hjust = 0))

ppp


#30+ petits

pp<- ggplot(tail(dfnivByIRIS,30), aes( ID_IRIS,count))+
  geom_bar(fill="darkolivegreen2", colour="darkgrey", stat = "identity")+
  ggtitle("nombre de données (=lignes du fichier=nombre de batiments?) des 30 plus petits IRIS")+
  labs(x="Code IRIS", y="nombre de lignes")+
  theme(axis.text.x=element_text(angle = -90, hjust = 0))

pp

ppp<- ggplot(head(dfnivByIRIS,30), aes( ID_IRIS,count))+
  geom_bar(fill="darkolivegreen2", colour="darkgrey", stat = "identity")+
  ggtitle("nombre de données (=lignes du fichier=nombre de batiments?) des 30 plus gros IRIS")+
  labs(x="Code IRIS", y="nombre de lignes")+
  theme(axis.text.x=element_text(angle = -90, hjust = 0))

ppp


# détail plus gros IRIS
IRISmaousse <-  dfnivByIRIS$ID_IRIS[1]
dbig <-  dfniv %>% filter(ID_IRIS== IRISmaousse)

pmaousse <-  ggplot(dbig, aes(FLOOR))+
  geom_histogram( fill="darkolivegreen2", colour="darkgrey", binwidth = 1)+
  labs(x="nombre d'étages ", y="effectif")+
  scale_x_continuous(breaks = seq(1,max(dbig$FLOOR), by = 1))+
  ggtitle(paste("Distribution du nombre d'étages moyen de l'IRIS", IRISmaousse, "(le plus représenté dans le fichier)"))
pmaousse


# Variété de hauteurs distinctes par IRIS
dfnivDistinctByIRIS <- dfniv %>% group_by(ID_IRIS) %>% summarize(count= n(),distcount=n_distinct(FLOOR)) %>% arrange(desc(distcount))

# réordonne les niveaux de facteurs   par nombre de hauteurs distinctes
dfnivDistinctByIRIS$ID_IRIS <- factor(dfnivDistinctByIRIS$ID_IRIS, levels = dfnivDistinctByIRIS$ID_IRIS[order(-dfnivDistinctByIRIS$distcount)])


library(scales)
ddmike <-  dfniv %>% group_by(ID_IRIS) %>% summarize(count= n(),distcount=n_distinct(FLOOR))


ddmike$indicMike <-  rescale(ddmike$count, to =c(0.0 , 1.0)) / rescale(ddmike$distcount, to =c(0.0 , 1.0))

ddmike$ID_IRIS <- factor(ddmike$ID_IRIS, levels = ddmike$ID_IRIS[order(-ddmike$count)])

ddmike <-  ddmike %>% arrange(desc(count))


pindicMike<- ggplot(ddmike, aes( ID_IRIS,indicMike))+
  geom_bar(aes(fill=distcount) , colour="darkgrey", stat = "identity")+
  ggtitle("ratio nombre d'étages distincts / nombre de bâtiments, par IRIS , ordonnées par ratio décroissant")+
  labs(x="Code IRIS illisible, sauf si on étend l'image à 1800px de large", y="nombre d'étages distincts / nombre de batiments")+
  theme(axis.text.x=element_text(angle = -90, hjust = 0))
pindicMike


pdistinct<- ggplot(dfnivDistinctByIRIS, aes( ID_IRIS,distcount))+
  geom_bar(fill="darkolivegreen2", colour="darkgrey", stat = "identity")+
  ggtitle("nombre de hauteurs d'étages distinctes par IRIS , ordonnées par nombre décroissant")+
  labs(x="Code IRIS illisible, sauf si on étend l'image à 1800px de large", y="nombre d'étages distincts")+
  theme(axis.text.x=element_text(angle = -90, hjust = 0))
pdistinct



# c'est ANTIGONE
IRISvarious <- dfnivDistinctByIRIS$ID_IRIS[2]

dvarious <- dfniv %>% filter(ID_IRIS==IRISvarious)

pvarious <-  ggplot(dvarious, aes(FLOOR))+
  geom_histogram( fill="darkolivegreen2", colour="darkgrey", binwidth = 1)+
  labs(x="nombre d'étages ", y="effectif")+
  scale_x_continuous(breaks = seq(1,max(dvarious$FLOOR), by = 1))+
  ggtitle(paste("Distribution du nombre d'étages de l'IRIS", IRISvarious, "(contient le plus de hauteurs distinctes)"))
pvarious


#compte les hauteurs (nb niv) distinctes, et le poids ormalisé associé
# ATTENTION , ces poids ne sont calculés que pour  des hauteurs déjà présentes dans l'IRIS
# Si une hauteur est absente, elle ne sera pas comptabilisée lors du count()  et il n'y aura pas de poids correspondant

# exemple individuel avec l'IRIS le plus varié
dvarious <- dfniv %>% filter(ID_IRIS==IRISvarious) %>% count(FLOOR) %>% mutate(poidsNorm = n / sum(n) )

# dataframe avec les poids de chaque hauteur, normalisés par rapport à l'existant, pour chaque IRIS
dPoidsNormExist  <- dfniv  %>% group_by(ID_IRIS) %>%  count(FLOOR)  %>% mutate(poidsNorm = n / sum(n) )
names(dPoidsNormExist) <-  c("ID_IRIS", "FLOOR", "effectif", "poidsNormalise_a_l_IRIS" )

# ecriture du fichier de poids
write_csv(dPoidsNormExist,path = "floor_weights_norm.csv")


#########################################################
# fit des distributions

#########################################################


dd <- dfniv %>% filter(ID_IRIS==IRISvarious)

qplot(dd$FLOOR)


# fonction à part pour la distrib logarithmique

logfitter <-  function(dd)
{
  AICmin <-  Inf
  pvalmin <- Inf
  bestfit <-  NULL
  pbestfit <- NULL

  for (p in seq(from = 0.01, to = 0.99 , by = 0.01))
  {
    tryCatch(
    {
      #cat("p=", p, "-----------\n")
      lolog <- fitdist(
        data = dd$FLOOR,
        discrete = T ,
        start = list(prob =p ),
        distr = "logarithmic",
        control = list(trace = 0, REPORT = 1)
      )

      xx <- gofstat(lolog)

      if (xx$aic < AICmin & xx$chisqpvalue< pvalmin)
      {
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


fitter <- function(dd, criterion )
{

  # distribution qui marchent sans paramètres supplementaires :#  "binom", "nbinom", "geom", "hyper" or "pois"

  poiss <- fitdist(dd$FLOOR, discrete = T, "pois")
  negbin <- fitdist(dd$FLOOR,
    discrete = T,
    "nbinom",
    control = list(trace = 0, REPORT = 1)
  )

  geo <- fitdist(dd$FLOOR, discrete = T, "geom")


  # celles qui marchent avec des params
  ztpoiss <- fitdist(
    data = dd$FLOOR,
    discrete = T,
    start = list(lambda = 1),
    distr = "ztpois",
    control = list(trace = 0, REPORT = 1)
  )


  ztgeom <- fitdist(
    data = dd$FLOOR,
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



fittedDistGenerator <-  function(nEtagesMax, meilleureDist)
{
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




#dataframe vide pour stocker les resultats
distribsResults <-  data.frame(
  ID_IRIS = factor(),
  FLOOR  = integer(),
  n = integer(),
  poidsFitAIC = numeric(),
  poidsFitCHI2 = numeric()
)
bckupNames <-  names(distribsResults)

i <- 0
for (c in unique(dfniv$ID_IRIS)) {
  # cat("###########IRIS ", c , "###################\n")
  distribObservee <-  dfniv %>% filter(ID_IRIS == c)
  netagesmax <-  max(distribObservee$FLOOR)
  distModelAIC <-  fitter(distribObservee, "AIC")
  distModelchi2pval <-  fitter(distribObservee, "chi2pval")
  if (!is.null(distModelAIC)) {
    distSimuleeAIC <-  fittedDistGenerator(netagesmax, distModelAIC)
  }
  if (!is.null(distModelchi2pval)) {
    distSimuleechi2pval <-fittedDistGenerator(netagesmax, distModelchi2pval)
  }

  i <-  i + 1
  cat(i, "/", length(unique(dfniv$ID_IRIS)), "\n")
  if (!is.null(distModelAIC) & !is.null(distModelchi2pval)) {
    effectifComplets <- c()
    # boucle très crade
    for (etage in 1:netagesmax) {
      effectifComplets <-
        append(effectifComplets, sum(distribObservee$FLOOR == etage))
    }
    currentIrisResult <- as.data.frame(
      cbind(rep(c, netagesmax),
            seq(from = 1, to = netagesmax, by = 1),
            effectifComplets))
    currentIrisResult <-cbind(currentIrisResult, distSimuleeAIC, distSimuleechi2pval)

    names(distribsResults) <-  bckupNames

        names(currentIrisResult) <-  bckupNames
    # on empile dans les resultats
    distribsResults <-  rbind (distribsResults, currentIrisResult)



  }

  ## sans candidats, opn remplace par la distrib observée :-()
  if (is.null(distModelchi2pval) & is.null(distModelAIC)) {
    cat("=#=#=#=#=# pas de fitting pour IRIS ", c, "=#=#=#=#=#\n")
    effectifComplets <- c()
    # boucle très crade
    for (etage in 1:netagesmax) {
      effectifComplets <-
        append(effectifComplets, sum(distribObservee$FLOOR == etage))
    }

    currentIrisResult <-as.data.frame(cbind(rep(c, netagesmax),
                              seq(from = 1, to = netagesmax, by = 1),
                              effectifComplets))

    currentIrisResult$poidsFitAIC <- currentIrisResult$effectifComplets / sum(currentIrisResult$effectifComplets)
    currentIrisResult$poidsFitCHI2 <- currentIrisResult$effectifComplets / sum(currentIrisResult$effectifComplets)

    names(currentIrisResult) <-  bckupNames
    names(distribsResults) <-  bckupNames

    # on empile dans les resultats
    distribsResults <-  rbind (distribsResults, currentIrisResult)

  }

}

names(distribsResults) <-  bckupNames


#sauvegarde en fichier
setwd()
write.csv(distribsResults, "distributionsEtagesFitted.csv")



# on vérifie que la distribution somme à 1 ou presque  :

ddd <-  read.csv("distributionsEtagesFitted.csv")
#somme des poids par IRIS
xx <- ddd %>% group_by(ID_IRIS) %>% summarise(totProbAIC = sum(poidsFitAIC), totProbCHI2 = sum(poidsFitCHI2))
## => le poifsFitAIC semble plus adapté puisque la la somme tend vers 1 (faudrait vérifier avec un statisticien )



#########----------------------------------------------------------------
#Pour un fit plus précis des distributions d'un IRIS, il faut regarder si les distributions fittées automatiquement s'approchent suffisament bien de la distribution observée , et le cas échéant , regarder pour quels valeurs d'étages la distribution fittée est insuffisante
 ################################"


#Exemple pourun IRIS dont on connait le code



dd <-  dfniv %>% filter(ID_IRIS == 340220101)


meilleureDistAIC <- fitter(dd,"AIC")
meilleureDistchipval <- fitter(dd,"chi2pval")


meilleureDistAIC
meilleureDistchipval


#dessin comparant les distribs fittées et la distrib observée
cdfcomp(list(meilleureDistAIC, meilleureDistchipval))





#### IRIS recalcitrant : impossible de fitter automatiquement
unique(dfniv$ID_IRIS)
ddd <- dfniv %>% filter(ID_IRIS==340220101)
qplot(ddd$FLOOR)
fitter(ddd, "chi2pval")
warnings()






#Distributions candidates  qui ne marchent pas toutes seules ------------------------------------------------------------------------------------
bin <-  fitdist(dd$FLOOR, discrete = T ,
                method = "mle",
                start=list( size=100, prob= 0.75),
                distr = dztbinom )

hyp <-  fitdist(dd$FLOOR, discrete = T ,
                start=list(p=0.75),
                "hyper" ,
                control=list(trace=1, REPORT=1))


hyp <-  fitdist(dd$FLOOR, discrete = T ,
                start=list(p=0.75),
                "hyper" ,
                control=list(trace=1, REPORT=1))


optimMethods <-  c("Nelder-Mead", "BFGS", "CG", "L-BFGS-B", "SANN","Brent")
for (m in optimMethods) {

  cat("METHODE", m ,"==========\n")
  tryCatch({

    ztbinom <- fitdist(data = dd$FLOOR, discrete = T ,
                       optim.method= m,
                       start=list(size=800,prob= 0.5 ),
                       distr = "ztbinom"
    )
  },error=function(e){cat("ERROR :",conditionMessage(e), "\n")})

}

for (m in optimMethods) {

  cat("METHODE", m ,"==========\n")
  tryCatch({
    ztnbinom <- fitdist(data = dd$FLOOR, discrete = T ,
                        start=list(size= 800, prob= 0.5 ),
                        distr = "ztnbinom")

  },error=function(e){cat("ERROR :",conditionMessage(e), "\n")})

}


for (m in optimMethods) {

  cat("METHODE", m ,"==========\n")
  tryCatch({
    zmpois <- fitdist(data = dd$FLOOR, discrete = T ,
                      start=list(lambda = 1 , p0=0.2),
                      distr = "zmpois")


  },error=function(e){cat("ERROR :",conditionMessage(e), "\n")})

}


for (m in optimMethods) {

  cat("METHODE", m ,"==========\n")
  tryCatch({
    zmpois <- fitdist(data = dd$FLOOR, discrete = T ,
                      start=list(size=200, prob = 0.5 , p0=0),
                      distr = "zmbinom")


  },error=function(e){cat("ERROR :",conditionMessage(e), "\n")})

}
