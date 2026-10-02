import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import sync_players_from_roster as m  # noqa: E402


def test_teams_에_없는_소속은_건너뜁니다():
    rows = [{"pid": 1, "nm": "가", "rt": "LG"},
            {"pid": 2, "nm": "나", "rt": "상무"},
            {"pid": 3, "nm": "다", "rt": "KIA"}]
    keep, skip = m.split_known(rows, {"LG", "KIA"})
    assert [r["pid"] for r in keep] == [1, 3]
    assert [r["pid"] for r in skip] == [2]


def _step(text, marker):
    """워크플로에서 marker 가 있는 단계 하나의 글자입니다."""
    start = text.index(marker)
    end = text.find("\n      - ", start)
    return text[start:end if end != -1 else None]


def test_roster_뒤_단계는_소속_갱신이_실패해도_돕니다():
    text = (ROOT / ".github" / "workflows" / "roster.yml").read_text(encoding="utf-8")
    for marker in ("id: newp", "id: futures", "name: 캐시 비우기"):
        assert "!cancelled()" in _step(text, marker), marker
