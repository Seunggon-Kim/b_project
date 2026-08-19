# -*- coding: utf-8 -*-
"""나뉜 D1 이 한 표였을 때와 같은 답을 주는지 확인합니다.

정답지는 로컬 SQLite `database/kbo_stats.db` 입니다. 여기에는 270만 행이
한 표에 그대로 들어 있습니다. 워커는 같은 행을 네 D1 에 나눠 담고 있으니,
두 답이 같아야 나누기가 옳게 된 것입니다.

앞서 쓰던 골든 정답지는 2025 시즌만 있던 시절에 뜬 것이라 더는 기준이
되지 못합니다. 그래서 이 파일을 따로 둡니다.
"""
import json
import sqlite3
import sys
import urllib.request

BASE = "http://127.0.0.1:8787"
DB = "database/kbo_stats.db"

PITCH_FILTER = (
    "pitch_type IS NOT NULL AND pitch_type NOT IN ('', '-', 'null')")


def get(path):
    # User-Agent 를 주지 않으면 클라우드플레어가 403 을 돌려줍니다.
    req = urllib.request.Request(BASE + path, headers={
        "User-Agent": "kbo-shard-verify/1.0",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def rng(season):
    return season * 10000, (season + 1) * 10000


class Check(object):
    def __init__(self):
        self.ok = 0
        self.bad = []

    def eq(self, name, want, got):
        if want == got:
            self.ok += 1
            print("  일치  %s" % name)
        else:
            self.bad.append(name)
            print("  다름  %s" % name)
            print("        정답 %r" % (want,))
            print("        워커 %r" % (got,))


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = Check()

    print("1) 플레이 수 합계")
    want = conn.execute("SELECT COUNT(*) FROM play_by_play").fetchone()[0]
    c.eq("dashboard.plays", want, get("/dashboard/stats")["plays"])

    print("2) 투수 구종 (시즌 하나 -> 담당 D1 한 개)")
    for pid, season in (("50030", 2026), ("50030", 2019), ("50030", 2015)):
        lo, hi = rng(season)
        rows = conn.execute(
            "SELECT pitch_type, px, pz, speed, pitch_result, pfx_x, pfx_z,"
            " game_date, x0, z0, sz_top, sz_bot FROM play_by_play"
            " WHERE pitcher_ID = ? AND game_date >= ? AND game_date < ?"
            " AND px IS NOT NULL AND pz IS NOT NULL AND " + PITCH_FILTER,
            (pid, lo, hi)).fetchall()
        got = get("/players/%s/arsenal?season=%d" % (pid, season))
        c.eq("arsenal %s %d 개수" % (pid, season), len(rows), got["count"])
        if rows and got["arsenal"]:
            # 순서까지 같아야 합니다. 화면이 순서대로 그립니다.
            want_first = dict(rows[0])
            got_first = got["arsenal"][0]
            c.eq("arsenal %s %d 첫 행" % (pid, season),
                 want_first, {k: got_first.get(k) for k in want_first})

    print("3) 구사율")
    for pid, season in (("50030", 2026), ("50030", 2018)):
        lo, hi = rng(season)
        n = conn.execute(
            "SELECT COUNT(*) FROM play_by_play WHERE pitcher_ID = ?"
            " AND game_date >= ? AND game_date < ? AND " + PITCH_FILTER,
            (pid, lo, hi)).fetchone()[0]
        got = get("/players/%s/usage?season=%d" % (pid, season))
        c.eq("usage %s %d 총 투구" % (pid, season), n,
             got.get("total_pitches", 0))

    print("4) 구장별 분포 (전 시즌 -> 네 D1 이어붙이기)")
    for bid in ("67025", "77532"):
        rows = conn.execute(
            "SELECT CAST(game_date / 10000 AS TEXT) AS season, stadium,"
            " COUNT(*) AS pa FROM play_by_play WHERE batter_ID = ?"
            " GROUP BY season, stadium ORDER BY season, pa DESC",
            (bid,)).fetchall()
        want = [dict(r) for r in rows]
        got = get("/wrc/batter/%s" % bid)["stadium_distribution"]
        c.eq("stadium_dist %s" % bid, want, got)

    print("5) 데이터 탐색기 페이지 넘기기 (샤드 경계 넘김)")
    # 정답지의 행 순서를 워커와 같게 맞춥니다.
    #
    # 워커는 샤드를 시즌 순으로 늘어놓고, 샤드 안은 rowid(=pbp_id) 순으로
    # 읽습니다. 그런데 로컬 DB 의 pbp_id 는 시즌 순이 아닙니다. 2025·2026 을
    # 먼저 적재하고 2015~2024 를 나중에 붙였기 때문에 1~405,416 이
    # 2025·2026 입니다. 그래서 로컬을 그냥 rowid 순으로 읽으면 워커와
    # 다른 행이 나옵니다. 데이터가 틀린 것이 아니라 순서 기준이 다릅니다.
    #
    # 아래 CASE 가 샤드 경계를 그대로 흉내 냅니다.
    SHARD_ORDER = """
        CASE WHEN game_date < 20180000 THEN 0
             WHEN game_date < 20210000 THEN 1
             WHEN game_date < 20240000 THEN 2
             ELSE 3 END, pbp_id
    """
    for off in (0, 700000, 1000000, 2100000, 2717112):
        rows = conn.execute(
            "SELECT pbp_id FROM play_by_play ORDER BY " + SHARD_ORDER
            + " LIMIT 5 OFFSET ?", (off,)).fetchall()
        want = [r["pbp_id"] for r in rows]
        got = get("/db/table/play_by_play?limit=5&offset=%d" % off)
        c.eq("db_table offset=%d pbp_id" % off, want,
             [r["pbp_id"] for r in got["rows"]])
        if off == 0:
            c.eq("db_table total", conn.execute(
                "SELECT COUNT(*) FROM play_by_play").fetchone()[0],
                got["total"])

    print("6) 기간별 팀성적 (기간이 걸치는 D1 만)")
    for a, b in (("2015-04-01", "2015-04-30"),
                 ("2017-09-01", "2018-05-31"),
                 ("2022-06-01", "2022-06-30")):
        lo = int(a.replace("-", ""))
        hi = int(b.replace("-", ""))
        want_pa = conn.execute(
            "SELECT COUNT(*) FROM play_by_play p"
            " JOIN games gm ON gm.game_id = p.gameID"
            " WHERE gm.game_date>=? AND gm.game_date<=?"
            " AND gm.game_type='정규시즌'"
            " AND p.pa_result IS NOT NULL AND p.pa_result<>''",
            (lo, hi)).fetchone()[0]
        want_r = conn.execute(
            "SELECT COALESCE(SUM(p.runs_scored),0) FROM play_by_play p"
            " JOIN games gm ON gm.game_id = p.gameID"
            " WHERE gm.game_date>=? AND gm.game_date<=?"
            " AND gm.game_type='정규시즌'", (lo, hi)).fetchone()[0]
        got = get("/stats/team_range?start=%s&end=%s" % (a, b))
        c.eq("team_range %s~%s PA 합" % (a, b), want_pa,
             sum(x.get("PA", 0) for x in got["batting"]))
        c.eq("team_range %s~%s 득점 합" % (a, b), want_r,
             sum(x.get("R", 0) for x in got["batting"]))

    print()
    print("일치 %d건, 불일치 %d건" % (c.ok, len(c.bad)))
    for name in c.bad:
        print("  - %s" % name)
    return 1 if c.bad else 0


if __name__ == "__main__":
    sys.exit(main())
