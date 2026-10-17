# -*- coding: utf-8 -*-
"""선수 정보(players)를 네이버 값과 play_by_play 로 채웁니다.

KBO 이용약관(2026-10-14 시행)으로 KBO 선수 상세(player_info_scraper.py)·선수
검색(add_new_players.py)·등록 명단(sync_players_from_roster.py)·KBO 이미지
서버(heal_player_photos.py)를 더 쓰지 않습니다. evan 결정 5(2026-10-18):

  (가) 투타·생년월일·키·몸무게·등번호·포지션·연봉·사진은 네이버 선수 상세 값.
  (나) 네이버가 비운 투구 손(throw)은 PBP throws 의 다수 값(2008 이후 던진 투수만).
       타석 방향(bat)도 PBP stands 가 80% 이상 한쪽이면 그 값, 아니면 None.
       2008~2026 대조: 투구 손 947/949, 타석 방향 883/886.
  (다) draft_year·draft_order·signing_bonus·career(출신 학교 전체 경로)는 None.
       네이버 career 는 마지막 학교 하나라 경로를 대신하지 못합니다.
  나머지 KBO 사이트에서 온 값은 남기지 않습니다.

    GET /statistics/categories/kbo/seasons/{y}/players/{id}   (y = 그 선수가 뛴 시즌)

없는 선수는 400 입니다(네이버가 통째로 뺀 선수 10명, 계획서 결정 2 참고).

## 사진

    https://sports-phinf.pstatic.net/player/kbo/default/{id}.png

없는 선수는 404 입니다. 확인은 HEAD 한 번이고 이것도 초당 1회 이하로 합니다.

## 소속

team_id 는 그 시즌 팀 이름(team_seasons)입니다. 올 시즌 선수 목록에 있는 선수만
소속을 넣고, 은퇴(isRetire)면 '' 입니다. 1군 등록 명단은 네이버에 없어 대신하지
않습니다.

    py data_collection/naver_players.py --all --dry-run       # 2008~ 전원
    py data_collection/naver_players.py --new --season 2026    # daily: PBP 에 처음 나온 선수
"""
import argparse
import collections
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))
sys.path.insert(0, str(ROOT))

import naver_http  # noqa: E402

PHOTO = "https://sports-phinf.pstatic.net/player/kbo/default/%d.png"
COLUMNS = ["player_id", "player_name", "team_id", "back_number", "position", "throw", "bat",
           "birthday", "height", "weight", "career", "draft_year", "draft_order",
           "signing_bonus", "salary", "image_url"]
BLANK = ("career", "draft_year", "draft_order", "signing_bonus")  # 결정 5 (다)

POSITION = {
    "PITCHER": "투수", "CATCHER": "포수",
    "FIRST_BASE": "내야수", "SECOND_BASE": "내야수", "THIRD_BASE": "내야수", "SHORTSTOP": "내야수",
    "INFIELDER": "내야수",
    "LEFT_FIELDER": "외야수", "CENTER_FIELDER": "외야수", "RIGHT_FIELDER": "외야수",
    "OUTFIELDER": "외야수",
}
HAND = {"우": "R", "좌": "L", "양": "S"}
BAT_SHARE = 0.8


def detail(pid, season, cl=None, cache=None):
    """네이버 선수 상세(result.player) 또는 None(400)."""
    if cache:
        p = Path(cache) / ("%d.json" % pid)
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            return d or None
    cl = cl or naver_http.client()
    try:
        d = cl.get("/statistics/categories/kbo/seasons/%d/players/%d" % (season, pid))
        d = (d.get("result") or {}).get("player")
    except naver_http.NaverError as e:
        if e.status != 400:
            raise
        d = None
    if cache:
        Path(cache).mkdir(parents=True, exist_ok=True)
        (Path(cache) / ("%d.json" % pid)).write_text(json.dumps(d or {}, ensure_ascii=False), encoding="utf-8")
    return d


_photo_lock = threading.Lock()
_photo_last = [0.0]


def photo(pid, opener=None, gap=naver_http.MIN_GAP_SEC):
    """사진 주소. 없는 선수(404)면 None."""
    u = PHOTO % pid
    with _photo_lock:
        left = gap - (time.monotonic() - _photo_last[0])
        if left > 0:
            time.sleep(left)
        _photo_last[0] = time.monotonic()
    if opener:
        return u if opener(u) == 200 else None
    req = urllib.request.Request(u, method="HEAD", headers=naver_http.HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return u if r.status == 200 else None
    except urllib.error.HTTPError:
        return None


def play_type(s):
    """'우투좌타' → ('R', 'L'), '우언양타' → ('R', 'S'). 모르면 (None, None)."""
    if not s or len(s) < 4:
        return None, None
    return HAND.get(s[0]), HAND.get(s[2])


def won(s):
    """연봉 글자 → 숫자. '50,000만원' → 500000000(원), '1,100,000달러' → 1100000(달러).

    외국인 선수는 예전 KBO 값처럼 달러 그대로 둡니다. 화면(isForeignPlayer)이
    1,000만 미만을 달러로 읽습니다.
    """
    if not s:
        return None
    digits = "".join(ch for ch in str(s) if ch.isdigit())
    if not digits:
        return None
    return int(digits) * (10000 if "만" in str(s) else 1)


def merge_hands(acc, rows):
    """여러 시즌 PBP 를 차례로 넣을 때 쓰는 누적판(acc = (th, st) Counter 사전)."""
    th, st = acc
    for x in rows:
        if x.get("pitch_number") in (None, ""):
            continue
        if x.get("pitcher_ID") and x.get("throws") in HAND:
            th[int(x["pitcher_ID"])][HAND[x["throws"]]] += 1
        if x.get("batter_ID") and x.get("stands") in HAND:
            st[int(x["batter_ID"])][HAND[x["stands"]]] += 1
    return acc


def new_hands():
    return (collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter))


def hands_from_pbp(rows):
    """PBP 행들 → ({투수 ID: 'R'|'L'}, {타자 ID: 'R'|'L'|'S'})."""
    return finish_hands(merge_hands(new_hands(), rows))


def finish_hands(acc):
    th, st = acc
    throw = {p: c.most_common(1)[0][0] for p, c in th.items()}
    bat = {}
    for p, c in st.items():
        top, n = c.most_common(1)[0]
        if n / sum(c.values()) >= BAT_SHARE:
            bat[p] = top
    return throw, bat


def build_row(pid, d, current_team, pbp_throw, pbp_bat, image_url, pbp_name=None):
    """d: 네이버 상세(None 이면 네이버가 뺀 선수). current_team: 올 시즌 소속 이름 또는 None."""
    t, b = play_type((d or {}).get("playerPlayType"))
    row = {
        "player_id": pid,
        "player_name": (d or {}).get("playerName") or pbp_name,
        "team_id": current_team or "",
        "back_number": (d or {}).get("backNo"),
        "position": POSITION.get((d or {}).get("position") or ""),
        "throw": t or pbp_throw.get(pid),
        "bat": b or pbp_bat.get(pid),
        "birthday": ((d or {}).get("dateOfBirth") or "").replace("-", "") or None,
        "height": (d or {}).get("height"),
        "weight": (d or {}).get("weight"),
        "salary": won((d or {}).get("salary")) if current_team else None,
        "image_url": image_url,
    }
    for c in BLANK:
        row[c] = None
    return row


def write(sink, rows, teams=None):
    """있으면 고치고 없으면 넣습니다. created_at 은 그대로 두고 updated_at 을 지금으로.

    teams({선수 ID: 그 시즌 팀 이름})를 주면 이미 있는 선수의 소속도 맞춥니다
    (sync_players_from_roster.py 를 대신합니다. 바뀐 줄만 고칩니다).
    """
    n = 0
    if rows:
        # created_at 은 넘기지 않습니다(넣을 때 MySQL 기본값, 고칠 때 그대로).
        n = sink.upsert("players", COLUMNS, ["player_id"], rows, touch="updated_at")
    for pid, team in sorted((teams or {}).items()):
        n += sink.execute("UPDATE players SET team_id = %s, updated_at = UTC_TIMESTAMP() "
                          "WHERE player_id = %s AND (team_id IS NULL OR team_id <> %s)",
                          (team, pid, team))
    sink.refresh_count("players")
    return n


def current_teams(season, names, cache=None):
    """올 시즌 선수 목록의 {선수 ID: 그 시즌 팀 이름}(경기 수 큰 행)."""
    import naver_season_stats as nss
    raw = nss.fetch_season(season, cache=cache)
    out = {}
    for kind, key in (("HITTER", "hitterGameCount"), ("PITCHER", "pitcherGameCount")):
        for pid, x in nss.pick(raw[kind], key).items():
            out.setdefault(pid, nss.team_name(x, season, names))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--all", action="store_true", help="2008~ 공식 기록·players 의 선수 전원")
    ap.add_argument("--new", action="store_true", help="그 시즌 PBP 에 나왔는데 players 에 없는 선수")
    ap.add_argument("--season", type=int)
    ap.add_argument("--detail-cache")
    ap.add_argument("--naver-cache")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    from d1_load import query
    from kbo_season import record_season
    season = a.season or record_season()
    names = {(r["franchise_id"], int(r["season"])): r["team_name"]
             for r in query("SELECT franchise_id, season, team_name FROM team_seasons")}
    teams = current_teams(season, names, a.naver_cache)
    have = {int(r["player_id"]) for r in query("SELECT player_id FROM players")}
    last = {}
    for t in ("kbo_official_batter_stats", "kbo_official_pitcher_stats"):
        for r in query("SELECT player_id, MAX(season) AS s FROM %s WHERE season >= 2008 GROUP BY player_id" % t):
            last[int(r["player_id"])] = max(last.get(int(r["player_id"]), 0), int(r["s"]))
    acc = new_hands()
    pbp_names = {}
    first, lastpbp = (2008, season) if a.all else (season, season)
    for y in range(first, lastpbp + 1):
        rows = query("SELECT pitch_number, pitcher_ID, batter_ID, pitcher, batter, throws, stands "
                     "FROM play_by_play WHERE game_date BETWEEN %d AND %d" % (y * 10000, y * 10000 + 9999))
        merge_hands(acc, rows)
        for x in rows:
            for k, nk in (("pitcher_ID", "pitcher"), ("batter_ID", "batter")):
                if x.get(k):
                    pbp_names[int(x[k])] = x.get(nk)
                    last.setdefault(int(x[k]), y)
    throw, bat = finish_hands(acc)
    if a.all:
        ids = sorted(have | set(last))
    elif a.new:
        ids = sorted(set(pbp_names) - have)
    else:
        ap.error("--all 이나 --new 가 필요합니다")
    print("대상 %d명" % len(ids), flush=True)
    rows = []
    miss = 0
    for i, pid in enumerate(ids, 1):
        d = detail(pid, last.get(pid, season), cache=a.detail_cache)
        miss += d is None
        img = photo(pid) if d else None
        rows.append(build_row(pid, d, teams.get(pid), throw, bat, img, pbp_names.get(pid)))
        if i % 100 == 0:
            print("  %d/%d" % (i, len(ids)), flush=True)
    print("행 %d, 네이버 상세 없음 %d, 사진 없음 %d"
          % (len(rows), miss, sum(1 for r in rows if not r["image_url"])))
    if a.dry_run:
        print("[미리보기] 넣지 않았습니다.")
        return 0
    from mysql_sink import mirror
    mirror("players", lambda sink: write(sink, rows, teams if a.new else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
