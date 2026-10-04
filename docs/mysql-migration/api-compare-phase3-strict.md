# API 대조

- A: https://kbo-api-stg-d1.bstats-baseball.workers.dev
- B: https://kbo-api.bstats-baseball.workers.dev
- URL 101개
- 배열 순서: 견줌
- 다른 URL 44개

## /leaders

차이 8건

- $.pitcher.era[1].player_id: "55633" ≠ "55268"
- $.pitcher.era[1].name: "올러" ≠ "최민석"
- $.pitcher.era[1].team: "KIA" ≠ "두산"
- $.pitcher.era[1].code: "HT" ≠ "OB"
- $.pitcher.era[2].player_id: "55268" ≠ "55633"
- $.pitcher.era[2].name: "최민석" ≠ "올러"
- $.pitcher.era[2].team: "두산" ≠ "KIA"
- $.pitcher.era[2].code: "OB" ≠ "HT"

## /leaders?season=2015

차이 4건

- $.pitcher.k[4].player_id: "74454" ≠ "63938"
- $.pitcher.k[4].name: "윤성환" ≠ "해커"
- $.pitcher.k[4].team: "삼성" ≠ "NC"
- $.pitcher.k[4].code: "SS" ≠ "NC"

## /leaders?season=2025

차이 8건

- $.pitcher.era[1].player_id: "54833" ≠ "54640"
- $.pitcher.era[1].name: "앤더슨" ≠ "네일"
- $.pitcher.era[1].team: "SSG" ≠ "KIA"
- $.pitcher.era[1].code: "SK" ≠ "HT"
- $.pitcher.era[2].player_id: "54640" ≠ "54833"
- $.pitcher.era[2].name: "네일" ≠ "앤더슨"
- $.pitcher.era[2].team: "KIA" ≠ "SSG"
- $.pitcher.era[2].code: "HT" ≠ "SK"

## /leaders?season=2026

차이 8건

- $.pitcher.era[1].player_id: "55633" ≠ "55268"
- $.pitcher.era[1].name: "올러" ≠ "최민석"
- $.pitcher.era[1].team: "KIA" ≠ "두산"
- $.pitcher.era[1].code: "HT" ≠ "OB"
- $.pitcher.era[2].player_id: "55268" ≠ "55633"
- $.pitcher.era[2].name: "최민석" ≠ "올러"
- $.pitcher.era[2].team: "두산" ≠ "KIA"
- $.pitcher.era[2].code: "OB" ≠ "HT"

## /stats/pitchers?season=2008&limit=50&min_ip=30

차이 386건(앞 20건)

- $.pitchers[24].player_id: "75537" ≠ "91848"
- $.pitchers[24].player_name: "조정훈" ≠ "김원형"
- $.pitchers[24].player_team: "롯데" ≠ "SK"
- $.pitchers[24].games: 14 ≠ 42
- $.pitchers[24].wins: 5 ≠ 12
- $.pitchers[24].losses: 3 ≠ 6
- $.pitchers[24].save: 0 ≠ 2
- $.pitchers[24].hold: 1 ≠ 2
- $.pitchers[24].winning_percentage: 0.625 ≠ 0.667
- $.pitchers[24].innings_pitched: "80" ≠ "74 1/3"
- $.pitchers[24].hits: 84 ≠ 73
- $.pitchers[24].base_on_balls: 18 ≠ 23
- $.pitchers[24].hit_by_pitch: 3 ≠ 5
- $.pitchers[24].strikeout: 54 ≠ 41
- $.pitchers[24].run: 35 ≠ 28
- $.pitchers[24].earned_run: 28 ≠ 26
- $.pitchers[24].walks_plus_hits_per_inning_pitched: 1.28 ≠ 1.29
- $.pitchers[24].complete_game: 1 ≠ 0
- $.pitchers[24].shutout: 1 ≠ 0
- $.pitchers[24].quality_start: 8 ≠ 0

## /stats/pitchers?season=2012&limit=50&min_ip=30

차이 480건(앞 20건)

- $.pitchers[2].player_id: "62263" ≠ "72463"
- $.pitchers[2].player_name: "변시원" ≠ "안지만"
- $.pitchers[2].player_team: "두산" ≠ "삼성"
- $.pitchers[2].games: 31 ≠ 56
- $.pitchers[2].wins: 4 ≠ 1
- $.pitchers[2].losses: 0 ≠ 2
- $.pitchers[2].save: 1 ≠ 0
- $.pitchers[2].hold: 2 ≠ 28
- $.pitchers[2].winning_percentage: 1 ≠ 0.333
- $.pitchers[2].innings_pitched: "31 2/3" ≠ "63 1/3"
- $.pitchers[2].hits: 15 ≠ 42
- $.pitchers[2].home_run: 0 ≠ 1
- $.pitchers[2].base_on_balls: 11 ≠ 20
- $.pitchers[2].hit_by_pitch: 3 ≠ 0
- $.pitchers[2].strikeout: 18 ≠ 58
- $.pitchers[2].run: 6 ≠ 12
- $.pitchers[2].earned_run: 6 ≠ 12
- $.pitchers[2].walks_plus_hits_per_inning_pitched: 0.82 ≠ 0.98
- $.pitchers[2].blown_save: 0 ≠ 1
- $.pitchers[2].total_batters_faced: 118 ≠ 246

## /stats/batters?season=2019&limit=50&min_pa=100

차이 725건(앞 20건)

- $.batters[4].player_id: "68050" ≠ "67341"
- $.batters[4].player_name: "강백호" ≠ "이정후"
- $.batters[4].player_team: "KT" ≠ "키움"
- $.batters[4].games: 116 ≠ 140
- $.batters[4].plate_appearance: 505 ≠ 630
- $.batters[4].at_bat: 438 ≠ 574
- $.batters[4].run: 72 ≠ 91
- $.batters[4].single: 147 ≠ 193
- $.batters[4].double: 29 ≠ 31
- $.batters[4].triple: 1 ≠ 10
- $.batters[4].home_run: 13 ≠ 6
- $.batters[4].total_bases: 217 ≠ 262
- $.batters[4].run_batted_in: 65 ≠ 68
- $.batters[4].sacrifice_bunts: 0 ≠ 3
- $.batters[4].base_on_balls: 61 ≠ 45
- $.batters[4].intentional_base_on_balls: 4 ≠ 0
- $.batters[4].hit_by_pitch: 2 ≠ 4
- $.batters[4].strikeout: 87 ≠ 40
- $.batters[4].ground_into_double_play: 11 ≠ 15
- $.batters[4].slugging_percentage: 0.495 ≠ 0.456

## /stats/pitchers?season=2019&limit=50&min_ip=30

차이 337건(앞 20건)

- $.pitchers[18].player_id: "62951" ≠ "63342"
- $.pitchers[18].player_name: "이형범" ≠ "조상우"
- $.pitchers[18].player_team: "두산" ≠ "키움"
- $.pitchers[18].games: 67 ≠ 48
- $.pitchers[18].wins: 6 ≠ 2
- $.pitchers[18].losses: 3 ≠ 4
- $.pitchers[18].save: 19 ≠ 20
- $.pitchers[18].hold: 10 ≠ 8
- $.pitchers[18].winning_percentage: 0.667 ≠ 0.333
- $.pitchers[18].innings_pitched: "61" ≠ "47 1/3"
- $.pitchers[18].hits: 57 ≠ 45
- $.pitchers[18].home_run: 4 ≠ 3
- $.pitchers[18].base_on_balls: 19 ≠ 8
- $.pitchers[18].hit_by_pitch: 9 ≠ 2
- $.pitchers[18].strikeout: 31 ≠ 46
- $.pitchers[18].run: 25 ≠ 15
- $.pitchers[18].earned_run: 18 ≠ 14
- $.pitchers[18].walks_plus_hits_per_inning_pitched: 1.25 ≠ 1.12
- $.pitchers[18].total_batters_faced: 258 ≠ 192
- $.pitchers[18].number_of_pitchers: 927 ≠ 710

## /stats/batters?season=2025&limit=50&min_pa=100

차이 592건(앞 20건)

- $.batters[8].player_id: "62404" ≠ "51203"
- $.batters[8].player_name: "구자욱" ≠ "안재석"
- $.batters[8].player_team: "삼성" ≠ "두산"
- $.batters[8].games: 142 ≠ 35
- $.batters[8].plate_appearance: 616 ≠ 147
- $.batters[8].at_bat: 529 ≠ 135
- $.batters[8].run: 106 ≠ 25
- $.batters[8].single: 169 ≠ 43
- $.batters[8].double: 43 ≠ 16
- $.batters[8].triple: 2 ≠ 1
- $.batters[8].home_run: 19 ≠ 4
- $.batters[8].total_bases: 273 ≠ 73
- $.batters[8].run_batted_in: 96 ≠ 20
- $.batters[8].sacrifice_fly: 8 ≠ 0
- $.batters[8].base_on_balls: 73 ≠ 11
- $.batters[8].intentional_base_on_balls: 7 ≠ 1
- $.batters[8].hit_by_pitch: 5 ≠ 0
- $.batters[8].strikeout: 91 ≠ 27
- $.batters[8].ground_into_double_play: 9 ≠ 3
- $.batters[8].slugging_percentage: 0.516 ≠ 0.541

## /stats/pitchers?season=2025&limit=50&min_ip=30

차이 384건(앞 20건)

- $.pitchers[6].player_id: "65769" ≠ "61666"
- $.pitchers[6].player_name: "김범수" ≠ "한승혁"
- $.pitchers[6].games: 73 ≠ 71
- $.pitchers[6].wins: 2 ≠ 3
- $.pitchers[6].losses: 1 ≠ 3
- $.pitchers[6].save: 2 ≠ 3
- $.pitchers[6].hold: 6 ≠ 16
- $.pitchers[6].winning_percentage: 0.667 ≠ 0.5
- $.pitchers[6].innings_pitched: "48" ≠ "64"
- $.pitchers[6].hits: 30 ≠ 56
- $.pitchers[6].home_run: 0 ≠ 4
- $.pitchers[6].base_on_balls: 22 ≠ 23
- $.pitchers[6].hit_by_pitch: 4 ≠ 7
- $.pitchers[6].strikeout: 41 ≠ 53
- $.pitchers[6].run: 17 ≠ 18
- $.pitchers[6].earned_run: 12 ≠ 16
- $.pitchers[6].walks_plus_hits_per_inning_pitched: 1.08 ≠ 1.23
- $.pitchers[6].blown_save: 0 ≠ 5
- $.pitchers[6].total_batters_faced: 195 ≠ 269
- $.pitchers[6].number_of_pitchers: 780 ≠ 1002

## /stats/batters?season=2026&limit=50&min_pa=100

차이 797건(앞 20건)

- $.batters[0].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"
- $.batters[1].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"
- $.batters[2].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"
- $.batters[3].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"
- $.batters[4].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"
- $.batters[5].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"
- $.batters[6].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"
- $.batters[7].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"
- $.batters[8].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"
- $.batters[9].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"
- $.batters[10].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"
- $.batters[11].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"
- $.batters[12].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"
- $.batters[13].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"
- $.batters[14].player_id: "72443" ≠ "67449"
- $.batters[14].player_name: "최형우" ≠ "김성윤"
- $.batters[14].games: 130 ≠ 118
- $.batters[14].plate_appearance: 555 ≠ 466
- $.batters[14].at_bat: 475 ≠ 398
- $.batters[14].run: 61 ≠ 77

## /stats/pitchers?season=2026&limit=50&min_ip=30

차이 384건(앞 20건)

- $.pitchers[0].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[1].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[2].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[3].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[4].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[5].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[6].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[7].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[8].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[9].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[10].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[11].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[12].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[13].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[14].player_id: "52992" ≠ "54263"
- $.pitchers[14].player_name: "이준혁" ≠ "김택연"
- $.pitchers[14].player_team: "NC" ≠ "두산"
- $.pitchers[14].games: 31 ≠ 51
- $.pitchers[14].wins: 0 ≠ 3
- $.pitchers[14].losses: 1 ≠ 3

## /stats/batters?season=2025&limit=30&team_ids=KIA,LG

차이 250건(앞 20건)

- $.batters[4].player_id: "65207" ≠ "53123"
- $.batters[4].player_name: "신민재" ≠ "오스틴"
- $.batters[4].games: 135 ≠ 116
- $.batters[4].plate_appearance: 538 ≠ 499
- $.batters[4].at_bat: 463 ≠ 425
- $.batters[4].run: 87 ≠ 82
- $.batters[4].single: 145 ≠ 133
- $.batters[4].double: 15 ≠ 25
- $.batters[4].triple: 7 ≠ 1
- $.batters[4].home_run: 1 ≠ 31
- $.batters[4].total_bases: 177 ≠ 253
- $.batters[4].run_batted_in: 61 ≠ 95
- $.batters[4].sacrifice_bunts: 6 ≠ 0
- $.batters[4].sacrifice_fly: 4 ≠ 11
- $.batters[4].base_on_balls: 62 ≠ 61
- $.batters[4].intentional_base_on_balls: 0 ≠ 7
- $.batters[4].hit_by_pitch: 3 ≠ 2
- $.batters[4].strikeout: 57 ≠ 62
- $.batters[4].ground_into_double_play: 7 ≠ 11
- $.batters[4].slugging_percentage: 0.382 ≠ 0.595

## /stats/pitchers?season=2019&limit=30&team_ids=두산,키움

차이 108건(앞 20건)

- $.pitchers[2].player_id: "68200" ≠ "65398"
- $.pitchers[2].player_name: "김민규" ≠ "임규빈"
- $.pitchers[2].player_team: "두산" ≠ "키움"
- $.pitchers[2].innings_pitched: "2" ≠ "1"
- $.pitchers[2].hits: 2 ≠ 1
- $.pitchers[2].base_on_balls: 1 ≠ 0
- $.pitchers[2].strikeout: 0 ≠ 2
- $.pitchers[2].walks_plus_hits_per_inning_pitched: 1.5 ≠ 1
- $.pitchers[2].total_batters_faced: 8 ≠ 4
- $.pitchers[2].number_of_pitchers: 24 ≠ 13
- $.pitchers[2].batting_average: 0.286 ≠ 0.25
- $.pitchers[2].double: 0 ≠ 1
- $.pitchers[2].games_finished: 1 ≠ 0
- $.pitchers[2].ground_into_double_play: 2 ≠ 0
- $.pitchers[2].ground_outs: 4 ≠ 0
- $.pitchers[2].go_ao: "4.00" ≠ "0.00"
- $.pitchers[2].batting_average_on_balls_in_play: 0.286 ≠ 0.5
- $.pitchers[2].p_g: 24 ≠ 13
- $.pitchers[2].p_ip: 12 ≠ 13
- $.pitchers[2].k_9: 0 ≠ 18

## /stats/team_range?start=20190501&end=20190531

차이 6건

- $.batting: 길이 11 ≠ 10
- $.batting[6].team: "SSG" ≠ "SK"
- $.batting[6].G: 0 ≠ 26
- $.pitching: 길이 11 ≠ 10
- $.pitching[1].team: "SSG" ≠ "SK"
- $.pitching[1].G: 0 ≠ 26

## /stats/team_range?start=2012-04-07&end=2012-05-07

차이 30건(앞 20건)

- $.pitching[1].team: "두산" ≠ "롯데"
- $.pitching[1].G: 21 ≠ 22
- $.pitching[1].IP_outs: 558 ≠ 589
- $.pitching[1].IP: 186 ≠ 196.3
- $.pitching[1].IP_text: "186" ≠ "196 1/3"
- $.pitching[1].H: 174 ≠ 189
- $.pitching[1].R: 88 ≠ 93
- $.pitching[1].BB: 88 ≠ 73
- $.pitching[1].SO: 150 ≠ 139
- $.pitching[1].HR: 7 ≠ 19
- $.pitching[1].AB_against: 682 ≠ 739
- $.pitching[1].WHIP: 1.409 ≠ 1.334
- $.pitching[1].K9: 7.26 ≠ 6.37
- $.pitching[1].BB9: 4.26 ≠ 3.35
- $.pitching[1].AVG_against: 0.255 ≠ 0.256
- $.pitching[2].team: "롯데" ≠ "두산"
- $.pitching[2].G: 22 ≠ 21
- $.pitching[2].IP_outs: 589 ≠ 558
- $.pitching[2].IP: 196.3 ≠ 186
- $.pitching[2].IP_text: "196 1/3" ≠ "186"

## /stats/batters?season=2025&limit=-1

차이 5714건(앞 20건)

- $.batters[0].player_id: "62558" ≠ "51762"
- $.batters[0].player_name: "김준태" ≠ "장규현"
- $.batters[0].player_team: "LG" ≠ "한화"
- $.batters[0].pinch_hit_batting_average: 1 ≠ 0
- $.batters[0].p_pa: 3 ≠ 3.5
- $.batters[0].team_id: "LG" ≠ "한화"
- $.batters[2].player_id: "51762" ≠ "62558"
- $.batters[2].player_name: "장규현" ≠ "김준태"
- $.batters[2].player_team: "한화" ≠ "LG"
- $.batters[2].pinch_hit_batting_average: 0 ≠ 1
- $.batters[2].p_pa: 3.5 ≠ 3
- $.batters[2].team_id: "한화" ≠ "LG"
- $.batters[5].player_id: "54815" ≠ "54305"
- $.batters[5].player_name: "정현승" ≠ "이재상"
- $.batters[5].player_team: "SSG" ≠ "키움"
- $.batters[5].games: 3 ≠ 2
- $.batters[5].double: 1 ≠ 0
- $.batters[5].total_bases: 2 ≠ 1
- $.batters[5].strikeout: 0 ≠ 1
- $.batters[5].slugging_percentage: 1 ≠ 0.5

## /players/search?q=김

차이 837건(앞 20건)

- $.players[0].player_id: "50304" ≠ "50115"
- $.players[0].player_name: "김병휘" ≠ "김수인"
- $.players[0].team_id: "키움" ≠ "LG"
- $.players[0].back_number: 23 ≠ 16
- $.players[0].birthday: 20010216 ≠ 19971019
- $.players[0].weight: 79 ≠ 85
- $.players[0].career: "효제초-홍은중-장충고" ≠ "광주화정초-자양중-신일고-중앙대-LG"
- $.players[0].draft_year: "20키움" ≠ "20LG"
- $.players[0].draft_order: "4라운드 37순위" ≠ "20 LG 육성선수"
- $.players[0].signing_bonus: 70000000 ≠ null
- $.players[0].salary: 35000000 ≠ 30000000
- $.players[0].image_url: "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle/2026/50304.jpg" ≠ "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle/2026/50115.jpg"
- $.players[0].created_at: "2026-01-24 18:45:14" ≠ "2026-08-22 11:41:43"
- $.players[0].updated_at: "2026-08-29 01:45:50" ≠ "2026-08-22 11:41:43"
- $.players[1].player_id: "50458" ≠ "50157"
- $.players[1].player_name: "김지찬" ≠ "김윤식"
- $.players[1].team_id: "삼성" ≠ "LG"
- $.players[1].back_number: 58 ≠ 47
- $.players[1].position: "외야수" ≠ "투수"
- $.players[1].throw: "R" ≠ "L"

## /players/53375

차이 1건

- $.pitcher_seasons[0].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"

## /players/77829/usage?season=2010

차이 18건

- $.total_pitches: 2768 ≠ 2891
- $.total_l: 768 ≠ 812
- $.total_r: 2000 ≠ 2079
- $.usage[0].count: 1521 ≠ 1587
- $.usage[0].usage_l: 55.2 ≠ 55.3
- $.usage[0].usage_r: 54.8 ≠ 54.7
- $.usage[1].count: 796 ≠ 849
- $.usage[1].usage_all: 28.8 ≠ 29.4
- $.usage[1].usage_l: 30.9 ≠ 31.4
- $.usage[1].usage_r: 28 ≠ 28.6
- $.usage[2].count: 231 ≠ 232
- $.usage[2].usage_all: 8.3 ≠ 8
- $.usage[2].usage_l: 4 ≠ 3.8
- $.usage[2].usage_r: 10 ≠ 9.7
- $.usage[3].count: 212 ≠ 215
- $.usage[3].usage_all: 7.7 ≠ 7.4
- $.usage[3].usage_l: 9.9 ≠ 9.5
- $.usage[3].usage_r: 6.8 ≠ 6.6

## /games?season=2008&limit=30

차이 81건(앞 20건)

- $.games[15].game_id: "20081004LTLG0" ≠ "20081004SKSS0"
- $.games[15].home_team_id: "LG" ≠ "삼성"
- $.games[15].away_team_id: "롯데" ≠ "SK"
- $.games[15].home_score: 4 ≠ 6
- $.games[15].away_score: 0 ≠ 3
- $.games[15].stadium: "잠실" ≠ "시민"
- $.games[15].home_team: "LG 트윈스" ≠ "삼성 라이온즈"
- $.games[15].away_team: "롯데 자이언츠" ≠ "SK 와이번스"
- $.games[17].game_id: "20081004SKSS0" ≠ "20081004WOHH0"
- $.games[17].home_team_id: "삼성" ≠ "한화"
- $.games[17].away_team_id: "SK" ≠ "우리"
- $.games[17].home_score: 6 ≠ 5
- $.games[17].stadium: "시민" ≠ "한밭"
- $.games[17].home_team: "삼성 라이온즈" ≠ "한화 이글스"
- $.games[17].away_team: "SK 와이번스" ≠ "우리 히어로즈"
- $.games[18].game_id: "20081004WOHH0" ≠ "20081004LTLG0"
- $.games[18].home_team_id: "한화" ≠ "LG"
- $.games[18].away_team_id: "우리" ≠ "롯데"
- $.games[18].home_score: 5 ≠ 4
- $.games[18].away_score: 3 ≠ 0

## /games?season=2019&limit=30

차이 77건(앞 20건)

- $.games[17].game_id: "20190929SKHH02019" ≠ "20190929WOLT02019"
- $.games[17].home_team_id: "한화" ≠ "롯데"
- $.games[17].away_team_id: "SK" ≠ "키움"
- $.games[17].home_score: 0 ≠ 1
- $.games[17].away_score: 2 ≠ 4
- $.games[17].stadium: "한밭" ≠ "사직"
- $.games[17].home_team: "한화 이글스" ≠ "롯데 자이언츠"
- $.games[17].away_team: "SK 와이번스" ≠ "키움 히어로즈"
- $.games[19].game_id: "20190929WOLT02019" ≠ "20190929SKHH02019"
- $.games[19].home_team_id: "롯데" ≠ "한화"
- $.games[19].away_team_id: "키움" ≠ "SK"
- $.games[19].home_score: 1 ≠ 0
- $.games[19].away_score: 4 ≠ 2
- $.games[19].stadium: "사직" ≠ "한밭"
- $.games[19].home_team: "롯데 자이언츠" ≠ "한화 이글스"
- $.games[19].away_team: "키움 히어로즈" ≠ "SK 와이번스"
- $.games[20].game_id: "20190928HHOB02019" ≠ "20190928NCKT02019"
- $.games[20].home_team_id: "두산" ≠ "KT"
- $.games[20].away_team_id: "한화" ≠ "NC"
- $.games[20].home_score: 7 ≠ 5

## /games?season=2025&limit=30

차이 40건(앞 20건)

- $.games[20].game_id: "20251001HHSK02025" ≠ "20251001KTHT02025"
- $.games[20].home_team_id: "SSG" ≠ "KIA"
- $.games[20].away_team_id: "한화" ≠ "KT"
- $.games[20].home_score: 6 ≠ 3
- $.games[20].away_score: 5 ≠ 9
- $.games[20].stadium: "문학" ≠ "광주"
- $.games[20].home_team: "SSG 랜더스" ≠ "KIA 타이거즈"
- $.games[20].away_team: "한화 이글스" ≠ "KT 위즈"
- $.games[21].game_id: "20251001KTHT02025" ≠ "20251001HHSK02025"
- $.games[21].home_team_id: "KIA" ≠ "SSG"
- $.games[21].away_team_id: "KT" ≠ "한화"
- $.games[21].home_score: 3 ≠ 6
- $.games[21].away_score: 9 ≠ 5
- $.games[21].stadium: "광주" ≠ "문학"
- $.games[21].home_team: "KIA 타이거즈" ≠ "SSG 랜더스"
- $.games[21].away_team: "KT 위즈" ≠ "한화 이글스"
- $.games[26].game_id: "20250930OBLG02025" ≠ "20250930SKWO02025"
- $.games[26].home_team_id: "LG" ≠ "키움"
- $.games[26].away_team_id: "두산" ≠ "SSG"
- $.games[26].home_score: 0 ≠ 3

## /games?season=2026&limit=30

차이 158건(앞 20건)

- $.games[0].game_id: "20261003HTLG02026" ≠ "20261003SKNC02026"
- $.games[0].home_team_id: "LG" ≠ "NC"
- $.games[0].away_team_id: "KIA" ≠ "SSG"
- $.games[0].home_score: 4 ≠ 13
- $.games[0].away_score: 5 ≠ 1
- $.games[0].stadium: "잠실" ≠ "창원"
- $.games[0].home_team: "LG 트윈스" ≠ "NC 다이노스"
- $.games[0].away_team: "KIA 타이거즈" ≠ "SSG 랜더스"
- $.games[2].game_id: "20261003OBSS02026" ≠ "20261003HTLG02026"
- $.games[2].home_team_id: "삼성" ≠ "LG"
- $.games[2].away_team_id: "두산" ≠ "KIA"
- $.games[2].home_score: 6 ≠ 4
- $.games[2].away_score: 4 ≠ 5
- $.games[2].stadium: "대구" ≠ "잠실"
- $.games[2].home_team: "삼성 라이온즈" ≠ "LG 트윈스"
- $.games[2].away_team: "두산 베어스" ≠ "KIA 타이거즈"
- $.games[3].game_id: "20261003SKNC02026" ≠ "20261003OBSS02026"
- $.games[3].home_team_id: "NC" ≠ "삼성"
- $.games[3].away_team_id: "SSG" ≠ "두산"
- $.games[3].home_score: 13 ≠ 6

## /roster/moves

차이 12건

- $.dates[0].added[0].name: "임정호" ≠ "이우성"
- $.dates[0].added[0].position: "투수" ≠ "외야수"
- $.dates[0].added[0].playerId: 63959 ≠ 63260
- $.dates[0].added[1].name: "이우성" ≠ "임정호"
- $.dates[0].added[1].position: "외야수" ≠ "투수"
- $.dates[0].added[1].playerId: 63260 ≠ 63959
- $.dates[0].added[3].name: "박정훈" ≠ "김태진"
- $.dates[0].added[3].position: "투수" ≠ "내야수"
- $.dates[0].added[3].playerId: 55394 ≠ 64984
- $.dates[0].added[4].name: "김태진" ≠ "박정훈"
- $.dates[0].added[4].position: "내야수" ≠ "투수"
- $.dates[0].added[4].playerId: 64984 ≠ 55394

## /roster/moves?days=30&limit=100

차이 46건(앞 20건)

- $.dates[4].removed[0].name: "한승연" ≠ "김현수"
- $.dates[4].removed[0].position: "외야수" ≠ "투수"
- $.dates[4].removed[0].playerId: 52628 ≠ 69516
- $.dates[4].removed[2].name: "김현수" ≠ "한승연"
- $.dates[4].removed[2].position: "투수" ≠ "외야수"
- $.dates[4].removed[2].playerId: 69516 ≠ 52628
- $.dates[4].removed[3].name: "전용주" ≠ "이정현"
- $.dates[4].removed[3].playerId: 69047 ≠ 67048
- $.dates[4].removed[5].name: "이정현" ≠ "전용주"
- $.dates[4].removed[5].playerId: 67048 ≠ 69047
- $.dates[4].removed[11].name: "정대선" ≠ "박세진"
- $.dates[4].removed[11].position: "내야수" ≠ "투수"
- $.dates[4].removed[11].playerId: 53568 ≠ 66047
- $.dates[4].removed[12].name: "박세진" ≠ "정대선"
- $.dates[4].removed[12].position: "투수" ≠ "내야수"
- $.dates[4].removed[12].playerId: 66047 ≠ 53568
- $.dates[4].removed[14].name: "최원준" ≠ "정민규"
- $.dates[4].removed[14].playerId: 53705 ≠ 51764
- $.dates[4].removed[15].name: "정민규" ≠ "최원준"
- $.dates[4].removed[15].playerId: 51764 ≠ 53705

## /wrc/leaderboard?season=2026&n=30

차이 24건(앞 20건)

- $[7].batter_ID: 54730 ≠ 67893
- $[7].player_name: "페라자" ≠ "박성한"
- $[7].player_team: "한화" ≠ "SSG"
- $[7].PA: 474 ≠ 513
- $[7].wOBA: 0.4136 ≠ 0.409
- $[7].wRAA: 27.6 ≠ 27.8
- $[7].home_stadium: "대전 한화생명 볼파크" ≠ "인천 SSG 랜더스필드"
- $[7].home_pf: 1101 ≠ 1039
- $[7].weighted_pf: 1046.5 ≠ 1024.9
- $[7].wRC_home: 134.8 ≠ 137.8
- $[7].wRC_weighted: 140.2 ≠ 139.2
- $[7].delta_methods: 0.4 ≠ -0.54
- $[8].batter_ID: 67893 ≠ 54730
- $[8].player_name: "박성한" ≠ "페라자"
- $[8].player_team: "SSG" ≠ "한화"
- $[8].PA: 513 ≠ 474
- $[8].wOBA: 0.409 ≠ 0.4136
- $[8].wRAA: 27.8 ≠ 27.6
- $[8].home_stadium: "인천 SSG 랜더스필드" ≠ "대전 한화생명 볼파크"
- $[8].home_pf: 1039 ≠ 1101

## /wrc/batter-search?q=김&season=2025

차이 12건

- $[17].player_id: "54097" ≠ "53554"
- $[17].player_team: "KT" ≠ "두산"
- $[18].player_id: "53554" ≠ "54097"
- $[18].player_team: "두산" ≠ "KT"
- $[20].player_id: "67504" ≠ "65048"
- $[20].player_team: "LG" ≠ "KT"
- $[21].player_id: "65048" ≠ "67504"
- $[21].player_team: "KT" ≠ "LG"
- $[22].player_id: "64004" ≠ "65269"
- $[22].player_team: "KT" ≠ "두산"
- $[23].player_id: "65269" ≠ "64004"
- $[23].player_team: "두산" ≠ "KT"

## /wrc/batter-search?q=이&season=2012

차이 2건

- $[8].player_id: "76100" ≠ "97109"
- $[9].player_id: "97109" ≠ "76100"

## /wrc/batter/74163

차이 9건

- $.stadium_distribution[8].pa: 318 ≠ 355
- $.stadium_distribution[9].pa: 178 ≠ 229
- $.stadium_distribution[10].pa: 90 ≠ 117
- $.stadium_distribution[22].stadium: "한밭" ≠ "군산"
- $.stadium_distribution[22].pa: 117 ≠ 133
- $.stadium_distribution[23].stadium: "군산" ≠ "한밭"
- $.stadium_distribution[23].pa: 116 ≠ 117
- $.stadium_distribution[25].pa: 931 ≠ 952
- $.stadium_distribution[32].pa: 82 ≠ 117

## /wrc/batter/69209

차이 4건

- $.stadium_distribution[4].stadium: "수원" ≠ "문학"
- $.stadium_distribution[5].stadium: "문학" ≠ "수원"
- $.stadium_distribution[29].stadium: "창원" ≠ "광주"
- $.stadium_distribution[30].stadium: "광주" ≠ "창원"

## /wrc/batter/65357

차이 4건

- $.stadium_distribution[15].stadium: "청주" ≠ "광주"
- $.stadium_distribution[16].stadium: "광주" ≠ "청주"
- $.stadium_distribution[27].stadium: "포항" ≠ "광주"
- $.stadium_distribution[28].stadium: "광주" ≠ "포항"

## /db/table/players?limit=50&offset=0

차이 802건(앞 20건)

- $.schema[0].type: "TEXT" ≠ "INTEGER"
- $.schema[0].notnull: false ≠ true
- $.schema[7].type: "DATE" ≠ "INTEGER"
- $.schema[16].type: "TIMESTAMP" ≠ "TEXT"
- $.schema[17].type: "TIMESTAMP" ≠ "TEXT"
- $.rows[0].player_id: "50030" ≠ "50007"
- $.rows[0].player_name: "소형준" ≠ "문상준"
- $.rows[0].team_id: "KT" ≠ "SSG"
- $.rows[0].back_number: 30 ≠ 53
- $.rows[0].position: "투수" ≠ "내야수"
- $.rows[0].birthday: 20010916 ≠ 20010314
- $.rows[0].height: 189 ≠ 183
- $.rows[0].weight: 92 ≠ 80
- $.rows[0].career: "호암초(의정부리틀)-구리인창중-유신고" ≠ "가동초-휘문중-휘문고-KT"
- $.rows[0].draft_order: "20 KT 1차" ≠ "8라운드 72순위"
- $.rows[0].signing_bonus: 360000000 ≠ 40000000
- $.rows[0].salary: 330000000 ≠ 31000000
- $.rows[0].image_url: "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle/2026/50030.jpg" ≠ "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle/2026/50007.jpg"
- $.rows[0].created_at: "2026-01-24 18:44:40" ≠ "2026-08-22 11:41:43"
- $.rows[0].updated_at: "2026-10-01 10:57:10" ≠ "2026-10-02 13:48:16"

## /db/table/games?limit=50&offset=0

차이 386건(앞 20건)

- $.schema[0].notnull: false ≠ true
- $.schema[1].type: "DATE" ≠ "INTEGER"
- $.rows[0].game_id: "20210519WOSS02021" ≠ "20080329HTSS0"
- $.rows[0].game_date: 20210519 ≠ 20080329
- $.rows[0].season: 2021 ≠ 2008
- $.rows[0].away_team_id: "키움" ≠ "KIA"
- $.rows[0].home_score: 2 ≠ 4
- $.rows[0].away_score: 9 ≠ 3
- $.rows[0].stadium: "대구" ≠ "시민"
- $.rows[1].game_id: "20210520NCLG02021" ≠ "20080329LGSK0"
- $.rows[1].game_date: 20210520 ≠ 20080329
- $.rows[1].season: 2021 ≠ 2008
- $.rows[1].home_team_id: "LG" ≠ "SK"
- $.rows[1].away_team_id: "NC" ≠ "LG"
- $.rows[1].home_score: 1 ≠ 5
- $.rows[1].away_score: 11 ≠ 4
- $.rows[1].stadium: "잠실" ≠ "문학"
- $.rows[2].game_id: "20210521HTSS02021" ≠ "20080329LTHH0"
- $.rows[2].game_date: 20210521 ≠ 20080329
- $.rows[2].season: 2021 ≠ 2008

## /db/table/team_seasons?limit=50&offset=0

차이 124건(앞 20건)

- $.rows[0].franchise_id: "OB" ≠ "HD"
- $.rows[0].team_name: "OB" ≠ "삼미"
- $.rows[1].franchise_id: "OB" ≠ "HD"
- $.rows[1].team_name: "OB" ≠ "삼미"
- $.rows[2].franchise_id: "OB" ≠ "HD"
- $.rows[2].team_name: "OB" ≠ "삼미"
- $.rows[3].franchise_id: "OB" ≠ "HD"
- $.rows[3].team_name: "OB" ≠ "청보"
- $.rows[4].franchise_id: "OB" ≠ "HD"
- $.rows[4].team_name: "OB" ≠ "청보"
- $.rows[5].franchise_id: "OB" ≠ "HD"
- $.rows[5].team_name: "OB" ≠ "청보"
- $.rows[6].franchise_id: "OB" ≠ "HD"
- $.rows[6].team_name: "OB" ≠ "태평양"
- $.rows[7].franchise_id: "OB" ≠ "HD"
- $.rows[7].team_name: "OB" ≠ "태평양"
- $.rows[8].franchise_id: "OB" ≠ "HD"
- $.rows[8].team_name: "OB" ≠ "태평양"
- $.rows[9].franchise_id: "OB" ≠ "HD"
- $.rows[9].team_name: "OB" ≠ "태평양"

## /db/table/wrc_plus_comparison?limit=50&offset=0

차이 4건

- $.schema[0].type: "INT" ≠ "INTEGER"
- $.schema[1].type: "INT" ≠ "INTEGER"
- $.schema[2].type: "INT" ≠ "INTEGER"
- $.schema[3].type: "INT" ≠ "INTEGER"

## /db/table/players?limit=50&offset=1000

차이 742건(앞 20건)

- $.schema[0].type: "TEXT" ≠ "INTEGER"
- $.schema[0].notnull: false ≠ true
- $.schema[7].type: "DATE" ≠ "INTEGER"
- $.schema[16].type: "TIMESTAMP" ≠ "TEXT"
- $.schema[17].type: "TIMESTAMP" ≠ "TEXT"
- $.rows[0].player_id: "62164" ≠ "65368"
- $.rows[0].player_name: "서상우" ≠ "정용준"
- $.rows[0].back_number: 52 ≠ 68
- $.rows[0].position: "내야수" ≠ "투수"
- $.rows[0].bat: "L" ≠ "R"
- $.rows[0].birthday: 19890917 ≠ 19950621
- $.rows[0].height: 187 ≠ 181
- $.rows[0].weight: 90 ≠ 80
- $.rows[0].career: "구리초(구리리틀)-구리인창중-유신고-건국대-LG-상무-LG" ≠ "율하초-경상중-대구상원고"
- $.rows[0].draft_year: "12LG" ≠ "15넥센"
- $.rows[0].draft_order: "9라운드 80순위" ≠ "4라운드 38순위"
- $.rows[0].image_url: "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle/2019/62164.jpg" ≠ "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle/2016/65368.jpg"
- $.rows[0].created_at: "2026-08-22 12:04:10" ≠ "2026-08-22 12:14:40"
- $.rows[1].player_id: "62242" ≠ "65392"
- $.rows[1].player_name: "윤명준" ≠ "김정인"

## /db/table/play_by_play?limit=50&offset=0

차이 109건(앞 20건)

- $.schema[0].notnull: false ≠ true
- $.schema[4].type: "TEXT" ≠ "INTEGER"
- $.schema[5].type: "TEXT" ≠ "INTEGER"
- $.schema[34].type: "TEXT" ≠ "INTEGER"
- $.schema[35].type: "TEXT" ≠ "INTEGER"
- $.schema[36].type: "TEXT" ≠ "INTEGER"
- $.schema[37].type: "TEXT" ≠ "INTEGER"
- $.schema[38].type: "TEXT" ≠ "INTEGER"
- $.schema[39].type: "TEXT" ≠ "INTEGER"
- $.schema[40].type: "TEXT" ≠ "INTEGER"
- $.schema[41].type: "TEXT" ≠ "INTEGER"
- $.schema[42].type: "TEXT" ≠ "INTEGER"
- $.schema[43].type: "TEXT" ≠ "INTEGER"
- $.schema[44].type: "TEXT" ≠ "INTEGER"
- $.schema[45].type: "TEXT" ≠ "INTEGER"
- $.schema[63].type: "DATE" ≠ "INTEGER"
- $.rows[0].pbp_id: 51 ≠ 1
- $.rows[1].pbp_id: 52 ≠ 2
- $.rows[2].pbp_id: 53 ≠ 3
- $.rows[3].pbp_id: 54 ≠ 4

## /db/table/kbo_roster?limit=50

차이 249건(앞 20건)

- $.rows[0].team: "KT" ≠ "KIA"
- $.rows[0].name: "고영표" ≠ "곽도규"
- $.rows[0].back_number: "1" ≠ "0"
- $.rows[0].player_id: 64001 ≠ 53609
- $.rows[1].team: "KT" ≠ "KIA"
- $.rows[1].name: "스기모토" ≠ "곽동효"
- $.rows[1].back_number: "11" ≠ "138"
- $.rows[1].role: "투수" ≠ "외야수"
- $.rows[1].player_id: 56011 ≠ 56638
- $.rows[1].league: "1군" ≠ "퓨처스"
- $.rows[2].team: "KT" ≠ "KIA"
- $.rows[2].name: "우규민" ≠ "김경묵"
- $.rows[2].back_number: "12" ≠ "118"
- $.rows[2].player_id: 73117 ≠ 55618
- $.rows[2].league: "1군" ≠ "퓨처스"
- $.rows[3].team: "KT" ≠ "KIA"
- $.rows[3].name: "문용익" ≠ "김규성"
- $.rows[3].back_number: "18" ≠ "14"
- $.rows[3].role: "투수" ≠ "내야수"
- $.rows[3].player_id: 67419 ≠ 66614

## /db/table/kbo_roster_moves?limit=50

차이 135건(앞 20건)

- $.rows[0].team: "한화" ≠ "KT"
- $.rows[0].name: "유민" ≠ "문용익"
- $.rows[0].position: "외야수" ≠ "투수"
- $.rows[0].player_id: 52765 ≠ 67419
- $.rows[1].team: "SSG" ≠ "LG"
- $.rows[1].name: "김도현" ≠ "김민수"
- $.rows[1].position: "투수" ≠ "포수"
- $.rows[1].player_id: 52844 ≠ 64793
- $.rows[2].team: "NC" ≠ "LG"
- $.rows[2].name: "이재학" ≠ "김현종"
- $.rows[2].position: "투수" ≠ "외야수"
- $.rows[2].player_id: 60263 ≠ 54166
- $.rows[3].team: "KT" ≠ "NC"
- $.rows[3].name: "문용익" ≠ "이재학"
- $.rows[3].player_id: 67419 ≠ 60263
- $.rows[4].team: "두산" ≠ "SSG"
- $.rows[4].name: "전다민" ≠ "김도현"
- $.rows[4].position: "외야수" ≠ "투수"
- $.rows[4].player_id: 54214 ≠ 52844
- $.rows[5].team: "키움" ≠ "두산"

## /db/table/team_logos?limit=2

차이 1건

- $.schema[0].notnull: false ≠ true

## /db/table/teams/csv?limit=100

차이 1건

- $._sha256: "aff3d4704289409843cfefc8e88d3ea30baf54917545d42a911a1bbbf971b900" ≠ "d7ed069e11d1114166bf4b1e9e8c4d0af14a049b1b917f14282d380530cfb1e2"

## /db/table/franchises/csv?limit=100

차이 1건

- $._sha256: "6c91d2d6a722cfe5f928f7bb69b61497b5cadf0f82d2dd472a96e68425ea25fe" ≠ "66b110b5bfd50f9ad6fa5cea5586b69b05dc2de30a53434f0b24854835721910"

## /db/table/play_by_play/csv?limit=20000&offset=0

차이 2건

- $._sha256: "be08bdff538e5f0060b7ec1070d39c359ffce52f02806999349961465b5e0515" ≠ "9a2f11eb9d87850ed6169513fe2a1690dea5358d9bd7593ddba370a89606a033"
- $._bytes: 7068192 ≠ 7041897

