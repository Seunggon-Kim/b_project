# -*- coding: utf-8 -*-
"""요청 조합을 실행해 응답을 저장합니다.

로컬 FastAPI 로 뜬 것이 정답지가 되고, 나중에 Workers 이식본으로 같은 조합을
다시 떠서 `golden_compare.py` 로 대조합니다.
"""
import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import requests

# `py migration/golden_capture.py` 로 직접 실행할 때 저장소 루트를 경로에 넣습니다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from migration.golden_matrix import build_matrix  # noqa: E402


def _body_of(resp):
    """응답 본문을 비교 가능한 형태로 바꿉니다.

    JSON 이 아니면(예: /logo/{code} 는 PNG) 바이트를 그대로 두지 않고
    해시와 길이로 요약합니다. 인코딩 추정 때문에 비교가 흔들리는 것을 막습니다.
    """
    try:
        return resp.json()
    except ValueError:
        return {
            "__content_type__": resp.headers.get("content-type", ""),
            "__length__": len(resp.content),
            "__sha256__": hashlib.sha256(resp.content).hexdigest(),
        }


def capture(base_url, matrix, out_dir, timeout=60):
    """각 요청을 실행해 {out_dir}/{name}.json 으로 저장합니다."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = 0
    fail = 0
    for i, item in enumerate(matrix, start=1):
        url = base_url.rstrip("/") + item["path"]
        try:
            resp = requests.get(url, params=item["params"], timeout=timeout)
            payload = {"status": resp.status_code, "body": _body_of(resp)}
            (out_dir / (item["name"] + ".json")).write_text(
                json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2),
                encoding="utf-8",
            )
            ok += 1
        except requests.RequestException as exc:
            fail += 1
            print("[%d/%d] 실패 %s: %s" % (i, len(matrix), item["name"], exc))
        if i % 20 == 0:
            print("[%d/%d] 진행 중" % (i, len(matrix)))
    return ok, fail


def main():
    ap = argparse.ArgumentParser(description="응답을 저장합니다")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--db", default="database/kbo_stats.db")
    ap.add_argument("--out", default="migration/golden/expected")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    matrix = build_matrix(conn)
    print("요청 %d개를 %s 로 보냅니다" % (len(matrix), args.base_url))
    ok, fail = capture(args.base_url, matrix, args.out)
    print("저장 %d건, 실패 %d건 -> %s" % (ok, fail, args.out))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
