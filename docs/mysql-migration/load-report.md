# MySQL 적재 보고

- 스냅샷: `d1_20261002.db`
- 적재 시각(UTC): 2026-10-02 05:10
- 걸린 시간: 30분

| 표 | 행 |
|---|---|
| franchises | 12 |
| futures_games | 598 |
| futures_season_stats | 13,036 |
| futures_teams | 13 |
| game_team_stats | 0 |
| games | 12,643 |
| kbo_official_batter_stats | 11,992 |
| kbo_official_pitcher_stats | 7,968 |
| kbo_roster | 618 |
| kbo_roster_moves | 304 |
| kbo_run_values_by_season | 243 |
| kbo_woba_weights_by_season | 19 |
| korean_series_champion | 44 |
| meta_backfill | 2 |
| meta_job_runs | 9 |
| meta_table_counts | 21 |
| play_by_play | 3,983,367 |
| players | 1,760 |
| re24_matrix_by_season | 456 |
| self_park_factor | 159 |
| stadium_dim | 16 |
| statiz_park_factor | 100 |
| statiz_yearly_constants | 16 |
| team_logos | 13 |
| team_season_rank | 373 |
| team_seasons | 373 |
| team_stadium_by_season | 178 |
| teams | 14 |
| weighted_pf_by_batter_season | 4,997 |
| wrc_plus_comparison | 3,218 |

- 이어서 넣기(--resume): 값 정리 건수는 이번 실행에서 넣은 행만 셉니다

## 값 정리

| 표.열 | 처리 | 건수 |
|---|---|---|
| play_by_play.ax | 빈 값 → NULL | 12,186 |
| play_by_play.ay | 빈 값 → NULL | 12,186 |
| play_by_play.az | 빈 값 → NULL | 12,186 |
| play_by_play.batter_ID | 소수점 표기 → 정수 | 846 |
| play_by_play.on_1b_id | 빈 값 → NULL | 150,825 |
| play_by_play.on_1b_id | 소수점 표기 → 정수 | 643,836 |
| play_by_play.on_2b_id | 빈 값 → NULL | 181,266 |
| play_by_play.on_2b_id | 소수점 표기 → 정수 | 392,934 |
| play_by_play.on_3b_id | 빈 값 → NULL | 204,724 |
| play_by_play.on_3b_id | 소수점 표기 → 정수 | 203,617 |
| play_by_play.pfx_x | 빈 값 → NULL | 12,186 |
| play_by_play.pfx_x_raw | 빈 값 → NULL | 12,186 |
| play_by_play.pfx_z | 빈 값 → NULL | 12,186 |
| play_by_play.pfx_z_raw | 빈 값 → NULL | 12,186 |
| play_by_play.pitch_number | 빈 값 → NULL | 11,283 |
| play_by_play.pitcher_ID | 소수점 표기 → 정수 | 682 |
| play_by_play.pos_1_id | 소수점 표기 → 정수 | 1,199 |
| play_by_play.pos_2_id | 소수점 표기 → 정수 | 1,199 |
| play_by_play.pos_3_id | 소수점 표기 → 정수 | 1,457 |
| play_by_play.pos_4_id | 소수점 표기 → 정수 | 1,741 |
| play_by_play.pos_5_id | 소수점 표기 → 정수 | 1,592 |
| play_by_play.pos_6_id | 소수점 표기 → 정수 | 1,513 |
| play_by_play.pos_7_id | 소수점 표기 → 정수 | 1,199 |
| play_by_play.pos_8_id | 소수점 표기 → 정수 | 1,487 |
| play_by_play.pos_9_id | 소수점 표기 → 정수 | 1,199 |
| play_by_play.px | 빈 값 → NULL | 12,186 |
| play_by_play.pz | 빈 값 → NULL | 12,186 |
| play_by_play.speed | 빈 값 → NULL | 12,103 |
| play_by_play.sz_bot | 빈 값 → NULL | 12,186 |
| play_by_play.sz_top | 빈 값 → NULL | 12,186 |
| play_by_play.vx0 | 빈 값 → NULL | 12,186 |
| play_by_play.vy0 | 빈 값 → NULL | 12,186 |
| play_by_play.vz0 | 빈 값 → NULL | 12,186 |
| play_by_play.x0 | 빈 값 → NULL | 12,186 |
| play_by_play.y0 | 빈 값 → NULL | 12,186 |
| play_by_play.z0 | 빈 값 → NULL | 12,186 |

## 외래키 고아 행

| 관계 | 고아 행 |
|---|---|
| game_team_stats.team_id → teams.team_id | 0 |
| game_team_stats.game_id → games.game_id | 0 |
| games.away_team_id → teams.team_id | 0 |
| games.home_team_id → teams.team_id | 0 |
| players.team_id → teams.team_id | 0 |
