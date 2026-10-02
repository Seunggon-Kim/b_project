import collections
import sqlite3
import sys

import pymysql
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


class FailingCursor:
    def __init__(self, fail_on_call=2):
        self.log = []
        self.call_count = 0
        self.fail_on_call = fail_on_call

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def executemany(self, sql, rows):
        self.call_count += 1
        if self.call_count == self.fail_on_call:
            raise RuntimeError("boom")
        self.log.append((sql, list(rows)))


class FailingConn:
    def __init__(self):
        self.cursor_obj = FailingCursor()
        self.commits = 0

    def cursor(self):
        return self.cursor_obj

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


def test_load_table_writes_rowid_as_renumbered_id():
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
    assert sql == ("INSERT INTO `play_by_play` (`pbp_id`, `batter_ID`, `px`) "
                   "VALUES (%s, %s, %s)")
    assert first == [(1, 1, 0.5), (2, 2, None)]
    assert my.log[1][1] == [(3, 3, 1.0)]
    assert my.commits == 2


def test_orphan_queries_parse_post_sql():
    post = ("CREATE INDEX `i` ON `t` (`a`);\n"
            "ALTER TABLE `players` ADD CONSTRAINT `fk_players_team_id` FOREIGN KEY "
            "(`team_id`) REFERENCES `teams` (`team_id`);\n")
    (label, sql), = load.orphan_queries(post)
    assert label == "players.team_id → teams.team_id"
    assert "LEFT JOIN `teams` p ON c.`team_id` = p.`team_id`" in sql
    assert "p.`team_id` IS NULL" in sql


def test_session_setup_keeps_zero_ids():
    assert "NO_AUTO_VALUE_ON_ZERO" in " ".join(load.SESSION_SETUP)
    assert "SET FOREIGN_KEY_CHECKS=0" in load.SESSION_SETUP


def test_load_table_names_table_and_rows_on_failure():
    sq = sqlite3.connect(":memory:")
    sq.execute('CREATE TABLE t (a INTEGER)')
    sq.executemany("INSERT INTO t VALUES (?)", [(1,), (2,), (3,)])
    spec = {"columns": [["a", "int"]], "renumber": None}
    my = FailingConn()
    fixes = collections.Counter()
    try:
        load.load_table(sq, my, "t", spec, fixes, batch=2)
        assert False, "Expected RuntimeError"
    except RuntimeError as e:
        assert "t: 2행을 넣은 뒤 멈췄습니다" in str(e)
        assert "boom" in str(e)


def test_orphan_queries_rejects_unreadable_fk():
    post = "ALTER TABLE t ADD FOREIGN KEY (a) REFERENCES p (b);\n"
    with pytest.raises(ValueError, match="외래키"):
        load.orphan_queries(post)


def test_fresh_and_tables_cannot_be_combined(monkeypatch):
    monkeypatch.setattr(sys, "argv",
                        ["load", "--snapshot", "x.db", "--fresh", "--tables", "a"])
    with pytest.raises(SystemExit):
        load.main()


# --- 연결이 끊겼을 때 묶음 단위로 다시 시도 -------------------------------

class RetryCursor:
    """SESSION_SETUP·SELECT COUNT(*)·executemany 를 받는 가짜 커서입니다."""

    def __init__(self, conn):
        self.conn = conn
        self.row = None
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, args=None):
        self.conn.executed.append(sql)
        if sql.startswith("SELECT COUNT(*)"):
            self.row = (self.conn.count,)
        elif "information_schema.PROCESSLIST" in sql:
            c = self.conn
            self.rows = c.processlists.pop(0) if c.processlists else []
        elif sql.startswith("KILL ") and self.conn.kill_error:
            raise self.conn.kill_error

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows

    def executemany(self, sql, rows):
        c = self.conn
        c.calls += 1
        if c.fail_always or c.calls in c.fail_calls:
            raise c.error
        c.log.append((sql, list(rows)))


class RetryConn:
    """executemany·commit 이 정해진 횟수에 실패하는 가짜 연결입니다.

    fail_calls: 실패할 executemany 호출 번호(1부터). fail_always: 항상 실패.
    commit_fail_on: 실패할 commit 호출 번호(서버엔 들어갔는데 응답을 못 받은 경우).
    ping_errors: ping 이 차례로 던질 오류 목록(다 쓰면 성공).
    """

    def __init__(self, count=0, fail_calls=(), fail_always=False,
                 commit_fail_on=(), error=None, ping_errors=(),
                 processlists=(), kill_error=None):
        self.log = []
        self.executed = []
        self.pings = []
        self.calls = 0
        self.commits = 0
        self.count = count
        self.fail_calls = set(fail_calls)
        self.fail_always = fail_always
        self.commit_fail_on = set(commit_fail_on)
        self.error = error or pymysql.err.OperationalError(2006, "gone away")
        self.ping_errors = list(ping_errors)
        self.processlists = [list(p) for p in processlists]   # PROCESSLIST 질의마다 차례로 답합니다
        self.kill_error = kill_error

    def cursor(self):
        return RetryCursor(self)

    def commit(self):
        self.commits += 1
        if self.commits in self.commit_fail_on:
            raise pymysql.err.OperationalError(2013, "lost connection")

    def ping(self, reconnect=True):
        self.pings.append(reconnect)
        if self.ping_errors:
            raise self.ping_errors.pop(0)


@pytest.fixture
def sleeps(monkeypatch):
    """다시 시도 사이의 기다림을 건너뛰고, 기다리려던 초를 모읍니다."""
    waited = []
    monkeypatch.setattr(load, "_sleep", waited.append)
    return waited


def _three_rows():
    sq = sqlite3.connect(":memory:")
    sq.execute('CREATE TABLE t (a INTEGER)')
    sq.executemany("INSERT INTO t VALUES (?)", [(1,), (2,), (3,)])
    return sq, {"columns": [["a", "int"]], "renumber": None}


def _batches(my):
    return [rows for _, rows in my.log]


def test_retry_after_drop_reinserts_uncommitted_batch(sleeps):
    sq, spec = _three_rows()
    my = RetryConn(count=0, fail_calls={1})
    n = load.load_table(sq, my, "t", spec, collections.Counter(), batch=2)
    assert n == 3
    assert my.pings == [True]
    assert [s for s in my.executed if s in load.SESSION_SETUP] == list(load.SESSION_SETUP)
    assert "SELECT COUNT(*) FROM `t`" in my.executed
    assert _batches(my) == [[(1,), (2,)], [(3,)]]
    assert sleeps == [5]


def test_retry_skips_batch_already_committed(sleeps):
    sq, spec = _three_rows()
    my = RetryConn(count=2, commit_fail_on={1})
    n = load.load_table(sq, my, "t", spec, collections.Counter(), batch=2)
    assert n == 3
    assert my.pings == [True]
    assert my.calls == 2
    assert _batches(my) == [[(1,), (2,)], [(3,)]]


def test_retry_gives_up_after_eight_with_backoff(sleeps):
    sq, spec = _three_rows()
    my = RetryConn(count=0, fail_always=True)
    with pytest.raises(RuntimeError, match="t: 0행을 넣은 뒤 멈췄습니다") as ei:
        load.load_table(sq, my, "t", spec, collections.Counter(), batch=2)
    assert len(my.pings) == 8
    assert my.calls == 9
    assert sleeps == [5, 10, 20, 40, 60, 60, 60, 60]
    assert isinstance(ei.value.__cause__, pymysql.err.OperationalError)


def test_non_retryable_error_fails_immediately(sleeps):
    sq, spec = _three_rows()
    my = RetryConn(fail_always=True, error=pymysql.err.IntegrityError(1062, "dup"))
    with pytest.raises(RuntimeError, match="t: 0행을 넣은 뒤 멈췄습니다") as ei:
        load.load_table(sq, my, "t", spec, collections.Counter(), batch=2)
    assert my.pings == []
    assert my.calls == 1
    assert sleeps == []
    assert isinstance(ei.value.__cause__, pymysql.err.IntegrityError)


def test_unknown_state_raises(sleeps):
    sq, spec = _three_rows()
    my = RetryConn(count=1, fail_calls={1})
    with pytest.raises(RuntimeError, match="t: 0행을 넣은 뒤 멈췄습니다"):
        load.load_table(sq, my, "t", spec, collections.Counter(), batch=2)
    assert my.calls == 1
    assert my.log == []


def test_retry_message_names_rows_already_in(sleeps, capsys):
    sq, spec = _three_rows()
    my = RetryConn(count=2, fail_calls={2})
    n = load.load_table(sq, my, "t", spec, collections.Counter(), batch=2)
    assert n == 3
    assert "   t: 연결이 끊겨 1번째 다시 시도합니다(2행까지 들어감)\n" in capsys.readouterr().out
    assert _batches(my) == [[(1,), (2,)], [(3,)]]


def test_reconnect_failure_counts_as_a_retry(sleeps):
    sq, spec = _three_rows()
    my = RetryConn(count=0, fail_calls={1},
                   ping_errors=[pymysql.err.OperationalError(2003, "can't connect")])
    n = load.load_table(sq, my, "t", spec, collections.Counter(), batch=2)
    assert n == 3
    assert len(my.pings) == 2
    assert sleeps == [5, 10]
    assert _batches(my) == [[(1,), (2,)], [(3,)]]


def test_retry_on_renumbered_table_reuses_same_ids(sleeps):
    sq = sqlite3.connect(":memory:")
    sq.execute('CREATE TABLE play_by_play (pbp_id INTEGER, batter_ID TEXT)')
    sq.executemany("INSERT INTO play_by_play VALUES (?,?)",
                   [(7, "10"), (7, "20"), (7, "30")])
    spec = {"columns": [["pbp_id", "int"], ["batter_ID", "int"]], "renumber": "pbp_id"}
    my = RetryConn(count=0, fail_calls={1})
    n = load.load_table(sq, my, "play_by_play", spec, collections.Counter(), batch=2)
    assert n == 3
    assert my.pings == [True]
    assert [[r[0] for r in rows] for rows in _batches(my)] == [[1, 2], [3]]
    assert _batches(my) == [[(1, 10), (2, 20)], [(3, 30)]]


def test_retry_kills_stale_sessions_before_count(sleeps, capsys):
    sq, spec = _three_rows()
    my = RetryConn(count=0, fail_calls={1}, processlists=[[(77,)], []])
    n = load.load_table(sq, my, "t", spec, collections.Counter(), batch=2)
    assert n == 3
    assert "KILL 77" in my.executed
    assert my.executed.index("KILL 77") < my.executed.index("SELECT COUNT(*) FROM `t`")
    assert _batches(my) == [[(1,), (2,)], [(3,)]]
    assert "   t: 끊긴 이전 연결 1개를 정리했습니다\n" in capsys.readouterr().out


def test_lock_wait_timeout_is_retryable(sleeps):
    sq, spec = _three_rows()
    my = RetryConn(count=0, fail_calls={1},
                   error=pymysql.err.OperationalError(1205, "Lock wait timeout exceeded"))
    n = load.load_table(sq, my, "t", spec, collections.Counter(), batch=2)
    assert n == 3
    assert my.pings == [True]
    assert _batches(my) == [[(1,), (2,)], [(3,)]]


def test_kill_ignores_unknown_thread(sleeps):
    sq, spec = _three_rows()
    my = RetryConn(count=0, fail_calls={1}, processlists=[[(77,)], []],
                   kill_error=pymysql.err.OperationalError(1094, "Unknown thread id: 77"))
    n = load.load_table(sq, my, "t", spec, collections.Counter(), batch=2)
    assert n == 3
    assert _batches(my) == [[(1,), (2,)], [(3,)]]


def test_is_retryable():
    assert load.is_retryable(pymysql.err.OperationalError(2006, "gone away"))
    assert load.is_retryable(pymysql.err.InterfaceError(2013, "lost"))
    assert load.is_retryable(pymysql.err.OperationalError(1205, "lock wait"))
    assert load.is_retryable(pymysql.err.OperationalError(1213, "deadlock"))
    assert not load.is_retryable(pymysql.err.IntegrityError(1062, "dup"))
    assert not load.is_retryable(pymysql.err.DataError(1264, "out of range"))
    assert load.is_retryable(ConnectionResetError())
    assert load.is_retryable(TimeoutError())
    assert load.is_retryable(OSError())
    assert not load.is_retryable(ValueError())


# --- 이어서 넣기(--resume) -------------------------------------------------

class ResumeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, args=None):
        c = self.conn
        c.executed.append((sql, args))
        if sql.startswith("SELECT COALESCE(MAX("):
            self.row = (c.max, c.count)
        elif sql.startswith("SELECT COUNT(*) FROM `"):
            self.row = (c.count,)
        elif "information_schema.STATISTICS" in sql:
            self.row = (1 if ("index",) + tuple(args) in c.existing else 0,)
        elif "information_schema.TABLE_CONSTRAINTS" in sql:
            self.row = (1 if ("fk",) + tuple(args) in c.existing else 0,)

    def fetchone(self):
        return self.row

    def executemany(self, sql, rows):
        self.conn.inserts.append((sql, list(rows)))


class ResumeConn:
    def __init__(self, max_id=0, count=0, existing=()):
        self.max = max_id
        self.count = count
        self.existing = set(existing)
        self.executed = []
        self.inserts = []
        self.commits = 0

    def cursor(self):
        return ResumeCursor(self)

    def commit(self):
        self.commits += 1


def _pbp(n):
    sq = sqlite3.connect(":memory:")
    sq.execute('CREATE TABLE play_by_play (pbp_id INTEGER, batter_ID TEXT)')
    sq.executemany("INSERT INTO play_by_play VALUES (?,?)",
                   [(9, str(i * 10)) for i in range(1, n + 1)])
    return sq, {"columns": [["pbp_id", "int"], ["batter_ID", "int"]],
                "renumber": "pbp_id"}


def test_resume_cannot_combine_with_fresh_or_tables(monkeypatch):
    def boom():
        raise AssertionError("연결하면 안 됩니다")
    monkeypatch.setattr(load.myconn, "connect", boom)
    for extra in (["--fresh"], ["--tables", "a"]):
        monkeypatch.setattr(sys, "argv",
                            ["load", "--snapshot", "없는파일.db", "--resume"] + extra)
        with pytest.raises(SystemExit) as ei:
            load.main()
        assert ei.value.code == 2


def test_resume_renumbered_loads_only_rows_after_max(sleeps):
    sq, spec = _pbp(5)
    my = ResumeConn(max_id=3, count=3)
    n = load.resume_table(sq, my, "play_by_play", spec, collections.Counter(), batch=10)
    assert n == 5
    (sql, rows), = my.inserts
    assert rows == [(4, 40), (5, 50)]
    assert "TRUNCATE" not in " ".join(e[0] for e in my.executed)


def test_resume_renumbered_batches_keep_counter(sleeps, capsys):
    sq, spec = _pbp(5)
    my = ResumeConn(max_id=3, count=3)
    load.resume_table(sq, my, "play_by_play", spec, collections.Counter(), batch=1)
    assert [rows for _, rows in my.inserts] == [[(4, 40)], [(5, 50)]]


def test_resume_refuses_gaps(sleeps):
    sq, spec = _pbp(5)
    my = ResumeConn(max_id=4, count=3)
    with pytest.raises(SystemExit, match="이어서 넣을 수 없습니다"):
        load.resume_table(sq, my, "play_by_play", spec, collections.Counter())
    assert my.inserts == []


def test_resume_small_table_equal_counts_is_skipped(capsys):
    sq, spec = _three_rows()
    my = ResumeConn(count=3)
    n = load.resume_table(sq, my, "t", spec, collections.Counter())
    assert n == 3
    assert my.inserts == []
    assert not any("TRUNCATE" in e[0] for e in my.executed)
    assert "t: 이미 다 들어 있어 건너뜁니다" in capsys.readouterr().out


def test_resume_small_table_different_counts_truncates_and_reloads():
    sq, spec = _three_rows()
    my = ResumeConn(count=1)
    n = load.resume_table(sq, my, "t", spec, collections.Counter(), batch=10)
    assert n == 3
    assert any(e[0] == "TRUNCATE TABLE `t`" for e in my.executed)
    assert my.inserts[0][1] == [(1,), (2,), (3,)]


def test_post_object_parses_both_kinds():
    assert load.post_object(
        "CREATE INDEX `idx_players_team` ON `players` (`team_id`)") == \
        ("index", "players", "idx_players_team")
    assert load.post_object(
        "CREATE UNIQUE INDEX `uq_x_1` ON `x` (`a`, `b`)") == ("index", "x", "uq_x_1")
    assert load.post_object(
        "ALTER TABLE `p` ADD CONSTRAINT `fk_p_t` FOREIGN KEY (`t`) "
        "REFERENCES `teams` (`team_id`)") == ("fk", "p", "fk_p_t")
    with pytest.raises(ValueError):
        load.post_object("DROP TABLE `x`")


def test_apply_post_skipping_existing_runs_only_missing():
    post = ("CREATE INDEX `i1` ON `a` (`x`);\n"
            "CREATE INDEX `i2` ON `a` (`y`);\n"
            "ALTER TABLE `a` ADD CONSTRAINT `f1` FOREIGN KEY (`x`) REFERENCES `b` (`x`);\n"
            "ALTER TABLE `a` ADD CONSTRAINT `f2` FOREIGN KEY (`y`) REFERENCES `b` (`y`);\n")
    my = ResumeConn(existing={("index", "a", "i1"), ("fk", "a", "f1")})
    with my.cursor() as cur:
        load.apply_post_skipping_existing(cur, post)
    ran = [e[0] for e in my.executed if not e[0].startswith("SELECT")]
    assert ran == ["CREATE INDEX `i2` ON `a` (`y`)",
                   "ALTER TABLE `a` ADD CONSTRAINT `f2` FOREIGN KEY (`y`) "
                   "REFERENCES `b` (`y`)"]
    checks = [e for e in my.executed if e[0].startswith("SELECT")]
    assert len(checks) == 4 and checks[0][1] == ("a", "i1")
