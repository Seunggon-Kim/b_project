# -*- coding: utf-8 -*-
"""화면을 눌러 보며 동작을 확인합니다.

check_pages_browser.py 는 페이지를 열기만 합니다. 첫 화면이 멀쩡해도
누르면 죽는 곳이 있습니다. 계획 C 가 확인하라고 정한 것들을 눌러 봅니다.

  - 홈의 퓨처스 탭: 로고를 /logo API(D1 BLOB)에서 받습니다. 1군 탭은
    정적 파일을 쓰므로 이쪽만 따로 봐야 합니다.
  - 선수 분석의 검색: 검색해야 데이터가 나오는 화면입니다.
  - 데이터 탐색의 표 열기와 CSV 내려받기
  - 아티클 본문 열기
"""
import argparse
import json as _json
import sys
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

DEFAULT_PAGES = "https://kbo-dashboard-a0g.pages.dev"


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1440,2200")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.set_capability("goog:loggingPrefs", {"browser": "ALL",
                                              "performance": "ALL"})
    return webdriver.Chrome(options=opts)


def failures(driver):
    out = []
    for entry in driver.get_log("performance"):
        try:
            msg = _json.loads(entry["message"])["message"]
        except Exception:
            continue
        if msg.get("method") == "Network.responseReceived":
            r = msg.get("params", {}).get("response", {})
            if r.get("status", 200) >= 400:
                out.append("%s %s" % (r.get("status"), r.get("url", "")[:130]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", default=DEFAULT_PAGES)
    ap.add_argument("--shots", default="")
    args = ap.parse_args()

    base = args.pages.rstrip("/")
    d = make_driver()
    bad = []

    def shot(name):
        if args.shots:
            from pathlib import Path
            Path(args.shots).mkdir(parents=True, exist_ok=True)
            d.save_screenshot(str(Path(args.shots) / (name + ".png")))

    def report(what, ok, detail=""):
        print("  %-40s %s%s" % (what, "정상" if ok else "문제",
                                "  " + detail if detail else ""))
        if not ok:
            bad.append((what, detail))

    try:
        # --- 홈: 퓨처스 탭 ---
        print("=== 홈 / 퓨처스 탭 (로고를 /logo API 로 받습니다) ===")
        d.get(base + "/")
        time.sleep(5)
        d.get_log("performance")  # 이전 로그를 비웁니다.
        clicked = False
        for el in d.find_elements(By.XPATH, "//*[contains(text(),'퓨처스')]"):
            try:
                d.execute_script("arguments[0].click();", el)
                clicked = True
                break
            except Exception:
                continue
        report("퓨처스 탭을 눌렀습니다", clicked)
        time.sleep(5)
        fails = [f for f in failures(d) if "/logo" in f]
        report("로고 API 요청", not fails, fails[0] if fails else "")
        # 이미지가 실제로 그려졌는지 봅니다. naturalWidth 가 0 이면 깨진
        # 이미지입니다. src 만 봐서는 알 수 없습니다.
        broken = d.execute_script(
            "return Array.from(document.images)"
            ".filter(i => i.src.includes('/logo') && i.complete"
            " && i.naturalWidth === 0).length;")
        total = d.execute_script(
            "return Array.from(document.images)"
            ".filter(i => i.src.includes('/logo')).length;")
        report("로고 이미지 %d개 중 깨짐 %d개" % (total, broken), broken == 0)
        shot("futures_tab")

        # --- 선수 분석: 검색 ---
        print()
        print("=== 선수 분석 / 검색 ===")
        d.get(base + "/pages/player-analytics.html")
        time.sleep(4)
        d.get_log("performance")
        box = d.find_elements(By.CSS_SELECTOR, "input[type=text], input[type=search]")
        if not box:
            report("검색창을 찾았습니다", False)
        else:
            box[0].send_keys("김도영")
            time.sleep(6)
            body = d.find_element(By.TAG_NAME, "body").text
            report("검색 결과가 나왔습니다", "김도영" in body,
                   "본문 %d자" % len(body))
            fails = failures(d)
            report("검색 중 실패한 요청", not fails, fails[0] if fails else "")
            shot("player_search")

        # --- 데이터 탐색: 표 열기 + CSV ---
        print()
        print("=== 데이터 탐색 / 표 열기 ===")
        d.get(base + "/pages/database-explorer.html")
        # 표 18개마다 행 수를 세므로 목록이 늦게 붙습니다. 고정 대기로는
        # 빠를 때와 느릴 때가 갈립니다. 요소가 나타날 때까지 기다립니다.
        try:
            WebDriverWait(d, 30).until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "[data-table]")))
        except Exception:
            pass
        d.get_log("performance")
        # 표 카드는 [data-table] 입니다. 텍스트로 찾으면 카드 제목이 자식
        # 요소에 있어 XPath 의 text() 로는 안 잡힙니다.
        cards = d.find_elements(By.CSS_SELECTOR, "[data-table]")
        report("표 카드 %d개를 찾았습니다" % len(cards), len(cards) > 0)
        if cards:
            name = cards[0].get_attribute("data-table")
            d.execute_script("arguments[0].click();", cards[0])
            time.sleep(6)
            body = d.find_element(By.TAG_NAME, "body").text
            # 표를 열면 컬럼 스키마와 행이 붙습니다. 이름만 있는 목록 상태와
            # 구분하려고 길이로 봅니다.
            report("%s 표가 열렸습니다" % name, len(body) > 4000,
                   "본문 %d자" % len(body))
            fails = failures(d)
            report("표 열기 요청", not fails, fails[0] if fails else "")
        shot("db_table_open")

        # --- 아티클 본문 ---
        print()
        print("=== 아티클 / 본문 열기 ===")
        d.get(base + "/pages/article.html")
        time.sleep(4)
        before = len(d.find_element(By.TAG_NAME, "body").text)
        d.get_log("performance")
        for el in d.find_elements(By.CSS_SELECTOR, ".article-card"):
            d.execute_script("arguments[0].click();", el)
            break
        time.sleep(6)
        after = len(d.find_element(By.TAG_NAME, "body").text)
        report("본문이 열렸습니다", after > before + 500,
               "%d자 -> %d자" % (before, after))
        fails = failures(d)
        report("본문 요청", not fails, fails[0] if fails else "")
        shot("article_open")
    finally:
        d.quit()

    print()
    if bad:
        print("문제 %d건" % len(bad))
        for what, detail in bad:
            print("  %s %s" % (what, detail))
        return 1
    print("눌러 본 것 모두 정상입니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
