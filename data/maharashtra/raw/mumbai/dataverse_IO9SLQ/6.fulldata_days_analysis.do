clear
set more off
*cd "/Users/alee87/Dropbox/Mumbai-Delhi/Analysis/"
cap cd "/Users/varun/Library/CloudStorage/Dropbox/PhD/Mumbai-Delhi/CPS_Replication"
set matsize 11000
set logtype text
capture log close
log using "./output", replace

* ------------------------------------------------------------: Data Analysis :------------------------------------------------------------ *

use "fulldata_reshaped.dta", clear

egen newid = group(adminward term)
sort newid
 do genindex1.do

egen ward_fe = group(adminward)

mkdir logdays_full_tables 
* ------------------------------------------------------------: Table A.12 :------------------------------------------------------------ *

do genindex1.do


drop bld_perm_temp_monsoon_shed  encr_municipal_colony_slum  encr_nuisance_due_to_vagrants
drop shp_online_renewal_application col_others_colony_officer_col  lic_others_lic lic_unauth_workshop_or_garage lic_unauth_storage_explosives

 
drop  rd_resurfacing_of_road rd_signals  rd_relaying_and_repairs_roads rd_providing_rd_name_plate  rd_reinstatement_of_trenches  rd_repairs_of_road_footpath
drop  ws_removal_of_water_meters ws_use_of_booster_pump  ws_non_receipt_water_bills ws_overflow_overhead_tank ws_unauth_use_waterchange_user  ws_others_was
drop  strm_provid_manhole_cover_swd 
drop drain_raising_of_manhole  drain_odour_from_drains  drain_others_drn
drop  swm_unhygienic_cond_toilets swm_removal_of_dead_animals swm_gbg_not_lifted_mun_market swm_others_swm
drop  pst_unauth_uncov_water_storage  pst_nuisance_cockroaches  pst_nuisance_due_to_white_ants

drop  bld_other_buildings  mun_others_rnt  mun_maint_municipal_property  shp_open_beyond_permis_hours
drop rd_digg* swm_clean*

*ssc install estout, replace



eststo complaints: quietly estpost summarize ///
	bld_* encr_* mun_* shp_* lic_* col_* fac_* ///
	rd_* ws_* strm_* drain_* swm_* gdn_* pst_* heal_*
*eststo complaints: quietly estpost summarize ///
	

esttab  complaints  using "./logdays_full_tables/Complaint_Means.tex", ///
	cells("mean(pattern(1 1 0) fmt(3)) sd(pattern(1 1 0)) b(star pattern(0 0 1) fmt(3)) t(pattern(0 0 1) par fmt(3))") label title("Summary statistics") collabels("Mean" "S.D.") mtitle( "Clientel" "PubG") nonum replace




* ------------------------------------------------------------: Table 4 Panle B Index :------------------------------------------------------------ *


genindex bld_* encr_* mun_* shp_* lic_* fac_* rd_* ws_*  strm_* drain_*  swm_* gdn_* pst_* heal_*, nv(every_index)






		
		reg every_indexA  genderquota i.year, vce(cluster newid)
		outreg2 using "./logdays_full_tables/every_indexA.tex", keep(every_indexA  genderquota)  replace label 

		reg every_indexA  genderquota gender_election i.year , vce(cluster newid)
		outreg2 using "./logdays_full_tables/every_indexA.tex", keep(every_indexA  genderquota gender_election ) append tex(frag) label
		
		
			
		
/*
if you use the raw data, complaints that take a long time to resolve will have 
(relatively) more impact on the estimate, and if you take logs, complaints that 
resolves fairly quickly will have (relatively) more impact on the estimate. 
I’d probably check both ways to ensure that your results are not qualitatively 
sensitive to the choice;	
*/


foreach var of varlist bld_* encr_* mun_* shp_* lic_*  fac_*  rd_* ws_* strm_* drain_* swm_* gdn_* pst_* heal_*{
		replace `var' = log(`var')
		}
		
	genindex bld_* encr_* mun_* shp_* lic_*  fac_*  rd_* ws_* strm_* drain_* swm_* gdn_* pst_* heal_*,nv(ln_every_index)
	
 drop ln_every_indexM- n_ln_every_index_var
lab var ln_every_indexA "ln_every_indexA index"
lab var ln_every_indexA_B "ln_every_indexA-binary"

		reg ln_every_indexA  genderquota i.year i.ward_fe, vce(cluster newid)
		outreg2 using "./logdays_full_tables/ln_every_indexA.tex",ctitle(gender Quota) keep(ln_every_indexA  genderquota)  replace label 
		
		
		reg ln_every_indexA   genderquota gender_election i.year i.ward_fe, vce(cluster newid)
		outreg2 using "./logdays_full_tables/ln_every_indexA.tex",ctitle(Women in Ward) keep(ln_every_indexA  genderquota gender_election) append label
		
		reg ln_every_indexA  genderquota gender_pre_local i.year i.ward_fe, vce(cluster newid)
		outreg2 using "./logdays_full_tables/ln_every_indexA.tex", keep(every_indexA genderquota gender_pre_local) append label

		reg ln_every_indexA  genderquota gender_aft_local  i.year i.ward_fe, vce(cluster newid)
		*outreg2 using logdays_index,ctitle(Women)  append label
		outreg2 using "./logdays_full_tables/ln_every_indexA.tex",  keep(ln_every_indexA  genderquota gender_aft_local) append  label 
		

* ------------------------------------------------------------: Fig A.1 Buildings  :------------------------------------------------------------ *


rename bld_change_user_res_comm bld_res_com
rename bld_heavy_leakage_from_ceiling bld_leak
rename bld_unauth_alteration_bldg bld_unauth_alter
rename bld_unauth_constr_development bld_unauth_cons 
   
   
egen z_bld_res_com = std(bld_res_com)

egen z_bld_leak = std(bld_leak)
egen z_bld_unauth_alter = std(bld_unauth_alter)
egen z_bld_unauth_cons = std(bld_unauth_cons)


foreach var of varlist z_bld_res_com z_bld_leak z_bld_unauth_alter  z_bld_unauth_cons {
quietly reg `var' genderquota i.year i.ward_fe, cluster(newid)
estimates store f_`var'
}
*ssc install grstyle
*grstyle init
*grstyle set plain, nogrid noextend 


coefplot (f_*), keep(genderquota) xline(0) asequation swapnames sort(, descending) ///
graphregion(col(white)) bgcol(white) ///
ylabel(,nogrid) xlabel(,nogrid) ///
levels(95, 90)  legend(order(1 "95% CI" 2 "90% CI")) ciopts(recast(. rcap)) /// 
coeflabels(f_z_bld_res_com = "Residential/Commercial Categorization" ///
			f_z_bld_leak = "Leak in Buildings" ///
			f_z_bld_unauth_alter = "Unauthorized Alteration" ///
			f_z_bld_unauth_cons = "Unauthorized Construction") ///  
			ylabel(,labsize(small)) ///
			title("Complaint Resolution - Buildings",size(medium))
			
			
			graph export "./graphics/building.pdf", replace
drop z_*	

	 
* encr
			
rename encr_hawkers encr_hawk
rename encr_municipal_land_foot_swd encr_foot_swd
rename encr_municipal_plot  encr_mun_plot
rename encr_others_ecnr encr_others
rename encr_private_land_bldg_fact encr_factory
			
			
foreach var of varlist encr_hawk  encr_foot_swd encr_mun_plot  encr_others encr_factory {
egen z_`var' = std(`var')
}

foreach var of varlist encr_hawk  encr_foot_swd encr_mun_plot  encr_others encr_factory {
quietly reg z_`var' genderquota i.year i.ward_fe, cluster(newid)
estimates store e_`var'
}
*ssc install grstyle
*grstyle init
*grstyle set plain, nogrid noextend 


coefplot (e_*), keep(genderquota) xline(0) asequation swapnames sort(, descending) ///
graphregion(col(white)) bgcol(white) ///
ylabel(,nogrid) xlabel(,nogrid) ///
levels(95, 90)  legend(order(1 "95% CI" 2 "90% CI")) ciopts(recast(. rcap)) ///
coeflabels(e_encr_hawk = "Hawkers" ///
			e_encr_foot_swd = "Footpath Encroachment" ///
			e_encr_factory = "Factory Encroachment" ///
			e_encr_mun_plot = "Municipal Plot Encroachment" ///
			e_encr_others = "Encorachment - Others") ///  
			ylabel(,labsize(small)) ///   
			title("Complaint Resolution - Encroachment",size(medium))
			
			
			graph export "encroachment.pdf", replace
			
			
drop z_*
			 
* Fig A.1 Municipality

rename mun_major_repairs_to_mun_prop mun_maj_repair
 rename mun_minor_repairs_to_mun_prop mun_min_repair

foreach var of varlist  mun_maj_repair mun_min_repair  {
egen z_`var' = std(`var')
}

foreach var of varlist  mun_maj_repair mun_min_repair  {
quietly reg z_`var' genderquota i.year i.ward_fe, cluster(newid)
estimates store m_`var'
}



coefplot (m_*), keep(genderquota) xline(0) asequation swapnames sort(, descending) ///
graphregion(col(white)) bgcol(white) ///
ylabel(,nogrid) xlabel(,nogrid) ///
levels(95, 90)  legend(order(1 "95% CI" 2 "90% CI")) ciopts(recast(. rcap)) ///  
coeflabels(m_mun_maj_repair = "Major Repairs " ///
			m_mun_min_repair = "Minor Repairs") ///   
			ylabel(,labsize(small)) ///
			title("Complaint Resolution - Municipal Matters",size(medium))
			
			
			graph export "./graphics/municiapl.pdf", replace
drop z_*
			


*** Fig A.1 License
 rename lic_trade_without_license lic_no_license
 rename lic_unauth_banners_advt_road lic_unauth_ads
 rename lic_unauth_stalls_road_foot lic_unauth_stalls
	
foreach var of varlist  lic_no_license lic_unauth_ads  lic_unauth_stalls {
egen z_`var' = std(`var')
}



foreach var of varlist  lic_no_license lic_unauth_ads  lic_unauth_stalls {
quietly reg z_`var' genderquota i.year i.ward_fe, cluster(newid)
estimates store l_`var'
}


coefplot (l_*), keep(genderquota) xline(0) asequation swapnames sort(, descending) ///
graphregion(col(white)) bgcol(white) ///
ylabel(,nogrid) xlabel(,nogrid) ///
levels(95, 90)  legend(order(1 "95% CI" 2 "90% CI")) ciopts(recast(. rcap)) /// 
coeflabels(l_lic_no_license = "No License Ops" ///
			l_lic_unauth_stalls = "Unauthorized Ads" ///
			l_lic_unauth_ads = "Unauthorized Stalls") ///     
			ylabel(,labsize(small)) ///
			title("Complaint Resolution - Licenses",size(medium))
			
			
			graph export "./graphics/license.pdf", replace
			
			drop z_*
			
*** Fig A.1 Factory and shops


rename shp_running_without_license shp_no_license 
rename fac_unauth_factory_workshop factory_unauth

foreach var of varlist  shp_no_license factory_unauth {
egen z_`var' = std(`var')
}

foreach var of varlist shp_no_license factory_unauth {
quietly reg z_`var' genderquota i.year i.ward_fe, cluster(newid)
estimates store one_`var'
}


coefplot (one_*), keep(genderquota) xline(0) asequation swapnames sort(, descending) ///
graphregion(col(white)) bgcol(white) ///
ylabel(,nogrid) xlabel(,nogrid) ///
levels(95, 90)  legend(order(1 "95% CI" 2 "90% CI")) ciopts(recast(. rcap)) ///  
coeflabels(one_shp_no_license = "Shops w/o License" ///
			one_factory_unauth = "Unauthorized Factory") ///  
			ylabel(,labsize(small)) title("Complaint Resolution - Factories and Shops",size(medium))
			
			
			graph export "./graphics/fac_shop.pdf", replace
			drop z_*
			
			
			 	
*** Fig A.1 Health 

rename heal_birth_deat_cert_issue heal_borndead_cert
rename heal_others_moh heal_others

 rename heal_unauth_food_sell heal_unauth_food

foreach var of varlist heal_borndead_cert heal_unauth_food heal_others {
egen z_`var' =std(`var')
}

foreach var of varlist heal_borndead_cert heal_unauth_food heal_others {
quietly reg z_`var' genderquota i.year i.ward_fe, cluster(newid)
estimates store heal_`var'
}


coefplot (heal_*), keep(genderquota) xline(0) asequation swapnames sort(, descending) ///
graphregion(col(white)) bgcol(white) ///
ylabel(,nogrid) xlabel(,nogrid) ///
levels(95, 90)  legend(order(1 "95% CI" 2 "90% CI")) ciopts(recast(. rcap)) /// 
coeflabels(heal_heal_borndead_cert = "Birth/Death Certificates" ///
			heal_heal_unauth_food = "Unauthorized Food Stalls" ///
			heal_heal_others = "Other Health Concerns") ///   
			ylabel(,labsize(small)) title("Complaint Resolution - Public Health",size(medium))
			
			
			graph export "./graphics/health.pdf", replace
			 
			
		drop z_*	
*** Fig A.1 Pest Control
rename pst_fogging  pst_fogg
rename pst_mosquito_nuisance pst_mosquito
 rename pst_rat_nuisance pst_rats
			
foreach var of varlist pst_fogg pst_mosquito   pst_rats {
egen z_`var' =std(`var')
}

foreach var of varlist pst_fogg pst_mosquito   pst_rats {
quietly reg z_`var' genderquota i.year i.ward_fe, cluster(newid)
estimates store pst_`var'
}


coefplot (pst_*), keep(genderquota) xline(0) asequation swapnames sort(, descending) ///
graphregion(col(white)) bgcol(white) ///
ylabel(,nogrid) xlabel(,nogrid) ///
levels(95, 90)  legend(order(1 "95% CI" 2 "90% CI")) ciopts(recast(. rcap)) /// 
coeflabels(pst_pst_fogg = "Fogging" ///
			pst_pst_mosquito = "Mosquito Control" ///
			pst_pst_rats = "Rat Control") ///     
			ylabel(,labsize(small)) title("Complaint Resolution - Pest Control",size(medium))
			
			
			graph export "./graphics/pest.pdf", replace
			
drop z_*		
 

** Fig A.1 Garden 
rename gdn_fallen_tree_on_road gdn_fall_tree
 rename gdn_lifting_of_tree_cutting gdn_lift_tree
 rename gdn_perm_for_tree_cutting gdn_perm_tree
 rename gdn_trimming_of_branches gdn_trim

 
 foreach var of varlist gdn_fall_tree gdn_lift_tree gdn_perm_tree gdn_trim {
 egen z_`var' =std(`var')
 }
 
  foreach var of varlist gdn_fall_tree gdn_lift_tree gdn_perm_tree gdn_trim {
quietly reg z_`var' genderquota i.year i.ward_fe, cluster(newid)
estimates store gdn_`var'
}


coefplot (gdn_*), keep(genderquota) xline(0) asequation swapnames sort(, descending) ///
graphregion(col(white)) bgcol(white) ///
ylabel(,nogrid) xlabel(,nogrid) ///
levels(95, 90)  legend(order(1 "95% CI" 2 "90% CI")) ciopts(recast(. rcap)) ///   
coeflabels(gdn_gdn_fall_tree = "Fallen tree" ///
			gdn_gdn_lift_tree = "Tree Lifting" ///
			gdn_gdn_perm_tree = "Tree Cutting Permission" /// 
			gdn_gdn_trim = "Trimming Trees") ///
			ylabel(,labsize(small)) title("Complaint Resolution - Gardens",size(medium))
			
			
			graph export "./graphics/garden.pdf", replace
			
drop z_*	

 

 *** Fig A,1 SWM
 
 
 rename swm_collection_pt_not_attend swm_collect_pt
 rename swm_gbg_lorry_not_report_cove swm_lorry_uncover
 rename swm_gbg_not_lifted_gully swm_gbg_lift
 rename swm_gbg_not_lifted_from_road  swm_gbg_road
 rename swm_no_attend_public_toilets swm_pub_toilet
 rename swm_non_attend_nuis_detect swm_attend_nuis
 rename swm_dustbins swm_bins
 rename swm_removal_of_debris swm_debris
 rename swm_silt_lifted_from_road swm_silt_road
 rename swm_sweeping_of_roads swm_sweep_road
 
foreach var of varlist  swm_collect_pt swm_lorry_uncover swm_gbg_lift  swm_gbg_road ///
 swm_pub_toilet swm_attend_nuis  swm_bins   swm_debris ///
 swm_silt_road swm_sweep_road  {
 egen z_`var' = std(`var')
 }
 
 foreach var of varlist  swm_collect_pt swm_lorry_uncover swm_gbg_lift  swm_gbg_road ///
 swm_pub_toilet swm_attend_nuis  swm_bins   swm_debris ///
 swm_silt_road swm_sweep_road  {
 quietly reg z_`var' genderquota i.year i.ward_fe, cluster(newid)
estimates store swm_`var'
}


coefplot (swm_*), keep(genderquota) xline(0) asequation swapnames sort(, descending) ///
graphregion(col(white)) bgcol(white) ///
ylabel(,nogrid) xlabel(,nogrid) ///
levels(95, 90)  legend(order(1 "95% CI" 2 "90% CI")) ciopts(recast(. rcap)) ///  
coeflabels(swm_swm_collect_pt = "Garbage Collection Point Attendance" ///
			swm_swm_lorry_uncover = "Garbage Lorry Uncovered" ///
			swm_swm_gbg_lift = "Garbage Lifting" /// 
			swm_swm_gbg_road = "Garbage on Roads" ///
			swm_swm_pub_toilet  "Public Toilet Cleaning" ///
			swm_swm_attend_nuis = "Nuisance Detector Attendance" ///
			swm_swm_bins  ="Gabage Bins" ///
			swm_swm_debris = "Debris not Lifted" ///
			swm_swm_silt_road = "Desilting" ///
			swm_swm_sweep_road = "Sweeping of Roads") ///
			ylabel(,labsize(small)) title("Complaint Resolution - Solid Waste Mgmt",size(medium))
			
			
			graph export "./graphics/swm.pdf", replace
			
			
			drop z_*

			  
			
*** Fig A.1 Drainage
rename drain_cleaning_of_septic_tank drain_clean
 rename drain_drainage_choke_blockage  drain_block
 rename drain_repairs_to_pipe_sewers drain_sewer
 rename drain_replacement_manhole drain_manhole_replace

foreach var of varlist drain_clean drain_block   drain_sewer drain_manhole_replace {
egen z_`var' = std(`var')
}

foreach var of varlist drain_clean drain_block   drain_sewer drain_manhole_replace {
quietly reg z_`var' genderquota i.year i.ward_fe, cluster(newid)
estimates store drain_`var'
}


coefplot (drain_*), keep(genderquota) xline(0) asequation swapnames sort(, descending) ///
graphregion(col(white)) bgcol(white) ///
ylabel(,nogrid) xlabel(,nogrid) ///
levels(95, 90)  legend(order(1 "95% CI" 2 "90% CI")) ciopts(recast(. rcap)) ///   
coeflabels(drain_drain_clean = "Cleaning of Septic Tanks" ///
			drain_drain_block = "Blocked Drains" ///
			drain_drain_sewer = "Repairs to Pipe Sewers" /// 
			drain_drain_manhole_replace = "Manhole Replacement") ///
			ylabel(,labsize(small)) title("Complaint Resolution - Drainage",size(medium))
			
			graph export "./graphics/drain.pdf", replace
			
			
			drop z_*
			
			  
			
*** Fig A.1 STROM WATER

rename strm_cleaning_of_open_swd  strm_clean_swd
rename strm_cleaning_water_entrance strm_clean_entrance
 rename strm_cleaning_removal_of_silt strm_silt
 rename strm_flooding_during_monsoon strm_flloding
 rename strm_repair_damaged_open_swd strm_damage_swd
 
 foreach var of varlist strm_clean_swd strm_clean_entrance strm_silt strm_flloding strm_damage_swd {
 egen z_`var' = std(`var')
 }
 
 foreach var of varlist strm_clean_swd strm_clean_entrance strm_silt strm_flloding strm_damage_swd {
 quietly reg z_`var' genderquota i.year i.ward_fe, cluster(newid)

estimates store strm_`var'
}


coefplot (strm_*), keep(genderquota) xline(0) asequation swapnames sort(, descending) ///
graphregion(col(white)) bgcol(white) ///
ylabel(,nogrid) xlabel(,nogrid) ///
levels(95, 90)  legend(order(1 "95% CI" 2 "90% CI")) ciopts(recast(. rcap)) ///  
coeflabels(strm_strm_clean_swd = "Cleaning of Storm Water Drains" ///
			strm_strm_damage_swd = "Damaged Storm Water Drains" ///
			strm_strm_clean_entrance = "Cleaning og Drain Entrance" ///
			strm_strm_silt = "Removal of Silt" /// 
			strm_strm_flloding = "Flooding of Drains") /// 
			ylabel(,labsize(small)) title("Complaint Resolution - Storm Water Drain",size(medium))
			
			
			graph export "./graphics/storm.pdf", replace
			
			
			drop z_*
  
 ** Fig A.1 Water Supply
 
 rename ws_burst_water_main_lines ws_burst_line
 rename ws_contaminated_water_supply ws_contamination
 rename ws_leaks_in_water_lines_meter ws_leak_meter
 rename ws_shortage_of_water_supply ws_water_shortage
 rename ws_unauth_tapping_water_conn ws_unauth_tapping
 
 
 foreach var of varlist ws_burst_line ws_contamination ws_leak_meter ws_water_shortage ws_unauth_tapping {
 egen z_`var' = std(`var')
 }
 
 foreach var of varlist ws_burst_line ws_contamination ws_leak_meter ws_water_shortage ws_unauth_tapping {
 quietly reg z_`var' genderquota i.year i.ward_fe, cluster(newid)
  estimates store ws_`var'
}





coefplot (ws_*), keep(genderquota) xline(0) asequation swapnames sort(, descending) ///
graphregion(col(white)) bgcol(white) ///
ylabel(,nogrid) xlabel(,nogrid) ///
levels(95, 90)  legend(order(1 "95% CI" 2 "90% CI")) ciopts(recast(. rcap)) /// 
coeflabels(ws_ws_burst_line = "Burst Water Line" ///
			ws_ws_contamination = "Water Contamination" ///
			ws_ws_leak_meter = "Leakage Near Meters" ///
			ws_ws_water_shortage = "Water Shortage" /// 
			ws_ws_unauth_tapping = "Unauthorized Tappings") ///   
			ylabel(,labsize(small)) title("Complaint Resolution - Water Supply",size(medium))
			
			
			graph export "./graphics/water supply.pdf", replace
			
			
			drop z_*
			
** Fig A.1 Roads 

rename rd_bad_patch_potholes rd_pothole
 rename rd_speed_breakers rd_speed
 rename rd_street_lighting rd_lighting

 
 foreach var of varlist rd_pothole rd_speed rd_lighting {
 egen z_`var' = std(`var')
 }
 
 foreach var of varlist rd_pothole rd_speed rd_lighting {
  quietly reg z_`var' genderquota i.year i.ward_fe, cluster(newid)
estimates store rd_`var'
}


coefplot (rd_*), keep(genderquota) xline(0) asequation swapnames sort(, descending) ///
graphregion(col(white)) bgcol(white) ///
ylabel(,nogrid) xlabel(,nogrid) ///
levels(95, 90)  legend(order(1 "95% CI" 2 "90% CI")) ciopts(recast(. rcap)) ///   
coeflabels(rd_rd_pothole = "Potholes" ///
			rd_rd_speed = "Speed Breakers" ///
			rd_rd_lighting = "Street Lighting") ///   
			ylabel(,labsize(small)) title("Complaint Resolution - Roads",size(medium))
			
			
			graph export "./graphics/Roads.pdf", replace
			
			
			drop z_*






* ------------------------------------------------------------: Table A. 13 Total Gender Quota Members in Admin Ward :------------------------------------------------------------ *


* not using this!
*egen med = median(genderquota) 
*gen treatment=0
*replace treatment =1 if genderquota >= med
*egen ward_fe = group(adminward)

gen women = members*genderquota
*replace women= round(women,1)

egen wom_med = median(women)
gen wom_bin = 0
replace wom_bin =1 if women>=wom_med


egen wom_mean = mean(women)
gen wom_mean_bin = 0
replace wom_mean_bin =1 if women>=wom_mean





*total women
		reg every_indexA  treatment i.year i.ward_fe, vce(cluster newid)
		outreg2 using "./logdays_full_tables/woman.tex", keep(every_indexA  treatment)  replace label 

*admin-ward has > median genderquota members in the city		
		reg every_indexA  wom_bin i.year i.ward_fe, vce(cluster newid)
		outreg2 using "./logdays_full_tables/woman.tex", keep(every_indexA  wom_bin)  append label 

		*admin-ward has > mean genderquota members in the city		

		reg every_indexA  wom_mean_bin i.year i.ward_fe	, vce(cluster newid)
		outreg2 using "./logdays_full_tables/woman.tex", keep(every_indexA  wom_mean_bin ) append tex(frag) label
		
		

	
	
	
	
	
