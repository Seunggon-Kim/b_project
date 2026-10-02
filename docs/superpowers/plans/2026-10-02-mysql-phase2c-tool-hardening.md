# 2C 1단계 도구 보강 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 1단계에서 빠진 인덱스 13개와 새 인덱스 `idx_pbp_game_date` 를 MySQL 에 만들고, 다음 스냅샷부터는 인덱스가 저절로 따라오게 하며, 적재기가 시작할 때 남은 연결을 정리하게 합니다.

**Architecture:** D1 → 스냅샷(`d1_to_sqlite.py`)이 인덱스 정의도 옮기고, 스키마 생성(`ddl.py`)이 그것을 `schema_post.sql` 로 냅니다. MySQL 에는 적재기의 새 `--post-only` 로 없는 개체만 만들고, 검증기의 새 `--objects-only` 로 모두 있는지 확인합니다.

**Tech Stack:** Python 3.11+, sqlite3, PyMySQL, pytest, wrangler 4(D1 읽기), Cloud SQL Auth Proxy

## Global Constraints

- 저장소 `Seunggon-Kim/b_project` 는 **공개**입니다. 서버 IP·비밀번호·키·`~/.bstats/` 내용을 코드·문서·커밋에 넣지 않습니다.
- 회사 계정(evan@delivered.co.kr)·회사 GCP 를 쓰지 않습니다. gcloud 는 늘 `--configuration=bstats --project=bstats-kbo` 를 붙이고, `default` 설정은 건드리지 않으며, `gcloud auth application-default login` 은 하지 않습니다.
- push·병합·배포는 건마다 evan 허락을 받습니다. 이 계획서는 로컬 브랜치 커밋과 MySQL 인덱스 생성(Task 5, evan 승인 뒤)까지입니다.
- D1 은 읽기만 합니다. 이 계획서의 D1 읽기는 `sqlite_master` 몇백 행뿐입니다.
- MySQL 접속은 Auth Proxy 로만 합니다(허용 네트워크 없음). 프록시는 백그라운드 작업 2시간 한도가 있어 긴 일 앞에 다시 띄웁니다.
- Python 은 `py`. 테스트: `PYTHONUTF8=1 py -m pytest <경로> -p no:cacheprovider -q`. 전체의 알려진 실패 2개(`tests/test_cron_table_parity.py`, `tests/test_workflow_deps.py`) 외 새 실패 0.
- 커밋 메시지 끝: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- 작업 위치: `git -C C:/Users/김승곤/Desktop/b_project worktree add C:/tmp/b_project_2c -b fix/phase2c-tools main` 로 만든 worktree.

## 보류한 1단계 보강 2건

로드맵의 `--append` 보호와 스냅샷 지문은 이번에 하지 않습니다. 2B 의 따라잡기는 공용 표를 `--tables` 로 다시 넣고 PBP 는 크롤러로 다시 받으므로 두 기능을 쓰지 않습니다. 전체 재이전이 필요해지면 그 계획서에서 합니다.

---

### Task 1: 스키마 생성이 부분 인덱스를 구분하고 추가 인덱스를 내기

SQLite 의 부분 인덱스(`… WHERE 조건`)는 MySQL 에 없습니다. 지금은 조건을 버리고 전체 인덱스로 옮겨, 부분 UNIQUE 는 넣을 수 있던 행을 막게 됩니다. 또 MySQL 에서는 `play_by_play` 가 400만 행 한 표라 `game_date` 인덱스가 필요합니다(D1 은 샤드라 없어도 됐습니다).

**Files:**
- Modify: `migration/mysql/ddl.py` (`EXTRA_INDEXES` 상수, `read_table`, `post_statements`, `build` 메모)
- Test: `tests/test_mysql_ddl.py` (끝에 3개 추가)

**Interfaces:**
- Produces: `ddl.EXTRA_INDEXES: dict[str, list[tuple[str, list[str]]]]` — `{"play_by_play": [("idx_pbp_game_date", ["game_date"])]}`
- Produces: `read_table(...)` 결과에 `"partial_unique": [이름, …]` 키 추가, `indexes` 항목에 `"partial": bool` 추가.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_mysql_ddl.py` 끝에 붙입니다.

```python
def _one_table(tmp_path, ddl_sql, insert_sql):
    p = tmp_path / "snap.db"
    con = sqlite3.connect(str(p))
    con.executescript(ddl_sql)
    con.execute(insert_sql)
    con.commit()
    con.close()
    return p


def test_partial_unique_index_skipped(tmp_path):
    """부분 UNIQUE 는 MySQL 에 같은 뜻이 없어 옮기지 않고 메모를 남깁니다."""
    p = _one_table(tmp_path, """
        CREATE TABLE u (a TEXT, b INTEGER);
        CREATE UNIQUE INDEX ux_part ON u(a) WHERE b = 1;
    """, "INSERT INTO u VALUES ('X', 1)")
    _, posts, _, notes = ddl.build(p)
    assert not any("ux_part" in s for s in posts)
    assert any("ux_part" in n and "부분 UNIQUE" in n for n in notes)


def test_partial_plain_index_kept_as_full(tmp_path):
    """부분 일반 인덱스는 전체 인덱스로 옮겨도 결과가 같습니다(크기만 큽니다)."""
    p = _one_table(tmp_path, """
        CREATE TABLE u (a TEXT, b INTEGER);
        CREATE INDEX ix_part ON u(a) WHERE b = 1;
    """, "INSERT INTO u VALUES ('X', 1)")
    _, posts, _, notes = ddl.build(p)
    assert "CREATE INDEX `ix_part` ON `u` (`a`);" in posts
    assert any("ix_part" in n and "전체 인덱스" in n for n in notes)


def test_extra_index_on_pbp_game_date(tmp_path):
    """MySQL 에서 한 표가 된 play_by_play 는 game_date 인덱스를 더 둡니다."""
    p = _one_table(tmp_path, """
        CREATE TABLE play_by_play (pbp_id INTEGER, gameID TEXT, game_date INTEGER);
    """, "INSERT INTO play_by_play VALUES (1, 'G1', 20261003)")
    _, posts, _, _ = ddl.build(p)
    assert "CREATE INDEX `idx_pbp_game_date` ON `play_by_play` (`game_date`);" in posts
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_ddl.py -p no:cacheprovider -q`
Expected: 새 3개 FAIL(부분 UNIQUE 가 posts 에 들어감, 메모 없음, 추가 인덱스 없음).

- [ ] **Step 3: `ddl.py` 고치기**

`RENUMBER = {"play_by_play": "pbp_id"}` 아래에 둡니다.

```python
# D1 에는 없지만 MySQL 에 더 두는 인덱스입니다. D1 은 시즌별 샤드라
# 날짜로 고를 일이 적었지만, MySQL 은 400만 행이 한 표라 하루치를
# 지우고 다시 넣는 `DELETE … WHERE game_date = ?` 가 인덱스 없이는
# 표 전체를 훑습니다(2단계 이중 적재).
EXTRA_INDEXES = {"play_by_play": [("idx_pbp_game_date", ["game_date"])]}
```

`read_table` 의 인덱스 반복을 바꿉니다(`PRAGMA index_list` 의 다섯째 칸이 부분 인덱스 여부입니다).

```python
    indexes = []
    expr_indexes = []
    partial_unique = []
    for r in con.execute('PRAGMA index_list("%s")' % table):
        name, unique, origin, partial = r[1], bool(r[2]), r[3], bool(r[4])
        if origin == "pk":
            continue
        icols = [x[2] for x in con.execute('PRAGMA index_info("%s")' % name)]
        if any(c is None for c in icols):
            expr_indexes.append(name)
        elif partial and unique:
            partial_unique.append(name)
        else:
            indexes.append({"name": name, "unique": unique, "columns": icols,
                            "partial": partial})
    return {"name": table, "columns": cols, "pk": pk, "fks": fks,
            "indexes": indexes, "expr_indexes": expr_indexes,
            "partial_unique": partial_unique,
            "multi_fk": [k for k, v in groups.items() if len(v) > 1]}
```

`post_statements` 의 인덱스 반복 다음, 외래키 반복 앞에 넣습니다.

```python
    have = {tuple(ix["columns"]) for ix in t["indexes"]}
    colnames = {c["name"] for c in t["columns"]}
    for ixname, icols in EXTRA_INDEXES.get(name, []):
        if tuple(icols) in have or not set(icols) <= colnames:
            continue
        indexes.append("CREATE INDEX %s ON %s (%s);" % (
            q(ixname), q(name), ", ".join(q(c) for c in icols)))
```

`build` 의 `# 식 인덱스 메모` 반복을 바꿉니다.

```python
    # 식 인덱스·부분 인덱스 메모
    for n in names:
        for expr_ix in tables[n]["expr_indexes"]:
            notes.append("%s: 식 인덱스 %s 는 옮기지 않았습니다" % (n, expr_ix))
        for pu in tables[n]["partial_unique"]:
            notes.append("%s: 부분 UNIQUE 인덱스 %s 는 MySQL 에 같은 뜻이 없어 "
                         "옮기지 않았습니다" % (n, pu))
        for ix in tables[n]["indexes"]:
            if ix["partial"]:
                notes.append("%s: 부분 인덱스 %s 를 전체 인덱스로 옮겼습니다"
                             % (n, ix["name"]))
```

- [ ] **Step 4: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_ddl.py -p no:cacheprovider -q`
Expected: 모두 PASS(기존 `test_expression_index_skipped`·`test_indexes_before_foreign_keys` 포함).

- [ ] **Step 5: 커밋**

```bash
git add migration/mysql/ddl.py tests/test_mysql_ddl.py
git commit -m "feat(mysql-ddl): 부분 인덱스 구분, play_by_play.game_date 인덱스 추가

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: 스냅샷이 D1 인덱스를 따라 가져오기

`wrangler d1 export --table` 은 표 정의와 행만 내리고 인덱스를 안 내립니다. 그래서 1단계 스냅샷에 공용 인덱스 13개가 없었고 MySQL 에도 안 생겼습니다(PBP 인덱스 3개는 손으로 다시 만들었습니다).

**Files:**
- Modify: `migration/d1_to_sqlite.py` (함수 3개, `--indexes-only` 옵션, `main`)
- Test: `tests/test_d1_to_sqlite_indexes.py` (새 파일)

**Interfaces:**
- Produces: `index_sql(db_name) -> list[tuple[str, str]]` — `(표 이름, CREATE INDEX 문)`.
- Produces: `idempotent_index(sql) -> str`, `copy_indexes(conn, db_names, fetch=index_sql) -> int`(만든 또는 이미 있던 인덱스 문 수).

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_d1_to_sqlite_indexes.py`:

```python
import sqlite3

from migration import d1_to_sqlite as m


def test_idempotent_index_adds_if_not_exists_once():
    assert (m.idempotent_index("CREATE INDEX idx_a ON t(a)")
            == "CREATE INDEX IF NOT EXISTS idx_a ON t(a)")
    assert (m.idempotent_index("CREATE UNIQUE INDEX u ON t(a)")
            == "CREATE UNIQUE INDEX IF NOT EXISTS u ON t(a)")
    assert (m.idempotent_index("CREATE INDEX IF NOT EXISTS i ON t(a)")
            == "CREATE INDEX IF NOT EXISTS i ON t(a)")
    # D1 정의에는 공백이 여러 칸인 것도 있습니다(idx_roster_team   ON …).
    assert (m.idempotent_index("CREATE INDEX idx_roster_team   ON kbo_roster(team)")
            == "CREATE INDEX IF NOT EXISTS idx_roster_team   ON kbo_roster(team)")


def test_copy_indexes_only_for_tables_we_have():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE games (game_id TEXT, game_date INTEGER)")
    fake = {"kbo-stats": [
        ("games", "CREATE INDEX idx_games_date ON games(game_date)"),
        ("players", "CREATE INDEX idx_players_team ON players(team_id)"),
    ]}
    assert m.copy_indexes(conn, ["kbo-stats"], fetch=fake.__getitem__) == 1
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'")}
    assert names == {"idx_games_date"}
    # 두 번 불러도 실패하지 않습니다.
    assert m.copy_indexes(conn, ["kbo-stats"], fetch=fake.__getitem__) == 1
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_d1_to_sqlite_indexes.py -p no:cacheprovider -q`
Expected: `AttributeError: module 'migration.d1_to_sqlite' has no attribute 'idempotent_index'`

- [ ] **Step 3: 함수 추가**

`migration/d1_to_sqlite.py` 의 `list_tables` 아래에 둡니다.

```python
_CREATE_INDEX = re.compile(r"^(\s*CREATE\s+(?:UNIQUE\s+)?INDEX\s+)(?!IF\s+NOT\s+EXISTS)",
                           re.IGNORECASE)


def index_sql(db_name=DB_NAME):
    """그 D1 의 인덱스 정의입니다. [(표 이름, CREATE INDEX 문)].

    `wrangler d1 export --table` 은 인덱스를 내리지 않습니다. 그래서 1단계
    스냅샷에 공용 인덱스 13개가 빠졌고 MySQL 에도 안 생겼습니다.
    sqlite_master 몇십 행만 읽습니다. sql 이 NULL 인 것은 UNIQUE 제약이
    만든 자동 인덱스라 표 정의에 이미 들어 있습니다.
    """
    out = subprocess.run(
        ["npx", "--yes", "wrangler@4", "d1", "execute", db_name, "--remote",
         "--command",
         "SELECT tbl_name, sql FROM sqlite_master "
         "WHERE type='index' AND sql IS NOT NULL ORDER BY tbl_name, name;",
         "--json", "--yes"],
        capture_output=True, text=True, shell=USE_SHELL,
        encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise RuntimeError("인덱스 목록 실패(%s): %s"
                           % (db_name, (out.stderr or out.stdout)[-400:]))
    body = out.stdout[out.stdout.find("["):]
    return [(r["tbl_name"], r["sql"]) for r in json.loads(body)[0]["results"]]


def idempotent_index(sql):
    """CREATE INDEX 에 IF NOT EXISTS 를 붙입니다. 이미 있으면 그대로 둡니다."""
    return _CREATE_INDEX.sub(r"\1IF NOT EXISTS ", sql, count=1)


def copy_indexes(conn, db_names, fetch=index_sql):
    """D1 의 인덱스를 로컬 스냅샷에 만듭니다. 로컬에 있는 표만 합니다.

    같은 이름이 여러 D1 에 있으면(샤드마다 games 사본) 한 번만 생깁니다.
    돌려주는 값은 실행한 문 수입니다.
    """
    have = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    n = 0
    for db in db_names:
        for table, sql in fetch(db):
            if table not in have:
                continue
            conn.execute(idempotent_index(sql))
            n += 1
    conn.commit()
    return n
```

`re` 는 이미 import 되어 있습니다(26행).

- [ ] **Step 4: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_d1_to_sqlite_indexes.py tests/test_d1_to_sqlite_options.py -p no:cacheprovider -q`
Expected: 모두 PASS.

- [ ] **Step 5: `main` 에 붙이기**

옵션을 하나 더합니다(`--count-check` 다음).

```python
    ap.add_argument("--indexes-only", action="store_true",
                    help="내려받지 않고, 이미 있는 --out 스냅샷에 D1 인덱스만 만듭니다")
```

`args = ap.parse_args()` 바로 다음에 넣습니다.

```python
    if args.indexes_only:
        out = Path(args.out)
        if not out.exists():
            raise SystemExit("%s 가 없습니다. --indexes-only 는 있는 스냅샷에만 씁니다." % out)
        conn = sqlite3.connect(str(out))
        dbs = [DB_NAME] + [s["database"] for s in shard_plan.shards()]
        n = copy_indexes(conn, dbs)
        conn.close()
        print("인덱스 %d문을 적용했습니다(이미 있던 것 포함): %s" % (n, out))
        return 0
```

내려받기 반복이 끝난 뒤 `conn.close()` 바로 앞에 넣습니다(`--all-tables` 일 때만, 즉 1단계 같은 전체 이전 때만).

```python
        if args.all_tables:
            dbs = sorted({db for _, db, _ in jobs})
            n = copy_indexes(conn, dbs)
            print("D1 인덱스 %d문을 스냅샷에 적용했습니다." % n, flush=True)
```

- [ ] **Step 6: 전체 테스트**

Run: `PYTHONUTF8=1 py -m pytest tests -p no:cacheprovider -q`
Expected: 알려진 2개 외 실패 0.

- [ ] **Step 7: 커밋**

```bash
git add migration/d1_to_sqlite.py tests/test_d1_to_sqlite_indexes.py
git commit -m "feat(d1-export): 전체 이전 스냅샷에 D1 인덱스를 함께 옮김, --indexes-only

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: 적재기 시작 정리·잠금 대기 한도·`--post-only`

적재기는 다시 연결할 때만 끊긴 이전 연결을 정리합니다. 이전 실행이 죽으며 남긴 서버 세션이 표 잠금을 쥐고 있으면, 새 실행의 `TRUNCATE` 가 기본값(1년) 동안 기다립니다. 1단계에서 실제로 손으로 KILL 했습니다.

**Files:**
- Modify: `migration/mysql/load.py` (docstring, `LOCK_WAIT_SEC`, `prepare_session`, `_reconnect_and_count`, `main`)
- Test: `tests/test_mysql_load.py` (끝에 4개 추가)

**Interfaces:**
- Produces: `load.prepare_session(cur) -> None`, `load.LOCK_WAIT_SEC = 120`
- Produces: CLI `py -m migration.mysql.load --post-only` — `schema_post.sql` 중 없는 개체만 만들고 고아 행을 셉니다. `--snapshot` 이 필요 없습니다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_mysql_load.py` 끝에 붙입니다.

```python
class SetupCursor:
    def __init__(self, log):
        self.log = log

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, args=None):
        self.log.append(sql)

    def fetchall(self):
        return []

    def fetchone(self):
        return (0,)        # 개체가 없다고 답하고, 고아 행도 0


class SetupConn:
    def __init__(self):
        self.log = []

    def cursor(self):
        return SetupCursor(self.log)

    def commit(self):
        pass

    def close(self):
        pass


def test_prepare_session_sets_lock_wait_timeout():
    conn = SetupConn()
    with conn.cursor() as cur:
        load.prepare_session(cur)
    assert "SET FOREIGN_KEY_CHECKS=0" in conn.log
    assert "SET SESSION lock_wait_timeout = 120" in conn.log


def test_snapshot_required_without_post_only(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["load", "--tables", "teams"])
    with pytest.raises(SystemExit):
        load.main()


def test_post_only_cannot_combine(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["load", "--post-only", "--fresh"])
    with pytest.raises(SystemExit):
        load.main()


def test_post_only_cleans_up_then_applies_missing(monkeypatch):
    conn = SetupConn()
    monkeypatch.setattr(load.myconn, "connect", lambda: conn)
    monkeypatch.setattr(sys, "argv", ["load", "--post-only"])
    assert load.main() == 0
    stale = next(i for i, s in enumerate(conn.log) if "PROCESSLIST" in s)
    first_post = next(i for i, s in enumerate(conn.log) if s.startswith("CREATE "))
    assert stale < first_post
    assert any(s.startswith("CREATE INDEX `idx_pbp_game`") for s in conn.log)
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_load.py -p no:cacheprovider -q`
Expected: 새 4개 FAIL(`prepare_session` 없음, `--post-only` 모름).

- [ ] **Step 3: 세션 준비를 한 곳으로**

`SESSION_SETUP` 아래에 둡니다.

```python
# 메타데이터 잠금(TRUNCATE·DDL) 대기 한도입니다. 기본값은 1년이라, 죽은 이전
# 실행의 세션이 잠금을 쥐고 있으면 적재가 끝없이 멈춥니다(1단계에서 겪음).
LOCK_WAIT_SEC = 120


def prepare_session(cur):
    """연결마다 거는 세션 설정입니다. 다시 연결하면 사라지므로 그때도 다시 겁니다."""
    for stmt in SESSION_SETUP:
        cur.execute(stmt)
    cur.execute("SET SESSION lock_wait_timeout = %d" % LOCK_WAIT_SEC)
```

`_reconnect_and_count` 안의 `for stmt in SESSION_SETUP: cur.execute(stmt)` 두 줄을 `prepare_session(cur)` 한 줄로 바꿉니다.

- [ ] **Step 4: `main` 고치기**

옵션 부분을 바꿉니다.

```python
    ap.add_argument("--snapshot", default=None)
    ...(--fresh, --tables, --resume 그대로)...
    ap.add_argument("--post-only", action="store_true",
                    help="넣지 않고 schema_post.sql 중 없는 인덱스·외래키만 만듭니다")
    args = ap.parse_args()

    if args.post_only and (args.fresh or args.tables or args.resume):
        ap.error("--post-only 는 --fresh·--tables·--resume 과 함께 쓸 수 없습니다.")
    if not args.post_only and not args.snapshot:
        ap.error("--snapshot 이 필요합니다.")
```

(기존 `--fresh`·`--tables`·`--resume` 검사는 그대로 둡니다.)

기존 검사들 다음, `types = json.loads(...)` 앞에 넣습니다.

```python
    if args.post_only:
        post = (OUT_DIR / "schema_post.sql").read_text(encoding="utf-8")
        my = myconn.connect()
        try:
            with my.cursor() as cur:
                prepare_session(cur)
                ids = kill_stale_sessions(cur)
                if ids:
                    print("이전 연결 %d개를 끊었습니다(같은 계정·같은 DB)." % len(ids))
                apply_post_skipping_existing(cur, post)
                bad = []
                for label, sql in orphan_queries(post):
                    cur.execute(sql)
                    n = cur.fetchone()[0]
                    if n:
                        bad.append((label, n))
                cur.execute("SET FOREIGN_KEY_CHECKS=1")
            my.commit()
        finally:
            my.close()
        for label, n in bad:
            print("고아 행 %s: %s" % (label, format(n, ",")))
        print("후처리 완료" if not bad else "후처리는 했지만 고아 행이 있습니다")
        return 1 if bad else 0
```

일반 경로의 첫 커서 블록을 바꿉니다(`for stmt in SESSION_SETUP:` 두 줄 대신).

```python
        with my.cursor() as cur:
            prepare_session(cur)
            # 죽은 이전 실행의 세션이 잠금을 쥐고 있을 수 있습니다. 시작할 때 정리합니다.
            ids = kill_stale_sessions(cur)
            if ids:
                print("이전 연결 %d개를 끊었습니다(같은 계정·같은 DB)." % len(ids), flush=True)
```

- [ ] **Step 5: docstring 문구를 실제와 맞추기**

모듈 docstring 의 이 단락을

```
다시 연결한 뒤에는 이 적재가 남긴 끊긴 이전 연결을 서버에서 스스로 끊으므로,
적재는 한 번에 하나만 돌리십시오.
```

아래로 바꾸고, 사용 예에 `--post-only` 를 더합니다.

```
시작할 때와 다시 연결한 뒤, **같은 계정·같은 DB 의 다른 연결을 모두** 끊습니다.
적재 중에 같은 계정으로 verify 나 다른 적재를 돌리지 마십시오(그 연결도 끊깁니다).
수집 계정(bstats_loader)의 연결은 계정이 달라 건드리지 않습니다.

    py -m migration.mysql.load --post-only     # 없는 인덱스·외래키만 만들기
```

- [ ] **Step 6: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_load.py -p no:cacheprovider -q`
Expected: 모두 PASS(기존 재시도·이어 넣기 테스트 포함).

- [ ] **Step 7: 커밋**

```bash
git add migration/mysql/load.py tests/test_mysql_load.py
git commit -m "feat(mysql-load): 시작 때 남은 연결 정리, lock_wait_timeout 120초, --post-only

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: 검증기가 인덱스·외래키가 모두 있는지 보기

**Files:**
- Modify: `migration/mysql/verify.py` (함수 추가, `main` 에 `--objects-only`)
- Test: `tests/test_mysql_verify.py` (끝에 1개 추가)

**Interfaces:**
- Consumes: `load.post_object(stmt)`, `load._EXISTS`, `ddl.split_sql`
- Produces: `verify.missing_post_objects(cur, post_sql) -> list[tuple[str, str, str]]` — `(종류, 표, 이름)`.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_mysql_verify.py` 끝에 붙입니다.

```python
class ExistsCursor:
    def __init__(self, present):
        self.present = present
        self.last = None

    def execute(self, sql, args=None):
        self.last = args

    def fetchone(self):
        return (1 if self.last[1] in self.present else 0,)


def test_missing_post_objects_lists_absent_only():
    post = ("CREATE INDEX `idx_a` ON `t` (`a`);\n"
            "ALTER TABLE `t` ADD CONSTRAINT `fk_t_b` FOREIGN KEY (`b`) "
            "REFERENCES `u` (`b`);\n")
    assert v.missing_post_objects(ExistsCursor({"idx_a"}), post) == [("fk", "t", "fk_t_b")]
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_verify.py -p no:cacheprovider -q`
Expected: `AttributeError: … has no attribute 'missing_post_objects'`

- [ ] **Step 3: 함수 추가**

import 를 바꿉니다.

```python
from migration.mysql.ddl import OUT_DIR, ROOT, split_sql
from migration.mysql.load import _EXISTS, post_object
```

`verify_games` 위에 둡니다.

```python
def missing_post_objects(cur, post_sql):
    """schema_post.sql 의 인덱스·외래키 중 MySQL 에 없는 것입니다."""
    missing = []
    for stmt in split_sql(post_sql):
        kind, table, name = post_object(stmt)
        cur.execute(_EXISTS[kind], (table, name))
        if not cur.fetchone()[0]:
            missing.append((kind, table, name))
    return missing
```

- [ ] **Step 4: `main` 에 붙이기**

옵션을 바꿉니다.

```python
    ap.add_argument("--snapshot", default=None)
    ap.add_argument("--objects-only", action="store_true",
                    help="스냅샷 대조 없이 schema_post.sql 개체가 모두 있는지만 봅니다")
    args = ap.parse_args()
    post = (OUT_DIR / "schema_post.sql").read_text(encoding="utf-8")
    if args.objects_only:
        my = myconn.connect()
        try:
            with my.cursor() as cur:
                missing = missing_post_objects(cur, post)
        finally:
            my.close()
        for kind, table, name in missing:
            print("없음: %s %s.%s" % (kind, table, name))
        print("개체 모두 있음" if not missing else "개체 %d개 없음" % len(missing))
        return 1 if missing else 0
    if not args.snapshot:
        ap.error("--snapshot 이 필요합니다.")
```

전체 대조에도 넣습니다. `if "play_by_play" in types:` 블록 다음, `REPORT.parent.mkdir` 앞에 둡니다.

```python
        with my.cursor() as cur:
            missing = missing_post_objects(cur, post)
        lines += ["", "인덱스·외래키: %s" % (
            "모두 있음" if not missing else
            "없음 " + ", ".join("%s.%s" % (t, n) for _, t, n in missing))]
        if missing:
            failed.append("인덱스·외래키")
```

- [ ] **Step 5: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_mysql_verify.py tests/test_mysql_load.py -p no:cacheprovider -q`
Expected: 모두 PASS.

- [ ] **Step 6: 커밋**

```bash
git add migration/mysql/verify.py tests/test_mysql_verify.py
git commit -m "feat(mysql-verify): schema_post 인덱스·외래키가 모두 있는지 확인, --objects-only

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: 스냅샷·스키마·MySQL 에 인덱스 적용 (evan 승인 뒤 실행)

MySQL 에 인덱스 14개를 만듭니다. `play_by_play` 400만 행의 `idx_pbp_game_date` 는 온라인 DDL(INPLACE)이라 읽기·쓰기를 막지 않고 몇 분 걸립니다. 사이트는 아직 D1 을 읽으므로 영향이 없습니다.

**Files:**
- Modify(생성물): `migration/mysql/schema_post.sql`, `docs/mysql-migration/schema-report.md`
- 로컬만: `~/.bstats/snapshots/d1_20261002.db` 에 인덱스 추가(데이터는 그대로)

- [ ] **Step 1: 프록시 띄우기(백그라운드)**

```bash
~/.bstats/bin/cloud-sql-proxy.exe --credentials-file ~/.bstats/sa-migrator.json \
  --address 127.0.0.1 --port 3307 bstats-kbo:asia-northeast3:bstats-mysql > C:/tmp/cloud_sql_proxy.log 2>&1
```

Run(다른 창): `BSTATS_MYSQL_SETTINGS=~/.bstats/mysql_proxy.json PYTHONUTF8=1 py -m migration.mysql.conn --ping`
Expected: `MySQL 8.4.… / DB bstats / 암호화 Auth Proxy 경유`

- [ ] **Step 2: 스냅샷에 D1 인덱스 넣기(D1 읽기 수백 행)**

Run: `PYTHONUTF8=1 py migration/d1_to_sqlite.py --out ~/.bstats/snapshots/d1_20261002.db --indexes-only`
Expected: `인덱스 N문을 적용했습니다` (N 은 공용 13 + 샤드 6개 × 3~7 = 30 안팎. 이름이 겹치는 것은 한 번만 생깁니다).

Run: `py -c "import sqlite3,os; c=sqlite3.connect(os.path.expanduser('~/.bstats/snapshots/d1_20261002.db')); print(sorted(r[0] for r in c.execute(\"select name from sqlite_master where type='index' and sql is not null\")))"`
Expected: 아래 16개가 모두 있습니다. 2015~2023 샤드에만 있는 인덱스가 있으면 더 나올 수 있습니다. 그러면 이름을 실행 기록에 적고 계속합니다.
`idx_futures_games_date, idx_game_stats_team, idx_games_away_team, idx_games_date, idx_games_home_team, idx_games_season, idx_moves_date, idx_moves_player, idx_pbp_batter, idx_pbp_game, idx_pbp_pitcher, idx_players_team, idx_roster_player, idx_roster_team, idx_wpf_batter_season, idx_wrc_season`

- [ ] **Step 3: 스키마 다시 만들기**

Run: `PYTHONUTF8=1 py -m migration.mysql.ddl --snapshot ~/.bstats/snapshots/d1_20261002.db`
Run: `git diff --stat`
Expected: 바뀐 파일은 `migration/mysql/schema_post.sql`, `docs/mysql-migration/schema-report.md` 둘뿐입니다. `schema_post.sql` 에 `CREATE INDEX` 14줄이 늘었습니다(공용 13 + `idx_pbp_game_date`). Step 2 에서 더 나온 인덱스가 있으면 그만큼 더 늡니다.

**`schema.sql` 이나 `schema_types.json` 이 바뀌었으면 멈춥니다.** 같은 데이터에서 열 정의가 달라질 이유가 없으므로 원인을 먼저 찾습니다.

- [ ] **Step 4: MySQL 에 만들기**

Run: `BSTATS_MYSQL_SETTINGS=~/.bstats/mysql_proxy.json PYTHONUTF8=1 py -m migration.mysql.load --post-only`
Expected: `후처리: 이미 있어 건너뜁니다 …` 가 기존 10개, `후처리: CREATE INDEX …` 가 새 14개, 끝에 `후처리 완료`.

- [ ] **Step 5: 모두 있는지 확인**

Run: `BSTATS_MYSQL_SETTINGS=~/.bstats/mysql_proxy.json PYTHONUTF8=1 py -m migration.mysql.verify --objects-only`
Expected: `개체 모두 있음`

- [ ] **Step 6: 커밋**

```bash
git add migration/mysql/schema_post.sql docs/mysql-migration/schema-report.md
git commit -m "feat(mysql): 공용 인덱스 13개와 idx_pbp_game_date 를 스키마에 반영·적용

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## 마무리

- [ ] 전체 테스트: 알려진 2개 외 실패 0.
- [ ] 로드맵의 "1단계 보강" 목록에서 1·3번을 완료로, 2·4번을 "보류(전체 재이전 때)"로 고칩니다.
- [ ] evan 에게 push·병합 여부를 묻습니다.
