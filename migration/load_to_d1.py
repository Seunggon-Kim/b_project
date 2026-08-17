# -*- coding: utf-8 -*-
"""청크 SQL 파일을 D1 에 순서대로 적재합니다.

하루 한도를 파일 개수가 아니라 **쓰기 행 수**로 셉니다
---------------------------------------------------
D1 무료 플랜은 하루 100,000 행까지 씁니다. 그런데 한 행을 넣을 때 실제로 계상되는
쓰기는 `1 + 그 테이블의 인덱스 수` 입니다. `play_by_play` 는 인덱스가 3개라 행당 4,
`teams` 는 인덱스가 없어 행당 1 입니다. 파일 개수로 세면 이 차이를 놓칩니다.

그래서 `manifest.json` 의 파일별 행 수와 로컬 스키마의 인덱스 수를 곱해 예산을
계산하고, 예산을 넘기 직전에 멈춥니다. 한도에 부딪혀 실패한 뒤 되짚는 것보다
미리 멈추는 편이 안전합니다.

성공한 파일은 `.progress` 에 기록되어 두 번 넣지 않습니다.
"""
import argparse
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

# 하루 한도 100,000 에서 5,000 을 여유로 남깁니다.
DEFAULT_BUDGET = 95_000


def pending_files(all_files, progress_path):
    """아직 적재하지 않은 파일 목록을 반환합니다."""
    progress_path = Path(progress_path)
    done = set()
    if progress_path.exists():
        for line in progress_path.read_text(encoding="utf-8").splitlines():
            name = line.strip()
            if name:
                done.add(name)
    return [f for f in all_files if Path(f).name not in done]


def index_counts(conn):
    """테이블별 인덱스 개수를 셉니다. 이름 없는 자동 인덱스는 제외합니다."""
    counts = {
        name: 0
        for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")
    }
    for (tbl,) in conn.execute(
            "SELECT tbl_name FROM sqlite_master "
            "WHERE type='index' AND sql IS NOT NULL"):
        if tbl in counts:
            counts[tbl] += 1
    return counts


def write_cost(rows, n_indexes):
    """D1 이 계상할 쓰기 행 수. 테이블 1 + 인덱스마다 1."""
    return rows * (1 + n_indexes)


def plan_batch(files, manifest, idx_counts, budget=DEFAULT_BUDGET):
    """예산 안에 들어가는 파일만 골라 (파일 목록, 예상 쓰기 수) 를 돌려줍니다.

    `budget` 이 0 이면 전부 고릅니다. 예산보다 큰 파일 하나뿐이면 그것만이라도
    시도합니다. 그렇게 하지 않으면 큰 파일에서 영원히 진행이 멈춥니다.
    """
    by_name = {f["name"]: f for f in manifest.get("files", [])}
    chosen = []
    total = 0
    for f in files:
        f = Path(f)
        if f.name not in by_name:
            raise KeyError(
                "%s 가 manifest 에 없습니다. export_to_d1.py 를 다시 실행하십시오."
                % f.name)
        info = by_name[f.name]
        cost = write_cost(info["rows"], idx_counts.get(info["table"], 0))
        if budget and chosen and total + cost > budget:
            break
        chosen.append(f)
        total += cost
        if budget and total >= budget:
            break
    return chosen, total


def refresh_meta_counts(db_name, names):
    """표별 행 수 메타를 다시 계산해 넣습니다.

    Worker 가 `COUNT(*)` 대신 이 값을 읽습니다. D1 은 스캔한 행 수로
    과금하는데 `COUNT(*)` 는 인덱스로 줄지 않아, 표 목록 화면 한 번에
    24만 행을 읽던 것을 18행으로 바꾼 장치입니다(src/lib/counts.js).

    **적재 뒤 반드시 불러야 합니다.** 안 부르면 화면이 낡은 행 수를
    보여 줍니다. 틀린 숫자는 없는 숫자보다 나쁩니다.

    행 수는 D1 에서 직접 셉니다. 로컬 값을 옮기면 적재가 덜 된 상태에서
    어긋납니다. `names` 는 셀 표 이름 목록입니다.
    """
    lines = [
        "CREATE TABLE IF NOT EXISTS meta_table_counts (",
        "  name TEXT PRIMARY KEY, n INTEGER NOT NULL, updated_at TEXT NOT NULL);",
    ]
    for n in names:
        lines.append(
            "INSERT OR REPLACE INTO meta_table_counts "
            "SELECT '%s', COUNT(*), datetime('now') FROM \"%s\";" % (n, n))

    out = Path("migration/meta_counts.sql")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    cmd = 'npx wrangler d1 execute %s --remote --file="%s" --yes' % (
        db_name, out.as_posix())
    r = subprocess.run(cmd, capture_output=True, text=True, shell=True,
                       encoding="utf-8", errors="replace")
    if r.returncode == 0:
        print("행 수 메타를 갱신했습니다 (표 %d개)." % len(names))
        return True
    print("행 수 메타 갱신에 실패했습니다. 화면이 낡은 숫자를 보입니다.")
    print("  다시 넣으려면: %s" % cmd)
    return False

def load_chunks(files, db_name, progress_path):
    """청크를 하나씩 D1 에 적재하고 (성공 수, 실패 수) 를 반환합니다."""
    progress_path = Path(progress_path)
    ok = 0
    fail = 0
    for i, f in enumerate(files, start=1):
        f = Path(f)
        cmd = 'npx wrangler d1 execute %s --remote --file="%s" --yes' % (
            db_name, f.as_posix())
        # 일시적인 네트워크 오류로 한 파일이 실패했다고 전체를 멈출 이유는
        # 없습니다. 한 번 더 시도하고, 그래도 안 되면 그때 멈춥니다.
        # 실제로 적재 도중 한 번 그런 일이 있었는데, 다시 넣으니 바로
        # 들어갔습니다.
        result = None
        for attempt in range(2):
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    shell=True, encoding="utf-8",
                                    errors="replace")
            if result.returncode == 0:
                break
            if attempt == 0:
                print("[%d/%d] 재시도 %s" % (i, len(files), f.name))
                time.sleep(3)

        if result.returncode == 0:
            ok += 1
            with progress_path.open("a", encoding="utf-8") as fh:
                fh.write(f.name + "\n")
            print("[%d/%d] OK   %s" % (i, len(files), f.name))
        else:
            fail += 1
            print("[%d/%d] 실패 %s" % (i, len(files), f.name))
            print((result.stderr or result.stdout or "").strip()[:800])
            # 두 번 다 실패했습니다. 한도 초과일 수 있으니 멈춥니다.
            break
    return ok, fail


def main():
    ap = argparse.ArgumentParser(description="청크 SQL 을 D1 에 적재합니다")
    ap.add_argument("--dir", default="migration/out")
    ap.add_argument("--db", default="kbo-stats")
    ap.add_argument("--local-db", default="database/kbo_stats.db",
                    help="인덱스 수를 세기 위한 로컬 DB")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="이번 실행의 쓰기 행 예산. 0 이면 제한 없음")
    ap.add_argument("--pattern", default="*.sql",
                    help="적재 대상 파일 패턴 (예: 20_play_by_play_*.sql)")
    ap.add_argument("--dry-run", action="store_true",
                    help="무엇을 넣을지만 보여 주고 넣지 않습니다")
    args = ap.parse_args()

    out_dir = Path(args.dir)
    progress = out_dir / ".progress"
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.exists():
        print("manifest 가 없습니다: %s" % manifest_path)
        print("먼저 py migration/export_to_d1.py 를 실행하십시오.")
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    conn = sqlite3.connect(args.local_db)
    idx = index_counts(conn)
    # 적재가 끝난 뒤 메타를 갱신할 때 쓸 표 목록입니다. 그 시점에는 이
    # 연결이 닫혀 있으므로 지금 뽑아 둡니다.
    table_names = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    conn.close()

    # manifest 에 있는 것만 적재 대상입니다. 이 폴더에 다른 용도의 SQL 이
    # 섞여도(뉴스 적재본 등) 멈추지 않고 건너뜁니다.
    known = {f["name"] for f in manifest.get("files", [])}
    all_files = []
    stray = []
    for f in sorted(out_dir.glob(args.pattern)):
        if f.name == "00_schema.sql":
            continue
        if f.name in known:
            all_files.append(f)
        else:
            stray.append(f.name)
    if stray:
        print("목록에 없어 건너뛴 파일 %d개: %s" % (
            len(stray), ", ".join(stray[:3])))
    todo = pending_files(all_files, progress)
    print("전체 %d개, 남은 것 %d개" % (len(all_files), len(todo)))
    if not todo:
        print("모두 적재했습니다.")
        return 0

    batch, cost = plan_batch(todo, manifest, idx, budget=args.budget)
    remaining = sum(
        write_cost(f["rows"], idx.get(f["table"], 0))
        for f in manifest["files"]
        if f["name"] in {p.name for p in todo})
    print("이번에 넣을 것 %d개, 예상 쓰기 %s행 (남은 총량 %s행)" % (
        len(batch), format(cost, ","), format(remaining, ",")))
    if args.budget:
        days = -(-remaining // args.budget)
        print("이 속도면 %d일 남았습니다." % days)

    if args.dry_run:
        for f in batch[:5]:
            print("  %s" % f.name)
        if len(batch) > 5:
            print("  ... 외 %d개" % (len(batch) - 5))
        return 0

    ok, fail = load_chunks(batch, args.db, progress)
    print()
    print("성공 %d, 실패 %d" % (ok, fail))

    # 적재로 행 수가 달라졌으니 메타를 다시 씁니다. 실패해도 적재 자체는
    # 성공이므로 종료 코드를 바꾸지 않고 경고만 냅니다.
    if ok:
        refresh_meta_counts(args.db, table_names)
    if fail:
        print("실패 지점부터 같은 명령으로 재개할 수 있습니다.")
        print("한도 초과라면 UTC 자정(한국 시간 오전 9시) 이후에 다시 실행하십시오.")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
