# API 대조

- A: https://kbo-api-stg-d1.bstats-baseball.workers.dev
- B: https://kbo-api.bstats-baseball.workers.dev
- URL 43개
- 배열 순서: 무시(--unordered, 다중집합)
- 다른 URL 23개

## /leaders?season=2015

차이 4건

- $.pitcher.k[2].code: "SS" ≠ "NC"
- $.pitcher.k[2].name: "윤성환" ≠ "해커"
- $.pitcher.k[2].player_id: "74454" ≠ "63938"
- $.pitcher.k[2].team: "삼성" ≠ "NC"

## /stats/pitchers?season=2019&limit=50&min_ip=30

차이 1396건(앞 20건)

- $.pitchers[14].air_outs: 223 ≠ 218
- $.pitchers[14].base_on_balls: 42 ≠ 63
- $.pitchers[14].base_on_balls_per_pa: 6.069364161849711 ≠ 8.289473684210526
- $.pitchers[14].batting_average: 0.27 ≠ 0.227
- $.pitchers[14].batting_average_on_balls_in_play: 0.286 ≠ 0.257
- $.pitchers[14].bb_9: 2.27 ≠ 3.08
- $.pitchers[14].complete_game: 2 ≠ 0
- $.pitchers[14].double: 37 ≠ 21
- $.pitchers[14].earned_run: 60 ≠ 74
- $.pitchers[14].earned_run_average: 3.25 ≠ 3.62
- $.pitchers[14].games: 28 ≠ 30
- $.pitchers[14].games_finished: 2 ≠ 0
- $.pitchers[14].games_started: 27 ≠ 30
- $.pitchers[14].go_ao: "0.82" ≠ "0.79"
- $.pitchers[14].ground_into_double_play: 19 ≠ 17
- $.pitchers[14].ground_outs: 183 ≠ 172
- $.pitchers[14].hit_by_pitch: 3 ≠ 12
- $.pitchers[14].hits: 171 ≠ 153
- $.pitchers[14].home_run: 8 ≠ 18
- $.pitchers[14].innings_pitched: "166 1/3" ≠ "184"

## /stats/batters?season=2025&limit=50&min_pa=100

차이 1192건(앞 20건)

- $.batters[5].at_bat: 385 ≠ 404
- $.batters[5].base_on_balls: 34 ≠ 44
- $.batters[5].base_on_balls_per_pa: 7.8 ≠ 8.4
- $.batters[5].batting_average: 0.275 ≠ 0.302
- $.batters[5].bb_k: "0.40" ≠ "0.69"
- $.batters[5].double: 19 ≠ 25
- $.batters[5].extended_runs: 50.4 ≠ 68.6
- $.batters[5].extra_base_hits: 26 ≠ 36
- $.batters[5].games: 112 ≠ 117
- $.batters[5].go_ao: "0.74" ≠ "0.96"
- $.batters[5].gross_production_average: 0.246 ≠ 0.279
- $.batters[5].ground_into_double_play: 2 ≠ 5
- $.batters[5].ground_outs: 84 ≠ 109
- $.batters[5].gw_rbi: 3 ≠ 6
- $.batters[5].hit_by_pitch: 2 ≠ 12
- $.batters[5].home_run: 7 ≠ 3
- $.batters[5].intentional_base_on_balls: 1 ≠ 5
- $.batters[5].isop: 0.104 ≠ 0.124
- $.batters[5].multi_hits: 31 ≠ 37
- $.batters[5].on_base_percentage: 0.336 ≠ 0.384

## /stats/batters?season=2026&limit=50&min_pa=100

차이 50건(앞 20건)

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
- $.batters[14].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"
- $.batters[15].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"
- $.batters[16].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"
- $.batters[17].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"
- $.batters[18].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"
- $.batters[19].updated_at: "2026-10-04 01:24:49" ≠ "2026-10-04 01:24:53"

## /stats/pitchers?season=2026&limit=50&min_ip=30

차이 94건(앞 20건)

- $.pitchers[0].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[1].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[2].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[3].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[4].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[5].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[6].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[7].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"
- $.pitchers[8].air_outs: 141 ≠ 147
- $.pitchers[8].base_on_balls: 31 ≠ 46
- $.pitchers[8].base_on_balls_per_pa: 5.457746478873239 ≠ 6.8350668647845465
- $.pitchers[8].batting_average: 0.267 ≠ 0.261
- $.pitchers[8].batting_average_on_balls_in_play: 0.307 ≠ 0.301
- $.pitchers[8].bb_9: 2.11 ≠ 2.64
- $.pitchers[8].double: 19 ≠ 27
- $.pitchers[8].earned_run: 59 ≠ 70
- $.pitchers[8].games: 24 ≠ 28
- $.pitchers[8].games_started: 24 ≠ 28
- $.pitchers[8].go_ao: "1.08" ≠ "1.21"
- $.pitchers[8].ground_into_double_play: 11 ≠ 15

## /stats/pitchers?season=2019&limit=30&team_ids=두산,키움

차이 278건(앞 20건)

- $.pitchers[17].air_outs: 46 ≠ 52
- $.pitchers[17].base_on_balls: 14 ≠ 28
- $.pitchers[17].base_on_balls_per_pa: 6.11353711790393 ≠ 11.764705882352942
- $.pitchers[17].batting_average: 0.312 ≠ 0.24
- $.pitchers[17].batting_average_on_balls_in_play: 0.353 ≠ 0.324
- $.pitchers[17].bb_9: 2.42 ≠ 4.45
- $.pitchers[17].blown_save: 5 ≠ 1
- $.pitchers[17].double: 14 ≠ 6
- $.pitchers[17].earned_run: 26 ≠ 19
- $.pitchers[17].earned_run_average: 4.5 ≠ 3.02
- $.pitchers[17].games: 61 ≠ 67
- $.pitchers[17].games_finished: 8 ≠ 1
- $.pitchers[17].go_ao: "1.35" ≠ "0.88"
- $.pitchers[17].ground_into_double_play: 6 ≠ 8
- $.pitchers[17].ground_outs: 62 ≠ 46
- $.pitchers[17].hit_by_pitch: 5 ≠ 2
- $.pitchers[17].hits: 64 ≠ 50
- $.pitchers[17].hold: 14 ≠ 40
- $.pitchers[17].home_run: 5 ≠ 3
- $.pitchers[17].innings_pitched: "52" ≠ "56 2/3"

## /stats/team_range?start=20190501&end=20190531

차이 327건(앞 20건)

- $.batting: 길이 11 ≠ 10
- $.batting[0].2B: 0 ≠ 31
- $.batting[0].3B: 0 ≠ 4
- $.batting[0].AB: 0 ≠ 914
- $.batting[0].AVG: 0 ≠ 0.269
- $.batting[0].BB: 0 ≠ 82
- $.batting[0].H: 0 ≠ 246
- $.batting[0].HBP: 0 ≠ 20
- $.batting[0].HR: 0 ≠ 23
- $.batting[0].OBP: 0 ≠ 0.341
- $.batting[0].OPS: 0 ≠ 0.728
- $.batting[0].PA: 0 ≠ 1028
- $.batting[0].R: 0 ≠ 131
- $.batting[0].SF: 0 ≠ 6
- $.batting[0].SH: 0 ≠ 5
- $.batting[0].SLG: 0 ≠ 0.387
- $.batting[0].SO: 0 ≠ 177
- $.batting[0].TB: 0 ≠ 354
- $.batting[1].2B: 31 ≠ 37
- $.batting[1].AB: 914 ≠ 907

## /players/search?q=김

차이 746건(앞 20건)

- $.players[1].back_number: 10 ≠ 101
- $.players[1].birthday: 20061215 ≠ 20011227
- $.players[1].career: "화순초-거원중-덕수고" ≠ "서울대왕초(강남구리틀)-영동중-덕수고-키움-상무"
- $.players[1].created_at: "2026-01-24 18:59:23" ≠ "2026-08-22 11:42:49"
- $.players[1].draft_order: "1라운드 5순위" ≠ "3라운드 27순위"
- $.players[1].draft_year: "25KIA" ≠ "20키움"
- $.players[1].image_url: "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle/2026/55610.jpg" ≠ "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle/2026/50360.jpg"
- $.players[1].is_active: 1 ≠ 0
- $.players[1].player_id: "55610" ≠ "50360"
- $.players[1].player_name: "김태형" ≠ "김동혁"
- $.players[1].salary: 60000000 ≠ 48000000
- $.players[1].signing_bonus: 300000000 ≠ 80000000
- $.players[1].team_id: "KIA" ≠ "키움"
- $.players[1].throw: "R" ≠ null
- $.players[1].updated_at: "2026-10-01 11:10:24" ≠ "2026-08-22 11:42:49"
- $.players[1].weight: 95 ≠ 80
- $.players[2].back_number: 11 ≠ 103
- $.players[2].bat: "L" ≠ "R"
- $.players[2].birthday: 20020904 ≠ 20030901
- $.players[2].career: "군산신풍초-군산중-군산상고" ≠ "희망대초-대원중-경기항공고"

## /players/53375

차이 1건

- $.pitcher_seasons[0].updated_at: "2026-10-04 01:28:46" ≠ "2026-10-04 01:28:50"

## /players/77829/usage?season=2010

차이 18건

- $.total_l: 768 ≠ 812
- $.total_pitches: 2768 ≠ 2891
- $.total_r: 2000 ≠ 2079
- $.usage[0].count: 231 ≠ 232
- $.usage[0].usage_all: 8.3 ≠ 8
- $.usage[0].usage_l: 4 ≠ 3.8
- $.usage[0].usage_r: 10 ≠ 9.7
- $.usage[1].count: 212 ≠ 215
- $.usage[1].usage_all: 7.7 ≠ 7.4
- $.usage[1].usage_l: 9.9 ≠ 9.5
- $.usage[1].usage_r: 6.8 ≠ 6.6
- $.usage[2].count: 1521 ≠ 1587
- $.usage[2].usage_l: 55.2 ≠ 55.3
- $.usage[2].usage_r: 54.8 ≠ 54.7
- $.usage[4].count: 796 ≠ 849
- $.usage[4].usage_all: 28.8 ≠ 29.4
- $.usage[4].usage_l: 30.9 ≠ 31.4
- $.usage[4].usage_r: 28 ≠ 28.6

## /games?season=2025&limit=30

차이 55건(앞 20건)

- $.games[4].away_score: 2 ≠ 13
- $.games[4].away_team: "SSG 랜더스" ≠ "NC 다이노스"
- $.games[4].away_team_id: "SSG" ≠ "NC"
- $.games[4].date: 20251002 ≠ 20250929
- $.games[4].game_date: 20251002 ≠ 20250929
- $.games[4].game_id: "20251002SKHT02025" ≠ "20250929NCHT02025"
- $.games[4].home_score: 7 ≠ 4
- $.games[5].date: 20251014 ≠ 20251002
- $.games[5].game_date: 20251014 ≠ 20251002
- $.games[5].game_id: "33331014SKSS02025" ≠ "20251002SKHT02025"
- $.games[5].game_type: "포스트시즌" ≠ "정규시즌"
- $.games[5].home_score: 5 ≠ 7
- $.games[5].home_team: "삼성 라이온즈" ≠ "KIA 타이거즈"
- $.games[5].home_team_id: "삼성" ≠ "KIA"
- $.games[5].stadium: "대구" ≠ "광주"
- $.games[6].away_team: "롯데 자이언츠" ≠ "SSG 랜더스"
- $.games[6].away_team_id: "롯데" ≠ "SSG"
- $.games[6].date: 20250929 ≠ 20251014
- $.games[6].game_date: 20250929 ≠ 20251014
- $.games[6].game_id: "20250929LTSK02025" ≠ "33331014SKSS02025"

## /wrc/batter/74163

차이 338건(앞 20건)

- $.stadium_distribution[16].pa: 116 ≠ 117
- $.stadium_distribution[16].season: "2010" ≠ "2009"
- $.stadium_distribution[16].stadium: "군산" ≠ "문학"
- $.stadium_distribution[19].season: "2020" ≠ "2011"
- $.stadium_distribution[19].stadium: "대구" ≠ "문학"
- $.stadium_distribution[20].pa: 118 ≠ 117
- $.stadium_distribution[20].stadium: "창원" ≠ "대구"
- $.stadium_distribution[21].pa: 119 ≠ 118
- $.stadium_distribution[21].season: "2017" ≠ "2020"
- $.stadium_distribution[21].stadium: "잠실" ≠ "창원"
- $.stadium_distribution[22].pa: 1190 ≠ 119
- $.stadium_distribution[22].season: "2021" ≠ "2017"
- $.stadium_distribution[22].stadium: "고척" ≠ "잠실"
- $.stadium_distribution[23].pa: 12 ≠ 1190
- $.stadium_distribution[23].season: "2025" ≠ "2021"
- $.stadium_distribution[23].stadium: "대전" ≠ "고척"
- $.stadium_distribution[24].pa: 120 ≠ 12
- $.stadium_distribution[24].season: "2014" ≠ "2025"
- $.stadium_distribution[24].stadium: "청주" ≠ "대전"
- $.stadium_distribution[25].season: "2018" ≠ "2014"

## /db/table/players?limit=50&offset=0

차이 752건(앞 20건)

- $.rows[0].birthday: 19960712 ≠ 19930419
- $.rows[0].career: "먼우금초-Lesbois(중)-Timberline(고)-Boise State(대)" ≠ "일본 타카사초-일본 키시중-일본 와세다실업고-일본 와세다대-두산-롯데"
- $.rows[0].created_at: "2026-01-24 18:46:57" ≠ "2026-08-22 11:41:43"
- $.rows[0].draft_order: "8라운드 75순위" ≠ "10라운드 99순위"
- $.rows[0].draft_year: "21KT" ≠ "20두산"
- $.rows[0].height: 182 ≠ 175
- $.rows[0].image_url: "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle/2025/51005.jpg" ≠ "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle/2023/50202.jpg"
- $.rows[0].player_id: "51005" ≠ "50202"
- $.rows[0].player_name: "김건형" ≠ "안권수"
- $.rows[0].salary: 33000000 ≠ 80000000
- $.rows[0].signing_bonus: 40000000 ≠ 30000000
- $.rows[0].team_id: "KT" ≠ null
- $.rows[0].updated_at: "2026-01-24 18:46:57" ≠ "2026-08-29 01:47:33"
- $.rows[0].weight: 83 ≠ 80
- $.rows[2].back_number: 10 ≠ 101
- $.rows[2].bat: "L" ≠ "R"
- $.rows[2].birthday: 20000502 ≠ 20010518
- $.rows[2].career: "동막초-영남중-강릉고-KIA-상무-KIA" ≠ "남정초-덕수중-휘문고-삼성-상무"
- $.rows[2].created_at: "2026-01-24 18:45:49" ≠ "2026-08-22 11:42:49"
- $.rows[2].draft_order: "2라운드 16순위" ≠ "5라운드 45순위"

## /db/table/games?limit=50&offset=0

차이 368건(앞 20건)

- $.rows[0].away_team_id: "KT" ≠ "KIA"
- $.rows[0].game_date: 20210521 ≠ 20080330
- $.rows[0].game_id: "20210521KTHH02021" ≠ "20080330HTSS0"
- $.rows[0].home_score: 4 ≠ 3
- $.rows[0].home_team_id: "한화" ≠ "삼성"
- $.rows[0].season: 2021 ≠ 2008
- $.rows[0].stadium: "대전" ≠ "시민"
- $.rows[1].away_team_id: "KT" ≠ "KIA"
- $.rows[1].game_date: 20210522 ≠ 20080406
- $.rows[1].game_id: "20210522KTHH02021" ≠ "20080406HTHH0"
- $.rows[1].home_score: 5 ≠ 4
- $.rows[1].season: 2021 ≠ 2008
- $.rows[1].stadium: "대전" ≠ "한밭"
- $.rows[2].away_team_id: "LG" ≠ "롯데"
- $.rows[2].game_date: 20210523 ≠ 20080410
- $.rows[2].game_id: "20210523LGSK02021" ≠ "20080410LTSS0"
- $.rows[2].home_score: 8 ≠ 2
- $.rows[2].home_team_id: "SSG" ≠ "삼성"
- $.rows[2].season: 2021 ≠ 2008
- $.rows[2].stadium: "문학" ≠ "시민"

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

- $.schema[4].type: "INT" ≠ "INTEGER"
- $.schema[8].type: "INT" ≠ "INTEGER"
- $.schema[9].type: "INT" ≠ "INTEGER"
- $.schema[10].type: "INT" ≠ "INTEGER"

## /db/table/players?limit=50&offset=1000

차이 753건(앞 20건)

- $.rows[0].back_number: 0 ≠ 11
- $.rows[0].birthday: 19850621 ≠ 19960316
- $.rows[0].career: "제주남초-제주제일중-일본 교토고쿠사이고-일본 아세아대" ≠ "도신초-강남중-충암고-경찰"
- $.rows[0].created_at: "2026-08-22 12:06:57" ≠ "2026-08-22 12:15:13"
- $.rows[0].draft_order: "13 LG 육성선수" ≠ "4라운드 35순위"
- $.rows[0].draft_year: "13LG" ≠ "15삼성"
- $.rows[0].height: 173 ≠ 182
- $.rows[0].image_url: "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle/2017/63077.jpg" ≠ "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle/2024/65496.jpg"
- $.rows[0].player_id: "63077" ≠ "65496"
- $.rows[0].player_name: "황목치승" ≠ "홍정우"
- $.rows[0].position: "내야수" ≠ "투수"
- $.rows[0].salary: null ≠ 60000000
- $.rows[0].signing_bonus: null ≠ 80000000
- $.rows[0].updated_at: "2026-08-29 01:49:07" ≠ "2026-08-22 12:15:13"
- $.rows[0].weight: 68 ≠ 85
- $.rows[1].back_number: 100 ≠ 127
- $.rows[1].bat: "R" ≠ "L"
- $.rows[1].birthday: 19930811 ≠ 19920311
- $.rows[1].career: "부산수영초-부산중-부산고-NC" ≠ "사당초-언북중-신일고-동국대"
- $.rows[1].created_at: "2026-08-22 12:06:24" ≠ "2026-08-22 12:14:40"

## /db/table/play_by_play?limit=50&offset=0

차이 115건(앞 20건)

- $.rows[0].on_1b_id: "74163.0" ≠ "74163"
- $.rows[0].pbp_id: 57 ≠ 7
- $.rows[1].on_1b_id: "74163.0" ≠ "74163"
- $.rows[1].pbp_id: 55 ≠ 5
- $.rows[2].on_1b_id: "74163.0" ≠ "74163"
- $.rows[2].pbp_id: 56 ≠ 6
- $.rows[3].on_1b_id: "96610.0" ≠ "96610"
- $.rows[3].on_2b_id: "71207.0" ≠ "71207"
- $.rows[3].pbp_id: 65 ≠ 15
- $.rows[4].on_1b_id: "96610.0" ≠ "96610"
- $.rows[4].on_2b_id: "71207.0" ≠ "71207"
- $.rows[4].pbp_id: 63 ≠ 13
- $.rows[5].on_1b_id: "96610.0" ≠ "96610"
- $.rows[5].on_2b_id: "71207.0" ≠ "71207"
- $.rows[5].pbp_id: 64 ≠ 14
- $.rows[6].on_1b_id: "77725.0" ≠ "77725"
- $.rows[6].pbp_id: 88 ≠ 38
- $.rows[7].pbp_id: 72 ≠ 22
- $.rows[8].pbp_id: 71 ≠ 21
- $.rows[9].on_1b_id: "71432.0" ≠ "71432"

## /db/table/kbo_roster?limit=50

차이 248건(앞 20건)

- $.rows[1].back_number: "0" ≠ "1"
- $.rows[1].name: "디아즈" ≠ "박정우"
- $.rows[1].player_id: 54400 ≠ 67609
- $.rows[1].role: "내야수" ≠ "외야수"
- $.rows[1].team: "삼성" ≠ "KIA"
- $.rows[2].back_number: "1" ≠ "10"
- $.rows[2].name: "고영표" ≠ "김태형"
- $.rows[2].player_id: 64001 ≠ 55610
- $.rows[2].team: "KT" ≠ "KIA"
- $.rows[3].back_number: "10" ≠ "104"
- $.rows[3].league: "1군" ≠ "퓨처스"
- $.rows[3].name: "김태형" ≠ "김민수"
- $.rows[3].player_id: 55610 ≠ 69627
- $.rows[3].role: "투수" ≠ "외야수"
- $.rows[4].back_number: "10" ≠ "109"
- $.rows[4].league: "1군" ≠ "퓨처스"
- $.rows[4].name: "김현수" ≠ "이영재"
- $.rows[4].player_id: 76290 ≠ 51605
- $.rows[4].team: "KT" ≠ "KIA"
- $.rows[5].name: "스기모토" ≠ "조상우"

## /db/table/kbo_roster_moves?limit=50

차이 3건

- $.rows[49].name: "이상규" ≠ "이상동"
- $.rows[49].player_id: 65117 ≠ 69054
- $.rows[49].team: "한화" ≠ "KT"

## /db/table/team_logos?limit=2

차이 1건

- $.schema[1].notnull: false ≠ true

## /db/table/teams/csv?limit=100

차이 1건

- $._sha256: "aff3d4704289409843cfefc8e88d3ea30baf54917545d42a911a1bbbf971b900" ≠ "d7ed069e11d1114166bf4b1e9e8c4d0af14a049b1b917f14282d380530cfb1e2"

## /db/table/franchises/csv?limit=100

차이 1건

- $._sha256: "6c91d2d6a722cfe5f928f7bb69b61497b5cadf0f82d2dd472a96e68425ea25fe" ≠ "66b110b5bfd50f9ad6fa5cea5586b69b05dc2de30a53434f0b24854835721910"

