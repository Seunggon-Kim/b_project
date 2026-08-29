# -*- coding: utf-8 -*-
"""잘린 경기를 가려냅니다.

## 왜 필요한가

네이버가 주는 PBP 가 경기 도중에 끊긴 것이 있습니다. 2008~2011 에
몰려 있고(20~35경기), 다시 받아도 똑같습니다. **우리 수집 문제가
아니라 원천이 불완전합니다.** 예를 들어 2008-05-03 두산-LG 전은
최종 20점인데 PBP 는 2회에서 끝나고 6점만 있습니다.

이런 경기를 그대로 두면 계산이 두 군데서 틀어집니다.

    RE24        3회에서 끊긴 경기를 넣으면 '그 뒤로 득점이 없었다' 고
                배웁니다. 기대득점이 낮게 잡히고, 그러면 아웃의 손실도
                작아져 wOBA 가중치의 장타 쪽이 부풀려집니다.
    파크팩터     그 구장의 득점이 실제보다 적게 잡힙니다.

## 어떻게 가리는가

**마지막 이닝이 9회 미만이고 득점이 최종 점수보다 적으면** 잘린
것입니다. 우천 콜드게임은 5회에 끝나도 득점이 최종 점수와 맞아서
걸리지 않습니다.

9회까지 있는데 득점이 2점 이상 모자란 경기도 함께 뺍니다(연장 누락).
1점 차이는 흔해서 남깁니다.
"""

CREATE = """
CREATE TABLE IF NOT EXISTS truncated_games (
    game_id TEXT PRIMARY KEY,
    season INTEGER NOT NULL,
    last_inning INTEGER,
    final_runs INTEGER,
    pbp_runs INTEGER,
    reason TEXT
)
"""

# 9회까지 있는 경기에서 이만큼 이상 모자라면 뺍니다.
SHORT_GAP = 2


def find(cur):
    """잘린 경기를 찾아 튜플 목록으로 돌려줍니다."""
    rows = cur.execute("""
        SELECT g.game_id, g.season,
               g.home_score + g.away_score AS fin,
               MAX(p.inning) AS last_inn,
               SUM(COALESCE(p.runs_scored, 0)) AS pbp
          FROM games g
          JOIN play_by_play p ON p.gameID = g.game_id
         WHERE g.home_score IS NOT NULL
         GROUP BY g.game_id""").fetchall()
    out = []
    for r in rows:
        fin, pbp, inn = r['fin'], r['pbp'], r['last_inn']
        if inn is not None and inn < 9 and fin > pbp:
            out.append((r['game_id'], r['season'], inn, fin, pbp, '이닝 잘림'))
        elif inn is not None and inn >= 9 and fin - pbp >= SHORT_GAP:
            out.append((r['game_id'], r['season'], inn, fin, pbp, '득점 모자람'))
    return out


def rebuild(con):
    """`truncated_games` 를 다시 만듭니다. 넣은 행 수를 돌려줍니다."""
    cur = con.cursor()
    cur.execute(CREATE)
    cur.execute('DELETE FROM truncated_games')
    rows = find(cur)
    cur.executemany(
        'INSERT INTO truncated_games '
        '(game_id, season, last_inning, final_runs, pbp_runs, reason) '
        'VALUES (?,?,?,?,?,?)', rows)
    con.commit()
    return len(rows)


# 계산기들이 WHERE 절에 붙일 조건입니다. 표가 없는 환경에서도 돌도록
# EXISTS 대신 NOT IN 을 쓰고, 표가 없으면 부르는 쪽에서 뺍니다.
EXCLUDE_SQL = (
    " AND g.game_id NOT IN (SELECT game_id FROM truncated_games) ")


def exclude_clause(cur, alias='g'):
    """표가 있으면 제외 조건을, 없으면 빈 문자열을 돌려줍니다."""
    has = cur.execute(
        "SELECT COUNT(*) FROM sqlite_master "
        "WHERE type='table' AND name='truncated_games'").fetchone()[0]
    if not has:
        return ''
    return (" AND %s.game_id NOT IN "
            "(SELECT game_id FROM truncated_games) " % alias)


if __name__ == '__main__':
    import os
    import sqlite3
    db = os.environ.get('KBO_DB', r'C:\tmp\kbo_pipeline.db')
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    n = rebuild(con)
    print('잘린 경기 %d개' % n)
    for r in con.execute(
            'SELECT season, reason, COUNT(*) n FROM truncated_games '
            'GROUP BY season, reason ORDER BY season'):
        print('  %d  %-12s %d' % (r['season'], r['reason'], r['n']))
    con.close()
