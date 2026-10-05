# -*- coding: utf-8 -*-
import argparse
import datetime

import pytest

from data_collection import pitch_run_value as prv


def ns(**kw):
    base = dict(season=None, current=False, from_=None, to=None, dry_run=False)
    base.update(kw)
    return argparse.Namespace(**base)


TODAY = datetime.date(2026, 10, 4)


def test_시즌_하나():
    assert prv.seasons_from_args(ns(season=2024), TODAY) == [2024]


def test_올해():
    assert prv.seasons_from_args(ns(current=True), TODAY) == [2026]


def test_범위():
    assert prv.seasons_from_args(ns(from_=2016, to=2018), TODAY) == [2016, 2017, 2018]


def test_2016_전은_거절합니다():
    with pytest.raises(SystemExit):
        prv.seasons_from_args(ns(season=2015), TODAY)


def test_읽기_질의는_정규시즌만_pbp_id_순입니다():
    sql = prv.fetch_sql()
    for p in ("3333", "4444", "5555", "7777", "9999"):
        assert "gameID NOT LIKE '%s%%%%'" % p in sql
    assert "ORDER BY gameID, pbp_id" in sql
    assert sql.count("%s") == 2


def test_행_만들기():
    assert prv.re_rows(2024, {(1, 0, 2, 1): 0.5}, {(1, 0, 2, 1): 7}) == [(2024, 1, 0, 2, 1, 0.5, 7)]
    assert prv.value_rows(2024, {(65933, "직구", "L"): [3, 1.25]}) == [(2024, 65933, "직구", "L", 3, 1.25)]


class FakeCur:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append(("execute", sql, params))

    def executemany(self, sql, rows):
        self.calls.append(("executemany", sql, list(rows)))


class FakeCon:
    def __init__(self):
        self.cur = FakeCur()
        self.committed = False
        self.rolled = False

    def cursor(self):
        return self.cur

    def begin(self):
        pass

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled = True


def test_시즌을_지우고_넣고_커밋합니다():
    con = FakeCon()
    prv.write_season(con, 2024, [(2024, 0, 0, 0, 0, 0.6, 10)], [(2024, 1, "직구", "R", 3, 0.2)],
                     [(2024, 1, "heart", 3, 0.2)], (2024,) + (1,) * 17)
    kinds = [(c[0], c[1].split()[0], c[1].split()[2] if c[0] == "execute" else c[1].split()[2]) for c in con.cur.calls]
    assert kinds == [("execute", "DELETE", "run_expectancy"), ("execute", "DELETE", "pitch_run_value"),
                     ("execute", "DELETE", "pitch_run_value_zone"),
                     ("execute", "DELETE", "plate_discipline_league"),
                     ("executemany", "INSERT", "run_expectancy"), ("executemany", "INSERT", "pitch_run_value"),
                     ("executemany", "INSERT", "pitch_run_value_zone"),
                     ("execute", "INSERT", "plate_discipline_league")]
    assert con.committed and not con.rolled


def test_실패하면_되돌립니다():
    con = FakeCon()

    def boom(sql, rows):
        raise RuntimeError("x")
    con.cur.executemany = boom
    with pytest.raises(RuntimeError):
        prv.write_season(con, 2024, [(2024, 0, 0, 0, 0, 0.6, 10)], [])
    assert con.rolled and not con.committed


def test_존_행은_투수_다음_heart_shadow_chase_waste_순서입니다():
    z = {(2, "waste"): [1, -0.5], (1, "chase"): [2, 0.25], (1, "heart"): [3, 1.0]}
    assert prv.zone_rows(2024, z) == [(2024, 1, "heart", 3, 1.0), (2024, 1, "chase", 2, 0.25),
                                      (2024, 2, "waste", 1, -0.5)]


def test_읽기_질의에_공_위치가_들어갑니다():
    sql = prv.fetch_sql()
    assert "px, pz, sz_top, sz_bot" in sql
    assert prv.COLS[-4:] == ("px", "pz", "sz_top", "sz_bot")


def test_리그_선구_행은_시즌_다음_정한_키_순서입니다():
    d = {k: i for i, k in enumerate(prv.pv.DISCIPLINE_KEYS)}
    assert prv.discipline_row(2025, d) == (2025,) + tuple(range(17))
