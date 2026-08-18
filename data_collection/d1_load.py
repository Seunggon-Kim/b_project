# -*- coding: utf-8 -*-
"""D1 에 직접 넣을 때 쓰는 공통 조각입니다.

수집 스크립트들이 저마다 SQL 을 만들면 같은 실수를 여러 번 합니다.
실제로 `daily_pbp_to_d1.py` 에서 문 길이를 **글자 수**로 세는 버그가
있었습니다. 한글은 UTF-8 로 3바이트라 문 하나가 108,774바이트가 되어
D1 한도 100,000 을 넘었고, wrangler 가 `D1_RESET_DO` 로 실패했습니다.
그런 계산은 한 곳에만 두는 편이 안전합니다.

GitHub Actions 러너에는 `database/kbo_stats.db` 가 없습니다. 226MB 라
git 에 두지 않기 때문입니다. 그래서 수집한 값을 로컬 SQLite 를 거치지
않고 바로 D1 에 넣습니다.
"""
import json
import subprocess
import sys

DB_NAME = "kbo-stats"

# D1 문 하나의 상한은 100,000 바이트입니다. 여유를 두고 자릅니다.
MAX_STATEMENT_BYTES = 90_000


def sql_literal(v):
    """값 하나를 SQL 리터럴로 만듭니다.

    CSV 는 모든 값이 문자열입니다. 빈 칸은 NULL 로, 나머지는 문자열로
    넣습니다. 숫자로 바꾸지 않는 이유가 있습니다. **컬럼 타입은 D1 이
    알고 있고 SQLite 는 문자열을 알아서 변환합니다.** 여기서 추측해
    바꾸면 `007` 같은 값이 7 이 되어 원본과 달라집니다.
    """
    if v is None:
        return "NULL"
    s = str(v)
    # 크롤러가 없는 값을 '-' 로 씁니다. 그대로 넣으면 숫자 컬럼에
    # 문자열 '-' 가 들어가 계산이 어긋납니다.
    if s == "" or s == "-":
        return "NULL"
    return "'" + s.replace("'", "''") + "'"


def _row_piece(row, columns):
    return "(" + ",".join(sql_literal(row.get(c)) for c in columns) + ")"


def _batched(head, tail, pieces, max_bytes):
    """조각들을 바이트 한도에 맞춰 문 여러 개로 나눕니다.

    **글자 수가 아니라 바이트로 셉니다.** 선수 이름과 상황 서술이
    한글이라 UTF-8 로 세 배가 됩니다.
    """
    fixed = len(head.encode("utf-8")) + len(tail.encode("utf-8"))
    out, batch, size = [], [], 0
    for piece in pieces:
        n = len(piece.encode("utf-8"))
        # 한 행이라도 넣고 나서 크기를 봅니다. 빈 배치를 내보내면
        # 문법 오류가 됩니다.
        if batch and size + n + 1 > max_bytes - fixed:
            out.append(head + ",".join(batch) + tail)
            batch, size = [], 0
        batch.append(piece)
        size += n + 1
    if batch:
        out.append(head + ",".join(batch) + tail)
    return out


def build_inserts(table, columns, rows, max_bytes=MAX_STATEMENT_BYTES):
    """행 목록을 INSERT 문 여러 개로 나눕니다."""
    if not rows:
        return []
    head = 'INSERT INTO "%s" (%s) VALUES ' % (
        table, ",".join('"%s"' % c for c in columns))
    pieces = (_row_piece(r, columns) for r in rows)
    return _batched(head, ";", pieces, max_bytes)


def build_upserts(table, columns, keys, rows, touch=None, keep=(),
                  max_bytes=MAX_STATEMENT_BYTES):
    """행 목록을 UPSERT(있으면 갱신) 문 여러 개로 나눕니다.

    공식 통계는 시즌 내내 같은 (player_id, season) 이 매일 갱신됩니다.
    지웠다 넣으면 그 사이에 표가 비어 화면이 깨지고, 쓰기도 두 배로
    계상됩니다. ON CONFLICT 로 제자리 갱신합니다.

    touch 는 갱신할 때 `datetime('now')` 로 채울 컬럼입니다
    (보통 updated_at).

    keep 은 넣을 때만 쓰고 갱신할 때는 건드리지 않을 컬럼입니다
    (보통 created_at). 이게 없으면 매일 갱신할 때마다 최초 등록 시각이
    오늘로 덮여 "언제부터 있던 선수인지"를 잃습니다.
    """
    if not rows:
        return []
    # touch 컬럼을 여기서 빼야 합니다. 빼지 않으면 SET 절에 같은 컬럼이
    # 두 번(`=excluded.x` 와 `=datetime('now')`) 들어가 SQLite 가
    # "duplicate column name" 으로 거부합니다.
    keyset = set(keys) | set(keep) | ({touch} if touch else set())
    updatable = [c for c in columns if c not in keyset]
    if not updatable:
        raise ValueError("갱신할 컬럼이 없습니다: %s" % table)

    head = 'INSERT INTO "%s" (%s) VALUES ' % (
        table, ",".join('"%s"' % c for c in columns))
    sets = ['"%s"=excluded."%s"' % (c, c) for c in updatable]
    if touch:
        sets.append('"%s"=datetime(\'now\')' % touch)
    tail = " ON CONFLICT(%s) DO UPDATE SET %s;" % (
        ",".join('"%s"' % k for k in keys), ",".join(sets))
    pieces = (_row_piece(r, columns) for r in rows)
    return _batched(head, tail, pieces, max_bytes)


def run_d1(sql, json_out=False, db_name=DB_NAME):
    cmd = ["npx", "--yes", "wrangler@4", "d1", "execute", db_name,
           "--remote", "--command", sql, "--yes"]
    if json_out:
        cmd.append("--json")
    r = subprocess.run(cmd, capture_output=True, text=True, shell=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("wrangler 실패: %s" % (r.stderr or r.stdout)[:400])
    return r.stdout


def run_d1_file(path, db_name=DB_NAME):
    cmd = ["npx", "--yes", "wrangler@4", "d1", "execute", db_name,
           "--remote", "--file", str(path), "--yes"]
    r = subprocess.run(cmd, capture_output=True, text=True, shell=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("wrangler 실패: %s" % (r.stderr or r.stdout)[:400])
    return r.stdout


def query(sql, db_name=DB_NAME):
    """SELECT 결과를 dict 목록으로 돌려줍니다."""
    out = run_d1(sql, json_out=True, db_name=db_name)
    # wrangler 가 배너를 먼저 찍으므로 JSON 시작 지점부터 읽습니다.
    data = json.loads(out[out.find("["):])
    return data[0]["results"]


def d1_columns(table, db_name=DB_NAME):
    """D1 의 실제 컬럼 순서를 읽습니다.

    CSV 헤더를 그대로 믿지 않습니다. 크롤러가 컬럼을 더하거나 순서를
    바꿔도 D1 스키마가 정본입니다. 다른 컬럼을 넣으려 하면 적재가
    통째로 실패합니다.
    """
    return [r["name"] for r in query('PRAGMA table_info("%s");' % table,
                                     db_name=db_name)]


def refresh_count(table, db_name=DB_NAME):
    """meta_table_counts 를 갱신합니다.

    빠뜨리면 데이터 탐색기가 어제 행 수를 계속 보여 줍니다
    (src/lib/counts.js).
    """
    run_d1("INSERT OR REPLACE INTO meta_table_counts "
           "SELECT '%s', COUNT(*), datetime('now') FROM \"%s\";"
           % (table, table), db_name=db_name)


def purge_cache(base_url, token):
    """Worker 캐시를 비웁니다.

    적재만 하고 비우지 않으면 캐시가 만료될 때까지(기본 한 시간) 화면이
    어제 숫자를 보여 줍니다. 2026 시즌을 넣었을 때 실제로 겪었습니다.
    """
    import urllib.request
    import urllib.error
    req = urllib.request.Request(
        base_url.rstrip("/") + "/admin/purge-cache", method="POST")
    req.add_header("Authorization", "Bearer " + token)
    # Cloudflare 엣지가 Python-urllib UA 를 1010 으로 막습니다.
    req.add_header("User-Agent", "Mozilla/5.0 (compatible; kbo-actions)")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8")[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")[:200]


def _self_test():
    """자체 점검입니다. `py data_collection/d1_load.py` 로 돌립니다.

    여기 걸린 두 가지는 실제로 났던 버그입니다. 다시 나면 여기서
    먼저 걸립니다.
    """
    import sqlite3

    ok = True

    # 1. 한글이 섞여도 문 하나가 100,000 바이트를 넘지 않아야 합니다.
    rows = [{"a": "가" * 100, "b": i} for i in range(500)]
    big = max(len(s.encode("utf-8"))
              for s in build_inserts("t", ["a", "b"], rows))
    big2 = max(len(s.encode("utf-8"))
               for s in build_upserts("t", ["a", "b"], ["b"], rows,
                                      touch="updated_at"))
    print("최대 문 크기  INSERT %s / UPSERT %s 바이트 (한도 100,000)"
          % (format(big, ","), format(big2, ",")))
    if big >= 100_000 or big2 >= 100_000:
        print("  실패: 한도를 넘습니다")
        ok = False

    # 2. UPSERT 가 실제 SQLite 에서 의도대로 동작해야 합니다.
    #    같은 컬럼이 SET 절에 두 번 들어가면 여기서 예외가 납니다.
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (a TEXT, b INTEGER, v TEXT, "
                 "created_at TEXT, updated_at TEXT, PRIMARY KEY(a,b))")
    cols = ["a", "b", "v", "created_at", "updated_at"]
    old = {"a": "x", "b": "1", "v": "처음",
           "created_at": "2020-01-01 00:00:00",
           "updated_at": "2020-01-01 00:00:00"}
    new = dict(old, v="나중", created_at="2030-09-09 00:00:00",
               updated_at="2030-09-09 00:00:00")
    for batch in (old, new):
        for s in build_upserts("t", cols, ["a", "b"], [batch],
                               touch="updated_at", keep=["created_at"]):
            conn.execute(s)
    n, v, created = conn.execute(
        "SELECT COUNT(*), MAX(v), MAX(created_at) FROM t").fetchone()
    print("UPSERT  행 %d개, v=%s, created_at=%s" % (n, v, created))
    if n != 1 or v != "나중" or not created.startswith("2020"):
        print("  실패: 갱신이 의도와 다릅니다")
        ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_self_test())
