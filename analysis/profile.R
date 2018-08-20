library(ggplot2)
library(dplyr)

setwd("~/encadrement/repoJulienERC/erc/traitements_Stats/")


# fichier de resultats de profil à considérer
df <-  read.csv("profile_24HEGI.csv")

df

## si les booleens sont encore des doubles, on peut éxécuter les lignes ci dessous pour 
if (is.numeric(df$pluPriority)) df$pluPriority <-  df$pluPriority > 0.5
if (is.numeric(df$buildNonRes))df$buildNonRes <-  df$buildNonRes > 0.5
if (is.numeric(df$densifyGround))df$densifyGround <-  df$densifyGround > 0.5
if (is.numeric(df$densifyOld))df$densifyOld <-  df$densifyOld > 0.5
if (is.numeric(df$maximumDensity))df$maximumDensity <-  df$maximumDensity > 0.5




pp <-  ggplot(df, aes(maxBuiltRatio, impact))+
  geom_point(aes(color=buildNonRes, shape=densifyOld))+
geom_line(color="lightgray")
  
pp



## autre profil sur winsize 

df3 <- read.csv("ProfilWinSizesurTauxTendanciel.csv")


ppp <-  ggplot(df3, aes(round(winSize), impact))+
  geom_point(aes(color=buildNonRes, shape=densifyOld))
ppp

