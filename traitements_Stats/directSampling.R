library(ggplot2)

setwd("~/encadrement/Stage_ERC_Vincent/traitements_Stats/")

files <-  list.files("./results/", pattern = "mesures.csv", recursive = T, include.dirs = T, full.names = T)
length(files)

## préparation du tableau final params + mesures
dd <- data.frame(
  taux= numeric(),
  scenario=character(),
  pluPriority = logical(),
  buildNonRes = logical(),
  densifyGround = logical(),
  maxBuiltRatio = numeric(),
  densifyOld = logical(),
  maximumDensity = logical(),
  winSize =  numeric(),
  minContig = numeric(),
  maxContig = numeric(),
  PopNotPutUp=numeric(),
  UnbuiltArea = numeric(),
  AvgCellPop = numeric(),
  AreaExpansion = numeric(),
  BuiltFloorArea = numeric(),
  CellesOpenTiUrb= numeric(),
  AvgArtifRate = numeric(),
  impact = numeric(),
  GrndDensifiedCells = numeric(),
  FloorDensifiedCells=numeric())

namesbckup <-  names(dd)




for (fifi in files){
  #on lit le fichier mesures.csv
  cat(fifi, "\n")
  dfbrut <-  read.csv(fifi, header = F)
  namesMesures <- dfbrut$V1
  
  # valeurs de mesures.csv
  mes <-  t(dfbrut$V2)
  mes <-  c(mes)
  if( length(mes)==8){
    mes <- c(mes, 0.0,0.0)
  }
  if( length(mes)==9){
    mes <- c(mes, 0.0)
    
    }
  ligneMesure <-  data.frame(t(mes))
  
  
  
  names(ligneMesure) <-  c("Population not put up","Unbuilt area" ,"Average cell populating","Area expansion","Built floor area",
                           "Cells open to urbanisation", "Average artificialisation rate", "Cumulated environnemental impact",
                           "Ground-densified cells count", "Floor-densified cells count" )
  
  
  
  #valeurs des parametres
  paramsfifi <-  strsplit(fifi,"_")
  paramsbruts <-  paramsfifi[[1]][2:11]

  taux <- as.numeric(as.character(paramsbruts[1]))
  scenario <- paramsbruts[2]
  pluPriority <-  as.logical(paramsbruts[3])
  buildNonRes <-  as.logical(paramsbruts[4])
  densifyGround <-  as.logical(paramsbruts[5])
  maxBuiltRatio <-  as.numeric(paramsbruts[6])
  densifyOld <-  as.logical(paramsbruts[7])
  maximumDensity <-  as.logical(paramsbruts[8])
  winSize <-   as.numeric(paramsbruts[9])
  minContig <-  as.numeric(paramsbruts[10])
  maxContig <-  5
  
  
  #une ligne du futur tableau qui reprend parametres et mesure
  # on ajoute ContigMax = 5 à la fin 
  ligneparam <-  data.frame(taux, scenario, pluPriority, buildNonRes, densifyGround, maxBuiltRatio, densifyOld, maximumDensity,winSize, minContig , maxContig)
  lignetotal <-  cbind(ligneparam, ligneMesure)
  cat(length(lignetotal),"colonnes \n")
  
        dd <-  rbind(dd, lignetotal)
  
}


names(dd) <-  namesbckup

dd$scenario

pp <-  ggplot(dd, aes(taux,  maxBuiltRatio,impact,scenario))+
geom_jitter(aes(color=impact, shape=scenario), height = 1.9, size=2)
  pp



  
  pp <-  ggplot(dd, aes(  maxBuiltRatio,impact,scenario))+
    geom_jitter(aes(color=scenario), height = 1.9, size=2)
  pp
  

