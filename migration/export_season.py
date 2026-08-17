# -*- coding: utf-8 -*-
"""시즌 하나만 D1 청크로 내보냅니다.

`export_to_d1.py` 는 표 전체를 내보냅니다. 시즌을 새로 넣을 때 그것을
쓰면 이미 D1 에 있는 행까지 다시 올립니다. play_by_play 40만 행을 다시
올리면 쓰기가 약 160만 계상됩니다(행당 1 + 인덱스 3).

이 스크립트는 해당 시즌 행만 뽑습니다. 2026 한 시즌이면 175,749행 ×
4 = 약 70만 쓰기입니다.

만든 청크는 `load_to_d1.py --dir` 로 적재합니다.

    py migration/export_season.py 2026
    py migration/load_to_d1.py --dir migration/out_2026 --budget 0
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from migration.export_to_d1 import export_table  # noqa: E402

# 시즌으로 자를 수 있는 표와 그 조건입니다.
#
# play_by_play 는 gameID 앞 4자가 연도입니다. games 는 season 컬럼이
# 따로 있습니다. 두 표의 시즌 표현이 다르므로 한 조건으로 못 씁니다.
SEASON_WHERE = {
    "games": "season = %s",
    "play_by_play": "substr(gameID,1,4) = '%s'",
}

# 내보낼 순서입니다. games 를 먼저 넣어야 참조가 성립합니다.
ORDER = ["games", "play_by_play"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("season")
    ap.add_argument("--db", default="database/kbo_stats.db")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    season = str(int(args.season))   # 숫자가 아니면 여기서 걸립니다
    out_dir = Path(args.out or ("migration/out_%s" % season))
    conn = sqlite3.connect(args.db)

    manifest = {"source": args.db, "season": season, "files": []}
    total = 0
    for i, table in enumerate(ORDER, start=1):
        where = SEASON_WHERE[table] % season
        n = conn.execute(
            'SELECT COUNT(*) FROM "%s" WHERE %s' % (table, where)).fetchone()[0]
        if not n:
            print("건너뜀 (%s 에 %s 시즌 행이 없습니다): %s" % (table, season, table))
            continue
        pairs = export_table(conn, table, out_dir, order=i, where=where)
        for path, rows in pairs:
            # 키 이름은 export_to_d1.py 와 같아야 합니다. load_to_d1.py 가
            # f["name"], f["table"], f["rows"] 로 읽습니다.
            manifest["files"].append({
                "name": path.name,
                "table": table,
                "rows": rows,
                "bytes": path.stat().st_size,
            })
        print("%-16s %s행 -> 청크 %d개" % (table, format(n, ","), len(pairs)))
        total += n

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    conn.close()

    print()
    print("합계 %s행, %s" % (format(total, ","), out_dir))
    print("적재: py migration/load_to_d1.py --dir %s --budget 0"
          % out_dir.as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
