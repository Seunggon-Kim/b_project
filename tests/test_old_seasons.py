# -*- coding: utf-8 -*-
"""1982년까지 거슬러 받을 때 조용히 비지 않게 막습니다.

옛 시즌을 받으면서 두 가지가 드러났습니다. 둘 다 오류 없이 0행이
나오는 종류입니다.

## 1. 팀 목록을 하드코딩하면 안 됩니다

리그는 6팀으로 시작해 지금 10팀입니다.

    1982~1985   6팀   삼미(HD) 있음, KT·NC·키움·SK 없음
    1991~1999   8팀   쌍방울(SB) 있음
    2015~       10팀

현재 10팀으로 1982 를 돌면 삼미 선수가 통째로 빠지고 없는 팀 넷을
헛돕니다.

## 2. Basic2·Detail 에서는 시즌을 바꿔도 팀 목록이 안 바뀝니다

Basic2 에서 1982 를 골라도 팀 드롭다운은 현재 10팀 그대로입니다.
거기에 HD 가 없으니 **조용히 0행**이 나옵니다. 실제로 HD 는 전
시즌 Basic2 가 비었고, 2015~2026 만 받을 때는 팀 구성이 안 바뀌어
눈에 띄지 않았습니다.

화면에서 사람은 Basic1 에서 시작해 '다음' 으로 넘어갑니다. 같은
순서를 따라야 선택 상태가 이어집니다.
"""
import ast
import json
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HTTP = ROOT / "data_collection" / "kbo_http.py"
COLLECT = ROOT / "data_collection" / "official_stats_http.py"
FRANCHISE = ROOT / "migration" / "build_franchises.py"
CACHE = ROOT / "migration" / "teams_by_season.json"


def const(path, name):
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    pytest.fail("%s 에서 %s 를 찾지 못했습니다" % (path.name, name))


# ------------------------------------------- 팀 목록을 시즌에서 읽습니다

def test_수집기가_시즌별_팀_목록을_읽습니다():
    src = COLLECT.read_text(encoding="utf-8")
    assert "def team_codes(" in src, "시즌별 팀 목록 함수가 없습니다"
    assert "codes = team_codes(year" in src, (
        "collect 가 하드코딩된 TEAM_CODES 를 그대로 돕니다. "
        "1982 에서 삼미가 빠집니다.")


def test_팀_목록을_못_읽으면_알립니다():
    """조용히 현재 10팀으로 돌면 옛 팀이 빠진 줄 모릅니다."""
    src = COLLECT.read_text(encoding="utf-8")
    body = src[src.index("def team_codes("):src.index("BATTER_MAP")]
    assert body.count("[경고]") >= 2, "실패를 알리지 않습니다"


# ---------------------------------- Basic1 을 거쳐야 선택이 이어집니다

def test_표를_받을_때_Basic1_을_거칩니다():
    src = HTTP.read_text(encoding="utf-8")
    body = src[src.index("def fetch_table("):]
    assert 'entry = page.split("/")[0] + "/Basic1.aspx"' in body, (
        "Basic2·Detail 에서 바로 시즌을 고르면 팀 목록이 안 바뀌어 "
        "옛 팀이 조용히 0행이 됩니다.")
    assert "if page != entry:" in body, "목표 페이지로 넘어가지 않습니다"


def test_시즌과_팀을_따로_보냅니다():
    """시즌을 바꾸면 팀 선택이 초기화됩니다."""
    src = HTTP.read_text(encoding="utf-8")
    body = src[src.index("def fetch_table("):]
    i = body.index('s.post("ddlSeason$ddlSeason"')
    j = body.index('s.post("ddlTeam$ddlTeam"')
    assert i < j, "팀을 시즌보다 먼저 보내면 초기화됩니다"


# ------------------------------------------------------- 프랜차이즈 표

def test_프랜차이즈가_열둘입니다():
    cur = const(FRANCHISE, "CURRENT")
    assert len(cur) == 12, "프랜차이즈가 12개가 아닙니다: %d" % len(cur)
    assert cur["HD"] is None, "현대(HD)는 2007 해체입니다"
    assert cur["SB"] is None, "쌍방울(SB)은 1999 마지막입니다"
    alive = {k: v for k, v in cur.items() if k not in ("HD", "SB")}
    assert all(alive.values()), "현재 팀이 빈 프랜차이즈: %s" % [
        k for k, v in alive.items() if not v]


def test_모르는_팀_코드가_나오면_멈춥니다():
    """새 팀이 생겼는데 조용히 빠지면 그 선수들이 프랜차이즈에 안 붙습니다."""
    src = FRANCHISE.read_text(encoding="utf-8")
    i = src.index("unknown = sorted(set(sp) - set(CURRENT))")
    assert "return 1" in src[i:i + 400], "모르는 코드를 만나도 계속 돕니다"


def test_팀_목록_캐시가_저장소에_있습니다():
    """사이트가 바뀌어도 지난 값으로 다시 만들 수 있어야 합니다."""
    assert CACHE.exists(), "teams_by_season.json 이 없습니다"
    d = json.loads(CACHE.read_text(encoding="utf-8"))
    assert len(d["1982"]) == 6, "1982 는 6팀입니다"
    assert len(d["2026"]) == 10, "2026 은 10팀입니다"
    codes82 = {c for c, _ in d["1982"]}
    assert "HD" in codes82, "1982 에 삼미(HD)가 있어야 합니다"
    assert "KT" not in codes82, "KT 는 2015 창단입니다"


def test_시즌마다_팀이_최소_여섯입니다():
    d = json.loads(CACHE.read_text(encoding="utf-8"))
    for y, teams in d.items():
        assert len(teams) >= 6, "%s 시즌 팀이 %d개뿐입니다" % (y, len(teams))
        codes = [c for c, _ in teams]
        assert len(codes) == len(set(codes)), "%s 에 코드가 겹칩니다" % y


def test_해체팀_활동기간이_맞습니다():
    d = json.loads(CACHE.read_text(encoding="utf-8"))
    years = {c: sorted(int(y) for y, ts in d.items()
                       if c in {x for x, _ in ts})
             for c in ("HD", "SB")}
    assert years["HD"][0] == 1982 and years["HD"][-1] == 2007, \
        "현대(HD)는 1982~2007 입니다: %s~%s" % (years["HD"][0], years["HD"][-1])
    assert years["SB"][0] == 1991 and years["SB"][-1] == 1999, \
        "쌍방울(SB)은 1991~1999 입니다: %s~%s" % (years["SB"][0], years["SB"][-1])


# ------------------------------------------------ 만들어진 표 (있을 때만)

def _db():
    p = ROOT / "database" / "kbo_stats.db"
    if not p.exists():
        pytest.skip("로컬 DB 가 없습니다")
    con = sqlite3.connect(str(p))
    have = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if "team_seasons" not in have:
        con.close()
        pytest.skip("아직 build_franchises.py --write 를 돌리지 않았습니다")
    return con


def test_시즌_소속으로_프랜차이즈를_찾습니다():
    con = _db()
    q = ("SELECT ts.franchise_id, f.current_name FROM team_seasons ts "
         "JOIN franchises f ON f.franchise_id = ts.franchise_id "
         "WHERE ts.season = ? AND ts.team_name = ?")
    cases = [
        (1982, "OB", "OB", "두산"),
        (1989, "MBC", "LG", "LG"),
        (2000, "해태", "HT", "KIA"),
        (1985, "청보", "HD", None),
        (1999, "쌍방울", "SB", None),
        (2026, "SSG", "SK", "SSG"),
    ]
    for season, name, want_fr, want_cur in cases:
        row = con.execute(q, (season, name)).fetchone()
        assert row, "%d %s 를 못 찾습니다" % (season, name)
        assert row[0] == want_fr, "%d %s -> %s (기대 %s)" % (
            season, name, row[0], want_fr)
        assert row[1] == want_cur, "%d %s 의 현재팀이 %r 입니다 (기대 %r)" % (
            season, name, row[1], want_cur)
    con.close()


def test_한_시즌_한_이름은_한_프랜차이즈입니다():
    """같은 해에 같은 이름이 둘이면 조인이 갈라집니다."""
    con = _db()
    dup = con.execute(
        "SELECT season, team_name, COUNT(*) c FROM team_seasons "
        "GROUP BY season, team_name HAVING c > 1").fetchall()
    con.close()
    assert not dup, "이름이 겹칩니다: %s" % dup[:5]
