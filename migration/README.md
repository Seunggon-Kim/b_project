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
py migration/export_schema.py            # 스키마 SQL 생성
npx wrangler d1 execute kbo-stats --remote --file=migration/out/00_schema.sql
py migration/export_to_d1.py             # 테이블별 INSERT 청크 생성
py migration/load_to_d1.py               # D1 적재
py migration/verify_d1.py                # 행 수 대조
```

## D1 무료 한도

| 항목 | 한도 | 대응 |
|---|---|---|
| 쓰기 | 100,000행/일 | `play_by_play` 229,667행이라 3일에 나눠 넣습니다 |
| 읽기 | 5,000,000행/일 | 인덱스로 스캔량을 줄입니다 |
| SQL 문 길이 | 100,000바이트 | 74컬럼 약 257자/행이므로 200행씩 묶습니다 |
| DB 크기 | 500MB | 현재 127.5MB. 시즌당 약 120MB씩 증가합니다 |

한도는 UTC 자정에 초기화됩니다. 한국 시간 오전 9시 이후에 재개하십시오.

## 재개 방법

`load_to_d1.py` 는 적재에 성공한 청크 파일명을 `migration/out/.progress` 에 한 줄씩 기록합니다.
중단 후 같은 명령을 다시 실행하면 기록에 없는 청크부터 이어서 넣습니다.

```powershell
# 하루치만 넣기
py migration/load_to_d1.py --pattern "16_play_by_play_*.sql" --limit 400

# 남은 것 전부 넣기
py migration/load_to_d1.py --pattern "16_play_by_play_*.sql"
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
