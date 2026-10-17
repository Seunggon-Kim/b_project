# -*- coding: utf-8 -*-
"""KBO 사이트에서 받은 표를 네이버 값으로 한 번에 바꿉니다(계획서 Task 7).

KBO 이용약관 제14조 차항(2026-10-14 시행)에 따라 evan 이 정했습니다(2026-10-18).

    결정 1  2007 이전 공식 기록·팀 순위는 백업 파일로 빼고 지웁니다.
    결정 2  네이버에 없는 타자 행은 지웁니다(그 시즌을 지우고 다시 넣으면 사라짐).
    결정 6  같은 표에 덮어씁니다. 덮기 전 백업 덤프, MySQL PITR 7일.

차례(--step 으로 하나씩, 기본은 미리보기만):

    backup     네 표 전체를 ~/.bstats/backups/<표>_kbo_<날짜>.sql 로(읽기만)
    report     바꿀 내용 미리보기: 시즌·표별 지울 행·넣을 행·칸별로 바뀌는 값 수
               (docs/naver-migration/dry-run.md). DB 는 읽기만 합니다.
    pre2008    2007 이전 kbo_official_*·team_season_rank 행을 지웁니다       (쓰기)
    ranks      2008~ team_season_rank 를 네이버 값으로                         (쓰기)
    official   2008~ 두 공식 표를 네이버·박스·PBP 값으로                        (쓰기)
    players    players 를 네이버 상세·PBP 투타로(결정 5)                        (쓰기)

쓰기 단계는 --execute 를 붙여야 씁니다. 각 단계는 mysql_sink.mirror 한 트랜잭션입니다
(official 은 시즌마다 한 트랜잭션).

되돌리기: backup 이 만든 .sql 을 그 표에 다시 넣습니다(먼저 그 표를 비움). 또는 Cloud
SQL PITR 로 쓰기 직전 시각으로 복제본을 만들어 옮깁니다.
"""
import argparse
import collections
import datetime
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))
sys.path.insert(0, str(ROOT))

TABLES = ("kbo_official_batter_stats", "kbo_official_pitcher_stats", "team_season_rank",
          "team_seasons", "players")
BACKUP_DIR = Path(os.path.expanduser("~")) / ".bstats" / "backups"
FIRST = 2008


def sql_literal(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return "'%s'" % v
    return "'%s'" % str(v).replace("\\", "\\\\").replace("'", "''")


def backup(query, out_dir=BACKUP_DIR, stamp=None):
    stamp = stamp or datetime.date.today().strftime("%Y%m%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    done = []
    for t in TABLES:
        rows = query("SELECT * FROM `%s`" % t)
        p = out_dir / ("%s_kbo_%s.sql" % (t, stamp))
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write("-- %s 백업 %d행 (naver_swap.py backup)\n" % (t, len(rows)))
            for r in rows:
                cols = ", ".join("`%s`" % c for c in r)
                f.write("INSERT INTO `%s` (%s) VALUES (%s);\n"
                        % (t, cols, ", ".join(sql_literal(v) for v in r.values())))
        done.append((t, len(rows), str(p)))
    return done


def same(a, b):
    if a in (None, "") and b in (None, ""):
        return True
    if a in (None, "") or b in (None, ""):
        return False
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()


def diff_rows(old, new, key, columns):
    """(지울 키, 넣을 키, {칸: 바뀌는 행 수})."""
    o = {key(r): r for r in old}
    n = {key(r): r for r in new}
    changed = collections.Counter()
    for k in set(o) & set(n):
        for c in columns:
            if not same(o[k].get(c), n[k].get(c)):
                changed[c] += 1
    return sorted(set(o) - set(n)), sorted(set(n) - set(o)), changed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--step", required=True,
                    choices=["backup", "report", "pre2008", "ranks", "official", "players"])
    ap.add_argument("--from", dest="first", type=int, default=FIRST)
    ap.add_argument("--to", dest="last", type=int)
    ap.add_argument("--box-dir")
    ap.add_argument("--naver-cache")
    ap.add_argument("--report-out", default=str(ROOT / "docs" / "naver-migration" / "dry-run.md"))
    ap.add_argument("--execute", action="store_true", help="쓰기 단계를 실제로 씁니다")
    a = ap.parse_args(argv)
    from d1_load import query
    from kbo_season import record_season
    last = a.last or record_season()
    seasons = list(range(a.first, last + 1))

    if a.step == "backup":
        for t, n, p in backup(query):
            print("%s %d행 → %s" % (t, n, p))
        return 0

    import naver_official_stats as no
    import naver_team_ranks as ntr
    names = {(r["franchise_id"], int(r["season"])): r["team_name"]
             for r in query("SELECT franchise_id, season, team_name FROM team_seasons")}

    def built(y):
        import naver_box_stats as nbx
        reg = no.regular_game_ids(query, y)
        files = [f for f in nbx.season_files(a.box_dir or no.DEFAULT_BOX_DIR, y)
                 if f.name.split(".")[0] in reg]
        if len(files) < len(reg):
            raise SystemExit("%d 박스가 %d/%d 경기뿐입니다. naver_boxscore.py 로 먼저 받으십시오."
                             % (y, len(files), len(reg)))
        return no.build_season(y, names, no.load_pbp(query, y, reg), files, a.naver_cache)

    if a.step == "report":
        lines = ["# 네이버 전환 미리보기(dry-run)", "",
                 "`migration/naver_swap.py --step report` 가 만든 표입니다. DB 는 읽기만 했습니다.", ""]
        pre = {t: query("SELECT COUNT(*) AS n FROM `%s` WHERE season < %d" % (t, FIRST))[0]["n"]
               for t in ("kbo_official_batter_stats", "kbo_official_pitcher_stats", "team_season_rank")}
        lines += ["## 2007 이전(결정 1: 지움)", "", "| 표 | 지울 행 |", "|---|---|"]
        lines += ["| %s | %d |" % (t, n) for t, n in pre.items()]
        lines += ["", "## 시즌별(2008~)", "",
                  "| 시즌 | 표 | 지금 | 새로 | 지울 행 | 넣을 행 | 값이 바뀌는 칸(행 수) |", "|---|---|---|---|---|---|---|"]
        for y in seasons:
            bats, pits, note = built(y)
            for t, new, cols in (("kbo_official_batter_stats", bats, no.BATTER_COLUMNS),
                                 ("kbo_official_pitcher_stats", pits, no.PITCHER_COLUMNS)):
                old = query("SELECT * FROM `%s` WHERE season = %d" % (t, y))
                gone, add, ch = diff_rows(old, new, lambda r: int(r["player_id"]), cols)
                top = ", ".join("%s %d" % (c, n) for c, n in ch.most_common(8))
                lines.append("| %d | %s | %d | %d | %d | %d | %s |" % (y, t.replace("kbo_official_", "").replace("_stats", ""),
                                                                    len(old), len(new), len(gone), len(add), top))
            ranks = ntr.to_rows(ntr.fetch(y), y, names)
            old = query("SELECT * FROM team_season_rank WHERE season = %d" % y)
            gone, add, ch = diff_rows(old, ranks, lambda r: r["franchise_id"] or r["team_name"], ntr.COLUMNS)
            lines.append("| %d | team_season_rank | %d | %d | %d | %d | %s |" % (
                y, len(old), len(ranks), len(gone), len(add), ", ".join("%s %d" % x for x in ch.most_common(5))))
            print(y, note, flush=True)
        Path(a.report_out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.report_out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("썼습니다: %s" % a.report_out)
        return 0

    if not a.execute:
        print("[미리보기] --execute 가 없어 쓰지 않습니다. 먼저 --step backup 을 하십시오.")
        return 0
    from mysql_sink import mirror
    if a.step == "pre2008":
        def drop(sink):
            n = 0
            for t in ("kbo_official_batter_stats", "kbo_official_pitcher_stats", "team_season_rank"):
                n += sink.execute("DELETE FROM `%s` WHERE season < %%s" % t, (FIRST,))
                sink.refresh_count(t)
            return n
        mirror("naver_swap", drop)
    elif a.step == "ranks":
        rows = [r for y in seasons for r in ntr.to_rows(ntr.fetch(y), y, names)]
        mirror("naver_swap", lambda sink: ntr.write(sink, rows, seasons, names))
    elif a.step == "official":
        for y in seasons:
            bats, pits, note = built(y)
            mirror("naver_swap", lambda sink: no.write(sink, y, bats, pits))
            print(y, len(bats), len(pits), note, flush=True)
    elif a.step == "players":
        import naver_players
        return naver_players.main(["--all"] + (["--naver-cache", a.naver_cache] if a.naver_cache else []))
    return 0


if __name__ == "__main__":
    sys.exit(main())
