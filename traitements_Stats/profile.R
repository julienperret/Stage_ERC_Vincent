library(ggplot2)

setwd("~/encadrement/repoJulienERC/erc/traitements_Stats/")

df2 <-  read.csv("ProfilMBRsurtauxTendanciel.csv")


df <-  read.csv("population862.csv")


names(df)

df$pluPriority <-  df$pluPriority > 0.5
df$buildNonRes <-  df$buildNonRes > 0.5
df$densifyGround <-  df$densifyGround > 0.5
df$densifyOld <-  df$densifyOld > 0.5
df$maximumDensity <-  df$maximumDensity > 0.5


df2$pluPriority <-  df2$pluPriority > 0.5
df2$buildNonRes <-  df2$buildNonRes > 0.5
df2$densifyGround <-  df2$densifyGround > 0.5
df2$densifyOld <-  df2$densifyOld > 0.5
df2$maximumDensity <-  df2$maximumDensity > 0.5




library(dplyr)
df <-  df %>%  filter(impact < max(impact))


names(df)


plot(df)

pp <-  ggplot(df, aes(maxBuiltRatio, impact))+
 # geom_point(aes(color=buildNonRes, shape=densifyOld))+
  geom_point(data=df2,aes(color=buildNonRes, shape=densifyOld), size= 2 ) 

pp


df3 <- read.csv("ProfilWinSizesurTauxTendanciel.csv")


pp <-  ggplot(df3, aes(round(winSize), impact))+
  geom_point(aes(color=buildNonRes, shape=densifyOld))+
  geom_point(data=df2,aes(color=buildNonRes, shape=densifyOld), size= 4 ) 
  geom_line(color="lightgray")+
  stat_smooth()
pp

