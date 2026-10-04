# migration/

데이터 저장소를 옮기며 쓴 도구와, 지금도 쓰는 MySQL(Cloud SQL) 도구가 있습니다.

- 2026-08: 로컬 SQLite → Cloudflare D1
- 2026-10: D1 → Cloud SQL(MySQL). 사이트가 MySQL 을 읽고, 수집도 MySQL 에만 씁니다.
- 2026-10-04: 수집 쪽에서 D1 을 걷어냈습니다. D1 에 쓰거나 D1 을 읽던 도구
  (`d1_to_sqlite.py`, `load_to_d1.py`, `export_to_d1.py`, `shard_*.py`,
  `verify_d1.py` 등)는 지웠습니다. 필요하면 git 기록에서 찾으십시오.

## 지금 쓰는 것

| 파일 | 하는 일 | 누가 부르나 |
|---|---|---|
| `mysql/ci_proxy.sh` | 러너에서 Cloud SQL Auth Proxy 를 띄우고 접속 파일을 만듭니다 | 네 워크플로 |
| `mysql/mysql_to_sqlite.py` | MySQL 표를 러너의 임시 SQLite 로 내려받습니다(`PIPELINE_TABLES`) | weekly·monthly |
| `sqlite_to_d1.py` | 임시 SQLite 에서 계산한 표를 MySQL 에 통째로 바꿔 넣습니다(이름은 예전 그대로) | weekly·monthly |
| `export_csv.py` | 전체 내려받기 CSV 를 만듭니다 | weekly |
| `mysql/conn.py` | MySQL 접속(`BSTATS_MYSQL_SETTINGS`) | 위 도구들 |
| `mysql/schema.sql` 외 | MySQL 표 정의와 1단계 적재 도구(`ddl.py`, `load.py`, `verify.py`, `repair.py`) | 손 |

## 손 도구(MySQL 에만 씁니다)

| 파일 | 하는 일 |
|---|---|
| `fill_games_from_pbp_day.py` | 문자중계는 있는데 games 가 안 만들어진 날을 채웁니다 |
| `fill_missing_games.py` | 처음 수집 때 빠진 정규시즌 경기 4개를 다시 받아 넣었습니다(2026-10-03) |
| `fix_games_final_score.py` | games 최종 점수를 끝내기 득점까지 넣어 고쳤습니다(2026-10-03) |
| `fix_games_from_naver.py` | PBP 가 없거나 끊긴 경기 7개의 결과를 네이버 값으로 넣었습니다(2026-10-03) |

모두 미리보기가 기본이고 `--write` 를 줘야 씁니다.

## 로컬 DB 에 대해 알아둘 것

`database/kbo_stats.db` 는 전체 스냅샷이 아니라 **2025 시즌 원천만** 담고 있습니다.
2015~2024 와 2026 원천은 EC2 에만 있었고 지금은 되찾을 수 없습니다. 원본은 MySQL 입니다.

`restore_derived.py` 는 API 가 서빙에 쓰는 파생·마스터 테이블을 다른 사본에서 로컬에 되살립니다.

| 테이블 | 출처 | 범위 |
|---|---|---|
| `wrc_plus_comparison` | `database/_bak_20260605_dump.sql` | 2015~2026 |
| `weighted_pf_by_batter_season` | 같은 덤프 | 2015~2026 |
| `team_stadium_by_season` | 같은 덤프 | 2015~2025 |
| `statiz_park_factor` | `cricket_project/database/kbo_stats.db` | 2015~2025 |
| `statiz_yearly_constants` | 같은 DB | 2011~2026 |
| `stadium_dim` | 스크립트 내 시드 | 고정 마스터 |

로컬 DB 를 대상으로 `park_factors/build_wrc_plus.py` 와 `build_re24_run_values.py` 를
돌리지 마십시오. 둘 다 `DELETE` 후 재삽입이라, 원천이 2025 뿐인 로컬에서 돌리면 복원해 둔
과거 시즌이 사라집니다. 정기 계산은 weekly 가 MySQL 에서 내려받아 합니다.

## 남겨 둔 것

- `shard_plan.json`: D1 시절 play_by_play 샤드 배정표입니다. Worker 쪽 사본(`src/lib/shard.js`)과
  맞는지 `test/shard.test.js` 가 봅니다. Worker 에서 D1 을 걷어낼 때 함께 지웁니다.
- `*.sql`(`add_indexes.sql`, `delete_*.sql`, `fix_game_type_2016_2017.sql`, `roster_schema.sql`):
  D1 시절 손으로 한 번 돌린 SQL 기록입니다. 코드는 이 파일들을 읽지 않습니다.

## 이 디렉터리에 대하여

산출물인 `migration/out/` 과 `migration/golden/` 은 git 비추적입니다.
