# -*- coding: utf-8 -*-
"""wOBA 가중치 파이프라인이 다시 끊기지 않게 막습니다.

`kbo_woba_weights_by_season` 은 원래 손으로 채우던 표였고 값은 Statiz
캡처였습니다(statiz_yearly_constants.source='Statiz', captured_at 이 전
행 같은 한 시각). 아무도 안 채우자 표가 사라졌고, D1 으로도 넘어오지
않아 주간 파이프라인이 첫 질의에서 죽었습니다. **한 번도 성공한 적이
없습니다.** 2026 wOBA·wRC+ 가 화면에서 비어 있던 이유입니다.

이제 play_by_play 에서 계산합니다. 사람이 넣을 값이 없습니다.
여기서 지키는 것은 세 가지입니다.

  1. 산식이 문서(column_descriptions.json)와 같은가
  2. 주간 워크플로가 표를 받아오고, 만들고, 되올리는가
  3. 빈 결과로 표를 비우지 않는가 (이게 제일 위험합니다)
"""
import ast
import re
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "park_factors" / "build_woba_weights.py"
WEEKLY = ROOT / ".github" / "workflows" / "weekly.yml"
TABLE = "kbo_woba_weights_by_season"


def load_module():
    pytest.importorskip("pandas")
    pytest.importorskip("numpy")
    import importlib.util
    import sys
    sys.path.insert(0, str(ROOT / "park_factors"))
    spec = importlib.util.spec_from_file_location("bww", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------ 산식

def test_가중치는_아웃을_빼고_배율을_곱합니다():
    """fg_wX = (raw_RV_X - avg_out_RV) x wOBA_scale"""
    m = load_module()
    # 아웃이 -0.3, 1루타가 +0.5 인 단순한 리그를 만듭니다.
    rv = {"1B": (0.5, 100), "2B": (0.8, 10), "3B": (1.1, 1),
          "HR": (1.4, 10), "uBB": (0.35, 20), "HBP": (0.36, 2),
          "SO": (-0.3, 100), "OutInPlay": (-0.3, 100)}
    tot = {"season": 2099, "PA": 1000, "AB": 900, "H": 250, "D2": 40,
           "D3": 5, "HR": 20, "BB": 80, "HBP": 10, "SF": 10}
    row = dict(zip(m.COLS, m.season_row(rv, tot)))
    assert row["avg_out_RV"] == pytest.approx(-0.3)
    # 배율을 곱하기 전 값이 (RV - 아웃) 이어야 합니다.
    assert row["fg_w1B"] / row["wOBA_scale"] == pytest.approx(0.5 - (-0.3))
    assert row["fg_wHR"] / row["wOBA_scale"] == pytest.approx(1.4 - (-0.3))
    # 볼넷 가중치는 고의4구를 뺀 uBB 득점가치에서 나옵니다.
    assert row["fg_wBB"] / row["wOBA_scale"] == pytest.approx(0.35 - (-0.3))


def test_배율은_출루율을_스케일_전_리그값으로_나눈_것입니다():
    m = load_module()
    rv = {"1B": (0.5, 100), "2B": (0.8, 10), "3B": (1.1, 1),
          "HR": (1.4, 10), "uBB": (0.35, 20), "HBP": (0.36, 2),
          "SO": (-0.3, 100), "OutInPlay": (-0.3, 100)}
    tot = {"season": 2099, "PA": 1000, "AB": 900, "H": 250, "D2": 40,
           "D3": 5, "HR": 20, "BB": 80, "HBP": 10, "SF": 10}
    row = dict(zip(m.COLS, m.season_row(rv, tot)))
    den = tot["AB"] + tot["BB"] + tot["SF"] + tot["HBP"]
    obp = (tot["H"] + tot["BB"] + tot["HBP"]) / den
    assert row["OBP"] == pytest.approx(obp, abs=1e-6)
    assert row["wOBA_scale"] == pytest.approx(obp / row["raw_lg_wOBA"],
                                              abs=1e-6)


def test_사건이_모자라면_만들지_않습니다():
    m = load_module()
    tot = {"season": 2099, "PA": 1000, "AB": 900, "H": 250, "D2": 40,
           "D3": 5, "HR": 20, "BB": 80, "HBP": 10, "SF": 10}
    assert m.season_row({"1B": (0.5, 10)}, tot) is None      # 아웃 없음
    assert m.season_row({"SO": (-0.3, 10)}, tot) is None      # 타격 사건 없음


# -------------------------------------------------- 결손 데이터 방어

def test_리그_합계에_NULL_이_있으면_그_시즌을_건너뜁니다(tmp_path):
    """2021 NC 49명의 볼넷이 통째로 빈 적이 있습니다.

    0 으로 세면 리그 볼넷이 모자라 가중치가 통째로 어긋납니다.
    그러면서도 아무 오류가 나지 않습니다.
    """
    m = load_module()
    db = tmp_path / "t.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE kbo_official_batter_stats ("
                "season INT, plate_appearance INT, at_bat INT, single INT,"
                "double INT, triple INT, home_run INT, base_on_balls INT,"
                "hit_by_pitch INT, sacrifice_fly INT)")
    con.execute("INSERT INTO kbo_official_batter_stats VALUES "
                "(2020,100,90,25,4,0,2,8,1,1)")
    con.execute("INSERT INTO kbo_official_batter_stats VALUES "
                "(2021,100,90,25,4,0,2,NULL,NULL,1)")
    con.commit()
    got = m.league_totals(con)
    con.close()
    assert 2020 in got
    assert 2021 not in got, "볼넷이 NULL 인 시즌을 계산에 넣고 있습니다"


def test_빈_결과로_표를_비우지_않습니다():
    """이게 제일 위험합니다.

    build_wrc_plus.py 는 무조건 `DELETE FROM wrc_plus_comparison` 을
    돌리고, 가중치가 없는 시즌은 continue 로 건너뜁니다. 가중치 표가
    비어 있으면 **전 시즌을 지우고 아무것도 넣지 않습니다.**
    """
    src = SCRIPT.read_text(encoding="utf-8")
    body = src[src.index("def main("):]
    del_at = body.index("DELETE FROM kbo_woba_weights_by_season")
    guard = body.index("if not rows:")
    assert guard < del_at, "빈 결과 방어가 DELETE 뒤에 있습니다"


def test_문법이_성립합니다():
    ast.parse(SCRIPT.read_text(encoding="utf-8"))


# ------------------------------------------------------- 워크플로 배선

def _weekly():
    return re.sub(r"\\\s*\n\s*", " ", WEEKLY.read_text(encoding="utf-8"))


def test_주간_워크플로가_가중치를_만듭니다():
    assert "build_woba_weights.py --write" in _weekly(), (
        "주간 워크플로가 가중치를 만들지 않습니다. "
        "표가 없으면 wRC+ 계산이 첫 질의에서 죽습니다.")


def test_가중치가_wRC보다_먼저_돕니다():
    s = _weekly()
    assert s.index("build_woba_weights.py") < s.index("build_wrc_plus.py"), \
        "wRC+ 가 가중치보다 먼저 돕니다"


def test_wRC_단계가_가중치_성공에_걸려_있습니다():
    s = _weekly()
    seg = s[s.index("build_woba_weights.py"):]
    assert "steps.woba.outcome == 'success'" in seg, (
        "가중치가 실패해도 wRC+ 가 돕니다. 낡은 가중치로 덮어씁니다.")


@pytest.mark.parametrize("mod,var", [
    ("migration/d1_to_sqlite.py", "PIPELINE_TABLES"),
    ("migration/sqlite_to_d1.py", "DERIVED_TABLES"),
])
def test_가중치_표가_내려받기와_올리기_목록에_있습니다(mod, var):
    tree = ast.parse((ROOT / mod).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == var for t in node.targets):
            names = ast.literal_eval(node.value)
            assert TABLE in names, "%s 의 %s 에 %s 가 없습니다" % (mod, var, TABLE)
            return
    pytest.fail("%s 에서 %s 를 찾지 못했습니다" % (mod, var))
