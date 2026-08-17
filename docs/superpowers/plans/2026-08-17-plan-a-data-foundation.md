# 계획 A: 데이터 기반 구축 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 로컬 SQLite의 전체 데이터를 Cloudflare D1에 적재하고, API 이식의 정확성을 기계적으로 검증할 골든 정답지를 만듭니다.

**Architecture:** 로컬 SQLite(127.5MB, 237,873행)에서 누락된 파생·마스터 테이블 6종을 먼저 채운 뒤, 테이블별 INSERT 문을 청크로 나눠 `wrangler d1 execute --remote` 로 D1에 적재합니다. D1 무료 쓰기 한도가 하루 10만 행이므로 `play_by_play` 는 3일에 걸쳐 재개 가능한 방식으로 넣습니다. 적재가 끝나면 현재 FastAPI를 로컬에서 띄워 29개 엔드포인트의 응답을 저장해 정답지로 씁니다.

> **[개정 2026-08-17]** 로컬 DB 는 전체 스냅샷이 아니라 **2025 시즌 원천만** 담고 있습니다. 파생 테이블 6종은
> 계산으로 만드는 대신 다른 사본에서 복원했습니다. 경위와 결과는 Task 3 을, 배경은 설계 문서 §1 정정 항목을 보십시오.

**Tech Stack:** Python 3.13, SQLite, Node 24 / npm 11, Cloudflare Wrangler, Cloudflare D1, GitHub Actions, pytest

## Global Constraints

- 예산 0원. 유료 플랜 전환, 도메인 구입, VPS 임차는 금지합니다.
- D1 무료 한도: DB당 저장 500MB, 쓰기 100,000행/일, 읽기 5,000,000행/일, SQL 문 하나당 100,000바이트.
- Workers 무료 한도: 요청 100,000/일, 호출당 CPU 10ms, Cron Trigger 계정당 5개.
- GitHub Actions 무료 한도: 비공개 저장소 월 2,000분.
- 비밀은 git에 두지 않습니다. Cloudflare API 토큰은 GitHub Secrets, `ANTHROPIC_API_KEY` 는 Workers 시크릿에 둡니다.
- 사용자 노출 한국어는 `습니다/합니다/입니다` 정중체를 씁니다.
- 작업 디렉터리는 저장소 루트입니다. 명령은 Windows PowerShell 기준으로 적습니다.
- 로컬 DB 경로: `database/kbo_stats.db`
- D1 데이터베이스 이름: `kbo-stats`

---

## File Structure

| 파일 | 책임 |
|---|---|
| `package.json` | wrangler 의존성 선언 |
| `wrangler.toml` | D1 바인딩 설정 |
| `conftest.py` | pytest가 저장소 루트를 import 경로에 넣도록 하는 빈 파일 |
| `migration/__init__.py` | `migration` 을 패키지로 만드는 빈 파일 |
| `migration/export_schema.py` | SQLite 스키마를 D1 적용용 SQL로 변환 |
| `migration/export_to_d1.py` | SQLite 테이블을 100KB 이하 INSERT 문 청크로 변환 |
| `migration/load_to_d1.py` | 청크 파일을 순서대로 D1에 적재하고 진행 상태를 기록 |
| `migration/verify_d1.py` | 로컬과 D1의 테이블별 행 수를 대조 |
| `migration/golden_matrix.py` | 29개 엔드포인트의 요청 조합을 생성 |
| `migration/golden_capture.py` | 요청 조합을 실행해 응답을 저장 |
| `migration/golden_compare.py` | 두 응답 집합을 비교하고 차이를 보고 |
| `migration/README.md` | 적재 절차와 재개 방법 |
| `tests/test_export_schema.py` | 스키마 변환 검증 (3개) |
| `tests/test_export_to_d1.py` | 청크 분할 로직 검증 (7개) |
| `tests/test_load_to_d1.py` | 재개 로직 검증 (3개) |
| `tests/test_golden_matrix.py` | 요청 조합 생성 검증 (7개) |
| `tests/test_golden_compare.py` | 비교 규칙 검증 (11개) |
| `.github/workflows/daily.yml` | 일일 수집 워크플로. 이 계획에서는 첫 단계만 만듭니다 |

`migration/` 을 앱 코드와 분리한 이유는 이관이 끝나면 통째로 걷어낼 수 있게 하기 위해서입니다.

---

## Task 1: 개발 환경과 D1 데이터베이스 생성

**Files:**
- Create: `package.json`
- Create: `wrangler.toml`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: 없음
- Produces: D1 데이터베이스 `kbo-stats` 와 그 `database_id`. 이후 모든 적재 작업이 `wrangler.toml` 의 바인딩을 사용합니다.

- [ ] **Step 1: Cloudflare 계정을 만듭니다**

브라우저에서 `https://dash.cloudflare.com/sign-up` 에 접속해 이메일과 비밀번호로 가입합니다. 무료 플랜은 카드 등록이 필요 없습니다.

가입 후 이메일 인증을 완료합니다.

- [ ] **Step 2: wrangler를 설치합니다**

```powershell
npm init -y
npm install --save-dev wrangler
npx wrangler --version
```

기대: 버전 문자열이 출력됩니다. 버전이 4 미만이면 `npm install --save-dev wrangler@latest` 로 올립니다.

- [ ] **Step 3: Cloudflare에 로그인합니다**

```powershell
npx wrangler login
```

브라우저가 열리면 권한을 승인합니다. 완료 후 확인합니다.

```powershell
npx wrangler whoami
```

기대: 계정 이메일과 Account ID가 출력됩니다.

- [ ] **Step 4: D1 데이터베이스를 만듭니다**

```powershell
npx wrangler d1 create kbo-stats
```

출력에 `database_id` 가 포함됩니다. 이 값을 다음 단계에서 씁니다.

- [ ] **Step 5: wrangler.toml을 작성합니다**

`<STEP4에서_출력된_ID>` 를 Step 4의 실제 값으로 바꿉니다.

```toml
name = "kbo-api"
main = "src/index.js"
compatibility_date = "2026-08-17"

[[d1_databases]]
binding = "DB"
database_name = "kbo-stats"
database_id = "<STEP4에서_출력된_ID>"
```

`main` 이 가리키는 `src/index.js` 는 계획 B에서 만듭니다. 이 계획에서는 `wrangler d1` 명령만 쓰므로 파일이 없어도 됩니다.

- [ ] **Step 6: .gitignore에 항목을 추가합니다**

파일 끝에 아래를 덧붙입니다.

```
# Node / Cloudflare
node_modules/
.wrangler/

# 이관 중간 산출물
migration/out/
migration/golden/
```

- [ ] **Step 7: D1 연결을 확인합니다**

```powershell
npx wrangler d1 execute kbo-stats --remote --command "SELECT 1 AS ok"
```

기대: `ok` 값 `1` 이 담긴 결과가 출력됩니다. 오류가 나면 Step 3의 로그인 상태와 Step 5의 `database_id` 를 확인합니다.

- [ ] **Step 8: 커밋합니다**

```powershell
git add package.json package-lock.json wrangler.toml .gitignore
git commit -m "chore(migration): wrangler 설정과 D1 데이터베이스 바인딩 추가"
```

---

## Task 2: 로컬 DB 백업과 현재 상태 진단

**Files:**
- Create: `migration/README.md`

**Interfaces:**
- Consumes: `database/kbo_stats.db`
- Produces: `database/kbo_stats.db.bak_YYYYMMDD` 백업 파일. Task 3·4가 원본 DB를 변경하므로 되돌릴 수 있어야 합니다.

- [ ] **Step 1: DB를 백업합니다**

```powershell
$stamp = Get-Date -Format "yyyyMMdd"
Copy-Item "database\kbo_stats.db" "database\kbo_stats.db.bak_$stamp"
Get-ChildItem "database\kbo_stats.db*" | Select-Object Name, @{n='MB';e={[math]::Round($_.Length/1MB,1)}}
```

기대: 원본과 백업이 모두 약 127.5MB로 나옵니다.

- [ ] **Step 2: 현재 테이블 목록을 기록합니다**

```powershell
py -c "import sqlite3;c=sqlite3.connect('database/kbo_stats.db');[print(n) for (n,) in c.execute(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name\")]"
```

기대 출력 (11개):

```
futures_games
futures_teams
game_team_stats
games
kbo_official_batter_stats
kbo_official_pitcher_stats
play_by_play
players
sqlite_sequence
team_logos
teams
```

- [ ] **Step 3: 빠진 테이블을 확인합니다**

아래 6개가 없어야 정상입니다. Task 3·4에서 생성합니다.

```
self_park_factor
wrc_plus_comparison
weighted_pf
re24_matrix_by_season
kbo_run_values_by_season
player_history
```

- [ ] **Step 4: migration/README.md를 작성합니다**

```markdown
# D1 이관 절차

로컬 SQLite(`database/kbo_stats.db`)를 Cloudflare D1(`kbo-stats`)로 옮깁니다.

## 순서

1. `py migration/export_to_d1.py` 로 테이블별 SQL 청크를 `migration/out/` 에 생성합니다.
2. `py migration/load_to_d1.py` 로 청크를 D1에 적재합니다.
3. `py migration/verify_d1.py` 로 행 수를 대조합니다.

## D1 무료 한도

- 쓰기 100,000행/일. `play_by_play` 는 229,667행이므로 3일에 나눠 넣습니다.
- SQL 문 하나당 100,000바이트. `play_by_play` 는 74컬럼 약 257자/행이므로 200행씩 묶습니다.

## 재개 방법

`load_to_d1.py` 는 `migration/out/.progress` 에 적재 완료된 청크 파일명을 한 줄씩 기록합니다.
중단 후 같은 명령을 다시 실행하면 기록에 없는 청크부터 이어서 넣습니다.
일일 한도에 걸리면 D1이 오류를 반환하며, 다음 날 같은 명령으로 재개합니다.

## 되돌리기

작업 전 `database/kbo_stats.db.bak_YYYYMMDD` 로 백업합니다.
D1을 비우려면 `npx wrangler d1 execute kbo-stats --remote --file=migration/out/00_schema.sql` 을
다시 실행합니다. 이 파일은 `DROP TABLE IF EXISTS` 로 시작합니다.
```

- [ ] **Step 5: 커밋합니다**

```powershell
git add migration/README.md
git commit -m "docs(migration): D1 이관 절차 문서 추가"
```

---

## Task 3: 파생·마스터 테이블 복원 — 완료 (2026-08-17)

> **[개정] 당초 계획은 "파크팩터 파이프라인을 돌려 5종을 생성"이었습니다. 실행 불가로 판명되어
> "다른 사본에서 복원"으로 바꿨습니다. 아래는 실제로 수행한 내용입니다.**

### 왜 바꿨는가

Task 2 진단에서 로컬 DB 가 **2025 시즌 원천만** 담고 있음을 확인했습니다(설계 문서 §1 정정 항목 참조).
이 사실이 원래 Task 3 을 두 방향에서 무너뜨립니다.

1. **입력이 없습니다.** `park_factors/build_wrc_plus.py` 는 재빌드 스크립트라 `kbo_woba_weights_by_season`,
   `team_stadium_by_season`, `stadium_dim`, `v_batter_wrc_plus` 뷰가 이미 있어야 동작합니다. 로컬 DB 에는
   넷 다 없었습니다. 게다가 47행이 **기존 `wrc_plus_comparison` 행에서 시즌 상수 L 을 역산**하므로,
   빈 상태에서는 어차피 0행이 나옵니다.
2. **돌리면 손해입니다.** 두 스크립트 모두 `DELETE` 후 재삽입입니다. 원천 PBP 가 2025 뿐인 지금 실행하면
   다른 곳에 남아 있던 2015~2024·2026 파생이 2025 로 덮여 사라집니다.

### 무엇을 했는가

`migration/restore_derived.py` 를 만들어 아래를 복원했습니다.

| 테이블 | 출처 | 결과 |
|---|---|---|
| `wrc_plus_comparison` | `database/_bak_20260605_dump.sql` | 2,140행, 2015~2026 |
| `weighted_pf_by_batter_season` | 같은 덤프 | 3,487행, 2015~2026 |
| `team_stadium_by_season` | 같은 덤프 | 110행, 2015~2025 |
| `statiz_park_factor` | `cricket_project/database/kbo_stats.db` | 100행, 2015~2025 |
| `statiz_yearly_constants` | 같은 DB | 16행, 2011~2026 |
| `stadium_dim` | 스크립트 내 수동 시드 | 16행 |

`self_park_factor`(2025, 9행)는 `compute_self_park_factors.py` 로 생성했습니다. 이 스크립트만은 PBP 만
읽으므로 실행에 문제가 없었고, 작업 전 백업에 해당 테이블이 없어 덮어쓴 것도 없습니다.

- [x] **Step 1: DB 경로 하드코딩을 걷어냅니다**

`park_factors` 세 스크립트의 `DB = '/home/ubuntu/b_project/database/kbo_stats.db'` 를 환경변수 `KBO_DB`
우선, 없으면 저장소 기준 상대경로로 바꿨습니다. EC2 절대경로는 Windows 와 Actions 러너 어디서도
동작하지 않습니다. 지금 실행하지 않더라도 재크롤링 이후 필요하므로 미리 고쳐 둡니다.

- [x] **Step 2: 파크팩터를 계산합니다**

```powershell
py park_factors/compute_self_park_factors.py
```

결과: `self_park_factor` 9행(2025). 2026 은 원천이 없어 0행입니다.

- [x] **Step 3: 복원 대상을 미리 확인합니다**

```powershell
py migration/restore_derived.py
```

기대: 6개 테이블의 출처·행 수·시즌 범위가 출력되고 DB 는 바뀌지 않습니다.

- [x] **Step 4: 복원을 반영합니다**

```powershell
py migration/restore_derived.py --write
```

기대: `kbo_stats.db.bak_<타임스탬프>` 백업이 생기고 6개 테이블이 반영됩니다. 마지막 줄에
`stadium_dim 이 실제 구장명 14개를 모두 덮습니다.` 가 나와야 합니다. 덮지 못한 구장명이 있으면
`STADIUM_DIM` 시드에 추가하고 다시 실행합니다.

- [x] **Step 5: 테이블 수를 확인합니다**

```powershell
py -c "import sqlite3;c=sqlite3.connect('database/kbo_stats.db');print(c.execute(\"SELECT COUNT(*) FROM sqlite_master WHERE type='table'\").fetchone()[0])"
```

결과: `18` (기존 12개 + `self_park_factor` 를 뺀 복원 6개).

- [x] **Step 6: API 를 띄워 전수 확인합니다**

```powershell
py -m uvicorn api.main:app --host 127.0.0.1 --port 8199
```

29개 엔드포인트를 모두 호출해 확인했습니다. HTTP 오류 0건입니다. wRC+ 계열은 `?season=2019` 처럼
과거 시즌을 지정해도 정상 응답합니다.

### 하지 않은 것과 그 이유

| 대상 | 판단 |
|---|---|
| `build_wrc_plus.py` 실행 | **금지.** 돌리면 2015~2024·2026 파생이 사라집니다. 재크롤링 이후에 실행합니다 |
| `build_re24_run_values.py --write` 실행 | **보류.** 2025 PBP 만으로 계산하면 `season=0` 통합 기준선이 한 시즌으로 왜곡됩니다. API 미참조라 급하지 않습니다 |
| `re24_matrix_by_season`, `kbo_run_values_by_season` | 위와 같은 이유로 만들지 않습니다. `api/main.py` 어디에서도 참조하지 않습니다 |

---

## Task 4: player_history — 계획 D로 이월

**당초 계획**: `player_registry_sync.py` 를 실행해 `player_history` 를 만든다.

**변경**: 만들지 않고 넘어갑니다.

계획 수립 당시 `api/main.py` 가 이 테이블을 참조한다고 적었으나, 실제로 확인하니 참조하지 않습니다.
`player_history` 를 쓰는 곳은 `data_collection/player_registry_sync.py` 와
`data_collection/daily_player_detector.py` 뿐이고, 둘 다 수집 파이프라인 내부용입니다.
서빙 경로에 없으므로 D1 적재 대상이 아닙니다.

이 테이블은 선수 속성 변경 이력(SCD Type 2)이라 **시간이 지나며 쌓이는 성격**입니다. 지금 만들면
초기 적재 한 시점만 담긴 껍데기가 됩니다. 크롤러를 Actions 에서 정상 가동한 뒤 자연히 쌓이게 하는 편이
맞습니다. 계획 D 에서 다룹니다.

- [x] **확인: API 가 참조하지 않음을 검증했습니다**

```powershell
py -c "import io,re;s=io.open('api/main.py',encoding='utf-8').read();print('참조 횟수:', len(re.findall('player_history', s)))"
```

기대: `참조 횟수: 0`

---

## Task 5: D1 스키마와 인덱스 생성

**Files:**
- Create: `migration/export_schema.py`
- Create: `migration/out/00_schema.sql` (생성물, git 비추적)

**Interfaces:**
- Consumes: `database/kbo_stats.db` 의 `sqlite_master`
- Produces: D1에 17개 테이블과 인덱스. Task 7·8의 INSERT가 이 스키마에 들어갑니다.

- [ ] **Step 1: 실패하는 테스트를 작성합니다**

`tests/test_export_schema.py` 를 만듭니다.

```python
# -*- coding: utf-8 -*-
import sqlite3

from migration.export_schema import build_schema_sql


def test_drops_before_create():
    """같은 파일을 다시 실행해도 되도록 DROP 이 앞에 옵니다."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (a INTEGER)")
    sql = build_schema_sql(conn)
    assert sql.index("DROP TABLE IF EXISTS \"t\"") < sql.index("CREATE TABLE t")


def test_skips_sqlite_internal_tables():
    """sqlite_sequence 같은 내부 테이블은 직접 만들지 않습니다."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (a INTEGER PRIMARY KEY AUTOINCREMENT)")
    conn.execute("INSERT INTO t DEFAULT VALUES")
    sql = build_schema_sql(conn)
    assert "sqlite_sequence" not in sql


def test_includes_indexes():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (a INTEGER)")
    conn.execute("CREATE INDEX idx_t_a ON t(a)")
    sql = build_schema_sql(conn)
    assert "CREATE INDEX idx_t_a" in sql
```

- [ ] **Step 2: 테스트가 실패하는지 확인합니다**

```powershell
py -m pytest tests/test_export_schema.py -v
```

기대: `ModuleNotFoundError: No module named 'migration.export_schema'` 로 실패합니다.

- [ ] **Step 3: 최소 구현을 작성합니다**

먼저 저장소 루트에 **빈 `conftest.py`** 를 만듭니다. 이 파일이 없으면 pytest가 `tests/` 만 import 경로에 넣어 `from migration...` 이 실패합니다.

```powershell
New-Item -ItemType File conftest.py
New-Item -ItemType Directory -Force migration | Out-Null
New-Item -ItemType File migration\__init__.py
New-Item -ItemType Directory -Force tests | Out-Null
```

그다음 `migration/export_schema.py` 를 작성합니다.

```python
# -*- coding: utf-8 -*-
"""로컬 SQLite 스키마를 D1 적용용 SQL 로 변환합니다."""
import sqlite3
import sys
from pathlib import Path

# SQLite 가 내부적으로 관리하는 테이블. 직접 만들지 않습니다.
INTERNAL = {"sqlite_sequence", "sqlite_stat1", "sqlite_stat4"}

# play_by_play 조회 성능을 위해 추가하는 인덱스.
# game_date 단독 인덱스와 복합 인덱스가 로컬에는 없습니다.
EXTRA_INDEXES = [
    'CREATE INDEX IF NOT EXISTS idx_pbp_date ON play_by_play(game_date)',
    'CREATE INDEX IF NOT EXISTS idx_pbp_pitcher_date ON play_by_play(pitcher_ID, game_date)',
    'CREATE INDEX IF NOT EXISTS idx_pbp_batter_date ON play_by_play(batter_ID, game_date)',
]


def build_schema_sql(conn):
    """DROP + CREATE TABLE + CREATE INDEX 순서의 SQL 문자열을 만듭니다."""
    tables = [
        (name, sql)
        for name, sql in conn.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type='table' AND sql IS NOT NULL ORDER BY name"
        )
        if name not in INTERNAL
    ]
    indexes = [
        sql
        for (sql,) in conn.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type='index' AND sql IS NOT NULL ORDER BY name"
        )
    ]

    parts = []
    for name, _ in reversed(tables):
        parts.append('DROP TABLE IF EXISTS "%s";' % name)
    for _, sql in tables:
        parts.append(sql.strip().rstrip(";") + ";")
    for sql in indexes:
        parts.append(sql.strip().rstrip(";") + ";")
    for sql in EXTRA_INDEXES:
        parts.append(sql + ";")
    return "\n".join(parts) + "\n"


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else "database/kbo_stats.db"
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "migration/out/00_schema.sql")
    out.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    out.write_text(build_schema_sql(conn), encoding="utf-8")
    print("wrote %s" % out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트가 통과하는지 확인합니다**

```powershell
py -m pytest tests/test_export_schema.py -v
```

기대: 3개 모두 PASS

- [ ] **Step 5: 스키마 파일을 생성합니다**

```powershell
py migration/export_schema.py
Get-Content migration\out\00_schema.sql -TotalCount 5
```

기대: `DROP TABLE IF EXISTS` 로 시작하는 내용이 보입니다.

> **[개정 2026-08-17] `EXTRA_INDEXES` 는 빈 목록으로 둡니다.**
>
> 원래 이 계획은 `idx_pbp_date`, `idx_pbp_pitcher_date`, `idx_pbp_batter_date` 를 추가하라고 적었습니다.
> 두 가지 이유로 넣지 않습니다.
>
> **첫째, 그 인덱스는 쓰이지 않습니다.** `api/main.py` 의 play_by_play 쿼리는 시즌을 전부
> `substr(gameID,1,4)` 로 거릅니다. `game_date` 로 거르는 쿼리가 하나도 없습니다.
>
> **둘째, 인덱스마다 적재 일수가 늘어납니다.** D1 은 인덱스 하나당 쓰기 행을 하나 더 셉니다.
> 실측했습니다.
>
> | 실측 | 결과 |
> |---|---|
> | 인덱스 6개 상태로 play_by_play 1,000행 삽입 | `rows_written` = **7,007** |
> | 1,000행 테이블에 `CREATE INDEX` 하나 | `rows_written` = **1,001** |
>
> 두 번째 수치가 중요합니다. "인덱스 없이 적재하고 나중에 만들기"가 불가능하다는 뜻입니다.
> 229,667행에 인덱스를 만들면 단일 DDL 하나가 229,667 쓰기라 하루 한도 100,000 을 그 자체로
> 넘고, DDL 은 며칠에 나눠 실행할 수 없습니다. **인덱스를 먼저 만들어 두고 적재해야** 비용이
> 행 단위로 쪼개져 여러 날에 나뉩니다.
>
> 그래서 로컬에 이미 있는 세 개(`gameID`, `batter_ID`, `pitcher_ID`)만 옮깁니다. 행당 쓰기는
> 1 + 3 = 4 이고, 하루 25,000행씩 넣게 됩니다.

- [ ] **Step 6: D1에 스키마를 적용합니다**

```powershell
npx wrangler d1 execute kbo-stats --remote --file=migration/out/00_schema.sql
```

기대: 오류 없이 완료됩니다. `AUTOINCREMENT` 나 외래키 구문에서 오류가 나면 해당 문장을 출력해 확인합니다.

- [ ] **Step 7: D1에 테이블이 생겼는지 확인합니다**

```powershell
npx wrangler d1 execute kbo-stats --remote --command "SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table'"
```

기대: **16 이상.** 로컬 17개 중 `sqlite_sequence` 는 직접 만들지 않으므로 16개가 생성되고, AUTOINCREMENT 사용으로 `sqlite_sequence` 가 자동 생성되면 17개가 됩니다. D1 내부 테이블이 더 잡힐 수도 있습니다.

- [ ] **Step 8: 커밋합니다**

```powershell
git add conftest.py migration/__init__.py migration/export_schema.py tests/test_export_schema.py
git commit -m "feat(migration): SQLite 스키마를 D1 적용용 SQL 로 변환하는 도구 추가"
```

---

## Task 6: 청크 분할 적재 도구 작성

**Files:**
- Create: `migration/export_to_d1.py`
- Create: `tests/test_export_to_d1.py`

**Interfaces:**
- Consumes: `database/kbo_stats.db`
- Produces:
  - `export_table(conn, table, out_dir, rows_per_file=1000, order=0) -> list[tuple[Path, int]]` — 테이블 하나를 청크 SQL 파일들로 내보내고 (경로, 행수) 목록을 반환합니다. `order` 는 파일명 앞의 2자리 순번입니다.
  - `build_statements(table, columns, rows, max_stmt_bytes=90000) -> list[str]` — 행 목록을 크기 한도를 지키는 INSERT 문 여러 개로 나눕니다.
  - `TABLE_ORDER: list[str]` — 적재 순서를 정한 테이블 이름 20개. `migration/verify_d1.py` 가 이 목록을 재사용합니다.
  - `missing_from_order(conn) -> list[str]` — DB 에는 있는데 `TABLE_ORDER` 에 없는 테이블을 알려줍니다.
  - `rows_to_insert(table, columns, rows) -> str` — 행 묶음을 INSERT 문 하나로 만듭니다.
  - `sql_literal(value) -> str` — 파이썬 값을 SQL 리터럴로 변환합니다.
  - `migration/out/manifest.json` — 파일별 테이블·행수·바이트. 로더가 하루 쓰기 예산을 세는 데 씁니다.
  - 파일명 규칙: `{순번2자리}_{테이블명}_{청크번호4자리}.sql` (예: `20_play_by_play_0001.sql`)

> **[개정 2026-08-17] 고정 200행 묶음을 버리고, 크기 기준 적응 분할로 바꿨습니다.**
>
> 계획은 "play_by_play 74컬럼 약 257자/행이므로 200행이면 55KB" 라고 적었습니다. 실측하니
> **행당 1,299바이트**로 5배 틀렸고, 200행이면 260KB 라 100KB 한도를 넘습니다. 행 크기는
> 테이블마다 크게 다릅니다.
>
> | 테이블 | 행당 평균 | 행당 최대 |
> |---|---|---|
> | `team_logos` | 14,080 B | **87,593 B** (로고가 통째로 들어 있습니다) |
> | `play_by_play` | 1,299 B | 1,483 B |
> | `team_stadium_by_season` | 120 B | 130 B |
>
> 그래서 행을 하나씩 붙여 보며 90KB 를 넘기 직전에 문을 끊습니다(`build_statements`).
> 그리고 파일 하나에 INSERT 문을 여러 개 담습니다. `wrangler d1 execute --file` 이 파일 안의
> 문을 순서대로 실행하므로 호출 횟수가 크게 줍니다. 파일당 1,000행 기준으로 250개 파일이 나오고,
> 가장 큰 파일이 0.55MB 입니다. 이 크기가 D1 에 들어가는 것을 실측으로 확인했습니다(4.7초).

- [ ] **Step 1: 실패하는 테스트를 작성합니다**

`tests/test_export_to_d1.py` 를 만듭니다.

```python
# -*- coding: utf-8 -*-
import sqlite3

from migration.export_to_d1 import export_table, rows_to_insert, sql_literal


def test_sql_literal_escapes_single_quote():
    assert sql_literal("O'Brien") == "'O''Brien'"


def test_sql_literal_handles_none():
    assert sql_literal(None) == "NULL"


def test_sql_literal_keeps_numbers_unquoted():
    assert sql_literal(3) == "3"
    assert sql_literal(1.5) == "1.5"


def test_rows_to_insert_builds_multi_row_statement():
    sql = rows_to_insert("t", ["a", "b"], [(1, "x"), (2, "y")])
    assert sql.startswith('INSERT INTO "t" ("a","b") VALUES')
    assert "(1,'x')" in sql
    assert "(2,'y')" in sql
    assert sql.endswith(";")


def test_export_table_splits_by_batch_size(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (a INTEGER)")
    conn.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(250)])
    files = export_table(conn, "t", tmp_path, batch_size=100, order=5)
    assert len(files) == 3
    assert files[0].name == "05_t_0001.sql"
    assert files[2].name == "05_t_0003.sql"


def test_export_table_statement_stays_under_limit(tmp_path):
    """D1 은 SQL 문 하나가 100,000 바이트를 넘으면 거부합니다."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (a TEXT)")
    conn.executemany("INSERT INTO t VALUES (?)", [("x" * 200,) for _ in range(400)])
    files = export_table(conn, "t", tmp_path, batch_size=200, order=5)
    for f in files:
        assert len(f.read_bytes()) < 100_000


def test_export_table_empty_returns_no_files(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (a INTEGER)")
    files = export_table(conn, "t", tmp_path, batch_size=100, order=5)
    assert files == []
```

- [ ] **Step 2: 테스트가 실패하는지 확인합니다**

```powershell
py -m pytest tests/test_export_to_d1.py -v
```

기대: `ModuleNotFoundError: No module named 'migration.export_to_d1'` 로 실패합니다.

- [ ] **Step 3: 최소 구현을 작성합니다**

`migration/export_to_d1.py` 를 작성합니다.

```python
# -*- coding: utf-8 -*-
"""SQLite 테이블을 D1 적재용 INSERT 청크 파일로 내보냅니다.

D1 제약:
  - SQL 문 하나가 100,000 바이트를 넘을 수 없습니다.
  - 무료 플랜은 하루 100,000 행까지 씁니다.
play_by_play 는 74컬럼 약 257자/행이므로 200행 묶음이면 문 하나가 약 55KB 입니다.
"""
import sqlite3
import sys
from pathlib import Path

# 적재 순서. 참조되는 쪽을 먼저 넣습니다.
TABLE_ORDER = [
    "teams",
    "team_logos",
    "futures_teams",
    "players",
    "player_history",
    "games",
    "game_team_stats",
    "futures_games",
    "kbo_official_batter_stats",
    "kbo_official_pitcher_stats",
    "self_park_factor",
    "weighted_pf",
    "wrc_plus_comparison",
    "re24_matrix_by_season",
    "kbo_run_values_by_season",
    "play_by_play",
]

MAX_STATEMENT_BYTES = 100_000


def sql_literal(value):
    """파이썬 값을 SQL 리터럴 문자열로 바꿉니다."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, bytes):
        return "X'%s'" % value.hex()
    return "'" + str(value).replace("'", "''") + "'"


def rows_to_insert(table, columns, rows):
    """행 묶음을 다중 VALUES INSERT 문 하나로 만듭니다."""
    cols = ",".join('"%s"' % c for c in columns)
    values = ",".join(
        "(" + ",".join(sql_literal(v) for v in row) + ")" for row in rows
    )
    return 'INSERT INTO "%s" (%s) VALUES %s;' % (table, cols, values)


def export_table(conn, table, out_dir, batch_size=200, order=0):
    """테이블 하나를 청크 SQL 파일들로 내보내고 경로 목록을 반환합니다."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    columns = [r[1] for r in conn.execute('PRAGMA table_info("%s")' % table)]
    if not columns:
        return []

    cur = conn.execute('SELECT * FROM "%s"' % table)
    files = []
    chunk_no = 0
    while True:
        rows = cur.fetchmany(batch_size)
        if not rows:
            break
        stmt = rows_to_insert(table, columns, rows)
        if len(stmt.encode("utf-8")) > MAX_STATEMENT_BYTES:
            raise ValueError(
                "%s 청크 %d 이 100KB 를 넘었습니다. batch_size 를 줄이십시오."
                % (table, chunk_no + 1)
            )
        chunk_no += 1
        path = out_dir / ("%02d_%s_%04d.sql" % (order, table, chunk_no))
        path.write_text(stmt + "\n", encoding="utf-8")
        files.append(path)
    return files


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else "database/kbo_stats.db"
    out_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "migration/out")
    conn = sqlite3.connect(db)
    total = 0
    for i, table in enumerate(TABLE_ORDER, start=1):
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            print("건너뜀 (테이블 없음): %s" % table)
            continue
        files = export_table(conn, table, out_dir, batch_size=200, order=i)
        n = conn.execute('SELECT COUNT(*) FROM "%s"' % table).fetchone()[0]
        total += n
        print("%-32s %8d행 -> 청크 %d개" % (table, n, len(files)))
    print("합계 %d행" % total)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트가 통과하는지 확인합니다**

```powershell
py -m pytest tests/test_export_to_d1.py -v
```

기대: 7개 모두 PASS

- [ ] **Step 5: 실제 청크를 생성합니다**

```powershell
py migration/export_to_d1.py
```

기대: 테이블별 행 수와 청크 개수가 출력되고 마지막에 `합계 232094행` 부근의 값이 나옵니다. `play_by_play` 는 약 1,149개 청크가 생깁니다.

- [ ] **Step 6: 청크 크기를 확인합니다**

```powershell
Get-ChildItem migration\out\*.sql | Sort-Object Length -Descending | Select-Object -First 3 Name, Length
```

기대: 가장 큰 파일도 100,000바이트 미만입니다.

- [ ] **Step 7: 커밋합니다**

```powershell
git add migration/export_to_d1.py tests/test_export_to_d1.py
git commit -m "feat(migration): SQLite 테이블을 D1 청크 SQL 로 내보내는 도구 추가"
```

---

## Task 7: 재개 가능한 적재 도구 작성과 소형 테이블 적재

**Files:**
- Create: `migration/load_to_d1.py`
- Create: `migration/verify_d1.py`

**Interfaces:**
- Consumes: `migration/out/*.sql`, Task 1의 `wrangler.toml`
- Produces:
  - `load_chunks(files, db_name, progress_path, limit=None) -> tuple[int, int]` — (성공 수, 실패 수) 를 반환하고 성공한 파일명을 `progress_path` 에 한 줄씩 기록합니다.
  - `pending_files(all_files, progress_path) -> list[Path]` — 아직 적재하지 않은 파일 목록을 반환합니다.

- [ ] **Step 1: 실패하는 테스트를 작성합니다**

`tests/test_load_to_d1.py` 를 만듭니다.

```python
# -*- coding: utf-8 -*-
from pathlib import Path

from migration.load_to_d1 import pending_files


def test_pending_excludes_recorded(tmp_path):
    a = tmp_path / "01_t_0001.sql"
    b = tmp_path / "01_t_0002.sql"
    a.write_text("x", encoding="utf-8")
    b.write_text("y", encoding="utf-8")
    progress = tmp_path / ".progress"
    progress.write_text("01_t_0001.sql\n", encoding="utf-8")
    assert pending_files([a, b], progress) == [b]


def test_pending_returns_all_when_no_progress(tmp_path):
    a = tmp_path / "01_t_0001.sql"
    a.write_text("x", encoding="utf-8")
    progress = tmp_path / ".progress"
    assert pending_files([a], progress) == [a]


def test_pending_ignores_blank_lines(tmp_path):
    a = tmp_path / "01_t_0001.sql"
    a.write_text("x", encoding="utf-8")
    progress = tmp_path / ".progress"
    progress.write_text("\n\n", encoding="utf-8")
    assert pending_files([a], progress) == [a]
```

- [ ] **Step 2: 테스트가 실패하는지 확인합니다**

```powershell
py -m pytest tests/test_load_to_d1.py -v
```

기대: `ModuleNotFoundError: No module named 'migration.load_to_d1'` 로 실패합니다.

- [ ] **Step 3: 최소 구현을 작성합니다**

`migration/load_to_d1.py` 를 작성합니다.

```python
# -*- coding: utf-8 -*-
"""청크 SQL 파일을 D1 에 순서대로 적재합니다.

D1 무료 플랜은 하루 100,000 행까지 씁니다. play_by_play 는 229,667 행이므로
--limit 으로 하루치만 넣고, 다음 날 같은 명령을 다시 실행해 이어서 넣습니다.
성공한 파일은 .progress 에 기록되어 두 번 넣지 않습니다.
"""
import argparse
import subprocess
import sys
from pathlib import Path


def pending_files(all_files, progress_path):
    """아직 적재하지 않은 파일 목록을 반환합니다."""
    progress_path = Path(progress_path)
    done = set()
    if progress_path.exists():
        for line in progress_path.read_text(encoding="utf-8").splitlines():
            name = line.strip()
            if name:
                done.add(name)
    return [f for f in all_files if Path(f).name not in done]


def load_chunks(files, db_name, progress_path, limit=None):
    """청크를 하나씩 D1 에 적재하고 (성공 수, 실패 수) 를 반환합니다."""
    progress_path = Path(progress_path)
    targets = files if limit is None else files[:limit]
    ok = 0
    fail = 0
    for i, f in enumerate(targets, start=1):
        f = Path(f)
        cmd = [
            "npx", "wrangler", "d1", "execute", db_name,
            "--remote", "--file=%s" % f.as_posix(), "--yes",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            ok += 1
            with progress_path.open("a", encoding="utf-8") as fh:
                fh.write(f.name + "\n")
            print("[%d/%d] OK   %s" % (i, len(targets), f.name))
        else:
            fail += 1
            print("[%d/%d] FAIL %s" % (i, len(targets), f.name))
            print(result.stderr.strip()[:500])
            break  # 한도 초과일 가능성이 높으므로 즉시 중단합니다
    return ok, fail


def main():
    ap = argparse.ArgumentParser(description="청크 SQL 을 D1 에 적재합니다")
    ap.add_argument("--dir", default="migration/out")
    ap.add_argument("--db", default="kbo-stats")
    ap.add_argument("--limit", type=int, default=None,
                    help="이번 실행에서 적재할 최대 청크 수")
    ap.add_argument("--pattern", default="*.sql",
                    help="적재 대상 파일 패턴 (예: 16_play_by_play_*.sql)")
    args = ap.parse_args()

    out_dir = Path(args.dir)
    progress = out_dir / ".progress"
    all_files = sorted(f for f in out_dir.glob(args.pattern)
                       if f.name != "00_schema.sql")
    todo = pending_files(all_files, progress)
    print("전체 %d개, 남은 것 %d개" % (len(all_files), len(todo)))
    if not todo:
        print("적재할 청크가 없습니다.")
        return 0

    ok, fail = load_chunks(todo, args.db, progress, args.limit)
    print("성공 %d, 실패 %d" % (ok, fail))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 테스트가 통과하는지 확인합니다**

```powershell
py -m pytest tests/test_load_to_d1.py -v
```

기대: 3개 모두 PASS

- [ ] **Step 5: 검증 도구를 작성합니다**

`migration/verify_d1.py` 를 작성합니다.

```python
# -*- coding: utf-8 -*-
"""로컬 SQLite 와 D1 의 테이블별 행 수를 대조합니다."""
import argparse
import json
import sqlite3
import subprocess
import sys

from migration.export_to_d1 import TABLE_ORDER


def d1_count(db_name, table):
    """D1 에서 테이블 행 수를 조회합니다. 실패하면 None 을 반환합니다."""
    cmd = [
        "npx", "wrangler", "d1", "execute", db_name, "--remote", "--json",
        "--command", 'SELECT COUNT(*) AS n FROM "%s"' % table,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
        return payload[0]["results"][0]["n"]
    except (ValueError, KeyError, IndexError):
        return None


def main():
    ap = argparse.ArgumentParser(description="로컬과 D1 의 행 수를 대조합니다")
    ap.add_argument("--local", default="database/kbo_stats.db")
    ap.add_argument("--db", default="kbo-stats")
    args = ap.parse_args()

    conn = sqlite3.connect(args.local)
    mismatched = 0
    print("%-32s %10s %10s  %s" % ("테이블", "로컬", "D1", "판정"))
    print("-" * 66)
    for table in TABLE_ORDER:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            continue
        local_n = conn.execute('SELECT COUNT(*) FROM "%s"' % table).fetchone()[0]
        remote_n = d1_count(args.db, table)
        if remote_n is None:
            verdict = "조회실패"
            mismatched += 1
        elif remote_n == local_n:
            verdict = "일치"
        else:
            verdict = "불일치"
            mismatched += 1
        print("%-32s %10d %10s  %s" % (table, local_n, remote_n, verdict))
    print("-" * 66)
    print("불일치 %d건" % mismatched)
    return 1 if mismatched else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: 소형 테이블만 적재합니다**

`play_by_play` 를 제외한 15개 테이블을 넣습니다. 합계 약 2,400행이라 한도에 여유가 있습니다.

```powershell
py migration/load_to_d1.py --pattern "0*.sql"
py migration/load_to_d1.py --pattern "1[0-5]_*.sql"
```

기대: 모든 청크가 OK 로 출력됩니다.

- [ ] **Step 7: 소형 테이블을 검증합니다**

```powershell
py migration/verify_d1.py
```

기대: `play_by_play` 만 불일치(D1 0행)이고 나머지는 전부 일치입니다.

- [ ] **Step 8: 커밋합니다**

```powershell
git add migration/load_to_d1.py migration/verify_d1.py tests/test_load_to_d1.py
git commit -m "feat(migration): 재개 가능한 D1 적재 도구와 행 수 검증 도구 추가"
```

---

## Task 8: play_by_play 3일 분할 적재

**Files:**
- Modify: 없음 (Task 7의 도구를 사용합니다)

**Interfaces:**
- Consumes: `migration/out/16_play_by_play_*.sql` 약 1,149개 청크
- Produces: D1의 `play_by_play` 229,667행

청크 하나가 200행이므로 하루 한도 100,000행은 **청크 450개**에 해당합니다. 안전 여유를 두고 하루 400개씩 넣습니다.

- [ ] **Step 1: 1일차를 적재합니다**

```powershell
py migration/load_to_d1.py --pattern "16_play_by_play_*.sql" --limit 400
```

기대: 400개가 OK 로 출력됩니다. 약 80,000행이 들어갑니다.

중간에 FAIL 이 나면서 한도 관련 오류가 보이면 그날은 중단하고 다음 날 재개합니다. 진행 상태는 `migration/out/.progress` 에 남아 있습니다.

- [ ] **Step 2: 1일차 결과를 확인합니다**

```powershell
npx wrangler d1 execute kbo-stats --remote --command "SELECT COUNT(*) AS n FROM play_by_play"
```

기대: 약 80,000

- [ ] **Step 3: 하루 기다린 뒤 2일차를 적재합니다**

D1 일일 한도는 UTC 자정에 초기화됩니다. 한국 시간 오전 9시 이후에 실행합니다.

```powershell
py migration/load_to_d1.py --pattern "16_play_by_play_*.sql" --limit 400
```

기대: 남은 것 749개 중 400개가 OK 로 출력됩니다.

- [ ] **Step 4: 하루 기다린 뒤 3일차를 적재합니다**

```powershell
py migration/load_to_d1.py --pattern "16_play_by_play_*.sql"
```

`--limit` 없이 실행해 남은 349개를 모두 넣습니다.

- [ ] **Step 5: 전체를 검증합니다**

```powershell
py migration/verify_d1.py
```

기대: 모든 테이블이 일치하고 `불일치 0건` 이 출력됩니다.

- [ ] **Step 6: 인덱스가 살아 있는지 확인합니다**

```powershell
npx wrangler d1 execute kbo-stats --remote --command "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='play_by_play'"
```

기대: `idx_pbp_game`, `idx_pbp_batter`, `idx_pbp_pitcher`, `idx_pbp_date`, `idx_pbp_pitcher_date`, `idx_pbp_batter_date` 가 보입니다.

- [ ] **Step 7: 저장 용량을 확인합니다**

```powershell
npx wrangler d1 info kbo-stats
```

기대: 크기가 500MB 한도보다 충분히 작습니다. 200MB를 넘으면 설계 문서 6장의 증가 전망을 다시 검토합니다.

- [ ] **Step 8: 커밋합니다**

```powershell
git commit --allow-empty -m "chore(migration): play_by_play 229,667행 D1 적재 완료"
```

---

## Task 9: 골든 응답 요청 조합 생성

**Files:**
- Create: `migration/golden_matrix.py`
- Create: `tests/test_golden_matrix.py`

**Interfaces:**
- Consumes: `database/kbo_stats.db` (실제 존재하는 선수 ID와 시즌을 뽑기 위해)
- Produces: `build_matrix(conn) -> list[dict]` — 각 항목은 `{"name": str, "path": str, "params": dict}` 입니다. `name` 은 파일명으로 쓰이므로 영숫자와 밑줄만 씁니다.

설계 문서 10장의 파라미터 규칙을 따릅니다. 결과 0건과 존재하지 않는 ID를 반드시 포함합니다.

- [ ] **Step 1: 실패하는 테스트를 작성합니다**

`tests/test_golden_matrix.py` 를 만듭니다.

```python
# -*- coding: utf-8 -*-
import sqlite3

from migration.golden_matrix import build_matrix, safe_name


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE players (player_id TEXT, player_name TEXT, is_active INTEGER)")
    conn.executemany(
        "INSERT INTO players VALUES (?,?,?)",
        [("1001", "가나다", 1), ("1002", "라마바", 1), ("1003", "사아자", 0)],
    )
    conn.execute("CREATE TABLE games (season INTEGER)")
    conn.executemany("INSERT INTO games VALUES (?)", [(2025,), (2026,)])
    return conn


def test_safe_name_strips_special_characters():
    assert safe_name("/stats/batters?season=2025") == "stats_batters_season_2025"


def test_matrix_covers_every_endpoint_path():
    matrix = build_matrix(_conn())
    paths = {item["path"].split("?")[0] for item in matrix}
    # 29개 엔드포인트의 고유 경로 패턴이 모두 등장해야 합니다
    assert "/dashboard/stats" in paths
    assert "/teams" in paths
    assert "/stats/batters" in paths
    assert "/wrc/leaderboard" in paths
    assert "/db/tables" in paths


def test_matrix_includes_nonexistent_id_case():
    matrix = build_matrix(_conn())
    names = {item["name"] for item in matrix}
    assert any("nonexistent" in n for n in names)


def test_matrix_includes_zero_result_case():
    matrix = build_matrix(_conn())
    assert any(item["params"].get("min_pa") == 999 for item in matrix)


def test_matrix_names_are_unique():
    matrix = build_matrix(_conn())
    names = [item["name"] for item in matrix]
    assert len(names) == len(set(names))


def test_hangul_and_empty_query_do_not_collide():
    """safe_name 이 한글을 지우므로 q=김 과 q= 의 이름이 겹칠 수 있습니다."""
    matrix = build_matrix(_conn())
    search = [i for i in matrix if i["path"] == "/players/search"]
    names = [i["name"] for i in search]
    assert len(search) == 3
    assert len(names) == len(set(names))


def test_matrix_is_deterministic():
    """같은 DB 로 두 번 만들면 이름과 순서가 같아야 합니다."""
    a = build_matrix(_conn())
    b = build_matrix(_conn())
    assert [i["name"] for i in a] == [i["name"] for i in b]
```

- [ ] **Step 2: 테스트가 실패하는지 확인합니다**

```powershell
py -m pytest tests/test_golden_matrix.py -v
```

기대: `ModuleNotFoundError: No module named 'migration.golden_matrix'` 로 실패합니다.

- [ ] **Step 3: 최소 구현을 작성합니다**

`migration/golden_matrix.py` 를 작성합니다.

```python
# -*- coding: utf-8 -*-
"""골든 응답 비교에 쓸 요청 조합을 만듭니다.

설계 문서 10장의 규칙을 따릅니다.
  - 파라미터 없음(기본값)
  - 실제 존재하는 값과 존재하지 않는 값
  - 데이터가 있는 시즌과 없는 시즌
  - 경계값 (limit=1, min_pa=0, min_pa=999)
  - 정렬·방향 파라미터의 모든 지원 값
"""
import re
import sqlite3
import sys

NONEXISTENT_PLAYER_ID = "99999999"
EMPTY_SEASON = 1990  # 데이터가 없는 시즌
DB_TABLES = ["players", "teams", "games", "play_by_play"]


def safe_name(text):
    """경로와 파라미터를 파일명으로 쓸 수 있는 문자열로 바꿉니다."""
    return re.sub(r"_+", "_", re.sub(r"[^0-9a-zA-Z]+", "_", text)).strip("_")


def _sample_players(conn, n=3):
    rows = conn.execute(
        "SELECT player_id FROM players ORDER BY player_id LIMIT ?", (n,)
    ).fetchall()
    return [str(r[0]) for r in rows]


def _seasons(conn):
    rows = conn.execute(
        "SELECT DISTINCT season FROM games ORDER BY season DESC LIMIT 2"
    ).fetchall()
    return [int(r[0]) for r in rows]


def _add(matrix, path, params=None, tag=""):
    params = params or {}
    key = path + ("_" + tag if tag else "")
    if params:
        key += "_" + "_".join("%s_%s" % (k, params[k]) for k in sorted(params))
    name = safe_name(key)

    # safe_name 이 한글 등 ASCII 외 문자를 지우므로 q=김 과 q= 의 이름이 같아집니다.
    # 파일이 덮어써지지 않도록 겹치면 번호를 붙입니다. 목록 순서가 같으면
    # 매번 같은 이름이 나오므로 정답지와 실제 응답의 파일명이 어긋나지 않습니다.
    existing = {item["name"] for item in matrix}
    if name in existing:
        n = 2
        while "%s_%d" % (name, n) in existing:
            n += 1
        name = "%s_%d" % (name, n)

    matrix.append({"name": name, "path": path, "params": params})


def build_matrix(conn):
    """요청 조합 목록을 만듭니다."""
    players = _sample_players(conn)
    seasons = _seasons(conn)
    season = seasons[0] if seasons else 2026
    prev = seasons[1] if len(seasons) > 1 else season - 1
    matrix = []

    # 파라미터 없는 엔드포인트
    for path in ["/", "/dashboard/stats", "/teams", "/stats/seasons",
                 "/stats/regulation", "/standings", "/db/tables",
                 "/schedule", "/schedule/futures", "/leaders"]:
        _add(matrix, path)

    # 시즌 파라미터
    for path in ["/games", "/leaders"]:
        for s in (season, prev, EMPTY_SEASON):
            _add(matrix, path, {"season": s})

    # 타자·투수 기록: 경계값 포함
    for path, minkey in [("/stats/batters", "min_pa"), ("/stats/pitchers", "min_ip")]:
        _add(matrix, path, {"season": season})
        _add(matrix, path, {"season": season, "limit": 1})
        _add(matrix, path, {"season": season, minkey: 0})
        _add(matrix, path, {"season": season, minkey: 999})
        _add(matrix, path, {"season": EMPTY_SEASON})

    # 선수 상세: 존재하는 ID 3개 + 존재하지 않는 ID
    for pid in players:
        for suffix in ["", "/news", "/arsenal", "/usage"]:
            _add(matrix, "/players/%s%s" % (pid, suffix))
    for suffix in ["", "/news", "/arsenal", "/usage"]:
        _add(matrix, "/players/%s%s" % (NONEXISTENT_PLAYER_ID, suffix),
             tag="nonexistent")

    # 선수 검색
    for q in ["김", "zzzz", ""]:
        _add(matrix, "/players/search", {"q": q})

    # 기간별 팀 기록
    _add(matrix, "/stats/team_range", {"start": "%d0301" % season,
                                       "end": "%d1031" % season})
    _add(matrix, "/stats/team_range", {"start": "%d0301" % season,
                                       "end": "%d0301" % season})

    # wRC+ 계열
    _add(matrix, "/wrc/seasons")
    _add(matrix, "/wrc/seasons", {"min_pa": 0})
    for s in (season, EMPTY_SEASON):
        _add(matrix, "/wrc/by-stadium", {"season": s})
        _add(matrix, "/wrc/distribution", {"season": s, "min_pa": 100})
        for sort in ("half", "full"):
            _add(matrix, "/wrc/leaderboard", {"season": s, "sort": sort, "n": 5})
        for direction in ("up", "down"):
            _add(matrix, "/wrc/top-changes", {"season": s, "direction": direction, "n": 5})
    for pid in players:
        _add(matrix, "/wrc/batter/%s" % pid)
    _add(matrix, "/wrc/batter/%s" % NONEXISTENT_PLAYER_ID, tag="nonexistent")
    _add(matrix, "/wrc/batter-search", {"q": "김", "season": season})
    _add(matrix, "/wrc/batter-search", {"q": "zzzz", "season": season})

    # DB 탐색
    for t in DB_TABLES:
        _add(matrix, "/db/table/%s" % t, {"limit": 5, "offset": 0})
        _add(matrix, "/db/table/%s" % t, {"limit": 5, "offset": 1000000},
             tag="far_offset")
        _add(matrix, "/db/table/%s/csv" % t, {"limit": 5})
    _add(matrix, "/db/table/no_such_table", {"limit": 5}, tag="nonexistent")

    # 로고
    _add(matrix, "/logo/LG")
    _add(matrix, "/logo/ZZ", tag="nonexistent")

    # 날짜 지정 일정
    _add(matrix, "/schedule", {"date": "%d0401" % season})
    _add(matrix, "/schedule/futures", {"date": "%d0401" % season})

    return matrix


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else "database/kbo_stats.db"
    conn = sqlite3.connect(db)
    matrix = build_matrix(conn)
    for item in matrix:
        print("%-60s %s" % (item["path"], item["params"]))
    print("총 %d개 요청" % len(matrix))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트가 통과하는지 확인합니다**

```powershell
py -m pytest tests/test_golden_matrix.py -v
```

기대: 7개 모두 PASS

- [ ] **Step 5: 실제 조합 수를 확인합니다**

```powershell
py migration/golden_matrix.py
```

기대: 100개 이상의 요청이 나열되고 마지막에 총 개수가 출력됩니다.

- [ ] **Step 6: 커밋합니다**

```powershell
git add migration/golden_matrix.py tests/test_golden_matrix.py
git commit -m "feat(migration): 골든 응답 비교용 요청 조합 생성기 추가"
```

---

## Task 10: 골든 응답 저장과 비교 도구

**Files:**
- Create: `migration/golden_capture.py`
- Create: `migration/golden_compare.py`
- Create: `tests/test_golden_compare.py`

**Interfaces:**
- Consumes: Task 9의 `build_matrix(conn)`
- Produces:
  - `capture(base_url, matrix, out_dir, timeout=60) -> tuple[int, int]` — (성공 수, 실패 수). 응답을 `{out_dir}/{name}.json` 에 `{"status": int, "body": ...}` 형태로 저장합니다.
  - `_body_of(resp) -> dict | list` — JSON 이 아닌 응답은 `__content_type__`, `__length__`, `__sha256__` 요약으로 바꿉니다.
  - `compare_values(expected, actual, path="", rel_tol=1e-9) -> list[str]` — 차이 설명 문자열 목록을 반환합니다. 빈 목록이면 동일합니다.
  - `compare_dirs(expected_dir, actual_dir, rel_tol=1e-9) -> dict` — `{"same": int, "different": list[str], "missing": list[str]}`

- [ ] **Step 1: 실패하는 테스트를 작성합니다**

`tests/test_golden_compare.py` 를 만듭니다.

```python
# -*- coding: utf-8 -*-
from migration.golden_compare import compare_values


def test_identical_returns_no_difference():
    assert compare_values({"a": 1}, {"a": 1}) == []


def test_float_within_tolerance_is_same():
    assert compare_values({"a": 0.1 + 0.2}, {"a": 0.3}) == []


def test_float_beyond_tolerance_differs():
    diffs = compare_values({"a": 1.0}, {"a": 1.001})
    assert len(diffs) == 1
    assert "a" in diffs[0]


def test_int_and_string_are_different():
    """player_id 는 타입까지 같아야 합니다."""
    diffs = compare_values({"player_id": 1001}, {"player_id": "1001"})
    assert len(diffs) == 1


def test_null_and_empty_string_are_different():
    diffs = compare_values({"a": None}, {"a": ""})
    assert len(diffs) == 1


def test_null_and_zero_are_different():
    diffs = compare_values({"a": None}, {"a": 0})
    assert len(diffs) == 1


def test_missing_key_is_reported():
    diffs = compare_values({"a": 1, "b": 2}, {"a": 1})
    assert len(diffs) == 1
    assert "b" in diffs[0]


def test_extra_key_is_reported():
    diffs = compare_values({"a": 1}, {"a": 1, "b": 2})
    assert len(diffs) == 1
    assert "b" in diffs[0]


def test_list_order_matters():
    diffs = compare_values([1, 2], [2, 1])
    assert diffs != []


def test_list_length_difference_is_reported():
    diffs = compare_values([1, 2], [1])
    assert len(diffs) == 1


def test_nested_path_appears_in_message():
    diffs = compare_values({"rows": [{"x": 1}]}, {"rows": [{"x": 2}]})
    assert "rows[0].x" in diffs[0]
```

- [ ] **Step 2: 테스트가 실패하는지 확인합니다**

```powershell
py -m pytest tests/test_golden_compare.py -v
```

기대: `ModuleNotFoundError: No module named 'migration.golden_compare'` 로 실패합니다.

- [ ] **Step 3: 비교 도구를 작성합니다**

`migration/golden_compare.py` 를 작성합니다.

```python
# -*- coding: utf-8 -*-
"""두 응답 집합을 비교합니다.

설계 문서 10장의 비교 규칙:
  - 부동소수점은 상대 오차 1e-9 이내면 같다고 봅니다.
  - 정수·문자열은 타입까지 완전 일치를 요구합니다.
  - 배열 순서는 그대로 비교합니다.
  - null, 빈 문자열, 0 을 구분합니다.
"""
import argparse
import json
import math
import sys
from pathlib import Path


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def compare_values(expected, actual, path="", rel_tol=1e-9):
    """두 값을 비교하고 차이 설명 목록을 반환합니다."""
    loc = path or "(root)"

    # 부동소수점 허용 오차. 단 int 와 float 의 혼용은 타입 차이로 봅니다.
    if _is_number(expected) and _is_number(actual):
        if isinstance(expected, float) or isinstance(actual, float):
            if isinstance(expected, float) and isinstance(actual, float):
                if math.isclose(expected, actual, rel_tol=rel_tol, abs_tol=1e-12):
                    return []
                return ["%s: 기대 %r, 실제 %r" % (loc, expected, actual)]
            return ["%s: 타입이 다릅니다. 기대 %s(%r), 실제 %s(%r)"
                    % (loc, type(expected).__name__, expected,
                       type(actual).__name__, actual)]
        if expected == actual:
            return []
        return ["%s: 기대 %r, 실제 %r" % (loc, expected, actual)]

    if type(expected) is not type(actual):
        return ["%s: 타입이 다릅니다. 기대 %s(%r), 실제 %s(%r)"
                % (loc, type(expected).__name__, expected,
                   type(actual).__name__, actual)]

    if isinstance(expected, dict):
        diffs = []
        for key in sorted(set(expected) | set(actual)):
            child = "%s.%s" % (path, key) if path else key
            if key not in actual:
                diffs.append("%s: 응답에 없습니다" % child)
            elif key not in expected:
                diffs.append("%s: 정답지에 없습니다" % child)
            else:
                diffs.extend(compare_values(expected[key], actual[key], child, rel_tol))
        return diffs

    if isinstance(expected, list):
        if len(expected) != len(actual):
            return ["%s: 길이가 다릅니다. 기대 %d, 실제 %d"
                    % (loc, len(expected), len(actual))]
        diffs = []
        for i, (e, a) in enumerate(zip(expected, actual)):
            diffs.extend(compare_values(e, a, "%s[%d]" % (path, i), rel_tol))
        return diffs

    if expected == actual:
        return []
    return ["%s: 기대 %r, 실제 %r" % (loc, expected, actual)]


def compare_dirs(expected_dir, actual_dir, rel_tol=1e-9):
    """두 디렉터리의 같은 이름 JSON 파일들을 비교합니다."""
    expected_dir = Path(expected_dir)
    actual_dir = Path(actual_dir)
    same = 0
    different = []
    missing = []
    for ef in sorted(expected_dir.glob("*.json")):
        af = actual_dir / ef.name
        if not af.exists():
            missing.append(ef.name)
            continue
        e = json.loads(ef.read_text(encoding="utf-8"))
        a = json.loads(af.read_text(encoding="utf-8"))
        diffs = compare_values(e, a, "", rel_tol)
        if diffs:
            different.append("%s\n    %s" % (ef.name, "\n    ".join(diffs[:5])))
        else:
            same += 1
    return {"same": same, "different": different, "missing": missing}


def main():
    ap = argparse.ArgumentParser(description="골든 응답을 비교합니다")
    ap.add_argument("expected_dir")
    ap.add_argument("actual_dir")
    ap.add_argument("--rel-tol", type=float, default=1e-9)
    args = ap.parse_args()

    result = compare_dirs(args.expected_dir, args.actual_dir, args.rel_tol)
    print("일치 %d건" % result["same"])
    if result["missing"]:
        print("\n응답 파일 없음 %d건" % len(result["missing"]))
        for name in result["missing"]:
            print("  " + name)
    if result["different"]:
        print("\n불일치 %d건" % len(result["different"]))
        for entry in result["different"]:
            print("  " + entry)
    return 1 if (result["different"] or result["missing"]) else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 테스트가 통과하는지 확인합니다**

```powershell
py -m pytest tests/test_golden_compare.py -v
```

기대: 11개 모두 PASS

- [ ] **Step 5: 저장 도구를 작성합니다**

`migration/golden_capture.py` 를 작성합니다.

```python
# -*- coding: utf-8 -*-
"""요청 조합을 실행해 응답을 저장합니다."""
import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import requests

from migration.golden_matrix import build_matrix


def _body_of(resp):
    """응답 본문을 비교 가능한 형태로 바꿉니다.

    JSON 이 아니면(예: /logo/{code} 는 PNG) 바이트를 그대로 두지 않고
    해시와 길이로 요약합니다. 인코딩 추정 때문에 비교가 흔들리는 것을 막습니다.
    """
    try:
        return resp.json()
    except ValueError:
        return {
            "__content_type__": resp.headers.get("content-type", ""),
            "__length__": len(resp.content),
            "__sha256__": hashlib.sha256(resp.content).hexdigest(),
        }


def capture(base_url, matrix, out_dir, timeout=60):
    """각 요청을 실행해 {out_dir}/{name}.json 으로 저장합니다."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = 0
    fail = 0
    for i, item in enumerate(matrix, start=1):
        url = base_url.rstrip("/") + item["path"]
        try:
            resp = requests.get(url, params=item["params"], timeout=timeout)
            payload = {"status": resp.status_code, "body": _body_of(resp)}
            (out_dir / (item["name"] + ".json")).write_text(
                json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2),
                encoding="utf-8",
            )
            ok += 1
        except requests.RequestException as exc:
            fail += 1
            print("[%d/%d] FAIL %s: %s" % (i, len(matrix), item["name"], exc))
        if i % 20 == 0:
            print("[%d/%d] 진행 중" % (i, len(matrix)))
    return ok, fail


def main():
    ap = argparse.ArgumentParser(description="응답을 저장합니다")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--db", default="database/kbo_stats.db")
    ap.add_argument("--out", default="migration/golden/expected")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    matrix = build_matrix(conn)
    print("요청 %d개를 %s 로 보냅니다" % (len(matrix), args.base_url))
    ok, fail = capture(args.base_url, matrix, args.out)
    print("저장 %d건, 실패 %d건 -> %s" % (ok, fail, args.out))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: 커밋합니다**

```powershell
git add migration/golden_capture.py migration/golden_compare.py tests/test_golden_compare.py
git commit -m "feat(migration): 골든 응답 저장·비교 도구 추가"
```

---

## Task 11: 골든 정답지 생성

**Files:**
- Create: `migration/golden/expected/*.json` (생성물, git 비추적)

**Interfaces:**
- Consumes: Task 10의 `capture`, 로컬 FastAPI
- Produces: 계획 B가 Worker 응답을 대조할 정답지

- [ ] **Step 1: FastAPI 의존성을 설치합니다**

```powershell
py -m pip install fastapi uvicorn requests
```

- [ ] **Step 2: 로컬 API 서버를 띄웁니다**

새 PowerShell 창을 열어 저장소 루트에서 실행합니다.

```powershell
py -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

기대: `Uvicorn running on http://127.0.0.1:8000` 이 출력됩니다.

- [ ] **Step 3: 서버가 응답하는지 확인합니다**

원래 창에서 실행합니다.

```powershell
py -c "import requests;r=requests.get('http://127.0.0.1:8000/teams', timeout=10);print(r.status_code, len(r.text))"
```

기대: `200` 과 0보다 큰 길이가 출력됩니다.

- [ ] **Step 4: 정답지를 생성합니다**

```powershell
py migration/golden_capture.py --out migration/golden/expected
```

기대: `실패 0건` 으로 끝납니다. 실패가 있으면 해당 엔드포인트의 서버 로그를 확인합니다.

- [ ] **Step 5: 생성 결과를 확인합니다**

```powershell
(Get-ChildItem migration\golden\expected\*.json | Measure-Object).Count
```

기대: Task 9 Step 5에서 확인한 요청 수와 같습니다.

- [ ] **Step 6: 비교 도구가 자기 자신과 일치하는지 확인합니다**

정답지를 복사해 비교하면 반드시 전부 일치해야 합니다. 비교 도구의 건전성 점검입니다.

```powershell
Copy-Item -Recurse migration\golden\expected migration\golden\selfcheck
py migration/golden_compare.py migration/golden/expected migration/golden/selfcheck
```

기대: `일치 N건` 만 출력되고 불일치가 0입니다.

- [ ] **Step 7: 점검용 사본을 지웁니다**

```powershell
Remove-Item -Recurse -Force migration\golden\selfcheck
```

- [ ] **Step 8: 정답지를 보존합니다**

`migration/golden/` 은 git 비추적입니다. 계획 B에서 쓸 때까지 지우지 않도록 압축 사본을 남깁니다.

```powershell
Compress-Archive -Path migration\golden\expected\* -DestinationPath migration\golden\expected_backup.zip -Force
Get-Item migration\golden\expected_backup.zip | Select-Object Name, @{n='KB';e={[math]::Round($_.Length/1KB,1)}}
```

- [ ] **Step 9: 커밋합니다**

```powershell
git commit --allow-empty -m "chore(migration): 골든 정답지 생성 완료"
```

---

## Task 12: GitHub Actions에서 KBO 접근 가능 여부 판명

**Files:**
- Create: `.github/workflows/daily.yml`

**Interfaces:**
- Consumes: `data_collection/selenium_batter_scraper.py`
- Produces: 위험 1의 판정 결과. 이 결과가 계획 D의 내용을 결정합니다.

설계 문서 7장 위험 1을 판정합니다. 이 워크플로는 최종 `daily.yml` 의 첫 단계이므로 버려지는 코드가 아닙니다.

- [ ] **Step 1: 워크플로를 작성합니다**

`.github/workflows/daily.yml` 을 만듭니다.

```yaml
name: daily

# 이 단계에서는 수동 실행만 합니다. 정기 실행은 계획 D 에서 추가합니다.
on:
  workflow_dispatch:

jobs:
  official-stats:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: 의존성 설치
        run: |
          python -m pip install --upgrade pip
          pip install selenium webdriver-manager beautifulsoup4 lxml requests pandas

      - name: KBO 사이트 도달 여부 확인
        run: |
          python - <<'PY'
          import requests
          r = requests.get("https://www.koreabaseball.com/Record/Player/HitterBasic/Basic1.aspx", timeout=30)
          print("status:", r.status_code)
          print("length:", len(r.text))
          snippet = r.text[:300].replace("\n", " ")
          print("snippet:", snippet)
          r.raise_for_status()
          PY

      - name: Selenium 으로 타자 기록 수집
        env:
          CHROMEDRIVER_PATH: /usr/bin/chromedriver
        run: |
          sudo apt-get update
          sudo apt-get install -y chromium-browser chromium-chromedriver
          python data_collection/selenium_batter_scraper.py

      - name: 산출물 업로드
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: official-stats-output
          path: |
            logs/
            *.csv
          if-no-files-found: warn
```

- [ ] **Step 2: 커밋하고 push합니다**

```powershell
git add .github/workflows/daily.yml
git commit -m "ci(daily): 공식 기록 수집 워크플로 1단계 추가"
git push
```

- [ ] **Step 3: 워크플로를 수동 실행합니다**

브라우저에서 `https://github.com/Seunggon-Kim/b_project/actions/workflows/daily.yml` 로 이동해 `Run workflow` 를 누릅니다.

- [ ] **Step 4: 첫 단계 결과를 판독합니다**

`KBO 사이트 도달 여부 확인` 단계의 로그를 봅니다.

| 결과 | 판정 |
|---|---|
| `status: 200` 이고 `length` 가 수만 이상 | **KBO 접근 가능.** HTTP 전환은 계획 D의 최적화 항목으로 둡니다 |
| `status: 403` 또는 연결 타임아웃 | **IP 대역 차단.** 설계 7장 위험 1의 2번(Cloudflare Worker)부터 시도합니다 |
| `status: 200` 이지만 내용이 차단 안내 페이지 | **차단.** 위 403과 같게 처리합니다 |

- [ ] **Step 5: Selenium 단계 결과를 판독합니다**

| 결과 | 판정 |
|---|---|
| 수집 성공 | 설계대로 진행합니다 |
| HTTP는 200인데 Selenium만 실패 | **브라우저 지문 탐지.** HTTP 직접 호출 전환을 계획 D가 아닌 즉시 과제로 올립니다 |
| 둘 다 실패 | 위험 1의 3단 사다리를 순서대로 시도합니다 |

- [ ] **Step 6: 판정 결과를 설계 문서에 기록합니다**

`docs/superpowers/specs/2026-08-17-cloudflare-migration-design.md` 의 7장 위험 1 항목 끝에 아래 형식으로 한 줄 추가합니다. 대괄호 안은 Step 4·5의 실제 결과로 채웁니다.

```markdown
**판정 (2026-MM-DD)**: HTTP 상태 [실제값], Selenium [성공 또는 실패]. 대응은 [사다리 N번] 으로 진행합니다.
```

- [ ] **Step 7: 커밋합니다**

```powershell
git add docs/superpowers/specs/2026-08-17-cloudflare-migration-design.md
git commit -m "docs(spec): 위험 1 판정 결과 기록"
git push
```

---

## 완료 기준

계획 A가 끝나면 아래가 모두 참이어야 합니다.

- [ ] `npx wrangler d1 execute kbo-stats --remote --command "SELECT 1"` 이 성공합니다
- [ ] `py migration/verify_d1.py` 가 `불일치 0건` 을 출력합니다
- [ ] D1의 `play_by_play` 가 229,667행입니다
- [ ] `play_by_play` 에 인덱스 6개가 있습니다
- [ ] `npx wrangler d1 info kbo-stats` 의 크기가 500MB 미만입니다
- [ ] `py -m pytest tests/ -v` 가 전부 통과합니다 (31개)
- [ ] `migration/golden/expected/` 에 요청 조합 수만큼 JSON 파일이 있습니다
- [ ] `migration/golden/expected_backup.zip` 이 존재합니다
- [ ] 설계 문서 7장에 위험 1 판정 결과가 기록되어 있습니다

## 계획 A에서 하지 않는 것

- **데이터 최신화**: D1에 넣는 것은 **2025 시즌 원천**과, 다른 사본에서 복원한 파생 테이블(wRC+ 계열은 2015~2026)입니다. 2015~2024·2026 원천 재크롤링은 계획 D에서 수행합니다. 정답지와 D1이 같은 데이터를 보므로 골든 비교에는 지장이 없습니다.
- **`/wrc/seasons` 의 시즌 목록 제한**: 이 엔드포인트는 시즌 목록을 `play_by_play` 에서 뽑아 파생 테이블과 조인합니다(`api/main.py:834`). PBP 가 2025 뿐이라 화면 셀렉터에 2025 만 나옵니다. 데이터는 살아 있고 원천을 되채우면 자동으로 풀립니다. 지금 고치면 골든 정답지의 기준이 흔들리므로 **코드를 건드리지 않습니다.** 계획 D 재크롤링 이후 재확인 항목입니다.
- **`re24_matrix_by_season` / `kbo_run_values_by_season` 생성**: 2025 PBP 만으로 계산하면 통합 기준선이 왜곡되고, `api/main.py` 가 참조하지 않습니다. 계획 D로 미룹니다.
- **`player_history` 생성**: API 미참조이며 시간에 따라 쌓이는 이력 테이블입니다. 계획 D로 미룹니다.
- **API 이식**: 계획 B에서 합니다.
- **프론트엔드 변경**: 계획 C에서 합니다.
- **정기 실행 설정**: `daily.yml` 은 이 계획에서 `workflow_dispatch` 만 둡니다. 정기 실행과 D1 적재 단계는 계획 D에서 붙입니다.
