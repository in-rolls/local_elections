** ssc install coefplot
**load required dataset
clear all 
**set working directory path to replication folder
cd "/Users/tg2778/Dropbox/0_Reviews_RnRs/092022_AJPS_PathwayPower/ReplicationFolder"
**start log file
log using "5_LogFiles/DataAnalysis_stata_log.log",replace
**load dataset
use "1_RawData/MunicipalCouncilSurvey.dta", replace
*label variables for dataset
label var respond "Interviewed"
label var eciparty1 "Party"
label var winnerhighedu "Highly educated"
label var resSC "SC Reserved"
label var z2winnervoteshare "Standardized vote-share"
label var z2mov "Standardized margin of victory"
label var gender1 "Female"
label var pcname2 "National constituency"
label var identifier "Unique Identifier"
*run regression
reg respond gender1 i.eciparty1 i.winnerhighedu i.resSC z2winnervoteshare z2mov i.pcname2, robust
estimates store m1

*display coefplot
coefplot (m1, msize(large)), xline(0) levels(95)  drop(_cons) ylabel(, labsize(large) notick) baselevels headings( 0.gender1={bf:Gender} 1.eciparty1={bf:Party} 0.winnerhighedu={bf:Education} 0.resSC={bf:Reservation} 1.pcname2={bf:Region}, labsize(large)) ylabel(, labsize(large) notick) scale(0.7)
graph export "4_Output/FigureA1.pdf", replace

****************************************

*clear all
import delimited "1_RawData/Municipal_TurnoutMappingResData.csv", clear 

**generate variables
encode resstatus, generate(resstatus1)
encode acname, generate(acname1)
replace eci_party1 = trim(eci_party1)
replace eci_party2 = trim(eci_party2)
encode eci_party1, generate(winnerparty)

gen indwinner = 0 
replace indwinner = 1 if eci_party1=="IND"

*keep if election<2017
gen aapwin =0
replace aapwin=1 if eci_party1=="AAP"

gen bjpwin =0
replace bjpwin=1 if eci_party1=="BJP"

gen incwin =0
replace incwin=1 if eci_party1=="INC"

tab aapwin
tab bjpwin
tab incwin

gen winnervote = (votes1*100)/totalvotes
gen femalecandper = female_cand/ncand
gen womenwin = 0 if gender1=="M"
replace womenwin=1 if gender1=="F"

gen femvoter = (female_voter*100)/tot_voter

****************************************************************************************
****************************************************************************************
****************************************************************************************

keep if election==2007|election==2012
keep bjpwin incwin femalecandper femvoter mov ncand femaleturnoutper winner_voteshare reswomen acname acno commonname pcno pcname mcdcorp election


reshape wide bjpwin incwin femalecandper femvoter mov ncand femaleturnoutper winner_voteshare reswomen, i(acname acno commonname pcno pcname mcdcorp) j(election)

label variable bjpwin2007 "BJP wins (L)"
label variable incwin2007 "INC wins (L)"
label variable mov2007 "Margin of victory (L)"
label variable ncand2007 "N candidates (L)"
label variable  femalecandper2007 "% female candidates (L)"
label variable  femvoter2007 "% female voters (L)"
label variable  femaleturnoutper2007 "Female turnout (L)"
label  variable winner_voteshare2007 "Winner voteshare (L)"
label  variable reswomen2007 "Reserved 2007 (L)"

reg  reswomen2012 bjpwin2007, robust 
estimates store m1
reg  reswomen2012 incwin2007, robust 
estimates store m2
reg  reswomen2012 mov2007, robust 
estimates store m3
reg  reswomen2012 ncand2007, robust 
estimates store m4
reg  reswomen2012 femalecandper2007, robust 
estimates store m5
reg  reswomen2012 femvoter2007, robust 
estimates store m6
reg  reswomen2012 femaleturnoutper2007, robust 
estimates store m7
reg  reswomen2012 winner_voteshare2007, robust 
estimates store m8
reg  reswomen2012 reswomen2007, robust 
estimates store m9

esttab m* using "4_Output/AppendixTable_A2.txt", replace cells(b(star fmt(3)) se(par fmt(3))) fixed wide starlevels(* 0.10 ** 0.05 *** 0.01) ///
legend label stats(  N r2_a, ///
fmt(%7.0g %7.3f))  ///
drop (_cons)

log close _all
