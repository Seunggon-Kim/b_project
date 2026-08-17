# -*- coding: utf-8 -*-
"""골든 응답 비교에 쓸 요청 조합을 만듭니다.

설계 문서 10장의 규칙을 따릅니다.
  - 파라미터 없음(기본값)
  - 실제 존재하는 값과 존재하지 않는 값
  - 데이터가 있는 시즌과 없는 시즌
  - 경계값 (limit=1, min_pa=0, min_pa=999)
  - 정렬·방향 파라미터의 지원 값 전부

원천과 파생의 시즌 범위가 다릅니다
-----------------------------------
로컬 DB 의 원천(games / play_by_play / 공식기록)은 2025 시즌뿐이지만, 복원한
파생 테이블(`wrc_plus_comparison`)에는 2015~2026 이 있습니다. 그래서 시즌 표본을
두 갈래로 뽑습니다. 파생 쪽 과거 시즌을 넣지 않으면 복원 데이터의 이식이
검증되지 않습니다.
"""
import re
import sqlite3
import sys

NONEXISTENT_PLAYER_ID = "99999999"
EMPTY_SEASON = 1990  # 데이터가 없는 시즌

# DB 탐색기가 보여 주는 테이블 중 성격이 다른 것들을 고릅니다.
DB_TABLES = ["players", "teams", "games", "play_by_play", "wrc_plus_comparison"]

# api/main.py 의 wrc_leaderboard 가 받는 정렬 키입니다.
WRC_SORTS = ("home", "half", "weighted", "wOBA")


def safe_name(text):
    """경로와 파라미터를 파일명으로 쓸 수 있는 문자열로 바꿉니다."""
    return re.sub(r"_+", "_", re.sub(r"[^0-9a-zA-Z]+", "_", text)).strip("_")


def _has_table(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,)).fetchone() is not None


def _sample_players(conn, n=3):
    rows = conn.execute(
        "SELECT player_id FROM players ORDER BY player_id LIMIT ?", (n,)
    ).fetchall()
    return [str(r[0]) for r in rows]


def _sample_batters(conn, n=3):
    """wRC+ 조회에 쓸 batter_ID. 타석이 많은 순으로 뽑습니다.

    players.player_id 와는 다른 식별자입니다. 여기를 헷갈리면 응답이 전부
    비어 이식 검증이 무의미해집니다.
    """
    if not _has_table(conn, "wrc_plus_comparison"):
        return []
    rows = conn.execute(
        "SELECT batter_ID FROM wrc_plus_comparison "
        "ORDER BY PA DESC, batter_ID LIMIT ?", (n,)).fetchall()
    return [str(r[0]) for r in rows]


def _seasons(conn):
    """원천 데이터가 있는 시즌. 최신순."""
    rows = conn.execute(
        "SELECT DISTINCT season FROM games ORDER BY season DESC").fetchall()
    return [int(r[0]) for r in rows]


def _derived_seasons(conn):
    """파생 테이블이 덮는 시즌 중 최신·중간·최초를 뽑습니다."""
    if not _has_table(conn, "wrc_plus_comparison"):
        return []
    rows = conn.execute(
        "SELECT DISTINCT season FROM wrc_plus_comparison ORDER BY season"
    ).fetchall()
    seasons = [int(r[0]) for r in rows]
    if not seasons:
        return []
    picks = {seasons[-1], seasons[0], seasons[len(seasons) // 2]}
    return sorted(picks)


def _add(matrix, path, params=None, tag=""):
    params = params or {}
    key = path + ("_" + tag if tag else "")
    if params:
        key += "_" + "_".join("%s_%s" % (k, params[k]) for k in sorted(params))
    name = safe_name(key)

    # 루트 경로 '/' 는 safe_name 을 거치면 빈 문자열이 됩니다. 그대로 두면
    # 파일이 '.json' 으로 저장되어 확장자만 있는 숨김 파일이 됩니다.
    if not name:
        name = "root"

    # safe_name 이 한글 등 ASCII 외 문자를 지우므로 q=김 과 q= 의 이름이 같아집니다.
    # 파일이 덮어써지지 않도록 겹치면 번호를 붙입니다. 목록 순서가 같으면
    # 매번 같은 이름이 나오므로 정답지와 실제 응답의 파일명이 어긋나지 않습니다.
    existing = {item["name"] for item in matrix}
    if name in existing:
        n = 2
        while "%s_%d" % (name, n) in existing:
            n += 1
        name = "%s_%d" % (name, n)

    matrix.append({"name": name, "path": path, "params": params})


def build_matrix(conn):
    """요청 조합 목록을 만듭니다."""
    players = _sample_players(conn)
    batters = _sample_batters(conn)
    seasons = _seasons(conn)
    season = seasons[0] if seasons else 2026
    prev = seasons[1] if len(seasons) > 1 else season - 1
    wrc_seasons = _derived_seasons(conn) or [season]
    matrix = []

    # 파라미터 없는 엔드포인트.
    # /leaders 는 season 이 필수라 422 가 납니다. 그 422 도 이식 대상이라 넣습니다.
    for path in ["/", "/dashboard/stats", "/teams", "/stats/seasons",
                 "/stats/regulation", "/standings", "/db/tables",
                 "/schedule", "/schedule/futures", "/leaders"]:
        _add(matrix, path)

    # 시즌 파라미터
    for path in ["/games", "/leaders"]:
        for s in (season, prev, EMPTY_SEASON):
            _add(matrix, path, {"season": s})

    # 타자·투수 기록: 경계값 포함
    for path, minkey in [("/stats/batters", "min_pa"),
                         ("/stats/pitchers", "min_ip")]:
        _add(matrix, path, {"season": season})
        _add(matrix, path, {"season": season, "limit": 1})
        _add(matrix, path, {"season": season, minkey: 0})
        _add(matrix, path, {"season": season, minkey: 999})
        _add(matrix, path, {"season": EMPTY_SEASON})

    # 선수 상세: 존재하는 ID 3개 + 존재하지 않는 ID
    for pid in players:
        for suffix in ["", "/news", "/arsenal", "/usage"]:
            _add(matrix, "/players/%s%s" % (pid, suffix))
    for suffix in ["", "/news", "/arsenal", "/usage"]:
        _add(matrix, "/players/%s%s" % (NONEXISTENT_PLAYER_ID, suffix),
             tag="nonexistent")

    # 선수 검색
    for q in ["김", "zzzz", ""]:
        _add(matrix, "/players/search", {"q": q})

    # 기간별 팀 기록
    _add(matrix, "/stats/team_range", {"start": "%d0301" % season,
                                       "end": "%d1031" % season})
    _add(matrix, "/stats/team_range", {"start": "%d0301" % season,
                                       "end": "%d0301" % season})

    # wRC+ 계열. 파생 테이블은 과거 시즌까지 있으므로 함께 훑습니다.
    _add(matrix, "/wrc/seasons")
    _add(matrix, "/wrc/seasons", {"min_pa": 0})
    for s in list(wrc_seasons) + [EMPTY_SEASON]:
        _add(matrix, "/wrc/by-stadium", {"season": s})
        _add(matrix, "/wrc/distribution", {"season": s, "min_pa": 100})
        _add(matrix, "/wrc/leaderboard", {"season": s, "min_pa": 999})
        for direction in ("up", "down"):
            _add(matrix, "/wrc/top-changes",
                 {"season": s, "direction": direction, "n": 5})
    # 정렬 키는 최신 시즌에서 전부 훑습니다.
    for sort in WRC_SORTS:
        _add(matrix, "/wrc/leaderboard",
             {"season": wrc_seasons[-1], "sort": sort, "n": 5})

    for bid in batters:
        _add(matrix, "/wrc/batter/%s" % bid)
    _add(matrix, "/wrc/batter/%s" % NONEXISTENT_PLAYER_ID, tag="nonexistent")
    _add(matrix, "/wrc/batter-search", {"q": "김", "season": season})
    _add(matrix, "/wrc/batter-search", {"q": "zzzz", "season": season})
    _add(matrix, "/wrc/batter-search", {"q": "", "season": 0})

    # DB 탐색
    for t in DB_TABLES:
        _add(matrix, "/db/table/%s" % t, {"limit": 5, "offset": 0})
        _add(matrix, "/db/table/%s" % t, {"limit": 5, "offset": 1000000},
             tag="far_offset")
        _add(matrix, "/db/table/%s/csv" % t, {"limit": 5})
    _add(matrix, "/db/table/no_such_table", {"limit": 5}, tag="nonexistent")

    # 로고
    _add(matrix, "/logo/LG")
    _add(matrix, "/logo/ZZ", tag="nonexistent")

    # 날짜 지정 일정.
    # /schedule 은 date 를 그대로 네이버에 넘기므로 YYYY-MM-DD 여야 합니다
    # (api/main.py:1190-1193). YYYYMMDD 로 보내면 400 이 돌아와 games 가
    # 빈 배열이 되고, 정답지로서 값을 잃습니다.
    game_day = "%d-04-01" % season
    _add(matrix, "/schedule", {"date": game_day})
    _add(matrix, "/schedule/futures", {"date": game_day})

    return matrix


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else "database/kbo_stats.db"
    conn = sqlite3.connect(db)
    matrix = build_matrix(conn)
    for item in matrix:
        print("%-46s %s" % (item["path"], item["params"] or ""))
    print()
    print("총 %d개 요청" % len(matrix))


if __name__ == "__main__":
    main()
