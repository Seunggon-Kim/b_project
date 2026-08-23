# -*- coding: utf-8 -*-
"""전량 내려받기용 CSV 를 지킵니다.

이 기능이 존재하는 이유가 **조용한 절단** 때문입니다. Workers 에서
큰 표를 스트리밍하면 오류 없이 중간에 끊기고, 사용자는 잘린 파일을
전량으로 알고 분석에 씁니다.

그런데 이 스크립트를 처음 쓸 때 **똑같은 고장을 냈습니다.**

    with gzip.open(path, "wb") as gz:
        w = csv.writer(io.TextIOWrapper(gz, ...))   # 참조를 안 들고 있음

`with` 를 빠져나갈 때 gz 가 먼저 닫히고 래퍼의 텍스트 버퍼가 사라져
파일마다 끝 4~18행이 잘렸습니다. 형식은 멀쩡했습니다. 모든 행이
74필드였고 gzip 도 정상이었습니다. **되읽어 세 보기 전에는 알 수
없었습니다.** 쓴 횟수를 세는 검사는 이걸 못 잡습니다. 버퍼가 날아가도
쓴 횟수는 그대로이기 때문입니다.

그래서 여기서 지키는 것은 하나입니다. **쓴 만큼 파일에 들어갔는가.**
"""
import ast
import csv
import gzip
import importlib.util
import io
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "migration" / "export_csv.py"


def mod():
    spec = importlib.util.spec_from_file_location("excsv", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["excsv"] = m
    spec.loader.exec_module(m)
    return m


def sample_db(path, rows):
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE t (id INTEGER, name TEXT, note TEXT)")
    con.executemany("INSERT INTO t VALUES (?,?,?)", rows)
    con.commit()
    return con


# ------------------------------------------------ 꼬리가 잘리지 않습니다

def test_쓴_만큼_파일에_들어갑니다(tmp_path):
    """버퍼가 날아가면 여기서 걸립니다."""
    m = mod()
    n = 5000
    con = sample_db(tmp_path / "a.db",
                    [(i, "이름%d" % i, "설명 " * 20) for i in range(n)])
    p = tmp_path / "out.csv.gz"
    wrote = m.write_gz(p, con.execute("SELECT * FROM t"))
    con.close()
    assert wrote == n
    assert m.count_gz(p) == n, "파일에 들어간 행이 모자랍니다(꼬리 잘림)"


def test_마지막_행이_그대로_있습니다(tmp_path):
    m = mod()
    n = 3000
    con = sample_db(tmp_path / "b.db", [(i, "n%d" % i, "x" * 50)
                                        for i in range(n)])
    p = tmp_path / "b.csv.gz"
    m.write_gz(p, con.execute("SELECT * FROM t ORDER BY id"))
    con.close()
    with gzip.open(p, "rb") as gz:
        r = csv.reader(io.TextIOWrapper(gz, encoding="utf-8", newline=""))
        next(r)
        last = None
        for row in r:
            last = row
    assert last[0] == str(n - 1), "마지막 행이 %s 입니다" % (last and last[0])


def test_되읽기_검사가_쓴_횟수가_아니라_파일을_봅니다():
    src = SRC.read_text(encoding="utf-8")
    assert "def count_gz(" in src, "파일을 되읽는 함수가 없습니다"
    assert "check(p, wrote)" in src, "만들 때마다 검사하지 않습니다"


def test_래퍼를_flush_하고_detach_합니다():
    """이 두 줄이 빠지면 꼬리가 잘립니다. 못을 박아 둡니다."""
    src = SRC.read_text(encoding="utf-8")
    body = src[src.index("def write_gz("):src.index("def count_gz(")]
    assert "text.flush()" in body
    assert "text.detach()" in body
    assert body.index("text.flush()") < body.index("text.detach()"), \
        "flush 가 detach 보다 먼저여야 합니다"


# ---------------------------------------------------------- 대상 고르기

def test_작은_표는_만들지_않습니다(tmp_path):
    """2만 행 미만은 화면에서 바로 받아집니다."""
    m = mod()
    con = sample_db(tmp_path / "c.db", [(i, "n", "x") for i in range(10)])
    made = m.export_table(con, "t", tmp_path / "out")
    con.close()
    assert made == []


def test_상한이_화면과_같습니다():
    """서로 다르면 화면은 413 을 내는데 파일은 없는 표가 생깁니다."""
    m = mod()
    js = (ROOT / "src" / "routes" / "dbexplorer.js").read_text(
        encoding="utf-8")
    import re
    n = int(re.search(r"CSV_MAX_ROWS = (\d+)", js).group(1))
    assert m.CSV_MAX_ROWS == n, "파이썬 %d / 화면 %d" % (m.CSV_MAX_ROWS, n)


def test_백업_표는_내보내지_않습니다(tmp_path):
    m = mod()
    con = sqlite3.connect(str(tmp_path / "d.db"))
    for t in ("keep", "keep_bak", "_cf_KV"):
        con.execute('CREATE TABLE "%s" (a INT)' % t)
    con.commit()
    got = m.tables(con)
    con.close()
    assert got == ["keep"]


def test_행_수가_안_맞으면_멈춥니다(tmp_path):
    """시즌이 NULL 인 행이 있으면 파일 합계가 모자랍니다."""
    m = mod()
    con = sqlite3.connect(str(tmp_path / "e.db"))
    con.execute("CREATE TABLE play_by_play (game_date INT, v TEXT)")
    con.executemany("INSERT INTO play_by_play VALUES (?,?)",
                    [(20250101, "x")] * 30001 + [(None, "x")])
    con.commit()
    with pytest.raises(RuntimeError, match="행"):
        m.export_table(con, "play_by_play", tmp_path / "out")
    con.close()


def test_문법이_성립합니다():
    ast.parse(SRC.read_text(encoding="utf-8"))


# ------------------------------------------------------------ 화면 안내

def test_화면이_내려받기_주소를_알려_줍니다():
    js = (ROOT / "src" / "routes" / "dbexplorer.js").read_text(
        encoding="utf-8")
    assert "DOWNLOAD_URL" in js
    assert "releases/tag/data-latest" in js
    assert "download: DOWNLOAD_URL" in js, "413 응답에 주소가 없습니다"


def test_주간_워크플로가_만들고_올립니다():
    import re
    s = re.sub(r"\\\s*\n\s*", " ",
               (ROOT / ".github" / "workflows" / "weekly.yml").read_text(
                   encoding="utf-8"))
    assert "export_csv.py" in s, "CSV 를 만들지 않습니다"
    assert "gh release upload" in s, "Releases 에 올리지 않습니다"
    assert "--clobber" in s, "자산을 갈아 끼우지 않으면 두 번째부터 실패합니다"
    assert s.index("export_csv.py") < s.index("gh release upload")
