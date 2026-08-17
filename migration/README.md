# D1 이관 절차

로컬 SQLite(`database/kbo_stats.db`)를 Cloudflare D1으로 옮깁니다.

- 설계: `docs/superpowers/specs/2026-08-17-cloudflare-migration-design.md`
- 계획: `docs/superpowers/plans/2026-08-17-plan-a-data-foundation.md`

## D1 정보

| 항목 | 값 |
|---|---|
| 데이터베이스 이름 | `kbo-stats` |
| database_id | `505c67f5-45ff-42ee-bce9-2f5f00cf90e7` |
| 리전 | APAC |
| 바인딩 이름 | `DB` |

설정은 저장소 루트의 `wrangler.toml` 에 있습니다.

## 순서

```powershell
py migration/restore_derived.py --write  # 파생·마스터 테이블 복원 (최초 1회)
py migration/export_schema.py            # 스키마 SQL 생성
npx wrangler d1 execute kbo-stats --remote --file=migration/out/00_schema.sql
py migration/export_to_d1.py             # 테이블별 INSERT 청크 생성
py migration/load_to_d1.py               # D1 적재
py migration/verify_d1.py                # 행 수 대조
```

## 로컬 DB 에 대해 알아둘 것

`database/kbo_stats.db` 는 전체 스냅샷이 아니라 **2025 시즌 원천만** 담고 있습니다.
2015~2024 와 2026 원천은 EC2 에만 있었고 지금은 되찾을 수 없습니다.

`restore_derived.py` 는 API 가 서빙에 쓰는 파생·마스터 테이블을 다른 사본에서 되살립니다.

| 테이블 | 출처 | 범위 |
|---|---|---|
| `wrc_plus_comparison` | `database/_bak_20260605_dump.sql` | 2015~2026 |
| `weighted_pf_by_batter_season` | 같은 덤프 | 2015~2026 |
| `team_stadium_by_season` | 같은 덤프 | 2015~2025 |
| `statiz_park_factor` | `cricket_project/database/kbo_stats.db` | 2015~2025 |
| `statiz_yearly_constants` | 같은 DB | 2011~2026 |
| `stadium_dim` | 스크립트 내 시드 | 고정 마스터 |

덕분에 wRC+ 화면은 전 시즌이 살아 있고, PBP·공식기록에 기대는 화면만 2025 로 제한됩니다.

`park_factors/build_wrc_plus.py` 와 `build_re24_run_values.py` 는 **실행하지 마십시오.**
둘 다 `DELETE` 후 재삽입이라, 원천이 2025 뿐인 지금 돌리면 복원해 둔 과거 시즌이 사라집니다.
원천을 다시 수집한 뒤에 실행합니다.

## D1 무료 한도

| 항목 | 한도 | 대응 |
|---|---|---|
| 쓰기 | 100,000행/일 | 인덱스 3개라 행당 4쓰기. 하루 25,000행씩 약 10일 |
| 읽기 | 5,000,000행/일 | 인덱스로 스캔량을 줄입니다 |
| SQL 문 길이 | 100,000바이트 | 행 크기가 제각각이라 90KB 기준 적응 분할 |

### 인덱스를 먼저 만들고 적재합니다

D1 은 인덱스 하나당 쓰기 행을 하나 더 셉니다. 실측값입니다.

| 실측 | 결과 |
|---|---|
| 인덱스 6개 상태로 `play_by_play` 1,000행 삽입 | `rows_written` 7,007 |
| 1,000행 테이블에 `CREATE INDEX` 하나 | `rows_written` 1,001 |

두 번째 값 때문에 "인덱스 없이 적재하고 나중에 만들기"를 쓸 수 없습니다. 229,667행에
인덱스를 만들면 단일 DDL 하나가 하루 한도를 넘는데, DDL 은 며칠에 나눌 수 없습니다.
인덱스를 먼저 만들어 두면 비용이 행 단위로 쪼개져 여러 날에 나뉩니다.

`play_by_play` 인덱스는 `gameID`·`batter_ID`·`pitcher_ID` 세 개만 둡니다.
`api/main.py` 는 시즌을 전부 `substr(gameID,1,4)` 로 거르므로 `game_date` 인덱스는
한 번도 쓰이지 않습니다.
| DB 크기 | 500MB | 현재 127.5MB(2025 한 시즌). 시즌당 약 120MB씩 증가합니다 |

원천을 2015~2026 으로 되채우면 약 1.5GB 가 되어 **DB당 500MB 한도를 넘습니다.**
그때는 시즌별로 D1 을 나눠야 합니다(계정 총량은 5GB, Worker 는 D1 바인딩을 여러 개 가질 수 있습니다).
계획 D 에서 다룹니다.

한도는 UTC 자정에 초기화됩니다. 한국 시간 오전 9시 이후에 재개하십시오.

## 재개 방법

`load_to_d1.py` 는 적재에 성공한 청크 파일명을 `migration/out/.progress` 에 한 줄씩 기록합니다.
중단 후 같은 명령을 다시 실행하면 기록에 없는 청크부터 이어서 넣습니다.
`--budget` 은 그날 쓸 쓰기 행 수 상한입니다. `manifest.json` 의 행 수에 테이블별 인덱스 수를
곱해 예산을 세므로, 한도에 부딪혀 실패하는 대신 미리 멈춥니다.

```powershell
# 오늘치만 넣기 (기본 예산 95,000 쓰기)
py migration/load_to_d1.py

# 남은 것 전부 넣기 (한도 무시, 실패하면 그 지점부터 재개)
py migration/load_to_d1.py --budget 0
```

## 되돌리기

작업 전 백업이 `database/kbo_stats.db.bak_YYYYMMDD` 에 있습니다.

D1을 비우려면 스키마 파일을 다시 실행합니다. 이 파일은 `DROP TABLE IF EXISTS` 로 시작합니다.

```powershell
npx wrangler d1 execute kbo-stats --remote --file=migration/out/00_schema.sql
```

## 이 디렉터리에 대하여

`migration/` 은 이관 전용입니다. 이전이 끝나면 통째로 제거할 수 있도록 앱 코드와 분리했습니다.
산출물인 `migration/out/` 과 `migration/golden/` 은 git 비추적입니다.
