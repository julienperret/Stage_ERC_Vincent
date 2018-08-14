
setwd("~/encadrement/repoJulienERC/erc/traitements_Stats/")




## pour aggréger les fichiers de simus individuelles
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
  
  
  
  #valeurs des parametres obtenues en parsant le nom du repertoire qui contient mesures.csv
  paramsfifi <-  strsplit(fifi,"_")
  paramsbruts <-  paramsfifi[[1]][2:12]
  
  taux <- as.numeric(as.character(paramsbruts[1]))
  scenario <- paramsbruts[2]
  pluPriority <-  as.logical(as.numeric(paramsbruts[3]))
  buildNonRes <-  as.logical(as.numeric(paramsbruts[4]))
  densifyGround <-  as.logical(as.numeric(paramsbruts[5]))
  maxBuiltRatio <-  as.numeric(paramsbruts[6])
  densifyOld <-  as.logical(as.numeric(paramsbruts[7]))
  maximumDensity <-  as.logical(as.numeric(paramsbruts[8]))
  winSize <-   as.numeric(paramsbruts[9])
  minContig <-  as.numeric(paramsbruts[10])
  maxContig <-  as.numeric(strsplit(paramsbruts[11], ".csv")[[1]][1])
  
  
  
  #une ligne du futur tableau qui reprend parametres et mesure
  # on ajoute ContigMax = 5 à la fin 
  ligneparam <-  data.frame(taux, scenario, pluPriority, buildNonRes, densifyGround, maxBuiltRatio, densifyOld, maximumDensity,winSize, minContig , maxContig)
  lignetotal <-  cbind(ligneparam, ligneMesure)
  cat(length(lignetotal),"colonnes \n")
  
  dd <-  rbind(dd, lignetotal)
  
}



names(dd) <-  namesbckup

dd



write.csv(dd, "simudataframe.csv")








####---------------------------------------------------------------------------------------
### pour structurer le fichier produit par le code d'aggregation des résultats en Scala
####---------------------------------------------------------------------------------------

library(readr)
library(compiler)
library(ggplot2)
library(dplyr)

setwd("~/encadrement/repoJulienERC/erc/traitements_Stats/Direct_Sampling_Analysis/")
dbrut <-read_csv("resultsAggregateByRRscript.csv")  
dbrut <- as.data.frame(dbrut)
names(dbrut)


OutputNames <-  c("Population.not.put.up","Unbuilt.area", "Average.cell.populating","Area.expansion","Built.floor.area",             "Cells.open.to.urbanisation","Average.artificialisation.rate", "impact","Ground.densified.cells.count","Floor.densified.cells.count")     
  
InputNames <-  c("taux","scenario","pluPriority","buildNonRes"  ,"densifyGround","maxBuiltRatio", "densifyOld","maximumDensity","winSize","minContig","maxContig","seed","sirene","transport","routes","ecologie","ocsol")

#init dataframe 

dd <- data.frame(
  taux= numeric(),
  scenario=numeric(),
  pluPriority = logical(),
  buildNonRes = logical(),
  densifyGround = logical(),
  maxBuiltRatio = numeric(),
  densifyOld = logical(),
  maximumDensity = logical(),
  winSize =  numeric(),
  minContig = numeric(),
  maxContig = numeric(),
  seed = numeric(),
  sirene= numeric(),
  transport = numeric(),
  routes = numeric(),
  ecologie= numeric(),
  ocsol=numeric(),
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

names(dd) <-  c(InputNames, OutputNames)
names(dbrut) <- c("Inputs", OutputNames)




lineFormatter <-  function(lili){
  inputValuesOfLine <- as.numeric(strsplit(lili[1],split= "_")[[1]][2:18])
  outputValuesOfLine <-  as.numeric(lili[2:11])
    return(c(inputValuesOfLine, outputValuesOfLine))
}


fastFormat <-  cmpfun(lineFormatter)


#application ligne à ligne du formattage des lignes du fichier brut
ddd <-  apply(dbrut,MARGIN = 1, FUN = fastFormat)
ddd <- as.data.frame(t(ddd))
names(ddd) <-  c(InputNames, OutputNames)



#on mets les bon types si possibles
ddd[ddd$scenario>=0 & ddd$scenario <1] <-  as.factor("tendanciel")
ddd[ddd$scenario>=1 & ddd$scenario <2] <-  as.factor("stable")
ddd[ddd$scenario>=2 & ddd$scenario <=3] <-  as.factor("reduction")

ddd$buildNonRes <-  as.logical(ddd$buildNonRes)
ddd$densifyOld <-  as.logical(ddd$densifyOld)
ddd$densifyGround <-  as.logical(ddd$densifyGround)
ddd$maximumDensity <-  as.logical(ddd$maximumDensity)
ddd$pluPriority <-  as.logical(ddd$pluPriority)



write.csv(ddd, "simudataframe_13Aout_616klines.csv")


