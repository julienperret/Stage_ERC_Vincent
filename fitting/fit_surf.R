library(ggplot2)
library(dplyr)
library(readr)
library(fitdistrplus)
library(actuar)

args <- commandArgs(trailingOnly=TRUE)
wd <- args[1]
setwd(wd)
setwd("/home/paulchapron/encadrement/repoJulienERC/erc22222/erc/fitting/")
df <-  read_csv("distrib_surf/20m_distrib_surf.csv")

#les codes iris sont des facteurs
df$ID_IRIS <- factor(df$ID_IRIS)
names(df) <-  c("ID_IRIS", "SURF")
head(df)

#plot global de la distribution des surfaces
psurf <-  ggplot(df, aes(SURF))+
  geom_histogram( fill="darkolivegreen2", colour="darkgrey", binwidth = 1 )+
  labs(x="surface", y="effectif")+
  ggtitle("Distribution des surfaces")
psurf


psurf2 <-  ggplot(df, aes(SURF))+
  geom_density( fill="darkolivegreen2", colour="darkgrey")+
  labs(x="surface", y="effectif")+
  ggtitle("Distribution des surfaces")
psurf2

#group by IRIS + nombre de lignes
dfSurfByIRIS <- df %>% group_by(ID_IRIS) %>% summarize(Surf_Tot=sum(SURF)) %>% arrange(desc(Surf_Tot))

# réordonne les niveaux de facteurs
dfSurfByIRIS$ID_IRIS <- factor(dfSurfByIRIS$ID_IRIS, levels = dfSurfByIRIS$ID_IRIS[order(-dfSurfByIRIS$Surf_Tot)])


#allure de la distribution globale

p<- ggplot(dfSurfByIRIS, aes( ID_IRIS,Surf_Tot  ))+
  geom_bar(fill="darkolivegreen2", colour="darkgrey", stat = "identity")+
  ggtitle(" Surface totale par IRIS , ordonnées par nombre décroissant")+
  labs(x="Code IRIS", y="Surface cumulée")+
  theme(axis.text.x=element_text(angle = -90, hjust = 0))

p

#30+gros

ppp<- ggplot(head(dfSurfByIRIS,30), aes( ID_IRIS,Surf_Tot))+
  geom_bar(fill="darkolivegreen2", colour="darkgrey", stat = "identity")+
  ggtitle("Surface des  30 plus gros IRIS")+
  labs(x="Code IRIS", y="Surface cumulée dans l'IRIS")+
  theme(axis.text.x=element_text(angle = -90, hjust = 0))

ppp


#30+ petits

pp<- ggplot(tail(dfSurfByIRIS,30), aes( ID_IRIS,Surf_Tot))+
  geom_bar(fill="darkolivegreen2", colour="darkgrey", stat = "identity")+
  ggtitle("Surface des 30 plus petits IRIS")+
  labs(x="Code IRIS", y="Surface cumulée dans l'IRIS")+
  theme(axis.text.x=element_text(angle = -90, hjust = 0))

pp


# détail plus gros IRIS
IRISmaousse <-  dfSurfByIRIS$ID_IRIS[1]
dbig <-  df %>% filter(ID_IRIS== IRISmaousse)

pmaousse <-  ggplot(dbig, aes(SURF))+
  geom_histogram( fill="darkolivegreen2", colour="darkgrey", binwidth = 1)+
  labs(x="Surface ", y="effectif")+
  scale_x_continuous(breaks = seq(0,max(dbig$SURF), by = 1000))+
  ggtitle(paste("Distribution de la surface de l'IRIS", IRISmaousse, "(le plus représenté dans le fichier)"))
pmaousse


# Variété de hauteurs distinctes par IRIS
dfSurfDistinct <- df %>% group_by(ID_IRIS) %>% summarize(Surf_Tot= sum(SURF),distcount=n_distinct(SURF)) %>% arrange(desc(distcount))

# réordonne les niveaux de facteurs   par nombre de hauteurs distinctes
dfSurfDistinct$ID_IRIS <- factor(dfSurfDistinct$ID_IRIS, levels = dfSurfDistinct$ID_IRIS[order(-dfSurfDistinct$distcount)])


IRISvarious <- dfSurfDistinct$ID_IRIS[1]

dvarious <- df %>% filter(ID_IRIS==IRISvarious)

pvarious <-  ggplot(dvarious, aes(SURF))+
  geom_histogram( fill="darkolivegreen2", colour="darkgrey", binwidth = 1)+
  labs(x="Surfaces", y="effectif")+
  scale_x_continuous(breaks = seq(0,max(dvarious$SURF), by = 100))+
  ggtitle(paste("Distribution des surfaces de l'IRIS", IRISvarious, "(contient le plus de surfaces distinctes)"))
pvarious


#compte les surfaces distinctes, et le poids normalisé associé
# ATTENTION , ces poids ne sont calculés que pour  des hauteurs déjà présentes dans l'IRIS
# Si une hauteur est absente, elle ne sera pas comptabilisée lors du count()  et il n'y aura pas de poids correspondant


# dataframe avec les poids de chaque surface observée, normalisés par rapport à l'existant, pour chaque IRIS
dSurfNormExist  <- df  %>% group_by(ID_IRIS) %>%  count(round(SURF))  %>% mutate(SurfNorm = n / sum(n) )
names(dSurfNormExist) <-  c("ID_IRIS", "SURFACE", "effectif", "Surface_normalisee_a_lIRIS" )

# ecriture du fichier de poids
write_csv(dSurfNormExist,path = "poidsDistObservee.csv")


#########################################################
# fit des distributions
#########################################################

dvarious <- df %>% filter(ID_IRIS==IRISvarious)

fitter <-  function (dd)
{
    candidats <-  c("gamma", "norm", "lnorm", "pois", "exp","cauchy", "geom", "beta" , "logis")
    methods <-  c("mle", "mme", "mge")

    minAIC <-  Inf
    minKS <-  Inf
    minAD <-  Inf
    minCVM <-  Inf
    bestCandidateAIC <-  NULL
    bestCandidateKS <-  NULL
    bestCandidateCVM <-  NULL
    bestCandidateAD <-  NULL

    for (candid in rev(candidats)) {
      cat("test avec distrib =", candid, "\n")
      for (met in methods) {
        cat("methode : " , met, "\n")
        tryCatch({
          fit <-  fitdist(dd$SURF, distr = candid, method=met, discrete = F)
          gof <-  gofstat(fit)

          if (gof$aic < minAIC & gof$aic > -Inf  ){
            cat("candidat : ",fit$distname,"AIC:", gof$aic, "min courrant :", minAIC, "\n")
                minAIC <-  gof$aic
                bestCandidateAIC <-  fit
          }
          if (gof$ks < minKS & gof$ks > -Inf){
            cat("candidat : ",fit$distname,"KS :", gof$ks,"min courrant :", minKS, "\n")
            minKS <-  gof$ks
            bestCandidateKS <-  fit
          }
          if (gof$cvm < minCVM & gof$cvm > -Inf){
            cat("candidat : ",fit$distname,"CVM" , gof$cvm,"min courrant :", minCVM, "\n")
            minCVM <-  gof$cvm
            bestCandidateCVM <-  fit
          }
          if (gof$ad < minAD & gof$ad > -Inf){
            cat("candidat : ",fit$distname,  "AD:" , gof$ad, "min courrant :", minAD,"\n")
            minAD <-  gof$ad
            bestCandidateAD <-  fit
          }

          }, error = function(e) {})

      } # for method
    } #for candidat

    besties <-  list(bestCandidateAD, bestCandidateCVM, bestCandidateKS, bestCandidateAIC)
    if(anyNA(besties))
    {
      cat("#####=====Aucun Candidat====####\n")
    }
    # denscomp(besties)
    # cdfcomp(besties)
    # ppcomp(besties)

    return(besties)

}




distgen <- function(ft, discrete, surfaceBinwidth) {
  nft <- length(ft)
  mydata <- ft[[1]]$data
  myBins <-  seq(from=0, to=round(max(mydata))+ surfaceBinwidth, by=surfaceBinwidth)
  Bmaxs <- c(0,head(myBins, length(myBins)-1), max(myBins))
  

  verif.ftidata <- function(fti) {
    if (any(fti$data != mydata)) 
      stop("All compared fits must have been obtained with the same dataset")
    invisible()
  }
  lapply(ft, verif.ftidata)
  xmin <- min(mydata)
  xmax <- max(mydata)
  xlim <- c(xmin, xmax)

    distname <- ft[[1]]$distname
  n <- length(mydata)
  
  sfin <- seq(xmin, xmax, length.out = 101)
    comput.fti <- function(i) {
    fti <- ft[[i]]
    para <- c(as.list(fti$estimate), as.list(fti$fix.arg))
    distname <- fti$distname
    pdistname <- paste("p", distname, sep = "")
    
    do.call(pdistname, c(list(q = myBins), as.list(para)))
    
    }
    giveMeTheName <- function(i){
      labels <-  c("bestAD", "bestCVM", "bestKS", "bestAIC")
         return(labels[i])
    }
    
  fittedprob <- sapply(1:nft, comput.fti)
  fittedprob <-  as.data.frame(fittedprob)
  fittedprobTosubstract <- rbind(rep(0,nft),head(fittedprob, nrow(fittedprob)-1))
  
  fittedprob <-  fittedprob - fittedprobTosubstract
  names(fittedprob) <- sapply(1:nft, giveMeTheName)
  fittedprob$surface <- myBins
  return(fittedprob)
}


yy <- fitter(xx)
zz <-  distgen(yy, F,10)

dobs  <- xx %>%  count(round(SURF))  %>% mutate(SurfNorm = n / sum(n) )



plot(round(dobs$SURF), dobs$SurfNorm)
points(zz$surface, zz$bestAD, col="green")
points(zz$surface, zz$bestCVM, col="red")
points(zz$surface, zz$bestKS, col="blue")
points(zz$surface, zz$bestAIC, col="purple")

denscomp(yy)
max(yy[[1]]$data)

ppcomp(yy)


fittedDistSurfGenerator <-  function(surfmax, distribModels, surfaceBinwidth)
{
 

  surfaceBins <-  seq(from=0, to=round(surfmax)+ surfaceBinwidth, by=surfaceBinwidth)

  #les candidats arrivent dans l'ordre :
  #list(bestCandidateAD, bestCandidateCVM, bestCandidateKS, bestCandidateAIC)


  dResult <-  data.frame(
    surface= surfaceBins,
    dBestAD = numeric(length(surfaceBins)),
    dBestCVM= numeric(length(surfaceBins)),
    dBestKS= numeric(length(surfaceBins)),
    dBestAIC = numeric(length(surfaceBins))
  )
  #bornes des bandes pour le calcul de probas

  Bmins <- surfaceBins
  Bmaxs <- c(tail(surfaceBins, length(surfaceBins)-1), max(surfaceBins)+surfaceBinwidth)

  distrib <-  NULL
  
  for (i in 1: length(distribModels))
  {
    b <- distribModels[[i]]
    distrib <-  NULL
    
    if (b$distname == "gamma") {
      cat(" distribution  gamma\n")
      shape <-  b$estimate
      distrib <-  pgamma(Bmaxs, shape) - pgamma(Bmins, shape)
    }

    if (b$distname == "norm") {
      cat(" distribution  de loi normale\n")
      mu <-  b$estimate[1]
      mysigma <- b$estimate[2]
      distrib <-  pnorm(Bmaxs, mu, mysigma) - pnorm(Bmins, mu, mysigma)
    }
    if (b$distname == "lnorm") {
      cat(" distribution  lognormale\n")
      mulog <-  b$estimate[1]
      sigmalog <- b$estimate[2]
      distrib <-  plnorm(Bmaxs, mulog, sigmalog) - plnorm(Bmins, mulog, sigmalog)
    }
    if (b$distname == "pois") {
      cat(" distribution  de Poisson\n")
      lambda <-  b$estimate[1]
      distrib <-  ppois(Bmaxs, lambda) - ppois(Bmins, lambda)
    }
    if (b$distname == "exp") {
      cat(" distribution  exponentielle\n")
      rate <-  b$estimate
      distrib <-  pexp(Bmaxs, rate) - pexp(Bmins, rate)
    }
    if (b$distname == "cauchy") {
      cat(" distribution  de Cauchy\n")
      location <-  b$estimate[1]
      scale <-  b$estimate[2]
      distrib <-  pcauchy(Bmaxs, location, scale) - pcauchy(Bmins, location, scale)
    }
    if (b$distname == "geom") {
      cat(" distribution  geométrique\n")
      prob <- b$estimate[1]
      distrib <-  pgeom(Bmaxs, prob) - pgeom(Bmins, prob)
    }
    if (b$distname == "beta") {
      cat(" distribution  beta\n")
      shape1 <- b$estimate[1]
      shape2 <- b$estimate[2]
      distrib <-  pbeta(Bmaxs, shape1, shape2) -pbeta(Bmins, shape1, shape2)
    }
    if (b$distname == "logis") {
      cat(" distribution  logistique\n")
      loc <-  b$estimate[1]
      sca <- b$estimate[2]
      distrib <-  plogis(Bmaxs, loc,sca)-plogis(Bmins, loc,sca)
    }

    dResult[,i+1] <-  distrib

  }
  return(dResult)
}


#dataframe vide pour stocker les resultats
distribsResults <-  data.frame(
  ID_IRIS = factor(),
  surface  = integer(),
  poidsFitAD= numeric(),
  poidsFitCVM = numeric(),
  poidsFitKS = numeric(),
  poidsFitAIC = numeric()
  )
bckupNames <-  names(distribsResults)

cptr <- 0
for (c in unique(df$ID_IRIS)) {

  distribObservee <-  df %>% filter(ID_IRIS == c)
  surfmax <-  round(max(distribObservee$SURF))

  tryCatch({
  models <-  fitter(distribObservee)
  },error=function(e){})

  surfbinwidth <-  10
  fittedDistros <-  fittedDistSurfGenerator(surfmax , distribModels = models, surfaceBinwidth = surfbinwidth)

  fittedDistros$ID_IRIS <- c

  cptr  <-  cptr + 1
  cat(cptr, "/", length(unique(df$ID_IRIS)),"IRIS:", c ,"\n")
  distribsResults <-  rbind (distribsResults, fittedDistros)

}

distribsResults


write.csv(distribsResults, "fittedWeights.csv")



dd <-  read.csv("fitting/surf_weights.csv")

####### Code de tests pour obtenir les probas (poids) qui somment à 1


fit <-  fitter(dd)
smax <-  max(dd$SURF )
binwidth <-  10

surfaceBins <-  seq(from=0, to=round(smax)+binwidth, by=binwidth)
didi <-  fittedDistSurfGenerator(fit,surfmax =smax, surfaceBinwidth = binwidth )




Bmins <- head(surfaceBins, length(surfaceBins)-1 )
Bmaxs <- tail(surfaceBins, length(surfaceBins)-1 )


vraiesProbas <-  pgeom(Bmaxs, fit[[1]]$estimate ) -pgeom(Bmins, fit[[1]]$estimate )



# version élégante que j'arrive pas àà faire tourner
integralDensite  <-  function(low,up){
        integrate(approxfun(dnorm), low, up)
  }
mapply(integralDensite, Bmins, Bmaxs)


## on vérfie si ça somme à 1

xx <- dd %>% group_by(ID_IRIS) %>% summarise(totProbAIC = sum(dBestAIC), totProbAD = sum(dBestAD), totProbCVM= sum(dBestCVM), totProbKS=sum(dBestKS))


names(distribsResults) <-  bckupNames



###### pour un IRIS particulier



riri <-  df %>% filter(ID_IRIS == 14)
mods  <- fitter(dd = riri)
#dessin comparant les distribs fittées et la distrib observée
cdfcomp(mods)
