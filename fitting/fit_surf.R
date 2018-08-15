library(ggplot2)
library(dplyr)
library(readr)
library(fitdistrplus)
library(actuar)

#setwd("/home/delbarvi/Geomatique/simulation/prepared/34/mtp/data/20m")
setwd("/home/vins/Geomatique/stage/simulation/prepared/34/mtp/data/20m")

df <-  read_csv("distrib_surf.csv")

#les codes iris sont des facteurs
df$ID_IRIS <- factor(df$ID_IRIS)

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


# dataframe avec les poids de chaque hauteur, normalisés par rapport à l'existant, pour chaque IRIS
dSurfNormExist  <- df  %>% group_by(ID_IRIS) %>%  count(round(SURF))  %>% mutate(SurfNorm = n / sum(n) )
names(dSurfNormExist) <-  c("ID_IRIS", "SURFACE", "effectif", "Surface_normalisee_a_lIRIS" )

# ecriture du fichier de poids
write_csv(dSurfNormExist,path = "surf_weights_nofit.csv")


#########################################################
# fit des distributions
#########################################################

dd <- df %>% filter(ID_IRIS==IRISvarious)

fitter <-  function (dd)
{
    candidats <-  c("gamma", "norm", "lnorm", "pois", "exp","cauchy", "gamma",  "geom", "beta" , "logis")
    methods <-  c("mle", "mme", "mge")

    minAIC <-  Inf
    minKS <-  Inf
    minAD <-  Inf
    minCVM <-  Inf
    bestCandidateAIC <-  NULL
    bestCandidateKS <-  NULL
    bestCandidateCVM <-  NULL
    bestCandidateAD <-  NULL

    for (candid in candidats) {
      #cat("test avec distrib =", candid, "\n")
      for (met in methods) {
       # cat("methode : " , met, "\n")
        tryCatch({
          fit <-  fitdist(dd$SURF, distr = candid, method=met, discrete = F)
          gof <-  gofstat(fit)

          if (gof$aic < minAIC){
                minAIC <-  gof$aic
                bestCandidateAIC <-  fit
          }
          if (gof$ks < minKS){
            minKS <-  gof$ks
            bestCandidateKS <-  fit
          }
          if (gof$cvm < minCVM){
            minCVM <-  gof$cvm
            bestCandidateCVM <-  fit
          }
          if (gof$ad < minAD){
            minAD <-  gof$ad
            bestCandidateAD <-  fit
          }

          }, error = function(e) {
          cat("ERROR :", conditionMessage(e), "\n")
        })

      }
    }

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


fittedDistSurfGenerator <-  function(surfmax, distribModels, surfaceBinwidth)
{
  distribGamma <-  NULL
  distribNorm <-  NULL
  distribLognorm <-  NULL
  distribPoiss <-  NULL
  distribCauchy <-  NULL
  distribGeom <-  NULL
  distribExp <-  NULL
  distribLogis <-  NULL
  distribBeta <-  NULL

  surfaceBins <-  seq(from=10, to=round(surfmax), by=surfaceBinwidth)

  #les candidats arrivent dans l'ordre :
  #list(bestCandidateAD, bestCandidateCVM, bestCandidateKS, bestCandidateAIC)


  dResult <-  data.frame(
    surface= surfaceBins,
    dBestAD = numeric(length(surfaceBins)),
    dBestCVM= numeric(length(surfaceBins)),
    dBestKS= numeric(length(surfaceBins)),
    dBestAIC = numeric(length(surfaceBins))
   )


  distrib <-  NULL

  for (i in 1: length(distribModels))
  {
    b <- distribModels[[i]]

    if (b$distname == "gamma") {
    cat(" distribution  gamma\n")
    shape <-  b$estimate
    distribGamma <-  dgamma(surfaceBins , shape)
    }

    if (b$distname == "norm") {
      cat(" distribution  de loi normale\n")
      mu <-  b$estimate[1]
      sigma <- b$estimate[2]
      distrib <-  dnorm(surfaceBins, mu, sigma)
    }
    if (b$distname == "lnorm") {
      cat(" distribution  lognormale\n")
      mulog <-  b$estimate[1]
      sigmalog <- b$estimate[2]
      distrib <-  dlnorm(surfaceBins, mulog, sigmalog)
    }
    if (b$distname == "pois") {
      cat(" distribution  de Poisson\n")
      mulog <-  b$estimate[1]
      sigmalog <- b$estimate[2]
      distrib <-  dlnorm(surfaceBins, mulog, sigmalog)
    }
    if (b$distname == "exp") {
      cat(" distribution  exponentielle\n")
      rate <-  b$estimate
      distrib <-  dexp(surfaceBins, rate)
    }
    if (b$distname == "cauchy") {
      cat(" distribution  de Cauchy\n")
      location <-  b$estimate[1]
      scale <-  b$estimate[2]
      distrib <-  dcauchy(surfaceBins, location, scale)
    }
    if (b$distname == "geom") {
      cat(" distribution  geométrique\n")
      prob <- b$estimate[1]
      distrib <-  dgeom(surfaceBins, prob)
    }
    if (b$distname == "beta") {
      cat(" distribution  beta\n")
      shape1 <- b$estimate[1]
      shape2 <- b$estimate[2]
      distrib <-  dbeta(surfaceBins, shape1, shape2)
    }
    if (b$distname == "logis") {
      cat(" distribution  logistique\n")
      loc <-  b$estimate[1]
      distrib <-  dlogis(surfaceBins, location)
    }


    dResult[,i+1] <-  distrib

  }

  return(dResult)
}


#dataframe vide pour stocker les resultats
distribsResults <-  data.frame(
  ID_IRIS = factor(),
  surface  = integer(),
  poidsFitAD=numeric(),
  poidsFitCVM = numeric(),
  poidsFitKS = numeric(),
  poidsFitAIC = numeric()
  )
bckupNames <-  names(distribsResults)

cptr <- 0
for (c in unique(df$ID_IRIS))
{

  distribObservee <-  df %>% filter(ID_IRIS == c)
  surfmax <-  round(max(distribObservee$SURF))

  tryCatch({
  models <-  fitter(df)
  },error=function(e){cat("ERROR :",conditionMessage(e), "\n")})

  surfbinwidth <-  10
  fittedDistros <-  fittedDistSurfGenerator(surfmax , distribModels = models, surfaceBinwidth = surfbinwidth)


  #
  # if (!is.null(distModelAIC)) {
  #   distSimuleeAIC <-  fittedDistGenerator(netagesmax, distModelAIC)
  # }
  # if (!is.null(distModelchi2pval)) {
  #   distSimuleechi2pval <-fittedDistGenerator(netagesmax, distModelchi2pval)
  # }
  #

  fittedDistros$ID_IRIS <- c

  cptr  <-  cptr + 1
  cat(cptr, "/", length(unique(df$ID_IRIS)),"IRIS:", c ,"\n")
  distribsResults <-  rbind (distribsResults, fittedDistros)

}


getwd()
write.csv(distribsResults, "surf_weights.csv")
dd <-  read.csv("surf_weights.csv")


## on vérfie si ça somme à 1

xx <- dd %>% group_by(ID_IRIS) %>% summarise(totProbAIC = sum(dBestAIC), totProbAD = sum(dBestAD), totProbCVM= sum(dBestCVM), totProbKS=sum(dBestKS))


names(distribsResults) <-  bckupNames


###### pour un IRIS particulier

riri <-  df %>% filter(ID_IRIS == 16)
mods  <- fitter(dd = riri)
#dessin comparant les distribs fittées et la distrib observée
cdfcomp(mods)


meilleureDistAIC
meilleureDistchipval
