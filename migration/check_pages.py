# -*- coding: utf-8 -*-
"""배포된 Pages 와 Worker 가 짝을 이뤄 동작하는지 확인합니다.

브라우저로 열어 보기 전에 명백한 실패를 걸러 냅니다. 페이지가 404 인지,
참조하는 자원이 빠졌는지, API 가 CORS 를 막는지 같은 것들입니다.
화면이 예쁘게 그려지는지는 사람이 봐야 합니다.

로컬 검사도 함께 합니다. config.js 로드 순서는 배포 전에 잡을 수 있는
실수인데, 틀리면 요청이 `undefined/teams` 로 나갑니다.
"""
import argparse
import io
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Cloudflare 엣지가 Python-urllib User-Agent 를 봇으로 보고 1010 으로
# 막습니다. 브라우저 형태로 보냅니다.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

DEFAULT_PAGES = "https://kbo-dashboard-a0g.pages.dev"
DEFAULT_API = "https://kbo-api.bstats-baseball.workers.dev"

PAGES = [
    "/",
    "/pages/player-stats.html",
    "/pages/team-stats.html",
    "/pages/player-analytics.html",
    "/pages/factor-stats.html",
    "/pages/database-explorer.html",
    "/pages/article.html",
]

# 화면이 실제로 부르는 것 중 대표를 고릅니다. 전부 부를 필요는 없습니다.
# 골든 비교가 이미 29개 엔드포인트를 대조했습니다. 여기서 보는 것은
# **브라우저에서 부를 수 있는지**, 즉 CORS 입니다.
API_PATHS = ["/teams", "/dashboard/stats", "/standings", "/stats/seasons"]


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)
    except Exception as exc:
        return 0, ("%s: %s" % (type(exc).__name__, exc)).encode(), {}


def check_load_order(root="dashboard_js"):
    """config.js 가 그것을 쓰는 모든 것보다 먼저 로드되는지 봅니다.

    순서가 뒤바뀌면 window.KBO_API_BASE 가 undefined 인 채로 읽혀 요청이
    `undefined/teams` 로 나갑니다. 배포 전에 잡을 수 있는 실수입니다.
    """
    bad = []
    files = sorted(Path(root).rglob("*.html"))
    if not files:
        return [("(로컬)", "%s 에서 HTML 을 찾지 못했습니다" % root)]

    for p in files:
        s = io.open(p, encoding="utf-8", newline="").read()
        m = re.search(r"<script[^>]+config\.js", s)
        if not m:
            bad.append((p.as_posix(), "config.js 를 부르지 않습니다"))
            continue
        cfg = m.start()
        for pat, what in ((r"<script[^>]+api\.js", "api.js"),
                          (r"window\.KBO_API_BASE", "KBO_API_BASE 사용")):
            for u in re.finditer(pat, s):
                if u.start() < cfg:
                    line = s[:u.start()].count("\n") + 1
                    bad.append((p.as_posix(),
                                "%s 가 %d행에서 config.js 보다 먼저" % (what, line)))
    return bad


def check_address(root="dashboard_js"):
    """API 주소가 config.js 한 곳에만 있는지 봅니다.

    흩어지면 다음에 바뀔 때 하나를 빠뜨리고, 그 페이지만 조용히 죽습니다.
    """
    bad = []
    for p in sorted(Path(root).rglob("*")):
        if p.suffix not in (".js", ".html") or p.name == "config.js":
            continue
        s = io.open(p, encoding="utf-8", newline="").read()
        for pat in (r"localhost:8000", r"['\"]/api['\"]"):
            m = re.search(pat, s)
            if m:
                line = s[:m.start()].count("\n") + 1
                bad.append((p.as_posix(),
                            "%d행에 주소가 박혀 있습니다" % line))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", default=DEFAULT_PAGES)
    ap.add_argument("--api", default=DEFAULT_API)
    ap.add_argument("--root", default="dashboard_js")
    args = ap.parse_args()

    bad = []

    print("=== 로컬: config.js 로드 순서 ===")
    order = check_load_order(args.root)
    for what, why in order:
        print("  %s: %s" % (what, why))
        bad.append(("로드순서", what, why))
    if not order:
        print("  모든 페이지에서 config.js 가 먼저입니다")

    print()
    print("=== 로컬: API 주소가 한 곳인지 ===")
    addr = check_address(args.root)
    for what, why in addr:
        print("  %s: %s" % (what, why))
        bad.append(("주소중복", what, why))
    if not addr:
        print("  config.js 한 곳뿐입니다")

    print()
    print("=== 배포된 페이지 ===")
    assets = set()
    for path in PAGES:
        status, body, _ = fetch(args.pages.rstrip("/") + path)
        text = body.decode("utf-8", "replace")
        # 500바이트는 오류 페이지를 걸러 내기 위한 하한입니다. 실제 페이지는
        # 가장 작은 것도 20KB 를 넘습니다.
        if not (status == 200 and len(text) > 500):
            bad.append(("페이지", path, status))
        print("  %-34s %s  %d바이트" % (path, status, len(body)))

        base = path.rsplit("/", 1)[0] or ""
        for m in re.finditer(r'(?:src|href)="([^"]+)"', text):
            u = m.group(1)
            if u.startswith(("http://", "https://", "//", "data:", "#")):
                continue
            assets.add(urllib.parse.urljoin(
                args.pages.rstrip("/") + base + "/", u))

    print()
    print("=== 참조 자원 %d개 ===" % len(assets))
    for u in sorted(assets):
        status, _, _ = fetch(u)
        if status != 200:
            bad.append(("자원", u, status))
            print("  %s  %s" % (status, u))
    print("  (200 인 것은 생략했습니다)")

    print()
    print("=== API CORS ===")
    for path in API_PATHS:
        status, _, headers = fetch(args.api + path)
        acao = headers.get("Access-Control-Allow-Origin", "")
        if not (status == 200 and acao == "*"):
            bad.append(("API", path, "%s / ACAO=%r" % (status, acao)))
        print("  %-20s %s  ACAO=%s" % (path, status, acao or "(없음)"))

    print()
    if bad:
        print("문제 %d건" % len(bad))
        for kind, what, why in bad:
            print("  [%s] %s -> %s" % (kind, what, why))
        return 1
    print("모두 정상입니다. 이제 브라우저로 열어 확인하십시오.")
    print("  화면  %s" % args.pages)
    print("  API   %s" % args.api)
    return 0


if __name__ == "__main__":
    sys.exit(main())
