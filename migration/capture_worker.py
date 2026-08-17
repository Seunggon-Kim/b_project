# -*- coding: utf-8 -*-
"""배포된 Worker 에서 응답을 떠 golden/actual 에 저장합니다.

`golden_capture.py` 와 하는 일이 같지만 두 가지가 다릅니다.

- 아직 이식하지 않은 엔드포인트는 404 가 나므로 건너뜁니다. 이식이 진행되는
  동안 매번 목록을 손으로 고치지 않으려는 것입니다.
- Cloudflare 엣지가 `Python-urllib` User-Agent 를 봇으로 보고 1010 으로
  막습니다. 브라우저 형태의 User-Agent 를 보냅니다.
"""
import argparse
import json
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from migration.golden_matrix import build_matrix  # noqa: E402

DEFAULT_BASE = "https://kbo-api.bstats-baseball.workers.dev"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")


def fetch(base, item, timeout):
    url = base.rstrip("/") + item["path"]
    if item["params"]:
        url += "?" + urllib.parse.urlencode(item["params"])
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument("--db", default="database/kbo_stats.db")
    ap.add_argument("--out", default="migration/golden/actual")
    ap.add_argument("--timeout", type=int, default=90)
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    matrix = build_matrix(conn)
    conn.close()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    saved = 0
    skipped = 0
    failed = []
    for item in matrix:
        try:
            status, raw = fetch(args.base_url, item, args.timeout)
        except Exception as exc:
            failed.append((item["name"], "%s: %s" % (type(exc).__name__, exc)))
            continue

        text = raw.decode("utf-8", "replace")
        try:
            body = json.loads(text)
        except ValueError:
            skipped += 1
            continue

        # 아직 이식하지 않은 경로입니다. 라우터가 내는 404 를 그대로 저장하면
        # 불일치 목록이 미이식 항목으로 가득 차 실제 문제를 가립니다.
        # 문자열로 찾지 않고 파싱한 값으로 판정합니다. JSON.stringify 는
        # 공백을 넣지 않아 문자열 비교가 어긋납니다.
        if (status == 404 and isinstance(body, dict)
                and body.get("detail") == "Not Found"):
            skipped += 1
            continue

        (out / (item["name"] + ".json")).write_text(
            json.dumps({"status": status, "body": body},
                       ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8")
        saved += 1

    print("저장 %d건, 미이식 건너뜀 %d건, 실패 %d건" % (saved, skipped, len(failed)))
    for name, why in failed:
        print("  실패 %s: %s" % (name, why))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
