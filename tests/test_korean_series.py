# -*- coding: utf-8 -*-
"""한국시리즈 우승 표를 확인합니다."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_collection.korean_series import (
    CHAMPIONS, FIRST_COMPUTABLE, to_sql, verify, winner_from_games)


def test_seasons_are_continuous():
    """1982년부터 한 해도 빠지지 않아야 합니다."""
    seasons = [s for s, _, _ in CHAMPIONS]
    assert seasons[0] == 1982
    assert seasons == sorted(seasons)
    assert len(set(seasons)) == len(seasons)
    gaps = [b for a, b in zip(seasons, seasons[1:]) if b - a != 1]
    assert gaps == [], '빠진 시즌이 있습니다: %s' % gaps


def test_1985_has_a_note():
    """한국시리즈가 안 열린 해는 그 사실을 남겨야 합니다."""
    note = {s: n for s, _, n in CHAMPIONS}[1985]
    assert '한국시리즈' in note


def test_winner_is_the_team_with_most_wins():
    rows = [(2011, '삼성')] * 4 + [(2011, 'SK')]
    assert winner_from_games(rows) == {2011: '삼성'}


def test_verify_flags_a_mismatch():
    """계산 결과와 표가 어긋나면 잡아야 합니다."""
    assert verify({2025: 'LG'}) == []
    bad = verify({2025: '한화'})
    assert bad == [(2025, 'LG', '한화')]


def test_verify_ignores_seasons_without_games():
    """2008년 전은 계산할 근거가 없어 넘어갑니다."""
    assert verify({1990: '엉뚱한팀'}) == []
    assert FIRST_COMPUTABLE == 2008


def test_verify_matches_games_derived_winners():
    """`games` 의 7777 경기에서 뽑은 값과 같아야 합니다.

    아래 값은 2026-08-29 에 D1 을 질의해 얻은 것입니다.

        SELECT season,
               CASE WHEN home_score > away_score
                    THEN home_team_id ELSE away_team_id END,
               COUNT(*)
          FROM games
         WHERE substr(game_id, 1, 4) = '7777'
           AND home_score IS NOT NULL AND home_score <> away_score
         GROUP BY 1, 2
    """
    wins = {
        2008: [('SK', 4), ('두산', 1)],
        2009: [('KIA', 4), ('SK', 3)],
        2010: [('SK', 4)],
        2011: [('삼성', 4), ('SK', 1)],
        2012: [('삼성', 4), ('SK', 2)],
        2013: [('삼성', 4), ('두산', 3)],
        2014: [('삼성', 4), ('넥센', 2)],
        2015: [('두산', 4), ('삼성', 1)],
        2016: [('두산', 4)],
        2017: [('KIA', 4), ('두산', 1)],
        2018: [('SK', 4), ('두산', 2)],
        2019: [('두산', 4)],
        2020: [('NC', 4), ('두산', 2)],
        2021: [('KT', 4)],
        2022: [('SSG', 4), ('키움', 2)],
        2023: [('LG', 4), ('KT', 1)],
        2024: [('KIA', 4), ('삼성', 1)],
        2025: [('LG', 4), ('한화', 1)],
    }
    rows = [(season, team)
            for season, pairs in wins.items()
            for team, n in pairs
            for _ in range(n)]
    assert verify(winner_from_games(rows)) == []


def test_sql_rewrites_the_whole_table():
    sql = to_sql()
    assert 'DELETE FROM korean_series_champion;' in sql
    assert sql.count('INSERT INTO korean_series_champion') == len(CHAMPIONS)
    # 그 시즌 표기명이어야 합니다. 1982년은 '두산' 이 아니라 'OB' 입니다.
    assert "VALUES (1982, 'OB'" in sql
    assert "VALUES (2001, '두산'" in sql
