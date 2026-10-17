# -*- coding: utf-8 -*-
"""박스스코어 받기(data_collection/naver_boxscore.py): 이어 받기와 정규시즌만."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import naver_boxscore as nb  # noqa: E402


class FakeClient:
    def __init__(self):
        self.paths = []

    def get(self, path):
        self.paths.append(path)
        return {"code": 200, "result": {"recordData": {
            "pitchersBoxscore": {"home": [], "away": []}, "etcRecords": [], "todayKeyStats": 1}}}


def test_이미_받은_경기는_건너뜁니다(tmp_path):
    fc = FakeClient()
    nb.fetch_all(["20100701LTSS0", "20160701HTWO02016"], tmp_path, cl=fc, log=lambda *_: None)
    assert len(fc.paths) == 2
    got, skipped, failed = nb.fetch_all(["20100701LTSS0", "20160701HTWO02016"], tmp_path,
                                        cl=fc, log=lambda *_: None)
    assert (got, skipped, failed) == (0, 2, [])
    assert nb.load(tmp_path, "20160701HTWO02016")["pitchersBoxscore"] == {"home": [], "away": []}


def test_쓰는_부분만_남깁니다():
    d = nb.slim({"result": {"recordData": {"pitchersBoxscore": 1, "homeStandings": 2}}})
    assert d["pitchersBoxscore"] == 1 and "homeStandings" not in d


def test_recordData_가_없으면_실패입니다():
    with pytest.raises(ValueError):
        nb.slim({"result": {}})


def test_정규시즌만_고릅니다(tmp_path):
    p = tmp_path / "g.csv"
    p.write_text("game_id,season,game_type\n20080329HTSS0,2008,정규시즌\n"
                 "20081016SKOB0,2008,포스트시즌\n20070405HTSS0,2007,정규시즌\n", encoding="utf-8")
    assert nb.games_from_csv(p, 2008, 2026) == ["20080329HTSS0"]


def test_박스_이닝_글자():
    import naver_box_stats as nbx
    assert nbx.inn_outs("4 ⅓") == 13 and nbx.inn_outs("0 ⅔") == 2 and nbx.inn_outs("6") == 18
    assert nbx.inn_outs("") == 0


def test_박스_약어():
    import naver_box_stats as nbx
    assert [nbx.kind(c) for c in ("유땅", "좌중2", "우홈", "고4", "투희번", "우희번", "중희실", "3실", "좌실", "스낫")] == \
        ["go", "h2", "hr", "ibb", "sh", "fly", "sf", "err_if", "err_of", "so"]
