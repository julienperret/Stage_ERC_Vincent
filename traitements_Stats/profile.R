library(ggplot2)

setwd("~/encadrement/Stage_ERC_Vincent/traitements_Stats/")

df <-  read.csv("population7609.csv")


names(df)


plot(df)

pp <-  ggplot(df, aes(maxBuiltRatio, impact))+
  geom_point()
pp
