# MySQL 스키마 보고

스냅샷: `d1_20261002.db`

| 표 | 열 수 | 새 번호 |
|---|---|---|
| franchises | 5 |  |
| futures_games | 14 |  |
| futures_season_stats | 29 |  |
| futures_teams | 6 |  |
| game_team_stats | 13 |  |
| games | 13 |  |
| kbo_official_batter_stats | 42 |  |
| kbo_official_pitcher_stats | 57 |  |
| kbo_roster | 7 |  |
| kbo_roster_moves | 6 |  |
| kbo_run_values_by_season | 4 |  |
| kbo_woba_weights_by_season | 23 |  |
| korean_series_champion | 3 |  |
| meta_backfill | 4 |  |
| meta_job_runs | 5 |  |
| meta_table_counts | 3 |  |
| play_by_play | 74 | pbp_id |
| players | 18 |  |
| re24_matrix_by_season | 5 |  |
| self_park_factor | 13 |  |
| stadium_dim | 7 |  |
| statiz_park_factor | 11 |  |
| statiz_yearly_constants | 17 |  |
| team_logos | 8 |  |
| team_season_rank | 11 |  |
| team_seasons | 3 |  |
| team_stadium_by_season | 3 |  |
| teams | 6 |  |
| weighted_pf_by_batter_season | 15 |  |
| wrc_plus_comparison | 16 |  |

## 타입·값 처리 메모

- futures_games.game_date: 선언 TEXT → DATE
- futures_season_stats.player_id: 선언 TEXT → INT UNSIGNED
- games.game_date: 선언 DATE → INT
- kbo_official_batter_stats.player_id: 선언 TEXT → INT UNSIGNED
- kbo_official_batter_stats.created_at: 선언 TEXT → DATETIME
- kbo_official_batter_stats.updated_at: 선언 TEXT → DATETIME
- kbo_official_pitcher_stats.player_id: 선언 TEXT → INT UNSIGNED
- kbo_official_pitcher_stats.created_at: 선언 TEXT → DATETIME
- kbo_official_pitcher_stats.updated_at: 선언 TEXT → DATETIME
- kbo_roster.as_of: 선언 TEXT → DATE
- kbo_roster_moves.move_date: 선언 TEXT → DATE
- meta_backfill.updated_at: 선언 TEXT → DATETIME
- meta_table_counts.updated_at: 선언 TEXT → DATETIME
- play_by_play.pitcher_ID: 선언 TEXT → INT UNSIGNED
- play_by_play.pitcher_ID: 소수점 표기 1,592개 → 정수
- play_by_play.batter_ID: 선언 TEXT → INT
- play_by_play.batter_ID: 소수점 표기 4,553개 → 정수
- play_by_play.speed: 빈 값 12,103개 → NULL
- play_by_play.on_1b_id: 선언 TEXT → INT UNSIGNED
- play_by_play.on_1b_id: 소수점 표기 1,365,902개 → 정수
- play_by_play.on_1b_id: 빈 값 150,825개 → NULL
- play_by_play.on_2b_id: 선언 TEXT → INT UNSIGNED
- play_by_play.on_2b_id: 소수점 표기 858,189개 → 정수
- play_by_play.on_2b_id: 빈 값 181,266개 → NULL
- play_by_play.on_3b_id: 선언 TEXT → INT UNSIGNED
- play_by_play.on_3b_id: 소수점 표기 451,205개 → 정수
- play_by_play.on_3b_id: 빈 값 204,724개 → NULL
- play_by_play.pos_1_id: 선언 TEXT → INT UNSIGNED
- play_by_play.pos_1_id: 소수점 표기 4,866개 → 정수
- play_by_play.pos_2_id: 선언 TEXT → INT UNSIGNED
- play_by_play.pos_2_id: 소수점 표기 5,173개 → 정수
- play_by_play.pos_3_id: 선언 TEXT → INT UNSIGNED
- play_by_play.pos_3_id: 소수점 표기 5,117개 → 정수
- play_by_play.pos_4_id: 선언 TEXT → INT UNSIGNED
- play_by_play.pos_4_id: 소수점 표기 6,425개 → 정수
- play_by_play.pos_5_id: 선언 TEXT → INT UNSIGNED
- play_by_play.pos_5_id: 소수점 표기 5,143개 → 정수
- play_by_play.pos_6_id: 선언 TEXT → INT UNSIGNED
- play_by_play.pos_6_id: 소수점 표기 5,750개 → 정수
- play_by_play.pos_7_id: 선언 TEXT → INT UNSIGNED
- play_by_play.pos_7_id: 소수점 표기 5,612개 → 정수
- play_by_play.pos_8_id: 선언 TEXT → INT UNSIGNED
- play_by_play.pos_8_id: 소수점 표기 6,120개 → 정수
- play_by_play.pos_9_id: 선언 TEXT → INT UNSIGNED
- play_by_play.pos_9_id: 소수점 표기 5,936개 → 정수
- play_by_play.px: 빈 값 12,186개 → NULL
- play_by_play.pz: 빈 값 12,186개 → NULL
- play_by_play.pfx_x: 빈 값 12,186개 → NULL
- play_by_play.pfx_z: 빈 값 12,186개 → NULL
- play_by_play.pfx_x_raw: 빈 값 12,186개 → NULL
- play_by_play.pfx_z_raw: 빈 값 12,186개 → NULL
- play_by_play.x0: 빈 값 12,186개 → NULL
- play_by_play.z0: 빈 값 12,186개 → NULL
- play_by_play.sz_top: 빈 값 12,186개 → NULL
- play_by_play.sz_bot: 빈 값 12,186개 → NULL
- play_by_play.y0: 빈 값 12,186개 → NULL
- play_by_play.vx0: 빈 값 12,186개 → NULL
- play_by_play.vy0: 빈 값 12,186개 → NULL
- play_by_play.vz0: 빈 값 12,186개 → NULL
- play_by_play.ax: 빈 값 12,186개 → NULL
- play_by_play.ay: 빈 값 12,186개 → NULL
- play_by_play.az: 빈 값 12,186개 → NULL
- play_by_play.game_date: 선언 DATE → INT
- play_by_play.pitch_number: 빈 값 11,283개 → NULL
- players.player_id: 선언 TEXT → INT UNSIGNED
- players.birthday: 선언 DATE → INT
- self_park_factor.captured_at: 선언 TEXT → DATETIME
- statiz_park_factor.captured_at: 선언 TEXT → DATETIME
- statiz_yearly_constants.captured_at: 선언 TEXT → DATETIME
- team_stadium_by_season: 기본키가 없습니다(원본과 같음)
- weighted_pf_by_batter_season: 기본키가 없습니다(원본과 같음)
- wrc_plus_comparison: 기본키가 없습니다(원본과 같음)
