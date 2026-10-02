# 2B 이중 적재 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 수집 스크립트가 D1 에 쓴 내용을 Cloud SQL MySQL 에도 같게 쓰고, 매일 두 DB 를 대조하며, 주간 파생 지표는 MySQL 에서 내려받아 계산합니다.

**Architecture:** D1 에 쓰는 코드는 그대로 둡니다. 새 모듈 `data_collection/mysql_sink.py` 가 파라미터 바인딩으로 MySQL 에 쓰고, 각 스크립트는 D1 적재가 끝난 뒤 `mirror(작업, 함수)` 를 한 번 부릅니다. 스위치(`BSTATS_MYSQL_MIRROR`)가 꺼져 있으면 아무것도 하지 않습니다. GitHub Actions 는 키 없는 GCP 인증(Workload Identity Federation)과 Cloud SQL Auth Proxy 로 붙고, 저장소 변수 `MYSQL_MIRROR=on` 일 때만 켭니다. MySQL 이 실패해도 D1 적재는 계속하고, 워크플로 마지막 판정이 빨간색으로 알립니다.

**Tech Stack:** Python 3.11+, PyMySQL, MySQL 8.4(Cloud SQL), sqlite3, pytest, GitHub Actions, google-github-actions/auth, Cloud SQL Auth Proxy v2.26.0

## Global Constraints

- 저장소 `Seunggon-Kim/b_project` 는 **공개**입니다. 서버 IP·비밀번호·키·`~/.bstats/` 내용을 코드·문서·커밋·로그에 넣지 않습니다. 비밀번호·토큰은 화면에 찍지 않습니다.
- 회사 계정(evan@delivered.co.kr)·회사 GCP 를 쓰지 않습니다. gcloud 는 늘 `--configuration=bstats --project=bstats-kbo` 를 붙이고, `default` 설정은 건드리지 않으며, `gcloud auth application-default login` 은 하지 않습니다. Git Bash 에서 gcloud 앞에 `export CLOUDSDK_PYTHON="/c/Users/김승곤/AppData/Local/Google/Cloud SDK/google-cloud-sdk/platform/bundledpython/python.exe" PYTHONUTF8=1` 가 필요합니다.
- push·병합·배포는 건마다 evan 허락을 받습니다. GCP 변경(Task 1)과 스위치 켜기(Task 9)는 evan 승인 뒤에 합니다.
- D1 쓰기는 하지 않습니다. D1 읽기는 1만 행이 넘으면 먼저 `PYTHONUTF8=1 py -m migration.mysql.d1_usage` 로 오늘 사용량을 봅니다.
- **D1 쪽 동작은 바꾸지 않습니다.** 코드를 옮기기만 하는 곳은 두 군데입니다. `add_new_players.py` 의 UPDATE 문 만들기를 함수로 옮기고(같은 글자가 나오는지 테스트로 고정), `sync_players_from_roster.py` 의 비교 SQL·고르기를 함수로 나눕니다(D1 에 보내는 SQL 글자는 같음).
- MySQL 접속은 Auth Proxy 로만 합니다. 로컬 프록시는 백그라운드 작업 2시간 한도가 있어 긴 일 앞에 다시 띄웁니다.
- Python 은 `py`. 테스트: `PYTHONUTF8=1 py -m pytest <경로> -p no:cacheprovider -q`. 전체의 알려진 실패 2개(`tests/test_cron_table_parity.py`, `tests/test_workflow_deps.py`) 외 새 실패 0. `test_workflow_deps` 의 실패 메시지에 이번에 부르는 새 모듈이 새로 나타나면 그 테스트의 `ENTRYPOINTS` 에 넣습니다.
- 커밋 메시지 끝: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- 사용자에게 보이는 한국어는 `습니다/합니다` 체, 이모지 금지.
- 작업 위치: `git -C C:/Users/김승곤/Desktop/b_project worktree add C:/tmp/b_project_2b -b feat/mysql-phase2-dual-write main` 로 만든 worktree. 2A·2C 가 main 에 먼저 들어갔으면 그 위에서 시작합니다.

## 흐름

```
수집 스크립트 ──▶ D1 (지금 그대로, 사이트가 읽음)
       │
       └─ mirror("작업", 함수) ──▶ MySQL (BSTATS_MYSQL_MIRROR 가 shadow 일 때)
                                     실패 → logs 의 jsonl 에 남김 → 워크플로 판정이 빨강

daily 끝 ── reconcile ──▶ D1 과 MySQL 대조(행 수·값·경기별 플레이 수)
weekly ── MySQL 에서 내려받기 ──▶ 계산 ──▶ D1 과 MySQL 에 결과 표
```

## 파일 지도

| 파일 | 할 일 | Task |
|---|---|---|
| `data_collection/mysql_sink.py` (새) | MySQL 쓰기 도구와 `mirror()` | 2 |
| `tests/conftest.py` (새) | 테스트용 `FakeSink`·`fake_sink` | 2 |
| `data_collection/daily_pbp_to_d1.py` | 하루치 PBP 이중 적재, `--mysql-only`(D1 → MySQL 따라잡기) | 3 |
| `data_collection/{daily_games_to_d1,futures_to_d1,csv_to_d1,record_job_run}.py` | 덮어쓰기형 이중 적재 | 4 |
| `data_collection/{roster_to_d1,sync_players_from_roster,add_new_players,futures_records}.py` | 명단·선수 이중 적재 | 5 |
| `migration/sqlite_to_d1.py`, `data_collection/heal_player_photos.py` | 표 통째 바꾸기·사진 주소 | 6 |
| `migration/mysql/ci_proxy.sh` (새), `migration/mysql/reconcile.py` (새), daily·roster·monthly 워크플로 | Actions 접속·대조·판정 | 7 |
| `migration/mysql/mysql_to_sqlite.py` (새), `migration/mysql/compare_derived.py` (새), weekly 워크플로 | 주간 계산을 MySQL 에서 | 8 |
| (운영) | 켜기·따라잡기·7일 지켜보기 | 9 |

---

### Task 1: GCP·MySQL·GitHub 준비 (evan 승인 뒤, 사람이 함께)

GitHub Actions 가 키 없이 GCP 에 붙도록 Workload Identity Federation 을 만들고, 수집 전용 서비스 계정과 MySQL 계정을 만듭니다.

| 무엇 | 이름 | 권한 |
|---|---|---|
| 서비스 계정 | `bstats-loader@bstats-kbo.iam.gserviceaccount.com` | `roles/cloudsql.client` 만 |
| WIF 풀·공급자 | `github` / `b-project` | 이 저장소(저장소 ID)의 `main` 에서 돈 실행만 |
| MySQL 계정 | `'bstats_loader'@'cloudsqlproxy~%'` | `bstats.*` 에 SELECT·INSERT·UPDATE·DELETE |

막히면(조직 정책·WIF 오류) 서비스 계정 키(JSON)를 시크릿에 두는 방식으로 돌아갑니다. 그때는 `ci_proxy.sh` 에 `--credentials-file` 을 쓰고 Task 7 의 인증 단계를 바꿉니다. 그 전환은 evan 에게 먼저 묻습니다.

- [ ] **Step 1: 준비**

```bash
export CLOUDSDK_PYTHON="/c/Users/김승곤/AppData/Local/Google/Cloud SDK/google-cloud-sdk/platform/bundledpython/python.exe" PYTHONUTF8=1
G="gcloud --configuration=bstats --project=bstats-kbo"
$G config list account --format='value(core.account)'
```

Expected: evan 의 **개인** 계정이 나옵니다. 회사 계정이면 멈춥니다.

```bash
$G services enable iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com
```

- [ ] **Step 2: 서비스 계정**

```bash
$G iam service-accounts create bstats-loader --display-name="bstats collectors (GitHub Actions)"
$G projects add-iam-policy-binding bstats-kbo \
  --member="serviceAccount:bstats-loader@bstats-kbo.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client" --condition=None
```

키는 만들지 않습니다.

- [ ] **Step 3: Workload Identity Federation**

저장소 이름은 바뀔 수 있어 바뀌지 않는 저장소 ID 로 묶습니다.

```bash
REPO_ID=$(gh api repos/Seunggon-Kim/b_project --jq .id)
$G iam workload-identity-pools create github --location=global --display-name="GitHub Actions"
$G iam workload-identity-pools providers create-oidc b-project \
  --location=global --workload-identity-pool=github \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository_id=='${REPO_ID}' && assertion.ref=='refs/heads/main'"
NUM=$($G projects describe bstats-kbo --format='value(projectNumber)')
$G iam service-accounts add-iam-policy-binding bstats-loader@bstats-kbo.iam.gserviceaccount.com \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${NUM}/locations/global/workloadIdentityPools/github/attribute.repository_id/${REPO_ID}"
$G iam workload-identity-pools providers describe b-project --location=global \
  --workload-identity-pool=github --format='value(name)' > ~/.bstats/gcp_wif_provider.txt
```

Expected: 마지막 파일에 `projects/<번호>/locations/global/workloadIdentityPools/github/providers/b-project` 한 줄.

- [ ] **Step 4: MySQL 계정(root 로, 프록시 경유)**

프록시를 띄웁니다(백그라운드).

```bash
~/.bstats/bin/cloud-sql-proxy.exe --credentials-file ~/.bstats/sa-migrator.json \
  --address 127.0.0.1 --port 3307 bstats-kbo:asia-northeast3:bstats-mysql > C:/tmp/cloud_sql_proxy.log 2>&1
```

```bash
PYTHONUTF8=1 py - <<'EOF'
import pathlib, secrets, string
import pymysql
home = pathlib.Path.home() / ".bstats"
pw = home / "mysql_loader_password.txt"
if not pw.exists():
    pw.write_text("".join(secrets.choice(string.ascii_letters + string.digits)
                          for _ in range(32)), encoding="ascii")
con = pymysql.connect(host="127.0.0.1", port=3307, user="root",
                      password=(home / "cloudsql_root_password.txt").read_text().strip(),
                      server_public_key=(home / "mysql_server_rsa_pub.pem").read_bytes())
with con.cursor() as cur:
    cur.execute("CREATE USER IF NOT EXISTS 'bstats_loader'@'cloudsqlproxy~%%' IDENTIFIED BY %s",
                (pw.read_text().strip(),))
    cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON `bstats`.* TO 'bstats_loader'@'cloudsqlproxy~%'")
    cur.execute("SHOW GRANTS FOR 'bstats_loader'@'cloudsqlproxy~%'")
    for r in cur.fetchall():
        print(r[0])
con.commit()
con.close()
EOF
```

Expected: `GRANT USAGE ON *.* …` 와 `GRANT SELECT, INSERT, UPDATE, DELETE ON \`bstats\`.* …` 두 줄. root 로그인이 1045 로 막히면 멈추고 evan 에게 알립니다.

- [ ] **Step 5: 수집 계정으로 붙어 보기(로컬)**

```bash
PYTHONUTF8=1 py - <<'EOF'
import json, pathlib
home = pathlib.Path.home() / ".bstats"
(home / "mysql_loader_proxy.json").write_text(json.dumps({
    "host": "127.0.0.1", "port": 3307, "database": "bstats", "user": "bstats_loader",
    "password_file": str(home / "mysql_loader_password.txt"), "ssl_ca": None,
    "server_public_key_file": str(home / "mysql_server_rsa_pub.pem")}), encoding="utf-8")
EOF
BSTATS_MYSQL_SETTINGS=~/.bstats/mysql_loader_proxy.json PYTHONUTF8=1 py - <<'EOF'
import pymysql
from migration.mysql import conn
c = conn.connect()
with c.cursor() as cur:
    cur.execute("SELECT COUNT(*) FROM teams")
    print("teams", cur.fetchone()[0])
    try:
        cur.execute("CREATE TABLE _probe (a INT)")
        print("문제: 표를 만들 수 있습니다")
    except pymysql.err.OperationalError as e:
        print("표 만들기 거부(정상)", e.args[0])
c.close()
EOF
```

Expected: `teams 14`, `표 만들기 거부(정상) 1142`.

- [ ] **Step 6: GitHub 시크릿 등록(evan 이 직접)**

값은 대화창에 붙이지 않습니다. evan 이 파일을 직접 열어 GitHub 화면(Settings → Secrets and variables → Actions → New repository secret)에 넣습니다.

| 시크릿 | 값 |
|---|---|
| `GCP_WIF_PROVIDER` | `~/.bstats/gcp_wif_provider.txt` 내용 |
| `GCP_LOADER_SA` | `bstats-loader@bstats-kbo.iam.gserviceaccount.com` |
| `CLOUDSQL_INSTANCE` | `bstats-kbo:asia-northeast3:bstats-mysql` |
| `MYSQL_LOADER_PASSWORD` | `~/.bstats/mysql_loader_password.txt` 내용 |
| `MYSQL_SERVER_PUBKEY` | `~/.bstats/mysql_server_rsa_pub.pem` 전체(BEGIN·END 줄 포함) |

변수 `MYSQL_MIRROR` 는 아직 만들지 않습니다(Task 9).

- [ ] **Step 7: 기록**

로드맵 `접속 설계` 표의 수집 줄을 `Cloud SQL Auth Proxy + Workload Identity Federation(키 없음) | bstats_loader (SELECT·INSERT·UPDATE·DELETE)` 로 고치고, `보안 정리` 에 "5단계 뒤 WIF 공급자 조건 재확인" 을 더합니다. 비밀번호·번호는 적지 않습니다.

```bash
git add docs/superpowers/plans/2026-10-01-mysql-migration-roadmap.md
git commit -m "docs(mysql): 수집 접속을 키 없는 연동(WIF)과 bstats_loader 로 기록

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: MySQL 쓰기 도구 `mysql_sink.py`

**Files:**
- Create: `data_collection/mysql_sink.py`
- Create: `tests/conftest.py`
- Test: `tests/test_mysql_sink.py` (새 파일)

**Interfaces:**
- Produces(이후 모든 Task 가 씀):
  - `mirror(job: str, fn: Callable[[Sink], T], required: bool = False, connect=None) -> T | None`
  - `class Sink`: `columns(table) -> list[str]`, `value(table, column, v)`, `execute(sql, params=None) -> int`, `query(sql, params=None) -> list[dict]`, `insert(table, columns, rows, batch=500) -> int`, `upsert(table, columns, keys, rows, touch=None, keep=(), batch=500) -> int`, `insert_missing(table, columns, keys, rows, batch=500) -> int`, `refresh_count(table) -> int`
  - 환경 변수 `BSTATS_MYSQL_MIRROR`(off·shadow·strict), `BSTATS_MYSQL_FAIL_LOG`
  - 테스트 fixture `fake_sink`(`FakeSink`): 부른 것을 `calls` 에 `("upsert", 표, 열, 열쇠, 행, touch, keep)`·`("insert", 표, 열, 행)`·`("insert_missing", 표, 열, 열쇠, 행)`·`("execute", sql, params)`·`("query", sql, params)`·`("refresh_count", 표)` 로 남깁니다. `answers` 에 `{sql 조각: 행 목록}` 을 넣으면 `query` 가 그 행을 돌려줍니다.

- [ ] **Step 1: 테스트 fixture**

`tests/conftest.py`:

```python
import pytest


class FakeSink:
    """data_collection.mysql_sink.Sink 를 흉내 냅니다. 부른 순서대로 calls 에 남깁니다."""

    def __init__(self):
        self.calls = []
        self.answers = {}

    def columns(self, table):
        from data_collection import mysql_sink
        return mysql_sink.table_columns(table)

    def value(self, table, column, v):
        from data_collection import mysql_sink
        return mysql_sink.Sink(None).value(table, column, v)

    def execute(self, sql, params=None):
        self.calls.append(("execute", sql, None if params is None else list(params)))
        return 1

    def query(self, sql, params=None):
        self.calls.append(("query", sql, params))
        for piece, rows in self.answers.items():
            if piece in sql:
                return rows
        return []

    def insert(self, table, columns, rows, batch=None):
        rows = list(rows)
        self.calls.append(("insert", table, list(columns), rows))
        return len(rows)

    def upsert(self, table, columns, keys, rows, touch=None, keep=(), batch=None):
        rows = list(rows)
        self.calls.append(("upsert", table, list(columns), list(keys), rows, touch, tuple(keep)))
        return len(rows)

    def insert_missing(self, table, columns, keys, rows, batch=None):
        rows = list(rows)
        self.calls.append(("insert_missing", table, list(columns), list(keys), rows))
        return len(rows)

    def refresh_count(self, table):
        self.calls.append(("refresh_count", table))
        return 0


@pytest.fixture
def fake_sink():
    return FakeSink()
```

- [ ] **Step 2: 실패하는 테스트 쓰기**

`tests/test_mysql_sink.py`:

```python
import json

import pytest

from data_collection import mysql_sink as ms


class Cur:
    def __init__(self, con):
        self.con = con
        self.description = con.desc
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        if self.con.fail_on and self.con.fail_on in sql:
            raise RuntimeError("boom")
        self.con.log.append((sql, params))

    def fetchall(self):
        return self.con.rows


class Con:
    def __init__(self, rows=None, desc=None, fail_on=None):
        self.log, self.rows, self.desc, self.fail_on = [], rows or [], desc, fail_on
        self.commits = self.rollbacks = self.closed = 0

    def cursor(self):
        return Cur(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed += 1


GAME = {"game_id": "20261003LGOB02026", "game_date": "20261003", "season": "2026",
        "game_type": "정규시즌", "home_team_id": "OB", "away_team_id": "LG",
        "home_score": "3", "away_score": "-", "stadium": "잠실"}


def test_upsert_uses_row_alias_and_parameters():
    con = Con()
    cols = list(GAME)
    assert ms.Sink(con).upsert("games", cols, ["game_id"], [GAME]) == 1
    sql, params = con.log[0]
    assert sql.startswith("INSERT INTO `games` (`game_id`, `game_date`")
    assert " AS new ON DUPLICATE KEY UPDATE `game_date`=new.`game_date`" in sql
    assert "`game_id`=new" not in sql
    # '-' 는 D1 처럼 NULL, 정수 열은 정수입니다.
    assert params[1] == 20261003 and params[2] == 2026 and params[7] is None


def test_upsert_touch_and_keep():
    con = Con()
    ms.Sink(con).upsert("futures_games", ["game_id", "season", "status", "updated_at"],
                        ["game_id"], [{"game_id": "x", "season": 2026, "status": "final",
                                       "updated_at": "t"}],
                        touch="updated_at", keep=["season"])
    sql = con.log[0][0]
    assert "`status`=new.`status`" in sql
    assert "`updated_at`=UTC_TIMESTAMP()" in sql
    assert "`season`=new" not in sql


def test_upsert_without_updatable_columns_is_an_error():
    with pytest.raises(ValueError):
        ms.Sink(Con()).upsert("teams", ["team_id"], ["team_id"], [{"team_id": "LG"}])


def test_insert_splits_batches():
    con = Con()
    rows = [{"job": "j%d" % i, "last_run_at": "2026-10-02 10:00", "status": "ok"}
            for i in range(5)]
    ms.Sink(con).insert("meta_job_runs", ["job", "last_run_at", "status"], rows, batch=2)
    assert len(con.log) == 3
    assert con.log[0][0].count("(%s, %s, %s)") == 2


def test_insert_missing_is_a_no_op_update():
    con = Con()
    ms.Sink(con).insert_missing("players", ["player_id", "player_name"], ["player_id"],
                                [{"player_id": "51234", "player_name": "가"}])
    sql, params = con.log[0]
    assert sql.endswith(" ON DUPLICATE KEY UPDATE `player_id`=`player_id`")
    assert params == [51234, "가"]


def test_bad_value_names_table_and_column():
    with pytest.raises(ValueError, match="games.home_score"):
        ms.Sink(Con()).insert("games", ["game_id", "home_score"],
                              [{"game_id": "g", "home_score": "abc"}])


def test_unknown_column_is_an_error():
    with pytest.raises(KeyError):
        ms.Sink(Con()).insert("games", ["nope"], [{"nope": 1}])


def test_refresh_count_writes_meta():
    con = Con(rows=[(3983367,)], desc=[("n",)])
    assert ms.Sink(con).refresh_count("play_by_play") == 3983367
    assert con.log[0][0] == "SELECT COUNT(*) AS n FROM `play_by_play`"
    assert con.log[1][0].startswith("INSERT INTO `meta_table_counts`")
    assert con.log[1][1][:2] == ["play_by_play", 3983367]


def test_mirror_off_does_nothing(monkeypatch):
    monkeypatch.delenv(ms.MODE_ENV, raising=False)
    called = []
    assert ms.mirror("j", lambda s: called.append(1), connect=Con) is None
    assert not called


def test_mirror_shadow_commits_and_closes(monkeypatch):
    monkeypatch.setenv(ms.MODE_ENV, "shadow")
    con = Con()
    assert ms.mirror("j", lambda s: 7, connect=lambda: con) == 7
    assert con.commits == 1 and con.closed == 1
    assert "innodb_lock_wait_timeout" in con.log[0][0]


def test_mirror_shadow_records_failure_and_continues(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv(ms.MODE_ENV, "shadow")
    log = tmp_path / "fail.jsonl"
    monkeypatch.setenv(ms.FAIL_LOG_ENV, str(log))
    con = Con(fail_on="INSERT")
    assert ms.mirror("games", lambda s: s.execute("INSERT INTO x VALUES (1)"),
                     connect=lambda: con) is None
    assert con.rollbacks == 1 and con.commits == 0 and con.closed == 1
    rec = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert rec["job"] == "games" and "boom" in rec["error"]
    assert "::warning" in capsys.readouterr().out


def test_mirror_strict_raises(monkeypatch, tmp_path):
    monkeypatch.setenv(ms.MODE_ENV, "strict")
    monkeypatch.setenv(ms.FAIL_LOG_ENV, str(tmp_path / "f.jsonl"))
    with pytest.raises(RuntimeError):
        ms.mirror("j", lambda s: s.execute("INSERT 1"), connect=lambda: Con(fail_on="INSERT"))


def test_mirror_required_runs_even_when_off(monkeypatch):
    monkeypatch.delenv(ms.MODE_ENV, raising=False)
    assert ms.mirror("j", lambda s: 1, required=True, connect=Con) == 1


def test_bad_mode_is_an_error(monkeypatch):
    monkeypatch.setenv(ms.MODE_ENV, "maybe")
    with pytest.raises(ValueError):
        ms.mode()
```

- [ ] **Step 3: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_sink.py -p no:cacheprovider -q`
Expected: `ModuleNotFoundError: No module named 'data_collection.mysql_sink'`

- [ ] **Step 4: `data_collection/mysql_sink.py` 쓰기**

```python
# -*- coding: utf-8 -*-
"""수집 결과를 Cloud SQL(MySQL)에도 씁니다. 2단계 이중 적재입니다.

D1 에 쓰는 코드는 그대로 두고, 각 스크립트가 D1 적재를 마친 뒤
`mirror()` 로 같은 내용을 MySQL 에 씁니다. 사이트는 3단계까지 D1 을
읽으므로 MySQL 이 실패해도 D1 적재를 막지 않습니다. 대신 실패를 파일에
남기고, 워크플로 마지막 판정이 그 파일을 보고 빨간색으로 끝냅니다.

## 켜고 끄기

    BSTATS_MYSQL_MIRROR    off(기본)  MySQL 에 손대지 않습니다
                           shadow     쓰고, 실패하면 기록만 하고 넘어갑니다
                           strict     쓰고, 실패하면 예외를 그대로 올립니다
    BSTATS_MYSQL_SETTINGS  접속 파일(migration/mysql/conn.py)
    BSTATS_MYSQL_FAIL_LOG  실패 기록 파일(기본 logs/mysql_mirror_failures.jsonl)

## D1 과 같은 값 쓰기

D1 쪽은 `d1_load.sql_literal` 이 ''·'-' 를 NULL 로 바꿉니다. 여기서도
같게 한 뒤, 열 종류(schema_types.json)에 맞춰 1단계 적재와 같은 규칙
(`typemap.normalize`)으로 바꿉니다. 값은 SQL 글자에 붙이지 않고
파라미터로 넘깁니다. MySQL 엄격 모드는 '12345.0' 같은 글자를 정수 열에
넣으면 실패하기 때문입니다.
"""
import datetime
import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from migration.mysql import typemap as tm  # noqa: E402

TYPES_PATH = ROOT / "migration" / "mysql" / "schema_types.json"
MODE_ENV = "BSTATS_MYSQL_MIRROR"
FAIL_LOG_ENV = "BSTATS_MYSQL_FAIL_LOG"
DEFAULT_FAIL_LOG = ROOT / "logs" / "mysql_mirror_failures.jsonl"
MODES = ("off", "shadow", "strict")
BATCH = 500
# 행 잠금 대기 한도(초)입니다. 수집 단계마다 시간 제한이 있어 오래 기다리지 않습니다.
LOCK_WAIT_SEC = 30

_types = None


def mode():
    m = (os.environ.get(MODE_ENV) or "off").strip().lower()
    if m not in MODES:
        raise ValueError("%s 는 off·shadow·strict 중 하나여야 합니다: %r" % (MODE_ENV, m))
    return m


def q(name):
    return "`%s`" % str(name).replace("`", "``")


def blank(v):
    """d1_load.sql_literal 과 같이 ''·'-' 를 값 없음으로 봅니다."""
    if v is None:
        return None
    s = str(v)
    if s == "" or s == "-":
        return None
    return v


def table_spec(table):
    global _types
    if _types is None:
        _types = json.loads(TYPES_PATH.read_text(encoding="utf-8"))
    if table not in _types:
        raise KeyError("schema_types.json 에 없는 표입니다: %s" % table)
    return _types[table]


def table_columns(table):
    return [c for c, _ in table_spec(table)["columns"]]


class Sink:
    """한 트랜잭션 안에서 MySQL 에 씁니다. mirror() 가 만들고 커밋합니다."""

    def __init__(self, con):
        self.con = con

    def columns(self, table):
        return table_columns(table)

    def value(self, table, column, v):
        kinds = dict(table_spec(table)["columns"])
        if column not in kinds:
            raise KeyError("%s 에 없는 열입니다: %s" % (table, column))
        try:
            return tm.normalize(blank(v), kinds[column])
        except ValueError as e:
            raise ValueError("%s.%s: %s" % (table, column, e)) from None

    def execute(self, sql, params=None):
        with self.con.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount

    def query(self, sql, params=None):
        with self.con.cursor() as cur:
            cur.execute(sql, params)
            names = [d[0] for d in cur.description]
            return [dict(zip(names, r)) for r in cur.fetchall()]

    def _write(self, table, columns, rows, tail, batch):
        rows = list(rows)
        head = "INSERT INTO %s (%s) VALUES " % (q(table), ", ".join(q(c) for c in columns))
        one = "(%s)" % ", ".join(["%s"] * len(columns))
        for i in range(0, len(rows), batch):
            chunk = rows[i:i + batch]
            params = []
            for r in chunk:
                params.extend(self.value(table, c, r.get(c)) for c in columns)
            self.execute(head + ", ".join([one] * len(chunk)) + tail, params)
        return len(rows)

    def insert(self, table, columns, rows, batch=BATCH):
        return self._write(table, columns, rows, "", batch)

    def upsert(self, table, columns, keys, rows, touch=None, keep=(), batch=BATCH):
        """d1_load.build_upserts 와 같은 뜻입니다.

        열쇠·keep·touch 를 뺀 열을 새 값으로 덮고, touch 열은 지금 UTC 시각으로
        둡니다(D1 의 datetime('now') 와 같음).
        """
        keyset = set(keys) | set(keep) | ({touch} if touch else set())
        updatable = [c for c in columns if c not in keyset]
        if not updatable:
            raise ValueError("갱신할 컬럼이 없습니다: %s" % table)
        sets = ["%s=new.%s" % (q(c), q(c)) for c in updatable]
        if touch:
            sets.append("%s=UTC_TIMESTAMP()" % q(touch))
        tail = " AS new ON DUPLICATE KEY UPDATE " + ", ".join(sets)
        return self._write(table, columns, rows, tail, batch)

    def insert_missing(self, table, columns, keys, rows, batch=BATCH):
        """없는 행만 넣습니다.

        D1 의 INSERT OR IGNORE 자리입니다. MySQL 의 INSERT IGNORE 는 값 잘림·
        외래키 오류까지 경고로 삼키므로 쓰지 않습니다.
        """
        k = q(keys[0])
        return self._write(table, columns, rows,
                           " ON DUPLICATE KEY UPDATE %s=%s" % (k, k), batch)

    def refresh_count(self, table):
        """meta_table_counts 를 MySQL 표 전체 행 수로 맞춥니다.

        D1 은 play_by_play 를 샤드마다 따로 셌지만 MySQL 은 한 표라 전체입니다.
        """
        n = self.query("SELECT COUNT(*) AS n FROM %s" % q(table))[0]["n"]
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.upsert("meta_table_counts", ["name", "n", "updated_at"], ["name"],
                    [{"name": table, "n": n, "updated_at": now}])
        return n


def _connect():
    from migration.mysql import conn as myconn
    return myconn.connect()


def one_line(e):
    return ("%s: %s" % (type(e).__name__, e)).replace("\n", " ")[:300]


def record_failure(job, e):
    path = Path(os.environ.get(FAIL_LOG_ENV) or DEFAULT_FAIL_LOG)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "job": job, "error": one_line(e),
            "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        }, ensure_ascii=False) + "\n")
    traceback.print_exc()


def mirror(job, fn, required=False, connect=None):
    """fn(Sink) 를 한 트랜잭션으로 MySQL 에 씁니다. fn 의 값을 돌려줍니다.

    꺼져 있으면(off) 아무것도 하지 않고 None 입니다. required=True 는 MySQL
    에만 쓰는 손 작업(따라잡기)용입니다. 꺼져 있어도 쓰고, 실패하면 예외를
    올립니다.
    """
    m = mode()
    if m == "off" and not required:
        return None
    con = None
    try:
        con = (connect or _connect)()
        with con.cursor() as cur:
            cur.execute("SET SESSION innodb_lock_wait_timeout = %d" % LOCK_WAIT_SEC)
        result = fn(Sink(con))
        con.commit()
        print("MySQL 반영: %s" % job, flush=True)
        return result
    except Exception as e:  # noqa: BLE001
        if con is not None:
            try:
                con.rollback()
            except Exception:  # noqa: BLE001
                pass
        record_failure(job, e)
        if m == "strict" or required:
            raise
        print("::warning title=MySQL 이중 적재 실패::%s: %s" % (job, one_line(e)), flush=True)
        return None
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:  # noqa: BLE001
                pass
```

- [ ] **Step 5: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_sink.py -p no:cacheprovider -q`
Expected: 모두 PASS.

- [ ] **Step 6: 실제 MySQL 에 왕복(되돌리기)**

프록시가 떠 있어야 합니다(Task 1 Step 4).

```bash
BSTATS_MYSQL_SETTINGS=~/.bstats/mysql_loader_proxy.json PYTHONUTF8=1 py - <<'EOF'
from data_collection import mysql_sink as ms
from migration.mysql import conn
c = conn.connect()
s = ms.Sink(c)
s.upsert("meta_job_runs", ["job", "last_run_at", "status", "note", "duration_sec"], ["job"],
         [{"job": "_sink_probe", "last_run_at": "2026-10-02 12:00", "status": "ok",
           "note": None, "duration_sec": 1}])
print(s.query("SELECT job, status FROM meta_job_runs WHERE job = %s", ["_sink_probe"]))
c.rollback()
print(s.query("SELECT COUNT(*) AS n FROM meta_job_runs WHERE job = %s", ["_sink_probe"]))
c.close()
EOF
```

Expected: `[{'job': '_sink_probe', 'status': 'ok'}]` 다음 `[{'n': 0}]`(되돌려서 남지 않음).

- [ ] **Step 7: 커밋**

```bash
git add data_collection/mysql_sink.py tests/conftest.py tests/test_mysql_sink.py
git commit -m "feat(mysql-sink): 수집 결과를 MySQL 에도 쓰는 도구와 mirror 스위치

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: 하루치 PBP 이중 적재와 `--mysql-only`

2A Task 2(`wrong_dates`)가 main 에 들어간 뒤에 합니다.

MySQL 은 400만 행 한 표입니다. D1 과 같이 그날 행을 지우고 다시 넣습니다(`idx_pbp_game_date` 는 2C Task 5 에서 만듭니다). `--mysql-only` 는 D1 에 이미 들어간 그날 행을 MySQL 로 옮기는 따라잡기용입니다. 다시 크롤링하지 않고 D1 에서 읽어 두 DB 가 정확히 같게 합니다.

**Files:**
- Modify: `data_collection/daily_pbp_to_d1.py`
- Test: `tests/test_daily_pbp_mysql.py` (새 파일)

**Interfaces:**
- Consumes: `mysql_sink.mirror`, `Sink.columns/execute/insert/refresh_count`, 2A 의 `wrong_dates(rows, day)`
- Produces: `mysql_write_pbp(sink, day, rows) -> int`, `d1_day_rows(day, pbp_db) -> list[dict]`, CLI `--mysql-only`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_daily_pbp_mysql.py`:

```python
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import daily_pbp_to_d1 as m  # noqa: E402


def test_mysql_write_deletes_day_then_inserts_without_pbp_id(fake_sink):
    rows = [{"pbp_id": "9", "gameID": "20261003LGOB02026", "game_date": "20261003"}]
    assert m.mysql_write_pbp(fake_sink, "20261003", rows) == 1
    assert [c[0] for c in fake_sink.calls] == ["execute", "insert", "refresh_count"]
    _, sql, params = fake_sink.calls[0]
    assert sql == "DELETE FROM `play_by_play` WHERE `game_date` = %s"
    assert params == [20261003]
    _, table, cols, inserted = fake_sink.calls[1]
    assert table == "play_by_play" and "pbp_id" not in cols and "gameID" in cols
    assert inserted == rows


def test_mysql_only_copies_day_from_d1(monkeypatch):
    calls = []

    def fake_query(sql, db_name="kbo-stats"):
        calls.append((sql, db_name))
        if "FROM games" in sql:
            return [{"g": "20261003LGOB02026"}]
        return [{"pbp_id": 7, "gameID": "20261003LGOB02026", "game_date": 20261003}]

    seen = {}

    def fake_mirror(job, fn, required=False):
        seen.update(job=job, required=required)
        return 1

    monkeypatch.setattr(m, "query", fake_query)
    monkeypatch.setattr(m, "mirror", fake_mirror)
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: pytest.fail("크롤러를 부르면 안 됩니다"))
    monkeypatch.setattr(m, "run_d1_file", lambda *a, **k: pytest.fail("D1 에 쓰면 안 됩니다"))
    monkeypatch.setattr(sys, "argv", ["x", "--date", "20261003", "--mysql-only"])
    assert m.main() == 0
    assert seen == {"job": "pbp", "required": True}
    assert calls[0][1] == "kbo-stats" and "game_date = 20261003" in calls[0][0]
    assert calls[1][1] == "kbo-pbp-2024-2026" and "ORDER BY pbp_id" in calls[1][0]


def test_mysql_only_stops_on_wrong_dates(monkeypatch):
    def fake_query(sql, db_name="kbo-stats"):
        if "FROM games" in sql:
            return [{"g": "33330929LTOB0"}]
        return [{"gameID": "33330929LTOB0", "game_date": "TOB00929"}]

    monkeypatch.setattr(m, "query", fake_query)
    monkeypatch.setattr(m, "mirror", lambda *a, **k: pytest.fail("넣으면 안 됩니다"))
    monkeypatch.setattr(sys, "argv", ["x", "--date", "20091029", "--mysql-only"])
    assert m.main() == 1
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_daily_pbp_mysql.py -p no:cacheprovider -q`
Expected: `AttributeError: … 'mysql_write_pbp'` 등으로 FAIL.

- [ ] **Step 3: 함수 추가**

import 를 바꿉니다.

```python
from d1_load import (  # noqa: E402
    build_inserts, d1_columns, query, refresh_count, run_d1_file,
)
from migration import shard_plan  # noqa: E402
from mysql_sink import mirror  # noqa: E402
```

`wrong_dates` 아래에 둡니다.

```python
def mysql_write_pbp(sink, day, rows):
    """MySQL 에 하루치를 씁니다. 표 하나라 샤드를 고르지 않습니다.

    D1 과 같이 그날 행을 지우고 다시 넣어, 다시 돌려도 결과가 같습니다.
    idx_pbp_game_date 가 있어야 이 DELETE 가 400만 행을 훑지 않습니다.
    pbp_id 는 넣지 않습니다. AUTO_INCREMENT 가 이어 붙이고, 받은 순서대로
    넣으므로 경기 안 순서(RE24 의 ORDER BY pbp_id)가 지켜집니다.
    """
    cols = [c for c in sink.columns("play_by_play") if c != "pbp_id"]
    sink.execute("DELETE FROM `play_by_play` WHERE `game_date` = %s", [int(day)])
    n = sink.insert("play_by_play", cols, rows)
    sink.refresh_count("play_by_play")
    return n


def d1_day_rows(day, pbp_db):
    """D1 에 이미 들어간 그날 행입니다. 따라잡기(--mysql-only)용입니다.

    D1 샤드의 game_date 에는 인덱스가 없어 날짜로 고르면 샤드 전체(약 70만
    행)를 읽습니다. 날짜 인덱스가 있는 games 에서 그날 경기를 찾고, gameID
    인덱스로 고릅니다. 읽는 양은 그날 행 수와 같습니다.
    """
    games = [r["g"] for r in query(
        "SELECT game_id AS g FROM games WHERE game_date = %d;" % int(day))]
    if not games:
        return []
    ids = ",".join("'%s'" % str(g).replace("'", "''") for g in games)
    return query("SELECT * FROM play_by_play WHERE gameID IN (%s) ORDER BY pbp_id;" % ids,
                 db_name=pbp_db)
```

- [ ] **Step 4: `main` 에 붙이기**

옵션을 더합니다.

```python
    ap.add_argument("--mysql-only", action="store_true",
                    help="크롤링·D1 쓰기 없이, D1 에 이미 있는 그날 행을 MySQL 에 넣습니다(따라잡기)")
```

`print("대상 D1: %s" % pbp_db)` 다음, `save_dir = ROOT / args.save_dir` 앞에 넣습니다.

```python
    if args.mysql_only:
        rows = d1_day_rows(day, pbp_db)
        print("D1 에서 읽은 행 %s개" % format(len(rows), ","))
        if not rows:
            print("%s 에 D1 행이 없습니다. 넣을 것이 없습니다." % day)
            return 0
        bad = wrong_dates(rows, day)
        if bad:
            print("game_date 가 %s 이 아닌 행이 있습니다: %s" % (day, ", ".join(bad[:5])))
            return 1
        if args.dry_run:
            print("[dry-run] MySQL 에 넣지 않았습니다.")
            return 0
        n = mirror("pbp", lambda s: mysql_write_pbp(s, day, rows), required=True)
        print("MySQL 적재 완료 (%s행)" % format(n, ","))
        return 0
```

맨 끝 `print("행 수 메타 갱신 완료")` 와 `return 0` 사이에 넣습니다.

```python
    mirror("pbp", lambda s: mysql_write_pbp(s, day, rows))
```

- [ ] **Step 5: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_daily_pbp_mysql.py tests/test_daily_pbp_guard.py tests/test_shard_routing.py -p no:cacheprovider -q`
Expected: 모두 PASS.

- [ ] **Step 6: 실제로 한 번(최근 날, D1 읽기 약 1,500행)**

2C Task 5(인덱스)가 끝난 뒤에만 합니다. MySQL 에는 2026-10-01 까지 들어 있으므로 그날을 다시 넣어 같은 결과가 나오는지 봅니다.

```bash
BSTATS_MYSQL_SETTINGS=~/.bstats/mysql_proxy.json PYTHONUTF8=1 py - <<'EOF'
from migration.mysql import conn
c = conn.connect()
with c.cursor() as cur:
    cur.execute("SELECT COUNT(*), MIN(pbp_id) FROM play_by_play WHERE game_date = 20261001")
    print("전", cur.fetchone())
c.close()
EOF
BSTATS_MYSQL_SETTINGS=~/.bstats/mysql_proxy.json PYTHONUTF8=1 py data_collection/daily_pbp_to_d1.py --date 20261001 --mysql-only
```

그다음 첫 블록을 다시 돌립니다.
Expected: 행 수가 전과 같고(1,339), MIN(pbp_id) 는 새 번호(전보다 큼)입니다. 번호만 바뀌고 내용은 같습니다.

- [ ] **Step 7: 커밋**

```bash
git add data_collection/daily_pbp_to_d1.py tests/test_daily_pbp_mysql.py
git commit -m "feat(daily-pbp): MySQL 이중 적재와 D1→MySQL 하루 따라잡기(--mysql-only)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: 덮어쓰기형 4개(경기·퓨처스 일정·공식 기록·작업 기록)

**Files:**
- Modify: `data_collection/daily_games_to_d1.py`, `data_collection/futures_to_d1.py`, `data_collection/csv_to_d1.py`, `data_collection/record_job_run.py`
- Test: `tests/test_mysql_mirror_upserts.py` (새 파일)

**Interfaces:**
- Consumes: `mirror`, `Sink.upsert`, `Sink.refresh_count`
- Produces: `daily_games_to_d1.mysql_write_games(sink, dicts)`, `futures_to_d1.mysql_write_futures(sink, rows)`, `csv_to_d1.mysql_write_upsert(sink, table, columns, keys, rows, touch, keep)`, `record_job_run.JOB_COLS`, `record_job_run.job_row(job, now, status, note, duration) -> dict`, `record_job_run.mysql_write_job(sink, row)`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_mysql_mirror_upserts.py`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import csv_to_d1  # noqa: E402
import daily_games_to_d1  # noqa: E402
import futures_to_d1  # noqa: E402
import record_job_run  # noqa: E402


def test_games(fake_sink):
    assert daily_games_to_d1.mysql_write_games(fake_sink, [{"game_id": "g"}]) == 1
    assert fake_sink.calls[0][:4] == ("upsert", "games", daily_games_to_d1.GAME_COLS, ["game_id"])
    assert fake_sink.calls[1] == ("refresh_count", "games")


def test_futures_keeps_team_columns(fake_sink):
    futures_to_d1.mysql_write_futures(fake_sink, [{"game_id": "f"}])
    call = fake_sink.calls[0]
    assert call[1] == "futures_games" and call[5] is None
    assert call[6] == tuple(futures_to_d1.KEEP)
    assert fake_sink.calls[1] == ("refresh_count", "futures_games")


def test_official_stats_touch_and_keep(fake_sink):
    csv_to_d1.mysql_write_upsert(
        fake_sink, "kbo_official_batter_stats",
        ["player_id", "season", "created_at", "updated_at"], ["player_id", "season"],
        [{}], "updated_at", ["created_at"])
    call = fake_sink.calls[0]
    assert call[5] == "updated_at" and call[6] == ("created_at",)
    assert fake_sink.calls[1] == ("refresh_count", "kbo_official_batter_stats")


def test_job_run(fake_sink):
    row = record_job_run.job_row("pbp", "2026-10-03 03:40", "ok", None, None)
    assert row == {"job": "pbp", "last_run_at": "2026-10-03 03:40", "status": "ok",
                   "note": None, "duration_sec": None}
    record_job_run.mysql_write_job(fake_sink, row)
    assert fake_sink.calls[0][1:5] == ("meta_job_runs", record_job_run.JOB_COLS, ["job"], [row])


def test_scripts_mirror_inside_main():
    for name in ("daily_games_to_d1", "futures_to_d1", "csv_to_d1", "record_job_run"):
        src = (ROOT / "data_collection" / (name + ".py")).read_text(encoding="utf-8")
        assert "from mysql_sink import mirror" in src, name
        assert "mirror(" in src.split("def main", 1)[1], name
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_mirror_upserts.py -p no:cacheprovider -q`
Expected: 모두 FAIL(함수 없음).

- [ ] **Step 3: `daily_games_to_d1.py`**

import 에 `from mysql_sink import mirror  # noqa: E402` 를 더하고(25행 다음), `main` 위에 둡니다.

```python
def mysql_write_games(sink, dicts):
    """D1 과 같은 UPSERT 입니다. 관중·날씨처럼 여기서 못 만드는 열은 덮지 않습니다."""
    n = sink.upsert("games", GAME_COLS, ["game_id"], dicts)
    sink.refresh_count("games")
    return n
```

`main` 끝 `print("D1 적재 완료 (%d경기)" % len(dicts))` 다음 줄에 넣습니다.

```python
    mirror("games", lambda s: mysql_write_games(s, dicts))
```

- [ ] **Step 4: `futures_to_d1.py`**

import 에 `from mysql_sink import mirror  # noqa: E402` 를 더하고, `main` 위에 둡니다.

```python
def mysql_write_futures(sink, rows):
    """D1 과 같이 팀·시즌 열(KEEP)은 덮지 않습니다."""
    n = sink.upsert("futures_games", COLS, ["game_id"], rows, touch=None, keep=KEEP)
    sink.refresh_count("futures_games")
    return n
```

`print("D1 적재 완료")` 다음 줄에 넣습니다.

```python
    mirror("futures", lambda s: mysql_write_futures(s, rows))
```

- [ ] **Step 5: `csv_to_d1.py`**

`from d1_load import (…)` 다음에 `from mysql_sink import mirror  # noqa: E402` 를 더하고, `main` 위에 둡니다.

```python
def mysql_write_upsert(sink, table, columns, keys, rows, touch, keep):
    """D1 과 같은 열·열쇠·touch·keep 으로 덮어씁니다."""
    n = sink.upsert(table, columns, keys, rows, touch=touch, keep=keep)
    sink.refresh_count(table)
    return n
```

`print("D1 적재 완료 (%s행)" …)` 다음 줄에 넣습니다.

```python
    touch = "updated_at" if "updated_at" in columns else None
    mirror("csv:" + args.table,
           lambda s: mysql_write_upsert(s, args.table, columns, keys, good, touch, keep))
```

- [ ] **Step 6: `record_job_run.py`**

import 를 `from d1_load import run_d1, sql_literal  # noqa: E402` 다음에 `from mysql_sink import mirror  # noqa: E402` 로 더하고, `KNOWN_JOBS` 아래에 둡니다.

```python
JOB_COLS = ["job", "last_run_at", "status", "note", "duration_sec"]


def job_row(job, now, status, note, duration):
    return {"job": job, "last_run_at": now, "status": status, "note": note,
            "duration_sec": duration}


def mysql_write_job(sink, row):
    return sink.upsert("meta_job_runs", JOB_COLS, ["job"], [row])
```

`print("기록: %s  %s  %s" …)` 다음 줄에 넣습니다.

```python
    row = job_row(args.job, now, args.status, args.note, args.duration)
    mirror("job_runs", lambda s: mysql_write_job(s, row))
```

- [ ] **Step 7: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_mirror_upserts.py tests/test_mysql_sink.py -p no:cacheprovider -q`
Expected: 모두 PASS.

- [ ] **Step 8: 꺼진 상태에서 D1 동작이 그대로인지 보기**

Run: `PYTHONUTF8=1 py data_collection/daily_games_to_d1.py --date 20261001 --dry-run`
Expected: 지금과 같은 출력(로컬에 그날 CSV 가 없으면 `경기가 없습니다`), `MySQL 반영` 줄 없음. 스위치가 꺼져 있고, dry-run 은 mirror 앞에서 끝납니다.

- [ ] **Step 9: 커밋**

```bash
git add data_collection/daily_games_to_d1.py data_collection/futures_to_d1.py data_collection/csv_to_d1.py data_collection/record_job_run.py tests/test_mysql_mirror_upserts.py
git commit -m "feat(mysql-mirror): 경기·퓨처스 일정·공식 기록·작업 기록을 MySQL 에도 씀

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: 명단·선수 4개(등록 명단·소속 갱신·새 선수·퓨처스 기록)

2A Task 4(`split_known`)가 main 에 들어간 뒤에 합니다.

**Files:**
- Modify: `data_collection/roster_to_d1.py`, `data_collection/sync_players_from_roster.py`, `data_collection/add_new_players.py`, `data_collection/futures_records.py`
- Test: `tests/test_mysql_mirror_roster.py` (새 파일)

**Interfaces:**
- Consumes: `mirror`, `Sink.upsert/execute/query/value/insert_missing`, 2A 의 `split_known(rows, known)`
- Produces: `roster_to_d1.mysql_write_roster(sink, rows, moves)`, `sync_players_from_roster.DIFF_SQL`, `pick_diffs(rows)`, `mysql_write_sync(sink)`, `add_new_players.NEW_PLAYER_COLS`, `id_fill_targets(found)`, `d1_update_sql(table, pid, conds)`, `mysql_write_new_players(sink, new_rows, targets)`, `futures_records.KEY`, `mysql_write_futures_stats(sink, rows, columns)`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_mysql_mirror_roster.py`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import add_new_players  # noqa: E402
import futures_records  # noqa: E402
import roster_to_d1  # noqa: E402
import sync_players_from_roster as sync  # noqa: E402


def test_roster_upserts_then_prunes(fake_sink):
    rows = [{"team": "LG", "name": "가", "back_number": "07"},
            {"team": "KT", "name": "나", "back_number": "1"}]
    moves = [{"move_date": "2026-10-02", "kind": "등록", "team": "LG", "name": "가"}]
    roster_to_d1.mysql_write_roster(fake_sink, rows, moves)
    kinds = [(c[0], c[1]) for c in fake_sink.calls]
    assert kinds == [("upsert", "kbo_roster"), ("upsert", "kbo_roster_moves"),
                     ("execute", fake_sink.calls[2][1])]
    _, sql, params = fake_sink.calls[2]
    assert sql == ("DELETE FROM `kbo_roster` WHERE (`team`, `name`, `back_number`) "
                   "NOT IN ((%s, %s, %s), (%s, %s, %s))")
    assert params == ["LG", "가", "07", "KT", "나", "1"]


def test_sync_uses_mysql_rows_and_skips_unknown_teams(fake_sink):
    fake_sink.answers = {
        "FROM teams": [{"team_id": "LG"}],
        "FROM kbo_roster r": [
            {"pid": 1, "nm": "가", "rt": "LG", "rb": "07", "pt": "OB", "pb": 7},
            {"pid": 2, "nm": "나", "rt": "상무", "rb": "1", "pt": "LG", "pb": 1},
            {"pid": 3, "nm": "다", "rt": "LG", "rb": "5", "pt": "LG", "pb": 5},
        ],
    }
    assert sync.mysql_write_sync(fake_sink) == 1
    updates = [c for c in fake_sink.calls if c[0] == "execute"]
    assert len(updates) == 1
    assert updates[0][1].startswith("UPDATE `players` SET `team_id`=%s, `back_number`=%s")
    assert updates[0][2] == ["LG", 7, 1]


def _found():
    return [
        ("가", "LG", {"player_id": "51234", "position": "투수", "back_number": "7"}, {"pos"}),
        ("나", "KT", {"player_id": "51235", "position": "포수", "back_number": "12"}, {"pos", "bn"}),
        ("다", "OB", {"player_id": "51236", "position": "내야수", "back_number": "3"}, set()),
    ]


def test_d1_update_sql_matches_old_text():
    """함수로 옮겨도 D1 에 보내는 글자는 예전과 같아야 합니다."""
    got = [add_new_players.d1_update_sql(*t) for t in add_new_players.id_fill_targets(_found())]
    assert got == [
        "UPDATE kbo_roster SET player_id=51234 WHERE player_id IS NULL AND name='가' AND team='LG' AND role='투수';",
        "UPDATE kbo_roster_moves SET player_id=51234 WHERE player_id IS NULL AND name='가' AND team='LG' AND position='투수';",
        "UPDATE kbo_roster SET player_id=51235 WHERE player_id IS NULL AND name='나' AND team='KT' AND role='포수' AND back_number='12';",
        "UPDATE kbo_roster SET player_id=51236 WHERE player_id IS NULL AND name='다' AND team='OB';",
        "UPDATE kbo_roster_moves SET player_id=51236 WHERE player_id IS NULL AND name='다' AND team='OB';",
    ]


def test_mysql_new_players(fake_sink):
    targets = add_new_players.id_fill_targets(_found())
    rows = [{"player_id": 51234, "player_name": "가"}]
    assert add_new_players.mysql_write_new_players(fake_sink, rows, targets) == 1
    assert fake_sink.calls[0][:4] == ("insert_missing", "players",
                                      add_new_players.NEW_PLAYER_COLS, ["player_id"])
    _, sql, params = fake_sink.calls[1]
    assert sql == ("UPDATE `kbo_roster` SET `player_id`=%s WHERE `player_id` IS NULL "
                   "AND `name`=%s AND `team`=%s AND `role`=%s")
    assert params == [51234, "가", "LG", "투수"]
    assert len([c for c in fake_sink.calls if c[0] == "execute"]) == 5


def test_futures_records(fake_sink):
    futures_records.mysql_write_futures_stats(fake_sink, [{"player_id": "1"}],
                                              ["player_id", "season", "kind", "AVG"])
    assert fake_sink.calls[0][:4] == ("upsert", "futures_season_stats",
                                      ["player_id", "season", "kind", "AVG"],
                                      ["player_id", "season", "kind"])
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_mirror_roster.py -p no:cacheprovider -q`
Expected: 모두 FAIL(함수 없음).

- [ ] **Step 3: `roster_to_d1.py`**

import 에 `from mysql_sink import mirror  # noqa: E402` 를 더하고(44행 다음), `main` 위에 둡니다.

```python
def mysql_write_roster(sink, rows, moves):
    """D1 과 같은 순서입니다. 명단·등말소를 덮어쓰고, 명단에서 빠진 선수를 지웁니다."""
    n = sink.upsert("kbo_roster", ROSTER_COLS, ["team", "name", "back_number"], rows)
    if moves:
        sink.upsert("kbo_roster_moves", MOVE_COLS, ["move_date", "kind", "team", "name"], moves)
    if rows:
        keys = [(x["team"], x["name"], x["back_number"]) for x in rows]
        sink.execute(
            "DELETE FROM `kbo_roster` WHERE (`team`, `name`, `back_number`) NOT IN (%s)"
            % ", ".join(["(%s, %s, %s)"] * len(keys)),
            [v for k in keys for v in k])
    return n
```

`print("현재 명단 %s명" % left)` 다음 줄에 넣습니다.

```python
    mirror("roster", lambda s: mysql_write_roster(s, rows, moves))
```

- [ ] **Step 4: `sync_players_from_roster.py`**

import 에 `from mysql_sink import mirror  # noqa: E402` 를 더합니다. `diffs()` 를 아래로 바꿉니다(D1 에 보내는 SQL 글자는 같습니다).

```python
DIFF_SQL = ("SELECT r.player_id AS pid, r.name AS nm, r.team AS rt, "
            "r.back_number AS rb, p.team_id AS pt, p.back_number AS pb "
            "FROM kbo_roster r JOIN players p ON p.player_id = r.player_id")


def pick_diffs(rows):
    """소속이나 등번호가 다른 행만 고릅니다."""
    out = []
    for r in rows:
        same_team = (r["pt"] or "") == r["rt"]
        if not (same_team and same_number(r["pb"], r["rb"])):
            out.append(r)
    return out


def diffs():
    """(player_id, 이름, 새 소속, 새 등번호, 옛 소속, 옛 등번호) 목록."""
    return pick_diffs(query(DIFF_SQL + ";"))


def mysql_write_sync(sink):
    """MySQL 의 명단·선수 표로 같은 판단을 다시 해 반영합니다.

    D1 의 결과를 옮기지 않고 MySQL 안에서 다시 계산합니다. 두 DB 가 같으면
    결과도 같고, 다르면 매일 대조(reconcile)가 잡아냅니다.
    """
    known = {r["team_id"] for r in sink.query("SELECT team_id FROM teams")}
    rows, _ = split_known(pick_diffs(sink.query(DIFF_SQL)), known)
    for r in rows:
        sink.execute(
            "UPDATE `players` SET `team_id`=%s, `back_number`=%s, "
            "`updated_at`=UTC_TIMESTAMP() WHERE `player_id`=%s",
            [r["rt"], sink.value("players", "back_number", r["rb"]), int(r["pid"])])
    return len(rows)
```

`main` 의 이름을 `sync_d1(args)` 로 바꾸고(인자 파싱 세 줄은 새 `main` 으로 옮김), 새 `main` 을 둡니다. D1 쪽이 바꿀 것이 없다고 일찍 끝나도 MySQL 쪽은 스스로 다시 판단합니다.

```python
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    rc = sync_d1(args)
    if not args.dry_run:
        mirror("players_sync", mysql_write_sync)
    return rc
```

- [ ] **Step 5: `add_new_players.py`**

import 에 `from mysql_sink import mirror  # noqa: E402` 를 더하고, `player_row` 아래에 둡니다.

```python
NEW_PLAYER_COLS = ["player_id", "player_name", "team_id", "back_number", "position",
                   "birthday", "height", "weight", "career", "image_url"]


def id_fill_targets(found):
    """빈 player_id 를 채울 (표, ID, [(열, 값), …]) 목록입니다.

    이름+팀만으로 안 갈렸던 선수는 가를 때 쓴 조건(포지션·등번호)을 똑같이
    붙입니다. 그래야 같은 팀 동명이인의 다른 한 명에게 ID 가 잘못 붙지
    않습니다. 등말소 표에는 등번호가 없어, 등번호로만 갈린 선수는 둘 중
    누구인지 모르니 건드리지 않습니다.
    """
    out, done = [], set()
    for name, team, hit, used in found:
        pid = int(hit["player_id"])
        base = [("name", name), ("team", team)]
        roster = base + ([("role", hit["position"])] if "pos" in used else [])
        if "bn" in used:
            roster = roster + [("back_number", hit["back_number"])]
        targets = [("kbo_roster", pid, roster)]
        if "bn" not in used:
            targets.append(("kbo_roster_moves", pid,
                            base + ([("position", hit["position"])] if "pos" in used else [])))
        for t in targets:
            key = (t[0], t[1], tuple(t[2]))
            if key not in done:
                done.add(key)
                out.append(t)
    return out


def d1_update_sql(table, pid, conds):
    where = " AND ".join("%s=%s" % (c, sql_val(v)) for c, v in conds)
    return "UPDATE %s SET player_id=%d WHERE player_id IS NULL AND %s;" % (table, pid, where)


def mysql_write_new_players(sink, new_rows, targets):
    """새 선수는 없을 때만 넣고(created_at·updated_at 은 MySQL 기본값), 빈 ID 를 채웁니다."""
    if new_rows:
        sink.insert_missing("players", NEW_PLAYER_COLS, ["player_id"], new_rows)
    for table, pid, conds in targets:
        sink.execute(
            "UPDATE `%s` SET `player_id`=%%s WHERE `player_id` IS NULL AND %s"
            % (table, " AND ".join("`%s`=%%s" % c for c, _ in conds)),
            [pid] + [sink.value(table, c, v) for c, v in conds])
    return len(new_rows)
```

`main` 의 D1 문 만들기를 바꿉니다. `cols = [...]` 정의를 지우고 `NEW_PLAYER_COLS` 를 씁니다.

```python
    lines = []
    for p in new_rows:
        lines.append(
            "INSERT OR IGNORE INTO players (%s, created_at, updated_at) "
            "VALUES (%s, datetime('now'), datetime('now'));"
            % (", ".join(NEW_PLAYER_COLS), ", ".join(sql_val(p[c]) for c in NEW_PLAYER_COLS)))
    targets = id_fill_targets(found)
    lines += [d1_update_sql(*t) for t in targets]
```

(`done = set()` 부터 `lines.append(stmt)` 까지의 기존 반복은 지웁니다.)

`print("반영 완료 (새 선수 %d명, 문 %d개)" …)` 다음 줄에 넣습니다.

```python
    mirror("players_new", lambda s: mysql_write_new_players(s, new_rows, targets))
```

- [ ] **Step 6: `futures_records.py`**

import 에 `from mysql_sink import mirror  # noqa: E402` 를 더하고, `insert_sql` 아래에 둡니다.

```python
KEY = ["player_id", "season", "kind"]


def mysql_write_futures_stats(sink, rows, columns):
    """D1 과 같이 같은 열쇠는 덮어씁니다. 표는 1단계에서 만들어 두었습니다.

    사이트가 새 열을 내기 시작하면 D1 쪽 INSERT 가 먼저 실패하고, 여기서도
    없는 열이라 실패합니다. 둘 다 빨간색으로 드러납니다.
    """
    return sink.upsert("futures_season_stats", columns, KEY, rows)
```

`print("적재 완료 %s행" …)` 다음 줄에 넣습니다.

```python
    mirror("futures_records", lambda s: mysql_write_futures_stats(s, rows, columns))
```

- [ ] **Step 7: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_mirror_roster.py tests/test_sync_players_known_teams.py tests/test_futures_records.py tests/test_player_roster_backfill.py -p no:cacheprovider -q`
Expected: 모두 PASS.

- [ ] **Step 8: 커밋**

```bash
git add data_collection/roster_to_d1.py data_collection/sync_players_from_roster.py data_collection/add_new_players.py data_collection/futures_records.py tests/test_mysql_mirror_roster.py
git commit -m "feat(mysql-mirror): 등록 명단·소속 갱신·새 선수·퓨처스 기록을 MySQL 에도 씀

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: 표 통째 바꾸기(주간 결과·월간 선수)와 사진 주소

**Files:**
- Modify: `migration/sqlite_to_d1.py`, `data_collection/heal_player_photos.py`
- Test: `tests/test_mysql_mirror_replace.py` (새 파일)

**Interfaces:**
- Produces: `sqlite_to_d1.mysql_replace_tables(sink, tables: list[tuple[str, list[str], list[dict]]]) -> int`, `heal_player_photos.mysql_write_photos(sink, updates: list[tuple[str, str]]) -> int`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_mysql_mirror_replace.py`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import heal_player_photos  # noqa: E402
from migration import sqlite_to_d1  # noqa: E402


def test_replace_deletes_inserts_and_counts_each_table(fake_sink):
    tables = [("self_park_factor", ["season", "stadium"], [{"season": 2026, "stadium": "잠실"}]),
              ("players", ["player_id"], [{"player_id": 1}])]
    assert sqlite_to_d1.mysql_replace_tables(fake_sink, tables) == 2
    assert [c[0] for c in fake_sink.calls] == ["execute", "insert", "refresh_count"] * 2
    assert fake_sink.calls[0][1] == "DELETE FROM `self_park_factor`"
    assert fake_sink.calls[1][1:] == ("self_park_factor", ["season", "stadium"],
                                      [{"season": 2026, "stadium": "잠실"}])


def test_photos(fake_sink):
    n = heal_player_photos.mysql_write_photos(fake_sink, [("51234", "https://x/51234.jpg")])
    assert n == 1
    _, sql, params = fake_sink.calls[0]
    assert sql == ("UPDATE `players` SET `image_url`=%s, `updated_at`=UTC_TIMESTAMP() "
                   "WHERE `player_id`=%s")
    assert params == ["https://x/51234.jpg", 51234]
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_mirror_replace.py -p no:cacheprovider -q`
Expected: FAIL(함수 없음).

- [ ] **Step 3: `migration/sqlite_to_d1.py`**

import 를 더합니다.

```python
from data_collection.mysql_sink import mirror  # noqa: E402
```

`d1_has` 아래에 둡니다.

```python
def mysql_replace_tables(sink, tables):
    """D1 에 올린 표를 MySQL 에서도 통째로 바꿉니다.

    한 트랜잭션이라 중간에 실패하면 모두 되돌아가 옛 값이 그대로 남습니다.
    MySQL 에서 players 를 가리키는 외래키는 없어 지우고 넣어도 됩니다.
    """
    for table, cols, rows in tables:
        sink.execute("DELETE FROM `%s`" % table)
        sink.insert(table, cols, rows)
        sink.refresh_count(table)
    return len(tables)
```

`main` 에서 `pushed, skipped = [], []` 를 `pushed, skipped, mirrored = [], [], []` 로 바꾸고, `pushed.append((table, len(rows)))` 다음 줄에 넣습니다.

```python
        mirrored.append((table, cols, rows))
```

`conn.close()` 다음, `print()` 앞에 넣습니다.

```python
    if mirrored and not args.dry_run:
        mirror("sqlite_push", lambda s: mysql_replace_tables(s, mirrored))
```

- [ ] **Step 4: `data_collection/heal_player_photos.py`**

import 에 `from mysql_sink import mirror  # noqa: E402` 를 더하고, `flush` 아래에 둡니다.

```python
def mysql_write_photos(sink, updates):
    """D1 에 보낸 주소를 MySQL 에도 씁니다."""
    for pid, url in updates:
        sink.execute("UPDATE `players` SET `image_url`=%s, `updated_at`=UTC_TIMESTAMP() "
                     "WHERE `player_id`=%s", [url, int(pid)])
    return len(updates)
```

`main` 에서 `updates = []` 다음 줄에 `all_updates = []` 를 두고, `updates.append((pid, found))` 다음 줄에 `all_updates.append((pid, found))` 를 둡니다. 마지막 `flush(updates, args.dry_run)` 다음 줄에 넣습니다.

```python
    if all_updates and not args.dry_run:
        mirror("photos", lambda s: mysql_write_photos(s, all_updates))
```

- [ ] **Step 5: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_mirror_replace.py tests/test_player_photos.py tests/test_pipeline_tables.py -p no:cacheprovider -q`
Expected: 모두 PASS.

- [ ] **Step 6: 커밋**

```bash
git add migration/sqlite_to_d1.py data_collection/heal_player_photos.py tests/test_mysql_mirror_replace.py
git commit -m "feat(mysql-mirror): 주간 결과·월간 선수 표와 사진 주소를 MySQL 에도 씀

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Actions 접속·매일 대조·판정 (daily·roster·monthly)

**Files:**
- Create: `migration/mysql/ci_proxy.sh`
- Create: `migration/mysql/reconcile.py`
- Modify: `.github/workflows/daily.yml`, `.github/workflows/roster.yml`, `.github/workflows/monthly.yml`
- Test: `tests/test_mysql_reconcile.py`, `tests/test_mysql_workflows.py` (새 파일)

**Interfaces:**
- Consumes: 시크릿 5개(Task 1), 변수 `MYSQL_MIRROR`
- Produces: `ci_proxy.sh` 가 `$GITHUB_ENV` 에 `BSTATS_MYSQL_SETTINGS`·`BSTATS_MYSQL_MIRROR`·`BSTATS_MYSQL_FAIL_LOG` 를 남김. 입력 환경 변수 `MIRROR_MODE`(기본 `shadow`). Task 8 도 씁니다.
- Produces: `py -m migration.mysql.reconcile [--days N]` — 다르면 종료 코드 1. 함수 `canon(v)`, `d1_value(v, kind)`, `compare_counts(d1, my) -> list[str]`, `compare_keyed(table, cols, keys, d1_rows, my_rows, kinds) -> list[str]`, `count_sql(tables, quote) -> str`.

- [ ] **Step 1: 대조 테스트 쓰기**

`tests/test_mysql_reconcile.py`:

```python
import datetime
import decimal

from migration.mysql import reconcile as r


def test_canon_matches_load_rules():
    assert r.canon("") is None and r.canon("-") is None
    assert r.canon(datetime.date(2026, 10, 3)) == "2026-10-03"
    assert r.canon(datetime.datetime(2026, 10, 3, 4, 5, 6)) == "2026-10-03 04:05:06"
    assert r.canon(decimal.Decimal("3.0")) == 3
    assert r.canon(0.1 + 0.2) == 0.3


def test_d1_value_uses_column_kind():
    assert r.d1_value("7.0", "int") == 7
    assert r.d1_value("00", "text") == "00"
    assert r.d1_value("", "int") is None


def test_compare_counts_lists_only_differences():
    assert r.compare_counts({"a": 1, "b": 2}, {"a": 1, "b": 3}) == ["b 행 수: D1 2 / MySQL 3"]


def test_compare_keyed_reports_missing_and_changed():
    kinds = {"player_id": "int", "team_id": "text", "back_number": "int"}
    cols = ["player_id", "team_id", "back_number"]
    d1 = [{"player_id": "1", "team_id": "LG", "back_number": "07"},
          {"player_id": "2", "team_id": "KT", "back_number": None},
          {"player_id": "4", "team_id": "NC", "back_number": "9"}]
    my = [{"player_id": 1, "team_id": "LG", "back_number": 7},
          {"player_id": 3, "team_id": "SS", "back_number": 1},
          {"player_id": 4, "team_id": "NC", "back_number": 10}]
    probs = r.compare_keyed("players", cols, ["player_id"], d1, my, kinds)
    assert any("D1 에만 1행" in p for p in probs)
    assert any("MySQL 에만 1행" in p for p in probs)
    assert any("(4,)" in p and "back_number" in p for p in probs)
    assert len(probs) == 3


def test_count_sql():
    assert r.count_sql(["a", "b"], r.q) == (
        "SELECT 'a' AS t, COUNT(*) AS n FROM `a` UNION ALL "
        "SELECT 'b' AS t, COUNT(*) AS n FROM `b`")
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_reconcile.py -p no:cacheprovider -q`
Expected: `ModuleNotFoundError: … reconcile`

- [ ] **Step 3: `migration/mysql/reconcile.py` 쓰기**

```python
# -*- coding: utf-8 -*-
"""D1 과 MySQL 을 대조합니다. 2단계 이중 적재 동안 매일 돕니다.

    py -m migration.mysql.reconcile               # 다르면 종료 코드 1
    py -m migration.mysql.reconcile --days 7      # 최근 7일 경기는 경기별 행 수까지

- play_by_play 를 뺀 모든 표: 양쪽 행 수.
- players·kbo_roster·kbo_roster_moves: 열쇠로 짝지어 값까지 견줍니다. 수집이
  UPDATE 로 고치는 표라 행 수만으로는 어긋남이 안 보입니다. created_at·
  updated_at 은 두 DB 가 따로 시각을 찍으므로 뺍니다.
- play_by_play: D1 샤드별 meta_table_counts 합과 MySQL 행 수. 최근 N일
  경기는 경기별 행 수.

D1 읽기는 하루 약 7만 행입니다(무료 한도 500만의 1.4%). 값 비교 규칙은
적재와 같습니다. ''·'-' 는 값 없음, 정수 열의 '7.0' 은 7 입니다.
"""
import argparse
import datetime
import decimal
import json
import os
import sys

from migration import shard_plan
from migration.mysql import conn as myconn
from migration.mysql import typemap as tm
from migration.mysql.ddl import OUT_DIR, q

KST = datetime.timezone(datetime.timedelta(hours=9))
PBP = "play_by_play"
FULL = {"players": ["player_id"],
        "kbo_roster": ["team", "name", "back_number"],
        "kbo_roster_moves": ["move_date", "kind", "team", "name"]}
SKIP_COLS = {"created_at", "updated_at"}


def d1_query(sql, db_name=None):
    from data_collection.d1_load import DB_NAME, query
    return query(sql, db_name=db_name or DB_NAME)


def my_query(con, sql, params=None):
    with con.cursor() as cur:
        cur.execute(sql, params)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]


def canon(v):
    """견주기 위한 모양입니다. 두 DB 값 모두 이것을 거칩니다."""
    if v is None:
        return None
    if isinstance(v, (bytes, bytearray)):
        v = v.decode("utf-8")
    if isinstance(v, str) and v in ("", "-"):
        return None
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, datetime.date):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        v = float(v)
    if isinstance(v, float):
        return int(v) if v.is_integer() else round(v, 9)
    return v


def d1_value(v, kind):
    """D1 값을 MySQL 에 들어갔을 모양으로 바꿉니다(적재와 같은 규칙)."""
    try:
        return canon(tm.normalize(canon(v), kind))
    except ValueError:
        return ("바꿀 수 없음", v)


def compare_counts(d1, my):
    out = []
    for t in sorted(set(d1) | set(my)):
        if d1.get(t) != my.get(t):
            out.append("%s 행 수: D1 %s / MySQL %s" % (t, d1.get(t), my.get(t)))
    return out


def _keyed(rows, cols, keys, conv):
    out = {}
    for r in rows:
        vals = {c: conv(c, r.get(c)) for c in cols}
        out[tuple(vals[k] for k in keys)] = tuple(vals[c] for c in cols)
    return out


def compare_keyed(table, cols, keys, d1_rows, my_rows, kinds):
    a = _keyed(d1_rows, cols, keys, lambda c, v: d1_value(v, kinds[c]))
    b = _keyed(my_rows, cols, keys, lambda c, v: canon(v))
    out = []
    only_a = sorted(set(a) - set(b), key=repr)
    only_b = sorted(set(b) - set(a), key=repr)
    diff = sorted((k for k in set(a) & set(b) if a[k] != b[k]), key=repr)
    if only_a:
        out.append("%s: D1 에만 %d행 (예: %s)" % (table, len(only_a), only_a[:3]))
    if only_b:
        out.append("%s: MySQL 에만 %d행 (예: %s)" % (table, len(only_b), only_b[:3]))
    for k in diff[:5]:
        cols_diff = [c for c, x, y in zip(cols, a[k], b[k]) if x != y]
        out.append("%s %s: 값이 다름 %s" % (table, k, ", ".join(cols_diff)))
    if len(diff) > 5:
        out.append("%s: 값이 다른 행 %d개 더" % (table, len(diff) - 5))
    return out


def count_sql(tables, quote):
    return " UNION ALL ".join("SELECT '%s' AS t, COUNT(*) AS n FROM %s" % (t, quote(t))
                              for t in tables)


def check(my, types, days):
    """다른 곳 목록과 견준 최근 경기 수를 돌려줍니다."""
    tables = [t for t in types if t != PBP]
    problems = []

    d1c = {r["t"]: int(r["n"]) for r in d1_query(count_sql(tables, lambda t: '"%s"' % t) + ";")}
    myc = {r["t"]: int(r["n"]) for r in my_query(my, count_sql(tables, q))}
    problems += compare_counts(d1c, myc)

    for table, keys in FULL.items():
        kinds = dict(types[table]["columns"])
        cols = [c for c in kinds if c not in SKIP_COLS]
        d1rows = d1_query('SELECT %s FROM "%s";' % (", ".join('"%s"' % c for c in cols), table))
        myrows = my_query(my, "SELECT %s FROM %s" % (", ".join(q(c) for c in cols), q(table)))
        problems += compare_keyed(table, cols, keys, d1rows, myrows, kinds)

    d1_pbp = 0
    for s in shard_plan.shards():
        rows = d1_query("SELECT n FROM meta_table_counts WHERE name='play_by_play';",
                        s["database"])
        if not rows:
            problems.append("%s: meta_table_counts 에 play_by_play 행 수가 없습니다"
                            % s["database"])
            continue
        d1_pbp += int(rows[0]["n"])
    my_pbp = my_query(my, "SELECT COUNT(*) AS n FROM `play_by_play`")[0]["n"]
    if d1_pbp != my_pbp:
        problems.append("play_by_play 전체: D1 샤드 meta 합 %s / MySQL %s "
                        "(D1 meta 가 낡았을 수도 있습니다. 경기별 결과를 함께 보십시오)"
                        % (format(d1_pbp, ","), format(my_pbp, ",")))

    since = int((datetime.datetime.now(KST).date()
                 - datetime.timedelta(days=days)).strftime("%Y%m%d"))
    games = my_query(my, "SELECT game_id AS g, season FROM `games` WHERE game_date >= %s",
                     [since])
    by_db = {}
    for r in games:
        by_db.setdefault(shard_plan.db_of(r["season"]), []).append(r["g"])
    for db, ids in by_db.items():
        if not db:
            continue
        lit = ",".join("'%s'" % str(g).replace("'", "''") for g in ids)
        a = {r["g"]: int(r["n"]) for r in d1_query(
            "SELECT gameID AS g, COUNT(*) AS n FROM play_by_play "
            "WHERE gameID IN (%s) GROUP BY gameID;" % lit, db)}
        b = {r["g"]: int(r["n"]) for r in my_query(
            my, "SELECT gameID AS g, COUNT(*) AS n FROM `play_by_play` "
            "WHERE gameID IN (%s) GROUP BY gameID" % ", ".join(["%s"] * len(ids)), ids)}
        for g in sorted(set(a) | set(b)):
            if a.get(g, 0) != b.get(g, 0):
                problems.append("경기 %s 플레이 수: D1 %s / MySQL %s"
                                % (g, a.get(g, 0), b.get(g, 0)))
    return problems, len(games), len(tables)


def report(problems, n_tables, n_games, days):
    lines = ["## D1·MySQL 대조", "",
             "- 표 %d개 행 수, 값 대조 %s, 최근 %d일 경기 %d개"
             % (n_tables, "·".join(FULL), days, n_games), ""]
    if problems:
        lines += ["다른 곳 %d건:" % len(problems), ""] + ["- %s" % p for p in problems[:50]]
    else:
        lines.append("모두 같습니다.")
    text = "\n".join(lines)
    print(text)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3, help="경기별로 견줄 최근 일수")
    args = ap.parse_args()
    types = json.loads((OUT_DIR / "schema_types.json").read_text(encoding="utf-8"))
    my = myconn.connect()
    try:
        problems, n_games, n_tables = check(my, types, args.days)
    finally:
        my.close()
    report(problems, n_tables, n_games, args.days)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_reconcile.py -p no:cacheprovider -q`
Expected: 모두 PASS.

- [ ] **Step 5: `migration/mysql/ci_proxy.sh` 쓰기**

```bash
#!/usr/bin/env bash
# GitHub Actions 러너에서 Cloud SQL Auth Proxy 를 띄우고, 수집용 접속 파일을 만듭니다.
#
# GCP 인증은 앞 단계(google-github-actions/auth)가 만든 키 없는 자격(ADC)을 씁니다.
# 아래 값은 워크플로가 시크릿에서 넘깁니다. 화면에 찍지 않습니다.
#
#   CLOUDSQL_INSTANCE       프로젝트:지역:인스턴스
#   MYSQL_LOADER_PASSWORD   bstats_loader 비밀번호
#   MYSQL_SERVER_PUBKEY     서버 RSA 공개키(PEM). 프록시 경유 첫 로그인(caching_sha2)에 필요합니다
#   MIRROR_MODE             이중 적재 모드(shadow·off). 기본 shadow
set -euo pipefail

VERSION=2.26.0
# 공식 릴리스 노트의 cloud-sql-proxy.linux.amd64 체크섬입니다.
SHA256=a38fe97690a27490e60a7945a8a178186ff9464abb81fe2bc652a3f773443387

DIR="${RUNNER_TEMP:-/tmp}/bstats-mysql"
mkdir -p "$DIR"
BIN="$DIR/cloud-sql-proxy"
curl -fsSL -o "$BIN" \
  "https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v${VERSION}/cloud-sql-proxy.linux.amd64"
echo "${SHA256}  ${BIN}" | sha256sum -c -
chmod +x "$BIN"

"$BIN" --address 127.0.0.1 --port 3307 "$CLOUDSQL_INSTANCE" > "$DIR/proxy.log" 2>&1 &
for _ in $(seq 1 30); do
  if (echo > /dev/tcp/127.0.0.1/3307) 2>/dev/null; then break; fi
  sleep 1
done
if ! (echo > /dev/tcp/127.0.0.1/3307) 2>/dev/null; then
  echo "프록시가 30초 안에 뜨지 않았습니다."
  tail -20 "$DIR/proxy.log"
  exit 1
fi

umask 077
printf '%s' "$MYSQL_LOADER_PASSWORD" > "$DIR/password.txt"
printf '%s\n' "$MYSQL_SERVER_PUBKEY" > "$DIR/server_pub.pem"
python - "$DIR" <<'EOF'
import json, pathlib, sys
d = pathlib.Path(sys.argv[1])
(d / "mysql_ci.json").write_text(json.dumps({
    "host": "127.0.0.1", "port": 3307, "database": "bstats", "user": "bstats_loader",
    "password_file": str(d / "password.txt"), "ssl_ca": None,
    "server_public_key_file": str(d / "server_pub.pem")}), encoding="utf-8")
EOF

export BSTATS_MYSQL_SETTINGS="$DIR/mysql_ci.json"
python -m migration.mysql.conn --ping
{
  echo "BSTATS_MYSQL_SETTINGS=$DIR/mysql_ci.json"
  echo "BSTATS_MYSQL_MIRROR=${MIRROR_MODE:-shadow}"
  echo "BSTATS_MYSQL_FAIL_LOG=$DIR/failures.jsonl"
} >> "$GITHUB_ENV"
```

- [ ] **Step 6: 워크플로 테스트 쓰기**

`tests/test_mysql_workflows.py`:

```python
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"


def test_ci_proxy_pins_version_and_checksum():
    s = (ROOT / "migration" / "mysql" / "ci_proxy.sh").read_text(encoding="utf-8")
    assert "VERSION=2.26.0" in s
    assert re.search(r"SHA256=[0-9a-f]{64}", s)
    assert "sha256sum -c" in s


def test_collect_workflows_have_mirror_steps():
    for name in ("daily.yml", "roster.yml", "monthly.yml"):
        t = (WF / name).read_text(encoding="utf-8")
        assert "id-token: write" in t, name
        assert "vars.MYSQL_MIRROR == 'on'" in t, name
        assert "bash migration/mysql/ci_proxy.sh" in t, name
        assert "pymysql" in t, name
        assert "id: mirror_check" in t, name


def test_daily_reconciles():
    t = (WF / "daily.yml").read_text(encoding="utf-8")
    assert "python -m migration.mysql.reconcile" in t


def test_no_secret_values_in_workflows():
    for p in WF.glob("*.yml"):
        t = p.read_text(encoding="utf-8")
        assert "BEGIN PUBLIC KEY" not in t, p.name
        assert "iam.gserviceaccount.com" not in t, p.name
```

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_workflows.py -p no:cacheprovider -q`
Expected: `test_ci_proxy_pins_version_and_checksum`·`test_no_secret_values_in_workflows` 는 PASS, 나머지 둘은 FAIL.

- [ ] **Step 7: `google-github-actions/auth` 최신 주 버전 확인**

Run: `gh api repos/google-github-actions/auth/releases/latest --jq .tag_name`
Expected: `v3.x.y` 꼴. 주 버전이 3 이 아니면 아래 `@v3` 를 그 주 버전으로 바꿉니다.

- [ ] **Step 8: 세 워크플로에 단계 넣기**

**공통 1 — 권한.** `daily.yml`·`roster.yml`·`monthly.yml` 의 최상위(`env:` 블록 바로 앞)에 넣습니다.

```yaml
# id-token 은 GCP 키 없는 인증(Workload Identity Federation)에 필요합니다.
permissions:
  contents: read
  id-token: write
```

**공통 2 — 의존성.** 각 파일의 `pip install …` 줄 끝에 ` pymysql` 을 더합니다(daily: `pip install beautifulsoup4 lxml requests pandas tqdm pymysql`, roster: `pip install requests pymysql`, monthly: `pip install selenium webdriver-manager beautifulsoup4 lxml requests pandas pymysql`).

**공통 3 — 접속.** 각 파일의 `인증 확인` 단계 바로 다음에 넣습니다.

```yaml
      # --- MySQL 이중 적재(2단계) --------------------------------------
      # 저장소 변수 MYSQL_MIRROR 가 on 일 때만 붙습니다. 실패해도 D1 적재는
      # 계속합니다(사이트는 아직 D1 을 읽습니다). 대신 마지막 판정이 빨갛습니다.
      - name: GCP 인증(키 없음)
        id: gcp
        if: ${{ vars.MYSQL_MIRROR == 'on' }}
        continue-on-error: true
        uses: google-github-actions/auth@v3
        with:
          workload_identity_provider: ${{ secrets.GCP_WIF_PROVIDER }}
          service_account: ${{ secrets.GCP_LOADER_SA }}

      - name: MySQL 연결
        id: mysql
        if: ${{ steps.gcp.outcome == 'success' }}
        continue-on-error: true
        env:
          CLOUDSQL_INSTANCE: ${{ secrets.CLOUDSQL_INSTANCE }}
          MYSQL_LOADER_PASSWORD: ${{ secrets.MYSQL_LOADER_PASSWORD }}
          MYSQL_SERVER_PUBKEY: ${{ secrets.MYSQL_SERVER_PUBKEY }}
        run: bash migration/mysql/ci_proxy.sh
```

**공통 4 — 실패 확인.** 각 파일의 `요약` 단계 바로 앞에 넣습니다.

```yaml
      - name: MySQL 이중 적재 실패 확인
        id: mirror_check
        if: ${{ always() && steps.mysql.outcome == 'success' }}
        continue-on-error: true
        run: |
          if [ -s "$BSTATS_MYSQL_FAIL_LOG" ]; then
            echo "MySQL 에 쓰지 못한 작업이 있습니다:"
            cat "$BSTATS_MYSQL_FAIL_LOG"
            exit 1
          fi
          echo "MySQL 이중 적재 실패 없음"
```

**daily 만 — 대조.** `MySQL 이중 적재 실패 확인` 바로 앞에 넣습니다.

```yaml
      - name: D1·MySQL 대조
        id: reconcile
        if: ${{ always() && steps.mysql.outcome == 'success' }}
        continue-on-error: true
        run: python -m migration.mysql.reconcile --days 3
```

**요약 표.** daily·roster·monthly 의 `요약` 단계 표 끝에 넣습니다(daily 는 세 줄, 나머지는 앞의 두 줄).

```yaml
            echo "| MySQL 연결 | ${{ steps.mysql.outcome }} |"
            echo "| MySQL 이중 적재 | ${{ steps.mirror_check.outcome }} |"
            echo "| D1·MySQL 대조 | ${{ steps.reconcile.outcome }} |"
```

**판정.** daily 의 `실패 판정` 단계에서 `if [ "$fail" = "1" ]; then` 앞에 넣습니다.

```bash
          # MySQL 이 켜져 있으면 연결·이중 적재·대조도 성공해야 합니다.
          if [ "${{ vars.MYSQL_MIRROR }}" = "on" ]; then
            for s in "${{ steps.mysql.outcome }}" "${{ steps.mirror_check.outcome }}" \
                     "${{ steps.reconcile.outcome }}"; do
              if [ "$s" != "success" ]; then fail=1; fi
            done
          fi
```

roster·monthly 는 맨 끝에 판정 단계를 하나 더합니다.

```yaml
      - name: MySQL 이중 적재 판정
        if: ${{ always() && vars.MYSQL_MIRROR == 'on' && (steps.mysql.outcome != 'success' || steps.mirror_check.outcome != 'success') }}
        run: |
          echo "MySQL 연결 또는 이중 적재가 실패했습니다. 요약 표를 보십시오."
          exit 1
```

- [ ] **Step 9: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_workflows.py tests/test_mysql_reconcile.py tests/test_subprocess_portable.py -p no:cacheprovider -q`
Expected: 모두 PASS.

Run: `PYTHONUTF8=1 py -m pytest tests -p no:cacheprovider -q`
Expected: 알려진 2개 외 실패 0.

- [ ] **Step 10: 로컬에서 대조 한 번(읽기만, D1 약 7만 행)**

```bash
PYTHONUTF8=1 py -m migration.mysql.d1_usage
BSTATS_MYSQL_SETTINGS=~/.bstats/mysql_proxy.json PYTHONUTF8=1 py -m migration.mysql.reconcile --days 3
```

Expected: 스크립트가 끝까지 돌고, 10/2 이후 D1 에만 있는 변경(경기·명단·공식 기록 등)이 "다른 곳" 으로 나옵니다. 아직 따라잡기 전이라 다른 것이 정상입니다. 오류로 멈추면 고칩니다.

- [ ] **Step 11: 커밋**

```bash
git add migration/mysql/ci_proxy.sh migration/mysql/reconcile.py .github/workflows/daily.yml .github/workflows/roster.yml .github/workflows/monthly.yml tests/test_mysql_reconcile.py tests/test_mysql_workflows.py
git commit -m "feat(actions): 키 없는 GCP 인증·프록시로 MySQL 이중 적재, 매일 D1·MySQL 대조

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: 주간 계산을 MySQL 에서 내려받아 하기

D1 에서 내려받으면 400만 행 읽기라 무료 한도를 거의 다 씁니다. MySQL 에서 내려받고, 계산 결과는 지금처럼 D1 에 올리고 MySQL 에도 씁니다. 계산 결과가 D1 기준과 같은지 먼저 로컬에서 확인합니다. 파이프라인은 `games.game_type='정규시즌'` 으로 거르므로, MySQL 에서 고친 포스트시즌 날짜는 결과에 닿지 않습니다. 닿을 수 있는 것은 값 모양(''→NULL, '78513.0'→78513)뿐입니다.

**Files:**
- Create: `migration/mysql/mysql_to_sqlite.py`, `migration/mysql/compare_derived.py`
- Modify: `.github/workflows/weekly.yml`
- Create(생성물): `docs/mysql-migration/weekly-compare-report.md`
- Test: `tests/test_mysql_to_sqlite.py`, `tests/test_compare_derived.py` (새 파일), `tests/test_mysql_workflows.py` (1개 추가)

**Interfaces:**
- Consumes: `migration.d1_to_sqlite.PIPELINE_TABLES`, `migration.sqlite_to_d1.DERIVED_TABLES`, Task 7 의 `ci_proxy.sh`(`MIRROR_MODE`)
- Produces: `py -m migration.mysql.mysql_to_sqlite --out PATH [--tables a,b]`, 함수 `sqlite_ddl(table, spec, pk)`, `to_sqlite(v)`, `copy_table(my, sq, table, spec, batch=5000) -> int`
- Produces: `py -m migration.mysql.compare_derived --a A.db --b B.db`, 함수 `compare(a_con, b_con, table) -> list[str]`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_mysql_to_sqlite.py`:

```python
import datetime
import sqlite3

from migration.mysql import mysql_to_sqlite as m


class FakeCur:
    def __init__(self, con):
        self.con = con
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, args=None):
        self.con.log.append(sql)
        if "KEY_COLUMN_USAGE" in sql:
            self.rows = [("game_id",)]
        elif "STATISTICS" in sql:
            self.rows = [("idx_games_date", 1, "game_date")]
        elif sql.startswith("SELECT `game_id`"):
            self.rows = list(self.con.data)
        else:
            self.rows = []

    def fetchall(self):
        rows, self.rows = self.rows, []
        return rows

    def fetchmany(self, n):
        rows, self.rows = self.rows[:n], self.rows[n:]
        return rows


class FakeMy:
    def __init__(self, data):
        self.data, self.log = data, []

    def cursor(self, cls=None):
        return FakeCur(self)


def test_copy_table_keeps_pk_dates_and_indexes():
    spec = {"columns": [["game_id", "text"], ["game_date", "int"], ["as_of", "date"]]}
    my = FakeMy([("g1", 20261003, datetime.date(2026, 10, 3)), ("g2", 20261004, None)])
    sq = sqlite3.connect(":memory:")
    assert m.copy_table(my, sq, "games", spec, batch=1) == 2
    assert sq.execute("SELECT * FROM games ORDER BY game_id").fetchall() == [
        ("g1", 20261003, "2026-10-03"), ("g2", 20261004, None)]
    ddl = sq.execute("SELECT sql FROM sqlite_master WHERE name='games'").fetchone()[0]
    assert 'PRIMARY KEY ("game_id")' in ddl
    assert sq.execute("SELECT 1 FROM sqlite_master WHERE type='index' "
                      "AND name='idx_games_date'").fetchone()
    assert any("ORDER BY `game_id`" in s for s in my.log)


def test_play_by_play_has_no_primary_key():
    ddl = m.sqlite_ddl("play_by_play", {"columns": [["pbp_id", "int"], ["gameID", "text"]]},
                       ["pbp_id"])
    assert "PRIMARY KEY" not in ddl
    assert '"pbp_id" INTEGER' in ddl


def test_to_sqlite_values():
    assert m.to_sqlite(datetime.datetime(2026, 10, 3, 1, 2, 3)) == "2026-10-03 01:02:03"
    assert m.to_sqlite(datetime.date(2026, 10, 3)) == "2026-10-03"
    import decimal
    assert m.to_sqlite(decimal.Decimal("0.5")) == 0.5
```

`tests/test_compare_derived.py`:

```python
import sqlite3

from migration.mysql import compare_derived as cd


def _db(v, x):
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE t (k INTEGER, v TEXT, x REAL)")
    con.execute("INSERT INTO t VALUES (1, ?, ?)", (v, x))
    con.execute("INSERT INTO t VALUES (2, 'z', 3.0)")
    return con


def test_compare_finds_empty_vs_null():
    probs = cd.compare(_db("", 0.1), _db(None, 0.1), "t")
    assert probs[0].startswith("t: A 에만 1행, B 에만 1행")


def test_compare_ignores_float_noise():
    assert cd.compare(_db("a", 0.1 + 0.2), _db("a", 0.3), "t") == []


def test_compare_reports_missing_table():
    a = _db("a", 1.0)
    b = sqlite3.connect(":memory:")
    assert "한쪽에 표가 없습니다" in cd.compare(a, b, "t")[0]
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_to_sqlite.py tests/test_compare_derived.py -p no:cacheprovider -q`
Expected: 모듈 없음으로 FAIL.

- [ ] **Step 3: `migration/mysql/mysql_to_sqlite.py` 쓰기**

```python
# -*- coding: utf-8 -*-
"""MySQL 의 표를 로컬 SQLite 로 내려받습니다. 주간 파생 지표 계산용입니다.

d1_to_sqlite.py 를 대신합니다. D1 에서 내려받으면 play_by_play 400만 행을
읽어 하루 무료 한도(500만)를 거의 다 씁니다. MySQL 은 읽기 한도가 없습니다.

만드는 SQLite 는 d1_to_sqlite 결과와 같은 모양을 따릅니다.
- play_by_play 는 기본키 없이 둡니다(d1_to_sqlite.drop_primary_key 와 같게).
- 날짜는 'YYYY-MM-DD', 일시는 'YYYY-MM-DD HH:MM:SS' 글자로 둡니다.
- 인덱스는 MySQL 에 있는 것을 따라 만듭니다.
- 모든 표를 한 시점(일관된 스냅샷)에서 읽습니다. 내려받는 동안 수집이 돌아도
  표끼리 어긋나지 않습니다.

    py -m migration.mysql.mysql_to_sqlite --out /tmp/kbo_pipeline.db
    py -m migration.mysql.mysql_to_sqlite --out x.db --tables players,teams
"""
import argparse
import datetime
import decimal
import json
import sqlite3
import sys
import time
from pathlib import Path

import pymysql

from migration.d1_to_sqlite import PIPELINE_TABLES
from migration.mysql import conn as myconn
from migration.mysql.ddl import OUT_DIR, q

SQLITE_TYPES = {"int": "INTEGER", "double": "REAL", "text": "TEXT",
                "date": "TEXT", "datetime": "TEXT", "blob": "BLOB"}
NO_PK = {"play_by_play"}
BATCH = 5000


def sqlite_ddl(table, spec, pk):
    cols = ['"%s" %s' % (c, SQLITE_TYPES[k]) for c, k in spec["columns"]]
    if pk and table not in NO_PK:
        cols.append("PRIMARY KEY (%s)" % ", ".join('"%s"' % c for c in pk))
    return 'CREATE TABLE "%s" (%s)' % (table, ", ".join(cols))


def to_sqlite(v):
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, datetime.date):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return float(v)
    return v


def primary_key(cur, table):
    cur.execute("SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s "
                "AND CONSTRAINT_NAME = 'PRIMARY' ORDER BY ORDINAL_POSITION", (table,))
    return [r[0] for r in cur.fetchall()]


def secondary_indexes(cur, table):
    cur.execute("SELECT INDEX_NAME, NON_UNIQUE, COLUMN_NAME FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND INDEX_NAME <> 'PRIMARY' "
                "ORDER BY INDEX_NAME, SEQ_IN_INDEX", (table,))
    out = {}
    for name, non_unique, col in cur.fetchall():
        out.setdefault(name, [not int(non_unique), []])[1].append(col)
    return [(n, u, cols) for n, (u, cols) in out.items()]


def copy_table(my, sq, table, spec, batch=BATCH):
    """표 하나를 옮기고 옮긴 행 수를 돌려줍니다."""
    cols = [c for c, _ in spec["columns"]]
    with my.cursor() as cur:
        pk = primary_key(cur, table)
        idx = secondary_indexes(cur, table)
    sq.execute('DROP TABLE IF EXISTS "%s"' % table)
    sq.execute(sqlite_ddl(table, spec, pk))
    ins = 'INSERT INTO "%s" (%s) VALUES (%s)' % (
        table, ", ".join('"%s"' % c for c in cols), ", ".join("?" * len(cols)))
    order = (" ORDER BY " + ", ".join(q(c) for c in pk)) if pk else ""
    n = 0
    with my.cursor(pymysql.cursors.SSCursor) as cur:
        cur.execute("SELECT %s FROM %s%s" % (", ".join(q(c) for c in cols), q(table), order))
        while True:
            rows = cur.fetchmany(batch)
            if not rows:
                break
            sq.executemany(ins, [tuple(to_sqlite(v) for v in r) for r in rows])
            n += len(rows)
    for name, unique, icols in idx:
        sq.execute('CREATE %sINDEX "%s" ON "%s" (%s)' % (
            "UNIQUE " if unique else "", name, table, ", ".join('"%s"' % c for c in icols)))
    sq.commit()
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--tables", default=None,
                    help="쉼표로 구분. 기본값은 주간 계산에 쓰는 표(d1_to_sqlite.PIPELINE_TABLES)")
    args = ap.parse_args()

    tables = ([t.strip() for t in args.tables.split(",") if t.strip()]
              if args.tables else PIPELINE_TABLES)
    types = json.loads((OUT_DIR / "schema_types.json").read_text(encoding="utf-8"))
    unknown = [t for t in tables if t not in types]
    if unknown:
        raise SystemExit("schema_types.json 에 없는 표: %s" % ", ".join(unknown))

    out = Path(args.out)
    if out.exists():
        out.unlink()
    out.parent.mkdir(parents=True, exist_ok=True)
    sq = sqlite3.connect(str(out))
    my = myconn.connect()
    try:
        with my.cursor() as cur:
            cur.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
        for i, t in enumerate(tables, start=1):
            t0 = time.time()
            n = copy_table(my, sq, t, types[t])
            with my.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM %s" % q(t))
                want = cur.fetchone()[0]
            if want != n:
                raise SystemExit("%s 행 수가 어긋납니다. MySQL %s / 로컬 %s"
                                 % (t, format(want, ","), format(n, ",")))
            print("[%2d/%d] %-34s %10s행 %5.0f초"
                  % (i, len(tables), t, format(n, ","), time.time() - t0), flush=True)
        my.rollback()
    finally:
        my.close()
        sq.close()
    print("만든 DB: %s (%.1fMB)" % (out, out.stat().st_size / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: `migration/mysql/compare_derived.py` 쓰기**

```python
# -*- coding: utf-8 -*-
"""두 SQLite 의 파생 표를 견줍니다.

같은 주간 계산을 D1 기준 스냅샷(A)과 MySQL 에서 내려받은 SQLite(B)에 각각
돌린 뒤 결과 표가 같은지 봅니다. 다르면 MySQL 로 옮기며 바뀐 값 모양
(''→NULL, '78513.0'→78513 등)이 계산에 닿은 것입니다.

    py -m migration.mysql.compare_derived --a C:/tmp/weekly_d1.db --b C:/tmp/weekly_mysql.db
"""
import argparse
import collections
import sqlite3
import sys

from migration.mysql.ddl import ROOT
from migration.sqlite_to_d1 import DERIVED_TABLES

REPORT = ROOT / "docs" / "mysql-migration" / "weekly-compare-report.md"


def canon(v):
    if isinstance(v, float):
        return int(v) if v.is_integer() else round(v, 9)
    return v


def columns(con, table):
    return [r[1] for r in con.execute('PRAGMA table_info("%s")' % table)]


def rows(con, table, cols):
    sql = 'SELECT %s FROM "%s"' % (", ".join('"%s"' % c for c in cols), table)
    return collections.Counter(tuple(canon(v) for v in r) for r in con.execute(sql))


def compare(a, b, table):
    ca, cb = columns(a, table), columns(b, table)
    if not ca or not cb:
        return ["%s: 한쪽에 표가 없습니다 (A %s / B %s)" % (table, bool(ca), bool(cb))]
    if set(ca) != set(cb):
        return ["%s: 열이 다릅니다 (A만 %s / B만 %s)"
                % (table, sorted(set(ca) - set(cb)), sorted(set(cb) - set(ca)))]
    cols = sorted(ca)
    ra, rb = rows(a, table, cols), rows(b, table, cols)
    only_a, only_b = ra - rb, rb - ra
    if not only_a and not only_b:
        return []
    out = ["%s: A 에만 %d행, B 에만 %d행 (전체 A %d / B %d)"
           % (table, sum(only_a.values()), sum(only_b.values()),
              sum(ra.values()), sum(rb.values()))]
    out += ["   A: %s" % dict(zip(cols, r)) for r in list(only_a)[:3]]
    out += ["   B: %s" % dict(zip(cols, r)) for r in list(only_b)[:3]]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="D1 기준 SQLite")
    ap.add_argument("--b", required=True, help="MySQL 에서 내려받은 SQLite")
    args = ap.parse_args()
    a, b = sqlite3.connect(args.a), sqlite3.connect(args.b)
    lines = ["# 주간 계산 비교(D1 기준 A · MySQL 기준 B)", ""]
    bad = 0
    for t in DERIVED_TABLES:
        probs = compare(a, b, t)
        lines.append("- %s: %s" % (t, "같음" if not probs else "다름"))
        lines += ["  %s" % p for p in probs]
        bad += bool(probs)
    a.close()
    b.close()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    print("보고서: %s" % REPORT)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_to_sqlite.py tests/test_compare_derived.py -p no:cacheprovider -q`
Expected: 모두 PASS.

- [ ] **Step 6: 로컬 비교(관문) — Task 9 따라잡기 전에 합니다**

따라잡기 뒤에는 MySQL 에 10/2 이후 자료가 들어가 스냅샷과 견줄 수 없습니다. 프록시를 다시 띄운 뒤 합니다.

```bash
cp ~/.bstats/snapshots/d1_20261002.db C:/tmp/weekly_d1.db
BSTATS_MYSQL_SETTINGS=~/.bstats/mysql_proxy.json PYTHONUTF8=1 py -m migration.mysql.mysql_to_sqlite --out C:/tmp/weekly_mysql.db
for DB in C:/tmp/weekly_d1.db C:/tmp/weekly_mysql.db; do
  export KBO_DB="$DB"
  PYTHONUTF8=1 py park_factors/compute_self_park_factors.py && \
  PYTHONUTF8=1 py park_factors/build_woba_weights.py --write && \
  PYTHONUTF8=1 py park_factors/build_wrc_plus.py && \
  PYTHONUTF8=1 py park_factors/build_re24_run_values.py --write || echo "실패: $DB"
done
PYTHONUTF8=1 py -m migration.mysql.compare_derived --a C:/tmp/weekly_d1.db --b C:/tmp/weekly_mysql.db
```

Expected: 내려받기 끝에 `play_by_play 3,983,367행`, 계산 8번이 모두 끝나고(`실패:` 줄 없음), 비교가 6개 표 모두 `같음`.

**다르면 멈추고 evan 에게 보고합니다.** 보고서(`docs/mysql-migration/weekly-compare-report.md`)의 예시 행으로 어느 값 모양이 닿았는지 적고, (가) 계산 스크립트를 NULL 에 맞게 고칠지, (나) 바뀐 값을 받아들일지 evan 이 정합니다.

- [ ] **Step 7: weekly.yml 바꾸기**

권한에 `id-token: write` 를 더합니다.

```yaml
permissions:
  contents: write
  id-token: write
```

의존성 설치를 `pip install pandas numpy pymysql` 로 바꿉니다.

`디스크 확인` 단계 다음에 넣습니다. weekly 는 MySQL 이 없으면 돌 수 없으므로 `continue-on-error` 를 두지 않습니다.

```yaml
      # MySQL 이 D1 과 같다는 매일 대조가 켜진 뒤에만 돕니다. 그 전에 돌면
      # 낡은 MySQL 로 계산한 값을 D1 에 올리게 됩니다.
      - name: MySQL 이중 적재 켜짐 확인
        if: ${{ vars.MYSQL_MIRROR != 'on' }}
        run: |
          echo "저장소 변수 MYSQL_MIRROR 가 on 이 아닙니다. 2B Task 9 뒤에 돌리십시오."
          exit 1

      - name: GCP 인증(키 없음)
        uses: google-github-actions/auth@v3
        with:
          workload_identity_provider: ${{ secrets.GCP_WIF_PROVIDER }}
          service_account: ${{ secrets.GCP_LOADER_SA }}

      - name: MySQL 연결
        id: mysql
        env:
          CLOUDSQL_INSTANCE: ${{ secrets.CLOUDSQL_INSTANCE }}
          MYSQL_LOADER_PASSWORD: ${{ secrets.MYSQL_LOADER_PASSWORD }}
          MYSQL_SERVER_PUBKEY: ${{ secrets.MYSQL_SERVER_PUBKEY }}
          MIRROR_MODE: shadow
        run: bash migration/mysql/ci_proxy.sh
```

`D1 내려받기` 단계를 바꿉니다.

```yaml
      - name: MySQL 내려받기
        id: pull
        run: python -m migration.mysql.mysql_to_sqlite --out "$KBO_DB"
```

`결과 표 D1 적재` 의 주석을 `# 계산 결과를 D1 에 올리고 MySQL 에도 씁니다(sqlite_to_d1 의 mirror).` 로 바꿉니다. `요약` 앞에 Task 7 의 `MySQL 이중 적재 실패 확인`(id: mirror_check) 단계를 그대로 넣고, 요약 표의 `D1 내려받기` 줄을 `MySQL 내려받기` 로 바꾸고 `| MySQL 이중 적재 | ${{ steps.mirror_check.outcome }} |` 줄을 더합니다. 파일 머리 주석의 "러너가 D1 을 통째로 내려받아" 단락을 아래로 바꿉니다.

```yaml
# 러너가 MySQL 에서 계산에 쓰는 표를 내려받아 SQLite 를 만들고 기존
# 파이프라인을 그대로 돌립니다. 예전에는 D1 에서 받았는데, 12시즌이면
# 약 400만 행 읽기라 하루 무료 한도(500만)를 거의 다 썼습니다(2단계에서 바꿈).
```

`tests/test_mysql_workflows.py` 끝에 붙입니다.

```python
def test_weekly_pulls_from_mysql():
    t = (WF / "weekly.yml").read_text(encoding="utf-8")
    assert "python -m migration.mysql.mysql_to_sqlite" in t
    assert "migration/d1_to_sqlite.py" not in t
    assert "id-token: write" in t and "id: mirror_check" in t
```

- [ ] **Step 8: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_workflows.py tests/test_woba_weights.py tests/test_pipeline_tables.py -p no:cacheprovider -q`
Expected: 모두 PASS. `test_woba_weights.py`·`test_pipeline_tables.py` 가 `D1 내려받기` 단계 이름이나 `d1_to_sqlite` 호출을 확인하고 있으면, 단계가 MySQL 로 바뀐 것에 맞게 그 확인을 고칩니다(무엇을 고쳤는지 커밋 메시지에 적습니다).

- [ ] **Step 9: 커밋**

```bash
git add migration/mysql/mysql_to_sqlite.py migration/mysql/compare_derived.py .github/workflows/weekly.yml docs/mysql-migration/weekly-compare-report.md tests/test_mysql_to_sqlite.py tests/test_compare_derived.py tests/test_mysql_workflows.py
git commit -m "feat(weekly): 주간 계산을 MySQL 에서 내려받아 함(D1 400만 행 읽기 제거)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: 켜기·따라잡기·7일 지켜보기 (운영, evan 과 함께)

**전제:** 2A·2C(Task 5 인덱스 포함)·2B Task 1~8 이 main 에 들어가 push 되었고(evan 허락), 시크릿 5개가 등록되었고, Task 8 Step 6 비교가 `같음` 이거나 evan 이 차이를 받아들였습니다.

**시간:** 평일 10:00~15:00 KST. daily(03:33 KST)·roster(16:07 KST)·monthly(매월 1일 13:13 KST)와 겹치지 않는 때입니다.

- [ ] **Step 1: 돌고 있는 작업이 없는지 보기**

Run: `gh run list --repo Seunggon-Kim/b_project --limit 5`
Expected: `in_progress` 가 없습니다.

- [ ] **Step 2: 켜기(evan)**

Settings → Secrets and variables → Actions → Variables → New repository variable: 이름 `MYSQL_MIRROR`, 값 `on`.

- [ ] **Step 3: 연결 확인 — roster 를 손으로 한 번(evan)**

Actions → roster → Run workflow(main).
Expected: 요약 표에 `MySQL 연결 success`, `MySQL 이중 적재 success`. 실패하면 Step 2 의 변수를 지워 끄고 로그를 봅니다(D1 쪽은 그대로 돕니다).

- [ ] **Step 4: 공용 표 따라잡기(D1 읽기 약 6만 행, MySQL 공용 표 다시 넣기)**

D1 이 정본입니다. 10/2 이후 D1 에만 들어간 공용 표 변경을 통째로 가져옵니다. 이 단계는 10분 안팎이고, 그 사이에 수집 작업이 돌지 않아야 합니다(Step 1 을 다시 봅니다).

```bash
PYTHONUTF8=1 py -m migration.mysql.d1_usage
TABLES=$(PYTHONUTF8=1 py -c "import json; print(','.join(t for t in json.load(open('migration/mysql/schema_types.json', encoding='utf-8')) if t != 'play_by_play'))")
SNAP=~/.bstats/snapshots/d1_shared_$(date +%Y%m%d).db
PYTHONUTF8=1 py migration/d1_to_sqlite.py --out "$SNAP" --tables "$TABLES" --count-check none
BSTATS_MYSQL_SETTINGS=~/.bstats/mysql_proxy.json PYTHONUTF8=1 py -m migration.mysql.load --snapshot "$SNAP" --tables "$TABLES"
```

Expected: 내려받기 29개 표, 적재가 표마다 행 수를 찍고 고아 행 0 으로 끝납니다(종료 코드 0).

- [ ] **Step 5: PBP 따라잡기(D1 읽기 하루 약 1,500행 × 날짜 수)**

MySQL 에는 2026-10-01 까지 있습니다. 2026-10-02 부터 Step 2 에서 켠 뒤 처음 돈 daily 가 맡은 날짜(그 daily 실행일의 전날) 바로 전날까지 옮깁니다. 아직 daily 가 한 번도 안 돌았으면 어제까지입니다.

```bash
LAST=20261005   # 예: 마지막으로 옮길 날짜(YYYYMMDD). 위 규칙으로 정합니다.
D=20261002
while [ "$D" -le "$LAST" ]; do
  BSTATS_MYSQL_SETTINGS=~/.bstats/mysql_proxy.json PYTHONUTF8=1 \
    py data_collection/daily_pbp_to_d1.py --date "$D" --mysql-only || break
  D=$(date -d "$D + 1 day" +%Y%m%d)
done
```

Expected: 날짜마다 `MySQL 적재 완료 (N행)` 또는 `D1 행이 없습니다`. 하나라도 실패하면 반복이 멈추고, 그 날짜부터 다시 돌립니다(같은 날을 다시 넣어도 결과가 같습니다).

- [ ] **Step 6: 대조**

```bash
BSTATS_MYSQL_SETTINGS=~/.bstats/mysql_proxy.json PYTHONUTF8=1 py -m migration.mysql.reconcile --days 7
```

Expected: `모두 같습니다.` 다르면 줄마다 원인을 찾아 고치고 다시 대조합니다. D1 meta 가 낡아 `play_by_play 전체` 만 다르고 경기별이 모두 같으면, 다음 daily 가 meta 를 고친 뒤 다시 봅니다.

- [ ] **Step 7: 주간 작업 다시 켜기(evan)**

2A Task 5 로 일정을 주석 처리했으면 그 주석을 풀어 `schedule: - cron: '47 20 * * 1'` 를 되살리는 커밋을 만들고(evan 허락 뒤 push), 화면에서 껐으면 Actions → weekly → Enable workflow 로 켭니다. 켠 뒤 Run workflow 로 한 번 돌려 요약 표의 `MySQL 내려받기`·`D1 적재`·`MySQL 이중 적재` 가 모두 success 인지 봅니다.

- [ ] **Step 8: 7일 지켜보기**

매일 daily 요약의 `D1·MySQL 대조` 가 success 인지 봅니다. 7일 연속 success 면 2단계를 마칩니다. 중간에 실패하면 원인을 고친 날부터 다시 셉니다.

- [ ] **Step 9: 기록**

로드맵에 `### 2단계 결과` 를 더합니다(켠 날, 따라잡은 날짜 범위, 7일 대조 결과, 남은 일). 0단계 0-5 를 "MySQL 기준으로 다시 켬" 으로 고칩니다.

```bash
git add docs/superpowers/plans/2026-10-01-mysql-migration-roadmap.md
git commit -m "docs(mysql): 2단계 이중 적재 결과를 로드맵에 기록

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## 되돌리기

- 즉시: 저장소 변수 `MYSQL_MIRROR` 를 지웁니다. 모든 워크플로가 MySQL 에 손대지 않고, D1 은 지금처럼 돕니다. weekly 는 켜짐 확인 단계에서 멈추므로 일정을 함께 끕니다.
- 코드: 2B 병합 커밋을 되돌립니다(`git revert -m 1 <병합>`). D1 쪽 코드는 `add_new_players.py` 의 함수 분리 외에 바뀐 것이 없습니다.
- GCP: `gcloud iam service-accounts delete bstats-loader@…`, `gcloud iam workload-identity-pools delete github --location=global`, MySQL `DROP USER 'bstats_loader'@'cloudsqlproxy~%'`.
