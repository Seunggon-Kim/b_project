# -*- coding: utf-8 -*-
"""수집 CSV 를 D1 표에 UPSERT 로 넣습니다.

`kbo_to_db.py`, `pitcher_to_db.py` 를 대신합니다. 그 스크립트들은 로컬
SQLite(`database/kbo_stats.db`)에 넣는데, GitHub Actions 러너에는 그
파일이 없습니다. 226MB 라 git 에 두지 않기 때문입니다.

컬럼 이름이 CSV 와 D1 이 같으므로 표마다 코드를 따로 쓸 필요가 없습니다.
D1 스키마를 읽어 겹치는 컬럼만 넣습니다.

    py data_collection/csv_to_d1.py \
        --table kbo_official_batter_stats \
        --csv crawler/save/official_stats/batter_stats_2026.csv \
        --key player_id,season --dry-run

시즌은 파일명 끝의 네 자리에서 뽑습니다(`batter_stats_2026.csv`).
`--const season=2026` 으로 직접 줄 수도 있습니다.
"""
import argparse
import csv
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from d1_load import (  # noqa: E402
    build_upserts, d1_columns, refresh_count, run_d1_file,
)

ROOT = Path(__file__).resolve().parent.parent

# 기존 행의 created_at 이 KST 로 들어가 있습니다. 러너는 UTC 라
# 그대로 쓰면 아홉 시간 어긋난 값이 섞입니다.
KST = timezone(timedelta(hours=9))


def read_csv_rows(path):
    # 공식 통계 CSV 는 utf-8-sig 입니다. PBP 크롤러는 cp949 로 씁니다.
    for enc in ("utf-8-sig", "cp949"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise RuntimeError("인코딩을 알 수 없습니다: %s" % path)


def season_from_name(path):
    m = re.search(r"_(\d{4})\.csv$", str(path))
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--key", required=True,
                    help="충돌 판정에 쓸 컬럼, 쉼표로 구분")
    ap.add_argument("--const", action="append", default=[],
                    help="모든 행에 같은 값을 넣습니다 (예: season=2026)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.is_absolute():
        csv_path = ROOT / csv_path
    if not csv_path.exists():
        # 수집이 실패해 파일이 없을 수 있습니다. 그때 D1 을 건드리지
        # 않고 실패로 끝내야 다음 단계가 건너뜁니다.
        print("CSV 가 없습니다: %s" % csv_path)
        return 1

    rows = read_csv_rows(csv_path)
    if not rows:
        print("CSV 가 비어 있습니다: %s" % csv_path)
        return 1
    print("CSV %s행" % format(len(rows), ","))

    consts = {}
    for item in args.const:
        k, _, v = item.partition("=")
        consts[k.strip()] = v.strip()
    # season 을 안 줬으면 파일명에서 뽑습니다.
    keys = [k.strip() for k in args.key.split(",") if k.strip()]
    if "season" in keys and "season" not in consts \
            and "season" not in rows[0]:
        s = season_from_name(csv_path)
        if not s:
            print("파일명에서 시즌을 뽑지 못했습니다. --const season=YYYY 를 주십시오.")
            return 1
        consts["season"] = s
        print("시즌: %s (파일명에서)" % s)

    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

    table_cols = d1_columns(args.table)
    if not table_cols:
        print("D1 에 %s 표가 없습니다." % args.table)
        return 1

    available = set(rows[0].keys()) | set(consts.keys())
    columns = [c for c in table_cols if c in available]
    keep = []
    if "created_at" in table_cols and "created_at" not in columns:
        columns.append("created_at")
        consts["created_at"] = now
        keep.append("created_at")
    # updated_at 은 갱신할 때 SQL 이 datetime('now') 로 채웁니다.
    if "updated_at" in table_cols and "updated_at" not in columns:
        columns.append("updated_at")
        consts["updated_at"] = now
    columns = [c for c in table_cols if c in set(columns)]

    missing_keys = [k for k in keys if k not in columns]
    if missing_keys:
        print("키 컬럼이 CSV·상수에 없습니다: %s" % ", ".join(missing_keys))
        return 1

    skipped_cols = sorted(set(rows[0].keys()) - set(table_cols))
    if skipped_cols:
        # D1 에 없는 컬럼을 넣으려 하면 적재가 통째로 실패합니다.
        # 빼고 진행하되 조용히 넘기지는 않습니다.
        print("D1 에 없어 뺀 CSV 컬럼 %d개: %s"
              % (len(skipped_cols), ", ".join(skipped_cols[:8])))

    # 키가 빈 행은 넣지 않습니다. player_id 가 비면 UPSERT 가 엉뚱한
    # 행을 덮습니다.
    good, dropped = [], 0
    for r in rows:
        merged = dict(r)
        merged.update(consts)
        if any(not str(merged.get(k, "")).strip()
               or str(merged.get(k)).lower() == "nan" for k in keys):
            dropped += 1
            continue
        good.append(merged)
    if dropped:
        print("키가 비어 건너뛴 행 %d개" % dropped)
    if not good:
        print("넣을 행이 없습니다.")
        return 1

    stmts = build_upserts(args.table, columns, keys, good,
                          touch="updated_at" if "updated_at" in columns else None,
                          keep=keep)
    biggest = max(len(s.encode("utf-8")) for s in stmts)
    print("컬럼 %d개, UPSERT %d문, 최대 %s 바이트"
          % (len(columns), len(stmts), format(biggest, ",")))

    out = Path(args.out) if args.out else (
        ROOT / "migration" / ("upsert_%s.sql" % args.table))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(stmts) + "\n", encoding="utf-8", newline="\n")
    print("SQL -> %s" % out)

    if args.dry_run:
        print("[dry-run] 적재하지 않았습니다.")
        return 0

    run_d1_file(out)
    refresh_count(args.table)
    print("D1 적재 완료 (%s행)" % format(len(good), ","))
    return 0


if __name__ == "__main__":
    sys.exit(main())
