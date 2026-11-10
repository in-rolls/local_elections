rm(list=ls())
# set working directory on line 33, 1311, 1411
# Below are the packages used in the code and need to be installed only once.
# install.packages("readxl")
# install.packages("dplyr")
# install.packages("expss")
# install.packages("sjlabelled")
# install.packages("tibble")
# install.packages("psych")
# install.packages("gridExtra")
# install.packages("ggplot2")
# install.packages("haven")
# install.packages("foreign")
# install.packages("clubSandwich")
# install.packages("stargazer")
# install.packages("lmtest")
# install.packages("tidyr")
# install.packages("sandwich")
# install.packages("stringr")
# install.packages("logr)
##############################################################################
# Load required packages
library(dplyr)
library(readxl)
library(sjlabelled) # package to read and write item labels and values
library(tibble)
library(psych)
library(gridExtra)
library(haven)
library(logr)
##############################################################################
# Set working directory
setwd("/Users/tg2778/Dropbox/0_Reviews_RnRs/092022_AJPS_PathwayPower/ReplicationFolder")
##############################################################################
##############################################################################
log_open("5_LogFiles/DataPrep.log")
##############################################################################

## Section 1 begins
## This code prepares the acmajor dataset that gives descriptives on state 
## constituency candidate level variables and to analyze career progression
##############################################################################
#load datasets for this section
acmajor<- read_excel("1_RawData/AE_WomenAffidavits.xls")

# Generate key variables 
acmajor$resur[is.na(acmajor$Recontest)==FALSE]<-0
acmajor$resur[acmajor$Recontest==TRUE]<-1
table(acmajor$resur)

acmajor$turncoatnew[is.na(acmajor$Turncoat)==FALSE]<-0
acmajor$turncoatnew[acmajor$Turncoat==TRUE]<-1
table(acmajor$turncoatnew)

acmajor$reincum[is.na(acmajor$Incumbent)==FALSE]<-0
acmajor$reincum[acmajor$Incumbent==TRUE & is.na(acmajor$Recontest)==FALSE]<-1
table(acmajor$reincum)

acmajor$femalecand[acmajor$Sex=="M"]<-0
acmajor$femalecand[acmajor$Sex=="F"]<-1
table(acmajor$femalecand)

acmajor$majcand<-0
acmajor$majcand[acmajor$Party=="AAP"| acmajor$Party=="BJP"| acmajor$Party=="INC"| acmajor$Party=="AAAP"]<-1
table(acmajor$majcand)

acmajor$partytype<-"Small"
acmajor$partytype[acmajor$Party=="AAP"| acmajor$Party=="AAAP"]<-"AAP"
acmajor$partytype[acmajor$Party=="BJP"]<-"BJP"
acmajor$partytype[acmajor$Party=="INC"]<-"INC"
acmajor$partytype[acmajor$Party=="IND"]<-"Independent"
table(acmajor$partytype)

acmajor$criminal<-NA
acmajor$criminal[acmajor$Criminal_cases=="No"]<-0
acmajor$criminal[acmajor$Criminal_cases=="Yes"]<-1

acmajor$Position<-as.numeric(acmajor$Position)
acmajor$scres<-NA
acmajor$scres[acmajor$Constituency_Type=="GEN"]<-0
acmajor$scres[acmajor$Constituency_Type=="SC"]<-1
acmajormajor<-as.data.frame(acmajor)
acmajor$Total_Assets<-as.numeric(acmajor$Total_Assets)
acmajor$lntotalassets<-log(acmajor$Total_Assets)
acmajor$lnage<-log(acmajor$Age2)


##Add caste background
fp <- read_excel("1_RawData/AE_WomenCasteBackground.xlsx", 
                 sheet = "FinalDataSheet")


table(fp$castecategory)
fp$castecategory[fp$castecategory=="classified OBC"]<-"OBC"
fp$castecategory[fp$castecategory=="Christian"|fp$castecategory=="sikh"]<-"Forward"
fp$castecategory[fp$castecategory=="classified SC"]<-"SC"
table(fp$castecategory)

fp$caste_forward<-0
fp$caste_forward[fp$castecategory=="Forward"]<-1
table(fp$caste_forward)

fp$caste_obc<-0
fp$caste_obc[fp$castecategory=="OBC"]<-1
table(fp$caste_obc)

fp$caste_sc<-0
fp$caste_sc[fp$castecategory=="SC"]<-1
table(fp$caste_sc)

fp$caste_muslim<-0
fp$caste_muslim[fp$castecategory=="Muslim"]<-1
table(fp$caste_muslim)

fp<-fp[,c("Year","Constituency_No","pid","Position","castecategory","caste_forward","caste_obc","caste_sc","caste_muslim")]


#merge the state level and candidate caste data
acmajor$newx<-1
fp$newy<- 2
acmajor2 <- merge(acmajor,fp , by.x=c("Year","Constituency_No","pid","Position"), by.y=c("Year","Constituency_No","pid","Position"), all.x = TRUE, all.y=FALSE)
acmajor2$stat.merge.variable <- rowSums(acmajor2[,c("newx", "newy")], na.rm=TRUE)
table(acmajor2$stat.merge.variable)
acmajor2<-subset(acmajor2, stat.merge.variable==3)
acmajor<-acmajor2[,c("resur","majcand","Vote_Share_Percentage","Margin_Percentage","Age2","lnage","lntotalassets","highedu","criminal","Year","Constituency_No","scres","castecategory","caste_forward","caste_obc","caste_sc","caste_muslim")]
#acmajor$progress<-acmajor$resur
colnames(acmajor)<-c("progress","majcand","votes","margin","age","lnage","lntotalassets","highedu","criminal","Year","Constituency_No","scres","castecategory","caste_forward","caste_obc","caste_sc","caste_muslim")
acmajor$identifier<-paste("Constituency_No","Year", sep="_")
save(acmajor, file="2_ProcessedData/acmajor.RData")
##############################################################################
## Section 1 ends
##############################################################################


##############################################################################
## Section 2 begins
## This code prepares the career history dataset
##############################################################################
cand <- read_excel("1_RawData/AE_WomenManualMatch.xls")

# keep candidates that have ever contested
cand<-subset(cand,cand$IsContestedEver=="Yes" )

cand2008<-subset(cand,Match2008=="Yes")
cand2008<-cand2008[,c(1:6,grep("2008",colnames(cand)))]
cand2008$year<-2008
colnames(cand2008)<-gsub("[[:digit:]]","",colnames(cand2008))

cand2013<-subset(cand,Match2013=="Yes")
cand2013<-cand2013[,c(1:6,grep("2013",colnames(cand)))]
cand2013$year<-2013
colnames(cand2013)<-gsub("[[:digit:]]","",colnames(cand2013))


cand2015<-subset(cand,Match2015=="Yes")
cand2015<-cand2015[,c(1:6,grep("2015",colnames(cand)))]
cand2015$year<-2015
colnames(cand2015)<-gsub("[[:digit:]]","",colnames(cand2015))
colnames(cand2015)[colnames(cand2015)=="Postion"]<-"Position"

cand2020<-subset(cand,Match2020=="Yes")
cand2020<-cand2020[,c(1:6,grep("2020",colnames(cand)))]
cand2020$year<-2020
colnames(cand2020)<-gsub("[[:digit:]]","",colnames(cand2020))

candnew<-rbind(cand2008, cand2013, cand2015, cand2020)

library(dplyr)
candnew<-candnew %>%
  group_by(ACNumber, year, Position) %>%
  mutate(mcdelect = order(order(ElectionYear, decreasing=FALSE)))
candnew<-candnew[,c(1:6,9,11,12)]

candnew<-candnew[,c(6:9,1:5)]
candnew1<-subset(candnew, mcdelect==1)
candnew2<-subset(candnew, mcdelect==2)
candnew3<-subset(candnew, mcdelect==3)

colnames(candnew1)<-c("acno","position","year","mcdelect","mcdyear1","mcdcommonname1","wardno1","wardname1","wardposition1")
colnames(candnew2)<-c("acno","position","year","mcdelect","mcdyear2","mcdcommonname2","wardno2","wardname2","wardposition2")
colnames(candnew3)<-c("acno","position","year","mcdelect","mcdyear3","mcdcommonname3","wardno3","wardname3","wardposition3")


ac_mcd <- merge(candnew1,candnew2 , by.x=c("acno","position", "year"), by.y=c("acno","position", "year"), all.x = TRUE, all.y=FALSE)
ac_mcd2 <- merge(ac_mcd,candnew3 , by.x=c("acno","position", "year"), by.y=c("acno","position", "year"), all.x = TRUE, all.y=FALSE)

colnames(ac_mcd2)

dropscol <-c("new1","new2","stat.merge.variable","X","mcdelect.x","mcdelect.y","mcdelect")
acmcd<-ac_mcd2[ , !(names(ac_mcd2) %in% dropscol)]

rm(list=setdiff(ls(), c("acmcd")))
acmcd$identifier<-paste(acmcd$acno, acmcd$year, sep="_")
save.image("2_ProcessedData/mcdcanddata.RData")


##############################################################################
## Section 3 begins
## This code prepares
##############################################################################
# Read state-level candidate file downloaded from TPCD
ac<-read.csv("1_RawData/TCPD_GE_Delhi_2020-2-23.csv")

# Retain only 2008 and main elections (exclude by elections)
ac<-subset(ac, Year>=2008 & Poll_No==0)

# Retain important columns only
ac<-ac[,c("Constituency_No","Constituency_Type","Year","Poll_No","Candidate","pid","Sex","Position","Party","Margin_Percentage","Votes","ENOP","Turncoat","Incumbent","Recontest","Electors","Valid_Votes","Contested","No_Terms")]

# Generate key variables for aggregating
ac$actotcand<-1

# Create party specific variables
ac$femalecand<-0
ac$femalecand[ac$Sex=="F"]<-1

ac$malecand<-0
ac$malecand[ac$Sex=="M"]<-1


ac$femalepos<-NA
ac$femalepos[ac$Sex=="F"]<-ac$Position[ac$Sex=="F"]

ac$femalevote<-NA
ac$femalevote[ac$Sex=="F"]<-ac$Votes[ac$Sex=="F"]

ac$incfemalevote<-NA
ac$incfemalevote[ac$Sex=="F" & ac$Party=="INC"]<-ac$Votes[ac$Sex=="F" & ac$Party=="INC"]

ac$bjpfemalevote<-NA
ac$bjpfemalevote[ac$Sex=="F" & ac$Party=="BJP"]<-ac$Votes[ac$Sex=="F" & ac$Party=="BJP"]

ac$aapfemalevote<-NA
ac$aapfemalevote[ac$Sex=="F" & (ac$Party=="AAP" | ac$Party=="AAAP")]<-ac$Votes[ac$Sex=="F" &  (ac$Party=="AAP" | ac$Party=="AAAP")]

ac$indfemalevote<-NA
ac$indfemalevote[ac$Sex=="F" & (ac$Party=="IND")]<-ac$Votes[ac$Sex=="F" &  (ac$Party=="IND")]

ac$majorfemalevote<-NA
ac$majorfemalevote[ac$Sex=="F" & (ac$Party=="AAP"| ac$Party=="BJP"| ac$Party=="INC"| ac$Party=="AAAP")]<-ac$Votes[ac$Sex=="F" &  (ac$Party=="AAP"| ac$Party=="BJP"| ac$Party=="INC"| ac$Party=="AAAP")]

ac$nonmajorfemalevote<-NA
ac$nonmajorfemalevote[ac$Sex=="F" & (ac$Party!="AAP" & ac$Party!="BJP" & ac$Party!="INC"& ac$Party!="AAAP")]<-ac$Votes[ac$Sex=="F" & (ac$Party!="AAP" & ac$Party!="BJP" & ac$Party!="INC"& ac$Party!="AAAP")]

ac$maleinccand<-0
ac$maleinccand[ac$Sex=="M"& (ac$Party=="INC")]<-1

ac$malebjpcand<-0
ac$malebjpcand[ac$Sex=="M"& (ac$Party=="BJP")]<-1

ac$maleaapcand<-0
ac$maleaapcand[ac$Sex=="M"& (ac$Party=="AAP"|ac$Party=="AAAP")]<-1

ac$femaleinccand<-0
ac$femaleinccand[ac$Sex=="F"& (ac$Party=="INC")]<-1

ac$femalebjpcand<-0
ac$femalebjpcand[ac$Sex=="F"& (ac$Party=="BJP")]<-1

ac$femaleaapcand<-0
ac$femaleaapcand[ac$Sex=="F"& (ac$Party=="AAP"|ac$Party=="AAAP")]<-1

ac$femalemajcand<-0
ac$femalemajcand[ac$Sex=="F"& (ac$Party=="AAP"| ac$Party=="BJP"| ac$Party=="INC"| ac$Party=="AAAP")]<-1

ac$femalenonmajcand<-0
ac$femalenonmajcand[ac$Sex=="F"& (ac$Party!="AAP" & ac$Party!="BJP" & ac$Party!="INC"& ac$Party!="AAAP")]<-1

ac$malemajcand<-0
ac$malemajcand[ac$Sex=="M"& (ac$Party=="AAP"| ac$Party=="BJP"| ac$Party=="INC"| ac$Party=="AAAP")]<-1

ac$malenonmajcand<-0
ac$malenonmajcand[ac$Sex=="M"& (ac$Party!="AAP" & ac$Party!="BJP" & ac$Party!="INC"& ac$Party!="AAAP")]<-1

ac$femaleindcand<-0
ac$femaleindcand[ac$Sex=="F"& (ac$Party=="IND")]<-1

ac$femalenonmajpartycand<-0
ac$femalenonmajpartycand[ac$Sex=="F"& (ac$Party!="AAP" & ac$Party!="BJP" & ac$Party!="INC"& ac$Party!="AAAP"&ac$Party!="IND")]<-1

ac$femaletop3cand<-0
ac$femaletop3cand[ac$Sex=="F"& (ac$Position<=3)]<-1

ac$femaletop5cand<-0
ac$femaletop5cand[ac$Sex=="F"& (ac$Position<=5)]<-1


ac$incvote<-NA
ac$incvote[ac$Party=="INC"]<-ac$Votes[ac$Party=="INC"]

ac$bjpvote<-NA
ac$bjpvote[ac$Party=="BJP"]<-ac$Votes[ac$Party=="BJP"]

ac$aapvote<-NA
ac$aapvote[(ac$Party=="AAP" | ac$Party=="AAAP")]<-ac$Votes[(ac$Party=="AAP" | ac$Party=="AAAP")]


# Create incumbency background variables
ac$maleincumbent<-0
ac$maleincumbent[ac$Incumbent=="TRUE" & ac$Sex=="M"]<-1

ac$femaleincumbent<-0
ac$femaleincumbent[ac$Incumbent=="TRUE" & ac$Sex=="F"]<-1

ac$femalerecontest<-0
ac$femalerecontest[ac$Recontest=="TRUE" & ac$Sex=="F"]<-1

ac$malerecontest<-0
ac$malerecontest[ac$Recontest=="TRUE" & ac$Sex=="M"]<-1


ac$incumbentwins<-0
ac$incumbentwins[ac$Incumbent=="TRUE" & ac$Position==1]<-1

ac$femaleincumbentwins<-0
ac$femaleincumbentwins[ac$Incumbent=="TRUE" & ac$Sex=="F" & ac$Position==1]<-1

ac$maleincumbentwins<-0
ac$maleincumbentwins[ac$Incumbent=="TRUE" & ac$Sex=="M" & ac$Position==1]<-1

ac$recontestwins<-0
ac$recontestwins[ac$Recontest=="TRUE" & ac$Position==1]<-1

ac$femalerecontestwins<-0
ac$femalerecontestwins[ac$Recontest=="TRUE" & ac$Sex=="F" & ac$Position==1]<-1

ac$malerecontestwins<-0
ac$malerecontestwins[ac$Recontest=="TRUE" & ac$Sex=="M" & ac$Position==1]<-1
################################################
ac$femalenewcand<-0
ac$femalenewcand[ac$Contested==1 & ac$Sex=="F"]<-1

ac$femalerecontesting<-0
ac$femalerecontesting[ac$Contested>1 & ac$Sex=="F"]<-1

ac$femalerecontestingBJP<-0
ac$femalerecontestingBJP[ac$Contested>1 & ac$Sex=="F" & ac$Party=="BJP"]<-1
table(ac$femalerecontestingBJP)

ac$femalerecontestingINC<-0
ac$femalerecontestingINC[ac$Contested>1 & ac$Sex=="F" & ac$Party=="INC"]<-1
table(ac$femalerecontestingINC)

ac$femalerecontestingAAP<-0
ac$femalerecontestingAAP[ac$Contested>1 & ac$Sex=="F" & (ac$Party=="AAP"| ac$Party=="AAAP")]<-1
table(ac$femalerecontestingAAP)

ac$femalerecontest_inc<-0
ac$femalerecontest_inc[ac$Contested>1 & ac$Sex=="F" & ac$Incumbent=="TRUE"]<-1
table(ac$femalerecontest_inc)

ac$femalerecontest_noninc<-0
ac$femalerecontest_noninc[ac$Contested>1 & ac$Sex=="F" & ac$Incumbent=="FALSE"]<-1

ac$femalenewmajcand<-0
ac$femalenewmajcand[ac$Contested==1 & ac$Sex=="F" & ac$femalemajcand==1]<-1

ac$femalenew_nonmajcand<-0
ac$femalenew_nonmajcand[ac$Contested==1 & ac$Sex=="F" & ac$femalemajcand==0]<-1

ac$femalerecontesting_maj<-0
ac$femalerecontesting_maj[ac$Contested>1 & ac$Sex=="F" & ac$femalemajcand==1]<-1

ac$femalerecontesting_nonmaj<-0
ac$femalerecontesting_nonmaj[ac$Contested>1 & ac$Sex=="F" & ac$femalemajcand==0]<-1


ac$femalerecontest_incmaj<-0
ac$femalerecontest_incmaj[ac$Contested>1 & ac$Sex=="F" & ac$Incumbent=="TRUE"  & ac$femalemajcand==1]<-1

ac$femalerecontest_incnonmaj<-0
ac$femalerecontest_incnonmaj[ac$Contested>1 & ac$Sex=="F" & ac$Incumbent=="TRUE" & ac$femalemajcand==0]<-1


ac$femalerecontest_nonincmaj<-0
ac$femalerecontest_nonincmaj[ac$Contested>1 & ac$Sex=="F" & ac$Incumbent=="FALSE"  & ac$femalemajcand==1]<-1

ac$femalerecontest_nonincnonmaj<-0
ac$femalerecontest_nonincnonmaj[ac$Contested>1 & ac$Sex=="F" & ac$Incumbent=="FALSE" & ac$femalemajcand==0]<-1

###
ac$malenewcand<-0
ac$malenewcand[ac$Contested==1 & ac$Sex=="M"]<-1

ac$malerecontesting<-0
ac$malerecontesting[ac$Contested>1 & ac$Sex=="M"]<-1

ac$malerecontest_inc<-0
ac$malerecontest_inc[ac$Contested>1 & ac$Sex=="M" & ac$Incumbent=="TRUE"]<-1
table(ac$malerecontest_inc)

ac$malerecontest_noninc<-0
ac$malerecontest_noninc[ac$Contested>1 & ac$Sex=="M" & ac$Incumbent=="FALSE"]<-1

ac$malenewmajcand<-0
ac$malenewmajcand[ac$Contested==1 & ac$Sex=="M" & ac$malemajcand==1]<-1

ac$malenew_nonmajcand<-0
ac$malenew_nonmajcand[ac$Contested==1 & ac$Sex=="M" & ac$malemajcand==0]<-1

ac$malerecontesting_maj<-0
ac$malerecontesting_maj[ac$Contested>1 & ac$Sex=="M" & ac$malemajcand==1]<-1

ac$malerecontesting_nonmaj<-0
ac$malerecontesting_nonmaj[ac$Contested>1 & ac$Sex=="M" & ac$malemajcand==0]<-1

ac$malerecontest_incmaj<-0
ac$malerecontest_incmaj[ac$Contested>1 & ac$Sex=="M" & ac$Incumbent=="TRUE"  & ac$malemajcand==1]<-1

ac$malerecontest_incnonmaj<-0
ac$malerecontest_incnonmaj[ac$Contested>1 & ac$Sex=="M" & ac$Incumbent=="TRUE" & ac$malemajcand==0]<-1

ac$malerecontest_nonincmaj<-0
ac$malerecontest_nonincmaj[ac$Contested>1 & ac$Sex=="M" & ac$Incumbent=="FALSE"  & ac$malemajcand==1]<-1

ac$malerecontest_nonincnonmaj<-0
ac$malerecontest_nonincnonmaj[ac$Contested>1 & ac$Sex=="M" & ac$Incumbent=="FALSE" & ac$malemajcand==0]<-1

################################################
# Load Municipal candidate dataset to merge with state level dataset and add municipal background variables
load("2_ProcessedData/mcdcanddata.RData")

ac$new1<-1
acmcd$new2<- 2
ac2 <- merge(ac,acmcd , by.x=c("Constituency_No","Year", "Position"), by.y=c("acno","year","position"), all.x = TRUE, all.y=FALSE)
ac2$evermcd <- rowSums(ac2[,c("new1", "new2")], na.rm=TRUE)
ac$new1<-NULL
acmcd$new2<- NULL

dropscol <-c("new1","new2","stat.merge.variable","X")
ac<-ac2[ , !(names(ac2) %in% dropscol)]

ac$evermcd[ac$evermcd==1]<-0
ac$evermcd[ac$evermcd==3]<-1

ac$everprior<-0
ac$everprior[ac$evermcd==1 & ac$mcdyear1<ac$Year]<-1

ac$everfuture<-0
ac$everfuture[ac$evermcd==1 & (ac$mcdyear1>ac$Year | ac$mcdyear2>ac$Year | ac$mcdyear3>ac$Year)]<-1

ac$nopriorf<-0
ac$nopriorf[ac$everprior==0 & ac$Sex=="F"]<-1


ac$everpriorf<-0
ac$everpriorf[ac$everprior==1 & ac$Sex=="F"]<-1
ac$everpriorm<-0
ac$everpriorm[ac$everprior==1 & ac$Sex=="M"]<-1


ac$everpriorfmaj<-0
ac$everpriorfmaj[ac$everprior==1 & ac$femalemajcand==1 & ac$Sex=="F"]<-1
ac$everpriormmaj<-0
ac$everpriormmaj[ac$everprior==1 & ac$malemajcand==1 & ac$Sex=="M"]<-1

ac$everpriorfbjp<-0
ac$everpriorfbjp[ac$everprior==1 & ac$femalebjpcand==1 & ac$Sex=="F"]<-1
ac$everpriormbjp<-0
ac$everpriormbjp[ac$everprior==1 & ac$malebjpcand==1 & ac$Sex=="M"]<-1

ac$everpriorfinc<-0
ac$everpriorfinc[ac$everprior==1 & ac$femaleinccand==1 & ac$Sex=="F"]<-1
ac$everpriorminc<-0
ac$everpriorminc[ac$everprior==1 & ac$maleinccand==1 & ac$Sex=="M"]<-1

ac$everpriorfaap<-0
ac$everpriorfaap[ac$everprior==1 & ac$femaleaapcand==1 & ac$Sex=="F"]<-1
ac$everpriormaap<-0
ac$everpriormaap[ac$everprior==1 & ac$maleaapcand==1 & ac$Sex=="M"]<-1

ac$everpriorrecfbjp<-0
ac$everpriorrecfbjp[ac$everprior==1 & ac$femalebjpcand==1 & ac$Sex=="F" & ac$femalerecontestingBJP==1]<-1
ac$everpriorrecfinc<-0
ac$everpriorrecfinc[ac$everprior==1 & ac$femaleinccand==1 & ac$Sex=="F" & ac$femalerecontestingINC==1]<-1
ac$everpriorrecfaap<-0
ac$everpriorrecfaap[ac$everprior==1 & ac$femaleaapcand==1 & ac$Sex=="F"& ac$femalerecontestingAAP==1]<-1

ac$everpriorfnonmaj<-0
ac$everpriorfnonmaj[ac$everprior==1 & ac$femalemajcand==0 & ac$Sex=="F"]<-1

ac$everpriormnonmaj<-0
ac$everpriormnonmaj[ac$everprior==1 & ac$malemajcand==0 & ac$Sex=="M"]<-1


ac$everfuturef<-0
ac$everfuturef[ac$everfuture==1 & ac$Sex=="F"]<-1
ac$everfuturem<-0
ac$everfuturem[ac$everfuture==1 & ac$Sex=="M"]<-1



ac$freqmcd1<-0
ac$freqmcd1[is.na(ac$mcdyear1)=="FALSE" & is.na(ac$mcdyear2)=="TRUE" &is.na(ac$mcdyear3)=="TRUE"]<-1
ac$freqmcd2<-0
ac$freqmcd2[is.na(ac$mcdyear1)=="FALSE" & is.na(ac$mcdyear2)=="FALSE" &is.na(ac$mcdyear3)=="TRUE"]<-1
ac$freqmcd3<-0
ac$freqmcd3[is.na(ac$mcdyear1)=="FALSE" & is.na(ac$mcdyear2)=="FALSE" &is.na(ac$mcdyear3)=="FALSE"]<-1


ac$freqmcd1f<-0
ac$freqmcd1f[ac$freqmcd1==1 & ac$Sex=="F"]<-1
ac$freqmcd1m<-0
ac$freqmcd1m[ac$freqmcd1==1 & ac$Sex=="M"]<-1


ac$freqmcd2f<-0
ac$freqmcd2f[ac$freqmcd2==1 & ac$Sex=="F"]<-1
ac$freqmcd2m<-0
ac$freqmcd2m[ac$freqmcd2==1 & ac$Sex=="M"]<-1


ac$freqmcd3f<-0
ac$freqmcd3f[ac$freqmcd3==1 & ac$Sex=="F"]<-1
ac$freqmcd3m<-0
ac$freqmcd3m[ac$freqmcd3==1 & ac$Sex=="M"]<-1

ac$priorfreqmcd1<-0
ac$priorfreqmcd1[is.na(ac$mcdyear1)=="FALSE" & ac$mcdyear1<ac$Year & is.na(ac$mcdyear2)=="TRUE" &is.na(ac$mcdyear3)=="TRUE"]<-1
ac$priorfreqmcd2<-0
ac$priorfreqmcd2[is.na(ac$mcdyear1)=="FALSE" & ac$mcdyear1<ac$Year & ac$mcdyear2<ac$Year & is.na(ac$mcdyear2)=="FALSE" &is.na(ac$mcdyear3)=="TRUE"]<-1
ac$priorfreqmcd3<-0
ac$priorfreqmcd3[is.na(ac$mcdyear1)=="FALSE" & ac$mcdyear1<ac$Year & ac$mcdyear2<ac$Year & ac$mcdyear3<ac$Year & is.na(ac$mcdyear2)=="FALSE" &is.na(ac$mcdyear3)=="FALSE"]<-1


ac$priorfreqmcd1f<-0
ac$priorfreqmcd1f[ac$priorfreqmcd1==1 & ac$Sex=="F"]<-1
ac$priorfreqmcd2f<-0
ac$priorfreqmcd2f[ac$priorfreqmcd2==1 & ac$Sex=="F"]<-1
ac$priorfreqmcd3f<-0
ac$priorfreqmcd3f[ac$priorfreqmcd3==1 & ac$Sex=="F"]<-1

ac$priorfreqmcd1m<-0
ac$priorfreqmcd1m[ac$priorfreqmcd1==1 & ac$Sex=="M"]<-1
ac$priorfreqmcd2m<-0
ac$priorfreqmcd2m[ac$priorfreqmcd2==1 & ac$Sex=="M"]<-1
ac$priorfreqmcd3m<-0
ac$priorfreqmcd3m[ac$priorfreqmcd3==1 & ac$Sex=="M"]<-1


ac$fprior_rec<-0
ac$fprior_rec[ac$everpriorf==1 & ac$femalerecontesting==1]<-1

ac$mprior_rec<-0
ac$mprior_rec[ac$everpriorm==1 & ac$malerecontesting==1]<-1


ac$fprior_recinc<-0
ac$fprior_recinc[ac$everpriorf==1 & ac$femalerecontest_inc==1]<-1

ac$ftotnewcand<-0
ac$ftotnewcand[ac$everpriorf==0 & ac$femalerecontesting==0 & ac$femalecand==1]<-1

ac$mtotnewcand<-0
ac$mtotnewcand[ac$everpriorm==0 & ac$malerecontesting==0 & ac$malecand==1]<-1

ac$ftotnewcandmaj<-0
ac$ftotnewcandmaj[ac$ftotnewcand==1 & ac$femalemajcand==1]<-1

ac$mtotnewcandmaj<-0
ac$mtotnewcandmaj[ac$mtotnewcand==1 & ac$malemajcand==1]<-1

ac$ftotnewcandnonmaj<-0
ac$ftotnewcandnonmaj[ac$ftotnewcand==1 & ac$femalemajcand==0]<-1

ac$mtotnewcandnonmaj<-0
ac$mtotnewcandnonmaj[ac$mtotnewcand==1 & ac$malemajcand==0]<-1

ac$nopriorcandmaj<-0
ac$nopriorcandmaj[ac$everpriorf==0 & ac$femalemajcand==1]<-1


ac$fprior_rec_maj<-0
ac$fprior_rec_maj[ac$everpriorf==1 & ac$femalerecontesting_maj==1]<-1

ac$mprior_rec_maj<-0
ac$mprior_rec_maj[ac$everpriorm==1 & ac$malerecontesting_maj==1]<-1

ac$fprior_rec_nonmaj<-0
ac$fprior_rec_nonmaj[ac$everpriorf==1 & ac$femalerecontesting_nonmaj==1]<-1

ac$mprior_rec_nonmaj<-0
ac$mprior_rec_nonmaj[ac$everpriorm==1 & ac$malerecontesting_nonmaj==1]<-1

table(ac$everpriorf, ac$femalerecontest_incmaj)
ac$fprior_recinc_maj<-0
ac$fprior_recinc_maj[ac$everpriorf==1 & ac$femalerecontest_incmaj==1]<-1
table(ac$fprior_recinc_maj)

table(ac$everpriorf, ac$femalerecontest_nonincmaj)
ac$fprior_recnoninc_maj<-0
ac$fprior_recnoninc_maj[ac$everpriorf==1 & ac$femalerecontest_nonincmaj==1]<-1
table(ac$fprior_recnoninc_maj)

#############################################
## Add state level candidates background data
rm(list=setdiff(ls(), c("ac")))
fp <- read_excel("1_RawData/AE_WomenCasteBackground.xlsx", 
                 sheet = "FinalDataSheet")
#for candidates whose information was not found, names were used to assign caste
#candidates without last name or with  kumari, bala, devi, wati etc are SC
#candidates with surname but non-SC are OBC

fp$castecategory[fp$castecategory=="classified OBC"]<-"OBC"
fp$castecategory[fp$castecategory=="Christian"|fp$castecategory=="sikh"]<-"Forward"
fp$castecategory[fp$castecategory=="classified SC"]<-"SC"

fp$caste_forward<-0
fp$caste_forward[fp$castecategory=="Forward"]<-1

fp$caste_obc<-0
fp$caste_obc[fp$castecategory=="OBC"]<-1

fp$caste_sc<-0
fp$caste_sc[fp$castecategory=="SC"]<-1

fp$caste_muslim<-0
fp$caste_muslim[fp$castecategory=="Muslim"]<-1


fp$bkr_councilor<-0
fp$bkr_councilor[fp$prior_and_family=="councilor"|fp$prior_and_family=="councilor+student"|fp$prior_and_family=="both"]<-1


fp$caste_mjr_forward<-0
fp$caste_mjr_forward[fp$caste_forward==1 & fp$majorparty=="yes"]<-1

fp$caste_mjr_sc<-0
fp$caste_mjr_sc[fp$caste_sc==1 & fp$majorparty=="yes"]<-1

fp$caste_mjr_obc<-0
fp$caste_mjr_obc[fp$caste_obc==1 & fp$majorparty=="yes"]<-1

fp$caste_mjr_muslim<-0
fp$caste_mjr_muslim[fp$caste_muslim==1 & fp$majorparty=="yes"]<-1

fp$caste_forwardprior<-0
fp$caste_forwardprior[fp$caste_forward==1  & fp$bkr_councilor==1]<-1

fp$caste_scprior<-0
fp$caste_scprior[fp$caste_sc==1  & fp$bkr_councilor==1]<-1

fp$caste_obcprior<-0
fp$caste_obcprior[fp$caste_obc==1  & fp$bkr_councilor==1]<-1

fp$caste_muslimprior<-0
fp$caste_muslimprior[fp$caste_muslim==1 & fp$bkr_councilor==1]<-1


fp$caste_mjr_forwardprior<-0
fp$caste_mjr_forwardprior[fp$caste_forward==1 & fp$majorparty=="yes" & fp$bkr_councilor==1]<-1

fp$caste_mjr_scprior<-0
fp$caste_mjr_scprior[fp$caste_sc==1 & fp$majorparty=="yes" & fp$bkr_councilor==1]<-1

fp$caste_mjr_obcprior<-0
fp$caste_mjr_obcprior[fp$caste_obc==1 & fp$majorparty=="yes" & fp$bkr_councilor==1]<-1

fp$caste_mjr_muslimprior<-0
fp$caste_mjr_muslimprior[fp$caste_muslim==1 & fp$majorparty=="yes" & fp$bkr_councilor==1]<-1


ac$pid<-as.character(ac$pid)

#remove any duplicates
fp<-fp[!duplicated(fp[,c("Constituency_No","Year","Position")]), ] 
fp<-fp[!duplicated(fp[,c("pid")]), ] 

#retain important variables
fp<-fp[,c("pid","caste_forward","caste_obc","caste_sc","caste_muslim","caste_forwardprior","caste_obcprior","caste_scprior","caste_muslimprior","caste_mjr_forwardprior","caste_mjr_scprior","caste_mjr_obcprior","caste_mjr_muslimprior","caste_mjr_forward","caste_mjr_sc","caste_mjr_obc","caste_mjr_muslim","bkr_councilor")]

#merge files
ac$newx<-1
fp$newy<- 2
acnew <- merge(ac,fp , by.x=c("pid"), by.y=c("pid"), all.x = TRUE, all.y=TRUE)
acnew$stat.merge.variable <- rowSums(acnew[,c("newx", "newy")], na.rm=TRUE)
table(acnew$stat.merge.variable)

#save background data file
save(acnew,file="2_ProcessedData/mlabackground.RData")


acnew$caste_forward[is.na(acnew$caste_forward)==TRUE]<-0
acnew$caste_mjr_forward[is.na(acnew$caste_mjr_forward)==TRUE]<-0
acnew$caste_forwardprior[is.na(acnew$caste_forwardprior)==TRUE]<-0
acnew$caste_mjr_forwardprior[is.na(acnew$caste_mjr_forwardprior)==TRUE]<-0

acnew$caste_obc[is.na(acnew$caste_obc)==TRUE]<-0
acnew$caste_mjr_obc[is.na(acnew$caste_mjr_obc)==TRUE]<-0
acnew$caste_obcprior[is.na(acnew$caste_obcprior)==TRUE]<-0
acnew$caste_mjr_obcprior[is.na(acnew$caste_mjr_obcprior)==TRUE]<-0

acnew$caste_sc[is.na(acnew$caste_sc)==TRUE]<-0
acnew$caste_mjr_sc[is.na(acnew$caste_mjr_sc)==TRUE]<-0
acnew$caste_scprior[is.na(acnew$caste_scprior)==TRUE]<-0
acnew$caste_mjr_scprior[is.na(acnew$caste_mjr_scprior)==TRUE]<-0

acnew$caste_muslim[is.na(acnew$caste_muslim)==TRUE]<-0
acnew$caste_mjr_muslim[is.na(acnew$caste_mjr_muslim)==TRUE]<-0
acnew$caste_muslimprior[is.na(acnew$caste_muslimprior)==TRUE]<-0
acnew$caste_mjr_muslimprior[is.na(acnew$caste_mjr_muslimprior)==TRUE]<-0

acnew$caste_forwardnew<-0
acnew$caste_forwardnew[acnew$caste_forward==1  & acnew$femalenewcand==1 & acnew$bkr_councilor==0]<-1

acnew$caste_scnew<-0
acnew$caste_scnew[acnew$caste_sc==1   & acnew$femalenewcand==1 & acnew$bkr_councilor==0]<-1


acnew$caste_obcnew<-0
acnew$caste_obcnew[acnew$caste_obc==1   & acnew$femalenewcand==1 & acnew$bkr_councilor==0]<-1

acnew$caste_muslimnew<-0
acnew$caste_muslimnew[acnew$caste_muslim==1  & acnew$femalenewcand==1 & acnew$bkr_councilor==0]<-1

acnew$caste_mjr_forwardnew<-0
acnew$caste_mjr_forwardnew[acnew$caste_forward==1 & acnew$femalenewcand==1 & acnew$bkr_councilor==0 & acnew$femalemajcand==1]<-1

acnew$caste_mjr_scnew<-0
acnew$caste_mjr_scnew[acnew$caste_sc==1 & acnew$femalenewcand==1 & acnew$bkr_councilor==0 & acnew$femalemajcand==1]<-1

acnew$caste_mjr_obcnew<-0
acnew$caste_mjr_obcnew[acnew$caste_obc==1 & acnew$femalenewcand==1 & acnew$bkr_councilor==0 & acnew$femalemajcand==1]<-1

acnew$caste_mjr_muslimnew<-0
acnew$caste_mjr_muslimnew[acnew$caste_muslim==1 & acnew$femalenewcand==1 & acnew$bkr_councilor==0 & acnew$femalemajcand==1]<-1

acnew$caste_forwardsmallind<-0
acnew$caste_forwardsmallind[acnew$caste_forward==1  & acnew$femalenonmajcand ==1]<-1

acnew$caste_scsmallind<-0
acnew$caste_scsmallind[acnew$caste_sc==1  & acnew$femalenonmajcand ==1]<-1


acnew$caste_obcsmallind<-0
acnew$caste_obcsmallind[acnew$caste_obc==1 & acnew$femalenonmajcand ==1]<-1

acnew$caste_muslimsmallind<-0
acnew$caste_muslimsmallind[acnew$caste_muslim==1 & acnew$femalenonmajcand ==1]<-1



acnew$caste_forwardrecont<-0
acnew$caste_forwardrecont[acnew$caste_forward==1  & acnew$femalerecontesting==1]<-1

acnew$caste_screcont<-0
acnew$caste_screcont[acnew$caste_sc==1  & acnew$femalerecontesting==1]<-1

acnew$caste_obcrecont<-0
acnew$caste_obcrecont[acnew$caste_obc==1  & acnew$femalerecontesting==1]<-1

acnew$caste_muslimrecont<-0
acnew$caste_muslimrecont[acnew$caste_muslim==1 & acnew$femalerecontesting==1]<-1


acnew$caste_mjr_forwardrecont<-0
acnew$caste_mjr_forwardrecont[acnew$caste_forward==1 & acnew$femalerecontesting_maj==1]<-1

acnew$caste_mjr_screcont<-0
acnew$caste_mjr_screcont[acnew$caste_sc==1 & acnew$femalerecontesting_maj==1]<-1

acnew$caste_mjr_obcrecont<-0
acnew$caste_mjr_obcrecont[acnew$caste_obc==1 & acnew$femalerecontesting_maj==1]<-1

acnew$caste_mjr_muslimrecont<-0
acnew$caste_mjr_muslimrecont[acnew$caste_muslim==1 & acnew$femalerecontesting_maj==1]<-1


acnew$caste_forwardboth<-0
acnew$caste_forwardboth[acnew$caste_forward==1  & acnew$femalerecontesting==1 & acnew$bkr_councilor==1]<-1

acnew$caste_scboth<-0
acnew$caste_scboth[acnew$caste_sc==1   & acnew$femalerecontesting==1 & acnew$bkr_councilor==1]<-1


acnew$caste_obcboth<-0
acnew$caste_obcboth[acnew$caste_obc==1   & acnew$femalerecontesting==1 & acnew$bkr_councilor==1]<-1

acnew$caste_muslimboth<-0
acnew$caste_muslimboth[acnew$caste_muslim==1  & acnew$femalerecontesting==1 & acnew$bkr_councilor==1]<-1


acnew$caste_mjr_forwardboth<-0
acnew$caste_mjr_forwardboth[acnew$caste_forward==1 & acnew$femalerecontesting_maj==1 & acnew$bkr_councilor==1]<-1

acnew$caste_mjr_scboth<-0
acnew$caste_mjr_scboth[acnew$caste_sc==1 & acnew$femalerecontesting_maj==1 & acnew$bkr_councilor==1]<-1

acnew$caste_mjr_obcboth<-0
acnew$caste_mjr_obcboth[acnew$caste_obc==1 & acnew$femalerecontesting_maj==1 & acnew$bkr_councilor==1 ]<-1

acnew$caste_mjr_muslimboth<-0
acnew$caste_mjr_muslimboth[acnew$caste_muslim==1 & acnew$femalerecontesting_maj==1 & acnew$bkr_councilor==1]<-1



ac<-acnew
drops <- c("stat.merge.variable","new1","new2","newx","newy","new5")
ac<-ac[ , !(names(ac) %in% drops)]

ac$fwin_obc<-0
ac$fwin_obc[ac$Sex=="F" & ac$Position==1 & ac$caste_obc==1]<-1

ac$fwin_forward<-0
ac$fwin_forward[ac$Sex=="F" & ac$Position==1 & ac$caste_forward==1]<-1

ac$fwin_sc<-0
ac$fwin_sc[ac$Sex=="F" & ac$Position==1 & ac$caste_sc==1]<-1

ac$fwin_muslim<-0
ac$fwin_muslim[ac$Sex=="F" & ac$Position==1 & ac$caste_muslim==1]<-1

###############################################

aclevel<- as.data.frame(ac %>% group_by(Constituency_No, Year) %>% summarise_if(is.numeric, sum, na.rm = TRUE))
ac<-subset(ac, Position==1)
ac<-ac[,c(1:14)]
aclevel<-aclevel[,c(1,2,6:ncol(aclevel))]
colnames(aclevel)[which(colnames(aclevel)=="Constituency_No")]<-"acno"
colnames(aclevel)[which(colnames(aclevel)=="Year")]<-"election"
colnames(aclevel)[which(colnames(aclevel)=="Votes")]<-"totalvotes"
colnames(aclevel)[which(colnames(aclevel)=="malecand")]<-"nmalecand"
colnames(aclevel)[which(colnames(aclevel)=="femalecand")]<-"nfemalecand"
colnames(aclevel)[which(colnames(aclevel)=="femalevote")]<-"totalfemalevote"

ac <- ac[order(ac$Constituency_No, ac$Year),] 
aclevel <- aclevel[order(aclevel$acno, aclevel$election),] 
acdata<-cbind(ac,aclevel)

dropscol <-c("acno","election")
acdata<-acdata[ , !(names(acdata) %in% dropscol)]
save(acdata, file="2_ProcessedData/acdata.RData")

########
rm(list=setdiff(ls(), c("acdata")))
ward<-read.csv("1_RawData/Municipal_TurnoutMappingResData.csv")
ward2012<-subset(ward, election==2012)
ward2007<-subset(ward, election==2007)
ward2017<-subset(ward, election==2017)
ward$nwards<-1

ward$scwomen<-0
ward$scwomen[ward$resstatus=="SCW"]<-1
table(ward$scwomen)

ward$scgen<-0
ward$scgen[ward$resstatus=="SC"]<-1
table(ward$scgen)

ward$sctotal<-0
ward$sctotal[ward$resstatus=="SC"|ward$resstatus=="SCW"]<-1
table(ward$sctotal)
table(ward$sctotal,ward$election)

ward$incwin<-0
ward$incwin[ward$eci_party1=="INC"]<-1

ward$bjpwin<-0
ward$bjpwin[ward$eci_party1=="BJP"]<-1

ward$aapwinner<-0
ward$aapwinner[ward$eci_party1=="AAP"|ward$eci_party1=="AAAP"]<-1

ward$bspwinner<-0
ward$bspwinner[ward$eci_party1=="BSP"]<-1

ward$indwinner<-0
ward$indwinner[ward$eci_party1=="IND"]<-1

ward$majorpartywinner<-0
ward$majorpartywinner[ward$eci_party1=="INC"|ward$eci_party1=="BJP" |ward$eci_party1=="AAP" ]<-1


ward$incfwin<-0
ward$incfwin[ward$eci_party1=="INC" & ward$gender1=="F"]<-1

ward$bjpfwin<-0
ward$bjpfwin[ward$eci_party1=="BJP"& ward$gender1=="F"]<-1

ward$aapfwinner<-0
ward$aapfwinner[(ward$eci_party1=="AAP"|ward$eci_party1=="AAAP") & ward$gender1=="F"]<-1

ward$bspfwinner<-0
ward$bspfwinner[ward$eci_party1=="BSP" & ward$gender1=="F"]<-1

ward$indfwinner<-0
ward$indfwinner[ward$eci_party1=="IND" & ward$gender1=="F"]<-1

ward$majorpartyfwinner<-0
ward$majorpartyfwinner[(ward$eci_party1=="INC"|ward$eci_party1=="BJP" |ward$eci_party1=="AAP") & ward$gender1=="F" ]<-1


ward$closef<-0
ward$closef[ward$gender1=="F" & ward$close5==1]<-1

ward$closebjpfwinner<-0
ward$closebjpfwinner[ward$eci_party1=="BJP"& ward$gender1=="F" & ward$close5==1]<-1

ward$closeincfwinner<-0
ward$closeincfwinner[ward$eci_party1=="INC"& ward$gender1=="F" & ward$close5==1]<-1
table(ward$closeincfwinner)

ward$closeaapfwinner<-0
ward$closeaapfwinner[ward$eci_party1=="AAP"& ward$gender1=="F" & ward$close5==1]<-1


ward$closebjpmwinner<-0
ward$closebjpmwinner[ward$eci_party1=="BJP"& ward$gender1=="M" & ward$close5==1]<-1

ward$closeincmwinner<-0
ward$closeincmwinner[ward$eci_party1=="INC"& ward$gender1=="M" & ward$close5==1]<-1

ward$closeaapmwinner<-0
ward$closeaapmwinner[ward$eci_party1=="AAP"& ward$gender1=="M" & ward$close5==1]<-1


ward$samewardres<-NA
ward$samewardres[(ward$reswomen==1|ward$reswomen==0) & (ward$prev_resstatus=="G" | ward$prev_resstatus=="SC")]<-0
ward$samewardres[(ward$reswomen==0) & (ward$prev_resstatus=="SCW" | ward$prev_resstatus=="W")]<-0
ward$samewardres[ward$reswomen==1 & (ward$prev_resstatus=="SCW"| ward$prev_resstatus=="W")]<-1

ward$aapclose<-NA
ward$aapclose[(ward$eci_party1=="AAP"| ward$eci_party2=="AAP") & ward$close5==1]<-1
ward$aapfclose<-NA
ward$aapfclose[(ward$eci_party1=="AAP"| ward$eci_party2=="AAP") & ward$close5==1 & ward$reswomen==1]<-1


ward$bjpclose<-0
ward$bjpclose[(ward$eci_party1=="BJP"| ward$eci_party2=="BJP") & ward$close5==1]<-1

ward$bjpclosewins<-0
ward$bjpclosewins[(ward$eci_party1=="BJP") & ward$close5==1]<-1

ward$incclose<-0
ward$incclose[(ward$eci_party1=="INC"|ward$eci_party2=="INC") & ward$close5==1]<-1

ward$incclosewins<-0
ward$incclosewins[(ward$eci_party1=="INC") & ward$close5==1]<-1

ward$aapclose<-0
ward$aapclose[(ward$eci_party1=="AAP" | ward$eci_party1=="AAAP"|ward$eci_party2=="AAP" | ward$eci_party2=="AAAP") & ward$close5==1]<-1

ward$aapclosewins<-0
ward$aapclosewins[(ward$eci_party1=="AAP" | ward$eci_party1=="AAAP") & ward$close5==1]<-1

ward$bjpfclose<-NA
ward$bjpfclose[(ward$eci_party1=="BJP"| ward$eci_party2=="BJP") & ward$close5==1 & ward$reswomen==1]<-1

ward$incclose<-NA
ward$incclose[(ward$eci_party1=="INC"| ward$eci_party2=="INC") & ward$close5==1]<-1
ward$incfclose<-NA
ward$incfclose[(ward$eci_party1=="INC"| ward$eci_party2=="INC") & ward$close5==1 & ward$reswomen==1]<-1

#ward<-ward[,c(2,7,19:26,32:49,169:ncol(ward))]
#ward<-subset(ward, election==2017)
# keepcolac <-c("commonname","wardname","acno","acname","actype","resstatus","mcdcorp","eci_candname1","gender1","eci_party1","eci_candname2","gender2","eci_party2","eci_candname3","gender3","eci_party3","winner_voteshare","runner_voteshare","close5")
# wardac<-ward[ ,  (names(ward) %in% keepcolac)]
#############################################################
ward<- as.data.frame(ward %>% group_by(election,acno) %>% summarise_if(is.numeric, sum, na.rm = TRUE))
# ward2012<- as.data.frame(ward2012 %>% group_by(acno) %>% summarise_if(is.numeric, sum, na.rm = TRUE))
# 
# table(ward2012$reswomen,ward2012$acno)
ward$match[ward$election==2007]<-1
ward$match[ward$election==2012]<-2
ward$match[ward$election==2017]<-3

acdata$match[acdata$Year==2008]<-1
acdata$match[acdata$Year==2013]<-2
acdata$match[acdata$Year==2015]<-2
acdata$match[acdata$Year==2020]<-3

colnames(ward) <- paste("w", colnames(ward), sep = ".")
save(ward, file="2_ProcessedData/ward.RData")

ward$new1<-1
acdata$new2<- 2
wardac2 <- merge(ward,acdata , by.x=c("w.acno","w.match"), by.y=c("Constituency_No","match"), all.x = TRUE, all.y=FALSE)
wardac2$stat.merge.variable <- rowSums(wardac2[,c("new1", "new2")], na.rm=TRUE)
ward$new1<-NULL
acdata$new2<- NULL

dropscol <-c("new1","new2","stat.merge.variable","X")
wardac2<-wardac2[ , !(names(wardac2) %in% dropscol)]

wardac2$femalewin<-0
wardac2$femalewin[wardac2$Sex=="F"]<-1

wardac2$w.nreswomen[wardac2$w.reswomen/wardac2$w.nwards<0.4]<-1
wardac2$w.nreswomen[wardac2$w.reswomen/wardac2$w.nwards>0.4 & wardac2$w.reswomen/wardac2$w.nwards<0.75]<-2
wardac2$w.nreswomen[wardac2$w.reswomen/wardac2$w.nwards>=0.75]<-3
table(wardac2$w.nreswomen, wardac2$Year)
wardac2$femalevoteshare<-round(wardac2$totalfemalevote*100/wardac2$totalvotes,2)
wardac2$nonmajfemalevoteshare<-round(wardac2$nonmajorfemalevote*100/wardac2$totalvotes,2)
wardac2$majfemalevoteshare<-round(wardac2$majorfemalevote*100/wardac2$totalvotes,2)

rm(list=setdiff(ls(), c("wardac2")))
#outcome variables - table 3
wardac2$femalemajcandper <- (wardac2$femalemajcand*100)/wardac2$actotcand
wardac2$femalemajcand_mod<-NA
wardac2$femalemajcand_mod[wardac2$femalemajcandper==0]<-0
wardac2$femalemajcand_mod[wardac2$femalemajcandper>1]<-1
wardac2$femalesmallpartyper <- (wardac2$femalenonmajpartycand*100)/wardac2$actotcand
wardac2$femalesmallparty_mod<-NA
wardac2$femalesmallparty_mod[wardac2$femalesmallpartyper==0] <-0
wardac2$femalesmallparty_mod[wardac2$femalesmallpartyper>0] <-1
wardac2$femaleindcandper <- (wardac2$femaleindcand*100)/wardac2$actotcand
wardac2$femaleindcand_mod<-NA
wardac2$femaleindcand_mod[wardac2$femaleindcandper==0] <-0
wardac2$femaleindcand_mod[wardac2$femaleindcandper>0] <-1

#outcome variables - table 4
wardac2$everpriorfmod<-NA
wardac2$everpriorfmod[wardac2$everpriorf==0]<-0
wardac2$everpriorfmod[wardac2$everpriorf>=1]<-1
wardac2$everpriorfper <- (wardac2$everpriorf*100)/wardac2$actotcand
wardac2$everpriorfmajper <- (wardac2$everpriorfmaj*100)/wardac2$actotcand


#outcome variables - table 5
#ftotnewcandmajmod femalerecontesting_majmod  femalerecontest_incmaj    fprior_rec_maj


wardac2$ftotnewcandmajmod<-NA
wardac2$ftotnewcandmajmod[wardac2$ftotnewcandmaj==0]<-0
wardac2$ftotnewcandmajmod[wardac2$ftotnewcandmaj>=1]<-1


wardac2$femalerecontestingcand<-NA
wardac2$femalerecontestingcand[wardac2$femalerecontest==0]<-0
wardac2$femalerecontestingcand[wardac2$femalerecontest>=1]<-1

wardac2$femalerecontesting_majmod<-NA
wardac2$femalerecontesting_majmod[wardac2$femalerecontesting_maj==0]<-0
wardac2$femalerecontesting_majmod[wardac2$femalerecontesting_maj>=1]<-1

#outcome variables - table 6
#turnout femalevoteshare femalewin femaleincumbentwins femaletop3cand femaletop5cand
wardac2$Electors[wardac2$Electors==0]<-NA
wardac2$turnout <- (wardac2$Valid_Votes*100)/ wardac2$Electors
wardac2$femaletop3cand[wardac2$femaletop3cand>1]<-1 
wardac2$femaletop5cand[wardac2$femaletop3cand>1]<-1 
wardac2turnout<-subset(wardac2, is.na(wardac2$turnout)==FALSE)

##table 5 - additional results - caste background
#caste_forward"                "caste_obc"                    "caste_sc"                     "caste_muslim
#caste_mjr_forward"            "caste_mjr_sc"                 "caste_mjr_obc caste_mjr_muslim
wardac2$caste_forwardper <-  (wardac2$caste_forward*100)/(wardac2$actotcand)
wardac2$caste_obcper <-  (wardac2$caste_obc*100)/(wardac2$actotcand)
wardac2$caste_scper <-  (wardac2$caste_sc*100)/(wardac2$actotcand)
wardac2$caste_muslimper <-  (wardac2$caste_muslim*100)/(wardac2$actotcand)
wardac2$caste_forwardmajper <-  (wardac2$caste_mjr_forward*100)/(wardac2$actotcand)
wardac2$caste_obcmajper <-  (wardac2$caste_mjr_obc*100)/(wardac2$actotcand)
wardac2$caste_scmajper <-  (wardac2$caste_mjr_sc*100)/(wardac2$actotcand)
wardac2$caste_muslimmajper <-  (wardac2$caste_mjr_muslim*100)/(wardac2$actotcand)
wardac2$caste_obcperprior <-  (wardac2$caste_obcprior*100)/(wardac2$actotcand)
wardac2$caste_obcmajperprior <-  (wardac2$caste_mjr_obcprior*100)/(wardac2$actotcand)
wardac2$caste_obcperrecont <-  (wardac2$caste_obcrecont*100)/(wardac2$actotcand)
wardac2$caste_obcmajperrecont <-  (wardac2$caste_mjr_obcrecont*100)/(wardac2$actotcand)
wardac2$caste_obcpernew <-  (wardac2$caste_obcnew*100)/(wardac2$actotcand)
wardac2$caste_obcmajpernew <-  (wardac2$caste_mjr_obcnew*100)/(wardac2$actotcand)


wardac2<-wardac2[,c("w.nwards","w.reswomen","w.acno","Year","femalemajcandper","femalemajcand_mod","femalesmallpartyper","femalesmallparty_mod","femaleindcandper","femaleindcand_mod","everpriorfmaj","everpriorfmajper","everpriorfmod","everpriorfper","ftotnewcandmajmod","femalerecontestingcand","femalerecontesting_majmod","femalerecontest_incmaj","fprior_rec_maj","turnout","femaletop3cand","femaletop5cand","femalewin","femaleincumbentwins","femalevoteshare","caste_forwardmajper","caste_obcmajper","caste_muslimmajper","caste_scmajper","caste_obcmajperprior","caste_obcmajperrecont","caste_obcmajpernew","everpriorm","malerecontesting","mprior_rec","nmalecand","everpriorf","fprior_rec","femalerecontesting","ftotnewcand","nfemalecand","ftotnewcandmaj","femalemajcand","femalerecontesting_maj","mtotnewcand","everpriormmaj","mprior_rec_maj","malerecontesting_maj","everpriormnonmaj","mprior_rec_nonmaj","malerecontesting_nonmaj","mtotnewcandnonmaj","malenonmajcand","everpriorfnonmaj","fprior_rec_nonmaj","femalerecontesting_nonmaj","ftotnewcandnonmaj","femalenonmajcand")]
wardac2$identifier<-paste("w.acno","Year",sep="_")

save(file="2_ProcessedData/wardac2023.RData",wardac2)
##############################################################################
## Section 3 ends
##############################################################################


##############################################################################
## Section 4 begins
## This code prepares 
##############################################################################
cand <- read_excel("1_RawData/CandidateElectionData_original.xlsx", 
                   col_types = c("numeric", "numeric", "text", 
                                 "text", "text", "numeric", "numeric", 
                                 "text", "text", "text", "text","numeric", "text", "text",
                                 "text", "text", "text", "text", 
                                 "text", "numeric", "text", "text", 
                                 "text", "text", "text", "text", "text", 
                                 "numeric", "numeric", "numeric", 
                                 "numeric", "numeric", "text", "numeric", 
                                 "numeric", "text", "numeric","text"))

cand<-cand[,c(1:ncol(cand)-1)]
x<-cand[duplicated(cand[,c("election","commonname","votes","eci_pos")], fromLast=TRUE), ]
caste <-read_excel("1_RawData/CasteData_Lee2020_AJPS.xlsx")

cand$new1<-1
caste$new2<- 2
cand_caste <- merge(cand,caste , by.x=c("election","commonname","votes"), by.y=c("year","connamnum","votespolled"), all.x = TRUE, all.y=FALSE)
cand_caste$stat.merge.variable <- rowSums(cand_caste[,c("new1", "new2")], na.rm=TRUE)

cand_nomatch <- subset(cand_caste,stat.merge.variable==1)
cand_match <- subset(cand_caste,stat.merge.variable==3)
cand_match$dup<-ifelse(duplicated(cand_match[,c("election","commonname","votes")]) | duplicated(cand_match[,c("election","commonname","votes")], fromLast = TRUE)==TRUE,1,0)#merge road and electoral data

x<-subset(cand_match, dup==1)

cand_match<-subset(cand_match, dup==0)
cand_match<-cand_match[,c(1:55)]

x<-x %>% group_by(election, commonname, votes) %>% mutate(n = n()) %>% filter(n > 1)
x<-subset(x, (x$n==4 & x$eci_party==x$party)| x$n==2)

x$dup2<-ifelse(duplicated(x[,c("election","commonname","votes","eci_pos","eci_party","party")]) | duplicated(x[,c("election","commonname","votes","eci_pos","eci_party","party")], fromLast = TRUE)==TRUE,1,0)#merge road and electoral data
x<-x[!duplicated(x[,c("election","commonname","votes","eci_pos","eci_party","party","totalassets")]), ]
x<-x[,c(1:55)]

candcaste_final<-rbind(as.data.frame(cand_match),as.data.frame(cand_nomatch),as.data.frame(x))
candcaste_final$identifier<-paste(candcaste_final$commonname, candcaste_final$election, sep="_")

save(candcaste_final, file="2_ProcessedData/candcaste_final.RData")

##############################################################################
## Section 4 ends
##############################################################################


##############################################################################
## Section 5 begins
## This code prepares 
##############################################################################
# Load required datasets
#1
cand <- read_excel("1_RawData/CandidateElectionData_original.xlsx", 
                   col_types = c("numeric", "numeric", "text", 
                                 "text", "text", "numeric", "numeric", 
                                 "text", "text", "text", "text","numeric", "text", "text",
                                 "text", "text", "text", "text", 
                                 "text", "numeric", "text", "text", 
                                 "text", "text", "text", "text", "text", 
                                 "numeric", "numeric", "numeric", 
                                 "numeric", "numeric", "text", "numeric", 
                                 "numeric", "text", "numeric","text"))
#2
load("2_ProcessedData/candcaste_final.RData")

#3
turnout<-read.csv("1_RawData/Municipal_TurnoutMappingResData.csv")
candelection<-turnout

#################################################################
#clean professions in candidate data
cand$occnew<-tolower(cand$occupation)
cand$spouseoccnew<-tolower(cand$spouse_occ)

cand$occnew<-gsub("\\W"," ",cand$occnew)
cand$spouseoccnew<-gsub("\\W"," ",cand$spouseoccnew)

cand$occnew<-gsub("\\d"," ",cand$occnew)
cand$spouseoccnew<-gsub("\\d"," ",cand$spouseoccnew)

cand$occnew<-gsub(" +"," ",cand$occnew)
cand$spouseoccnew<-gsub(" "," ",cand$spouseoccnew)

cand$occcat<-NA
cand$occcat[is.na(cand$occnew)==FALSE]<-"none"
cand$occheck<-NA
cand$housewife<-ifelse(grepl("homemaker|wife|house make|home maker",cand$occnew)==TRUE & cand$gender=="F",1,0)

cand$occheck<-0
cand$occheck[cand$housewife==1]<-1
cand$occcat[cand$housewife==1]<-"housewife"

cand$govt<-ifelse(grepl("dcw|chief|govt|government|police|serviceman|army|aganwari|anganbadi|service man|service men|angan",cand$occnew)==TRUE & cand$occheck==0 ,1,0)

cand$occheck[cand$govt==1]<-1
cand$occcat[cand$govt==1]<-"govt. job"

cand$realestate_property<-ifelse(grepl("building|property|builder|construction|real estate|real state|developer|estate|commision|properties" ,cand$occnew)==TRUE & cand$occheck==0 ,1,0)

cand$occheck[cand$realestate_property==1]<-1
cand$occcat[cand$realestate_property==1]<-"property"

cand$business<-ifelse(grepl("store|busniess|factory|academy|proprietor|publisher|profession|traders|partner|cricket coach|film|buisness|designer|manufacture|industrialist|confectioner|computer|capital|trading|bussines|business|business|shop|own|bussiness|coaching" ,cand$occnew)==TRUE & cand$occheck==0 ,1,0)

cand$occheck[cand$business==1]<-1
cand$occcat[cand$business==1]<-"small business"

cand$privateprof<-ifelse(grepl("tennis|coach|creative|writer|decorator|pravite|sport|stock broker|employed|journalist|service|technician|medical|musician|hospital|bank|journalism|director|advisor|chartered|accountant|editor|private|pvt|own|employee|salaried|consultant|professional|doctor|engineer|advertisement|media" ,cand$occnew)==TRUE & cand$occheck==0 ,1,0)

cand$occheck[cand$privateprof==1]<-1
cand$occcat[cand$privateprof==1]<-"private sector and professionals"

cand$mcd<-ifelse(grepl("politician|political|councilor|m c d|councellor|councillor|mcd|corporation" ,cand$occnew)==TRUE & cand$occheck==0 ,1,0)

cand$occheck[cand$mcd==1]<-1
cand$occcat[cand$mcd==1]<-"mcd"

cand$teaching<-ifelse(grepl("education|head mistress|teacher|school|uni|college|principal|professor|faculty" ,cand$occnew)==TRUE & cand$occheck==0 ,1,0)

cand$occheck[cand$teaching==1]<-1
cand$occcat[cand$teaching==1]<-"teaching"

cand$advocate<-ifelse(grepl("correspondent|llb|advicate|adocated|advocacy|lowyer|law|advocate|lawyer|legal",cand$occnew)==TRUE & cand$occheck==0 ,1,0)

cand$occheck[cand$advocate==1]<-1
cand$occcat[cand$advocate==1]<-"advocate"

cand$student<-ifelse(grepl("student|ba|studing",cand$occnew)==TRUE & cand$occheck==0 ,1,0)
cand$occheck[cand$student==1]<-1
cand$occcat[cand$student==1]<-"student"

cand$farmer<-ifelse(grepl("farmer|agri|farming" ,cand$occnew)==TRUE & cand$occheck==0 ,1,0)

cand$occheck[cand$farmer==1]<-1
cand$occcat[cand$farmer==1]<-"farmer"


cand$retired<-ifelse(grepl("retired|retd.|pension|old|retire" ,cand$occnew)==TRUE & cand$occheck==0 ,1,0)

cand$occheck[cand$retired==1]<-1
cand$occcat[cand$retired==1]<-"retired"

cand$workingclass<-ifelse(grepl("vendor|dispensary|worker|mistry|driver|electrician|worker|co ordinator|comm|lab|domastic|agent|maison|bike|travel|daily|artist|authorised|barber|belt|bone|air|contractor|supplier|auto driver|coaching|subzi|tuition|tuittion|serap|tution|theatre|tent|tutor|yoga|beautician|sweeper|safai|martial|parlor|boutique|dry|pco|salesman|sales men|singer|tea|talier|mashakhor|mason|mazdoori|mochi|nurse|chhole|photo|pot|printing|embroidery|electician|howker|illetrate|insurance|kerosene|fabric|fish|flower|fruit|stall|garments|genral store|guide|handicraft work at home|hobby|beauty|stich|botique|bouting|boutique|box|lic|milk|catering|mechanic|cashier|cable|cloth|contractual|cook|dance|document|bangle|scrap|painter|tour|labour|maid|domestic|servant|waiter|wage|carpenter|cable|operator|transport|dastkari|kirana|painter|plumber|mistri|tailor|agentartist|astro|pandit" ,cand$occnew)==TRUE & cand$occheck==0 ,1,0)
cand$occheck[cand$workingclass==1]<-1
cand$occcat[cand$workingclass==1]<-"workingclass"

cand$rentalincome<-ifelse(grepl("rent|rental|income" ,cand$occnew)==TRUE & cand$occheck==0 ,1,0)
cand$occheck[cand$rentalincome==1]<-1
cand$occcat[cand$rentalincome==1]<-"rental income"

cand$selfemployed<-ifelse(grepl("self" ,cand$occnew)==TRUE & cand$occheck==0 ,1,0)
cand$occheck[cand$selfemployed==1]<-1
cand$occcat[cand$selfemployed==1]<-"self-employed"

cand$socialwork<-ifelse(grepl("n g o |ngo|social|activist|sociar|socieal" ,cand$occnew)==TRUE & cand$occheck==0 ,1,0)
cand$occheck[cand$socialwork==1]<-1
cand$occcat[cand$socialwork==1]<-"social worker"

cand$unemployed<-ifelse(grepl("no|unemp|not working|preparation for competition exam" ,cand$occnew)==TRUE & cand$occheck==0 ,1,0)
cand$occheck[cand$unemployed==1]<-1
cand$occcat[cand$unemployed==1]<-"unemployed"

cand$occcat[(grepl("not filled" ,cand$occnew)==TRUE & cand$occheck==0)]<-NA

mcd <- read_excel("1_RawData/AE_WomenManualMatch.xls")
mcd<-subset(mcd,mcd$IsContestedEver=="Yes" )

dropscol <-c("WardNumber","WardName")
mcd<-mcd[ , !(names(mcd) %in% dropscol)]

cand$new1<-1
mcd$new2<- 2
mcdall <- merge(cand,mcd , by.x=c("election","commonname", "eci_pos"), by.y=c("ElectionYear","CommonName","WardPosition"), all.x = TRUE, all.y=FALSE)
mcdall$contestmla <- rowSums(mcdall[,c("new1", "new2")], na.rm=TRUE)
cand$new1<-NULL
mcd$new2<- NULL

mcdall$contestmla[mcdall$contestmla==1]<-0
mcdall$contestmla[mcdall$contestmla==3]<-1

dropscol <-c("new1","new2")
mcdall<-mcdall[ , !(names(mcdall) %in% dropscol)]

mcdall<-subset(mcdall, mcdall$eci_candname!="NOTA")
########################################################
#add data on caste produced 2_CandidateDatabase/ 2_addcastedata file
candcaste_final$castedata[candcaste_final$stat.merge.variable==1]<-0
candcaste_final$castedata[candcaste_final$stat.merge.variable==3]<-1
dropscol <-c("new1","new2","stat.merge.variable")
candcaste_final<-candcaste_final[ , !(names(candcaste_final) %in% dropscol)]
candcaste_final<-candcaste_final[,c(1,2,7,39:ncol(candcaste_final))]


mcdall$new1<-1
candcaste_final$new2<- 2
mcdall2 <- merge(mcdall,candcaste_final , by.x=c("election","commonname", "eci_pos"), by.y=c("election","commonname", "eci_pos"), all.x = TRUE, all.y=FALSE)
mcdall2$castematch <- rowSums(mcdall2[,c("new1", "new2")], na.rm=TRUE)
mcdall$new1<-NULL
candcaste_final$new2<- NULL
dropscol <-c("new1","new2","castematch")
mcdall<-mcdall2[ , !(names(mcdall2) %in% dropscol)]

########################################################
#add turnout data
turnout<-turnout[,c("pcno","pcname","pctype","acno","acname","actype","election","commonname","wardpop","wardscpop","wardscper2001","prev_resstatus","tot_electorate","male_electorate","female_electorate","tot_voter","male_voter","female_voter","turnoutper","maleturnoutper","femaleturnoutper","perchangeinturnout","pergapturnout_malefemale")]
mcdall$new1<-1
turnout$new2<- 2
mcdall2 <- merge(mcdall,turnout , by.x=c("election","commonname"), by.y=c("election","commonname"), all.x = TRUE, all.y=FALSE)
mcdall2$statmatch <- rowSums(mcdall2[,c("new1", "new2")], na.rm=TRUE)
mcdall$new1<-NULL
turnout$new2<- NULL

dropscol <-c("new1","new2","statmatch")
mcdall<-mcdall2[ , !(names(mcdall2) %in% dropscol)]

########################################################
#add more data from turnout file
#candelection<-candelection[,c("election","commonname","eci_party1","eci_candname1","gender1","votes1","eci_party2","eci_candname2","gender2","votes2","eci_party3","eci_candname3","gender3","votes3","mov","margin_runsecondrun","close5","close25","close1")]
candelection<-candelection[,c("election","commonname","eci_party1","eci_candname1","gender1","votes1","eci_party2","eci_candname2","gender2","votes2","eci_party3","eci_candname3","gender3","votes3","mov")]
mcdall$new1<-1
candelection$new2<- 2
mcdall2 <- merge(mcdall,candelection , by.x=c("election","commonname"), by.y=c("election","commonname"), all.x = TRUE, all.y=FALSE)
mcdall2$statmatch <- rowSums(mcdall2[,c("new1", "new2")], na.rm=TRUE)
mcdall$new1<-NULL
candelection$new2<- NULL
dropscol <-c("new1","new2","statmatch")
mcdall<-mcdall2[ , !(names(mcdall2) %in% dropscol)]
mcdallretain<-mcdall

#are female candidates that contest high level having different backgrounds?
colnames(mcdall)<-gsub("\\.","_",colnames(mcdall))
mcdall<-mcdall %>% group_by(commonname, election)  %>% mutate(wardvotes=sum(votes, na.rm=TRUE))
mcdall$wardvotesper<-(mcdall$votes*100)/mcdall$wardvotes

###
setwd("/Users/tg2778/Dropbox/0_Reviews_RnRs/092022_AJPS_PathwayPower/ReplicationFolder")
save(file="2_ProcessedData/mcdall_03022021.RData",mcdall)

load("2_ProcessedData/mcdall_03022021.RData")
mcdall$election<-as.factor(mcdall$election)
mcdall$acno<-as.factor(mcdall$acno)
mcdall$women[mcdall$gender=="M"]<-0 
mcdall$women[mcdall$gender=="F"]<-1
table(mcdall$women)

mcdall$major <- 0 
mcdall$major[mcdall$eci_party=="INC"|mcdall$eci_party=="BJP"|mcdall$eci_party=="AAP"]<-1
table(mcdall$major)

mcdall$independent <-0
mcdall$independent[mcdall$eci_party=="IND"]<-1
table(mcdall$independent)

mcdall$majormla <- 0
mcdall$majormla[mcdall$contestmla==1 & mcdall$major==1] <- 1 
table(mcdall$majormla )

mcdall$majormla2 <- 0
mcdall$majormla2[(mcdall$contestmla==1 & mcdall$election==2007 & (mcdall$Party2008=="AAP"|mcdall$Party2008=="BJP"|mcdall$Party2008=="INC"))] <- 1
mcdall$majormla2[(mcdall$contestmla==1 & mcdall$election==2012 & (mcdall$Party2013=="AAP"|mcdall$Party2013=="BJP"|mcdall$Party2013=="INC"))] <- 1
mcdall$majormla2[(mcdall$contestmla==1 & mcdall$election==2012 & (mcdall$Party2015=="AAP"|mcdall$Party2015=="BJP"|mcdall$Party2015=="INC"))] <- 1 
mcdall$majormla2[(mcdall$contestmla==1 & mcdall$election==2017 & (mcdall$Party2020=="AAP"|mcdall$Party2020=="BJP"|mcdall$Party2020=="INC"))] <- 1 
table(mcdall$majormla2)

mcdall$z2wardvotesper = scale(mcdall$wardvotesper)
summary(mcdall$z2wardvotesper)

mcdall$indepmla <- 0
mcdall$indepmla[(mcdall$contestmla==1 & mcdall$election==2007 & (mcdall$Party2008=="IND"))] <- 1
mcdall$indepmla[(mcdall$contestmla==1 & mcdall$election==2012 & (mcdall$Party2013=="IND"))] <- 1
mcdall$indepmla[(mcdall$contestmla==1 & mcdall$election==2012 & (mcdall$Party2015=="IND"))] <- 1 
mcdall$indepmla[(mcdall$contestmla==1 & mcdall$election==2017 & (mcdall$Party2020=="IND"))] <- 1 
table(mcdall$indepmla)


#background variables
#highedu criminal highcases lntotalassets  lnage z2wardvotesper
# table(mcdall$edurecode2)
# mcdall$highedu[mcdall$edurecode2=="below high school"]<-0
# mcdall$highedu[mcdall$edurecode2=="high school and above"]<-1
# 

mcdall$highedu<-NA
mcdall$highedu[mcdall$edurecode1!="Graduate and above" & is.na(mcdall$edurecode1)==FALSE]<-0
mcdall$highedu[mcdall$edurecode1=="Graduate and above"]<-1

table(mcdall$highedu)
mcdall$criminal<-NA
mcdall$criminal[mcdall$ncases==0]<-0
mcdall$criminal[mcdall$ncases>=1]<-1
table(mcdall$criminal)

mcdall$highcases<-NA
mcdall$highcases[mcdall$ncases<=1]<-0
mcdall$highcases[mcdall$ncases>=2]<-1
table(mcdall$highcases)



mcdall$scres<-0
mcdall$scres[mcdall$resstatus=="SC" | mcdall$resstatus=="SCW"]<-1
table(mcdall$scres)

table(mcdall$newcaste)
mcdall$sccand<-NA
mcdall$sccand[is.na(mcdall$newcaste)==FALSE]<-0
mcdall$sccand[mcdall$newcaste=="Scheduled Caste"]<-1
table(mcdall$sccand)
mcdall$obc<-NA
mcdall$obc[is.na(mcdall$newcaste)==FALSE]<-0
mcdall$obc[mcdall$newcaste=="Gujjar"|mcdall$newcaste=="Jat"|mcdall$newcaste=="Other OBC"|mcdall$newcaste=="Yadav"]<-1
mcdall$forward<-NA
mcdall$forward[is.na(mcdall$newcaste)==FALSE]<-0
mcdall$forward[mcdall$newcaste=="Bania"|mcdall$newcaste=="Brahmin"|mcdall$newcaste=="Kayastha"|mcdall$newcaste=="Khatri"|mcdall$newcaste=="Rajput"|mcdall$newcaste=="Sikh"]<-1



mcdall$lntotalassets <-log(mcdall$totalassets)
mcdall$lnage <- log(mcdall$age)


mcdallselect<-mcdall[,c("women","education","edurecode1","wardvotesper","mov","z2wardvotesper","majormla","majormla2",
                        "major","highedu","contestmla","criminal","highcases","totalassets","lntotalassets","age","lnage",
                        "election","acno", "scres","forward","obc","sccand","muslim","nontwice","commonname")]

save(mcdallselect, file="2_ProcessedData/mcdallselect.RData")


##############################################################################
## Section 5 ends
##############################################################################

## GENERATE CODEBOOKS
##############################################################################
# Set working directory
setwd("/Users/tg2778/Dropbox/0_Reviews_RnRs/092022_AJPS_PathwayPower/ReplicationFolder")
##############################################################################

##############################################################################
# Load analysis datasets
load("2_ProcessedData/wardac2023.RData")
wardac2 <- set_label(wardac2, c("Number of local seats", "Number of reserved local seats", "Constituency number","Election year","Percent women major party candidates","Has a woman major party candidate","Percent women small party candidates","Has a woman small party candidate","Percent women independent candidates","Has a woman independent candidate","Has women major party candidate with local background","Percent women major party candidate with local background","Has woman party candidate with local background","Percent women candidate with local background","Has new women major party candidate","Recontesting woman candidate","Recontesting woman major party candidate","Recontesting woman incumbent major party", "Recontesting woman major party candidate with local background", "Voter turnout", "Women in top 3", "Women in top 5", "Woman wins", "Woman incumbent wins","Women vote share", "Woman major party forward caste percent","Woman major party OBC caste percent","Woman major party Muslim percent","Woman major party SC percent", "Woman major party OBC with local bakground percent", "Woman major party OBC recontesting percent", "Woman new OBC percent","Men with local background","Recontesting men","Recontesting men with local background","N male candidate","Women with local background","Recontesting women with local background","Recontesting women","Total new woman candidates","Total female candidates","Total new woman major party candidates","Total woman major party candidates","Total woman recontesting major party candidates","Total new male candidates","Men major with local background","Men recontesting major with local background","Men recontesting major", "Men non-major with local background","Men recontesting non-major with local","Men recontesting non-major","Total new men non-major","N men non-major","Women non-major with local background","Women non-major recontesting with local","Women recontesting non-major","Total woman new non-major","Women non-major candidates","Unique identifier"))
str(wardac2)
simple_codebook <- enframe(get_label(wardac2))

descriptives <- wardac2 %>% describe(fast=TRUE)  %>% 
  mutate_if(is.numeric, round, digits=3) %>% as_tibble() %>% select("mean","sd","n","min","max")
descriptives$variabletype<-"Numeric"
descriptives$dataset<-"wardac2023.RData"
# add stats to codebook 
wardaccodebook <- cbind(simple_codebook,descriptives)

##############################################################################
load("2_ProcessedData/mcdallselect.RData")
mcdallselect$election<-as.numeric(as.character(mcdallselect$election))
mcdallselect$acno<-as.numeric(as.character(mcdallselect$acno))
mcdallselect <- set_label(mcdallselect, c("Woman","Education value","Education category","Candidates vote share percentage","Margin of victory","Standardize vote share percentage","Contest state elections on major party (ever)","Contest state election on major party in subsequent state election","Major party municipal candidate","Graduate and above educated","Contest state elections ever","Criminal allegations","High N criminal cases","Total assets","Total assets (log)","Age","Age (log)","Election year","State constituency number","Local seat reserved for SC","Forward caste","OBC","SC","Muslim","Non-twice","Local constituency number"))

str(mcdallselect)
simple_codebook2 <- enframe(get_label(mcdallselect))
descriptives <- mcdallselect %>% describe(fast=TRUE)  %>% 
  mutate_if(is.numeric, round, digits=3) %>% as_tibble() %>% select("mean","sd","n","min","max")
descriptives <- do.call(data.frame,                      # Replace Inf in data by NA
                        lapply(descriptives,
                               function(x) replace(x, is.infinite(x) | is.nan(x) | is.na(x), "")))
descriptives<-as.data.frame(descriptives)
descriptives$variabletype<-"Numeric"
descriptives$variabletype[descriptives$mean==""]<-"String"
descriptives$dataset<-"mcdallselect.RData"
mcdselectcodebook <- cbind(simple_codebook2,descriptives)

##############################################################################
load("1_RawData/ActivistSurveyData.RData")
alldata <- set_label(alldata, c("Name of the party of the respondent","Gender","Unique Identifier"))
str(alldata)
simple_codebook3 <- enframe(get_label(alldata))
descriptives <- alldata %>% describe(fast=TRUE)  %>% 
  mutate_if(is.numeric, round, digits=3) %>% as_tibble() %>% select("mean","sd","n","min","max")
descriptives <- do.call(data.frame,                      # Replace Inf in data by NA
                        lapply(descriptives,
                               function(x) replace(x, is.infinite(x) | is.nan(x) | is.na(x), "")))
descriptives$variabletype<-"Numeric"
descriptives$variabletype[descriptives$mean==""]<-"String"
descriptives$dataset<-"ActivistSurveyData.RData"
activistdatacodebook <- cbind(simple_codebook3,descriptives)
##############################################################################
load("2_ProcessedData/acmajor.RData")
acmajor <- set_label(acmajor, c("Recontests next election","Major party candidate","Voteshare","Margin of victory","Age","Age (ln)","Total assets (ln)","Highly educated","Criminal record","Election year","Constituency number","Reserved for SC","Caste","Forward caste","OBC","SC","Muslim","Unique Identifier","Woman"))
str(acmajor)
simple_codebook4 <- enframe(get_label(acmajor))
descriptives <- acmajor %>% describe(fast=TRUE)  %>% 
  mutate_if(is.numeric, round, digits=3) %>% as_tibble() %>% select("mean","sd","n","min","max")
descriptives <- do.call(data.frame,                      # Replace Inf in data by NA
                        lapply(descriptives,
                               function(x) replace(x, is.infinite(x) | is.nan(x) | is.na(x), "")))
descriptives$variabletype<-"Numeric"
descriptives$variabletype[descriptives$mean==""]<-"String"
descriptives$dataset<-"acmajor.RData"
acmajorcodebook <- cbind(simple_codebook4,descriptives)


##############################################################################
turnoutdata<-read.csv("1_RawData/Municipal_TurnoutMappingResData.csv")
turnoutdata <- set_label(turnoutdata, c("Unique identifier","Election year","Local consituency number or ward number","National constituency number","National constituency name","National constituency type",
                                        "State constituency number (or vidhan sabha number or acno)","State constituency name","State constituency type","Ward number","Ward number (non-alphabetic)","Ward name",
                                        "Ward population (2001 census)","Ward SC population (2001 census)","Ward SC percentage (2001 census)","Municipal corporation type","Reservation type","Previous reservation type",
                                        "Reserved women","Reserved SC","Total electorate","Male electorate","Female electorate","Total voters",
                                        "Male voters","Female voters","Turnout percent","Male turnout per","Female turnout per","Percent change in turnout",
                                        "Percent gender gap","N Candidates","N Independent Candidates","N party candidates","N viable candidates","Percent high school and above educated",
                                        "Percent missing education","Winner is highly educated","Runner is highly educated","Runner 2 is highly educated","Winners education is missing","Runner's education is missing",
                                        "Runner 2's education is missing","N female candidates","N female independent candidates","N Female party candidates","N female major party candidates","N female small party candidate",
                                        "Female votes","Total votes","Winner's party","Winner's name","Winner's gender","Winner's votes",
                                        "Runner's party","Runner's name","Runner's gender","Runner's vote","Runner 2's party","Runner 2's name",
                                        "Runner 2's gender","Runner 2's votes","Total votes","Winner's voteshare","Runner's voteshare","Runner 2's votershare","Margin of victory"))
str(turnoutdata)

simple_codebook5 <- enframe(get_label(turnoutdata))
descriptives <- turnoutdata %>% describe(fast=TRUE)  %>% 
  mutate_if(is.numeric, round, digits=3) %>% as_tibble() %>% select("mean","sd","n","min","max")
descriptives <- do.call(data.frame,                      # Replace Inf in data by NA
                        lapply(descriptives,
                               function(x) replace(x, is.infinite(x) | is.nan(x) | is.na(x), "")))
descriptives$variabletype<-"Numeric"
descriptives$variabletype[descriptives$mean==""]<-"String"
descriptives$dataset<-"Municipal_TurnoutMappingResData.csv"
turnoutcodebook <- cbind(simple_codebook5,descriptives)

##############################################################################
mcd<-read_dta("1_RawData/MunicipalCouncilSurvey.dta")
mcd <- set_label(mcd, c("Reserved for SC","Winner is highly educated","Winner's party","Winner's gender","Responded to interview","Unique identifier (anonymized)","Winner's vote share (standardized)","Margin of victory","National Constituency name"))
str(mcd)

simple_codebook6 <- enframe(get_label(mcd))
descriptives <- mcd %>% describe(fast=TRUE)  %>% 
  mutate_if(is.numeric, round, digits=3) %>% as_tibble() %>% select("mean","sd","n","min","max")
descriptives <- do.call(data.frame,                      # Replace Inf in data by NA
                        lapply(descriptives,
                               function(x) replace(x, is.infinite(x) | is.nan(x) | is.na(x), "")))
descriptives$variabletype<-"Numeric"
descriptives$variabletype[descriptives$mean==""]<-"String"
descriptives$dataset<-"MunicipalCouncilSurvey.dta"
mcdcodebook <- cbind(simple_codebook6,descriptives)
##############################################################################
# Generate FINAL Codebook
simple_codebook<-rbind(wardaccodebook,mcdselectcodebook,acmajorcodebook,turnoutcodebook)
colnames(simple_codebook)<-c("Variable","Description","Mean","StdDev","N", "Min","Max","VariableType","Dataset")
simple_codebook<-simple_codebook[,c("Dataset","Variable","Description","VariableType","Mean","StdDev","N", "Min","Max")]
write.csv(simple_codebook,"codebook.csv")

###
log_close()