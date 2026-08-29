# -*- coding: utf-8 -*-
"""한국시리즈 우승 이력입니다.

## 왜 표로 들고 있는가

KBO 사이트에는 한국시리즈 우승 이력을 주는 페이지가 없습니다.
`History/Champion/*`, `Record/Post/*`, `Schedule/*` 를 모두 두드려 봤지만
전부 404 였습니다. 우리 `games` 표에도 2008년부터만 있습니다.

그래서 두 갈래로 나눕니다.

    1982~2007   여기 적힌 표 (26회)
    2008~       `games` 의 `7777` 경기에서 계산 (4승 먼저 한 팀)

2008년 이후를 굳이 계산하는 이유는 **손으로 적은 값을 기계가 검산**
하도록 두기 위해서입니다. 표에 오타가 나면 `verify()` 가 잡습니다.

## 1985년

1985년에는 한국시리즈가 열리지 않았습니다. 삼성이 전기·후기를 모두
1위로 끝내 통합우승했기 때문입니다. 우승 구단으로는 세되 `note` 를
남겨 화면에서 밝힙니다.

## 계보

여기에는 **그 시즌 표기명**만 적습니다. 'OB' 이지 '두산' 이 아닙니다.
프랜차이즈로 묶는 일은 `team_seasons` 가 합니다. 계보 판단이 두 곳에
있으면 언젠가 어긋납니다.
"""

# 1982~2007 우승 구단입니다. 그 시즌 표기명입니다.
EARLY = [
    (1982, 'OB', ''),
    (1983, '해태', ''),
    (1984, '롯데', ''),
    (1985, '삼성', '전·후기 통합우승으로 한국시리즈가 열리지 않았습니다'),
    (1986, '해태', ''),
    (1987, '해태', ''),
    (1988, '해태', ''),
    (1989, '해태', ''),
    (1990, 'LG', ''),
    (1991, '해태', ''),
    (1992, '롯데', ''),
    (1993, '해태', ''),
    (1994, 'LG', ''),
    (1995, 'OB', ''),
    (1996, '해태', ''),
    (1997, '해태', ''),
    (1998, '현대', ''),
    (1999, '한화', ''),
    (2000, '현대', ''),
    (2001, '두산', ''),
    (2002, '삼성', ''),
    (2003, '현대', ''),
    (2004, '현대', ''),
    (2005, '삼성', ''),
    (2006, '삼성', ''),
    (2007, 'SK', ''),
]

# 2008년 이후입니다. `games` 에서 계산한 값과 같아야 합니다.
# `verify()` 가 그것을 확인합니다.
LATE = [
    (2008, 'SK', ''),
    (2009, 'KIA', ''),
    (2010, 'SK', ''),
    (2011, '삼성', ''),
    (2012, '삼성', ''),
    (2013, '삼성', ''),
    (2014, '삼성', ''),
    (2015, '두산', ''),
    (2016, '두산', ''),
    (2017, 'KIA', ''),
    (2018, 'SK', ''),
    (2019, '두산', ''),
    (2020, 'NC', ''),
    (2021, 'KT', ''),
    (2022, 'SSG', ''),
    (2023, 'LG', ''),
    (2024, 'KIA', ''),
    (2025, 'LG', ''),
]

CHAMPIONS = EARLY + LATE

# `games` 에서 한국시리즈 경기를 가리키는 접두입니다.
KS_PREFIX = '7777'
# 계산으로 확인할 수 있는 첫 시즌입니다. 그 전은 경기 기록이 없습니다.
FIRST_COMPUTABLE = 2008


def winner_from_games(rows):
    """한국시리즈 경기에서 시즌별 우승 구단을 뽑습니다.

    `rows` 는 `(season, winner_team_name)` 입니다. 무승부는 미리 빼고
    넣습니다. 한 시즌에 가장 많이 이긴 팀이 우승입니다.

    4승제라 4승을 먼저 하면 시리즈가 끝납니다. 그래서 최다승이 곧
    우승입니다. 동률은 나올 수 없습니다.
    """
    tally = {}
    for season, team in rows:
        tally.setdefault(season, {})
        tally[season][team] = tally[season].get(team, 0) + 1
    out = {}
    for season, teams in tally.items():
        best = max(teams.items(), key=lambda kv: kv[1])
        out[season] = best[0]
    return out


def verify(computed):
    """표와 계산 결과를 맞춰 봅니다. 어긋난 시즌 목록을 돌려줍니다.

    2008년 이후만 봅니다. 그 전은 계산할 근거가 없습니다.
    """
    table = {s: t for s, t, _ in CHAMPIONS}
    bad = []
    for season, team in sorted(computed.items()):
        if season < FIRST_COMPUTABLE:
            continue
        if table.get(season) != team:
            bad.append((season, table.get(season), team))
    return bad


def sql_literal(value):
    """작은따옴표를 두 번 써서 감쌉니다."""
    return "'" + str(value).replace("'", "''") + "'"


def to_sql():
    """적재용 SQL 입니다. 표를 통째로 다시 씁니다.

    45행짜리 표라 지우고 다시 넣는 편이 낫습니다. 어느 해가 바뀌었는지
    따지는 코드가 필요 없습니다.
    """
    lines = [
        'CREATE TABLE IF NOT EXISTS korean_series_champion (',
        '    season INTEGER PRIMARY KEY,',
        '    team_name TEXT NOT NULL,',
        '    note TEXT NOT NULL DEFAULT %s' % sql_literal(''),
        ');',
        'DELETE FROM korean_series_champion;',
    ]
    for season, team, note in CHAMPIONS:
        lines.append(
            'INSERT INTO korean_series_champion (season, team_name, note) '
            'VALUES (%d, %s, %s);'
            % (season, sql_literal(team), sql_literal(note)))
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else 'migration/out/korean_series.sql'
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(to_sql())
    print('%s (%d시즌)' % (out, len(CHAMPIONS)))
