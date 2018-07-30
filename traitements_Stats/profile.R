library(ggplot2)
library(dplyr)

setwd("~/encadrement/repoJulienERC/erc/traitements_Stats/")

df2 <-  read.csv("ProfilMBRsurtauxTendanciel.csv")

df <-  read.csv("profile_24HEGI.csv")


names(df)


## si les booleens sont encore des doubles, on peut éxécuter les lignes ci dessous pour 
df$pluPriority <-  df$pluPriority > 0.5
df$buildNonRes <-  df$buildNonRes > 0.5
df$densifyGround <-  df$densifyGround > 0.5
df$densifyOld <-  df$densifyOld > 0.5
df$maximumDensity <-  df$maximumDensity > 0.5




pp <-  ggplot(df, aes(maxBuiltRatio, impact))+
  geom_point(aes(color=buildNonRes, shape=densifyOld))+
geom_line(color="lightgray")
  
pp


df3 <- read.csv("ProfilWinSizesurTauxTendanciel.csv")


pp <-  ggplot(df3, aes(round(winSize), impact))+
  geom_point(aes(color=buildNonRes, shape=densifyOld))+
  geom_point(data=df2,aes(color=buildNonRes, shape=densifyOld), size= 4 ) 
  geom_line(color="lightgray")+
  stat_smooth()
pp

