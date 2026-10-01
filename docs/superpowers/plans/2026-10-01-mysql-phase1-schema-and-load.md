# 1단계: MySQL 스키마 설계와 데이터 이전 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** D1 7개(공용 `kbo-stats` + `play_by_play` 샤드 6개)를 로컬 SQLite 스냅샷으로 한 번 내려받고, 그 스냅샷을 Cloud SQL MySQL `bstats` 한 DB 로 옮긴 뒤, 두 쪽이 같은지 표·열 단위로 증명합니다.

**Architecture:** D1 읽기는 스냅샷 내려받기 한 번뿐입니다. 스키마는 스냅샷의 실제 값을 훑어(프로파일) 자동으로 만들고 사람이 검토합니다. 적재와 검증은 스냅샷 ↔ MySQL 사이에서만 일어나므로 D1 한도를 쓰지 않습니다. 사이트·수집은 이 단계 내내 D1 으로 돕니다.

**Tech Stack:** Python 3.13(`py`), sqlite3, PyMySQL 1.x, pytest, gcloud(`--configuration=bstats`), wrangler 4(`npx --yes wrangler@4`), Cloud SQL for MySQL 8.4.

**전체 지도:** `docs/superpowers/plans/2026-10-01-mysql-migration-roadmap.md`

## Global Constraints

- GCP 프로젝트 `bstats-kbo`, 인스턴스 `bstats-mysql`, 데이터베이스 `bstats`. gcloud 명령에는 항상 `--configuration=bstats --project=bstats-kbo` 를 붙입니다. 기본 설정(`default`, 회사 계정)을 활성화하거나 바꾸지 않습니다.
- `gcloud auth application-default login` 을 하지 않습니다(회사 ADC 를 덮습니다).
- gcloud 는 `export CLOUDSDK_PYTHON="/c/Users/김승곤/AppData/Local/Google/Cloud SDK/google-cloud-sdk/platform/bundledpython/python.exe" PYTHONUTF8=1` 가 있어야 돕니다(Git Bash).
- 비밀번호·인증서·접속 정보는 `~/.bstats/` 에만 둡니다. 화면·로그·커밋에 비밀번호를 출력하지 않습니다.
- **이 저장소는 공개(GitHub PUBLIC)입니다.** DB 서버 IP·계정 비밀번호·접속 파일 내용을 문서·코드·보고서에 적지 않습니다.
- 스냅샷은 `~/.bstats/snapshots/` 에 둡니다(1.5GB 이상, 저장소 밖).
- 이 단계에서 D1 에 쓰지 않습니다. D1 을 통째로 읽기 전에는 `py -m migration.mysql.d1_usage --max 1500000` 이 0 으로 끝나야 합니다.
- PyMySQL 은 `PyMySQL>=1.1,<2` 입니다.
- 테스트는 `py -m pytest tests/<파일> -v` 로 돌립니다.
- 코드 주석과 출력 문구는 기존 코드처럼 `~습니다` 체 한국어입니다.
- 이 저장소는 화면 세션이 동시에 씁니다. `dashboard_js/` 를 건드리지 않고, `git add` 는 파일을 하나하나 적습니다(`-A`·`.` 금지). 브랜치를 바꾸지 않습니다.
- 커밋은 evan 확인 후에 합니다. 커밋 메시지는 `feat(mysql): …` 형식의 한국어이고 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` 를 붙입니다. push 는 하지 않습니다.

## 파일 구조

| 파일 | 할 일 |
|---|---|
| `migration/mysql/__init__.py` | 패키지 표시(빈 파일) |
| `migration/mysql/tables.py` | 옮길 표/뺄 표 기준(내려받기·스키마가 공유) |
| `migration/mysql/conn.py` | `~/.bstats/mysql.json` 을 읽어 TLS 연결, `--ping` |
| `migration/mysql/d1_usage.py` | 오늘(UTC) D1 읽기 사용량(Cloudflare 통계, D1 한도 안 씀) |
| `migration/mysql/typemap.py` | 열 프로파일, 값 종류 선택, MySQL 타입, 값 정리 |
| `migration/mysql/ddl.py` | 스냅샷 → `schema.sql`·`schema_post.sql`·`schema_types.json`·보고서 |
| `migration/mysql/load.py` | 스냅샷 → MySQL 적재, 외래키 고아 행 확인, 적재 보고서 |
| `migration/mysql/verify.py` | 스냅샷 ↔ MySQL 대조, 검증 보고서 |
| `migration/d1_to_sqlite.py` (수정) | `--all-tables`·`--shards`·`--append`·`--count-check` |
| `requirements.txt` (수정) | PyMySQL 추가 |
| `tests/test_mysql_*.py`, `tests/test_d1_usage.py`, `tests/test_d1_to_sqlite_options.py` | 테스트 |
| 생성물: `migration/mysql/schema*.sql`, `schema_types.json`, `docs/mysql-migration/*.md` | 검토 후 커밋 |

---

### Task 1: 접속 준비 (PyMySQL, 이전용 계정, TLS 연결)

**Files:**
- Create: `migration/mysql/__init__.py`, `migration/mysql/conn.py`
- Modify: `requirements.txt`
- Test: `tests/test_mysql_conn.py`

**Interfaces:**
- Produces: `conn.load_settings(path=SETTINGS_PATH) -> dict`(필수 키 `host, port, database, user, password_file, ssl_ca`), `conn.connect(settings=None, database=True) -> pymysql.connections.Connection`(autocommit 꺼짐, utf8mb4, TLS), CLI `py -m migration.mysql.conn --ping`.

- [ ] **Step 1: PyMySQL 설치와 의존성 기록**

```bash
py -m pip install "PyMySQL>=1.1,<2"
```

`requirements.txt` 맨 아래에 붙입니다.

```text

# DB (Cloud SQL MySQL 이전)
PyMySQL>=1.1,<2
```

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/test_mysql_conn.py`

```python
import json

import pytest

from migration.mysql import conn


def _write(tmp_path, data):
    p = tmp_path / "mysql.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_load_settings_reads_all_required_keys(tmp_path):
    p = _write(tmp_path, {"host": "1.2.3.4", "port": 3306, "database": "bstats",
                          "user": "u", "password_file": "pw.txt", "ssl_ca": "ca.pem"})
    s = conn.load_settings(p)
    assert s["host"] == "1.2.3.4"
    assert s["port"] == 3306


def test_load_settings_names_missing_keys(tmp_path):
    p = _write(tmp_path, {"host": "1.2.3.4"})
    with pytest.raises(ValueError, match="ssl_ca"):
        conn.load_settings(p)
```

- [ ] **Step 3: 실패 확인**

Run: `py -m pytest tests/test_mysql_conn.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'migration.mysql'`)

- [ ] **Step 4: 구현**

`migration/mysql/__init__.py` 는 빈 파일입니다.

`migration/mysql/conn.py`

```python
# -*- coding: utf-8 -*-
"""Cloud SQL(MySQL) 접속 정보를 읽어 연결을 만듭니다.

접속 정보는 저장소 밖 `~/.bstats/mysql.json` 에 둡니다. 비밀번호는 그
파일이 가리키는 별도 파일에서 읽습니다. 둘 다 커밋하지 않습니다.

서버 인증서는 Cloud SQL 서버 CA 로 검증합니다. 공인 IP 로 붙으므로
호스트 이름 검증(ssl_verify_identity)은 끕니다. 인증서의 이름은 IP 가
아니라 인스턴스 이름입니다.

    py -m migration.mysql.conn --ping
"""
import argparse
import json
import sys
from pathlib import Path

import pymysql

SETTINGS_PATH = Path.home() / ".bstats" / "mysql.json"
REQUIRED = ("host", "port", "database", "user", "password_file", "ssl_ca")


def load_settings(path=SETTINGS_PATH):
    """접속 정보를 읽습니다. 빠진 항목이 있으면 이름을 적어 ValueError."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise ValueError("mysql.json 에 없는 항목: %s" % ", ".join(missing))
    return data


def connect(settings=None, database=True):
    """TLS 연결을 엽니다. autocommit 은 꺼져 있습니다."""
    s = settings or load_settings()
    password = Path(s["password_file"]).read_text(encoding="ascii").strip()
    return pymysql.connect(
        host=s["host"], port=int(s["port"]), user=s["user"],
        password=password,
        database=s["database"] if database else None,
        charset="utf8mb4", autocommit=False,
        ssl_ca=s["ssl_ca"], ssl_verify_cert=True, ssl_verify_identity=False,
        connect_timeout=20, read_timeout=900, write_timeout=900)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ping", action="store_true", help="버전과 암호화 여부를 봅니다")
    ap.parse_args()
    con = connect()
    with con.cursor() as cur:
        cur.execute("SELECT VERSION(), DATABASE()")
        version, db = cur.fetchone()
        cur.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
        cipher = cur.fetchone()[1]
    con.close()
    print("MySQL %s / DB %s / 암호화 %s" % (version, db, cipher or "없음"))
    return 0 if cipher else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `py -m pytest tests/test_mysql_conn.py -v`
Expected: 2 passed

- [ ] **Step 6: 내 PC IP 를 허용하고 서버 CA 를 받기**

```bash
export CLOUDSDK_PYTHON="/c/Users/김승곤/AppData/Local/Google/Cloud SDK/google-cloud-sdk/platform/bundledpython/python.exe" PYTHONUTF8=1
MYIP=$(curl -s https://api.ipify.org)
gcloud sql instances patch bstats-mysql --authorized-networks="$MYIP/32" \
  --configuration=bstats --project=bstats-kbo --quiet
gcloud sql instances describe bstats-mysql --configuration=bstats --project=bstats-kbo \
  --format="value(serverCaCert.cert)" > ~/.bstats/server-ca.pem
test -s ~/.bstats/server-ca.pem || gcloud sql ssl server-ca-certs list --instance=bstats-mysql \
  --configuration=bstats --project=bstats-kbo --format="value(cert)" > ~/.bstats/server-ca.pem
head -1 ~/.bstats/server-ca.pem
```

Expected: 마지막 줄이 `-----BEGIN CERTIFICATE-----`. 집 인터넷 IP 가 바뀌면 이 단계의 `patch` 만 다시 합니다(목록을 통째로 바꿉니다).

- [ ] **Step 7: 이전용 계정 `bstats_migrator` 만들기**

이 저장소는 공개입니다. 서버 IP 를 계획서·코드에 적지 않고, 실행할 때 gcloud 로 받아 `~/.bstats/` 에만 남깁니다.

```bash
gcloud sql instances describe bstats-mysql --configuration=bstats --project=bstats-kbo \
  --format="value(ipAddresses[0].ipAddress)" > ~/.bstats/mysql_host.txt
py - <<'EOF'
import pathlib, secrets, string
import pymysql
home = pathlib.Path.home() / ".bstats"
pw_file = home / "mysql_migrator_password.txt"
if not pw_file.exists():
    pw_file.write_text("".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32)), encoding="ascii")
con = pymysql.connect(
    host=(home / "mysql_host.txt").read_text().strip(), user="root",
    password=(home / "cloudsql_root_password.txt").read_text().strip(),
    ssl_ca=str(home / "server-ca.pem"), ssl_verify_cert=True, ssl_verify_identity=False)
with con.cursor() as cur:
    cur.execute("CREATE USER IF NOT EXISTS 'bstats_migrator'@'%%' IDENTIFIED BY %s REQUIRE SSL",
                (pw_file.read_text().strip(),))
    cur.execute("GRANT ALL PRIVILEGES ON `bstats`.* TO 'bstats_migrator'@'%'")
con.commit()
con.close()
print("bstats_migrator 준비 완료")
EOF
```

첫 질의는 인자가 있어 `%%` 가 `%` 로 바뀌고, 두 번째는 인자가 없어 `%` 를 그대로 씁니다(PyMySQL 규칙).

Expected: `bstats_migrator 준비 완료`

- [ ] **Step 8: 접속 정보 파일 쓰기**

```bash
py - <<'EOF'
import json, pathlib
home = pathlib.Path.home() / ".bstats"
(home / "mysql.json").write_text(json.dumps({
    "host": (home / "mysql_host.txt").read_text().strip(), "port": 3306, "database": "bstats",
    "user": "bstats_migrator",
    "password_file": str(home / "mysql_migrator_password.txt"),
    "ssl_ca": str(home / "server-ca.pem"),
}, ensure_ascii=False, indent=1), encoding="utf-8")
print("저장:", home / "mysql.json")
EOF
```

- [ ] **Step 9: 실제 접속 확인**

Run: `py -m migration.mysql.conn --ping`
Expected: `MySQL 8.4.x / DB bstats / 암호화 TLS_…` 이고 종료 코드 0

- [ ] **Step 10: 커밋(evan 확인 후)**

```bash
git add migration/mysql/__init__.py migration/mysql/conn.py tests/test_mysql_conn.py requirements.txt
git commit -m "feat(mysql): Cloud SQL 이전용 TLS 연결 모듈" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: 내려받기 도구 확장 (표 전부, 샤드 나눠 받기, 읽기 예산)

**Files:**
- Create: `migration/mysql/tables.py`, `migration/mysql/d1_usage.py`
- Modify: `migration/d1_to_sqlite.py`
- Test: `tests/test_mysql_tables.py`, `tests/test_d1_usage.py`, `tests/test_d1_to_sqlite_options.py`

**Interfaces:**
- Produces: `tables.is_migrated(name) -> bool`, `tables.migrated_tables(names) -> list[str]`(정렬 + `play_by_play` 한 번), `tables.SHARD_ONLY = ("play_by_play",)`; `d1_usage.summarize(groups, names) -> (int, dict)`; `d1_to_sqlite.export_jobs(tables, shards=None)`, `d1_to_sqlite._has_rows(conn, table) -> bool`, `d1_to_sqlite.list_tables(db_name)`, `d1_to_sqlite.meta_row_count(table, db_name)`, CLI 옵션 `--all-tables --shards --append --count-check {d1,meta,none}`.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_mysql_tables.py`

```python
from migration.mysql.tables import is_migrated, migrated_tables


def test_skips_internal_and_backup_tables():
    for name in ["sqlite_sequence", "_cf_KV", "d1_migrations",
                 "wrc_plus_comparison_bak", "kbo_official_batter_stats_bak_pre12"]:
        assert not is_migrated(name), name


def test_keeps_real_tables():
    for name in ["players", "kbo_roster_moves", "meta_table_counts",
                 "meta_backfill", "team_logos"]:
        assert is_migrated(name), name


def test_migrated_tables_adds_shard_only_table_once():
    assert migrated_tables(["teams", "players", "sqlite_sequence"]) == \
        ["players", "teams", "play_by_play"]
    assert migrated_tables(["play_by_play"]) == ["play_by_play"]
```

`tests/test_d1_usage.py`

```python
from migration.mysql.d1_usage import summarize


def test_summarize_adds_rows_per_database_and_total():
    groups = [
        {"dimensions": {"databaseId": "a"}, "sum": {"rowsRead": 10}},
        {"dimensions": {"databaseId": "b"}, "sum": {"rowsRead": 5}},
        {"dimensions": {"databaseId": "a"}, "sum": {"rowsRead": 1}},
    ]
    total, per = summarize(groups, {"a": "kbo-stats"})
    assert total == 16
    assert per == {"kbo-stats": 11, "b": 5}
```

`tests/test_d1_to_sqlite_options.py`

```python
import sqlite3

from migration import d1_to_sqlite as m


def test_export_jobs_limits_shards_when_asked():
    jobs = m.export_jobs(["teams", "play_by_play"],
                         shards={"DB_2008_2011", "DB_2012_2014"})
    assert ("teams", "kbo-stats", "teams") in jobs
    pbp = [j for j in jobs if j[0] == "play_by_play"]
    assert [j[1] for j in pbp] == ["kbo-pbp-2008-2011", "kbo-pbp-2012-2014"]


def test_export_jobs_without_filter_keeps_all_six_shards():
    pbp = [j for j in m.export_jobs(["play_by_play"]) if j[0] == "play_by_play"]
    assert len(pbp) == 6


def test_has_rows(tmp_path):
    con = sqlite3.connect(str(tmp_path / "x.db"))
    assert not m._has_rows(con, "t")
    con.execute("CREATE TABLE t (a)")
    assert not m._has_rows(con, "t")
    con.execute("INSERT INTO t VALUES (1)")
    assert m._has_rows(con, "t")
```

- [ ] **Step 2: 실패 확인**

Run: `py -m pytest tests/test_mysql_tables.py tests/test_d1_usage.py tests/test_d1_to_sqlite_options.py -v`
Expected: FAIL (`No module named 'migration.mysql.tables'`, `export_jobs() got an unexpected keyword argument 'shards'`)

- [ ] **Step 3: `migration/mysql/tables.py` 구현**

```python
# -*- coding: utf-8 -*-
"""MySQL 로 옮길 표와 옮기지 않을 표를 가릅니다.

내려받기(`migration/d1_to_sqlite.py --all-tables`)와 스키마 생성
(`migration/mysql/ddl.py`)이 같은 기준을 써야 합니다. 한쪽만 고치면
받아 놓고 안 옮기거나, 옮기려는데 안 받은 표가 생깁니다.
"""
import re

# sqlite_* 와 _cf_* 는 SQLite·D1 내부 표입니다. d1_migrations 는 wrangler
# 마이그레이션 기록입니다. _bak 은 손으로 만든 백업입니다.
_SKIP = re.compile(r"^(sqlite_|_cf_)|^d1_migrations$|_bak($|_)")

# 공용 DB 에 없고 샤드에만 있는 표입니다.
SHARD_ONLY = ("play_by_play",)


def is_migrated(name):
    """옮길 표면 True 입니다."""
    return not _SKIP.search(name)


def migrated_tables(names):
    """공용 DB 표 이름에서 옮길 것만 고르고, 샤드 전용 표를 한 번 더합니다."""
    out = sorted(n for n in names if is_migrated(n))
    for t in SHARD_ONLY:
        if t not in out:
            out.append(t)
    return out
```

- [ ] **Step 4: `migration/mysql/d1_usage.py` 구현**

```python
# -*- coding: utf-8 -*-
"""오늘(UTC) D1 읽기 사용량을 봅니다.

D1 무료 요금제는 하루 500만 행을 읽으면 다음 00:00 UTC(09:00 KST)까지
모든 질의가 막힙니다. D1 을 통째로 읽는 작업 전에 이걸 먼저 돌립니다.
Cloudflare 통계(GraphQL)만 읽으므로 D1 한도를 쓰지 않습니다.

인증은 wrangler 로그인 토큰을 씁니다(`npx wrangler login` 이 만든 것).

    py -m migration.mysql.d1_usage
    py -m migration.mysql.d1_usage --max 1500000   # 넘으면 종료 코드 2
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

LIMIT = 5_000_000
API = "https://api.cloudflare.com/client/v4"
QUERY = """query($acc:String!,$d:Date!){viewer{accounts(filter:{accountTag:$acc}){
  d1AnalyticsAdaptiveGroups(limit:1000, filter:{date_geq:$d, date_leq:$d}){
    sum{ rowsRead } dimensions{ databaseId } } }}}"""


def token_paths():
    paths = []
    if os.environ.get("APPDATA"):
        paths.append(Path(os.environ["APPDATA"]) / "xdg.config" / ".wrangler"
                     / "config" / "default.toml")
    paths.append(Path.home() / ".config" / ".wrangler" / "config" / "default.toml")
    paths.append(Path.home() / ".wrangler" / "config" / "default.toml")
    return paths


def read_token():
    for p in token_paths():
        if p.exists():
            m = re.search(r'oauth_token\s*=\s*"([^"]+)"', p.read_text(encoding="utf-8"))
            if m:
                return m.group(1)
    raise SystemExit("wrangler 로그인 토큰이 없습니다. `npx wrangler login` 을 먼저 하십시오.")


def summarize(groups, names):
    """GraphQL 결과 행을 (합계, {DB 이름: 행 수}) 로 줄입니다."""
    per = {}
    for g in groups:
        db = g["dimensions"]["databaseId"]
        name = names.get(db, db)
        per[name] = per.get(name, 0) + g["sum"]["rowsRead"]
    return sum(per.values()), per


def _call(tok, url, body=None):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode() if body else None,
        headers={"Authorization": "Bearer " + tok,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=None,
                    help="오늘 이보다 많이 읽었으면 종료 코드 2")
    args = ap.parse_args()
    tok = read_token()
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    total, per_all = 0, {}
    for acc in _call(tok, API + "/accounts")["result"]:
        names = {d["uuid"]: d["name"] for d in _call(
            tok, API + "/accounts/%s/d1/database?per_page=100" % acc["id"])["result"]}
        r = _call(tok, API + "/graphql",
                  {"query": QUERY, "variables": {"acc": acc["id"], "d": today}})
        if r.get("errors"):
            raise SystemExit("통계 조회 실패: %s" % r["errors"][0].get("message"))
        groups = r["data"]["viewer"]["accounts"][0]["d1AnalyticsAdaptiveGroups"]
        t, per = summarize(groups, names)
        total += t
        per_all.update(per)
    print("%s (UTC) D1 읽기 %s행 / 한도 %s행 (%.1f%%)"
          % (today, format(total, ","), format(LIMIT, ","), total * 100 / LIMIT))
    for name, n in sorted(per_all.items(), key=lambda kv: -kv[1]):
        print("   %-22s %s" % (name, format(n, ",")))
    if args.max is not None and total > args.max:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: `migration/d1_to_sqlite.py` 수정**

`from migration import shard_plan  # noqa: E402` 바로 아래에 더합니다.

```python
from migration.mysql.tables import migrated_tables  # noqa: E402
```

`shard_row_count` 함수 아래에 세 함수를 더합니다.

```python
def list_tables(db_name=DB_NAME):
    """공용 D1 의 표 이름입니다. sqlite_master 몇 줄만 읽습니다."""
    out = subprocess.run(
        ["npx", "--yes", "wrangler@4", "d1", "execute", db_name, "--remote",
         "--command",
         "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;",
         "--json", "--yes"],
        capture_output=True, text=True, shell=USE_SHELL,
        encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise RuntimeError("표 목록 실패: %s" % (out.stderr or out.stdout)[-400:])
    body = out.stdout[out.stdout.find("["):]
    return [r["name"] for r in json.loads(body)[0]["results"]]


def meta_row_count(table, db_name):
    """샤드의 meta_table_counts 에 적힌 행 수입니다. 없으면 None 입니다.

    `shard_row_count` 는 COUNT(*) 라 표 전체를 한 번 더 읽습니다(샤드당
    55만~70만 행). 이건 한 줄만 읽습니다.
    """
    try:
        out = subprocess.run(
            ["npx", "--yes", "wrangler@4", "d1", "execute", db_name,
             "--remote", "--command",
             "SELECT n FROM meta_table_counts WHERE name='%s';" % table,
             "--json", "--yes"],
            capture_output=True, text=True, shell=USE_SHELL,
            encoding="utf-8", errors="replace")
        if out.returncode != 0:
            return None
        rows = json.loads(out.stdout[out.stdout.find("["):])[0]["results"]
        return int(rows[0]["n"]) if rows else None
    except Exception:            # noqa: BLE001
        return None


def _has_rows(conn, table):
    """로컬 SQLite 에 그 표가 있고 한 줄이라도 있으면 True 입니다."""
    found = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,)).fetchone()
    if not found:
        return False
    return conn.execute('SELECT 1 FROM "%s" LIMIT 1' % table).fetchone() is not None
```

`export_jobs` 를 바꿉니다(기존 호출은 그대로 동작합니다).

```python
def export_jobs(tables, shards=None):
    """(표, D1 이름, 파일이름) 목록입니다. 나뉜 표는 샤드마다 하나씩.

    shards 를 주면(바인딩 이름 집합) 나뉜 표는 그 샤드에서만 받습니다.
    무료 요금제에서 하루 읽기 한도를 넘지 않게 이틀에 나눠 받을 때
    씁니다.

    샤드는 하나의 원본 표를 시즌으로 갈라 담았고 `pbp_id` 를 그대로
    옮겼습니다. 그래서 샤드끼리 번호가 겹치지 않고, 합쳐도 PK 가
    부딪히지 않습니다. 나중에 지난 시즌을 샤드에 새로 넣으면 그 샤드가
    자기 최대값 다음 번호를 붙이므로 겹칠 수 있습니다. 그때는 아래
    executescript 가 UNIQUE 위반으로 시끄럽게 실패합니다. 조용히
    덮어써서 행을 잃는 것보다 낫습니다.
    """
    jobs = []
    for t in tables:
        if t in SHARDED_TABLES:
            for s in shard_plan.shards():
                if shards is None or s["binding"] in shards:
                    jobs.append((t, s["database"], "%s__%s" % (t, s["binding"])))
        else:
            jobs.append((t, DB_NAME, t))
    return jobs
```

`main()` 의 인자 정의 뒤를 다음처럼 바꿉니다(`--out`·`--tables`·`--keep-sql` 은 그대로).

```python
    ap.add_argument("--all-tables", action="store_true",
                    help="공용 D1 의 옮길 표 전부와 play_by_play 를 받습니다")
    ap.add_argument("--shards", default=None,
                    help="나뉜 표를 이 바인딩의 샤드에서만 받습니다. "
                         "예: DB_2008_2011,DB_2012_2014")
    ap.add_argument("--append", action="store_true",
                    help="--out 을 지우지 않고 나뉜 표를 이어 붙입니다")
    ap.add_argument("--count-check", choices=["d1", "meta", "none"],
                    default="d1",
                    help="샤드 행 수 확인: d1=COUNT(*)(표를 한 번 더 읽음), "
                         "meta=meta_table_counts 한 줄, none=안 함")
    args = ap.parse_args()

    if args.all_tables:
        tables = migrated_tables(list_tables())
    elif args.tables:
        tables = [t.strip() for t in args.tables.split(",") if t.strip()]
    else:
        tables = PIPELINE_TABLES
    shards = ({s.strip() for s in args.shards.split(",") if s.strip()}
              if args.shards else None)

    out = Path(args.out)
    if out.exists() and not args.append:
        # 이어붙이면 이전 실행의 행이 남아 계산이 어긋납니다.
        out.unlink()
    out.parent.mkdir(parents=True, exist_ok=True)
```

`conn = sqlite3.connect(str(out))` 다음 줄들을 바꿉니다.

```python
        conn = sqlite3.connect(str(out))
        total_bytes = 0
        prev_rows = {}
        if args.append:
            # 이어 받을 때는 이미 있는 행 수부터 셉니다. 그래야 이번에
            # 받은 조각만 D1 쪽 행 수와 견줍니다.
            for t in SHARDED_TABLES:
                if _has_rows(conn, t):
                    prev_rows[t] = conn.execute(
                        'SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
        jobs = export_jobs(tables, shards)
        for i, (t, db, tag) in enumerate(jobs, start=1):
            if args.append and t not in SHARDED_TABLES and _has_rows(conn, t):
                raise SystemExit(
                    "%s 는 이미 %s 에 있습니다. --append 는 나뉜 표를 더 받을 "
                    "때만 씁니다." % (t, out))
```

샤드 행 수 확인 블록을 바꿉니다.

```python
            if t in SHARDED_TABLES and args.count_check != "none":
                want = (shard_row_count(t, db) if args.count_check == "d1"
                        else meta_row_count(t, db))
                got = n - prev_rows.get(t, 0)
                if want is None:
                    print("   %s(%s) 행 수를 확인하지 못했습니다(메타 없음)."
                          % (t, db), flush=True)
                elif want != got:
                    raise SystemExit(
                        "%s(%s) 행 수가 어긋납니다. D1 %s / 로컬 %s"
                        % (t, db, format(want, ","), format(got, ",")))
            prev_rows[t] = n
```

- [ ] **Step 6: 테스트 통과 확인(기존 샤드 테스트 포함)**

Run: `py -m pytest tests/test_mysql_tables.py tests/test_d1_usage.py tests/test_d1_to_sqlite_options.py tests/test_shard_routing.py tests/test_pipeline_tables.py -v`
Expected: 전부 passed

- [ ] **Step 7: 사용량 도구 실제 실행**

Run: `py -m migration.mysql.d1_usage`
Expected: `YYYY-MM-DD (UTC) D1 읽기 …행 / 한도 5,000,000행 (…%)` 과 DB 별 줄

- [ ] **Step 8: 커밋(evan 확인 후)**

```bash
git add migration/mysql/tables.py migration/mysql/d1_usage.py migration/d1_to_sqlite.py \
  tests/test_mysql_tables.py tests/test_d1_usage.py tests/test_d1_to_sqlite_options.py
git commit -m "feat(mysql): D1 전체 내려받기 옵션과 읽기 사용량 확인 도구" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: D1 스냅샷 만들기 (D1 읽기는 여기서 한 번)

**Files:**
- Create(저장소 밖): `~/.bstats/snapshots/d1_<YYYYMMDD>.db`

**Interfaces:**
- Consumes: Task 2 의 CLI 옵션, `d1_usage`.
- Produces: 스냅샷 SQLite 한 개. 공용 DB 의 옮길 표 전부 + 6개 샤드를 합친 `play_by_play`(PK 없음, rowid 순서 = 샤드 순서 → 샤드 안 원래 `pbp_id` 순서).

이 Task 는 코드가 아니라 실행입니다. 반드시 09:00 KST(00:00 UTC) 이후, 그날 사용량을 본 뒤 합니다.

- [ ] **Step 1: 그날 사용량 확인**

Run: `py -m migration.mysql.d1_usage --max 1500000`
Expected: 종료 코드 0. 2 면 그날은 멈추고 다음 날 합니다.

- [ ] **Step 2-A: D1 유료라면 한 번에 받기**

```bash
SNAP=~/.bstats/snapshots/d1_$(date -u +%Y%m%d).db
py migration/d1_to_sqlite.py --all-tables --count-check d1 --out "$SNAP"
```

Expected: 마지막에 `만든 DB: …(약 1,500MB 이상)`. 샤드 6개 모두 행 수 확인 통과.

- [ ] **Step 2-B: 무료라면 이틀에 나눠 받기**

첫날(공용 표 + 오래된 샤드 3개, 약 200만 행):

```bash
SNAP=~/.bstats/snapshots/d1_$(date -u +%Y%m%d).db
py migration/d1_to_sqlite.py --all-tables --shards DB_2008_2011,DB_2012_2014,DB_2015_2017 \
  --count-check meta --out "$SNAP"
echo "$SNAP" > ~/.bstats/snapshots/CURRENT
```

다음 날 09:00 KST 이후, Step 1 을 다시 통과한 뒤(나머지 샤드 3개, 약 210만 행):

```bash
SNAP=$(cat ~/.bstats/snapshots/CURRENT)
py migration/d1_to_sqlite.py --tables play_by_play --shards DB_2018_2020,DB_2021_2023,DB_2024_2026 \
  --count-check meta --append --out "$SNAP"
```

`meta` 확인에서 "행 수를 확인하지 못했습니다" 가 나오면 그 샤드에 메타가 없는 것입니다(로드맵 0-2). 멈추지 않고 계속합니다. 이틀 사이에 바뀐 공용 표·최근 경기는 5단계 전환 때 마지막 변경분으로 맞춥니다.

- [ ] **Step 3: 스냅샷 점검**

```bash
SNAP=$(ls -t ~/.bstats/snapshots/d1_*.db | head -1)
py - "$SNAP" <<'EOF'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
print("표", con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0])
print("play_by_play", con.execute(
    "SELECT COUNT(*), MIN(game_date), MAX(game_date) FROM play_by_play").fetchone())
for name, in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    print("  %-34s %s" % (name, format(con.execute('SELECT COUNT(*) FROM "%s"' % name).fetchone()[0], ",")))
EOF
```

Expected: `play_by_play` 약 3,980,000행 이상, 최소 `game_date` 2008xxxx, 최대는 받은 날 전날 근처. `players`·`games`·`kbo_roster`·`kbo_roster_moves`·`meta_table_counts` 가 목록에 있음.

- [ ] **Step 4: 결과를 evan 에게 보고**

표 수, `play_by_play` 행 수와 날짜 범위, 걸린 시간, 그날 D1 사용량(`d1_usage` 다시 실행)을 알립니다. 커밋할 것은 없습니다.

---

### Task 4: 타입 규칙 (프로파일, 값 종류, MySQL 타입, 값 정리)

**Files:**
- Create: `migration/mysql/typemap.py`
- Test: `tests/test_mysql_typemap.py`

**Interfaces:**
- Produces: `new_profile() -> dict`, `observe_text(p, s, n=1)`, `profile_column(con, table, column) -> dict`, `column_kind(column, decl, p) -> str`(`'int'|'double'|'date'|'datetime'|'blob'|'text'`), `mysql_type(kind, p, is_key=False, column="") -> str`, `normalize(value, kind)`, 상수 `EMPTY_TEXT`, `NUM_LIKE`, `PLAYER_ID`.
- 프로파일 키: `nonnull, ints, reals, blobs, texts, int_texts, num_texts, dotzero, empties, dates, datetimes, max_len, int_min, int_max`.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_mysql_typemap.py`

```python
import sqlite3

import pytest

from migration.mysql import typemap as tm


def _profile(values, decl="TEXT", column="c"):
    con = sqlite3.connect(":memory:")
    con.execute('CREATE TABLE t ("%s" %s)' % (column, decl))
    con.executemany("INSERT INTO t VALUES (?)", [(v,) for v in values])
    return tm.profile_column(con, "t", column)


def test_profile_counts_empty_text_and_float_style_ids():
    p = _profile(["78513.0", "12", "", None], column="batter_ID")
    assert p["nonnull"] == 3
    assert p["int_texts"] == 2 and p["dotzero"] == 1 and p["empties"] == 1
    assert (p["int_min"], p["int_max"]) == (12, 78513)


def test_player_id_text_column_becomes_unsigned_int():
    p = _profile(["78513.0", "12", ""], column="batter_ID")
    kind = tm.column_kind("batter_ID", "TEXT", p)
    assert kind == "int"
    assert tm.mysql_type(kind, p, column="batter_ID") == "INT UNSIGNED"


def test_player_id_with_names_stays_text():
    p = _profile(["78513", "홍길동"], column="pos_1_id")
    assert tm.column_kind("pos_1_id", "TEXT", p) == "text"


def test_real_column_with_empty_strings_stays_double():
    p = _profile([1.5, "", 2.0], decl="REAL", column="px")
    assert tm.column_kind("px", "REAL", p) == "double"


def test_back_number_text_keeps_leading_zeros():
    p = _profile(["00", "0", "12"], column="back_number")
    kind = tm.column_kind("back_number", "TEXT", p)
    assert kind == "text"
    assert tm.normalize("00", kind) == "00"


def test_game_date_declared_date_but_stored_as_int_stays_int():
    p = _profile([20260930, 20260929], decl="DATE", column="game_date")
    assert tm.column_kind("game_date", "DATE", p) == "int"


def test_text_dates_become_date_and_datetimes_become_datetime():
    p = _profile(["2026-09-30", "2026-09-28"], column="move_date")
    assert tm.column_kind("move_date", "TEXT", p) == "date"
    p = _profile(["2026-09-30 07:31:00"], column="updated_at")
    assert tm.column_kind("updated_at", "TEXT", p) == "datetime"


def test_minutes_only_timestamps_stay_text():
    p = _profile(["2026-10-01 07:31"], column="last_run_at")
    assert tm.column_kind("last_run_at", "TEXT", p) == "text"


def test_int_column_with_other_values_falls_back():
    p = _profile([1, "2.5"], decl="INTEGER", column="n")
    assert tm.column_kind("n", "INTEGER", p) == "double"
    p = _profile([1, "abc"], decl="INTEGER", column="n")
    assert tm.column_kind("n", "INTEGER", p) == "text"


def test_blob_column():
    p = _profile([b"\x89PNG"], decl="BLOB", column="img")
    assert tm.column_kind("img", "BLOB", p) == "blob"
    assert tm.mysql_type("blob", p) == "MEDIUMBLOB"


def test_varchar_steps_and_key_limit():
    p = tm.new_profile()
    p["max_len"] = 5
    assert tm.mysql_type("text", p) == "VARCHAR(16)"
    p["max_len"] = 100
    assert tm.mysql_type("text", p) == "VARCHAR(255)"
    p["max_len"] = 600
    assert tm.mysql_type("text", p) == "TEXT"
    assert tm.mysql_type("text", p, is_key=True) == "VARCHAR(768)"
    p["max_len"] = 900
    with pytest.raises(ValueError):
        tm.mysql_type("text", p, is_key=True, column="k")


def test_bigint_when_out_of_int32():
    p = tm.new_profile()
    p["int_min"], p["int_max"] = 0, 3_000_000_000
    assert tm.mysql_type("int", p, column="n") == "BIGINT"


@pytest.mark.parametrize("value,kind,expected", [
    ("78513.0", "int", 78513), ("", "int", None), ("-", "double", None),
    (" 1.25 ", "double", 1.25), (3.0, "int", 3), (7, "text", "7"),
    ("2026-09-30", "date", "2026-09-30"), (None, "int", None),
    (b"ab", "blob", b"ab"),
])
def test_normalize(value, kind, expected):
    assert tm.normalize(value, kind) == expected


def test_normalize_rejects_non_numbers():
    with pytest.raises(ValueError):
        tm.normalize("abc", "int")
    with pytest.raises(ValueError):
        tm.normalize(2.5, "int")
```

- [ ] **Step 2: 실패 확인**

Run: `py -m pytest tests/test_mysql_typemap.py -v`
Expected: FAIL (`No module named 'migration.mysql.typemap'`)

- [ ] **Step 3: 구현**

`migration/mysql/typemap.py`

```python
# -*- coding: utf-8 -*-
"""SQLite 열 하나를 MySQL 타입으로 옮기는 규칙입니다.

D1(SQLite)은 선언과 다른 타입의 값도 받습니다. 그래서 같은 열에 숫자와
빈 문자열이 섞여 있습니다(플레이 기록 숫자 열 18개에 약 4%가 ''). 선수
ID 일부는 '78513.0' 처럼 소수점이 붙은 글자입니다. MySQL 엄격 모드는
그런 값을 거부합니다. 여기서 열마다 실제 값을 훑어(프로파일) 타입을
고르고, 옮길 때 값을 고칩니다.

규칙의 요지(로드맵 1단계와 같습니다):
- 숫자로 선언된 열의 '' 와 '-' 는 NULL 입니다.
- 선수 ID 열은 값이 모두 정수 모양이면 INT UNSIGNED 입니다.
- 글자로 선언된 열은 글자로 둡니다('00' 과 '0' 을 지킵니다). 다만 값이
  모두 YYYY-MM-DD 면 DATE, YYYY-MM-DD HH:MM:SS 면 DATETIME 입니다.
- game_date 처럼 DATE 로 선언됐지만 YYYYMMDD 정수인 열은 INT 입니다.
"""
import re

EMPTY_TEXT = {"", "-"}
INT_LIKE = re.compile(r"^[+-]?\d+(\.0+)?$")
NUM_LIKE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")
DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_TIME = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
PLAYER_ID = re.compile(
    r"^(player_id|batter_id|pitcher_id|on_[123]b_id|pos_[1-9]_id)$",
    re.IGNORECASE)
VARCHAR_STEPS = (16, 32, 64, 128, 255, 512, 1024)
KEY_VARCHAR_MAX = 768          # utf8mb4 인덱스 한도 3072바이트 / 4바이트
KEY_MAX_CHARS = 600            # 이보다 긴 키는 설계를 다시 봐야 하는 신호입니다
INT32 = (-2 ** 31, 2 ** 31 - 1)
BLOB_MEDIUM_MAX = 16 * 1024 * 1024 - 1
TEXT_MAX_CHARS = 16000         # TEXT 65,535바이트 / utf8mb4 4바이트, 여유를 둠


def new_profile():
    return {"nonnull": 0, "ints": 0, "reals": 0, "blobs": 0, "texts": 0,
            "int_texts": 0, "num_texts": 0, "dotzero": 0, "empties": 0,
            "dates": 0, "datetimes": 0, "max_len": 0,
            "int_min": None, "int_max": None}


def _widen(p, v):
    p["int_min"] = v if p["int_min"] is None else min(p["int_min"], v)
    p["int_max"] = v if p["int_max"] is None else max(p["int_max"], v)


def observe_text(p, s, n=1):
    """글자 값 하나(가 n 번)를 프로파일에 반영합니다. nonnull 은 그대로 둡니다."""
    t = s.strip()
    if t in EMPTY_TEXT:
        p["empties"] += n
    elif INT_LIKE.match(t):
        p["int_texts"] += n
        if "." in t:
            p["dotzero"] += n
        _widen(p, int(t.split(".")[0]))
    elif NUM_LIKE.match(t):
        p["num_texts"] += n
    else:
        p["texts"] += n
        if DATE_ONLY.match(t):
            p["dates"] += n
        elif DATE_TIME.match(t):
            p["datetimes"] += n


def profile_column(con, table, column):
    """SQLite 스냅샷에서 열 하나의 프로파일을 만듭니다.

    큰 표(플레이 기록 약 400만 행)도 감당하도록 개수·길이는 SQL 로 세고,
    글자 값은 서로 다른 값만 꺼내 분류합니다.
    """
    c, t = '"%s"' % column, '"%s"' % table
    row = con.execute(
        "SELECT COUNT({c}), "
        "SUM(typeof({c})='integer'), SUM(typeof({c})='real'), "
        "SUM(typeof({c})='blob'), "
        "MIN(CASE WHEN typeof({c})='integer' THEN {c} END), "
        "MAX(CASE WHEN typeof({c})='integer' THEN {c} END), "
        "MAX(CASE WHEN typeof({c})='blob' THEN length({c}) "
        "         WHEN {c} IS NOT NULL THEN length(CAST({c} AS TEXT)) END) "
        "FROM {t}".format(c=c, t=t)).fetchone()
    p = new_profile()
    p["nonnull"] = row[0]
    p["ints"], p["reals"], p["blobs"] = row[1] or 0, row[2] or 0, row[3] or 0
    if row[4] is not None:
        _widen(p, row[4])
        _widen(p, row[5])
    p["max_len"] = row[6] or 0
    for value, n in con.execute(
            "SELECT {c}, COUNT(*) FROM {t} WHERE typeof({c})='text' "
            "GROUP BY {c}".format(c=c, t=t)):
        observe_text(p, value, n)
    return p


def _date_kind(p):
    """값이 전부 날짜(또는 일시) 모양 글자면 그 종류입니다."""
    if (p["texts"] == 0 or p["ints"] or p["reals"] or p["blobs"]
            or p["int_texts"] or p["num_texts"] or p["empties"]):
        return None
    if p["dates"] == p["texts"]:
        return "date"
    if p["datetimes"] == p["texts"]:
        return "datetime"
    return None


def column_kind(column, decl, p):
    """'int' 'double' 'date' 'datetime' 'blob' 'text' 중 하나를 고릅니다."""
    d = (decl or "").upper()
    # 빈 문자열은 NULL 로 바뀌므로 숫자 열을 막지 않습니다.
    numeric_only = p["texts"] == 0 and p["blobs"] == 0
    integral = numeric_only and p["reals"] == 0 and p["num_texts"] == 0
    if PLAYER_ID.match(column):
        return "int" if integral else "text"
    if "BLOB" in d:
        return "blob"
    if "INT" in d:
        if integral:
            return "int"
        return "double" if numeric_only else "text"
    if any(k in d for k in ("REAL", "FLOA", "DOUB", "NUMERIC", "DECIMAL")):
        return "double" if numeric_only else "text"
    if "DATE" in d or "TIME" in d:
        # game_date 는 DATE 로 선언됐지만 YYYYMMDD 정수로 쌓고 비교합니다.
        if integral and (p["ints"] or p["int_texts"]):
            return "int"
        return _date_kind(p) or "text"
    if not d:
        if p["blobs"] and p["blobs"] == p["nonnull"]:
            return "blob"
        if numeric_only and (p["ints"] or p["reals"] or p["int_texts"]
                             or p["num_texts"]):
            return "int" if integral else "double"
    # 글자로 선언된 열은 글자로 둡니다. back_number 의 '00' 과 '0' 을 지킵니다.
    return _date_kind(p) or "text"


def mysql_type(kind, p, is_key=False, column=""):
    """값 종류와 프로파일로 MySQL 열 타입을 고릅니다."""
    if kind == "int":
        lo, hi = p["int_min"], p["int_max"]
        if PLAYER_ID.match(column) and (lo is None or lo >= 0):
            return "INT UNSIGNED"
        if lo is None or (INT32[0] <= lo and hi <= INT32[1]):
            return "INT"
        return "BIGINT"
    if kind == "double":
        return "DOUBLE"
    if kind == "date":
        return "DATE"
    if kind == "datetime":
        return "DATETIME"
    if kind == "blob":
        return "MEDIUMBLOB" if p["max_len"] <= BLOB_MEDIUM_MAX else "LONGBLOB"
    want = max(16, p["max_len"] * 2)
    for step in VARCHAR_STEPS:
        if step >= want:
            if is_key and step > KEY_VARCHAR_MAX:
                break
            return "VARCHAR(%d)" % step
    if is_key:
        if p["max_len"] <= KEY_MAX_CHARS:
            return "VARCHAR(%d)" % KEY_VARCHAR_MAX
        raise ValueError("키 열 %s 가 너무 깁니다(%d자)" % (column, p["max_len"]))
    return "TEXT" if p["max_len"] < TEXT_MAX_CHARS else "MEDIUMTEXT"


def normalize(value, kind):
    """스냅샷 값 하나를 MySQL 에 넣을 값으로 바꿉니다. 못 바꾸면 ValueError."""
    if value is None:
        return None
    if kind == "text":
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value if isinstance(value, str) else str(value)
    if kind == "blob":
        return value if isinstance(value, bytes) else str(value).encode("utf-8")
    if isinstance(value, bytes):
        raise ValueError("바이트 값을 %s 로 바꿀 수 없습니다" % kind)
    if isinstance(value, str):
        t = value.strip()
        if t in EMPTY_TEXT:
            return None
        if kind == "int":
            if not INT_LIKE.match(t):
                raise ValueError("정수가 아닙니다: %r" % value)
            return int(t.split(".")[0])
        if kind == "double":
            if not NUM_LIKE.match(t):
                raise ValueError("숫자가 아닙니다: %r" % value)
            return float(t)
        return t                    # date / datetime: 프로파일에서 모양을 확인했습니다
    if kind == "int":
        if isinstance(value, float):
            if not value.is_integer():
                raise ValueError("정수가 아닙니다: %r" % value)
            return int(value)
        return value
    if kind == "double":
        return float(value)
    raise ValueError("%s 열에 숫자 %r 가 있습니다" % (kind, value))
```

키 열 규칙: 키 열은 실제 최대 `KEY_MAX_CHARS`(600)자까지 `VARCHAR(768)` 로 받고, 그보다 길면 멈춥니다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `py -m pytest tests/test_mysql_typemap.py -v`
Expected: 전부 passed

- [ ] **Step 5: 커밋(evan 확인 후)**

```bash
git add migration/mysql/typemap.py tests/test_mysql_typemap.py
git commit -m "feat(mysql): 열 프로파일과 타입·값 정리 규칙" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: 스키마 생성기와 검토

**Files:**
- Create: `migration/mysql/ddl.py`
- Test: `tests/test_mysql_ddl.py`
- 생성물: `migration/mysql/schema.sql`, `migration/mysql/schema_post.sql`, `migration/mysql/schema_types.json`, `docs/mysql-migration/schema-report.md`

**Interfaces:**
- Consumes: `typemap.profile_column`, `typemap.column_kind`, `typemap.mysql_type`, `typemap.NUM_LIKE`, `tables.is_migrated`.
- Produces: `ddl.q(name) -> str`(백틱), `ddl.split_sql(text) -> list[str]`, `ddl.default_clause(default, kind, mtype) -> (str, str|None)`, `ddl.build(snapshot) -> (creates, posts, types, notes)`, 상수 `ddl.OUT_DIR`, `ddl.ROOT`, `ddl.RENUMBER = {"play_by_play": "pbp_id"}`.
- `schema_types.json` 모양: `{"표": {"columns": [["열", "종류"], …], "renumber": "pbp_id" 또는 null}}`.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_mysql_ddl.py`

```python
import json
import sqlite3

from migration.mysql import ddl


def _snapshot(tmp_path):
    p = tmp_path / "snap.db"
    con = sqlite3.connect(str(p))
    con.executescript("""
        CREATE TABLE teams (team_id TEXT PRIMARY KEY, team_name TEXT NOT NULL);
        CREATE TABLE players (
            player_id TEXT PRIMARY KEY, player_name TEXT NOT NULL,
            team_id TEXT, back_number INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams(team_id));
        CREATE TABLE play_by_play (pbp_id INTEGER, batter_ID TEXT, px REAL, gameID TEXT);
        CREATE INDEX idx_pbp_game ON play_by_play(gameID);
        CREATE TABLE meta (k INTEGER PRIMARY KEY, v TEXT DEFAULT '1군');
        CREATE TABLE futures (code TEXT UNIQUE, n INTEGER);
        CREATE TABLE wrc_bak (a INTEGER);
    """)
    con.execute("INSERT INTO teams VALUES ('KIA', 'KIA 타이거즈')")
    con.execute("INSERT INTO players (player_id, player_name, team_id, back_number) "
                "VALUES ('62404', '구자욱', 'KIA', 7)")
    con.executemany("INSERT INTO play_by_play VALUES (?,?,?,?)",
                    [(1, "78513.0", 1.5, "G1"), (1, "12", "", "G1")])
    con.execute("INSERT INTO meta (v) VALUES ('2군')")
    con.execute("INSERT INTO futures VALUES ('SS', 1)")
    con.commit()
    con.close()
    return p


def test_build_skips_backup_tables_and_renumbers_pbp(tmp_path):
    creates, posts, types, notes = ddl.build(_snapshot(tmp_path))
    assert set(types) == {"teams", "players", "play_by_play", "meta", "futures"}
    pbp = next(c for c in creates if c.startswith("CREATE TABLE `play_by_play`"))
    assert "`pbp_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT" in pbp
    assert "PRIMARY KEY (`pbp_id`)" in pbp
    assert "`batter_ID` INT UNSIGNED" in pbp
    assert "`px` DOUBLE" in pbp
    assert types["play_by_play"]["renumber"] == "pbp_id"


def test_build_keeps_keys_defaults_and_foreign_keys(tmp_path):
    creates, posts, types, notes = ddl.build(_snapshot(tmp_path))
    players = next(c for c in creates if c.startswith("CREATE TABLE `players`"))
    assert "`player_id` INT UNSIGNED NOT NULL" in players
    assert "`created_at` DATETIME DEFAULT CURRENT_TIMESTAMP" in players
    assert "`back_number` INT" in players
    meta = next(c for c in creates if c.startswith("CREATE TABLE `meta`"))
    assert "`k` INT NOT NULL AUTO_INCREMENT" in meta
    assert "DEFAULT '1군'" in meta
    assert ("ALTER TABLE `players` ADD CONSTRAINT `fk_players_team_id` "
            "FOREIGN KEY (`team_id`) REFERENCES `teams` (`team_id`);") in posts
    assert "CREATE INDEX `idx_pbp_game` ON `play_by_play` (`gameID`);" in posts
    assert "CREATE UNIQUE INDEX `uq_futures_1` ON `futures` (`code`);" in posts


def test_notes_explain_value_fixes(tmp_path):
    _, _, _, notes = ddl.build(_snapshot(tmp_path))
    joined = "\n".join(notes)
    assert "play_by_play.batter_ID" in joined
    assert "소수점 표기 1개 → 정수" in joined
    assert "play_by_play.px: 빈 값 1개 → NULL" in joined


def test_split_sql():
    text = "CREATE TABLE `a` (\n  `x` INT\n);\n\nCREATE TABLE `b` (`y` INT);\n"
    assert ddl.split_sql(text) == ["CREATE TABLE `a` (\n  `x` INT\n)",
                                   "CREATE TABLE `b` (`y` INT)"]


def test_default_clause():
    assert ddl.default_clause("CURRENT_TIMESTAMP", "datetime", "DATETIME") == \
        (" DEFAULT CURRENT_TIMESTAMP", None)
    clause, why = ddl.default_clause("CURRENT_TIMESTAMP", "text", "VARCHAR(32)")
    assert clause == "" and "뺐습니다" in why
    assert ddl.default_clause("0", "int", "INT") == (" DEFAULT 0", None)
    assert ddl.default_clause("'x'", "text", "TEXT") == (" DEFAULT ('x')", None)
    assert ddl.default_clause(None, "int", "INT") == ("", None)


def test_main_writes_files(tmp_path, monkeypatch):
    out = tmp_path / "out"
    monkeypatch.setattr(ddl, "OUT_DIR", out)
    monkeypatch.setattr(ddl, "REPORT", tmp_path / "report.md")
    monkeypatch.setattr("sys.argv", ["ddl", "--snapshot", str(_snapshot(tmp_path))])
    assert ddl.main() == 0
    types = json.loads((out / "schema_types.json").read_text(encoding="utf-8"))
    assert types["play_by_play"]["columns"][0] == ["pbp_id", "int"]
    assert ddl.split_sql((out / "schema.sql").read_text(encoding="utf-8"))
    assert "# MySQL 스키마 보고" in (tmp_path / "report.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: 실패 확인**

Run: `py -m pytest tests/test_mysql_ddl.py -v`
Expected: FAIL (`No module named 'migration.mysql.ddl'`)

- [ ] **Step 3: 구현**

`migration/mysql/ddl.py`

```python
# -*- coding: utf-8 -*-
"""SQLite 스냅샷을 보고 MySQL 스키마를 만듭니다.

    py -m migration.mysql.ddl --snapshot ~/.bstats/snapshots/d1_20261002.db

만드는 파일(사람이 검토하고 커밋합니다):
    migration/mysql/schema.sql         표 만들기(기본키만)
    migration/mysql/schema_post.sql    인덱스·외래키(데이터를 넣은 뒤 적용)
    migration/mysql/schema_types.json  열마다 값 종류(적재·검증이 씁니다)
    docs/mysql-migration/schema-report.md  고른 타입과 값 처리 메모

인덱스와 외래키를 따로 두는 이유: 400만 행을 넣을 때 인덱스가 있으면
줄마다 인덱스를 고칩니다. 다 넣고 한 번에 만드는 편이 빠릅니다.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

from migration.mysql import typemap as tm
from migration.mysql.tables import is_migrated

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "migration" / "mysql"
REPORT = ROOT / "docs" / "mysql-migration" / "schema-report.md"

# 새로 번호를 매기는 표입니다. 샤드마다 따로 붙인 pbp_id 가 겹칠 수
# 있습니다. 시즌 순 → 샤드 안 원래 번호 순으로 넣어 경기 안 순서를 지킵니다.
RENUMBER = {"play_by_play": "pbp_id"}
NAME_MAX = 64
NOW_DEFAULTS = {"CURRENT_TIMESTAMP", "(CURRENT_TIMESTAMP)",
                "DATETIME('NOW')", "(DATETIME('NOW'))"}


def q(name):
    """MySQL 식별자로 감쌉니다."""
    return "`%s`" % name.replace("`", "``")


def split_sql(text):
    """이 생성기가 만든 파일을 문장으로 나눕니다(문자열 안 ';\\n' 은 없다고 봅니다)."""
    return [s.strip().rstrip(";").strip() for s in text.split(";\n") if s.strip()]


def read_table(con, table):
    """표 하나의 열·기본키·외래키·인덱스를 PRAGMA 로 읽습니다."""
    cols = [{"name": r[1], "decl": r[2] or "", "notnull": bool(r[3]),
             "default": r[4], "pk": r[5]}
            for r in con.execute('PRAGMA table_info("%s")' % table)]
    pk = [c["name"] for c in sorted((c for c in cols if c["pk"]),
                                    key=lambda c: c["pk"])]
    groups = {}
    for r in con.execute('PRAGMA foreign_key_list("%s")' % table):
        groups.setdefault(r[0], []).append(r)
    fks = []
    for rows in groups.values():
        if len(rows) == 1:
            fks.append({"column": rows[0][3], "ref_table": rows[0][2],
                        "ref_column": rows[0][4]})
    indexes = []
    for r in con.execute('PRAGMA index_list("%s")' % table):
        name, unique, origin = r[1], bool(r[2]), r[3]
        if origin == "pk":
            continue
        icols = [x[2] for x in con.execute('PRAGMA index_info("%s")' % name)]
        indexes.append({"name": name, "unique": unique, "columns": icols})
    return {"name": table, "columns": cols, "pk": pk, "fks": fks,
            "indexes": indexes, "multi_fk": [k for k, v in groups.items() if len(v) > 1]}


def key_columns(tables):
    """기본키·외래키(양쪽)·인덱스에 쓰이는 (표, 열) 입니다."""
    keys = set()
    for t in tables.values():
        keys.update((t["name"], c) for c in t["pk"])
        for fk in t["fks"]:
            keys.add((t["name"], fk["column"]))
            keys.add((fk["ref_table"], fk["ref_column"]))
        for ix in t["indexes"]:
            keys.update((t["name"], c) for c in ix["columns"])
    return keys


def default_clause(default, kind, mtype):
    """SQLite 기본값을 MySQL 로 옮깁니다. (절, 뺀 이유 또는 None)."""
    if default is None:
        return "", None
    d = default.strip()
    u = d.upper().replace(" ", "")
    if u in NOW_DEFAULTS:
        if kind == "datetime":
            return " DEFAULT CURRENT_TIMESTAMP", None
        return "", "현재 시각 기본값은 DATETIME 열에만 둘 수 있어 뺐습니다"
    if u == "NULL":
        return " DEFAULT NULL", None
    if kind in ("int", "double") and tm.NUM_LIKE.match(d):
        return " DEFAULT %s" % d, None
    if len(d) >= 2 and d[0] == d[-1] == "'":
        if kind in ("int", "double", "blob"):
            return "", "글자 기본값 %s 가 이 열에 맞지 않아 뺐습니다" % d
        return (" DEFAULT (%s)" if "TEXT" in mtype else " DEFAULT %s") % d, None
    return "", "알 수 없는 기본값 %s 를 뺐습니다" % d


def _category(decl):
    d = (decl or "").upper()
    if "INT" in d:
        return "int"
    if any(k in d for k in ("REAL", "FLOA", "DOUB", "NUMERIC", "DECIMAL")):
        return "double"
    if "BLOB" in d:
        return "blob"
    if "DATE" in d or "TIME" in d:
        return "date"
    return "text" if d else None


def _type_changed(decl, kind):
    cat = _category(decl)
    if cat is None:
        return True
    if cat == "date":
        return kind not in ("date", "datetime")
    return cat != kind


def plan_table(con, t, keys):
    """표 하나의 CREATE TABLE 과 열 종류, 보고 메모를 만듭니다."""
    name = t["name"]
    renumber = RENUMBER.get(name)
    lines, columns, notes = [], [], []
    for c in t["columns"]:
        col = c["name"]
        p = tm.profile_column(con, name, col)
        if col == renumber:
            kind = "int"
            lines.append("  %s BIGINT UNSIGNED NOT NULL AUTO_INCREMENT" % q(col))
            columns.append([col, kind])
            continue
        kind = tm.column_kind(col, c["decl"], p)
        mtype = tm.mysql_type(kind, p, is_key=(name, col) in keys, column=col)
        notnull = c["notnull"] or col in t["pk"]
        dflt, why = default_clause(c["default"], kind, mtype)
        if why:
            notes.append("%s.%s: %s" % (name, col, why))
        auto = ""
        if t["pk"] == [col] and c["decl"].upper() == "INTEGER":
            auto = " AUTO_INCREMENT"   # SQLite rowid 처럼 번호를 이어 붙입니다
        lines.append("  %s %s%s%s%s" % (q(col), mtype,
                                        " NOT NULL" if notnull else "", dflt, auto))
        columns.append([col, kind])
        if _type_changed(c["decl"], kind):
            notes.append("%s.%s: 선언 %s → %s" % (name, col, c["decl"] or "(없음)", mtype))
        if kind == "int" and p["dotzero"]:
            notes.append("%s.%s: 소수점 표기 %s개 → 정수"
                         % (name, col, format(p["dotzero"], ",")))
        if kind not in ("text", "blob") and p["empties"]:
            notes.append("%s.%s: 빈 값 %s개 → NULL"
                         % (name, col, format(p["empties"], ",")))
    pk = [renumber] if renumber else t["pk"]
    if pk:
        lines.append("  PRIMARY KEY (%s)" % ", ".join(q(c) for c in pk))
    else:
        notes.append("%s: 기본키가 없습니다(원본과 같음)" % name)
    for fid in t["multi_fk"]:
        notes.append("%s: 여러 열 외래키(%s)는 옮기지 않았습니다" % (name, fid))
    create = ("CREATE TABLE %s (\n%s\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 "
              "COLLATE=utf8mb4_0900_ai_ci;" % (q(name), ",\n".join(lines)))
    return {"create": create, "columns": columns, "renumber": renumber, "notes": notes}


def post_statements(t):
    """데이터를 넣은 뒤 만들 인덱스와 외래키입니다."""
    name = t["name"]
    out = []
    for i, ix in enumerate(t["indexes"], start=1):
        if name in RENUMBER and ix["columns"] == [RENUMBER[name]]:
            continue
        ixname = ix["name"]
        if ixname.startswith("sqlite_autoindex_"):
            ixname = "uq_%s_%d" % (name, i)
        out.append("CREATE %s %s ON %s (%s);" % (
            "UNIQUE INDEX" if ix["unique"] else "INDEX", q(ixname[:NAME_MAX]),
            q(name), ", ".join(q(c) for c in ix["columns"])))
    for fk in t["fks"]:
        fname = ("fk_%s_%s" % (name, fk["column"]))[:NAME_MAX]
        out.append("ALTER TABLE %s ADD CONSTRAINT %s FOREIGN KEY (%s) "
                   "REFERENCES %s (%s);" % (q(name), q(fname), q(fk["column"]),
                                            q(fk["ref_table"]), q(fk["ref_column"])))
    return out


def build(snapshot):
    """스냅샷 하나에서 (CREATE 목록, 후처리 목록, 열 종류, 메모) 를 만듭니다."""
    con = sqlite3.connect(Path(snapshot).resolve().as_uri() + "?mode=ro", uri=True)
    names = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        if is_migrated(r[0])]
    tables = {n: read_table(con, n) for n in names}
    notes = []
    for n in names:
        kept = []
        for fk in tables[n]["fks"]:
            if fk["ref_table"] in tables:
                kept.append(fk)
            else:
                notes.append("%s.%s: 참조 표 %s 를 옮기지 않아 외래키를 뺐습니다"
                             % (n, fk["column"], fk["ref_table"]))
        tables[n]["fks"] = kept
    keys = key_columns(tables)
    creates, posts, types = [], [], {}
    for n in names:
        print("   스키마: %s" % n, flush=True)
        plan = plan_table(con, tables[n], keys)
        creates.append(plan["create"])
        types[n] = {"columns": plan["columns"], "renumber": plan["renumber"]}
        notes.extend(plan["notes"])
        posts.extend(post_statements(tables[n]))
    con.close()
    return creates, posts, types, notes


def render_report(snapshot, types, notes):
    lines = ["# MySQL 스키마 보고", "",
             "스냅샷: `%s`" % Path(snapshot).name, "",
             "| 표 | 열 수 | 새 번호 |", "|---|---|---|"]
    for n, spec in types.items():
        lines.append("| %s | %d | %s |" % (n, len(spec["columns"]),
                                           spec["renumber"] or ""))
    lines += ["", "## 타입·값 처리 메모", ""] + ["- " + x for x in notes] + [""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    args = ap.parse_args()
    creates, posts, types, notes = build(args.snapshot)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "schema.sql").write_text(
        "\n\n".join(creates) + "\n", encoding="utf-8", newline="\n")
    (OUT_DIR / "schema_post.sql").write_text(
        "\n".join(posts) + "\n", encoding="utf-8", newline="\n")
    (OUT_DIR / "schema_types.json").write_text(
        json.dumps(types, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(render_report(args.snapshot, types, notes),
                      encoding="utf-8", newline="\n")
    print("표 %d개, 후처리 %d문, 메모 %d줄" % (len(creates), len(posts), len(notes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `py -m pytest tests/test_mysql_ddl.py tests/test_mysql_typemap.py -v`
Expected: 전부 passed

- [ ] **Step 5: 실제 스냅샷으로 스키마 만들기**

```bash
SNAP=$(ls -t ~/.bstats/snapshots/d1_*.db | head -1)
py -m migration.mysql.ddl --snapshot "$SNAP"
```

Expected: `표 N개, 후처리 M문, 메모 K줄`. 플레이 기록 열 74개를 훑으므로 10분 안팎 걸립니다.

- [ ] **Step 6: 스키마를 MySQL 에 시험 적용(빈 표)**

```bash
py - <<'EOF'
from migration.mysql import conn
from migration.mysql.ddl import OUT_DIR, split_sql
con = conn.connect()
with con.cursor() as cur:
    for stmt in split_sql((OUT_DIR / "schema.sql").read_text(encoding="utf-8")):
        cur.execute(stmt)
    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='bstats'")
    print("만든 표", cur.fetchone()[0])
    # 인덱스와 외래키도 시험 적용합니다(크기 한도 오류를 조기에 잡습니다).
    post_stmts = split_sql((OUT_DIR / "schema_post.sql").read_text(encoding="utf-8"))
    for stmt in post_stmts:
        cur.execute(stmt)
    print("후처리 %d문 적용" % len(post_stmts))
con.commit()
con.close()
EOF
```

Expected: `만든 표 N`과 `후처리 M문 적용` 모두 나타나야 합니다(인덱스·외래키 오류를 배포 전에 잡습니다). 오류가 나면 그 문장을 고칠 규칙을 Task 4·5 에 테스트와 함께 더하고 Step 5 부터 다시 합니다. 빈 표는 Task 6 의 `--fresh` 가 지우고 다시 만듭니다.

- [ ] **Step 7: evan 검토**

`docs/mysql-migration/schema-report.md` 의 메모(타입이 바뀐 열, 빈 값 → NULL 건수, 소수점 ID 건수, 기본키 없는 표, 뺀 기본값·외래키)를 evan 에게 요약해 보여 주고 승인받습니다. 규칙을 바꾸자는 의견이 나오면 Task 4·5 로 돌아갑니다.

- [ ] **Step 8: 커밋(evan 확인 후)**

```bash
git add migration/mysql/ddl.py tests/test_mysql_ddl.py migration/mysql/schema.sql \
  migration/mysql/schema_post.sql migration/mysql/schema_types.json \
  docs/mysql-migration/schema-report.md
git commit -m "feat(mysql): 스냅샷 기반 MySQL 스키마 생성기와 첫 스키마" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: 적재기와 첫 적재

**Files:**
- Create: `migration/mysql/load.py`
- Test: `tests/test_mysql_load.py`
- 생성물: `docs/mysql-migration/load-report.md`

**Interfaces:**
- Consumes: `conn.connect`, `typemap.normalize`, `ddl.OUT_DIR`, `ddl.ROOT`, `ddl.q`, `ddl.split_sql`, `schema_types.json`.
- Produces: `load.insert_sql(table, columns) -> str`, `load.convert_row(row, kinds, names, table, fixes) -> tuple`, `load.load_table(sq, my, table, spec, fixes, batch=2000) -> int`, `load.orphan_queries(post_sql) -> list[(label, sql)]`, CLI `py -m migration.mysql.load --snapshot … [--fresh] [--tables …]`.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_mysql_load.py`

```python
import collections
import sqlite3

import pytest

from migration.mysql import load


class FakeCursor:
    def __init__(self, log):
        self.log = log

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def executemany(self, sql, rows):
        self.log.append((sql, list(rows)))


class FakeConn:
    def __init__(self):
        self.log = []
        self.commits = 0

    def cursor(self):
        return FakeCursor(self.log)

    def commit(self):
        self.commits += 1


def test_insert_sql_quotes_names():
    assert load.insert_sql("t", ["a", "rank"]) == \
        "INSERT INTO `t` (`a`, `rank`) VALUES (%s, %s)"


def test_convert_row_counts_fixes_and_names_bad_cells():
    fixes = collections.Counter()
    row = load.convert_row(("78513.0", "", "가"), ["int", "double", "text"],
                           ["batter_ID", "px", "nm"], "pbp", fixes)
    assert row == (78513, None, "가")
    assert fixes[("pbp", "batter_ID", "소수점 표기 → 정수")] == 1
    assert fixes[("pbp", "px", "빈 값 → NULL")] == 1
    with pytest.raises(ValueError, match="pbp.batter_ID"):
        load.convert_row(("abc",), ["int"], ["batter_ID"], "pbp", fixes)


def test_load_table_skips_renumbered_column_and_keeps_rowid_order():
    sq = sqlite3.connect(":memory:")
    sq.execute('CREATE TABLE play_by_play (pbp_id INTEGER, batter_ID TEXT, px REAL)')
    sq.executemany("INSERT INTO play_by_play VALUES (?,?,?)",
                   [(5, "1.0", 0.5), (1, "2", ""), (5, "3", 1.0)])
    spec = {"columns": [["pbp_id", "int"], ["batter_ID", "int"], ["px", "double"]],
            "renumber": "pbp_id"}
    my = FakeConn()
    fixes = collections.Counter()
    n = load.load_table(sq, my, "play_by_play", spec, fixes, batch=2)
    assert n == 3
    sql, first = my.log[0]
    assert sql == "INSERT INTO `play_by_play` (`batter_ID`, `px`) VALUES (%s, %s)"
    assert first == [(1, 0.5), (2, None)]
    assert my.log[1][1] == [(3, 1.0)]
    assert my.commits == 2


def test_orphan_queries_parse_post_sql():
    post = ("CREATE INDEX `i` ON `t` (`a`);\n"
            "ALTER TABLE `players` ADD CONSTRAINT `fk_players_team_id` FOREIGN KEY "
            "(`team_id`) REFERENCES `teams` (`team_id`);\n")
    (label, sql), = load.orphan_queries(post)
    assert label == "players.team_id → teams.team_id"
    assert "LEFT JOIN `teams` p ON c.`team_id` = p.`team_id`" in sql
    assert "p.`team_id` IS NULL" in sql
```

- [ ] **Step 2: 실패 확인**

Run: `py -m pytest tests/test_mysql_load.py -v`
Expected: FAIL (`No module named 'migration.mysql.load'`)

- [ ] **Step 3: 구현**

`migration/mysql/load.py`

```python
# -*- coding: utf-8 -*-
"""SQLite 스냅샷을 MySQL 로 옮깁니다.

    py -m migration.mysql.load --snapshot ~/.bstats/snapshots/d1_20261002.db --fresh
    py -m migration.mysql.load --snapshot … --tables players,teams

--fresh 는 표를 지우고 schema.sql 로 새로 만든 뒤, 다 넣고 나서
schema_post.sql(인덱스·외래키)을 적용합니다. --tables 는 그 표만 비우고
다시 넣습니다(인덱스는 이미 있습니다).

외래키 검사는 넣는 동안 끕니다. 대신 끝나고 외래키마다 고아 행을 세어
보고서에 남깁니다. 넣는 순서를 맞추는 것보다 확실합니다.
"""
import argparse
import collections
import datetime as dt
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

from migration.mysql import conn as myconn
from migration.mysql import typemap as tm
from migration.mysql.ddl import OUT_DIR, ROOT, q, split_sql

REPORT = ROOT / "docs" / "mysql-migration" / "load-report.md"
BATCH = 2000
_FK = re.compile(r"ALTER TABLE `([^`]+)` ADD CONSTRAINT `[^`]+` FOREIGN KEY "
                 r"\(`([^`]+)`\) REFERENCES `([^`]+)` \(`([^`]+)`\)")


def insert_sql(table, columns):
    return "INSERT INTO %s (%s) VALUES (%s)" % (
        q(table), ", ".join(q(c) for c in columns), ", ".join(["%s"] * len(columns)))


def convert_row(row, kinds, names, table, fixes):
    """한 행을 MySQL 값으로 바꾸고, 고친 값의 수를 fixes 에 셉니다."""
    out = []
    for v, kind, col in zip(row, kinds, names):
        try:
            nv = tm.normalize(v, kind)
        except ValueError as e:
            raise ValueError("%s.%s: %s" % (table, col, e)) from None
        if v is not None and nv is None:
            fixes[(table, col, "빈 값 → NULL")] += 1
        elif kind == "int" and isinstance(v, str) and "." in v:
            fixes[(table, col, "소수점 표기 → 정수")] += 1
        out.append(nv)
    return tuple(out)


def load_table(sq, my, table, spec, fixes, batch=BATCH):
    """스냅샷 표 하나를 rowid 순서대로 옮깁니다. 넣은 행 수를 돌려줍니다."""
    renumber = spec.get("renumber")
    names = [c for c, _ in spec["columns"] if c != renumber]
    kinds = [k for c, k in spec["columns"] if c != renumber]
    src = sq.execute('SELECT %s FROM "%s" ORDER BY rowid'
                     % (", ".join('"%s"' % c for c in names), table))
    ins = insert_sql(table, names)
    n = 0
    with my.cursor() as cur:
        while True:
            chunk = src.fetchmany(batch)
            if not chunk:
                break
            cur.executemany(ins, [convert_row(r, kinds, names, table, fixes)
                                  for r in chunk])
            my.commit()
            n += len(chunk)
            if n % 100000 < batch:
                print("   %s %s행" % (table, format(n, ",")), flush=True)
    return n


def orphan_queries(post_sql):
    """schema_post.sql 의 외래키마다 고아 행을 세는 질의입니다."""
    out = []
    for child, ccol, parent, pcol in _FK.findall(post_sql):
        out.append(("%s.%s → %s.%s" % (child, ccol, parent, pcol),
                    "SELECT COUNT(*) FROM `%s` c LEFT JOIN `%s` p "
                    "ON c.`%s` = p.`%s` WHERE c.`%s` IS NOT NULL AND p.`%s` IS NULL"
                    % (child, parent, ccol, pcol, ccol, pcol)))
    return out


def render_report(snapshot, counts, fixes, orphans, secs):
    lines = ["# MySQL 적재 보고", "",
             "- 스냅샷: `%s`" % Path(snapshot).name,
             "- 적재 시각(UTC): %s" % dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"),
             "- 걸린 시간: %.0f분" % (secs / 60), "",
             "| 표 | 행 |", "|---|---|"]
    lines += ["| %s | %s |" % (t, format(n, ",")) for t, n in counts.items()]
    lines += ["", "## 값 정리", "", "| 표.열 | 처리 | 건수 |", "|---|---|---|"]
    lines += ["| %s.%s | %s | %s |" % (t, c, what, format(n, ","))
              for (t, c, what), n in sorted(fixes.items())]
    lines += ["", "## 외래키 고아 행", "", "| 관계 | 고아 행 |", "|---|---|"]
    lines += ["| %s | %s |" % (label, format(n, ",")) for label, n in orphans]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--fresh", action="store_true",
                    help="표를 지우고 schema.sql 로 새로 만듭니다")
    ap.add_argument("--tables", default=None,
                    help="쉼표로 구분. 이 표만 비우고 다시 넣습니다")
    args = ap.parse_args()

    types = json.loads((OUT_DIR / "schema_types.json").read_text(encoding="utf-8"))
    tables = ([t.strip() for t in args.tables.split(",") if t.strip()]
              if args.tables else list(types))
    unknown = [t for t in tables if t not in types]
    if unknown:
        raise SystemExit("schema_types.json 에 없는 표: %s" % ", ".join(unknown))

    sq = sqlite3.connect(Path(args.snapshot).resolve().as_uri() + "?mode=ro", uri=True)
    my = myconn.connect()
    with my.cursor() as cur:
        cur.execute("SET FOREIGN_KEY_CHECKS=0")
        if args.fresh:
            for t in types:
                cur.execute("DROP TABLE IF EXISTS %s" % q(t))
            for stmt in split_sql((OUT_DIR / "schema.sql").read_text(encoding="utf-8")):
                cur.execute(stmt)
        else:
            for t in tables:
                cur.execute("TRUNCATE TABLE %s" % q(t))
    my.commit()

    t0 = time.time()
    fixes = collections.Counter()
    counts = {}
    for t in tables:
        counts[t] = load_table(sq, my, t, types[t], fixes)
        print("%-34s %12s행" % (t, format(counts[t], ",")), flush=True)

    post = (OUT_DIR / "schema_post.sql").read_text(encoding="utf-8")
    orphans = []
    with my.cursor() as cur:
        if args.fresh:
            for stmt in split_sql(post):
                print("   후처리: %s" % stmt[:80], flush=True)
                cur.execute(stmt)
        for label, sql in orphan_queries(post):
            cur.execute(sql)
            orphans.append((label, cur.fetchone()[0]))
        cur.execute("SET FOREIGN_KEY_CHECKS=1")
    my.commit()
    my.close()
    sq.close()

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(render_report(args.snapshot, counts, fixes, orphans,
                                    time.time() - t0),
                      encoding="utf-8", newline="\n")
    print("보고서: %s" % REPORT)
    bad = [(label, n) for label, n in orphans if n]
    for label, n in bad:
        print("고아 행 %s: %s" % (label, format(n, ",")))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `py -m pytest tests/test_mysql_load.py -v`
Expected: 4 passed

- [ ] **Step 5: 첫 적재 실행**

```bash
SNAP=$(ls -t ~/.bstats/snapshots/d1_*.db | head -1)
py -m migration.mysql.load --snapshot "$SNAP" --fresh
```

Expected: 표마다 행 수가 찍히고(플레이 기록은 10만 행마다 진행 표시), 마지막에 `보고서: …load-report.md`, 종료 코드 0(고아 행 없음). 플레이 기록 약 400만 행은 20~40분 걸립니다. 값 변환 오류(`표.열: 정수가 아닙니다 …`)로 멈추면 Task 4 규칙에 그 경우를 테스트와 함께 더하고, Task 5 Step 5 부터 다시 합니다.

종료 코드 1(고아 행 있음)이면 보고서의 관계와 건수를 evan 에게 보여 주고, 원본(D1)에도 같은 고아가 있는지 스냅샷에서 같은 질의로 확인합니다. 원본과 같으면 데이터 품질 문제로 기록하고 진행합니다.

- [ ] **Step 6: 커밋(evan 확인 후)**

```bash
git add migration/mysql/load.py tests/test_mysql_load.py docs/mysql-migration/load-report.md
git commit -m "feat(mysql): 스냅샷 적재기와 첫 적재 보고" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: 검증기와 대조

**Files:**
- Create: `migration/mysql/verify.py`
- Test: `tests/test_mysql_verify.py`
- 생성물: `docs/mysql-migration/verify-report.md`

**Interfaces:**
- Consumes: `conn.connect`, `ddl.OUT_DIR`, `ddl.ROOT`, `schema_types.json`.
- Produces: `verify.sqlite_expr(col, kind) -> (count_sql, sum_sql)`, `verify.mysql_expr(col, kind) -> (count_sql, sum_sql)`, `verify.close(a, b) -> bool`, `verify.verify_table(sq, my, table, spec) -> (snap_rows, my_rows, problems)`, `verify.verify_games(sq, my) -> (game_count, mismatched_ids)`, CLI `py -m migration.mysql.verify --snapshot …`(문제 있으면 종료 코드 1).

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_mysql_verify.py`

```python
import sqlite3

from migration.mysql import verify as v


def test_sqlite_side_treats_empty_as_null_and_dot_zero_as_number():
    con = sqlite3.connect(":memory:")
    con.execute('CREATE TABLE t ("b" TEXT, "px" REAL, "nm" TEXT)')
    con.executemany("INSERT INTO t VALUES (?,?,?)",
                    [("78513.0", 1.5, ""), ("", "", "가나"), ("12", 2.0, None)])
    exprs = []
    for c, k in [("b", "int"), ("px", "double"), ("nm", "text")]:
        exprs.extend(v.sqlite_expr(c, k))
    row = con.execute("SELECT %s FROM t" % ", ".join(exprs)).fetchone()
    assert row == (2, 78525.0, 2, 3.5, 2, 2.0)


def test_mysql_expressions_match_kinds():
    assert v.mysql_expr("px", "double") == ("COUNT(`px`)", "SUM(`px`)")
    assert v.mysql_expr("nm", "text") == ("COUNT(`nm`)", "SUM(CHAR_LENGTH(`nm`))")
    assert v.mysql_expr("d", "date") == \
        ("COUNT(`d`)", "SUM(CHAR_LENGTH(CAST(`d` AS CHAR)))")
    assert v.mysql_expr("img", "blob") == ("COUNT(`img`)", "SUM(LENGTH(`img`))")


def test_close_allows_float_noise_only():
    assert v.close(1e12, 1e12 + 0.0001)
    assert v.close(None, 0)
    assert not v.close(100.0, 101.0)
```

- [ ] **Step 2: 실패 확인**

Run: `py -m pytest tests/test_mysql_verify.py -v`
Expected: FAIL (`No module named 'migration.mysql.verify'`)

- [ ] **Step 3: 구현**

`migration/mysql/verify.py`

```python
# -*- coding: utf-8 -*-
"""스냅샷과 MySQL 을 대조합니다.

표마다 행 수를, 열마다 '값 있는 칸 수' 와 합계(숫자) 또는 글자 길이 합
(글자·날짜·바이너리)을 양쪽에서 세어 견줍니다. 스냅샷 쪽은 적재 때와
같은 규칙으로 ''·'-' 를 값 없음으로 봅니다. play_by_play 는 경기(gameID)
별 행 수도 견줍니다. 새로 매긴 번호(pbp_id)는 견주지 않습니다.

    py -m migration.mysql.verify --snapshot ~/.bstats/snapshots/d1_20261002.db
"""
import argparse
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path

from migration.mysql import conn as myconn
from migration.mysql.ddl import OUT_DIR, ROOT

REPORT = ROOT / "docs" / "mysql-migration" / "verify-report.md"


def sqlite_expr(col, kind):
    c = '"%s"' % col
    present = ("CASE WHEN typeof(%s)='text' AND trim(%s) IN ('','-') "
               "THEN NULL ELSE %s END" % (c, c, c))
    if kind in ("int", "double"):
        return "COUNT(%s)" % present, "TOTAL(CAST(%s AS REAL))" % present
    if kind in ("date", "datetime"):
        return "COUNT(%s)" % present, "TOTAL(length(trim(%s)))" % present
    return "COUNT(%s)" % c, "TOTAL(length(%s))" % c


def mysql_expr(col, kind):
    c = "`%s`" % col
    if kind in ("int", "double"):
        return "COUNT(%s)" % c, "SUM(%s)" % c
    if kind in ("date", "datetime"):
        return "COUNT(%s)" % c, "SUM(CHAR_LENGTH(CAST(%s AS CHAR)))" % c
    if kind == "blob":
        return "COUNT(%s)" % c, "SUM(LENGTH(%s))" % c
    return "COUNT(%s)" % c, "SUM(CHAR_LENGTH(%s))" % c


def close(a, b):
    """합계가 같은지 봅니다. 실수 덧셈 순서에서 오는 오차만 허용합니다."""
    a, b = float(a or 0), float(b or 0)
    return abs(a - b) <= max(1e-6, 1e-9 * max(abs(a), abs(b)))


def verify_table(sq, my, table, spec):
    cols = [(c, k) for c, k in spec["columns"] if c != spec.get("renumber")]
    s_parts, m_parts = ["COUNT(*)"], ["COUNT(*)"]
    for c, k in cols:
        s_parts.extend(sqlite_expr(c, k))
        m_parts.extend(mysql_expr(c, k))
    s = sq.execute('SELECT %s FROM "%s"' % (", ".join(s_parts), table)).fetchone()
    with my.cursor() as cur:
        cur.execute("SELECT %s FROM `%s`" % (", ".join(m_parts), table))
        m = cur.fetchone()
    problems = []
    if s[0] != m[0]:
        problems.append("행 수 %s / %s" % (format(s[0], ","), format(m[0], ",")))
    for i, (c, k) in enumerate(cols):
        sc, ss = s[1 + 2 * i], s[2 + 2 * i]
        mc, ms = m[1 + 2 * i], m[2 + 2 * i]
        if sc != mc:
            problems.append("%s: 값 있는 칸 %s / %s" % (c, sc, mc))
        elif not close(ss, ms):
            problems.append("%s: 합계 %s / %s" % (c, ss, ms))
    return s[0], m[0], problems


def verify_games(sq, my):
    s = dict(sq.execute('SELECT "gameID", COUNT(*) FROM play_by_play GROUP BY 1'))
    with my.cursor() as cur:
        cur.execute("SELECT `gameID`, COUNT(*) FROM `play_by_play` GROUP BY 1")
        m = {k: int(n) for k, n in cur.fetchall()}
    bad = sorted((g for g in set(s) | set(m) if s.get(g) != m.get(g)),
                 key=lambda g: str(g))
    return len(s), bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    args = ap.parse_args()
    types = json.loads((OUT_DIR / "schema_types.json").read_text(encoding="utf-8"))
    sq = sqlite3.connect(Path(args.snapshot).resolve().as_uri() + "?mode=ro", uri=True)
    my = myconn.connect()
    lines = ["# MySQL 대조 보고", "",
             "- 스냅샷: `%s`" % Path(args.snapshot).name,
             "- 대조 시각(UTC): %s" % dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"),
             "", "| 표 | 스냅샷 행 | MySQL 행 | 결과 |", "|---|---|---|---|"]
    failed = []
    for table, spec in types.items():
        srows, mrows, problems = verify_table(sq, my, table, spec)
        lines.append("| %s | %s | %s | %s |" % (
            table, format(srows, ","), format(mrows, ","),
            "같음" if not problems else "<br>".join(problems)))
        if problems:
            failed.append(table)
        print("%-34s %s" % (table, "같음" if not problems else "; ".join(problems)),
              flush=True)
    if "play_by_play" in types:
        games, bad = verify_games(sq, my)
        lines += ["", "경기별 플레이 수: %s경기 중 다른 경기 %d개%s" % (
            format(games, ","), len(bad),
            "" if not bad else " (" + ", ".join(str(g) for g in bad[:20]) + ")")]
        if bad:
            failed.append("play_by_play(경기별)")
    my.close()
    sq.close()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("보고서: %s" % REPORT)
    print("결과: %s" % ("모두 같음" if not failed else "다름 - " + ", ".join(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 테스트 통과 확인(1단계 전체)**

Run: `py -m pytest tests/test_mysql_conn.py tests/test_mysql_tables.py tests/test_d1_usage.py tests/test_d1_to_sqlite_options.py tests/test_mysql_typemap.py tests/test_mysql_ddl.py tests/test_mysql_load.py tests/test_mysql_verify.py tests/test_shard_routing.py -v`
Expected: 전부 passed

- [ ] **Step 5: 실제 대조 실행**

```bash
SNAP=$(ls -t ~/.bstats/snapshots/d1_*.db | head -1)
py -m migration.mysql.verify --snapshot "$SNAP"
```

Expected: 모든 표 `같음`, `경기별 플레이 수: …경기 중 다른 경기 0개`, `결과: 모두 같음`, 종료 코드 0.

다른 표가 나오면: 그 열의 값 정리 규칙(Task 4)과 대조 규칙(이 Task) 중 어느 쪽이 틀렸는지 스냅샷에서 해당 열의 서로 다른 값 몇 개를 꺼내 확인합니다. 규칙을 고치면 테스트를 먼저 더하고, `load --tables <그 표>` 로 그 표만 다시 넣고 다시 대조합니다.

- [ ] **Step 6: 커밋(evan 확인 후)**

```bash
git add migration/mysql/verify.py tests/test_mysql_verify.py docs/mysql-migration/verify-report.md
git commit -m "feat(mysql): 스냅샷 대 MySQL 대조 검증과 첫 보고" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 7: 1단계 마무리 보고**

evan 에게 알립니다: 옮긴 표 수와 총 행 수, 값 정리 건수(빈 값 → NULL, 소수점 ID → 정수), 고아 행, 대조 결과, MySQL 저장 용량(`SELECT ROUND(SUM(data_length+index_length)/1024/1024) FROM information_schema.tables WHERE table_schema='bstats'`), 걸린 시간. 그리고 2단계(수집 스크립트) 상세 계획서를 쓸지 묻습니다.

---

## 이 단계에서 하지 않는 것

- 수집 스크립트·API·화면 변경(2·3단계).
- D1 쓰기, D1 메타 보정(로드맵 0단계, 별도 승인).
- 스냅샷 이후 D1 에 생긴 변경분 반영(5단계 전환 때).
- CHECK 제약 옮기기(원본이 SQLite 에서 이미 지켜 온 값이라 데이터는 맞습니다. 필요하면 2단계 이후에 더합니다).

---

## 실행 중 보완 (2026-10-02)

Task 4~7 을 구현하면서 테스트로 다음을 확인했습니다. 이 계획서의 코드 블록과 다르면 커밋된 코드가 기준입니다.

- **(Task 4) `typemap.py`**: 날짜는 달력 형식만 인정하고(`YYYY-MM-DD`), 정규식은 ASCII 숫자만 받습니다. 선수 ID 는 2^32-1 이하일 때만 INT UNSIGNED 로 옮기고, 정수가 BIGINT 범위를 넘으면 멈춥니다.
- **(Task 5) `ddl.py`**: 후처리 문(인덱스·외래키)은 인덱스 전부를 먼저 보낸 뒤 외래키 전부를 보내므로, 외래키가 유니크 인덱스를 참조해도 순서 오류가 나지 않습니다(MySQL 오류 1822 방지). 기본키와 인덱스는 3072바이트 한도를, 행은 65,535바이트 한도를 넘지 않는지 생성 단계에서 검사합니다(내용을 넣기 전에 오류를 잡습니다). 새로 번호를 붙이는 열(`play_by_play.pbp_id`)은 프로필을 만들지 않으므로 4백만 행을 모두 훑는 일을 피합니다. 식 인덱스는 스키마에서 빼고(보고서 메모로 남깁니다); 참조 열이 명시되지 않은 외래키는 부모 표의 단일 열 기본키를 참조하고, 그것이 불가능할 때만 스키마에서 뺍니다(보고서 메모로 남깁니다). Step 6 은 빈 표에 인덱스와 외래키까지 적용해 배포 전에 정의 오류를 조기에 잡습니다.
- **(Task 6) `load.py`**: 자동 번호 열의 0번을 그대로 지킵니다(NO_AUTO_VALUE_ON_ZERO). 적재가 멈추면 표 이름과 넣은 행 수, "--fresh 로 처음부터" 안내를 냅니다. --fresh 와 --tables 를 함께 쓸 수 없고, --tables 는 보고서를 덮어쓰지 않습니다. 외래키 문장을 다 읽지 못하면 멈춥니다. 연결은 예외 발생 후에도 닫습니다.
- **(Task 7) `verify.py`**: 정수·글자 길이·날짜는 합계가 정확히 같아야 하고 실수만 덧셈 오차를 허용합니다. 날짜는 YYYYMMDD(일시는 초까지) 내용 합계를 견줍니다. 표마다 무작위 200행을 키로 짝지어 값을 하나하나 견줍니다(플레이 기록은 새 번호 = 스냅샷 줄 번호). 공백 처리를 적재 규칙과 맞추고, 경기 ID 는 대소문자를 구분해 묶고, 스냅샷에 없는 열을 잡아냅니다.
