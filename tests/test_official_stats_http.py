# -*- coding: utf-8 -*-
"""브라우저 없이 읽는 공식 기록 수집기를 지킵니다.

Selenium 을 걷어내고 HTTP 로 바꿨습니다. 2021 로 대조해 타자 394명
37컬럼, 투수 308명 51컬럼이 전부 일치했고 13분 21초가 2분 21초로
줄었습니다.

여기서 막는 것은 조용히 비는 경우입니다. 실제로 겪은 것만 담았습니다.

  - 세부기록 주소가 `Detail.aspx` 가 아니라 `Detail1.aspx` 입니다.
    틀리면 3KB 짜리 빈 페이지가 오고 세부 컬럼이 통째로 빕니다.
  - 투수는 세부기록이 **두 쪽**입니다. Detail2 를 빠뜨리면 BABIP·
    P/G·K/9·OBP 같은 값이 308명 전부 빕니다.
  - 컬럼 이름이 D1 스키마와 어긋나면 그 값이 NULL 로 남습니다
    (`wild_pitch` 는 단수입니다).
"""
import ast
import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data_collection" / "official_stats_http.py"
HTTP = ROOT / "data_collection" / "kbo_http.py"


def mod():
    sys.path.insert(0, str(ROOT / "data_collection"))
    spec = importlib.util.spec_from_file_location("osh", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ------------------------------------------------------------ 페이지 구성

def test_세부기록은_Detail1_입니다():
    m = mod()
    for kind, pages in m.PAGES.items():
        assert any("Detail1.aspx" in p for p in pages), kind
        assert not any(p.endswith("/Detail.aspx") for p in pages), (
            "%s: Detail.aspx 는 빈 페이지입니다. Detail1.aspx 여야 합니다"
            % kind)


def test_투수는_세부기록이_두_쪽입니다():
    m = mod()
    pit = m.PAGES["pitcher"]
    assert any("Detail2.aspx" in p for p in pit), (
        "Detail2 가 빠지면 BABIP·P/G·K/9·OBP 가 전부 빕니다")
    # 타자는 Detail1 이 끝입니다. 없는 쪽을 부르면 빈 표 경고만 납니다.
    assert not any("Detail2.aspx" in p for p in m.PAGES["batter"])


def test_열_팀을_다_돕니다():
    m = mod()
    assert len(m.TEAM_CODES) == 10
    assert len(set(m.TEAM_CODES)) == 10


# --------------------------------------------------------- 컬럼 이름 계약

def selenium_map(name):
    """옛 스크래퍼의 COLUMN_MAPPING 을 실행 없이 읽습니다."""
    src = (ROOT / "data_collection" / name).read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "COLUMN_MAPPING"
                for t in node.targets):
            return ast.literal_eval(node.value)
    pytest.skip("%s 에 COLUMN_MAPPING 이 없습니다" % name)


@pytest.mark.parametrize("kind,legacy", [
    ("batter", "selenium_batter_scraper.py"),
    ("pitcher", "selenium_pitcher_scraper.py"),
])
def test_컬럼_이름이_옛_수집기와_같습니다(kind, legacy):
    """이름이 하나만 어긋나도 그 값이 D1 에서 조용히 NULL 이 됩니다."""
    old = selenium_map(legacy)
    new = mod().MAPS[kind]
    bad = {h: (old[h], new[h]) for h in set(old) & set(new)
           if old[h] != new[h]}
    assert not bad, "머리글별 컬럼 이름이 다릅니다: %s" % bad
    missing = sorted(set(old) - set(new))
    assert not missing, "새 수집기에 없는 머리글: %s" % ", ".join(missing)


def test_투수_wild_pitch_는_단수입니다():
    """D1 스키마가 단수입니다. 복수로 쓰면 통째로 NULL 입니다."""
    v = mod().MAPS["pitcher"]
    assert v["WP"] == "wild_pitch"
    assert v["BK"] == "balk"


# --------------------------------------------------------------- 결손 판정

def test_핵심_컬럼이_비면_결손으로_셉니다():
    m = mod()
    good = {"1": {"plate_appearance": "100", "at_bat": "90",
                  "base_on_balls": "8", "hit_by_pitch": "1",
                  "strikeout": "20"}}
    assert m.holes("batter", good) == 0
    for blank in ("", "-", "   "):
        bad = {"1": dict(good["1"], base_on_balls=blank)}
        assert m.holes("batter", bad) == 1, "%r 을 결손으로 안 봅니다" % blank


def test_결손이_있으면_적재하지_않습니다():
    """2021 NC 49명이 빈 채로 D1 에 들어간 적이 있습니다."""
    src = SRC.read_text(encoding="utf-8")
    main = src[src.index("def main("):]
    assert "if bad:" in main and "rc = 1" in main, "결손 시 실패 처리가 없습니다"
    assert main.index("if bad:") < main.index("write_csv("), \
        "결손 검사가 CSV 쓰기 뒤에 있습니다"


# ------------------------------------------------------------- HTTP 모듈

def test_포스트백_접두사가_세_겹입니다():
    src = HTTP.read_text(encoding="utf-8")
    assert 'PREFIX = "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$"' \
        in src, "컨트롤 접두사가 바뀌면 포스트백이 통째로 무시됩니다"


def test_요청_사이에_쉬어_갑니다():
    src = HTTP.read_text(encoding="utf-8")
    m = re.search(r"DELAY_SEC = ([0-9.]+)", src)
    assert m and float(m.group(1)) > 0, "간격 없이 두드리면 안 됩니다"


def test_표를_못_찾으면_빈_값을_줍니다():
    """조용히 예외로 죽지 않고, 부르는 쪽이 행 수로 판단하게 합니다."""
    sys.path.insert(0, str(ROOT / "data_collection"))
    import kbo_http
    s = kbo_http.Session()
    s.html = "<html><body>표가 없습니다</body></html>"
    assert s.header() == []
    assert s.rows() == []
    assert s.page_count() == 1


def test_문법이_성립합니다():
    for p in (SRC, HTTP):
        ast.parse(p.read_text(encoding="utf-8"))
