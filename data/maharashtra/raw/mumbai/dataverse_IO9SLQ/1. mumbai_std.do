clear
set more off
*cd "/Users/alee87/Dropbox/Mumbai-Delhi/Analysis/"
cap cd "/Users/varun/Library/CloudStorage/Dropbox/PhD/Mumbai-Delhi/CPS_Replication"
set matsize 10000


*Run mkdir lines only once

use mumbai_full.dta, clear

replace curruption=100-curruption
recode year (.=2014)
encode adminward, gen (admin_num)
replace funds_prop= total_funds/10000000 if year==2016

*gen attend_corpward=(gbm_attended+ ward_att)/(total_gbms+ total_ward_meetings)

fvset base 2018 year

*rename  
 rename availabilityofpublicgardens publicgardens
 rename availabilityofpublictransport   publictransport  
 rename hospitalsandothermedicalfaci hospitals
 rename appropriateschoolsandcolleges  schoolsandcolleges
 rename waterloggingduringrainyseaso waterlogging
rename cleanlinesssanitationfacilit cleanlinesssanitation
rename availabilityoffoodthroughrations foodthroughrations
		rename recallforparty recallforparty
	rename	recallforname	recallforname
		rename accesibility 	accesibility 
		rename satisfaction 	satisfaction 
		rename traffic traffic


	local min "genderquota i.year i.castenum "
	
	gen ward_fe = .
replace ward_fe = ward if year <2017
	
	** runup and immediate aftermath of state election
**state election year was  fall 2014 therefore 14 and 15 gender_election
	


*state election year was  fall 2014 therefore 14 and 15
gen gender_election=0
replace gender_election=1 if year==2015&genderquota==1
replace gender_election=1 if year==2014&genderquota==1





do genindex1.do 
mkdir Tables_pg_percept 

* ------------------------------------------------------------: TABLE A.3 Panel A Summary Statistics Observables:-----------------------------------------
bysort genderquota: summ pancard
bysort genderquota: summ attend_univ
bysort genderquota: tabulate criminal
bysort genderquota: summ age


eststo genderquota: quietly estpost summarize ///
	pancard attend_uni criminal age no_of_criminal_cases if genderquota == 1
eststo nongenderquota: quietly estpost summarize ///
	pancard attend_uni criminal age no_of_criminal_cases if genderquota == 0
eststo diff: quietly estpost ttest ///
	pancard attend_uni criminal age no_of_criminal_cases, by(genderquota) unequal
esttab nongenderquota genderquota diff using "./Tables_pg_percept/sumstat.tex", ///
	cells("mean(pattern(1 1 0) fmt(3)) sd(pattern(1 1 0)) b(star pattern(0 0 1) fmt(3)) t(pattern(0 0 1) par fmt(3))") label title("Summary statistics") collabels("Mean" "S.D.") mtitle( "Non Gender Quota Seats" "Gender Quota Seats" "Difference") nonum replace


	

** Two broad families
*1) Effort - Measured via ward attendance, funds disbursed, questions asked in the chamber including rhetorical questions, and ideological questions. 
*2) Outcomes - Using Opinion survey data on name recall, party recall, and pg provision conditionofroads  publicgardens publictransport  hospitals schoolsandcolleges powersupply watersupply waterlogging  instancesofcrime lawordersituation cleanlinesssanitation  accesibility satisfaction curruption




* ------------------------------------------------------------: TABLE A.3 Panel B Summary Stat Constituency Service-----------------------------------------


eststo genderquota: quietly estpost summarize ///
	conditionofroads  publicgardens traffic publictransport  hospitals schoolsandcolleges  watersupply waterlogging    cleanlinesssanitation  accesibility satisfaction curruption improvmentinlifestyle if genderquota == 1
eststo	 nongenderquota: quietly estpost summarize ///
	conditionofroads  publicgardens publictransport  hospitals schoolsandcolleges  watersupply waterlogging   cleanlinesssanitation  accesibility satisfaction curruption improvmentinlifestyle if genderquota == 0
eststo diff: quietly estpost ttest ///
	conditionofroads  publicgardens traffic publictransport  hospitals schoolsandcolleges  watersupply waterlogging   cleanlinesssanitation  accesibility satisfaction curruption improvmentinlifestyle, by(genderquota) unequal
esttab nongenderquota genderquota diff using "./Tables_pg_percept/pg_summary.tex", ///
	cells("mean(pattern(1 1 0) fmt(3)) sd(pattern(1 1 0)) b(star pattern(0 0 1) fmt(3)) t(pattern(0 0 1) par fmt(3))") label title("Summary statistics") collabels("Mean" "S.D." "b" "t") mtitle( "Non Gender Quota Seats" "Gender Quota Seats" "Difference") nonum replace

	
* ------------------------------------------------------------: TABLE A.3 Panel C Summary Stat Other Perception Measures ----------------------------------------


eststo genderquota: quietly estpost summarize ///
	    powersupply   instancesofcrime lawordersituation pollutionproblems if genderquota == 1
eststo	 nongenderquota: quietly estpost summarize ///
	powersupply   instancesofcrime lawordersituation pollutionproblems if genderquota == 0
eststo diff: quietly estpost ttest ///
	powersupply   instancesofcrime lawordersituation pollutionproblems, by(genderquota) unequal
esttab nongenderquota genderquota diff using "./Tables_pg_percept/placebo.tex", ///
	cells("mean(pattern(1 1 0) fmt(3)) sd(pattern(1 1 0)) b(star pattern(0 0 1) fmt(3)) t(pattern(0 0 1) par fmt(3))") label title("Summary statistics: PLacebo") collabels("Mean" "S.D." "b" "t") mtitle( "Non Gender Quota Seats" "Gender Quota Seats" "Difference") nonum replace



* ------------------------------------------------------------: TABLE A.3 Panel D Summary Stat Q Asked-----------------------------------------


eststo clear
eststo: quietly estpost summarize ///
    q_education q_health  q_otherinfrastructure q_pollution q_recreationcommunity  q_transport q_watertoilets q_corporation q_distribution q_housing q_humanres q_license q_renaming q_crimecorrupt q_culture
esttab using q_summary.tex, replace cells("mean(fmt(2)) sd(par fmt(2)) min max count(fmt(0))") label nodepvar  ///
title(Questions Summary\label{ques_summary})


eststo genderquota: quietly estpost summarize ///
	q_education q_health  q_otherinfrastructure q_pollution q_recreationcommunity  q_transport q_watertoilets q_corporation q_distribution q_housing q_humanres q_license q_renaming q_crimecorrupt q_culture if genderquota == 1
eststo nongenderquota: quietly estpost summarize ///
	q_education q_health  q_otherinfrastructure q_pollution q_recreationcommunity  q_transport q_watertoilets q_corporation q_distribution q_housing q_humanres q_license q_renaming q_crimecorrupt q_culture if genderquota == 0
eststo diff: quietly estpost ttest ///
	q_education q_health  q_otherinfrastructure q_pollution q_recreationcommunity  q_transport q_watertoilets q_corporation q_distribution q_housing q_humanres q_license q_renaming q_crimecorrupt q_culture, by(genderquota) unequal
esttab nongenderquota genderquota diff using "./Tables_pg_percept/q_summary.tex", ///
	cells("mean(pattern(1 1 0) fmt(2)) sd(pattern(1 1 0)) b(star pattern(0 0 1) fmt(2)) t(pattern(0 0 1) par fmt(3))") label title("Summary statistics") collabels("Mean" "S.D." "b" "t") mtitle( "Non Gender Quota Seats" "Gender Quota Seats" "Difference") nonum replace





* ------------------------------------------------------------: Table 4 Constituency Servicen-----------------------------------------
    

alpha conditionofroads  publicgardens publictransport  hospitals ///
schoolsandcolleges  watersupply waterlogging cleanlinesssanitation  ///
accesibility satisfaction curruption improvmentinlifestyle recallforname, item std
mkdir index_tables
do genindex1.do

genindex publicgardens publictransport conditionofroads   traffic   hospitals schoolsandcolleges  watersupply waterlogging    cleanlinesssanitation   curruption accesibility satisfaction  improvmentinlifestyle recallforname ,nv(pg_index)
 drop pg_indexM- n_pg_index_var
lab var pg_indexA "PG index"
lab var pg_indexA_B "PG Index-binary"


* Table 4 Panel A
		reg pg_indexA  genderquota i.year  , vce(cluster newid)
		outreg2 using "./index_tables/pg_index.tex",ctitle((1)) keep(pg_indexA  genderquota)  replace label 

		reg pg_indexA   genderquota gender_election i.year  , vce(cluster newid)
		outreg2 using "./index_tables/pg_index.tex",ctitle((2)) keep(pg_indexA  genderquota gender_election) tex(frag)  label
		
			
	
		
		
* Table 4 Panel B 
genindex conditionofroads traffic  publicgardens publictransport  hospitals schoolsandcolleges  watersupply waterlogging    cleanlinesssanitation   curruption   ,nv(pg_index_wardfe)
	drop pg_index_wardfeM- n_pg_index_wardfe_var
lab var pg_index_wardfeA "pg_index_wardfe Sans Ward FE"
lab var pg_index_wardfeA_B "pg_index_wardfe-binary"	



		reg pg_index_wardfeA  genderquota i.year i.ward_fe if year <2017, vce(cluster newid)
		outreg2 using "./index_tables/pg_index_fe.tex",ctitle((1)) keep(pg_index_wardfeA  genderquota)  replace label 

		reg pg_index_wardfeA   genderquota gender_election i.year i.ward_fe if year <2017 , vce(cluster newid)
		outreg2 using "./index_tables/pg_index_fe.tex",ctitle((4)) keep(pg_index_wardfeA  genderquota) append tex(frag)label
		
		
								

	
	
		
*: Figure 1 -----------------------------------------

mkdir graphics

foreach var of varlist conditionofroads  publicgardens publictransport  hospitals schoolsandcolleges  watersupply waterlogging    cleanlinesssanitation  accesibility satisfaction curruption improvmentinlifestyle recallforname  traffic {	
					   
		qui sum `var' if genderquota==0
		qui gen `var'_mean=r(mean)
		qui gen `var'_sd=r(sd)
		qui gen `var'_std=(`var'-`var'_mean)/`var'_sd
		drop `var'_mean `var'_sd
		}
					
*alpha conditionofroads  publicgardens publictransport  hospitals schoolsandcolleges  watersupply waterlogging    cleanlinesssanitation  accesibility satisfaction curruption improvmentinlifestyle , item std
					

* no wrd fe because Accessibility, satisfaction, recallforname and improvement in lifestyle missing for 2011
foreach var of varlist conditionofroads publicgardens publictransport ///
   traffic   hospitals schoolsandcolleges  watersupply ///
waterlogging cleanlinesssanitation curruption accesibility ///
satisfaction  improvmentinlifestyle recallforname {
quietly reg `var'_std genderquota i.year, cluster(newid)
estimates store fit_`var'
}
*ssc install grstyle
*grstyle init
*grstyle set plain, nogrid noextend 





coefplot (fit*), keep(genderquota) xline(0) asequation swapnames sort(, descending) ///
graphregion(col(white)) bgcol(white) ///
ylabel(,nogrid) xlabel(,nogrid) ///
levels(95, 90)  legend(order(1 "95% CI" 2 "90% CI")) ciopts(recast(. rcap)) ///   
			coeflabels(fit_conditionofroads = "Condition of Roads" ///
			fit_publicgardens = "Public Gardens" ///
			fit_publictransport = "Public Transport" ///
			fit_traffic = "Traffic Situation" ///
			fit_hospitals = "Hospitals" ///
			fit_schoolsandcolleges = "Schools & Colleges" ///
			fit_watersupply="Water Supply" ///
			fit_waterlogging="Water Logging" ///
			fit_cleanlinesssanitation = "Sanitation" ///
			fit_curruption="Perceived Corruption" ///
			fit_accesibility ="Accessibility of the Corporator" ///
			fit_satisfaction = "Satisfcation with the Corporator" ///
			fit_improvmentinlifestyle = "Lifestyle Improvements" ///
			fit_recallforname = "Recall for Corporator's Name") ylabel(,labsize(small)) ///

			title("Effect of Gender Quotas Constituency Service",size(medium))

graph export "./graphics/pg_plot.pdf", replace

drop _est*
drop *_std

	
	
* ------------------------------------------------------------: Table A.10 Placebo -----------------------------------------


genindex powersupply  instancesofcrime lawordersituation  pollutionproblems,nv(placebo_index)
 drop placebo_indexM- n_placebo_index_var
lab var placebo_indexA "placebo_index index"
lab var placebo_indexA_B "placebo_index-binary"

		reg placebo_indexA  genderquota i.year i.ward_fe , vce(cluster newid)
		outreg2 using "./index_tables/placebo_indexA.tex",ctitle((1)) keep(placebo_indexA  genderquota)  replace label 

		reg placebo_indexA   genderquota gender_election i.year i.ward_fe  , vce(cluster newid)
		outreg2 using "./index_tables/placebo_indexA.tex",ctitle((2)) keep(placebo_indexA  genderquota gender_election) append label
		
		reg placebo_indexA   genderquota gender_pre_local i.year i.ward_fe gender_pre_local, vce(cluster newid)
		outreg2 using "./index_tables/placebo_indexA.tex",ctitle((1)) keep(placebo_indexA  genderquota gender_pre_local ) append label
		
		reg placebo_indexA   genderquota gender_aft_local i.year i.ward_fe gender_aft_local, vce(cluster newid)
		outreg2 using "./index_tables/placebo_indexA.tex",ctitle((1)) keep(placebo_indexA  genderquota gender_aft_local) append tex(frag)label
		
	
	
	
* ------------------------------------------------------------: Table A.11 Individual Corruption model -----------------------------------------

* Constituency fixed effects models exclude  years after  2017 as the constituency maps were redrawn making them uncomparable with previous years.

	reg curruption genderquota, vce(cluster newid)
	outreg2 using "./index_tables/corruption.tex",ctitle((1)) keep(curruption  genderquota)  replace label 
	
	reg curruption genderquota i.year, vce(cluster newid)
	outreg2 using "./index_tables/corruption.tex",ctitle((1)) keep(curruption  genderquota)  append label 

		reg curruption genderquota i.year i.ward_fe if year<2017, vce(cluster newid)
		outreg2 using "./index_tables/corruption.tex",ctitle((1)) keep(curruption  genderquota) append tex(frag)label

	
	


* ------------------------------------------------------------: Table 1 and Figure A.3:-----------------------------------------
*first set are pg
* second set are individual goods q_distribution q_housing q_humanres q_license
* third set includes rhetorical questions q_renaming  q_crimecorrupt q_culture
*q_corporation is extraction of rent?


alpha q_education q_health  q_otherinfrastructure q_pollution ///
q_recreationcommunity  q_transport q_watertoilets q_corporation ///
q_distribution q_housing q_humanres q_license q_renaming  q_crimecorrupt ///
 q_culture, item std

genindex q_education q_health  q_otherinfrastructure q_pollution ///
q_recreationcommunity  q_transport q_watertoilets q_corporation ///
q_distribution q_housing q_humanres q_license q_renaming  q_crimecorrupt ///
 q_culture,nv(q_asked)
 drop q_askedM- n_q_asked_var
lab var q_askedA "Questions index"
lab var q_askedA_B "Questions Index-binary"

	

		reg q_askedA  genderquota i.year , vce(cluster newid)
		outreg2 using "./effort_tables/q_asked.tex",ctitle((1)) dec(3) pdec(3) keep(q_askedA  genderquota)  replace label 

		reg q_askedA  genderquota i.year i.ward_fe if year<2017, vce(cluster newid)
		outreg2 using "./effort_tables/q_asked.tex",ctitle((1)) dec(3) pdec(3) keep(q_askedA  genderquota)  append label 

		
		reg q_askedA   genderquota gender_election i.year   , vce(cluster newid)
		outreg2 using "./effort_tables/q_asked.tex",ctitle((2)) dec(3) pdec(3) keep(q_askedA  genderquota gender_election) append tex(frag) label
		

		
		

foreach var of varlist q_education q_health  q_otherinfrastructure q_pollution q_recreationcommunity  q_transport q_watertoilets q_corporation q_distribution q_housing q_humanres q_license q_renaming  q_crimecorrupt q_culture{	
		qui sum `var' if genderquota==0
		qui gen `var'_mean=r(mean)
		qui gen `var'_sd=r(sd)
		qui gen `var'_std=(`var'-`var'_mean)/`var'_sd
		drop `var'_mean `var'_sd
		}

		
foreach var of varlist q_education q_health  q_otherinfrastructure q_pollution ///
q_recreationcommunity  q_transport q_watertoilets q_corporation q_distribution ///
q_housing q_humanres q_license q_renaming  q_crimecorrupt q_culture{ 
quietly reg `var'_std genderquota i.year i.ward_fe, cluster(newid)
estimates store fit3_`var'
}


coefplot (fit3_*), keep(genderquota) xline(0) asequation swapnames sort(, descending) ///
graphregion(col(white)) bgcol(white) ///
ylabel(,nogrid) xlabel(,nogrid) ///
levels(95 90)  legend(order(1 "95% CI" 2 "90% CI")) ciopts(recast(. rcap)) ///
coeflabels(fit3_q_education = "Education" ///
fit3_q_health = "Health" ///
fit3_q_otherinfrastructure = "Other Infra" ///
fit3_q_pollution = "Pollution" ///
fit3_q_recreationcommunity = "Community Recreation" ///
fit3_q_transport = "transport" ///
fit3_q_watertoilets = "Toilets and Water" ///
fit3_q_corporation = "Corporation Related" ///
fit3_q_distribution = "Distribution" ///
fit3_q_housing = "Housing" ///
fit3_q_humanres = "Human Resources" ///
fit3_q_license = "License" ///
fit3_q_renaming = "Renaming of Roads" ///
fit3_q_crimecorrupt = "Crime and Corruption" ///
fit3_q_culture = "Culture") ///
  title("Gender Quotas & Question Asked",size(medium))
  
  
graph export "./graphics/questions_plot.pdf", replace					


  
  
  



* ------------------------------------------------------------: Table 2 Panel A :-----------------------------------------
	
alpha q_renaming  q_crimecorrupt q_culture, item std



genindex  q_renaming  q_crimecorrupt q_culture, nv(rheto_ques)

 drop rheto_quesM- n_rheto_ques_var
lab var rheto_quesA "rheto_ques  index"
lab var rheto_quesA_B "rheto_ques  Index-binary"

		*reg rheto_quesA  genderquota mayor_woman i.year , vce(cluster newid)
		*outreg2  using "./effort_tables/woman_mayor.tex", keep(rheto_quesA  genderquota mayor_woman)  append label 


	
		reg rheto_quesA  genderquota i.year   , vce(cluster newid)
		outreg2 using "./effort_tables/rheto_ques.tex",ctitle((1)) keep(rheto_quesA  genderquota) stats(coef se pval) paren(se) bracket(pval) dec(3) pdec(3)  replace label 
		
		reg rheto_quesA  genderquota i.year  i.ward_fe if year<2017 , vce(cluster newid)
		outreg2 using "./effort_tables/rheto_ques.tex",ctitle((2)) keep(rheto_quesA  genderquota) stats(coef se pval) paren(se) bracket(pval) dec(3) pdec(3)  append tex(frag) label 

		
		
	
eststo rheto_ques: rwolf rheto_quesA , indepvar(genderquota gender_election) method(regress) controls(i.year) vce(cluster newid) cluster(newid)  reps(5000) seed(1617)   nodots verbose  holm
matrix m=e(RW_genderquota)

matrix list m
scalar rwolf_genderquota=m[1,3]	
matrix n=e(RW_gender_election) 
matrix list n
scalar rwolf_gender_election = n[1,3]	
	
	
foreach var of varlist q_renaming  q_crimecorrupt q_culture{	
		qui sum `var' if genderquota==0
		qui gen `var'_mean=r(mean)
		qui gen `var'_sd=r(sd)
		qui gen `var'_std=(`var'-`var'_mean)/`var'_sd
		drop `var'_mean `var'_sd
		}


		
  

* ------------------------------------------------------------: Table 2 Panel B :-----------------------------------------



alpha q_education q_health  q_otherinfrastructure q_pollution q_recreationcommunity  q_transport q_watertoilets, item std


genindex q_education q_health  q_otherinfrastructure q_pollution q_recreationcommunity  q_transport q_watertoilets, nv(pubg_ques)

 drop pubg_quesM- n_pubg_ques_var
lab var pubg_quesA "PubG Ques index"
lab var pubg_quesA_B "PubG Ques Index-binary"

		*reg pubg_quesA  genderquota mayor_woman i.year , vce(cluster newid)
		*outreg2  using "./effort_tables/woman_mayor.tex", keep(pubg_quesA  genderquota mayor_woman)  append label 

	
		reg pubg_quesA  genderquota i.year   , vce(cluster newid)
		outreg2 using "./effort_tables/pubg_ques.tex",ctitle((1)) keep(pubg_quesA  genderquota) stats(coef se pval) paren(se) bracket(pval) dec(3) pdec(3)  replace label 
		
		reg pubg_quesA  genderquota i.year  i.ward_fe if year<2017 , vce(cluster newid)
		outreg2 using "./effort_tables/pubg_ques.tex",ctitle((1)) keep(pubg_quesA  genderquota) stats(coef se pval) paren(se) bracket(pval) dec(3) pdec(3)  append tex(frag) label 

		
		
			
	
eststo pubg_ques: rwolf pubg_quesA, indepvar(genderquota gender_election) method(regress) controls(i.year) vce(cluster newid) cluster(newid)  reps(5000) seed(1618)   nodots verbose  holm
matrix m=e(RW_genderquota)

matrix list m
scalar rwolf_genderquota=m[1,3]	
matrix n=e(RW_gender_election) 
matrix list n
scalar rwolf_gender_election = n[1,3]	
		
		
foreach var of varlist   q_health  q_otherinfrastructure q_pollution q_recreationcommunity  q_transport q_watertoilets{ 
			qui reg `var'_std genderquota i.year i.castenum i.ward_fe, vce(cluster newid)
			outreg2 using pg_questions, append tex(frag) label 
} 





	
* ------------------------------------------------------------: Table 2 Panel C :-----------------------------------------

alpha q_distribution q_housing q_humanres q_license, item std

foreach var of varlist q_distribution q_housing q_humanres q_license{	
		qui sum `var' if genderquota==0
		qui gen `var'_mean=r(mean)
		qui gen `var'_sd=r(sd)
		qui gen `var'_std=(`var'-`var'_mean)/`var'_sd
		drop `var'_mean `var'_sd
		}


		
	
genindex  q_distribution q_housing q_humanres q_license, nv(indiv_ques)

 drop indiv_quesM- n_indiv_ques_var
lab var indiv_quesA "indiv_ques  index"
lab var indiv_quesA_B "indiv_ques  Index-binary"


		*reg indiv_quesA  genderquota mayor_woman i.year , vce(cluster newid)
		*outreg2  using "./effort_tables/woman_mayor.tex", keep(indiv_quesA  genderquota mayor_woman)  append label 

		
		reg indiv_quesA  genderquota i.year   , vce(cluster newid)
		outreg2 using "./effort_tables/indiv_ques.tex",ctitle((1)) keep(indiv_quesA  genderquota) stats(coef se pval) paren(se) bracket(pval) dec(3) pdec(3)  replace label 
		
		reg indiv_quesA  genderquota i.year  i.ward_fe if year<2017 , vce(cluster newid)
		outreg2 using "./effort_tables/indiv_ques.tex",ctitle((1)) keep(indiv_quesA  genderquota) stats(coef se pval) paren(se) bracket(pval) dec(3) pdec(3)  append tex(frag) label 

	
		
		
		
eststo indiv_ques: rwolf indiv_quesA , indepvar(genderquota gender_election) method(regress) controls(i.year) vce(cluster newid) cluster(newid)  reps(5000) seed(1619)   nodots verbose  holm
matrix m=e(RW_genderquota)

matrix list m
scalar rwolf_genderquota=m[1,3]	
matrix n=e(RW_gender_election) 
matrix list n
scalar rwolf_gender_election = n[1,3]	
		
		
		
					
			
* ------------------------------------------------------------: Table 2 Panel D :-----------------------------------------

foreach var of varlist q_corporation {
		qui sum `var' if genderquota==0
		qui gen `var'_mean=r(mean)
		qui gen `var'_sd=r(sd)
		qui gen `var'_std=(`var'-`var'_mean)/`var'_sd
		drop `var'_mean `var'_sd
		}
			
			
	
			reg q_corporation_std genderquota  i.year  , vce(cluster newid)
			outreg2 using "./effort_tables/rental.tex",ctitle((1)) keep(q_corporation_std  genderquota) stats(coef se pval) paren(se) bracket(pval) dec(3) pdec(3)  replace label 
			
			reg q_corporation_std genderquota  i.year i.ward_fe , vce(cluster newid)
			outreg2 using "./effort_tables/rental.tex",ctitle((1)) keep(q_corporation_std  genderquota) stats(coef se pval) paren(se) bracket(pval) dec(3) pdec(3)  append tex(frag) label 
			
			
		
			
	eststo q_corp: rwolf q_corp_star , indepvar(genderquota gender_election) method(regress) controls(i.year) vce(cluster newid) cluster(newid)  reps(5000) seed(1620)   nodots verbose  holm
	matrix m=e(RW)
	matrix list m
	scalar rwolf_q_corp=m[1,3]	
	

		
		 
	
	
* ------------------------------------------------------------: Table 3 Panel A :-----------------------------------------
*mkdir effort_tables
* Funds Prop unavailable for 2011 so cannot do ward_fe

alpha attend_ward funds_prop, item std
*not correlated at all, alpha = 0.175
*corr = 0.09
*Don't have to index. But to be fully certain I am bootstrapping using Romano-Wolf



foreach var of varlist attend_ward funds_prop{	
			qui sum `var' if genderquota==0
			qui gen `var'_mean=r(mean)
			qui gen `var'_sd=r(sd)
			qui gen `var'_std=(`var'-`var'_mean)/`var'_sd
			drop `var'_mean `var'_sd
			}

		
		

* ssc install wyoung, replace
* ssc install rwolf, replace
*wyoung attend_ward funds_prop, cmd(regress OUTCOMEVAR genderquota) familyp(genderquota) bootstraps(100)

reg attend_ward_std genderquota i.year, vce(cluster newid)
outreg2 using "./effort_tables/fund_attend.tex",ctitle((1)) keep(attend_ward_std  genderquota) stats(coef se pval) paren(se) bracket(pval) dec(3) pdec(3)  replace label 

reg attend_ward_std genderquota i.year i.ward_fe if year<2017, vce(cluster newid)
outreg2 using "./effort_tables/fund_attend.tex",ctitle((1)) keep(attend_ward_std  genderquota) stats(coef se pval) paren(se) bracket(pval) dec(3) pdec(3)  append label 

reg funds_prop_std genderquota i.year , vce(cluster newid)
outreg2 using "./effort_tables/fund_attend.tex",ctitle((1)) keep(funds_prop_std  genderquota) stats(coef se pval) paren(se) bracket(pval) dec(3) pdec(3)  append tex(frag) label 




eststo wolf_attend_ward: rwolf attend_ward_std funds_prop_std , indepvar(genderquota) method(regress) controls(i.year) vce(cluster newid) cluster(newid)  reps(5000) seed(11231)  nodots verbose  holm
matrix m=e(RW)
matrix list m
scalar rwolf_attend=m[1,3]
scalar rwolf_funds=m[2,3]



* ------------------------------------------------------------: Table 3 Panel B :-----------------------------------------

alpha attend_corp total_questions, item std
*Not correlated at all: alpha = 0.37, corr = 0.2314. 
*Don't have to index. But to be fully certain I am bootstrapping using Romano-Wolf



foreach var of varlist attend_corp total_questions{	
		qui sum `var' if genderquota==0
		qui gen `var'_mean=r(mean)
		qui gen `var'_sd=r(sd)
		qui gen `var'_std=(`var'-`var'_mean)/`var'_sd
		drop `var'_mean `var'_sd
		}

		rename total_questions_std total_q_std
		
		
		
reg attend_corp_std genderquota i.year, vce(cluster newid)
outreg2 using "./effort_tables/parl_act.tex",ctitle((1)) keep(genderquota) stats(coef se pval) paren(se) bracket(pval) dec(3) pdec(3)  replace label 

reg attend_corp_std genderquota i.year i.ward_fe if year<2017, vce(cluster newid)
outreg2 using "./effort_tables/parl_act.tex",ctitle((1)) keep(genderquota) stats(coef se pval) paren(se) bracket(pval) dec(3) pdec(3)  append label 

reg total_q_std genderquota i.year , vce(cluster newid)
outreg2 using "./effort_tables/parl_act.tex",ctitle((1)) keep(genderquota) stats(coef se pval) paren(se) bracket(pval) dec(3) pdec(3)  append tex(frag) label 




eststo wolf_attend_corp: rwolf attend_corp_std total_q_std , indepvar(genderquota) method(regress) controls(i.year) vce(cluster newid) cluster(newid)  reps(5000) seed(11232)  nodots verbose  holm
matrix m=e(RW)
matrix list m
scalar rwolf_attend=m[1,3]
scalar rwolf_funds=m[2,3]



* ------------------------------------------------------------: Table A.4 Balance Test :-----------------------------------------

*duplicate ward8
 replace ward =. if (ward == 8 & year == 2014)
 drop if ward==.
 
  
drop if year >2013
gen newyear=0
 replace newyear=1 if year==2013
 
 tsset ward newyear
  sort ward newyear 

  
 
	encode margin, generate(margin1)
	egen partyid = group(party)
	egen runnerup_id = group(runner_up_party)


  
	
    reg genderquota L.slum 
	outreg2 using "./balance_test.tex",ctitle(reserved for Women)  stats(coef se pval) paren(se) dec(3) pdec(3)  replace  label 
	
	
	reg genderquota L.margin1
	outreg2 using "./balance_test.tex",ctitle(reserved for Women)  stats(coef se pval) paren(se) dec(3) pdec(3)  append  label 
	
	reg genderquota L.partyid
	outreg2 using "./balance_test.tex",ctitle(reserved for Women)  stats(coef se pval) paren(se) dec(3) pdec(3)  append  label 
	
	reg genderquota L.runnerup_id
	outreg2 using "./balance_test.tex",ctitle(reserved for Women)  stats(coef se pval) paren(se) dec(3) pdec(3)  append  label 
	
	reg genderquota L.admin_num
	outreg2 using "./balance_test.tex",ctitle(reserved for Women)  stats(coef se pval) paren(se) dec(3) pdec(3)  append tex(frag) label 
	

		* ------------------------------------------------------------: Table A.9: Constituency Service without individual measures-----------------------------------------

	
alpha conditionofroads  publicgardens publictransport  hospitals ///
schoolsandcolleges  watersupply waterlogging cleanlinesssanitation, item std
*mkdir index_tables
do genindex1.do

genindex publicgardens publictransport conditionofroads   traffic   hospitals schoolsandcolleges  watersupply waterlogging    cleanlinesssanitation  ,nv(no_indiv_measures)
 drop no_indiv_measuresM- n_no_indiv_measures_var
lab var no_indiv_measuresA "PG index No Indiv MEasures"
lab var no_indiv_measuresA_B "PG Index-binary No Indiv MEasures"

		reg no_indiv_measuresA  genderquota i.year  , vce(cluster newid)
		outreg2 using "./index_tables/no_indiv_measuresA.tex",ctitle((1)) keep(no_indiv_measuresA  genderquota)  replace label 

		reg no_indiv_measuresA   genderquota gender_election i.year  , vce(cluster newid)
		outreg2 using "./index_tables/no_indiv_measuresA.tex",ctitle((2)) keep(no_indiv_measuresA  genderquota gender_election) append tex(frag)label
		
		
