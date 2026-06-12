"""선수 정보 레지스트리 동기화 — 신규 영입·이적·등번호 변경을 매일 DB에 반영한다.

기존 한계(이 모듈이 메우는 구멍):
  - player_info_scraper.py(월 1회)는 공식 스탯에 등장한 선수만 수집 → 영입 직후 선수 누락
  - daily_player_detector.py는 players에 이미 있는 선수의 팀 변경만 감지 → 신규 INSERT 없음

소스 4종:
  1) 현 시즌 kbo_official_*_stats  — players 미등록 player_id (id·팀 확정)
  2) 현 시즌 play_by_play          — players 미등록 batter/pitcher id
  3) RegisterAll.aspx (등록 현황)  — 팀별 1군 등록 (이름·등번호) → 신규/변경 의심
  4) GetTradeList ws (이동 현황)   — 트레이드·등번호 변경·FA·추가 등록 이벤트
     원본은 player_moves_raw 테이블에 멱등 적재(감사 추적), 신규 행만 트리거로 사용
     (일시 오류로 처리 실패한 행은 raw에서 지워 다음 실행에서 재트리거)

반영 정책:
  - 신규 선수: 프로필 수집(requests, 정적 HTML) → players UPSERT + player_history 시드 행
  - 기존 선수 변경: 프로필 재수집 → SCD-추적 필드(팀·등번호·포지션·투타·신체) 달라졌을 때만
    player_history 기존 행 닫고(valid_to) 새 행 INSERT + players UPDATE
  - 개명: SCD 필드 무변경이어도 이름은 players에 반영 (history 스키마에 이름 컬럼 없음)
  - valid_from: 이동 이벤트 날짜 > 오늘 순. 단 열린 history 행보다 과거로는 닫지 않음(역전 방지)
  - 이벤트는 날짜 오름차순으로 적용 (API는 최신순 반환 — 그대로 적용하면 옛 상태가 최종 승자가 됨)

cron (KST 05:40, 스탯·PBP·detector 이후):
  40 20 * * * cd ~/b_project && venv/bin/python data_collection/player_registry_sync.py >> /tmp/player_registry_sync.log 2>&1
초기 백필:
  venv/bin/python data_collection/player_registry_sync.py --full
"""
import argparse
import logging
import re
import sqlite3
import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# 파서는 기존 모듈을 단일 출처로 재사용한다.
# (player_info_scraper는 import 시 자체 logging.basicConfig를 호출하므로
#  이 모듈은 propagate=False인 전용 로거를 쓴다)
from player_info_scraper import (
    parse_birthday,
    parse_draft_info,
    parse_height_weight,
    parse_number,
    parse_position,
)

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "database" / "kbo_stats.db"

BASE = "https://www.koreabaseball.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
PROFILE_PREFIX = "cphContents_cphContents_cphContents_playerProfile_"

KBO_TEAMS = {"LG", "KT", "SSG", "NC", "두산", "KIA", "롯데", "삼성", "한화", "키움"}

# 소속·등번호·이름이 실제로 바뀌는 이벤트만 SCD 트리거로 쓴다
# (부상자 명단·말소류는 등록 상태 변화일 뿐 소속 변화가 아님 — raw 적재만)
TRIGGER_SECTIONS = {
    "트레이드", "트레이드(웨이버)", "등번호 변경", "FA 계약", "소속선수 추가 등록",
    "웨이버", "임의해지 복귀", "2차 드래프트", "FA 보상선수", "해외 복귀 FA 계약",
    "군보류 해제", "개명",
}

# SCD Type 2로 이력을 남기는 필드 (player_history 컬럼과 일치)
SCD_FIELDS = ("team_id", "back_number", "position", "throw", "bat", "height", "weight")

ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")

logger = logging.getLogger("player_registry_sync")
logger.setLevel(logging.INFO)
logger.propagate = False
_h = logging.StreamHandler()
_h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(_h)


def _norm_back(v):
    """등번호 정규화: '00'→0, '46'→46, 비숫자/None→None (DB INTEGER 컬럼과 동일 기준)."""
    s = str(v).strip() if v is not None else ""
    return int(s) if s.isdigit() else None


def _soup(html):
    """KBO 페이지는 IE 조건부 주석 때문에 표준 html.parser가 문서 대부분을 버린다
    (태그 36개만 파싱되는 침묵 실패) — lxml을 우선 사용한다."""
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


# ──────────────────────────── HTTP ────────────────────────────

def _get(session, url, **kw):
    for attempt in (1, 2):
        try:
            r = session.get(url, timeout=15, **kw)
            if r.status_code == 200:
                return r
        except requests.RequestException as e:
            logger.warning(f"GET 재시도({attempt}) {url}: {e}")
        time.sleep(1)
    return None


def _post(session, url, data, referer):
    for attempt in (1, 2):
        try:
            r = session.post(url, data=data, headers={"Referer": referer}, timeout=15)
            if r.status_code == 200:
                return r.json()
        except (requests.RequestException, ValueError) as e:
            logger.warning(f"POST 재시도({attempt}) {url}: {e}")
        time.sleep(1)
    return None


def make_session():
    """KBO ws 엔드포인트는 쿠키·Referer가 필요하므로 워밍업 GET 후 세션 반환.

    워밍업이 실패해도 세션은 반환한다 — 정적 프로필 수집은 쿠키 없이 동작하고,
    ws 호출은 _post가 None을 반환해 단계별로 우아하게 건너뛴다.
    """
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "X-Requested-With": "XMLHttpRequest"})
    if _get(s, f"{BASE}/Player/Search.aspx") is None:
        logger.warning("워밍업 GET 실패 — 쿠키 없이 진행 (ws 호출은 실패할 수 있음)")
    return s


# ──────────────────────── 프로필 수집 ─────────────────────────

def scrape_player_profile(session, player_id):
    """선수 상세 페이지(정적 HTML)에서 프로필 파싱. 타자/투수 자동 감지, 실패 시 None.

    페이지에 팀 표기가 없으므로 team_id는 호출자가 소스(스탯·등록현황·이벤트)에서 채운다.
    """
    for kind in ("HitterDetail", "PitcherDetail"):
        r = _get(session, f"{BASE}/Record/Player/{kind}/Basic.aspx?playerId={player_id}")
        if r is None:
            continue
        soup = _soup(r.text)

        def lbl(name):
            el = soup.find(id=PROFILE_PREFIX + name)
            txt = el.get_text(strip=True) if el else None
            return txt if txt and txt != "-" else None

        name = lbl("lblName")
        if not name:
            continue

        position, throw, bat = parse_position(lbl("lblPosition"))
        height, weight = parse_height_weight(lbl("lblHeightWeight"))
        draft_year, draft_order = parse_draft_info(lbl("lblDraft"))

        img = soup.find(id=PROFILE_PREFIX + "imgProgile")
        image_url = img.get("src") if img else None
        if image_url and "no-Image" in image_url:
            image_url = None
        if image_url and image_url.startswith("//"):
            image_url = "https:" + image_url

        return {
            "player_id": str(player_id),
            "player_name": name,
            "back_number": _norm_back(lbl("lblBackNo")),
            "position": position,
            "throw": throw,
            "bat": bat,
            "birthday": parse_birthday(lbl("lblBirthday")),
            "height": height,
            "weight": weight,
            "career": lbl("lblCareer"),
            "draft_year": draft_year,
            "draft_order": draft_order,
            "signing_bonus": parse_number(lbl("lblPayment")),
            "salary": parse_number(lbl("lblSalary")),
            "image_url": image_url,
        }
    return None


def search_player(session, name):
    """이름 → 현역 후보 목록 [{P_ID, P_NM, BACK_NO, POS_NO, T_NM, ...}].

    통신·응답 오류는 None, 검색 성공이지만 결과 없음은 [] — 호출자가 반드시 구분할 것.
    (오류를 0건으로 뭉개면 일시 장애가 잘못된 이적 처리로 고착된다)
    """
    data = _post(session, f"{BASE}/ws/Controls.asmx/GetSearchPlayer",
                 {"name": name}, referer=f"{BASE}/Player/Search.aspx")
    if data is None or data.get("code") != "100":
        return None
    return data.get("now") or []


# ─────────────────────── 외부 소스 파싱 ───────────────────────

def fetch_register_all(session):
    """등록 현황 → [(team, pos_group, name, back_number:int|None)].

    표 구조: 행=구단, 열=[감독, 코치, 투수, 포수, 내야수, 외야수], 항목="이름(등번호)"
    감독·코치 열은 선수가 아니므로 제외한다.
    """
    r = _get(session, f"{BASE}/Player/RegisterAll.aspx")
    if r is None:
        return []
    soup = _soup(r.text)
    # 팀마다 별도 table.tData가 있다 (단일 테이블 아님 — find()는 LG만 잡힌다)
    tables = soup.find_all("table", class_="tData")
    if not tables:
        logger.warning("RegisterAll: 표를 찾지 못함 (페이지 구조 변경?)")
        return []

    pos_groups = (None, None, "투수", "포수", "내야수", "외야수")
    out = []
    for table in tables:
        body = table.find("tbody")
        if body is None:
            continue
        for tr in body.find_all("tr"):
            th = tr.find("th")
            if th is None:
                continue
            team = th.get_text(" ", strip=True).split()[0]
            if team not in KBO_TEAMS:
                continue  # 로스터 외 표(범례 등)
            for idx, td in enumerate(tr.find_all("td")):
                if idx >= len(pos_groups) or pos_groups[idx] is None:
                    continue
                for li in td.find_all("li"):
                    m = re.match(r"^(.+?)\((\d+)\)$", li.get_text(strip=True))
                    if m:
                        out.append((team, pos_groups[idx], m.group(1).strip(), int(m.group(2))))
    teams_seen = {t for t, *_ in out}
    if len(teams_seen) < len(KBO_TEAMS):
        logger.warning(f"RegisterAll: {len(KBO_TEAMS)}팀 중 {len(teams_seen)}팀만 파싱됨 "
                       f"(누락: {sorted(KBO_TEAMS - teams_seen)})")
    return out


def fetch_trade_events(session, year, month):
    """이동 현황(GetTradeList) → [{date, section, team, player, note}]. month=0이면 연도 전체."""
    events, page, list_count = [], 1, 100
    while page <= 30:
        data = _post(session, f"{BASE}/ws/Player.asmx/GetTradeList", {
            "seasonId": str(year), "monthId": str(month), "bdSc": "0",
            "teamName": "", "searchIf": "", "pageNo": str(page), "listCount": str(list_count),
        }, referer=f"{BASE}/Player/Trade.aspx")
        rows = (data or {}).get("rows") or []
        for row in rows:
            cells = [c.get("Text", "") or "" for c in row.get("row", [])]
            if len(cells) >= 4:
                events.append({
                    "date": cells[0].strip(), "section": cells[1].strip(),
                    "team": cells[2].strip(), "player": cells[3].strip(),
                    "note": (cells[4].strip() if len(cells) > 4 else ""),
                })
        if len(rows) < list_count:
            break
        page += 1
    return events


def strip_player_text(text):
    """'정은원(내야수)' → '정은원'."""
    return re.sub(r"\([^)]*\)\s*$", "", text).strip()


# ──────────────────────────── DB ─────────────────────────────

def ensure_tables(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS player_moves_raw (
            move_date   TEXT NOT NULL,
            section     TEXT NOT NULL,
            team        TEXT NOT NULL,
            player_text TEXT NOT NULL,
            note        TEXT NOT NULL DEFAULT '',
            fetched_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (move_date, section, team, player_text, note)
        )
    """)


def store_moves(con, events):
    """이벤트 원본 멱등 적재, 이번에 새로 들어온 행만 반환."""
    new_events = []
    cur = con.cursor()
    for e in events:
        cur.execute("""
            INSERT OR IGNORE INTO player_moves_raw (move_date, section, team, player_text, note)
            VALUES (?, ?, ?, ?, ?)
        """, (e["date"], e["section"], e["team"], e["player"], e["note"]))
        if cur.rowcount:
            new_events.append(e)
    con.commit()
    return new_events


def unstore_move(con, e):
    """처리 실패(일시 오류) 이벤트를 raw에서 제거해 다음 실행에서 재트리거되게 한다."""
    con.execute("""
        DELETE FROM player_moves_raw
        WHERE move_date=? AND section=? AND team=? AND player_text=? AND note=?
    """, (e["date"], e["section"], e["team"], e["player"], e["note"]))
    con.commit()


def upsert_player(con, info, team_id):
    """players UPSERT. None 필드는 기존 값을 보존한다(미상으로 덮지 않음)."""
    con.execute("""
        INSERT INTO players (player_id, player_name, team_id, back_number, position, throw, bat,
                             birthday, height, weight, career, draft_year, draft_order,
                             signing_bonus, salary, image_url, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(player_id) DO UPDATE SET
            player_name = excluded.player_name,
            team_id = COALESCE(excluded.team_id, players.team_id),
            back_number = COALESCE(excluded.back_number, players.back_number),
            position = COALESCE(excluded.position, players.position),
            throw = COALESCE(excluded.throw, players.throw),
            bat = COALESCE(excluded.bat, players.bat),
            birthday = COALESCE(excluded.birthday, players.birthday),
            height = COALESCE(excluded.height, players.height),
            weight = COALESCE(excluded.weight, players.weight),
            career = COALESCE(excluded.career, players.career),
            draft_year = COALESCE(excluded.draft_year, players.draft_year),
            draft_order = COALESCE(excluded.draft_order, players.draft_order),
            signing_bonus = COALESCE(excluded.signing_bonus, players.signing_bonus),
            salary = COALESCE(excluded.salary, players.salary),
            image_url = COALESCE(excluded.image_url, players.image_url),
            updated_at = CURRENT_TIMESTAMP
    """, (info["player_id"], info["player_name"], team_id, info["back_number"],
          info["position"], info["throw"], info["bat"], info["birthday"],
          info["height"], info["weight"], info["career"], info["draft_year"],
          info["draft_order"], info["signing_bonus"], info["salary"], info["image_url"]))


def seed_history(con, info, team_id, src, valid_from=None):
    """신규 선수의 history 시드 행. 이미 열린 행이 있으면 중복 생성하지 않는다."""
    if con.execute("SELECT 1 FROM player_history WHERE player_id=? AND valid_to IS NULL",
                   (info["player_id"],)).fetchone():
        return
    con.execute("""
        INSERT INTO player_history
            (player_id, valid_from, valid_to, team_id, back_number, position,
             throw, bat, height, weight, detection_src)
        VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (info["player_id"], valid_from or date.today().isoformat(), team_id,
          info["back_number"], info["position"], info["throw"], info["bat"],
          info["height"], info["weight"], src))


def insert_new_player(con, info, team_id, src, valid_from=None):
    upsert_player(con, info, team_id)
    seed_history(con, info, team_id, src, valid_from)
    con.commit()
    logger.info(f"  신규 등록: {info['player_id']} {info['player_name']} "
                f"team={team_id} back={info['back_number']} src={src}")


def apply_player_change(con, pid, info, new_team, src, event_date=None):
    """SCD-추적 필드가 실제로 달라졌을 때만 history 닫고 새 행 + players 갱신.

    - new_team=None이면 팀은 변경하지 않는다(프로필 페이지에 팀 정보가 없으므로
      팀 변경은 스탯·등록현황·이동 이벤트가 줄 때만 반영).
    - SCD 무변경이어도 이름이 바뀌었으면(개명) players.player_name은 갱신한다.
    - valid_from은 열린 history 행의 valid_from보다 과거로 내려가지 않는다(구간 역전 방지).
    반환: 변경 적용 여부.
    """
    cur = con.cursor()
    row = cur.execute(
        "SELECT player_name, team_id, back_number, position, throw, bat, height, weight "
        "FROM players WHERE player_id=?", (pid,)).fetchone()
    if row is None:
        return False
    old_name, old_scd = row[0], row[1:]

    new_vals = dict(zip(SCD_FIELDS, old_scd))
    for f in SCD_FIELDS[1:]:  # team_id 제외 프로필 필드
        if info.get(f) is not None:
            new_vals[f] = info[f]
    if new_team:
        new_vals["team_id"] = new_team

    changed = [f for f, old in zip(SCD_FIELDS, old_scd) if new_vals[f] != old]
    name_changed = bool(info.get("player_name")) and info["player_name"] != old_name

    if not changed:
        if name_changed:  # 순수 개명 — history 스키마에 이름 컬럼이 없으므로 players만 갱신
            cur.execute("UPDATE players SET player_name=?, updated_at=datetime('now') "
                        "WHERE player_id=?", (info["player_name"], pid))
            con.commit()
            logger.info(f"  개명 반영: {pid} {old_name} → {info['player_name']} src={src}")
            return True
        return False

    valid_from = event_date if (event_date and ISO_DATE.match(event_date)) \
        else date.today().isoformat()
    open_row = cur.execute(
        "SELECT valid_from FROM player_history WHERE player_id=? AND valid_to IS NULL",
        (pid,)).fetchone()
    if open_row and open_row[0] and valid_from < open_row[0]:
        valid_from = open_row[0]  # 늦게 공시된 과거 이벤트가 최신 구간을 역전시키지 않도록

    cur.execute("UPDATE player_history SET valid_to=? WHERE player_id=? AND valid_to IS NULL",
                (valid_from, pid))
    cur.execute("""
        INSERT INTO player_history
            (player_id, valid_from, valid_to, team_id, back_number, position,
             throw, bat, height, weight, detection_src)
        VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (pid, valid_from, new_vals["team_id"], new_vals["back_number"], new_vals["position"],
          new_vals["throw"], new_vals["bat"], new_vals["height"], new_vals["weight"], src))
    cur.execute("""
        UPDATE players SET team_id=?, back_number=?, position=?, throw=?, bat=?,
                           height=?, weight=?, player_name=?, updated_at=datetime('now')
        WHERE player_id=?
    """, (new_vals["team_id"], new_vals["back_number"], new_vals["position"], new_vals["throw"],
          new_vals["bat"], new_vals["height"], new_vals["weight"],
          info.get("player_name") or old_name, pid))
    con.commit()
    logger.info(f"  변경 반영: {pid} {info.get('player_name') or old_name} {changed} "
                f"src={src} from={valid_from}")
    return True


# ─────────────────────── 동기화 단계 ──────────────────────────

def current_season(con):
    row = con.execute("""
        SELECT MAX(season) FROM (
            SELECT MAX(season) AS season FROM kbo_official_batter_stats
            UNION ALL SELECT MAX(season) FROM kbo_official_pitcher_stats)
    """).fetchone()
    return row[0] or date.today().year


def sync_missing_from_stats(con, session):
    """현 시즌 공식 스탯에 있는데 players에 없는 선수 수집 (id·팀 확정).

    부수 작업: 과거 INSERT 잔재로 team_id가 NULL인 기존 행도 스탯 팀으로 보정한다.
    """
    season = current_season(con)
    rows = con.execute("""
        SELECT s.player_id, s.player_name, s.player_team
        FROM (SELECT player_id, player_name, player_team
                FROM kbo_official_batter_stats WHERE season=?
              UNION
              SELECT player_id, player_name, player_team
                FROM kbo_official_pitcher_stats WHERE season=?) s
        LEFT JOIN players p ON p.player_id = s.player_id
        WHERE p.player_id IS NULL
    """, (season, season)).fetchall()
    # 타자·투수 표에 모두 등장하면 UNION이 2행을 줄 수 있으므로 id 기준 dedup
    targets = {}
    for pid, name, team in rows:
        targets.setdefault(str(pid), (name, team if team in KBO_TEAMS else None))

    n = 0
    for pid, (name, team) in targets.items():
        info = scrape_player_profile(session, pid)
        if info is None:
            logger.warning(f"  스탯 미등록 {pid} {name}: 프로필 수집 실패")
            continue
        insert_new_player(con, info, team, "registry_stats")
        n += 1
        time.sleep(0.5)
    logger.info(f"[1/4] 스탯 기준 미등록: 대상 {len(targets)} / 등록 {n}")

    null_rows = con.execute("""
        SELECT p.player_id, s.player_team
        FROM players p
        JOIN (SELECT player_id, player_team FROM kbo_official_batter_stats WHERE season=?
              UNION SELECT player_id, player_team FROM kbo_official_pitcher_stats WHERE season=?) s
          ON s.player_id = p.player_id
        WHERE p.team_id IS NULL
    """, (season, season)).fetchall()
    for pid, team in dict(null_rows).items():
        if team in KBO_TEAMS:
            con.execute("UPDATE players SET team_id=?, updated_at=datetime('now') "
                        "WHERE player_id=? AND team_id IS NULL", (team, pid))
            logger.info(f"  팀 미상 보정: {pid} → {team}")
    con.commit()
    return n


def sync_missing_from_pbp(con, session):
    """현 시즌 PBP에 등장하는데 players에 없는 선수 수집 (팀은 검색으로 보강)."""
    season = str(current_season(con))
    rows = con.execute("""
        SELECT DISTINCT id FROM (
            SELECT batter_ID AS id FROM play_by_play WHERE substr(gameID,1,4)=?
            UNION SELECT pitcher_ID FROM play_by_play WHERE substr(gameID,1,4)=?)
        WHERE id IS NOT NULL AND id <> ''
          AND CAST(id AS TEXT) NOT IN (SELECT player_id FROM players)
    """, (season, season)).fetchall()
    n = 0
    for (pid,) in rows:
        info = scrape_player_profile(session, pid)
        if info is None:
            logger.warning(f"  PBP 미등록 {pid}: 프로필 수집 실패")
            continue
        team = None
        cands = search_player(session, info["player_name"]) or []
        for cand in cands:
            if str(cand.get("P_ID")) == str(pid) and cand.get("T_NM") in KBO_TEAMS:
                team = cand["T_NM"]
                break
        insert_new_player(con, info, team, "registry_pbp")
        n += 1
        time.sleep(0.5)
    logger.info(f"[2/4] PBP 기준 미등록: 대상 {len(rows)} / 등록 {n}")
    return n


def resolve_and_apply(con, session, name, team, src, event_date=None, back_number=None):
    """이름(+팀)을 players에 매칭해 변경 반영하거나, 미등록이면 검색으로 신규 등록.

    반환: "changed" | "new" | "same" | "skip"(모호) | "fail"(일시 오류 — 재시도 가치 있음)
    """
    cur = con.cursor()
    cands = cur.execute(
        "SELECT player_id, back_number FROM players WHERE player_name=? AND team_id=?",
        (name, team)).fetchall()
    if len(cands) > 1 and back_number is not None:
        narrowed = [c for c in cands if c[1] == back_number]
        if len(narrowed) == 1:
            cands = narrowed
    if len(cands) > 1:
        logger.warning(f"  동명이인 모호({src}): {team} {name} — 건너뜀")
        return "skip"

    if len(cands) == 1:
        pid, db_back = cands[0]
        info = scrape_player_profile(session, pid)
        if info is None:
            logger.warning(f"  {pid} {name}: 프로필 수집 실패({src})")
            return "fail"
        prof_back = info.get("back_number")
        # 로스터 등번호가 DB·최신 프로필 어느 쪽과도 다르면 같은 팀 동명이인
        # 신규 선수일 수 있으므로 본인 확정하지 않고 검색 분기로 내려보낸다
        treat_self = (back_number is None or db_back == back_number
                      or prof_back == back_number or prof_back is None)
        if treat_self:
            if prof_back is None and back_number is not None:
                info["back_number"] = back_number  # 등록 현황 등번호를 보조 값으로 채움
            return "changed" if apply_player_change(con, pid, info, team, src, event_date) \
                else "same"

    # 같은 팀에 (확정) 후보 없음 → 검색으로 식별
    found = search_player(session, name)
    if found is None:
        logger.warning(f"  검색 실패({src}): {team} {name} — 다음 실행에서 재시도")
        return "fail"
    matches = [c for c in found if c.get("P_NM") == name and c.get("T_NM") == team]
    if back_number is not None and len(matches) > 1:
        matches = [c for c in matches if _norm_back(c.get("BACK_NO")) == back_number]
    if len(matches) > 1:
        logger.warning(f"  검색 모호({src}): {team} {name} 후보 {len(matches)}건 — 건너뜀")
        return "skip"

    if not matches:
        # 검색은 성공했지만 해당 팀 후보 없음(검색 인덱스 지연 등) —
        # 현역 팀 내 전 소속 단일 매칭이면 이적으로 처리
        ph = ",".join("?" * len(KBO_TEAMS))
        others = cur.execute(
            f"SELECT player_id FROM players WHERE player_name=? AND team_id IN ({ph})",
            (name, *KBO_TEAMS)).fetchall()
        if len(others) == 1:
            pid = others[0][0]
            info = scrape_player_profile(session, pid)
            if info is None:
                return "fail"
            if apply_player_change(con, pid, info, team, f"{src}+fallback", event_date):
                return "changed"
        logger.warning(f"  매칭 실패({src}): {team} {name} — 건너뜀")
        return "skip"

    pid = str(matches[0]["P_ID"])
    info = scrape_player_profile(session, pid)
    if info is None:
        logger.warning(f"  {pid} {name}: 프로필 수집 실패({src})")
        return "fail"
    if info.get("back_number") is None and back_number is not None:
        info["back_number"] = back_number
    if cur.execute("SELECT 1 FROM players WHERE player_id=?", (pid,)).fetchone():
        return "changed" if apply_player_change(con, pid, info, team, src, event_date) \
            else "same"
    insert_new_player(con, info, team, src, event_date)
    return "new"


def sync_trade_events(con, session, full=False):
    """이동 현황 이벤트를 raw 적재하고, 신규 트리거 이벤트만 선수별로 반영."""
    today = date.today()
    if full:
        months = [(y, 0) for y in (today.year - 1, today.year)]
    else:
        months = [(today.year, today.month)]
        if today.day <= 3:  # 월초에는 전월 막바지 이벤트도 함께
            prev = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
            months.append(prev)

    events = []
    for y, m in months:
        events.extend(fetch_trade_events(session, y, m))
    new_events = store_moves(con, events)
    # API는 최신순 반환 — 그대로 적용하면 다건 이벤트 선수의 옛 상태가 최종 승자가 된다
    new_events.sort(key=lambda e: e["date"])

    stats = {"changed": 0, "new": 0, "same": 0, "skip": 0, "fail": 0}
    for e in new_events:
        if e["section"] not in TRIGGER_SECTIONS or e["team"] not in KBO_TEAMS:
            continue
        name = strip_player_text(e["player"])
        if not name:
            continue
        event_date = e["date"] if ISO_DATE.match(e["date"]) else None
        r = resolve_and_apply(con, session, name, e["team"], f"trade:{e['section']}",
                              event_date=event_date)
        stats[r] += 1
        if r == "fail":
            unstore_move(con, e)  # 일시 오류는 다음 실행에서 재트리거
        time.sleep(0.3)
    logger.info(f"[3/4] 이동 이벤트: 수집 {len(events)} / 신규 {len(new_events)} / 반영 {stats}")
    return stats


def sync_register_all(con, session):
    """1군 등록 현황과 players를 대조해 신규·팀/등번호 변경을 반영."""
    entries = fetch_register_all(session)
    if not entries:
        logger.warning("[4/4] 등록 현황: 수집 실패 또는 0건")
        return {}
    cur = con.cursor()
    stats = {"changed": 0, "new": 0, "same": 0, "skip": 0, "fail": 0, "ok": 0}
    for team, _pos, name, back_no in entries:
        rows = cur.execute(
            "SELECT player_id, back_number FROM players WHERE player_name=? AND team_id=?",
            (name, team)).fetchall()
        if any(r[1] == back_no for r in rows):
            stats["ok"] += 1  # 이름·팀·등번호 일치 행 존재 — 변경 없음
            continue
        r = resolve_and_apply(con, session, name, team, "register_all", back_number=back_no)
        stats[r] += 1
        time.sleep(0.3)
    logger.info(f"[4/4] 등록 현황: 항목 {len(entries)} / 반영 {stats}")
    return stats


def main():
    ap = argparse.ArgumentParser(description="선수 정보 레지스트리 동기화")
    ap.add_argument("--full", action="store_true",
                    help="초기 백필: 이동 현황을 작년~올해 전체로 수집")
    args = ap.parse_args()

    logger.info(f"=== player_registry_sync 시작 (full={args.full}) ===")
    con = sqlite3.connect(DB_PATH, timeout=60)
    con.execute("PRAGMA journal_mode = WAL")
    try:
        ensure_tables(con)
        session = make_session()
        for step in (lambda: sync_missing_from_stats(con, session),
                     lambda: sync_missing_from_pbp(con, session),
                     lambda: sync_trade_events(con, session, full=args.full),
                     lambda: sync_register_all(con, session)):
            try:
                step()
            except Exception:
                logger.exception("단계 실패 — 다음 단계 계속")
    finally:
        con.close()
    logger.info("=== player_registry_sync 완료 ===")


if __name__ == "__main__":
    main()
