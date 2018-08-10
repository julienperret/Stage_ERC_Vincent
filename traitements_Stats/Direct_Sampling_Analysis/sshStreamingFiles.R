library(parallel)

# Calculate the number of cores
no_cores <- detectCores() - 4

# Initiate cluster
cl <- makeCluster(no_cores)




setwd("~/encadrement/repoJulien/erc/traitements_Stats/Direct_Sampling_Analysis/")
#setwd("~/.openmole/zangdar/webui/projects/erc/results")


## pour aggréger les fichiers de simus individuelles
files <-  list.files("./resExtrait/", pattern = "mesures.csv", recursive = T, include.dirs = T, full.names = T)
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



extractLine <-  function(fifi){
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
  paramsbruts <-  paramsfifi[[1]][2:18]
  
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
  maxContig <-  as.numeric(paramsbruts[11])
  seed <-  as.numeric(paramsbruts[12])
  sirene <- as.numeric(paramsbruts[13]) 
  transport <- as.numeric(paramsbruts[14])
  routes <- as.numeric(paramsbruts[15])
  ecologie <- as.numeric(paramsbruts[16])
  ocsol <- as.numeric(strsplit(paramsbruts[17], "/")[[1]][1])
  

  ligneparam <-  data.frame(taux, scenario, pluPriority, buildNonRes, densifyGround, maxBuiltRatio, densifyOld, maximumDensity,winSize, minContig , maxContig,seed,sirene, transport, routes, ecologie, ocsol)
  lignetotal <-  cbind(ligneparam, ligneMesure)
  
  return(lignetotal)
 
    
}

lili <-  head(files, 279600)

start_time <- Sys.time()
ww <-  sapply(lili, FUN = extractLine)
write.csv(t(ww), "simudataframe.csv")
end_time <- Sys.time()

cat(end_time -start_time)


stopCluster(cl)
