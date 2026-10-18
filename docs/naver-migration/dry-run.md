# 네이버 전환 미리보기(dry-run)

`migration/naver_swap.py --step report` 가 만든 표입니다. DB 는 읽기만 했습니다.
"값이 바뀌는 칸"에는 검증(official-verify.md)을 못 넘어 비우는 칸도 들어 있습니다. 2026-10-18 evan 결정 반영 뒤 다시 만들었습니다(네이버가 뺀 투수 10명 27행은 박스 합계로 넣음). 세 갈래(2008~2013·2014~2019·2020~2026)로 나눠 돌린 결과를 합쳤습니다. 지금 값은 Cloud SQL 에서 읽었습니다.

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
| 2013 | pitcher | 194 | 194 | 0 | 0 | blown_save 194, intentional_base_on_balls 194, save_opportunity 194, total_saves 194, ground_into_double_play 194, ground_outs 194, slugging_percentage 194, on_base_plus_slugging 194 |
| 2013 | team_season_rank | 9 | 9 | 0 | 0 |  |
| 2014 | batter | 304 | 304 | 0 | 0 | runners_in_scoring_position 304, ground_outs 304, p_pa 241, go_ao 217, pinch_hit_batting_average 5, air_outs 2, gw_rbi 2, extended_runs 2 |
| 2014 | pitcher | 210 | 210 | 0 | 0 | blown_save 210, save_opportunity 210, total_saves 210, ground_into_double_play 210, ground_outs 210, on_base_plus_slugging 210, slugging_percentage 209, go_ao 201 |
| 2014 | team_season_rank | 9 | 9 | 0 | 0 |  |
| 2015 | batter | 379 | 378 | 1 | 0 | pinch_hit_batting_average 378, ground_outs 378, p_pa 293, go_ao 267, runners_in_scoring_position 19, gw_rbi 2, air_outs 1, plate_appearance 1 |
| 2015 | pitcher | 244 | 244 | 0 | 0 | blown_save 244, save_opportunity 244, total_saves 244, ground_into_double_play 244, ground_outs 244, go_ao 236, double 22, slugging_percentage 22 |
| 2015 | team_season_rank | 10 | 10 | 0 | 0 |  |
| 2016 | batter | 378 | 377 | 1 | 0 | pinch_hit_batting_average 377, ground_outs 377, extended_runs 377, p_pa 287, go_ao 262, runners_in_scoring_position 9, ground_into_double_play 3, air_outs 1 |
| 2016 | pitcher | 250 | 250 | 0 | 0 | blown_save 250, save_opportunity 250, total_saves 250, ground_into_double_play 250, ground_outs 250, go_ao 245, double 14, intentional_base_on_balls 14 |
| 2016 | team_season_rank | 10 | 10 | 0 | 0 |  |
| 2017 | batter | 360 | 359 | 1 | 0 | ground_outs 359, p_pa 279, go_ao 258, runners_in_scoring_position 56, pinch_hit_batting_average 55, ground_into_double_play 31, extended_runs 31, plate_appearance 28 |
| 2017 | pitcher | 239 | 239 | 0 | 0 | blown_save 239, save_opportunity 239, total_saves 239, ground_into_double_play 239, ground_outs 239, go_ao 236, double 26, intentional_base_on_balls 26 |
| 2017 | team_season_rank | 10 | 10 | 0 | 0 |  |
| 2018 | batter | 331 | 328 | 3 | 0 | pinch_hit_batting_average 328, ground_outs 328, p_pa 273, go_ao 254, runners_in_scoring_position 7, ground_into_double_play 2, extended_runs 2, gw_rbi 1 |
| 2018 | pitcher | 260 | 260 | 0 | 0 | blown_save 260, save_opportunity 260, total_saves 260, ground_into_double_play 260, ground_outs 260, go_ao 255, double 20, intentional_base_on_balls 20 |
| 2018 | team_season_rank | 10 | 10 | 0 | 0 |  |
| 2019 | batter | 353 | 352 | 1 | 0 | ground_outs 352, extended_runs 352, p_pa 290, go_ao 264, runners_in_scoring_position 60, pinch_hit_batting_average 59, gw_rbi 3, air_outs 3 |
| 2019 | pitcher | 257 | 257 | 0 | 0 | blown_save 257, save_opportunity 257, total_saves 257, ground_into_double_play 257, ground_outs 257, go_ao 247, air_outs 24, batting_average 22 |
| 2019 | team_season_rank | 10 | 10 | 0 | 0 |  |
| 2020 | batter | 373 | 370 | 3 | 0 | pinch_hit_batting_average 370, ground_outs 370, extended_runs 370, p_pa 286, go_ao 262, runners_in_scoring_position 7, gw_rbi 3, ground_into_double_play 3 |
| 2020 | pitcher | 283 | 283 | 0 | 0 | blown_save 283, save_opportunity 283, total_saves 283, ground_outs 283, go_ao 275, ground_into_double_play 20, air_outs 20, batting_average_on_balls_in_play 20 |
| 2020 | team_season_rank | 10 | 10 | 0 | 0 |  |
| 2021 | batter | 394 | 389 | 5 | 0 | gw_rbi 389, p_pa 289, pinch_hit_batting_average 29, runners_in_scoring_position 27, ground_outs 3, go_ao 3, extended_runs 3, air_outs 1 |
| 2021 | pitcher | 308 | 308 | 0 | 0 | blown_save 308, save_opportunity 308, total_saves 308, ground_outs 308, go_ao 304, ground_into_double_play 27, batting_average 26, double 26 |
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

## players(결정 5, `naver_players.py --all --dry-run`, 2026-10-18 결정 반영)

| 항목 | 값 |
|---|---|
| 지금 행 | 1,760 |
| 새로 만든 행 | 2,173 (PBP·공식 기록에는 있는데 players 에 없던 선수 413명이 새로 들어감) |
| 네이버 상세 없음 | 15명(네이버가 뺀 투수 10명 포함, PBP 이름·투타만) |
| 사진 없음 | 597명(네이버 이미지가 404) |
| 소속 | 올 시즌 1군 기록 589명, 네이버 상세(올해·은퇴 아님) 154명, 빈 값 1,430명(은퇴 표시면 1군 기록이 있어도 비움) |
| 빈 소속 | 지금 1,022/1,760 → 바꾼 뒤 같은 1,760명 중 1,017, 전체 1,430/2,173 |
| 소속 바뀜(지금 1,760명) | 같음 1,588 · 새로 생김 86 · 비움 79 · 다른 팀 7 |
| 은퇴인데 소속이 보이는 선수 | 0명(박병호·황재균은 2026 은퇴식 특별 출장 기록이 있지만 네이버가 은퇴로 표시해 비움, 공식 기록 행은 그대로) |
| 드래프트(draft_year·draft_order) | 862명(지금 값과 둘 다 있는 861명 모두 같음) |
| 경력(네이버 마지막 학교) | 2,155명 |
| 계약금 | 전부 비움(네이버에 없음) |

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
| salary | 586/588 | 675 | 올 시즌 소속 선수만 |

## 주간 소속 갱신(`naver_players.py --refresh-teams --dry-run`, 2026-10-18)

지금 DB(전환 전) 기준입니다. 다시 받을 선수 1,424명(지금 소속 있음 + 캐시상 현역 + 지난 시즌 이후 기록), 네이버 호출 1,424번 + 시즌 목록 20번, 1.1초 간격이라 약 26분. 소속은 시즌 기록 589 · 선수 상세 154 · 없음 681, 바뀌는 선수 173명입니다.
