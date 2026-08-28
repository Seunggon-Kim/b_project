# -*- coding: utf-8 -*-
"""GitHub Actions 러너에서 KBO 사이트에 닿는지 판정합니다.

설계 문서 7장 위험 1 을 가르는 프로브입니다. 결과에 따라 대응이 갈립니다.

  HTTP 200 + 본문 수만 자   -> 접근 가능. 설계대로 Actions 에서 수집합니다.
  HTTP 403 / 타임아웃        -> IP 대역 차단. Cloudflare Worker 경유를 시도합니다.
  HTTP 는 되는데 Selenium 만 실패 -> 브라우저 지문 탐지. HTTP 직접 호출로 전환합니다.

`--mode selenium` 은 스크래퍼 전체 대신 페이지를 열어 표가 그려지는지만 봅니다.
전체 수집은 10팀을 도느라 오래 걸려서, 판정을 먼저 짧게 끝내려는 것입니다.
"""
import argparse
import sys

URL = "https://www.koreabaseball.com/Record/Player/HitterBasic/Basic1.aspx"

# 차단 페이지가 200 으로 오는 경우를 가려냅니다.
BLOCK_HINTS = ("access denied", "blocked", "차단", "비정상적인 접근",
               "요청이 많아", "cloudflare", "captcha")


def probe_http():
    import requests

    print("대상: %s" % URL)
    try:
        r = requests.get(URL, timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
        })
    except Exception as exc:
        print("판정: 도달 실패 (%s: %s)" % (type(exc).__name__, exc))
        return 1

    body = r.text
    print("status: %s" % r.status_code)
    print("length: %s" % len(body))
    print("snippet: %s" % body[:300].replace("\n", " "))

    lowered = body[:5000].lower()
    hit = [h for h in BLOCK_HINTS if h in lowered]
    if hit:
        print("판정: 차단 안내로 보이는 문구 발견 %s" % hit)
        return 1
    if r.status_code != 200:
        print("판정: HTTP %s" % r.status_code)
        return 1
    # 기록 페이지는 ASP.NET WebForms 라 __VIEWSTATE 가 반드시 들어 있습니다.
    if "__VIEWSTATE" not in body:
        print("판정: 200 이지만 기록 페이지가 아닙니다 (__VIEWSTATE 없음)")
        return 1
    if len(body) < 20000:
        print("판정: 200 이지만 본문이 너무 짧습니다")
        return 1
    print("판정: 접근 가능")
    return 0


def probe_selenium():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    # 러너에는 Chrome 이 깔려 있고 Selenium Manager 가 드라이버를 맞춰 줍니다.
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(URL)
        driver.implicitly_wait(10)
        print("title: %s" % driver.title)
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        print("표 행 수: %d" % len(rows))
        if not rows:
            print("판정: 페이지는 열렸으나 표가 비었습니다")
            print("본문 앞부분: %s" % driver.page_source[:300].replace("\n", " "))
            return 1
        print("판정: Selenium 수집 가능")
        return 0
    except Exception as exc:
        print("판정: Selenium 실패 (%s: %s)" % (type(exc).__name__, exc))
        return 1
    finally:
        driver.quit()


# `google-news` 모드가 있었습니다. 러너에서 구글 뉴스 RSS 가 열리는지
# 재던 것인데, 뉴스 수집 자체를 그만두면서 없앴습니다.


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["http", "selenium"], required=True)
    args = ap.parse_args()
    if args.mode == "http":
        return probe_http()
    return probe_selenium()


if __name__ == "__main__":
    sys.exit(main())
