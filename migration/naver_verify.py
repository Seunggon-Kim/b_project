# -*- coding: utf-8 -*-
"""네이버로 만든 공식 기록 칸을 지금 DB 값(10/14 전에 KBO 에서 받은 값)과 맞춰 봅니다.

KBO 이용약관(2026-10-14 시행)으로 공식 기록을 네이버 시즌 API·박스스코어·PBP 로
바꿉니다(data_collection/naver_official_stats.py). 칸마다, 시즌마다 지금 값과 같은
행의 비율을 세어 **99% 이상인 (칸, 시즌)만** 쓰기로 합니다(evan 결정 3).

    database/naver_verified.json            칸 → 통과한 시즌 목록(수집기가 읽음)
    docs/naver-migration/official-verify.md  칸 × 시즌 일치율 표

지금 DB 값은 전환(migration/naver_swap.py)하면 사라집니다. 그래서 이 검증은 전환
**전에** 한 번 돌리고 결과 파일을 저장소에 둡니다. 전환 뒤 새 시즌은 가장 최근에
통과한 시즌의 결과를 따릅니다(naver_official_stats.allowed).

지금 값을 MySQL 에서 읽거나(기본), 공개 API 로 받아 둔 CSV(--csv-dir, 표 이름.csv)를
씁니다. PBP 는 MySQL 에서 읽거나 시즌별 피클(--pbp-dir, <시즌>.pkl.gz, 행 dict 목록)을
씁니다.

    py migration/naver_verify.py --from 2008 --to 2026 --box-dir ~/.bstats/naver_boxscore
"""
import argparse
import collections
import csv
import datetime
import gzip
import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))
sys.path.insert(0, str(ROOT))

import naver_box_stats as nbx  # noqa: E402
import naver_official_stats as no  # noqa: E402

THRESHOLD = 0.99
OUT_JSON = ROOT / "database" / "naver_verified.json"
OUT_MD = ROOT / "docs" / "naver-migration" / "official-verify.md"
TABLE = {"batter": "kbo_official_batter_stats", "pitcher": "kbo_official_pitcher_stats"}


def same(a, b):
    if a in (None, "") and b in (None, ""):
        return True
    if a in (None, "") or b in (None, ""):
        return False
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()


def rates(old_rows, new_rows, columns):
    """{칸: (같은 행, 쓴 행, 비운 행)} — 두 쪽에 다 있는 선수만 셉니다.

    '비운 행'은 우리가 None 으로 둔 행입니다(PBP 가 온전하지 않은 선수 등). 그 행은
    틀린 값을 쓰지 않으므로 맞음·틀림에 넣지 않고 따로 셉니다. 지금 DB 도 비어
    있으면 같은 것으로 봅니다.
    """
    old = {int(float(r["player_id"])): r for r in old_rows}
    new = {int(r["player_id"]): r for r in new_rows}
    both = set(old) & set(new)
    out = {}
    for c in columns:
        if c in ("player_id", "season"):
            continue
        ok = written = blank = 0
        for p in both:
            a, b = old[p].get(c), new[p].get(c)
            if b is None and a not in (None, ""):
                blank += 1
                continue
            written += 1
            ok += same(a, b)
        out[c] = (ok, written, blank)
    return out


def passed(table, threshold=THRESHOLD):
    """{칸: [통과한 시즌]} table = {시즌: {칸: (ok, 쓴 행, 비운 행)}}.

    쓴 행의 99% 이상이 지금 값과 같고, 쓴 행이 하나 이상인 시즌만 통과입니다.
    """
    out = collections.defaultdict(list)
    for y, cols in sorted(table.items()):
        for c, (ok, n, _blank) in cols.items():
            if n and ok / n >= threshold:
                out[c].append(int(y))
    return dict(out)


def markdown(result):
    lines = ["# 네이버 전환 칸 검증", "",
             "`migration/naver_verify.py` 가 만든 표입니다. 지금 DB 값(2026-10-14 전에 KBO 에서 받은 값)과",
             "네이버로 만든 값이 같은 행의 비율(%)입니다. 두 쪽에 다 있는 선수만 셉니다.",
             "괄호 안은 우리가 비운 행 수입니다(PBP 중계가 끊겨 셀 수 없는 선수 등, 틀린 값을 쓰지 않음).",
             "쓴 행의 99% 이상이 같은 칸·시즌만 씁니다(**굵게**). 나머지는 비우고 화면에서 숨깁니다.", ""]
    for kind in ("batter", "pitcher"):
        t = result[kind]
        ys = sorted(t)
        if not ys:
            continue
        lines += ["## %s" % ("타자" if kind == "batter" else "투수"), "",
                  "| 칸 | " + " | ".join(str(y) for y in ys) + " |",
                  "|---|" + "---|" * len(ys)]
        for c in t[ys[0]]:
            cells = []
            for y in ys:
                ok, n, blank = t[y][c]
                v = 100.0 * ok / n if n else 0.0
                cell = ("**%.1f**" if n and ok / n >= THRESHOLD else "%.1f") % v
                cells.append(cell + (" (%d)" % blank if blank else ""))
            lines.append("| %s | %s |" % (c, " | ".join(cells)))
        lines.append("")
    notes = result.get("notes") or {}
    if notes:
        lines += ["## 시즌별 메모", "", "| 시즌 | 메모 |", "|---|---|"]
        lines += ["| %s | %s |" % (y, json.dumps(v, ensure_ascii=False)) for y, v in sorted(notes.items())]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--from", dest="first", type=int, default=2008)
    ap.add_argument("--to", dest="last", type=int, default=2026)
    ap.add_argument("--box-dir", default=str(no.DEFAULT_BOX_DIR))
    ap.add_argument("--csv-dir")
    ap.add_argument("--pbp-dir")
    ap.add_argument("--naver-cache")
    ap.add_argument("--out-json", default=str(OUT_JSON))
    ap.add_argument("--out-md", default=str(OUT_MD))
    ap.add_argument("--rates-file", help="시즌별 일치율을 이 파일에 쌓습니다(여러 번 나눠 돌릴 때)")
    a = ap.parse_args(argv)

    if a.csv_dir:
        def load(t):
            with open(Path(a.csv_dir) / ("%s.csv" % t), encoding="utf-8-sig", newline="") as f:
                return list(csv.DictReader(f))
        games = load("games")
        old = {k: collections.defaultdict(list) for k in TABLE}
        for k, t in TABLE.items():
            for r in load(t):
                old[k][int(r["season"])].append(r)
        names = {(r["franchise_id"], int(r["season"])): r["team_name"] for r in load("team_seasons")}
        reg_of = lambda y: {g["game_id"] for g in games if g["season"] == str(y) and g["game_type"] == "정규시즌"}  # noqa: E731
        old_of = lambda k, y: old[k][y]  # noqa: E731
    else:
        from d1_load import query
        names = {(r["franchise_id"], int(r["season"])): r["team_name"]
                 for r in query("SELECT franchise_id, season, team_name FROM team_seasons")}
        reg_of = lambda y: no.regular_game_ids(query, y)  # noqa: E731
        old_of = lambda k, y: query("SELECT * FROM %s WHERE season = %d" % (TABLE[k], y))  # noqa: E731

    result = {"batter": {}, "pitcher": {}, "notes": {}}
    if a.rates_file and Path(a.rates_file).exists():
        saved = json.loads(Path(a.rates_file).read_text(encoding="utf-8"))
        for k in result:
            result[k] = {int(y): ({c: tuple(v) for c, v in cols.items()} if k != "notes" else cols)
                         for y, cols in saved.get(k, {}).items()}
    for y in range(a.first, a.last + 1):
        reg = reg_of(y)
        files = [f for f in nbx.season_files(a.box_dir, y) if f.name.split(".")[0] in reg]
        if len(files) < len(reg):
            print("%d 박스가 %d/%d 경기뿐이라 건너뜁니다." % (y, len(files), len(reg)))
            continue
        if a.pbp_dir:
            with gzip.open(Path(a.pbp_dir) / ("%d.pkl.gz" % y)) as f:
                pbp = [r for r in pickle.load(f) if r["gameID"] in reg]
        else:
            from d1_load import query
            pbp = no.load_pbp(query, y, reg)
        bats, pits, note = no.build_season(y, names, pbp, files, a.naver_cache, gated=False)
        result["batter"][y] = rates(old_of("batter", y), bats, no.BATTER_COLUMNS)
        result["pitcher"][y] = rates(old_of("pitcher", y), pits, no.PITCHER_COLUMNS)
        result["notes"][y] = note
        print(y, note, flush=True)
        if a.rates_file:
            Path(a.rates_file).write_text(json.dumps(result, ensure_ascii=False, default=list), encoding="utf-8")

    verified = {
        "generated": datetime.date.today().isoformat(),
        "threshold": THRESHOLD,
        "batter": passed(result["batter"]),
        "pitcher": passed(result["pitcher"]),
    }
    Path(a.out_json).write_text(json.dumps(verified, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(a.out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out_md).write_text(markdown(result), encoding="utf-8")
    print("썼습니다: %s, %s" % (a.out_json, a.out_md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
