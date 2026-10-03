# -*- coding: utf-8 -*-
"""games 의 최종 점수는 마지막 플레이의 득점까지 넣어야 합니다.

PBP 의 score_home/score_away 는 그 플레이 **전** 점수입니다. 최댓값만 쓰면
끝내기처럼 마지막 플레이에서 난 점수가 빠져 무승부로 남습니다. 2015~2025
정규시즌마다 50~80경기가 그랬습니다(공식 무승부는 5~22경기, 2026-10-03 발견).

또 daily 는 그날 CSV 를 글자(TEXT) 열의 작은 DB 에 넣어 셉니다. 글자끼리
최댓값을 고르면 '9' 가 '15' 보다 큽니다. 2026-08-18 뒤 두 자리 점수가
한 자리로 들어갔습니다.
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

from games_from_pbp import derive_games  # noqa: E402

COLS = ["gameID", "game_date", "home_alias", "away_alias", "stadium",
        "inning_topbot", "score_home", "score_away", "runs_scored"]


def db(plays):
    """daily 와 같이 모든 열이 TEXT 인 작은 DB 입니다."""
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE teams (team_id TEXT)")
    con.executemany("INSERT INTO teams VALUES (?)", [("LT",), ("HH",)])
    con.execute("CREATE TABLE games (game_id TEXT)")
    con.execute("CREATE TABLE play_by_play (%s)" % ",".join('"%s" TEXT' % c for c in COLS))
    gid = "20250930LTHH02025"
    con.executemany(
        "INSERT INTO play_by_play VALUES (%s)" % ",".join("?" * len(COLS)),
        [(gid, "20250930", "HH", "LT", "대전") + p for p in plays])
    return con


def scores(con):
    rows, _ = derive_games(con, skip_existing=False)
    (row,) = rows
    return row[6], row[7]          # home_score, away_score


def test_walk_off_run_counts():
    # 10회말 0:0 에서 끝내기 안타로 1점. 최종 한화 1 : 롯데 0.
    con = db([("초", "0", "0", "0"), ("말", "0", "0", "0"), ("말", "0", "0", "1")])
    assert scores(con) == (1, 0)


def test_top_half_runs_count_for_away():
    # 마지막 플레이가 초 공격의 득점이어도 원정 점수에 들어갑니다.
    con = db([("초", "2", "3", "0"), ("초", "2", "3", "2")])
    assert scores(con) == (2, 5)


def test_two_digit_scores_compare_as_numbers():
    con = db([("말", "9", "4", "0"), ("말", "15", "4", "0"), ("초", "15", "10", "0")])
    assert scores(con) == (15, 10)


def test_blank_runs_scored_is_zero():
    con = db([("말", "3", "2", ""), ("초", "3", "2", None)])
    assert scores(con) == (3, 2)
