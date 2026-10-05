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
하고, 일정이 나오기 전에는 넣을 수도 없습니다. 실제로 2026 값은 2025 를
베껴 둔 03-22 였는데, 2026 개막은 03-28 이라 03-22~24 시범경기 15경기가
정규시즌으로 들어갔습니다. 네이버 일정은 경기마다 `roundCode` 를
줍니다. 그해 첫 `kbo_r` 경기가 개막일입니다.

2008~2025 열여덟 시즌 모두 이렇게 찾은 날이 표와 하루도 다르지 않았습니다
(2026-10-05 대조). `kbo_p` 는 넣지 않습니다. 2020 의 `kbo_p` 는 개막 전
연습경기(04-21~05-03)였고, 그 밖에는 시즌 끝의 순위결정전입니다. 넣으면
2020 개막이 05-05 가 아니라 04-21 로 잡힙니다. `kbo_e` 는 시범경기입니다.
"""
import datetime
import json
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

# 개막일을 가르는 roundCode 입니다(맨 위 설명). 정규시즌 판정 자체는
# game_type.py 가 합니다. 여기서는 첫 날짜만 찾습니다.
OPENING_ROUND = "kbo_r"

# 경기가 끝났다는 상태입니다. 크롤러(get_game_ids)와 같은 값입니다.
DONE = ("RESULT", "ENDED")


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


def fetch_month(year, month, timeout=30):
    """네이버 일정에서 그 달 1군 경기들입니다. 실패하면 예외를 그대로 냅니다.

    돌려주는 값은 경기마다 `gameDate`('YYYY-MM-DD')·`roundCode`·
    `statusCode` 가 있는 dict 목록입니다.
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
    req = urllib.request.Request("%s?%s" % (SCHEDULE_API, q), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read().decode("utf-8"))
    return (body.get("result") or {}).get("games") or []


def opening_day(year, fetch=fetch_month, played=False, until=None):
    """그해 정규시즌 첫 경기(첫 `kbo_r`) 날짜(datetime.date)입니다. 없으면 None 입니다.

    played 면 **끝난** 정규시즌 경기 가운데 첫 날짜입니다. 개막일이 비로
    밀려도 실제로 기록이 생긴 날을 봅니다. until(날짜)을 주면 그 달까지만
    찾습니다. 지나지 않은 달에는 끝난 경기가 있을 수 없습니다.

    일정 받기가 실패하면 예외를 냅니다. 부르는 쪽이 정합니다.
    """
    for m in OPENING_MONTHS:
        if until is not None and (year, m) > (until.year, until.month):
            break
        days = []
        for g in fetch(year, m) or []:
            if str(g.get("roundCode") or "") != OPENING_ROUND:
                continue
            if played and str(g.get("statusCode") or "") not in DONE:
                continue
            try:
                days.append(datetime.date.fromisoformat(str(g.get("gameDate"))[:10]))
            except ValueError:
                continue
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
    같습니다. 일정을 못 받으면 예전처럼 올해로 둡니다(그 사실을 찍습니다).
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
    return t.year - 1
