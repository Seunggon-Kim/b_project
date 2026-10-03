# 주간 계산 비교(D1 기준 A · MySQL 기준 B)

- self_park_factor: 같음
- kbo_woba_weights_by_season: 같음
- wrc_plus_comparison: 다름
  wrc_plus_comparison: A 에만 261행, B 에만 261행 (전체 A 3231 / B 3231)
     A: {'OBP_denom': 596, 'PA': 596, 'batter_ID': 72133, 'home_run_pf': 867, 'lg_wOBA': 0.353068623, 'pf_half': 933.5, 'pf_home': 867, 'pf_weighted': 944.814144737, 'season': 2017, 'wOBA': 0.405134978, 'wOBA_scale': 1.103753, 'wRAA_FG': 28.114576312, 'wRC_half': 141.58701546, 'wRC_home': 148.23701546, 'wRC_weighted': 140.455600987, 'wpf_run': 944.814144737}
     A: {'OBP_denom': 320, 'PA': 321, 'batter_ID': 99606, 'home_run_pf': 867, 'lg_wOBA': 0.353068623, 'pf_half': 933.5, 'pf_home': 867, 'pf_weighted': 958.546296296, 'season': 2017, 'wOBA': 0.378241006, 'wOBA_scale': 1.103753, 'wRAA_FG': 7.32078206, 'wRC_half': 123.540906755, 'wRC_home': 130.190906755, 'wRC_weighted': 121.036277125, 'wpf_run': 958.546296296}
     A: {'OBP_denom': 85, 'PA': 85, 'batter_ID': 74823, 'home_run_pf': 867, 'lg_wOBA': 0.353068623, 'pf_half': 933.5, 'pf_home': 867, 'pf_weighted': 943.886363636, 'season': 2017, 'wOBA': 0.287528318, 'wOBA_scale': 1.103753, 'wRAA_FG': -5.047257782, 'wRC_half': 62.671837534, 'wRC_home': 69.321837534, 'wRC_weighted': 61.63320117, 'wpf_run': 943.886363636}
     B: {'OBP_denom': 282, 'PA': 287, 'batter_ID': 50458, 'home_run_pf': 1171, 'lg_wOBA': 0.348618194, 'pf_half': 1085.5, 'pf_home': 1171, 'pf_weighted': 1094.418300654, 'season': 2020, 'wOBA': 0.276930128, 'wOBA_scale': 1.120787, 'wRAA_FG': -18.357167938, 'wRC_half': 42.736765376, 'wRC_home': 34.186765376, 'wRC_weighted': 41.844935311, 'wpf_run': 1094.418300654}
     B: {'OBP_denom': 217, 'PA': 217, 'batter_ID': 50469, 'home_run_pf': 1171, 'lg_wOBA': 0.348618194, 'pf_half': 1085.5, 'pf_home': 1171, 'pf_weighted': 1079.713636364, 'season': 2020, 'wOBA': 0.289096171, 'wOBA_scale': 1.120787, 'wRAA_FG': -11.524294273, 'wRC_half': 51.003793988, 'wRC_home': 42.453793988, 'wRC_weighted': 51.582430352, 'wpf_run': 1079.713636364}
     B: {'OBP_denom': 354, 'PA': 354, 'batter_ID': 52526, 'home_run_pf': 1112, 'lg_wOBA': 0.333375438, 'pf_half': 1056, 'pf_home': 1112, 'pf_weighted': 1054.641456583, 'season': 2022, 'wOBA': 0.321630198, 'wOBA_scale': 1.206711, 'wRAA_FG': -3.445576607, 'wRC_half': 86.049504288, 'wRC_home': 80.449504288, 'wRC_weighted': 86.18535863, 'wpf_run': 1054.641456583}
- weighted_pf_by_batter_season: 다름
  weighted_pf_by_batter_season: A 에만 266행, B 에만 266행 (전체 A 5008 / B 5008)
     A: {'batter_ID': 72133, 'home_hr_pf': 700, 'home_pa_n': 331, 'home_run_pf': 867, 'home_share': 55.5, 'home_slg_pf': 945, 'home_stadium': '서울종합운동장 야구장', 'hr_pf_diff_pct': 23.45, 'n_PA': 596, 'run_pf_diff': 77.814144737, 'run_pf_diff_pct': 8.98, 'season': 2017, 'wpf_hr': 864.134868421, 'wpf_run': 944.814144737, 'wpf_slg': 974.953947368}
     A: {'batter_ID': 99606, 'home_hr_pf': 700, 'home_pa_n': 158, 'home_run_pf': 867, 'home_share': 49.2, 'home_slg_pf': 945, 'home_stadium': '서울종합운동장 야구장', 'hr_pf_diff_pct': 27.42, 'n_PA': 321, 'run_pf_diff': 91.546296296, 'run_pf_diff_pct': 10.56, 'season': 2017, 'wpf_hr': 891.966049383, 'wpf_run': 958.546296296, 'wpf_slg': 980.033950617}
     A: {'batter_ID': 74823, 'home_hr_pf': 700, 'home_pa_n': 50, 'home_run_pf': 867, 'home_share': 58.8, 'home_slg_pf': 945, 'home_stadium': '서울종합운동장 야구장', 'hr_pf_diff_pct': 22.14, 'n_PA': 85, 'run_pf_diff': 76.886363636, 'run_pf_diff_pct': 8.87, 'season': 2017, 'wpf_hr': 855, 'wpf_run': 943.886363636, 'wpf_slg': 973.693181818}
     B: {'batter_ID': 50458, 'home_hr_pf': 1303, 'home_pa_n': 166, 'home_run_pf': 1171, 'home_share': 57.8, 'home_slg_pf': 1046, 'home_stadium': '대구 삼성 라이온즈파크', 'hr_pf_diff_pct': -10.74, 'n_PA': 287, 'run_pf_diff': -76.581699346, 'run_pf_diff_pct': -6.54, 'season': 2020, 'wpf_hr': 1163.117647059, 'wpf_run': 1094.418300654, 'wpf_slg': 1025.290849673}
     B: {'batter_ID': 50469, 'home_hr_pf': 1303, 'home_pa_n': 99, 'home_run_pf': 1171, 'home_share': 45.6, 'home_slg_pf': 1046, 'home_stadium': '대구 삼성 라이온즈파크', 'hr_pf_diff_pct': -13.14, 'n_PA': 217, 'run_pf_diff': -91.286363636, 'run_pf_diff_pct': -7.8, 'season': 2020, 'wpf_hr': 1131.727272727, 'wpf_run': 1079.713636364, 'wpf_slg': 1020.877272727}
     B: {'batter_ID': 52526, 'home_hr_pf': 967, 'home_pa_n': 183, 'home_run_pf': 1112, 'home_share': 51.7, 'home_slg_pf': 1020, 'home_stadium': '사직야구장', 'hr_pf_diff_pct': 2.68, 'n_PA': 354, 'run_pf_diff': -57.358543417, 'run_pf_diff_pct': -5.16, 'season': 2022, 'wpf_hr': 992.868347339, 'wpf_run': 1054.641456583, 'wpf_slg': 1009.955182073}
- re24_matrix_by_season: 같음
- kbo_run_values_by_season: 같음

## 차이의 원인과 결정(2026-10-03)

- 두 표의 차이는 D1 의 선수 ID 표기 때문입니다. D1 경기 기록에는 같은 선수가 `72133` 과 `72133.0` 으로
  섞여 있습니다(예: 2017년 72133번 타자 2,530타석 중 17타석). D1 기준 계산은 `.0` 타석을 다른 선수로 보고
  빠뜨리고, MySQL 은 1단계에서 ID 를 정수로 통일해 모두 셉니다.
- `.0` 표기가 있는 시즌(2008~2011, 2017, 2019, 2020, 2022)과 차이가 난 시즌이 같고, 없는 2023·2024 는 차이가 없습니다.
- wOBA 가중치·RE24·득점가치·파크팩터는 같습니다(파크팩터는 계산 시각 열만 달라 비교에서 뺐습니다).
- 결정: MySQL 기준 값(빠진 타석이 들어간 값)을 받아들입니다(evan, 2026-10-03). 주간 작업을 MySQL 기준으로
  켜면 사이트의 wRC+·선수별 가중 파크팩터가 해당 시즌 일부 타자에서 조금 바뀝니다.
