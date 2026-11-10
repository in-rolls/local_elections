rm(list=ls())
library(dplyr)
library(ggplot2)
library(clubSandwich)
library(stargazer)
library(sandwich)
library(lmtest)
library(stringr)
library(logr)
################################################################################
#set working directory
setwd("/Users/tg2778/Dropbox/0_Reviews_RnRs/092022_AJPS_PathwayPower/ReplicationFolder")
################################################################################
##############################################################################
log_open("5_LogFiles/DataAnalysis.log")
##############################################################################
#load required data sets
load("2_ProcessedData/wardac2023.RData")
load("2_ProcessedData/mcdallselect.RData")
################################################################################
#keep only 4 wards as per main results stratification
wardac2<-subset(wardac2,wardac2$w.nwards==4)
wardac2$w.acno<-as.factor(wardac2$w.acno)
wardac2$Year<-as.factor(wardac2$Year)

################################################################################
#retain in mcdselect candidates for which affidavit data is available to add background controls
mcdall<-mcdallselect
mcdallselect<-mcdallselect[,c("contestmla","women","z2wardvotesper","major","election","highedu","criminal","highcases","lntotalassets","lnage","acno")]
mcdallselect<-mcdallselect[is.finite(mcdallselect$lntotalassets) & is.finite(mcdallselect$lnage), ]
mcdallselect<-na.omit(mcdallselect)
########################################################################
########################################################################
########################################################################
# MODELS
##gender gap in career progession
tab5_1<-lm(data=mcdall, contestmla ~ women + z2wardvotesper +major + election , na.action=na.exclude)
cov5_1       <- vcovCR(tab5_1,type="CR0",cluster=mcdall$acno)
robust_se5_1    <- sqrt(diag(cov5_1))

tab5_3<-lm(data=mcdall, contestmla ~ women + z2wardvotesper +major + election + acno, na.action=na.exclude)
cov5_3      <- vcovCR(tab5_3,type="CR0",cluster=mcdall$acno)
robust_se5_3    <- sqrt(diag(cov5_3))

tab5_2<-lm(data=mcdallselect, contestmla ~ women + z2wardvotesper + major + election + highedu + criminal+  highcases + lntotalassets +  lnage + z2wardvotesper, na.action=na.exclude)
cov5_2       <- vcovCR(tab5_2,type="CR0",cluster=mcdallselect$acno)
robust_se5_2    <- sqrt(diag(cov5_2))


tab5_4<-lm(data=mcdallselect, contestmla ~ women + z2wardvotesper + major + election + highedu + criminal+  highcases + lntotalassets +  lnage + z2wardvotesper + acno, na.action=na.exclude)
cov5_4       <- vcovCR(tab5_4,type="CR0",cluster=mcdallselect$acno)
robust_se5_4    <- sqrt(diag(cov5_4))


##FIRST TABLE
main1<-lm(data=wardac2, femalemajcand_mod ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov1m        <- vcovCR(main1,type="CR0",cluster=wardac2$w.acno)
robust_se1m    <- sqrt(diag(cov1m))
main2<-lm(data=wardac2, femalemajcandper ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov2m        <- vcovCR(main2,type="CR0",cluster=wardac2$w.acno)
robust_se2m    <- sqrt(diag(cov2m))
main3<-lm(data=wardac2, femalesmallparty_mod ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov3m        <- vcovCR(main3,type="CR0",cluster=wardac2$w.acno)
robust_se3m    <- sqrt(diag(cov3m))
main4<-lm(data=wardac2, femalesmallpartyper ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov4m        <- vcovCR(main4,type="CR0",cluster=wardac2$w.acno)
robust_se4m    <- sqrt(diag(cov4m))
main5<-lm(data=wardac2, femaleindcand_mod ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov5m        <- vcovCR(main5,type="CR0",cluster=wardac2$w.acno)
robust_se5m    <- sqrt(diag(cov5m))
main6<-lm(data=wardac2, femaleindcandper ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov6m        <- vcovCR(main6,type="CR0",cluster=wardac2$w.acno)
robust_se6m    <- sqrt(diag(cov6m))

tab2_1<-lm(data=wardac2, everpriorfmod ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov2_1       <- vcovCR(tab2_1,type="CR0",cluster=wardac2$w.acno)
robust_se2_1    <- sqrt(diag(cov2_1))
tab2_2<-lm(data=wardac2, everpriorfper ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov2_2       <- vcovCR(tab2_2,type="CR0",cluster=wardac2$w.acno)
robust_se2_2   <- sqrt(diag(cov2_2))
tab2_3<-lm(data=wardac2, everpriorfmaj ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov2_3       <- vcovCR(tab2_3,type="CR0",cluster=wardac2$w.acno)
robust_se2_3    <- sqrt(diag(cov2_3))
tab2_4<-lm(data=wardac2, everpriorfmajper ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov2_4       <- vcovCR(tab2_4,type="CR0",cluster=wardac2$w.acno)
robust_se2_4    <- sqrt(diag(cov2_4))


tab3_1<-lm(data=wardac2, ftotnewcandmajmod ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov3_1       <- vcovCR(tab3_1,type="CR0",cluster=wardac2$w.acno)
robust_se3_1    <- sqrt(diag(cov3_1))
tab3_2<-lm(data=wardac2, femalerecontesting_majmod ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov3_2       <- vcovCR(tab3_2,type="CR0",cluster=wardac2$w.acno)
robust_se3_2   <- sqrt(diag(cov3_2))
tab3_3<-lm(data=wardac2, femalerecontest_incmaj ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov3_3       <- vcovCR(tab3_3,type="CR0",cluster=wardac2$w.acno)
robust_se3_3    <- sqrt(diag(cov3_3))
tab3_4<-lm(data=wardac2, fprior_rec_maj ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov3_4       <- vcovCR(tab3_4,type="CR0",cluster=wardac2$w.acno)
robust_se3_4    <- sqrt(diag(cov3_4))
tab3_5<-lm(data=wardac2, femalerecontestingcand ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov3_5       <- vcovCR(tab3_5,type="CR0",cluster=wardac2$w.acno)
robust_se3_5    <- sqrt(diag(cov3_5))

#only keep data where turnout is available for the turnout analysis
wardac2turnout<-subset(wardac2, is.na(wardac2$turnout)==FALSE)
tab4_1<-lm(data=wardac2turnout, turnout ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov4_1       <- vcovCR(tab4_1,type="CR0",cluster=wardac2turnout$w.acno)
robust_se4_1    <- sqrt(diag(cov4_1))
tab4_2<-lm(data=wardac2, femalevoteshare ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov4_2       <- vcovCR(tab4_2,type="CR0",cluster=wardac2$w.acno)
robust_se4_2   <- sqrt(diag(cov4_2))
tab4_3<-lm(data=wardac2, femalewin ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov4_3       <- vcovCR(tab4_3,type="CR0",cluster=wardac2$w.acno)
robust_se4_3    <- sqrt(diag(cov4_3))
tab4_4<-lm(data=wardac2, femaleincumbentwins ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov4_4       <- vcovCR(tab4_4,type="CR0",cluster=wardac2$w.acno)
robust_se4_4    <- sqrt(diag(cov4_4))
tab4_5<-lm(data=wardac2, femaletop3cand ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov4_5       <- vcovCR(tab4_5,type="CR0",cluster=wardac2$w.acno)
robust_se4_5    <- sqrt(diag(cov4_5))
tab4_6<-lm(data=wardac2, femaletop5cand ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov4_6       <- vcovCR(tab4_6,type="CR0",cluster=wardac2$w.acno)
robust_se4_6    <- sqrt(diag(cov4_6))

########################################################################
########################################################################
########################################################################
# TABLE 1
stargazer(tab5_1,tab5_3,tab5_2,tab5_4,
          se = list(robust_se5_1,robust_se5_3,robust_se5_2,robust_se5_4), 
          #column.labels   = c("Men respondents", "Women respondents", "Men respondents", "Women respondents", "Men respondents", "Women respondents"),
          omit.stat = c("rsq", "f","adj.rsq","ser"),
          report="vc*sp",
          type="text",
          omit = c("Constant","acno","election","z2wardvotesper","major","highedu","criminal","highcases","lntotalassets","lnage","z2wardvotesper"),
          covariate.labels = c("Women","Voteshare % (std.)","Major party candidate","Highly educated","Criminal allegations","High number of criminal allegations","Total assets (ln)","Age (ln)"),
          # column.labels   = c("", "Open seat- women", "Open seat- men", "Open seat- man/ woman pair"),
          style = "apsr",digits=3,digits.extra = 0, out="4_Output/Maintable1.txt")

# TABLE 3
stargazer(main1,main2,main3,main4,main5,main6,
          se = list(robust_se1m,robust_se2m,robust_se3m,robust_se4m,robust_se5m,robust_se6m), 
          #column.labels   = c("Men respondents", "Women respondents", "Men respondents", "Women respondents", "Men respondents", "Women respondents"),
          omit.stat = c("rsq", "f","adj.rsq","ser"),
          report="vc*sp",
          type="text",
          omit = c("w.acno","Year", "Constant"),
          style = "apsr",digits=3,digits.extra = 0,
          column.labels   = c("Secures nomination", "% secures nomination","Secures nomination", "% secures nomination","Run as independents", "% run as independents"),
          title            = "More women secure major party nomintions where women have greater local control",
          covariate.labels = c("Number of reserved local seats"),
          add.lines = list(c("Baseline mean",
                             round(mean(wardac2$femalemajcand_mod[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femalemajcandper[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femalesmallparty_mod[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femalesmallpartyper[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femaleindcand_mod[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femaleindcandper[wardac2$w.reswomen==1]),3)))
          , out="4_Output/Maintable3.txt")

# TABLE 4
stargazer(tab2_1,tab2_2,tab2_3,tab2_4,
          se = list(robust_se2_1,robust_se2_2,robust_se2_3,robust_se2_4), 
          #column.labels   = c("Men respondents", "Women respondents", "Men respondents", "Women respondents", "Men respondents", "Women respondents"),
          omit.stat = c("rsq", "f","adj.rsq","ser"),
          report="vc*sp",
          type="text",
          omit = c("w.acno","Year", "Constant"),
          style = "apsr",digits=3,digits.extra = 0,
          add.lines = list(c("Baseline mean",round(mean(wardac2$everpriorfmod[wardac2$w.reswomen==1]),3),round(mean(wardac2$everpriorfper[wardac2$w.reswomen==1]),3),round(mean(wardac2$everpriorfmaj[wardac2$w.reswomen==1]),3),round(mean(wardac2$everpriorfmajper[wardac2$w.reswomen==1]),3))),
          column.labels   = c("Candidate runs", "% candidate runs", "Secures major party nomination", "% secures major party nomination"),
          title            = "Local woman candidate runs and secures party nominations in state elections",
          covariate.labels = c("Number of reserved local seats"),
          dep.var.caption  = "",
          dep.var.labels   = c("","","",""), out="4_Output/Maintable4.txt")


# TABLE 5
stargazer(tab3_1,tab3_5,tab3_2,tab3_3,
          se = list(robust_se3_1,robust_se3_5,robust_se3_2,robust_se3_3), 
          omit.stat = c("rsq", "f","adj.rsq","ser"),
          # star.char = c( "*", "**", "***"),
          # star.cutoffs = c(0.1, 0.05, 0.01),
          report="vc*sp",
          type="text",
          omit = c("w.acno","Year", "Constant"),
          style = "apsr",digits=3,digits.extra = 0,
          add.lines = list(c("Baseline mean",round(mean(wardac2$ftotnewcandmajmod[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femalerecontestingcand[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femalerecontesting_majmod[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femalerecontest_incmaj[wardac2$w.reswomen==1]),3))),
          column.labels   = c("New state candidate", "All recontesting candidates" , "All major party recontestants", "State incumbent"),
          title            = "Female state candidates re-run on major party nomination",
          covariate.labels = c("Number of reserved local seats"),
          dep.var.caption  = "",
          dep.var.labels   = c("","","",""), out="4_Output/Maintable5.txt")

# TABLE 6
stargazer(tab4_1,tab4_2,tab4_3,tab4_4,tab4_5,tab4_6,
          se = list(robust_se4_1,robust_se4_2,robust_se4_3,robust_se4_4,robust_se4_5,robust_se4_6), 
          #column.labels   = c("Men respondents", "Women respondents", "Men respondents", "Women respondents", "Men respondents", "Women respondents"),
          omit.stat = c("rsq", "f","adj.rsq","ser"),
          report="vc*sp",
          type="text",
          omit = c("w.acno","Year", "Constant"),
          column.labels   = c("Turnout", "Women's vote share" , "Any woman wins","Woman incumbent wins", "Woman in top 3", "Women in top 5"),
          title            = "More women control local politics, more votes for women in state elections",
          covariate.labels = c("Number of reserved local seats"),
          dep.var.caption  = "",
          dep.var.labels   = c("","","","","","",""),
          add.lines = list(c("Baseline mean",
                             round(mean(wardac2turnout$turnout[wardac2turnout$w.reswomen==1]),3),
                             round(mean(wardac2$femalevoteshare[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femalewin[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femaleincumbentwins[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femaletop3cand[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femaletop5cand[wardac2$w.reswomen==1]),3))),
          style = "apsr",digits=3,digits.extra = 0, out="4_Output/Maintable6.txt")
################################################################################
################################################################################

################################################################################
#load required data sets
load("2_ProcessedData/wardac2023.RData")
ward<-wardac2
################################################################################
#Create a new dataframe for graph
party <- c("Total","Total","Total","Total","Total")
gender <- c('Women', 'Women', 'Women', 'Women',"Women")
background <- c('Local','State','New','Local+State',"Total")
number <- c(sum(ward$everpriorf)-sum(ward$fprior_rec),sum(ward$femalerecontesting)-sum(ward$fprior_rec), sum(ward$ftotnewcand), sum(ward$fprior_rec),sum(ward$nfemalecand) )
# Join the variables to create a data frame
f_total <- data.frame(party,gender,background,number)

party <- c("Major parties","Major parties","Major parties","Major parties","Major parties")
gender <- c('Women', 'Women', 'Women', 'Women',"Women")
background <- c('Local','State','New','Local+State',"Total")
number <- c(sum(ward$everpriorfmaj)-sum(ward$fprior_rec_maj),sum(ward$femalerecontesting_maj)-sum(ward$fprior_rec_maj), sum(ward$ftotnewcandmaj), sum(ward$fprior_rec_maj),sum(ward$femalemajcand))

################################################################################
# Join the variables to create a data frame
f_major <- data.frame(party,gender,background,number)

party <- c("Small parties or Independents","Small parties or Independents","Small parties or Independents","Small parties or Independents","Small parties or Independents")
gender <- c('Women', 'Women', 'Women', 'Women',"Women")
background <- c('Local','State','New','Local+State',"Total")
number <- c(sum(ward$everpriorfnonmaj)-sum(ward$fprior_rec_nonmaj),sum(ward$femalerecontesting_nonmaj)-sum(ward$fprior_rec_nonmaj), sum(ward$ftotnewcandnonmaj), sum(ward$fprior_rec_nonmaj),sum(ward$femalenonmajcand) )

################################################################################
# Join the variables to create a data frame
f_nonmajor <- data.frame(party,gender,background,number)

party <- c("Total","Total","Total","Total","Total")
gender <- c('Men', 'Men', 'Men', 'Men',"Men")
background <- c('Local','State','New','Local+State',"Total")
number <- c(sum(ward$everpriorm)-sum(ward$mprior_rec),sum(ward$malerecontesting)-sum(ward$mprior_rec), sum(ward$mtotnewcand), sum(ward$mprior_rec),sum(ward$nmalecand) )

################################################################################
# Join the variables to create a data frame
m_total <- data.frame(party,gender,background,number)

party <- c("Major parties","Major parties","Major parties","Major parties","Major parties")
gender <- c('Men', 'Men', 'Men', 'Men',"Men")
background <- c('Local','State','New','Local+State',"Total")
number <- c(sum(ward$everpriormmaj)-sum(ward$mprior_rec_maj),sum(ward$malerecontesting_maj)-sum(ward$mprior_rec_maj), sum(ward$mtotnewcandmaj), sum(ward$mprior_rec_maj),sum(ward$malemajcand))


################################################################################
# Join the variables to create a data frame
m_major <- data.frame(party,gender,background,number)

party <- c("Small parties or Independents","Small parties or Independents","Small parties or Independents","Small parties or Independents","Small parties or Independents")
gender <- c('Men', 'Men', 'Men', 'Men',"Men")
background <- c('Local','State','New','Local+State',"Total")
number <- c(sum(ward$everpriormnonmaj)-sum(ward$mprior_rec_nonmaj),sum(ward$malerecontesting_nonmaj)-sum(ward$mprior_rec_nonmaj), sum(ward$mtotnewcandnonmaj), sum(ward$mprior_rec_nonmaj),sum(ward$malenonmajcand) )

################################################################################
# Join the variables to create a data frame
m_nonmajor <- data.frame(party,gender,background,number)

final<-rbind(f_total,f_major,f_nonmajor, m_total,m_major,m_nonmajor)
final<-subset(final, final$party!="Total" & final$background!="Total")

final<-final %>% group_by(gender)  %>% mutate(total=sum(number))

final$percat<-round(((final$number*100)/final$total),2)

final$Background<-NA
final$Background[final$background=="Local"]<-1
final$Background[final$background=="Local+State"]<-2
final$Background[final$background=="State"]<-3
final$Background[final$background=="New"]<-4
final$Background <- factor(final$Background, labels = c("Local","Local+State","State","New"))


################################################################################
ggplot(data=final, aes(x=party, y=percat, fill=Background)) + 
  geom_bar(stat="identity") + 
  theme_classic() + theme(axis.text.x = element_text(size=16),axis.ticks.x =element_blank(),
                          axis.text.y = element_text(size=16)) +
  labs(y="",x="",title="")+
  scale_y_continuous(limits = c(0,90), breaks=seq(0,90,10)) +
  scale_x_discrete(labels = function(x) str_wrap(x, width = 15))+
  facet_grid(.~gender ,  space="free_x", scales="free_x")+
  labs(x="",title="")+
  ylab("Percentage of candidates")+
  theme(axis.title.y = element_text(size=16))+
  theme(axis.text.x = element_text(size=16,angle=0),
        axis.text.y = element_text(size=16,angle=0))+
  theme(legend.title=element_text(size=16),legend.text=element_text(size=16),legend.position = "bottom")+
  theme(strip.text.x = element_text(size=16))+
  theme(strip.text.y = element_text(size=16))+
  theme(strip.background =element_rect(fill="#FFFFFF"))+
  theme(panel.grid.major = element_blank(), panel.grid.minor = element_blank(),
        panel.background = element_blank(), axis.line = element_line(colour = "black"))+
  scale_fill_grey(start = 0.1, end = .8)
ggsave(filename = "4_Output/Figure1.pdf",width = 9, height = 7, dpi = 300, units = "in", device='pdf')
################################################################################
################################################################################

################################################################################
################################################################################
#load required datasets
ac<-read.csv("1_RawData/TCPD_GE_Delhi_2020-2-23.csv")
ac<-subset(ac, Year>=2008 & Poll_No==0)

ac$resur[is.na(ac$Recontest)==FALSE]<-0
ac$resur[ac$Recontest==TRUE]<-1

ac$turncoatnew[is.na(ac$Turncoat)==FALSE]<-0
ac$turncoatnew[ac$Turncoat==TRUE]<-1

ac$reincum[is.na(ac$Incumbent)==FALSE]<-0
ac$reincum[ac$Incumbent==TRUE & is.na(ac$Recontest)==FALSE]<-1

ac$femalecand[ac$Sex=="M"]<-0
ac$femalecand[ac$Sex=="F"]<-1

ac$majcand<-0
ac$majcand[ac$Party=="AAP"| ac$Party=="BJP"| ac$Party=="INC"| ac$Party=="AAAP"]<-1

ac$partytype<-"Small"
ac$partytype[ac$Party=="AAP"| ac$Party=="AAAP"]<-"AAP"
ac$partytype[ac$Party=="BJP"]<-"BJP"
ac$partytype[ac$Party=="INC"]<-"INC"
ac$partytype[ac$Party=="IND"]<-"Independent"

################################################################################
# retain incumbents
incumbent<-subset(ac, ac$Position==1)

################################################################################
#  retain major parties only
acmajor<-subset(ac, ac$Party=="AAP"| ac$Party=="AAAP"|ac$Party=="BJP"| ac$Party=="INC")

################################################################################
# MODELS
olsmodel_maj<-lm(data=acmajor, resur~femalecand+as.factor(Year)+as.factor(acmajor$Constituency_No))
olsmodel_maj1     <- vcovCR(olsmodel_maj,type="CR0",cluster=as.factor(acmajor$Constituency_No))
robust_se_maj1  <- sqrt(diag(olsmodel_maj1))

olsmodel<-lm(data=ac, resur~femalecand+as.factor(Year)+as.factor(ac$Constituency_No))
cov1     <- vcovCR(olsmodel,type="CR0",cluster=as.factor(ac$Constituency_No))
robust_se    <- sqrt(diag(cov1))

olsmodel2<-lm(data=incumbent, resur~femalecand +as.factor(Year)+as.factor(incumbent$Constituency_No))
cov2     <- vcovCR(olsmodel2,type="CR0",cluster=as.factor(incumbent$Constituency_No))
robust_ac2    <- sqrt(diag(cov2))


# TABLE 2
stargazer(olsmodel,olsmodel_maj, olsmodel2,
          se = list(robust_se,robust_se_maj1, robust_ac2), 
          report="vc*sp",
          omit.stat = c("rsq", "f","adj.rsq","ser"),
          type="text",
          omit = c("Constituency_No", "Constant","Year"),
          style = "apsr",digits=3,digits.extra = 0,
          add.lines = list(c("Mean survival rates",
                             round(mean(ac$resur),3),round(mean(acmajor$resur),3),
                             round(mean(incumbent$resur),3)
          )),
          column.labels   = c("Candidates", "Major party candidates", "Incumbents"),
          title            = "Gender gap in political survival in state elections",
          covariate.labels = c("Gender"),
          dep.var.caption  = "",
          dep.var.labels   = c("",""), out="4_Output/Maintable2.txt")

################################################################################
################################################################################
################################################################################

################################################################################
#load required data sets
load("1_RawData/ActivistSurveyData.RData")

################################################################################
#aggregate dataset
x<-alldata %>%
  group_by(interviewparty, woman) %>%
  summarize(n())
x$woman[x$woman==1]<-"Women"
x$woman[x$woman==0]<-"Men"
x$woman<-as.factor(x$woman)
colnames(x)<-c("party","woman","freq")

################################################################################
#generate graph
ggplot(x, aes(x=woman, y=freq)) +
  geom_bar(stat="identity", aes(fill = woman), position = "dodge")+
  theme_classic()+
  facet_grid(. ~ party,  scales = "free", space = "free")+
  #scale_fill_grey(start=0.1, end=0.9)+
  scale_y_continuous(breaks=c(0,50,100,150,200,250,300,350,400), limits = c(0,400))+
 # scale_fill_manual(values=wes_palette("Moonrise3"))+
  #geom_text(aes(label=Freq), color="black", size=2)+
  theme(axis.text.x = element_text(size=rel(1),angle = 0, hjust = 0.5, vjust=0.5))+
  theme(legend.title=element_blank())+
  ylab("N party activists (municipal-level)") +
  xlab(" ")+theme(legend.position="none")
ggsave("4_Output/FigureA2.pdf",width = 6, height = 3, dpi = 300, units = "in", device='pdf')
################################################################################
################################################################################

################################################################################
#load required data sets
load("2_ProcessedData/acmajor.RData")
load("2_ProcessedData/mcdallselect.RData")

################################################################################
#remove missing and nan rows
mcd<-na.omit(mcdallselect)
mcd<-mcd[is.finite(mcd$lntotalassets) & is.finite(mcd$lnage), ]

mcd<-mcd[,c("acno", "women","election","commonname","highedu","criminal","age","lntotalassets","wardvotesper","mov","scres","muslim","sccand","obc","forward","contestmla","majormla","majormla2","major")]
mcd<-as.data.frame(mcd)
mcd1<-subset(mcd, women==1)
mcd1<-mcd1[,c("contestmla","majormla2","highedu","criminal","age","lntotalassets","wardvotesper","mov","scres","forward","sccand","obc","muslim")]

ac<-acmajor[,c("progress","highedu","criminal","age","lntotalassets","votes","margin","scres","caste_forward","caste_sc","caste_obc","caste_muslim")]
ac<-as.data.frame(ac)


################################################################################################
################################################################################################
################################################################################################
mcdwomen<-subset(mcd, women==1)
mcdmen<-subset(mcd, women==0)

##which type of women progerss upwards? RUN models

tab6_1<-lm(data=mcdwomen, contestmla ~ election + acno  + major  + wardvotesper + mov +criminal + highedu + age + lntotalassets   + muslim  + sccand + obc, na.action=na.exclude)
cov6_1       <- vcovCR(tab6_1,type="CR0",cluster=mcdwomen$acno)
robust_se6_1    <- sqrt(diag(cov6_1))

tab6_2<-lm(data=mcdwomen, majormla2 ~ election + acno   + major   + wardvotesper + mov +criminal + highedu + age + lntotalassets + muslim  + sccand + obc, na.action=na.exclude)
cov6_2      <- vcovCR(tab6_2,type="CR0",cluster=mcdwomen$acno)
robust_se6_2    <- sqrt(diag(cov6_2))

#olsmodel_maj<-lm(data=acmajor, progress~as.factor(Year)+as.factor(Constituency_No)+ majcand+Vote_Share_Percentage+Margin_Percentage+ criminal + highedu + lnage+lntotalassets+caste_muslim+ caste_sc+ caste_obc)
olsmodel_maj<-lm(data=acmajor, progress~as.factor(Year)+as.factor(Constituency_No)+ majcand+votes+margin+ criminal + highedu + lnage+lntotalassets+caste_muslim+ caste_sc+ caste_obc)
######################################################
######################################################
######################################################
##summary tables of backgrounds of women in politics
################################################################################
#TABLE A4
stargazer(mcd1, type="text" , covariate.labels = c("Contest state election", "Contest state election on major party nomination", "Graduate and above educated", "Criminal allegation",
                                                   "Age", "Log total assets", "Voteshare", "Margin of victory", "SC reservation","Forward caste","Scheduled caste","Other backward caste","Muslim"), out="4_Output/AppendixTable_A4.txt")
################################################################################
#TABLE A5
stargazer(ac, type="text", covariate.labels = c("Recontest state election","Graduate and above educated", "Criminal allegation",
                                                "Age", "Log total assets", "Voteshare", "Margin of victory", "SC reservation","Forward caste","Scheduled caste","Other backward caste","Muslim"), out="4_Output/AppendixTable_A5.txt")



################################################################################
# TABLE A6
stargazer(tab6_1,tab6_2,
          se = list(robust_se6_1,robust_se6_2), 
          #column.labels   = c("Men respondents", "Women respondents", "Men respondents", "Women respondents", "Men respondents", "Women respondents"),
          omit.stat = c("rsq", "f","adj.rsq","ser"),
          report="vc*sp",
          type="text",
          omit = c("Constant","acno","election"),
          covariate.labels = c("Holds major party nomination in local politics","Voteshare %","Margin of victory","Criminal allegations","Highly educated","Age","Total assets (ln)","Muslim (ref. Forward caste)","SC (ref. Forward caste)","OBC (ref. Forward caste)"),
          column.labels   = c("Contest state elections", "Contest state elections on major party nomination"),
          style = "apsr",digits=3,digits.extra = 0, out="4_Output/AppendixTable_A6.txt")


################################################################################
## TABLE A7
stargazer(olsmodel_maj,
          #se = list(robust_se,robust_se_maj1, robust_ac2), 
          report="vc*sp",
          omit.stat = c("rsq", "f","adj.rsq","ser"),
          type="text",
          omit = c("Constituency_No", "Constant","Year"),
          style = "apsr",digits=3,digits.extra = 0,
          column.labels   = c("Dependent variable: Woman recontests state elections.."),
          title            = "",
          covariate.labels = c("Holds major party nomination","Voteshare %","Margin of victory","Criminal allegations","Highly educated","Age (ln)","Total assets (ln)","Muslim (ref. Forward caste)","SC (ref. Forward caste)","OBC (ref. Forward caste)"),
          dep.var.caption  = "",
          dep.var.labels   = c("",""), out="4_Output/AppendixTable_A7.txt")

################################################################################
################################################################################

################################################################################
#load required data sets
load("2_ProcessedData/wardac2023.RData")

################################################################################
#keep only 4 wards as per main results stratification
wardac2<-subset(wardac2,wardac2$w.nwards==4)
wardac2$w.acno<-as.factor(wardac2$w.acno)
wardac2$Year<-as.factor(wardac2$Year)
################################################################################
## MODELS
main1<-lm(data=wardac2, femalemajcand_mod ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov1m        <- vcovCR(main1,type="CR0",cluster=wardac2$w.acno)
robust_se1m    <- sqrt(diag(cov1m))
main2<-lm(data=wardac2, femalemajcandper ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov2m        <- vcovCR(main2,type="CR0",cluster=wardac2$w.acno)
robust_se2m    <- sqrt(diag(cov2m))
main3<-lm(data=wardac2, femalesmallparty_mod ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov3m        <- vcovCR(main3,type="CR0",cluster=wardac2$w.acno)
robust_se3m    <- sqrt(diag(cov3m))
main4<-lm(data=wardac2, femalesmallpartyper ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov4m        <- vcovCR(main4,type="CR0",cluster=wardac2$w.acno)
robust_se4m    <- sqrt(diag(cov4m))
main5<-lm(data=wardac2, femaleindcand_mod ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov5m        <- vcovCR(main5,type="CR0",cluster=wardac2$w.acno)
robust_se5m    <- sqrt(diag(cov5m))
main6<-lm(data=wardac2, femaleindcandper ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov6m        <- vcovCR(main6,type="CR0",cluster=wardac2$w.acno)
robust_se6m    <- sqrt(diag(cov6m))


tab2_1<-lm(data=wardac2, everpriorfmod ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov2_1       <- vcovCR(tab2_1,type="CR0",cluster=wardac2$w.acno)
robust_se2_1    <- sqrt(diag(cov2_1))
tab2_2<-lm(data=wardac2, everpriorfper ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov2_2       <- vcovCR(tab2_2,type="CR0",cluster=wardac2$w.acno)
robust_se2_2   <- sqrt(diag(cov2_2))
tab2_3<-lm(data=wardac2, everpriorfmaj ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov2_3       <- vcovCR(tab2_3,type="CR0",cluster=wardac2$w.acno)
robust_se2_3    <- sqrt(diag(cov2_3))
tab2_4<-lm(data=wardac2, everpriorfmajper ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov2_4       <- vcovCR(tab2_4,type="CR0",cluster=wardac2$w.acno)
robust_se2_4    <- sqrt(diag(cov2_4))

tab3_1<-lm(data=wardac2, ftotnewcandmajmod ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov3_1       <- vcovCR(tab3_1,type="CR0",cluster=wardac2$w.acno)
robust_se3_1    <- sqrt(diag(cov3_1))
tab3_2<-lm(data=wardac2, femalerecontesting_majmod ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov3_2       <- vcovCR(tab3_2,type="CR0",cluster=wardac2$w.acno)
robust_se3_2   <- sqrt(diag(cov3_2))
tab3_3<-lm(data=wardac2, femalerecontest_incmaj ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov3_3       <- vcovCR(tab3_3,type="CR0",cluster=wardac2$w.acno)
robust_se3_3    <- sqrt(diag(cov3_3))
tab3_4<-lm(data=wardac2, fprior_rec_maj ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov3_4       <- vcovCR(tab3_4,type="CR0",cluster=wardac2$w.acno)
robust_se3_4    <- sqrt(diag(cov3_4))
tab3_5<-lm(data=wardac2, femalerecontestingcand ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov3_5       <- vcovCR(tab3_5,type="CR0",cluster=wardac2$w.acno)
robust_se3_5    <- sqrt(diag(cov3_5))

#only keep data where turnout is available for the turnout analysis
wardac2turnout<-subset(wardac2, is.na(wardac2$turnout)==FALSE)

tab4_1<-lm(data=wardac2turnout, turnout ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov4_1       <- vcovCR(tab4_1,type="CR0",cluster=wardac2turnout$w.acno)
robust_se4_1    <- sqrt(diag(cov4_1))
tab4_2<-lm(data=wardac2, femalevoteshare ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov4_2       <- vcovCR(tab4_2,type="CR0",cluster=wardac2$w.acno)
robust_se4_2   <- sqrt(diag(cov4_2))
tab4_3<-lm(data=wardac2, femalewin ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov4_3       <- vcovCR(tab4_3,type="CR0",cluster=wardac2$w.acno)
robust_se4_3    <- sqrt(diag(cov4_3))
tab4_4<-lm(data=wardac2, femaleincumbentwins ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov4_4       <- vcovCR(tab4_4,type="CR0",cluster=wardac2$w.acno)
robust_se4_4    <- sqrt(diag(cov4_4))
tab4_5<-lm(data=wardac2, femaletop3cand ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov4_5       <- vcovCR(tab4_5,type="CR0",cluster=wardac2$w.acno)
robust_se4_5    <- sqrt(diag(cov4_5))
tab4_6<-lm(data=wardac2, femaletop5cand ~ as.factor(w.reswomen) + w.acno + Year, na.action=na.exclude)
cov4_6       <- vcovCR(tab4_6,type="CR0",cluster=wardac2$w.acno)
robust_se4_6    <- sqrt(diag(cov4_6))



## TABLES

stargazer(main1,main2,main3,main4,main5,main6,
          se = list(robust_se1m,robust_se2m,robust_se3m,robust_se4m,robust_se5m,robust_se6m), 
          #column.labels   = c("Men respondents", "Women respondents", "Men respondents", "Women respondents", "Men respondents", "Women respondents"),
          omit.stat = c("rsq", "f","adj.rsq","ser"),
          report="vc*sp",
          type="text",
          omit = c("w.acno","Year", "Constant"),
          style = "apsr",digits=3,digits.extra = 0,
          column.labels   = c("Secures nomination", "% secures nomination","Secures nomination", "% secures nomination","Run as independents", "% run as independents"),
          title            = "More women secure major party nomintions where women have greater local control",
          covariate.labels = c("2 reserved seats out of 4","3 reserved seats out of 4"),
          add.lines = list(c("Baseline mean",
                             round(mean(wardac2$femalemajcand_mod[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femalemajcandper[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femalesmallparty_mod[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femalesmallpartyper[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femaleindcand_mod[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femaleindcandper[wardac2$w.reswomen==1]),3)
          )), out="4_Output/AppendixTable_A12.txt")

stargazer(tab2_1,tab2_2,tab2_3,tab2_4,
          se = list(robust_se2_1,robust_se2_2,robust_se2_3,robust_se2_4), 
          #column.labels   = c("Men respondents", "Women respondents", "Men respondents", "Women respondents", "Men respondents", "Women respondents"),
          omit.stat = c("rsq", "f","adj.rsq","ser"),
          report="vc*sp",
          type="text",
          omit = c("w.acno","Year", "Constant"),
          style = "apsr",digits=3,digits.extra = 0,
          add.lines = list(c("Baseline mean",round(mean(wardac2$everpriorfmod[wardac2$w.reswomen==1]),3),round(mean(wardac2$everpriorfper[wardac2$w.reswomen==1]),3),round(mean(wardac2$everpriorfmaj[wardac2$w.reswomen==1]),3),round(mean(wardac2$everpriorfmajper[wardac2$w.reswomen==1]),3))),
          column.labels   = c("Candidate runs", "% candidate runs", "Secures major party nomination", "% secures major party nomination"),
          title            = "Local woman candidate runs and secures party nominations in state elections",
          covariate.labels = c("2 reserved seats out of 4","3 reserved seats out of 4"),
          dep.var.caption  = "",
          dep.var.labels   = c("","","",""), out="4_Output/AppendixTable_A13.txt")


stargazer(tab3_1,tab3_5,tab3_2,tab3_3,
          se = list(robust_se3_1,robust_se3_5,robust_se3_2,robust_se3_3), 
          omit.stat = c("rsq", "f","adj.rsq","ser"),
          # star.char = c( "*", "**", "***"),
          # star.cutoffs = c(0.1, 0.05, 0.01),
          report="vc*sp",
          type="text",
          omit = c("w.acno","Year", "Constant"),
          style = "apsr",digits=3,digits.extra = 0,
          add.lines = list(c("Baseline mean",round(mean(wardac2$ftotnewcandmajmod[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femalerecontestingcand[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femalerecontesting_majmod[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femalerecontest_incmaj[wardac2$w.reswomen==1]),3))),
          column.labels   = c("New state candidate", "All recontesting candidates" , "All major party recontestants", "State incumbent"),
          title            = "Female state candidates re-run on major party nomination",
          covariate.labels = c("2 reserved seats out of 4","3 reserved seats out of 4"),
          dep.var.caption  = "",
          dep.var.labels   = c("","","",""), out="4_Output/AppendixTable_A14.txt")

stargazer(tab4_1,tab4_2,tab4_3,tab4_4,tab4_5,tab4_6,
          se = list(robust_se4_1,robust_se4_2,robust_se4_3,robust_se4_4,robust_se4_5,robust_se4_6), 
          #column.labels   = c("Men respondents", "Women respondents", "Men respondents", "Women respondents", "Men respondents", "Women respondents"),
          omit.stat = c("rsq", "f","adj.rsq","ser"),
          report="vc*sp",
          type="text",
          omit = c("w.acno","Year", "Constant"),
          column.labels   = c("Turnout", "Women's vote share" , "Any woman wins","Woman incumbent wins", "Woman in top 3", "Women in top 5"),
          title            = "More women control local politics, more votes for women in state elections",
          covariate.labels = c("2 reserved seats out of 4","3 reserved seats out of 4"),
          dep.var.caption  = "",
          dep.var.labels   = c("","","","","","",""),
          style = "apsr",digits=3,digits.extra = 0, out="4_Output/AppendixTable_A15.txt")


########################################################################################
########################################################################################

load("2_ProcessedData/wardac2023.RData")

################################################################################
#keep only 4 wards as per main results stratification and exclude 2020
wardac2<-subset(wardac2,wardac2$w.nwards==4  & wardac2$Year!=2020)
wardac2$w.acno<-as.factor(wardac2$w.acno)
wardac2$Year<-as.factor(wardac2$Year)
########################################################################
########################################################################
########################################################################

# MODELS
##FIRST TABLE
main1<-lm(data=wardac2, femalemajcand_mod ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov1m        <- vcovCR(main1,type="CR0",cluster=wardac2$w.acno)
robust_se1m    <- sqrt(diag(cov1m))
main2<-lm(data=wardac2, femalemajcandper ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov2m        <- vcovCR(main2,type="CR0",cluster=wardac2$w.acno)
robust_se2m    <- sqrt(diag(cov2m))
main3<-lm(data=wardac2, femalesmallparty_mod ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov3m        <- vcovCR(main3,type="CR0",cluster=wardac2$w.acno)
robust_se3m    <- sqrt(diag(cov3m))
main4<-lm(data=wardac2, femalesmallpartyper ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov4m        <- vcovCR(main4,type="CR0",cluster=wardac2$w.acno)
robust_se4m    <- sqrt(diag(cov4m))
main5<-lm(data=wardac2, femaleindcand_mod ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov5m        <- vcovCR(main5,type="CR0",cluster=wardac2$w.acno)
robust_se5m    <- sqrt(diag(cov5m))
main6<-lm(data=wardac2, femaleindcandper ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov6m        <- vcovCR(main6,type="CR0",cluster=wardac2$w.acno)
robust_se6m    <- sqrt(diag(cov6m))

tab2_1<-lm(data=wardac2, everpriorfmod ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov2_1       <- vcovCR(tab2_1,type="CR0",cluster=wardac2$w.acno)
robust_se2_1    <- sqrt(diag(cov2_1))
tab2_2<-lm(data=wardac2, everpriorfper ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov2_2       <- vcovCR(tab2_2,type="CR0",cluster=wardac2$w.acno)
robust_se2_2   <- sqrt(diag(cov2_2))
tab2_3<-lm(data=wardac2, everpriorfmaj ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov2_3       <- vcovCR(tab2_3,type="CR0",cluster=wardac2$w.acno)
robust_se2_3    <- sqrt(diag(cov2_3))
tab2_4<-lm(data=wardac2, everpriorfmajper ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov2_4       <- vcovCR(tab2_4,type="CR0",cluster=wardac2$w.acno)
robust_se2_4    <- sqrt(diag(cov2_4))


tab3_1<-lm(data=wardac2, ftotnewcandmajmod ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov3_1       <- vcovCR(tab3_1,type="CR0",cluster=wardac2$w.acno)
robust_se3_1    <- sqrt(diag(cov3_1))
tab3_2<-lm(data=wardac2, femalerecontesting_majmod ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov3_2       <- vcovCR(tab3_2,type="CR0",cluster=wardac2$w.acno)
robust_se3_2   <- sqrt(diag(cov3_2))
tab3_3<-lm(data=wardac2, femalerecontest_incmaj ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov3_3       <- vcovCR(tab3_3,type="CR0",cluster=wardac2$w.acno)
robust_se3_3    <- sqrt(diag(cov3_3))
tab3_4<-lm(data=wardac2, fprior_rec_maj ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov3_4       <- vcovCR(tab3_4,type="CR0",cluster=wardac2$w.acno)
robust_se3_4    <- sqrt(diag(cov3_4))
tab3_5<-lm(data=wardac2, femalerecontestingcand ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov3_5       <- vcovCR(tab3_5,type="CR0",cluster=wardac2$w.acno)
robust_se3_5    <- sqrt(diag(cov3_5))


#only keep data where turnout is available for the turnout analysis
wardac2turnout<-subset(wardac2, is.na(wardac2$turnout)==FALSE)

tab4_1<-lm(data=wardac2turnout, turnout ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov4_1       <- vcovCR(tab4_1,type="CR0",cluster=wardac2turnout$w.acno)
robust_se4_1    <- sqrt(diag(cov4_1))
tab4_2<-lm(data=wardac2, femalevoteshare ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov4_2       <- vcovCR(tab4_2,type="CR0",cluster=wardac2$w.acno)
robust_se4_2   <- sqrt(diag(cov4_2))
tab4_3<-lm(data=wardac2, femalewin ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov4_3       <- vcovCR(tab4_3,type="CR0",cluster=wardac2$w.acno)
robust_se4_3    <- sqrt(diag(cov4_3))
tab4_4<-lm(data=wardac2, femaleincumbentwins ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov4_4       <- vcovCR(tab4_4,type="CR0",cluster=wardac2$w.acno)
robust_se4_4    <- sqrt(diag(cov4_4))
tab4_5<-lm(data=wardac2, femaletop3cand ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov4_5       <- vcovCR(tab4_5,type="CR0",cluster=wardac2$w.acno)
robust_se4_5    <- sqrt(diag(cov4_5))
tab4_6<-lm(data=wardac2, femaletop5cand ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov4_6       <- vcovCR(tab4_6,type="CR0",cluster=wardac2$w.acno)
robust_se4_6    <- sqrt(diag(cov4_6))

########################################################################
########################################################################
########################################################################

# TABLE 3
stargazer(main1,main2,main3,main4,main5,main6,
          se = list(robust_se1m,robust_se2m,robust_se3m,robust_se4m,robust_se5m,robust_se6m), 
          #column.labels   = c("Men respondents", "Women respondents", "Men respondents", "Women respondents", "Men respondents", "Women respondents"),
          omit.stat = c("rsq", "f","adj.rsq","ser"),
          report="vc*sp",
          type="text",
          omit = c("w.acno","Year", "Constant"),
          style = "apsr",digits=3,digits.extra = 0,
          column.labels   = c("Secures nomination", "% secures nomination","Secures nomination", "% secures nomination","Run as independents", "% run as independents"),
          title            = "More women secure major party nomintions where women have greater local control",
          covariate.labels = c("Number of reserved local seats"),
          add.lines = list(c("Baseline mean",
                             round(mean(wardac2$femalemajcand_mod[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femalemajcandper[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femalesmallparty_mod[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femalesmallpartyper[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femaleindcand_mod[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femaleindcandper[wardac2$w.reswomen==1]),3)
          )), out="4_Output/AppendixTable_A8.txt")

# TABLE 4
stargazer(tab2_1,tab2_2,tab2_3,tab2_4,
          se = list(robust_se2_1,robust_se2_2,robust_se2_3,robust_se2_4), 
          #column.labels   = c("Men respondents", "Women respondents", "Men respondents", "Women respondents", "Men respondents", "Women respondents"),
          omit.stat = c("rsq", "f","adj.rsq","ser"),
          report="vc*sp",
          type="text",
          omit = c("w.acno","Year", "Constant"),
          style = "apsr",digits=3,digits.extra = 0,
          add.lines = list(c("Baseline mean",round(mean(wardac2$everpriorfmod[wardac2$w.reswomen==1]),3),round(mean(wardac2$everpriorfper[wardac2$w.reswomen==1]),3),round(mean(wardac2$everpriorfmaj[wardac2$w.reswomen==1]),3),round(mean(wardac2$everpriorfmajper[wardac2$w.reswomen==1]),3))),
          column.labels   = c("Candidate runs", "% candidate runs", "Secures major party nomination", "% secures major party nomination"),
          title            = "Local woman candidate runs and secures party nominations in state elections",
          covariate.labels = c("Number of reserved local seats"),
          dep.var.caption  = "",
          dep.var.labels   = c("","","",""), out="4_Output/AppendixTable_A9.txt")


# TABLE 5
stargazer(tab3_1,tab3_5,tab3_2,tab3_3,
          se = list(robust_se3_1,robust_se3_5,robust_se3_2,robust_se3_3), 
          omit.stat = c("rsq", "f","adj.rsq","ser"),
          # star.char = c( "*", "**", "***"),
          # star.cutoffs = c(0.1, 0.05, 0.01),
          report="vc*sp",
          type="text",
          omit = c("w.acno","Year", "Constant"),
          style = "apsr",digits=3,digits.extra = 0,
          add.lines = list(c("Baseline mean",round(mean(wardac2$ftotnewcandmajmod[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femalerecontestingcand[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femalerecontesting_majmod[wardac2$w.reswomen==1]),3),
                             round(mean(wardac2$femalerecontest_incmaj[wardac2$w.reswomen==1]),3))),
          column.labels   = c("New state candidate", "All recontesting candidates" , "All major party recontestants", "State incumbent"),
          title            = "Female state candidates re-run on major party nomination",
          covariate.labels = c("Number of reserved local seats"),
          dep.var.caption  = "",
          dep.var.labels   = c("","","",""), out="4_Output/AppendixTable_A10.txt")

# TABLE 6
stargazer(tab4_1,tab4_2,tab4_3,tab4_4,tab4_5,tab4_6,
          se = list(robust_se4_1,robust_se4_2,robust_se4_3,robust_se4_4,robust_se4_5,robust_se4_6), 
          #column.labels   = c("Men respondents", "Women respondents", "Men respondents", "Women respondents", "Men respondents", "Women respondents"),
          omit.stat = c("rsq", "f","adj.rsq","ser"),
          report="vc*sp",
          type="text",
          omit = c("w.acno","Year", "Constant"),
          column.labels   = c("Turnout", "Women's vote share" , "Any woman wins","Woman incumbent wins", "Woman in top 3", "Women in top 5"),
          title            = "More women control local politics, more votes for women in state elections",
          covariate.labels = c("Number of reserved local seats"),
          dep.var.caption  = "",
          dep.var.labels   = c("","","","","","",""),
          style = "apsr",digits=3,digits.extra = 0, out="4_Output/AppendixTable_A11.txt")

################################################################################
################################################################################
#load required data sets
load("2_ProcessedData/wardac2023.RData")

################################################################################
#keep only 4 wards as per main results stratification
wardac2<-subset(wardac2,wardac2$w.nwards==4)
wardac2$w.acno<-as.factor(wardac2$w.acno)
wardac2$Year<-as.factor(wardac2$Year)

################################################################################
# MODELS
tab99a_5<-lm(data=wardac2, caste_forwardmajper ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov99a_5       <- vcovCR(tab99a_5,type="CR0",cluster=wardac2$w.acno)
robust_se99a_5    <- sqrt(diag(cov99a_5))

tab99a_6<-lm(data=wardac2, caste_obcmajper ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov99a_6       <- vcovCR(tab99a_6,type="CR0",cluster=wardac2$w.acno)
robust_se99a_6    <- sqrt(diag(cov99a_6))

tab99a_8<-lm(data=wardac2, caste_muslimmajper ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov99a_8       <- vcovCR(tab99a_8,type="CR0",cluster=wardac2$w.acno)
robust_se99a_8    <- sqrt(diag(cov99a_8))


tab99a_7<-lm(data=wardac2, caste_scmajper ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov99a_7       <- vcovCR(tab99a_7,type="CR0",cluster=wardac2$w.acno)
robust_se99a_7    <- sqrt(diag(cov99a_7))

tab98a_6<-lm(data=wardac2, caste_obcmajperprior ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov98a_6       <- vcovCR(tab98a_6,type="CR0",cluster=wardac2$w.acno)
robust_se98a_6    <- sqrt(diag(cov98a_6))


tab97a_6<-lm(data=wardac2, caste_obcmajperrecont ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov97a_6       <- vcovCR(tab97a_6,type="CR0",cluster=wardac2$w.acno)
robust_se97a_6    <- sqrt(diag(cov97a_6))

tab95a_6<-lm(data=wardac2, caste_obcmajpernew ~ w.reswomen + w.acno + Year, na.action=na.exclude)
cov95a_6       <- vcovCR(tab95a_6,type="CR0",cluster=wardac2$w.acno)
robust_se95a_6    <- sqrt(diag(cov95a_6))

###

stargazer(tab99a_5,tab99a_6,tab99a_7,tab99a_8,
          se = list(robust_se99a_5,robust_se99a_6,robust_se99a_7,robust_se99a_8), 
          #column.labels   = c("Men respondents", "Women respondents", "Men respondents", "Women respondents", "Men respondents", "Women respondents"),
          omit.stat = c("rsq", "f","adj.rsq","ser"),
          report="vc*sp",
          type="text",
          omit = c("w.acno","Year", "Constant"),
          column.labels   = c("Forward caste", "OBC" , "SC","Muslim"),
          title            = " ",
          covariate.labels = c("Number of reserved local  seats"),
          add.lines = list(c("Baseline mean",
                             round(mean(wardac2$caste_forwardmajper[wardac2$w.reswomen==1]),3),round(mean(wardac2$caste_obcmajper[wardac2$w.reswomen==1]),3),round(mean(wardac2$caste_scmajper[wardac2$w.reswomen==1]),3),round(mean(wardac2$caste_muslimmajper[wardac2$w.reswomen==1]),3))),
          
          style = "apsr",digits=3,digits.extra = 0, out="4_Output/AppendixTable_A16.txt")



stargazer(tab98a_6,tab97a_6,tab95a_6,
          se = list(robust_se98a_6,robust_se97a_6,robust_se95a_6), 
          #column.labels   = c("Men respondents", "Women respondents", "Men respondents", "Women respondents", "Men respondents", "Women respondents"),
          omit.stat = c("rsq", "f","adj.rsq","ser"),
          report="vc*sp",
          type="text",
          omit = c("w.acno","Year", "Constant"),
          column.labels   = c("Percent OBC major party with local experience" , "Percent OBC recontesting major party", "Percent OBC new on major party"),
          title            = "",
          covariate.labels = c("Number of reserved local  seats"),
          add.lines = list(c("Baseline mean",round(mean(wardac2$caste_obcmajperprior[wardac2$w.reswomen==1]),3),round(mean(wardac2$caste_obcmajperrecont[wardac2$w.reswomen==1]),3),round(mean(wardac2$caste_obcmajpernew[wardac2$w.reswomen==1]),3))),
          
          style = "apsr",digits=3,digits.extra = 0, out="4_Output/AppendixTable_A17.txt")

################################################################################
################################################################################
###
log_close()