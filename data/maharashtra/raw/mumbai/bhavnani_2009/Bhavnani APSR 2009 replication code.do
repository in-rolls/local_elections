***************************************************************************************************************************************************************************
*Replication code for 
*Bhavnani, Rikhil. 2009. "Do Electoral Quotas Work After They Are Withdrawn? Evidence from a Natural Experiment in India," American Political Science Review 103 (1):23-35.
***************************************************************************************************************************************************************************
clear 
set mem 100m
set more off
use "Bhavnani APSR 2009 replication data.dta"

*********
*FIGURE 1
*********
tab groups

********
*TABLE 2
********
tabstat genderofwinner anywomencan noofwomencan noofcan perwomencan femalevoteper avgfemalevoteper turnout winmargin, by(reservedforwomen) 
*proportion and t-tests for reserved/not reserved
foreach var in genderofwinner anywomencan {
	prtest `var', by(reservedforwomen)
}
foreach var in noofwomencan noofcan perwomencan femalevoteper avgfemalevoteper turnout winmargin {
	display "`var'"
	ttest `var', by(reservedforwomen)
}

********
*TABLE 3
********
tabstat genderofwinner anywomencan noofwomencan noofcan perwomencan noofserwomencan noofsercan perserwomencan nooffemalenewcan anyfemalecancompetitive femalevoteper avgfemalevoteper turnout wincanvoteper winmargin, by(controltreat)
*proportion and t-tests for control/treat
foreach var in genderofwinner anywomencan {
	prtest `var', by(controltreat)
}
foreach var in noofwomencan noofcan perwomencan noofserwomencan noofsercan perserwomencan nooffemalenewcan {
	display "`var'"
	ttest `var', by(controltreat)
}
foreach var in anyfemalecancompetitive {
	display "`var'"
	prtest `var', by(controltreat)
}
foreach var in femalevoteper avgfemalevoteper turnout wincanvoteper winmargin {
	display "`var'"
	ttest `var', by(controltreat)
}

********
*TABLE 4
********
logit genderofwinner controltreat
outreg using table4.txt, replace se br bdec(3) addstat("Pseudo R-squared", e(r2_p)) 3aster
logit genderofwinner controltreat incumbentM incumbentF
outreg using table4.txt, append  se br bdec(3) addstat("Pseudo R-squared", e(r2_p)) 3aster
firthlogit genderofwinner controltreat anyfemalecanran noofwomencan noofwomencan2
outreg using table4.txt, append  se br bdec(3) 3aster
foreach var in "turnout pvchangem pvchangef" "turnout97 controltreatturnout97" {
	logit genderofwinner controltreat `var' 
	outreg using table4.txt, append se br bdec(3) addstat("Pseudo R-squared", e(r2_p)) 3aster
}
logit genderofwinner controltreat incumbentF noofwomencan noofwomencan2 
outreg using table4.txt, append se br bdec(3) addstat("Pseudo R-squared", e(r2_p)) 3aster
firthlogit genderofwinner controltreat incumbentM incumbentF anyfemalecanran noofwomencan noofwomencan2 turnout pvchangem pvchangef turnout97 controltreatturnout97
outreg using table4.txt, append se br bdec(3) 3aster

********
*TABLE 5 
********
summ *ranfemale if reservedforwomen==1
tab controltreat, summ(ssranfemale)
tab controltreat, summ(bjpranfemale)
tab controltreat, summ(incranfemale)
tab controltreat, summ(ncpranfemale)

********
*TABLE 6 
********
tabstat turnout vchange vchangem vchangef, by(controltreat)
foreach var in turnout vchange vchangem vchangef {
	display "`var'"
	ttest `var', by(controltreat)
}




