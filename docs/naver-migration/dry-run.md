# 네이버 전환 미리보기(dry-run)

`migration/naver_swap.py --step report` 가 만든 표입니다. DB 는 읽기만 했습니다.
"값이 바뀌는 칸"에는 검증(official-verify.md)을 못 넘어 비우는 칸도 들어 있습니다. 생성 2026-10-18. 세 갈래(2008~2013·2014~2019·2020~2026)로 나눠 돌린 결과를 합쳤습니다. 네이버 시즌 API·박스스코어는 그날 받은 값, 지금 값은 Cloud SQL 에서 읽었습니다.

## 2007 이전(결정 1: 지움)

| 표 | 지울 행 |
|---|---|
| kbo_official_batter_stats | 5572 |
| kbo_official_pitcher_stats | 3348 |
| team_season_rank | 195 |

## 시즌별(2008~)

| 시즌 | 표 | 지금 | 새로 | 지울 행 | 넣을 행 | 값이 바뀌는 칸(행 수) |
|---|---|---|---|---|---|---|
| 2008 | batter | 278 | 273 | 5 | 0 | runners_in_scoring_position 273, pinch_hit_batting_average 273, ground_outs 273, air_outs 273, gw_rbi 273, p_pa 217, go_ao 198, plate_appearance 2 |
| 2008 | pitcher | 187 | 187 | 0 | 0 | blown_save 187, save_opportunity 187, total_saves 187, ground_outs 187, go_ao 180, double 86, air_outs 86, slugging_percentage 86 |
| 2008 | team_season_rank | 8 | 8 | 0 | 0 |  |
| 2009 | batter | 278 | 240 | 38 | 0 | runners_in_scoring_position 240, pinch_hit_batting_average 240, ground_outs 240, air_outs 240, gw_rbi 240, p_pa 207, go_ao 187, extended_runs 2 |
| 2009 | pitcher | 192 | 192 | 0 | 0 | blown_save 192, double 192, save_opportunity 192, total_saves 192, ground_into_double_play 192, ground_outs 192, air_outs 192, on_base_percentage 192 |
| 2009 | team_season_rank | 8 | 8 | 0 | 0 |  |
| 2010 | batter | 269 | 269 | 0 | 0 | runners_in_scoring_position 269, pinch_hit_batting_average 269, ground_outs 269, air_outs 269, gw_rbi 269, p_pa 200, go_ao 182, player_name 2 |
| 2010 | pitcher | 191 | 191 | 0 | 0 | blown_save 191, wild_pitch 191, games_finished 191, save_opportunity 191, total_saves 191, ground_into_double_play 191, ground_outs 191, go_ao 187 |
| 2010 | team_season_rank | 8 | 8 | 0 | 0 | gb 5 |
| 2011 | batter | 263 | 216 | 47 | 0 | ground_outs 216, air_outs 216, gw_rbi 216, p_pa 206, go_ao 192, runners_in_scoring_position 134, pinch_hit_batting_average 134, extended_runs 1 |
| 2011 | pitcher | 186 | 186 | 0 | 0 | complete_game 186, shutout 186, blown_save 186, total_batters_faced 186, number_of_pitchers 186, batting_average 186, wild_pitch 186, balk 186 |
| 2011 | team_season_rank | 8 | 8 | 0 | 0 |  |
| 2012 | batter | 284 | 284 | 0 | 0 | pinch_hit_batting_average 284, ground_outs 284, gw_rbi 284, p_pa 226, go_ao 208, runners_in_scoring_position 21, extended_runs 2, air_outs 2 |
| 2012 | pitcher | 188 | 188 | 0 | 0 | blown_save 188, save_opportunity 188, total_saves 188, ground_into_double_play 188, ground_outs 188, air_outs 188, go_ao 185, double 12 |
| 2012 | team_season_rank | 8 | 8 | 0 | 0 |  |
| 2013 | batter | 310 | 309 | 1 | 0 | pinch_hit_batting_average 309, gw_rbi 309, p_pa 250, go_ao 227, runners_in_scoring_position 71, ground_outs 3, extended_runs 3, air_outs 2 |
| 2013 | pitcher | 194 | 193 | 1 | 0 | blown_save 193, intentional_base_on_balls 193, save_opportunity 193, total_saves 193, ground_into_double_play 193, ground_outs 193, slugging_percentage 193, on_base_plus_slugging 193 |
| 2013 | team_season_rank | 9 | 9 | 0 | 0 |  |
| 2014 | batter | 304 | 304 | 0 | 0 | runners_in_scoring_position 304, ground_outs 304, p_pa 241, go_ao 217, pinch_hit_batting_average 5, air_outs 2, gw_rbi 2, extended_runs 2 |
| 2014 | pitcher | 210 | 209 | 1 | 0 | blown_save 209, save_opportunity 209, total_saves 209, ground_into_double_play 209, ground_outs 209, on_base_plus_slugging 209, slugging_percentage 208, go_ao 200 |
| 2014 | team_season_rank | 9 | 9 | 0 | 0 |  |
| 2015 | batter | 379 | 378 | 1 | 0 | pinch_hit_batting_average 378, ground_outs 378, p_pa 293, go_ao 267, runners_in_scoring_position 19, gw_rbi 2, air_outs 1, plate_appearance 1 |
| 2015 | pitcher | 244 | 243 | 1 | 0 | blown_save 243, save_opportunity 243, total_saves 243, ground_into_double_play 243, ground_outs 243, go_ao 235, double 22, slugging_percentage 22 |
| 2015 | team_season_rank | 10 | 10 | 0 | 0 |  |
| 2016 | batter | 378 | 377 | 1 | 0 | pinch_hit_batting_average 377, ground_outs 377, extended_runs 377, p_pa 287, go_ao 262, runners_in_scoring_position 9, ground_into_double_play 3, air_outs 1 |
| 2016 | pitcher | 250 | 249 | 1 | 0 | blown_save 249, save_opportunity 249, total_saves 249, ground_into_double_play 249, ground_outs 249, go_ao 244, double 14, intentional_base_on_balls 14 |
| 2016 | team_season_rank | 10 | 10 | 0 | 0 |  |
| 2017 | batter | 360 | 359 | 1 | 0 | ground_outs 359, p_pa 279, go_ao 258, runners_in_scoring_position 56, pinch_hit_batting_average 55, ground_into_double_play 31, extended_runs 31, plate_appearance 28 |
| 2017 | pitcher | 239 | 237 | 2 | 0 | blown_save 237, save_opportunity 237, total_saves 237, ground_into_double_play 237, ground_outs 237, go_ao 234, double 25, intentional_base_on_balls 25 |
| 2017 | team_season_rank | 10 | 10 | 0 | 0 |  |
| 2018 | batter | 331 | 328 | 3 | 0 | pinch_hit_batting_average 328, ground_outs 328, p_pa 273, go_ao 254, runners_in_scoring_position 7, ground_into_double_play 2, extended_runs 2, gw_rbi 1 |
| 2018 | pitcher | 260 | 257 | 3 | 0 | blown_save 257, save_opportunity 257, total_saves 257, ground_into_double_play 257, ground_outs 257, go_ao 252, double 19, intentional_base_on_balls 19 |
| 2018 | team_season_rank | 10 | 10 | 0 | 0 |  |
| 2019 | batter | 353 | 352 | 1 | 0 | ground_outs 352, extended_runs 352, p_pa 290, go_ao 264, runners_in_scoring_position 60, pinch_hit_batting_average 59, gw_rbi 3, air_outs 3 |
| 2019 | pitcher | 257 | 254 | 3 | 0 | blown_save 254, save_opportunity 254, total_saves 254, ground_into_double_play 254, ground_outs 254, go_ao 244, air_outs 23, batting_average 21 |
| 2019 | team_season_rank | 10 | 10 | 0 | 0 |  |
| 2020 | batter | 373 | 370 | 3 | 0 | pinch_hit_batting_average 370, ground_outs 370, extended_runs 370, p_pa 286, go_ao 262, runners_in_scoring_position 7, gw_rbi 3, ground_into_double_play 3 |
| 2020 | pitcher | 283 | 275 | 8 | 0 | blown_save 275, save_opportunity 275, total_saves 275, ground_outs 275, go_ao 267, ground_into_double_play 20, air_outs 20, batting_average_on_balls_in_play 20 |
| 2020 | team_season_rank | 10 | 10 | 0 | 0 |  |
| 2021 | batter | 394 | 389 | 5 | 0 | gw_rbi 389, p_pa 289, pinch_hit_batting_average 29, runners_in_scoring_position 27, ground_outs 3, go_ao 3, extended_runs 3, air_outs 1 |
| 2021 | pitcher | 308 | 301 | 7 | 0 | blown_save 301, save_opportunity 301, total_saves 301, ground_outs 301, go_ao 297, ground_into_double_play 27, batting_average 26, double 26 |
| 2021 | team_season_rank | 10 | 10 | 0 | 0 |  |
| 2022 | batter | 356 | 355 | 1 | 0 | ground_outs 355, p_pa 278, pinch_hit_batting_average 14, runners_in_scoring_position 12, go_ao 3, gw_rbi 2, air_outs 1, extended_runs 1 |
| 2022 | pitcher | 281 | 281 | 0 | 0 | blown_save 281, save_opportunity 281, total_saves 281, ground_into_double_play 281, ground_outs 11, double 10, go_ao 10, slugging_percentage 10 |
| 2022 | team_season_rank | 10 | 10 | 0 | 0 |  |
| 2023 | batter | 366 | 366 | 0 | 0 | ground_outs 366, p_pa 293, pinch_hit_batting_average 9, runners_in_scoring_position 8, go_ao 3, air_outs 2, extended_runs 2, gw_rbi 1 |
| 2023 | pitcher | 285 | 285 | 0 | 0 | blown_save 285, save_opportunity 285, total_saves 285, ground_into_double_play 285, ground_outs 12, go_ao 12, air_outs 11, batting_average 10 |
| 2023 | team_season_rank | 10 | 10 | 0 | 0 |  |
| 2024 | batter | 386 | 386 | 0 | 0 | ground_outs 386, p_pa 298, go_ao 276, runners_in_scoring_position 40, pinch_hit_batting_average 40, extended_runs 2, gw_rbi 2, ground_into_double_play 1 |
| 2024 | pitcher | 291 | 291 | 0 | 0 | blown_save 291, save_opportunity 291, total_saves 291, ground_outs 291, go_ao 38, ground_into_double_play 37, batting_average_on_balls_in_play 37, batting_average 36 |
| 2024 | team_season_rank | 10 | 10 | 0 | 0 |  |
| 2025 | batter | 398 | 398 | 0 | 0 | strikeout_per_pa 299, base_on_balls_per_pa 299, p_pa 299, runners_in_scoring_position 23, pinch_hit_batting_average 23, gw_rbi 3, ground_outs 2, go_ao 2 |
| 2025 | pitcher | 281 | 281 | 0 | 0 | blown_save 281, save_opportunity 281, total_saves 281, strikeout_per_pa 281, base_on_balls_per_pa 281, ground_outs 11, go_ao 11, ground_into_double_play 10 |
| 2025 | team_season_rank | 10 | 10 | 0 | 0 |  |
| 2026 | batter | 364 | 364 | 0 | 0 | ground_outs 364, p_pa 291, go_ao 266, runners_in_scoring_position 19, pinch_hit_batting_average 18, ground_into_double_play 2, extended_runs 2, gw_rbi 1 |
| 2026 | pitcher | 296 | 296 | 0 | 0 | blown_save 296, save_opportunity 296, total_saves 296, ground_into_double_play 296, ground_outs 296, go_ao 290, batting_average 27, double 27 |
| 2026 | team_season_rank | 10 | 10 | 0 | 0 |  |

## players(결정 5, `naver_players.py --all --dry-run`)

| 항목 | 값 |
|---|---|
| 지금 행 | 1,760 |
| 새로 만든 행 | 2,173 (PBP·공식 기록에는 있는데 players 에 없던 선수 413명이 새로 들어감) |
| 네이버 상세 없음 | 15명(네이버가 뺀 투수 10명 포함, PBP 이름·투타만) |
| 사진 없음 | 597명(네이버 이미지가 404) |

둘 다 값이 있는 행끼리 지금 값과 같은 비율입니다(괄호는 새로 비는 행).

| 칸 | 같음 | 새로 비움 | 메모 |
|---|---|---|---|
| throw | 1,499/1,499 (100%) | 253 | 2008 이후 던지지 않은 은퇴 야수 |
| bat | 1,435/1,437 | 321 | 타석이 없거나 한쪽 80% 미만 |
| position | 1,512/1,515 | 75 | |
| birthday | 1,746/1,747 | 13 | |
| height | 1,711/1,747 | 13 | 네이버가 최근 값 |
| weight | 1,666/1,747 | 13 | 네이버가 최근 값 |
| back_number | 1,306/1,605 | 11 | 은퇴 선수는 네이버가 마지막 시즌 번호 |
| team_id | 535/542 | 196 | 올 시즌 1군 기록이 없는 선수는 소속이 빔(등록 명단이 네이버에 없음) |
| salary | 586/588 | 675 | 올 시즌 1군 선수만 |
| career·draft_year·draft_order·signing_bonus | - | 전부 | 결정 5(다) |
