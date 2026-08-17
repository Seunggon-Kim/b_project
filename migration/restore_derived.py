# -*- coding: utf-8 -*-
"""로컬 DB 에 빠진 파생·마스터 테이블을 복원한다.

배경
----
로컬 `database/kbo_stats.db` 는 2025 시즌 원천 데이터만 담은 축소본입니다.
2015~2024 와 2026 의 원천(games / play_by_play / 공식기록)은 EC2 에만 있었고
지금은 접근할 수 없습니다.

다행히 API 가 서빙에 쓰는 파생 테이블 두 개는 다른 곳에 온전히 남아 있습니다.

  - `database/_bak_20260605_dump.sql`
      wrc_plus_comparison           2015~2026
      weighted_pf_by_batter_season  2015~2026
      team_stadium_by_season        2015~2025
  - `cricket_project/database/kbo_stats.db`
      statiz_park_factor            2015~2025
      statiz_yearly_constants       2011~2026

`park_factors/build_wrc_plus.py` 로 재생성하면 안 됩니다. 그 스크립트는
DELETE 후 재삽입이라, 원천이 2025 뿐인 지금 돌리면 과거 시즌이 사라집니다.
재생성은 원천을 다시 수집한 뒤에 합니다.

`stadium_dim` 은 수동 마스터라 아래 시드로 만듭니다.

사용법
------
    py migration/restore_derived.py            # 미리보기
    py migration/restore_derived.py --write    # 실제 반영
"""
import argparse
import io
import os
import shutil
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get("KBO_DB") or os.path.join(ROOT, "database", "kbo_stats.db")
DUMP = os.path.join(ROOT, "database", "_bak_20260605_dump.sql")
# cricket_project 는 b_project 와 같은 상위 폴더에 있습니다.
CRICKET = os.environ.get("KBO_CRICKET_DB") or os.path.join(
    os.path.dirname(ROOT), "cricket_project", "database", "kbo_stats.db")

# 덤프 안의 이름 -> 복원할 이름
FROM_DUMP = {
    "wrc_plus_comparison_bak_20260605": "wrc_plus_comparison",
    "weighted_pf_by_batter_season_bak_20260605": "weighted_pf_by_batter_season",
    "team_stadium_by_season_bak_20260605": "team_stadium_by_season",
}

FROM_CRICKET = ["statiz_park_factor", "statiz_yearly_constants"]

# stadium_dim 시드. 컬럼 정의는 database/column_descriptions.json 을 따릅니다.
# (stadium_id, full_name, primary_team, active_from, active_to, is_temporary, note)
STADIUM_DIM = [
    (1, "서울종합운동장 야구장", "LG·두산", 1982, None, 0, "잠실, LG/두산 공동 사용"),
    (2, "고척스카이돔", "키움", 2016, None, 0, "고척, 국내 유일 돔구장"),
    (3, "목동야구장", "키움", 2008, 2015, 0, "목동, 2016년 고척 이전 전 홈구장"),
    (4, "인천 SSG 랜더스필드", "SSG", 2002, None, 0, "문학, 2021년 SK에서 SSG 로 승계"),
    (5, "케이티위즈파크", "KT", 2015, None, 0, "수원"),
    (6, "광주-KIA 챔피언스 필드", "KIA", 2014, None, 0, "광주"),
    (7, "사직야구장", "롯데", 1986, None, 0, "사직"),
    (8, "대구 삼성 라이온즈파크", "삼성", 2016, None, 0, "대구"),
    (9, "대구시민운동장 야구장", "삼성", 1948, 2015, 0, "대구 시민, 2016년 라팍 이전 전 홈구장"),
    (10, "창원NC파크", "NC", 2019, None, 0, "창원"),
    (11, "마산종합운동장 야구장", "NC", 2011, 2018, 0, "마산, 2019년 창원NC파크 이전 전 홈구장"),
    (12, "대전 한화생명 볼파크", "한화", 2025, None, 0, "대전, 2025년 신축 개장"),
    (13, "대전 한밭야구장", "한화", 1964, 2024, 0, "대전 한밭, 2025년 볼파크 이전 전 홈구장"),
    (14, "울산문수야구장", "롯데", 2014, None, 1, "울산, 롯데 제2구장"),
    (15, "청주야구장", "한화", 1979, None, 1, "청주, 한화 제2구장"),
    (16, "포항야구장", "삼성", 2012, None, 1, "포항, 삼성 제2구장"),
]

STADIUM_DIM_DDL = """
CREATE TABLE stadium_dim (
  stadium_id   INTEGER PRIMARY KEY,
  full_name    TEXT NOT NULL UNIQUE,
  primary_team TEXT,
  active_from  INTEGER,
  active_to    INTEGER,
  is_temporary INTEGER DEFAULT 0,
  note         TEXT
)
"""


def load_dump():
    """덤프를 메모리 DB 로 읽어 커넥션을 돌려준다."""
    with io.open(DUMP, "r", encoding="utf-8", errors="replace") as f:
        sql = f.read()
    con = sqlite3.connect(":memory:")
    con.executescript(sql)
    return con


def table_names(con):
    return {n for (n,) in con.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}


def copy_table(src, dst, src_name, dst_name):
    """src 의 테이블을 dst 로 통째로 옮긴다. 기존 dst 테이블은 지웁니다."""
    ddl = src.execute(
        "SELECT sql FROM sqlite_master WHERE name=?", (src_name,)).fetchone()[0]
    # CREATE TABLE <src_name> ... -> CREATE TABLE <dst_name> ...
    if src_name != dst_name:
        ddl = ddl.replace(src_name, dst_name, 1)
    cols = [r[1] for r in src.execute('PRAGMA table_info("%s")' % src_name)]
    rows = src.execute('SELECT * FROM "%s"' % src_name).fetchall()

    dst.execute('DROP TABLE IF EXISTS "%s"' % dst_name)
    dst.execute(ddl)
    dst.executemany(
        'INSERT INTO "%s" (%s) VALUES (%s)' % (
            dst_name,
            ",".join('"%s"' % c for c in cols),
            ",".join("?" * len(cols))),
        rows)
    return len(rows)


def season_span(con, name):
    cols = [r[1] for r in con.execute('PRAGMA table_info("%s")' % name)]
    if "season" not in cols:
        return ""
    rows = con.execute(
        'SELECT MIN(season), MAX(season), COUNT(DISTINCT season) FROM "%s"' % name
    ).fetchone()
    return "시즌 %s~%s (%s개)" % rows


def main(write):
    for p, label in ((DB, "로컬 DB"), (DUMP, "덤프")):
        if not os.path.exists(p):
            print("없음: %s (%s)" % (p, label))
            return 1
    has_cricket = os.path.exists(CRICKET)
    if not has_cricket:
        print("주의: cricket_project DB 를 찾지 못해 statiz 계열은 건너뜁니다.")
        print("      %s" % CRICKET)

    dump = load_dump()
    dumped = table_names(dump)
    for src_name in FROM_DUMP:
        if src_name not in dumped:
            print("덤프에 %s 가 없습니다." % src_name)
            return 1

    con = sqlite3.connect(DB)
    existing = table_names(con)

    print("=== 복원 대상 ===")
    for src_name, dst_name in FROM_DUMP.items():
        n = dump.execute('SELECT COUNT(*) FROM "%s"' % src_name).fetchone()[0]
        mark = " (기존 것을 덮어씀)" if dst_name in existing else ""
        print("  %-30s <- 덤프  %6s행  %s%s" % (
            dst_name, format(n, ","), season_span(dump, src_name), mark))
    if has_cricket:
        cri = sqlite3.connect("file:%s?mode=ro" % CRICKET.replace("\\", "/"),
                              uri=True)
        for t in FROM_CRICKET:
            if t not in table_names(cri):
                print("  %-30s <- cricket  (없음, 건너뜀)" % t)
                continue
            n = cri.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
            print("  %-30s <- cricket %6s행  %s" % (
                t, format(n, ","), season_span(cri, t)))
    print("  %-30s <- 시드   %6s행" % ("stadium_dim", len(STADIUM_DIM)))

    if not write:
        print()
        print("[미리보기] DB 를 바꾸지 않았습니다. --write 를 붙이면 반영합니다.")
        return 0

    bak = "%s.bak_%s" % (DB, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(DB, bak)
    print()
    print("백업: %s" % os.path.basename(bak))
    print()
    print("=== 반영 ===")

    for src_name, dst_name in FROM_DUMP.items():
        n = copy_table(dump, con, src_name, dst_name)
        print("  %-30s %6s행" % (dst_name, format(n, ",")))

    if has_cricket:
        for t in FROM_CRICKET:
            if t not in table_names(cri):
                continue
            n = copy_table(cri, con, t, t)
            print("  %-30s %6s행" % (t, format(n, ",")))
        cri.close()

    con.execute("DROP TABLE IF EXISTS stadium_dim")
    con.execute(STADIUM_DIM_DDL)
    con.executemany(
        "INSERT INTO stadium_dim (stadium_id, full_name, primary_team, "
        "active_from, active_to, is_temporary, note) VALUES (?,?,?,?,?,?,?)",
        STADIUM_DIM)
    print("  %-30s %6s행" % ("stadium_dim", len(STADIUM_DIM)))

    con.commit()

    # 시드가 실제 구장명을 모두 덮는지 확인합니다.
    known = {r[0] for r in con.execute("SELECT full_name FROM stadium_dim")}
    used = set()
    for q in ("SELECT DISTINCT home_stadium FROM weighted_pf_by_batter_season",
              "SELECT DISTINCT stadium FROM team_stadium_by_season"):
        used |= {r[0] for r in con.execute(q) if r[0]}
    gap = sorted(used - known)
    print()
    if gap:
        print("경고: stadium_dim 시드에 없는 구장명 %d개" % len(gap))
        for g in gap:
            print("    %s" % g)
    else:
        print("stadium_dim 이 실제 구장명 %d개를 모두 덮습니다." % len(used))

    con.close()
    dump.close()
    print("완료.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="실제로 DB 를 바꿉니다.")
    sys.exit(main(ap.parse_args().write))
