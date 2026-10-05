# -*- coding: utf-8 -*-
"""선수 분류(아시아쿼터)가 쓰는 시즌을 봅니다.

예전에는 player_info_scraper.py·player_registry_sync.py 가 각자 2026 을
박았습니다(2026-10-05 검토). 이제 player_flags.ASIA_QUOTA_BY_SEASON 의
가장 최근 시즌을 씁니다. 보유자는 KBO 공시라 계산할 수 없으므로 2027
공시가 나오면 표에 그 시즌만 더합니다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import player_flags as pf  # noqa: E402

QUOTA = "55348"  # 2026 아시아쿼터(웰스)


def test_오늘은_2026_표를_씁니다():
    assert pf.LATEST_QUOTA_SEASON == 2026
    assert pf.classify_player(QUOTA, "호주") == pf.classify_player(QUOTA, "호주", 2026)
    assert pf.classify_player(QUOTA, "호주")[2] == "아시아쿼터"


def test_새_시즌을_표에_더하면_그_시즌을_씁니다(monkeypatch):
    table = dict(pf.ASIA_QUOTA_BY_SEASON)
    table[2027] = {"99999": {"name": "새선수", "nationality": "일본"}}
    monkeypatch.setattr(pf, "ASIA_QUOTA_BY_SEASON", table)
    monkeypatch.setattr(pf, "LATEST_QUOTA_SEASON", max(table))
    assert pf.classify_player("99999", "일본 고교")[2] == "아시아쿼터"
    # 2027 에 없는 2026 보유자는 외국인으로 돌아갑니다.
    assert pf.classify_player(QUOTA, "호주")[2] == "외국인"


def test_부르는_곳이_시즌을_박지_않습니다():
    for name in ("player_info_scraper.py", "player_registry_sync.py"):
        src = (ROOT / "data_collection" / name).read_text(encoding="utf-8")
        assert "CLASSIFY_SEASON = pf.LATEST_QUOTA_SEASON" in src, name
