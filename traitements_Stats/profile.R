library(ggplot2)

setwd("~/encadrement/repoJulienERC/erc/traitements_Stats/")

df <-  read.csv("population7609.csv")

df <-  read.csv("population862.csv")


names(df)


plot(df)

pp <-  ggplot(df, aes(maxBuiltRatio, impact))+
  geom_point()
pp
