# -*- coding: utf-8 -*-
"""네이버 스포츠 API(api-gw.sports.naver.com)를 JSON 으로 읽습니다.

KBO 이용약관 제14조 차항(2026-10-14 시행)이 KBO 사이트 자동 수집을 막아
공식 기록·팀 순위·선수 정보를 네이버로 옮겼습니다. 이 모듈은 그 수집기들이
같이 쓰는 호출 도우미입니다.

지키는 것 세 가지입니다.

  - 호스트가 api-gw.sports.naver.com 이 아니면 부르지 않습니다. KBO 사이트
    주소가 실수로 들어와도 여기서 막힙니다.
  - 직전 호출에서 MIN_GAP_SEC(1.1초)가 안 지났으면 기다립니다. 초당 1회
    이하로 부릅니다.
  - 연결 오류·5xx 는 RETRIES 번 다시 묻고, 4xx 는 바로 예외입니다(없는
    시즌·선수는 400 이 옵니다. 다시 물어도 같습니다).

통계(statistics) 주소는 브라우저 User-Agent 와 Referer 가 있어야 답합니다.
Worker 쪽 src/lib/naver.js 와 같은 헤더입니다.
"""
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

HOST = "api-gw.sports.naver.com"
BASE = "https://" + HOST
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Referer": "https://m.sports.naver.com/"}
MIN_GAP_SEC = 1.1
RETRIES = 3
RETRY_SLEEP_SEC = 5
TIMEOUT = 30


class NaverError(Exception):
    """네이버가 4xx 로 답했거나 응답 모양이 다릅니다."""

    def __init__(self, msg, status=None):
        super().__init__(msg)
        self.status = status


class Client:
    """호출 간격을 지키는 네이버 API 손님입니다.

    clock·sleep·opener 는 시험에서 바꿔 끼웁니다.
    """

    def __init__(self, gap=MIN_GAP_SEC, retries=RETRIES, clock=time.monotonic,
                 sleep=time.sleep, opener=None):
        self.gap = gap
        self.retries = retries
        self.clock = clock
        self.sleep = sleep
        self.opener = opener or _open
        self._last = None
        self._lock = threading.Lock()
        self.calls = 0

    def url(self, path, params=None):
        if path.startswith("http"):
            u = path
        else:
            u = BASE + (path if path.startswith("/") else "/" + path)
        if params:
            u += ("&" if "?" in u else "?") + urllib.parse.urlencode(params)
        host = urllib.parse.urlsplit(u).hostname
        if host != HOST:
            raise ValueError("네이버 API 주소가 아닙니다: %s" % host)
        return u

    def _wait(self):
        """호출 **시작** 사이를 gap 이상 벌립니다. 여러 스레드가 한 손님을 같이
        써도 시작 간격은 지켜집니다(응답을 기다리는 동안 다음 호출이 출발할 수는
        있습니다)."""
        with self._lock:
            if self._last is not None:
                left = self.gap - (self.clock() - self._last)
                if left > 0:
                    self.sleep(left)
            self._last = self.clock()

    def get(self, path, params=None):
        """JSON 을 돌려줍니다. `code` 가 200 이 아니면 NaverError 입니다."""
        u = self.url(path, params)
        for attempt in range(self.retries + 1):
            self._wait()
            self.calls += 1
            try:
                status, body = self.opener(u)
            except OSError as e:  # 연결·시간 초과
                if attempt >= self.retries:
                    raise
                print("  [알림] 네이버 연결 실패, %d초 뒤 다시 묻습니다: %s" % (RETRY_SLEEP_SEC, e))
                self.sleep(RETRY_SLEEP_SEC)
                continue
            if status >= 500:
                if attempt >= self.retries:
                    raise NaverError("네이버 %d: %s" % (status, u), status)
                print("  [알림] 네이버 %d, %d초 뒤 다시 묻습니다." % (status, RETRY_SLEEP_SEC))
                self.sleep(RETRY_SLEEP_SEC)
                continue
            if status >= 400:
                raise NaverError("네이버 %d: %s" % (status, u), status)
            data = json.loads(body)
            code = data.get("code") if isinstance(data, dict) else None
            if code is not None and code != 200:
                raise NaverError("네이버 응답 code %s: %s" % (code, u), code)
            return data
        raise NaverError("네이버를 읽지 못했습니다: %s" % u)


def _open(u):
    req = urllib.request.Request(u, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


_default = None


def client():
    """프로세스 하나에서 같이 쓰는 손님입니다(간격을 함께 지킵니다)."""
    global _default
    if _default is None:
        _default = Client()
    return _default
