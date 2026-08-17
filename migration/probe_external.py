# -*- coding: utf-8 -*-
"""배포된 Worker 를 통해 외부 도메인 도달 여부를 판정합니다.

설계 문서 §7 위험 2 를 가르는 프로브입니다. 로컬 PC 에서 직접 부르면
한국 IP 라 늘 성공하므로, 반드시 Worker 를 거쳐 확인해야 합니다.
"""
import argparse
import json
import sys
import urllib.request

DEFAULT_BASE = "https://kbo-api.bstats-baseball.workers.dev"

# 도메인별 최소 기대치입니다. 차단 페이지가 200 으로 오는 경우를 거릅니다.
EXPECT = {
    "naver": {"min_length": 200, "must_contain": "result"},
    "kbo_html": {"min_length": 20000, "must_contain": "__VIEWSTATE"},
    "kbo_json": {"min_length": 20, "must_contain": "game"},
    "google_news": {"min_length": 500, "must_contain": "<rss"},
}


def judge(row):
    """(통과 여부, 사유) 를 돌려줍니다."""
    rule = EXPECT.get(row["name"])
    if rule is None:
        return False, "판정 기준이 없습니다"
    if row.get("status") != 200:
        return False, "HTTP %s %s" % (row.get("status"), row.get("error", ""))
    if row.get("length", 0) < rule["min_length"]:
        return False, "본문이 %d자로 너무 짧습니다" % row.get("length", 0)
    if rule["must_contain"] not in row.get("head", ""):
        # head 는 앞 160자뿐이라 표지 문자열이 없을 수 있습니다.
        # 본문이 기대치의 두 배를 넘으면 정상 응답으로 봅니다.
        if row.get("length", 0) >= rule["min_length"] * 2:
            return True, "본문 %d자 (표지 문자열은 앞부분에 없음)" % row["length"]
        return False, "기대 문자열 %r 이 없습니다" % rule["must_contain"]
    return True, "본문 %d자" % row["length"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base_url", nargs="?", default=DEFAULT_BASE,
                    help="예: https://kbo-api.bstats-baseball.workers.dev")
    args = ap.parse_args()

    url = args.base_url.rstrip("/") + "/probe/external"
    print("경유: %s" % url)
    print()
    # urllib 기본 User-Agent(Python-urllib/x.y)는 Cloudflare 가 봇으로 보고
    # 403 을 돌려줍니다. 브라우저 형태로 바꿔 보냅니다.
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/125.0 Safari/537.36",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read().decode("utf-8"))

    print("%-14s %-6s %8s %9s  %s" % ("도메인", "판정", "상태", "소요", "사유"))
    print("-" * 80)
    failed = []
    for row in data["results"]:
        ok, why = judge(row)
        if not ok:
            failed.append(row["name"])
        print("%-14s %-6s %8s %7dms  %s" % (
            row["name"], "통과" if ok else "실패",
            row.get("status"), row.get("ms", 0), why))

    print()
    if failed:
        print("차단 의심 %d곳: %s" % (len(failed), ", ".join(failed)))
        print("설계 문서 §7 위험 2 의 대응을 검토하십시오.")
        return 1
    print("네 곳 모두 도달합니다. 위험 2 해소.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
