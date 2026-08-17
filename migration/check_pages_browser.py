# -*- coding: utf-8 -*-
"""배포된 화면을 실제 브라우저로 열어 데이터가 그려지는지 봅니다.

check_pages.py 는 파일이 200 인지까지만 봅니다. 그것으로는 화면이 비어
있어도 통과합니다. 여기서는 헤드리스 Chrome 으로 실제로 열어 자바스크립트를
돌리고, 콘솔 오류와 실패한 네트워크 요청을 걷어 옵니다.

사람의 눈을 대체하지 않습니다. 배치가 틀어졌는지, 숫자가 말이 되는지는
사람이 봐야 합니다. 여기서 잡는 것은 **명백한 실패**입니다.

  - undefined/teams 로 나가는 요청 (config.js 로드 순서 문제)
  - CORS 로 막힌 요청
  - 404 로 실패한 자원
  - 데이터를 못 받아 표가 비어 있는 화면
"""
import argparse
import sys
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

DEFAULT_PAGES = "https://kbo-dashboard-a0g.pages.dev"

# (경로, 데이터가 들어왔다면 화면에 있어야 할 것)
#
# 선택자가 아니라 텍스트 조각으로 확인합니다. 선택자는 화면을 조금만
# 고쳐도 깨지는데, 이 스크립트는 이전이 잘 됐는지 보는 것이 목적이라
# 화면 구조에 덜 얽히는 편이 낫습니다.
PAGES = [
    ("/", ["KBO", "순위"]),
    ("/pages/player-stats.html", ["타자", "투수"]),
    ("/pages/team-stats.html", ["팀"]),
    ("/pages/player-analytics.html", ["선수"]),
    ("/pages/factor-stats.html", ["파크", "팩터"]),
    ("/pages/database-explorer.html", ["테이블", "play_by_play"]),
    ("/pages/article.html", ["아티클"]),
]

# 화면이 그려질 시간을 줍니다. API 가 여러 번 오가므로 즉시 보면 빈 채로
# 잡힙니다.
SETTLE_SEC = 6


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1440,2000")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    # 콘솔과 네트워크 로그를 받으려면 켜야 합니다.
    opts.set_capability("goog:loggingPrefs", {"browser": "ALL",
                                              "performance": "ALL"})
    return webdriver.Chrome(options=opts)


def collect(driver):
    """콘솔 오류와 실패한 요청을 걷어 옵니다."""
    errors = []
    for entry in driver.get_log("browser"):
        if entry.get("level") in ("SEVERE", "ERROR"):
            errors.append(entry.get("message", "")[:300])

    failed = []
    import json as _json
    for entry in driver.get_log("performance"):
        try:
            msg = _json.loads(entry["message"])["message"]
        except Exception:
            continue
        method = msg.get("method", "")
        p = msg.get("params", {})
        if method == "Network.responseReceived":
            r = p.get("response", {})
            if r.get("status", 200) >= 400:
                failed.append("%s %s" % (r.get("status"), r.get("url", "")[:150]))
        elif method == "Network.loadingFailed":
            failed.append("실패 %s" % p.get("errorText", "")[:80])
    return errors, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", default=DEFAULT_PAGES)
    ap.add_argument("--settle", type=int, default=SETTLE_SEC)
    ap.add_argument("--shots", default="")
    args = ap.parse_args()

    driver = make_driver()
    bad = []
    try:
        for path, needles in PAGES:
            url = args.pages.rstrip("/") + path
            driver.get(url)
            time.sleep(args.settle)

            body = driver.find_element("tag name", "body").text
            errors, failed = collect(driver)

            # undefined 로 나가는 요청은 config.js 순서 문제입니다.
            undef = [f for f in failed if "undefined" in f]
            missing = [n for n in needles if n not in body]

            ok = not errors and not failed and not missing
            print("%-34s %s  본문 %d자" % (
                path, "정상" if ok else "문제", len(body)))
            if missing:
                print("    없는 문구: %s" % ", ".join(missing))
                bad.append((path, "화면에 %s 가 없습니다" % ", ".join(missing)))
            if undef:
                print("    undefined 요청: %s" % undef[0])
                bad.append((path, "config.js 로드 순서 문제로 보입니다"))
            for f in failed[:4]:
                print("    요청 %s" % f)
                bad.append((path, "요청 %s" % f))
            for e in errors[:4]:
                print("    콘솔 %s" % e)
                bad.append((path, "콘솔 %s" % e[:120]))

            if args.shots:
                from pathlib import Path
                Path(args.shots).mkdir(parents=True, exist_ok=True)
                name = (path.strip("/").replace("/", "_") or "root") + ".png"
                driver.save_screenshot(str(Path(args.shots) / name))
    finally:
        driver.quit()

    print()
    if bad:
        print("문제 %d건" % len(bad))
        return 1
    print("일곱 페이지 모두 데이터와 함께 그려집니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
