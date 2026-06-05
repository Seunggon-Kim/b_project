

# ===== KBO 경기 일정/결과 (Naver 스포츠 API 프록시) =====
import time as _time
import concurrent.futures as _futures

_SCHEDULE_CACHE = {}
_SCHEDULE_TTL = 30  # seconds


def _kbo_fetch_json(url, timeout=8):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _kbo_game_meta(game_id):
    try:
        return _kbo_fetch_json("https://api-gw.sports.naver.com/schedule/games/" + game_id)
    except Exception:
        return None


def _kbo_normalize_game(meta):
    g = (meta or {}).get("result", {}).get("game", {})
    if not g:
        return None
    status = g.get("statusCode", "") or ""
    final = status in ("RESULT", "ENDED")
    live = status in ("LIVE", "PLAYING", "STARTED")
    show_score = final or live
    dt = g.get("gameDateTime", "") or ""
    time_str = dt[11:16] if len(dt) >= 16 else ""

    def _score(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    def _team(prefix):
        return {
            "name": g.get(prefix + "TeamName", "") or "",
            "code": g.get(prefix + "TeamCode", "") or "",
            "emblem": g.get(prefix + "TeamEmblemUrl", "") or "",
            "score": _score(g.get(prefix + "TeamScore")) if show_score else None,
            "starter": g.get(prefix + "StarterName", "") or "",
        }

    return {
        "gameId": g.get("gameId"),
        "datetime": dt,
        "time": time_str,
        "stadium": g.get("stadium", "") or "",
        "statusCode": status,
        "statusInfo": g.get("statusInfo", "") or "",
        "currentInning": g.get("currentInning", "") or "",
        "broadChannel": g.get("broadChannel", "") or "",
        "cancel": bool(g.get("cancel")),
        "final": final,
        "live": live,
        "showScore": show_score,
        "winner": g.get("winner", "") or "",
        "home": _team("home"),
        "away": _team("away"),
    }


@app.get("/schedule")
async def get_schedule(date: str = None):
    """KBO 경기 일정/결과 (Naver 스포츠 API 프록시). date=YYYY-MM-DD (미지정 시 KST 오늘)."""
    try:
        if not date:
            kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
            date = kst.strftime("%Y-%m-%d")
        target = date.replace("-", "")

        cached = _SCHEDULE_CACHE.get(date)
        if cached and (_time.time() - cached[0] < _SCHEDULE_TTL):
            return cached[1]

        cal = _kbo_fetch_json(
            "https://api-gw.sports.naver.com/schedule/calendar"
            "?upperCategoryId=kbaseball&categoryIds=kbo&date=" + date
        )
        gids = []
        for d in cal.get("result", {}).get("dates", []):
            dkey = str(d.get("ymd") or d.get("date") or "").replace("-", "")
            if dkey == target:
                for gi in (d.get("gameInfos") or []):
                    if gi.get("gameId"):
                        gids.append(gi.get("gameId"))
                break

        games = []
        if gids:
            with _futures.ThreadPoolExecutor(max_workers=8) as ex:
                metas = list(ex.map(_kbo_game_meta, gids))
            for m in metas:
                ng = _kbo_normalize_game(m)
                if ng:
                    games.append(ng)
            games.sort(key=lambda x: ((x.get("datetime") or ""), (x.get("gameId") or "")))

        result = {"date": date, "count": len(games), "games": games}
        _SCHEDULE_CACHE[date] = (_time.time(), result)
        return result
    except Exception as e:
        return {"date": date, "count": 0, "games": [], "error": str(e)}
