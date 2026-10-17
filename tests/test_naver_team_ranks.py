# -*- coding: utf-8 -*-
"""네이버 팀 순위(data_collection/naver_team_ranks.py): 칸 대응·그 시즌 이름·게임차 표기."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import naver_team_ranks as tr  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "naver"


def stats(y):
    return json.loads((FIX / ("teams_%d.json" % y)).read_text(encoding="utf-8"))


def test_2010_은_그_시즌_이름과_네이버_게임차를_씁니다():
    rows = tr.to_rows(stats(2010), 2010, {("WO", 2010): "넥센", ("SK", 2010): "SK"})
    by = {r["franchise_id"]: r for r in rows}
    assert len(rows) == 8
    assert by["SK"]["rank"] == 1 and by["SK"]["gb"] == "0" and by["SK"]["pct"] == "0.632"
    assert by["WO"]["team_name"] == "넥센"
    # 무승부를 패로 센 게임차(2010 규칙): 두산 73-57-3 → 11
    assert by["OB"]["gb"] == "11"
    assert all(r["league"] == "단일" for r in rows)


def test_새_시즌_줄은_team_seasons_에_넣을_후보가_됩니다():
    rows = tr.to_rows(stats(2025), 2025, {})
    assert len(rows) == 10
    new = tr.new_team_seasons(rows, {})
    assert {r["franchise_id"] for r in new} == {r["franchise_id"] for r in rows}


def test_게임차_표기():
    assert tr.fmt_gb(0.0) == "0" and tr.fmt_gb(10.5) == "10.5" and tr.fmt_gb(26) == "26"
    assert tr.fmt_pct(0.6316) == "0.632" and tr.fmt_pct(0.3125) == "0.313"
