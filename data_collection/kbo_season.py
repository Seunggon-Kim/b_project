# -*- coding: utf-8 -*-
"""시즌 경계를 한 곳에서 정합니다.

## 왜 필요한가

수집과 계산 곳곳에 2026 이 박혀 있었습니다(2026-10-05 검토). 그대로 두면
2027 시즌이 와도 계산 범위에서 조용히 빠지고, 크롤러는 개막일 표에 2027 이
없어 KeyError 로 죽고, 공식 기록 수집은 비시즌 석 달 동안 매일 빨갛게
끝납니다. 날짜와 네이버 일정으로 정해서 해가 바뀌어도 손댈 곳이 없게
합니다.

세 가지를 줍니다.

    last_season(today)    계산할 마지막 시즌입니다. 한국 날짜의 올해이고
                          2026 아래로 내려가지 않습니다. API 의
                          src/lib/pbpseasons.js pbpLastSeason 과 같은 규칙입니다.
                          아직 경기가 없는 해는 빈 결과가 될 뿐입니다.

    opening_day(year)     그해 정규시즌 첫 경기 날짜입니다. 네이버 일정의
                          roundCode 로 찾습니다. 일정이 아직 없으면
                          None 입니다.

    record_season(today)  지금 기록을 받을 시즌입니다. 올해 정규시즌 경기가
                          하루라도 끝났으면 올해, 아니면(비시즌·시범경기)
                          지난해입니다.

## 개막일을 표로 들고 있지 않는 이유

크롤러의 `regular_start` 표(crawler/download.py)는 사람이 해마다 넣어야
하고, 일정이 나오기 전에는 넣을 수도 없습니다. 실제로 2026 값은 처음에
2025 를 베낀 03-22 였습니다. 2026 개막은 03-28 이라 03-22~24 시범경기
15경기가 정규시즌으로 들어갔습니다. 2026-10-05 에 표를 0328 로 고치고 그
경기들을 지웠습니다. 네이버 일정은 경기마다 `roundCode` 를 줍니다. 그해
첫 `kbo_r` 경기가 개막일입니다.

2008~2025 열여덟 시즌 모두 이렇게 찾은 날이 표와 하루도 다르지 않았습니다
(2026-10-05 대조). `kbo_p` 는 넣지 않습니다. 2020 의 `kbo_p` 는 개막 전
연습경기(04-21~05-03)였고, 그 밖에는 시즌 끝의 순위결정전입니다. 넣으면
2020 개막이 05-05 가 아니라 04-21 로 잡힙니다. `kbo_e` 는 시범경기입니다.

## 네이버가 이상한 답을 주면 조용히 넘기지 않습니다

연결이 끊기거나 HTTP 오류가 나면 한 번 더 묻고, 그래도 안 되면 예외를
냅니다. **200 으로 답했는데 모양이 다른 경우**(result.games 가 없음,
`success` 가 거짓, 경기에 `roundCode`·`gameDate`·`statusCode` 가 없음, 목록이
잘림)도 예외(ValueError)입니다. 그대로 두면 "개막 일정이 없다" 로 읽혀
크롤러가 그해 경기를 통째로 건너뛰고, 기록 시즌이 지난해에 머뭅니다.
2008·2016·2020·2024~2026 의 4,877경기 모두 세 키가 있었습니다(2026-10-05).

모양은 맞는데 그해 정규시즌 경기가 6월 1일이 되도록 없으면, 그것도 일정이
이상한 것으로 봅니다. 가장 늦은 개막은 2020-05-05 였습니다. 그때
record_season 은 올해로 물러서고(예전 동작), 크롤러는 실패로 끝냅니다.
"""
import datetime
import json
import time
import urllib.parse
import urllib.request

KST = datetime.timezone(datetime.timedelta(hours=9))

# 예전 샤드 배정표(2008~2026)의 마지막 시즌입니다. 이보다 앞당기지 않습니다.
# src/lib/pbpseasons.js 의 PBP_MIN_LAST_SEASON 과 같은 값입니다.
MIN_LAST_SEASON = 2026

SCHEDULE_API = "https://api-gw.sports.naver.com/schedule/games"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# 개막일을 찾아볼 달입니다. 보통 3월 말이고, 2020 은 5월 5일이었습니다.
OPENING_MONTHS = range(2, 10)

# 이 날짜(월, 일)가 되도록 정규시즌 경기가 없으면 일정이 이상한 것입니다.
# 가장 늦은 개막은 2020-05-05 였습니다(맨 위 설명).
LATEST_OPENING = (6, 1)

# 개막일을 가르는 roundCode 입니다(맨 위 설명). 정규시즌 판정 자체는
# game_type.py 가 합니다. 여기서는 첫 날짜만 찾습니다.
OPENING_ROUND = "kbo_r"

# 경기마다 있어야 하는 키입니다.
GAME_KEYS = ("gameDate", "roundCode", "statusCode")

# 경기가 끝났다는 상태입니다. 크롤러(get_game_ids)와 같은 값입니다.
DONE = ("RESULT", "ENDED")

# 일정 받기가 실패하면 이만큼 쉬고 한 번 더 묻습니다.
RETRIES = 1
RETRY_SLEEP_SEC = 3


def kst_today(now=None):
    """한국 날짜의 오늘입니다. 러너는 UTC 라 1월 1일 새벽이 어긋납니다."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return now.astimezone(KST).date()


def _as_date(today):
    if today is None:
        return kst_today()
    if isinstance(today, datetime.datetime):
        return today.astimezone(KST).date() if today.tzinfo else today.date()
    if isinstance(today, datetime.date):
        return today
    return datetime.date.fromisoformat(str(today)[:10])


def last_season(today=None):
    """계산할 마지막 시즌입니다. 한국 날짜의 올해이고 2026 이상입니다."""
    return max(MIN_LAST_SEASON, _as_date(today).year)


def seasons_through(first, today=None):
    """first 부터 last_season(today) 까지의 시즌 목록입니다."""
    return list(range(first, last_season(today) + 1))


def games_of(body):
    """일정 응답에서 경기 목록을 꺼냅니다. 모양이 다르면 ValueError 입니다.

    정상 응답은 `{"success": true, "result": {"games": [...], "gameTotalCount": n}}`
    입니다. 경기가 없는 달은 games 가 빈 목록입니다.
    """
    if not isinstance(body, dict) or body.get("success") is False:
        raise ValueError("네이버 일정 응답이 실패입니다: %s" % str(body)[:200])
    result = body.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("games"), list):
        raise ValueError("네이버 일정 응답에 result.games 목록이 없습니다: %s" % str(body)[:200])
    games = result["games"]
    total = result.get("gameTotalCount")
    if isinstance(total, int) and total > len(games):
        raise ValueError("네이버 일정이 잘렸습니다: %d / %d경기" % (len(games), total))
    return games


def fetch_month(year, month, timeout=30, retries=RETRIES, sleep=time.sleep):
    """네이버 일정에서 그 달 1군 경기들입니다.

    돌려주는 값은 경기마다 `gameDate`('YYYY-MM-DD')·`roundCode`·
    `statusCode` 가 있는 dict 목록입니다. 받기가 실패하면 RETRY_SLEEP_SEC
    쉬고 retries 번 더 묻습니다. 그래도 안 되면 예외를 그대로 냅니다.
    응답 모양이 다르면 다시 묻지 않고 ValueError 를 냅니다(games_of).
    """
    first = datetime.date(year, month, 1)
    last = (first + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
    q = urllib.parse.urlencode({
        "fields": "basic,roundCode",
        "upperCategoryId": "kbaseball",
        "categoryId": "kbo",
        "fromDate": first.isoformat(),
        "toDate": last.isoformat(),
        "size": 500,
    })
    url = "%s?%s" % (SCHEDULE_API, q)
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = json.loads(r.read().decode("utf-8"))
            break
        except (OSError, ValueError) as e:  # 연결·HTTP·시간 초과·JSON 오류
            if attempt >= retries:
                raise
            print("  [알림] 네이버 일정 %d-%02d 받기 실패, %d초 뒤 다시 묻습니다: %s: %s"
                  % (year, month, RETRY_SLEEP_SEC, type(e).__name__, e))
            sleep(RETRY_SLEEP_SEC)
    return games_of(body)


def opening_day(year, fetch=fetch_month, played=False, until=None):
    """그해 정규시즌 첫 경기(첫 `kbo_r`) 날짜(datetime.date)입니다. 없으면 None 입니다.

    played 면 **끝난** 정규시즌 경기 가운데 첫 날짜입니다. 개막일이 비로
    밀려도 실제로 기록이 생긴 날을 봅니다. until(날짜)을 주면 그 달까지만
    찾습니다. 지나지 않은 달에는 끝난 경기가 있을 수 없습니다.

    일정 받기가 실패하거나 경기에 GAME_KEYS 가 없으면 예외를 냅니다.
    None 은 "모양은 맞는데 정규시즌 경기가 없다" 는 뜻입니다.
    """
    for m in OPENING_MONTHS:
        if until is not None and (year, m) > (until.year, until.month):
            break
        days = []
        for g in fetch(year, m):
            if not isinstance(g, dict) or any(k not in g for k in GAME_KEYS):
                raise ValueError("네이버 일정 경기에 %s 가 없습니다: %s"
                                 % ("·".join(GAME_KEYS), str(g)[:200]))
            if str(g.get("roundCode") or "") != OPENING_ROUND:
                continue
            if played and str(g.get("statusCode") or "") not in DONE:
                continue
            days.append(datetime.date.fromisoformat(str(g.get("gameDate"))[:10]))
        if days:
            return min(days)
    return None


def record_season(today=None, fetch=fetch_month):
    """지금 기록을 받을 시즌입니다.

    올해 정규시즌 경기가 오늘 전에 하나라도 끝났으면 올해, 아니면 지난해입니다.

        2026-10-05   2026   (2026 개막 03-28 이 지났습니다)
        2027-02-15   2026   (비시즌, 2027 경기가 없습니다)
        2027-03-20   2026   (시범경기만 있습니다)
        2027-04-15   2027

    비시즌에 지난해를 다시 받는 것은 해가 없습니다. 이미 끝난 시즌이라 값이
    같습니다.

    일정을 못 받거나 모양이 이상하면 예전처럼 올해로 둡니다. 6월 1일이
    되도록 끝난 정규시즌 경기가 없다고 나와도 일정이 이상한 것이라 올해로
    둡니다. 두 경우 모두 경고를 찍습니다. 지난해로 물러서는 것은 비시즌
    (1월~5월)뿐입니다.
    """
    t = _as_date(today)
    try:
        first = opening_day(t.year, fetch=fetch, played=True, until=t)
    except Exception as e:  # noqa: BLE001
        print("  [경고] 네이버 일정을 못 읽어 올해(%d)로 둡니다: %s: %s"
              % (t.year, type(e).__name__, e))
        return t.year
    if first is not None and first < t:
        return t.year
    if first is None and (t.month, t.day) >= LATEST_OPENING:
        print("  [경고] %d 정규시즌 경기가 %d월 %d일이 되도록 네이버 일정에 없습니다. "
              "일정이 이상할 수 있어 올해(%d)로 둡니다." % ((t.year,) + LATEST_OPENING + (t.year,)))
        return t.year
    return t.year - 1
