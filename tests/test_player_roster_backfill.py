# -*- coding: utf-8 -*-
"""`players` 백필이 성립하는 조건을 지킵니다.

리더보드와 기록실은 선수 이름을 `players` 에서 가져옵니다. 그 표를
채우는 것이 월간 워크플로인데, 두 가지가 어긋나 있었습니다.

  1. 워크플로가 `--tables players` 만 내려받았습니다. 그런데 스크래퍼는
     수집 대상 명단을 **공식 기록 두 표**에서 뽑습니다. 그 표가 없어
     "no such table" 로 죽었습니다. meta_job_runs 에 player_info 기록이
     한 번도 없는 이유입니다.
  2. 명단을 최신 시즌에서만 뽑아, 지난 시즌 백필을 할 수 없었습니다.
"""
import re
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MONTHLY = ROOT / ".github" / "workflows" / "monthly.yml"

# 스크래퍼가 명단을 읽는 표입니다.
NEEDED_TABLES = ("kbo_official_batter_stats", "kbo_official_pitcher_stats")


def _scraper(monkeypatch, db_path):
    """selenium 이 없는 환경에서는 건너뜁니다."""
    pytest.importorskip("selenium")
    pytest.importorskip("webdriver_manager")
    pytest.importorskip("pandas")
    import sys
    sys.path.insert(0, str(ROOT / "data_collection"))
    import player_info_scraper as mod
    monkeypatch.setattr(mod, "DB_PATH", str(db_path))
    return mod


def _make_db(path, with_stats=True):
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE players (player_id TEXT PRIMARY KEY)")
    if with_stats:
        for t in NEEDED_TABLES:
            con.execute('CREATE TABLE %s (player_id TEXT, season INTEGER)' % t)
        con.executemany(
            "INSERT INTO kbo_official_batter_stats VALUES (?,?)",
            [("옛타자", 2016), ("새타자", 2026)])
        con.executemany(
            "INSERT INTO kbo_official_pitcher_stats VALUES (?,?)",
            [("옛투수", 2016), ("새투수", 2026)])
    con.commit()
    con.close()


# --------------------------------------------------- 워크플로가 표를 받습니다

def test_월간_워크플로가_공식기록_표를_내려받습니다():
    """이게 빠지면 스크래퍼가 첫 질의에서 죽습니다.

    주석에도 `--tables players` 라는 글자가 있어서, 처음 나오는 것만
    보면 주석을 읽고 통과·실패가 뒤집힙니다. 내려받기 명령
    (`d1_to_sqlite.py`)에 붙은 것만 봅니다.
    """
    # 줄 끝 `\` 이음을 먼저 펴서 명령 한 줄로 만듭니다.
    src = re.sub(r"\\\s*\n\s*", " ", MONTHLY.read_text(encoding="utf-8"))
    m = re.search(r"d1_to_sqlite\.py[^\n]*", src)
    assert m, "monthly.yml 에서 d1_to_sqlite.py 호출을 찾지 못했습니다"
    t = re.search(r"--tables\s+([A-Za-z0-9_,]+)", m.group(0))
    assert t, "내려받기 명령에 --tables 가 없습니다: %s" % m.group(0)
    listed = {x for x in t.group(1).split(",") if x}
    for name in ("players",) + NEEDED_TABLES:
        assert name in listed, (
            "monthly.yml 이 %s 를 내려받지 않습니다. "
            "player_info_scraper 가 그 표를 읽습니다. 받는 것: %s"
            % (name, sorted(listed))
        )


# ------------------------------------------------------- 명단을 뽑는 규칙

def test_공식기록_표가_없으면_실패합니다(tmp_path, monkeypatch):
    """조용히 빈 목록을 주면 안 됩니다. 아무도 수집되지 않는데
    성공으로 보입니다."""
    db = tmp_path / "only_players.db"
    _make_db(db, with_stats=False)
    mod = _scraper(monkeypatch, db)
    with pytest.raises(Exception):
        mod.get_existing_player_ids()


def test_기본값은_최신_시즌뿐입니다(tmp_path, monkeypatch):
    """월간 워크플로가 매달 12시즌을 다시 훑지 않게 합니다."""
    db = tmp_path / "full.db"
    _make_db(db)
    mod = _scraper(monkeypatch, db)
    ids, scope = mod.get_existing_player_ids()
    assert ids == ["새타자", "새투수"]
    assert "2026" in scope


def test_전_시즌_옵션이_옛_선수를_데려옵니다(tmp_path, monkeypatch):
    db = tmp_path / "full.db"
    _make_db(db)
    mod = _scraper(monkeypatch, db)
    ids, _ = mod.get_existing_player_ids(all_seasons=True)
    assert ids == ["새타자", "새투수", "옛" + "타자", "옛투수"] or set(ids) == {
        "옛타자", "새타자", "옛투수", "새투수"}


def test_전_시즌_옵션이_CLI_에_있습니다():
    src = (ROOT / "data_collection" / "player_info_scraper.py").read_text(
        encoding="utf-8")
    assert "--all-seasons" in src


# --- 등말소 날짜는 KBO 가 준 날짜를 씁니다 --------------------------
#
# `move_date` 에 수집일을 넣고 있었습니다. KBO 등말소는 경기 2~4시간
# 전에 갱신되므로, 새벽에 도는 daily 는 **전날 명단**을 봅니다. 그런데
# 오늘 날짜를 붙여 저장하니 같은 내용이 이틀치로 쌓였습니다.
#
#     2026-08-28  등록 9 · 말소 7
#     2026-08-29  등록 9 · 말소 7   <- 같은 선수들
#
# 페이지가 날짜를 줍니다. 그것을 씁니다.
#
#     <input ... id="..._hfSearchDate" value="20260828" />
#     <span  ... id="..._lblGameDate">2026.08.28(금)</span>

def test_페이지에서_기준일을_읽습니다():
    from kbo_register import page_date
    html = ('<input type="hidden" name="x$hfSearchDate" '
            'id="cphContents_cphContents_cphContents_hfSearchDate" '
            'value="20260828" />')
    assert page_date(html) == "2026-08-28"


def test_표시용_날짜로도_읽습니다():
    from kbo_register import page_date
    html = ('<span id="cphContents_cphContents_cphContents_lblGameDate">'
            '2026.08.28(금)</span>')
    assert page_date(html) == "2026-08-28"


def test_날짜를_못_읽으면_None_입니다():
    from kbo_register import page_date
    # 부르는 쪽이 오늘 날짜로 물러섭니다. 없는 날짜를 지어내지 않습니다.
    assert page_date("<html></html>") is None
