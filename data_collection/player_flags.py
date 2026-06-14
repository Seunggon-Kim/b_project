# -*- coding: utf-8 -*-
"""선수 분류 플래그 도출 (국적 / 외국인 / 아시아쿼터).

players.career 의 선두 토큰(국가명)으로 외국인·국적을 도출한다.
- 외국인 career 는 국적으로 시작한다.  예) "미국 California State(대)", "도미니카-LG"
- 한국 선수 career 는 한국 학교 진학(초-중-고[-대])로 시작한다.
- 아시아쿼터는 외국인의 하위 분류(시즌당 KBO 공시 기준 현 보유자)이며 수동 시드로 관리한다.
- is_active(현역)는 career 가 아니라 현 로스터 기준이므로 본 모듈이 아닌
  player_registry_sync.refresh_is_active() 에서 산출한다.

backfill_player_flags.py 와 player_registry_sync.py / player_info_scraper.py 의
UPSERT 가 공통으로 import 한다 (단일 진실 소스).
"""

import re

# career 선두 토큰으로 외국인을 식별하는 국가명 집합 (KBO 등록 외국인/아시아쿼터 출신국)
FOREIGN_COUNTRIES = {
    "도미니카", "도미니카공화국", "미국", "베네수엘라", "쿠바", "캐나다",
    "푸에르토리코", "푸에르토", "파나마", "멕시코", "콜롬비아", "니카라과",
    "네덜란드", "큐라소", "독일", "브라질", "아루바", "자메이카", "바하마",
    "일본", "대만", "호주", "중국",
}

# career 가 국가명으로 시작하지만 국내 신분인 선수 (재일/재미 교포 등) — 수동 오버라이드
# {player_id: 메모}
KOREAN_OVERRIDES = {
    "50202": "안권수(재일교포, 한국선수)",
}

# career 로 외국인을 식별할 수 없는 선수 (career 가 공란/팀명뿐) — 수동 오버라이드
# {player_id: nationality}.  검토 리스트에서 확정되는 대로 채운다.
FOREIGN_OVERRIDES = {
    "55013": "미국",       # 스티븐슨 (career 공란)
    "51144": "미국",       # 보어 Justin Bour (career 'LG')
    "51714": "베네수엘라",  # 페레즈 (career '한화')
}

# 시즌별 아시아쿼터 현 보유자 (KBO 공시 기준, 시즌당 갱신).
# {player_id: {"name": ..., "nationality": ...}}
ASIA_QUOTA_BY_SEASON = {
    2026: {
        "55348": {"name": "웰스", "nationality": "호주"},
        "56632": {"name": "데일", "nationality": "호주"},
        "56719": {"name": "왕옌청", "nationality": "대만"},
        "56011": {"name": "스기모토", "nationality": "일본"},
        "56348": {"name": "유토", "nationality": "일본"},
        "56415": {"name": "미야지", "nationality": "일본"},
        "56548": {"name": "쿄야마", "nationality": "일본"},
        "56911": {"name": "토다", "nationality": "일본"},
        "56212": {"name": "타카다", "nationality": "일본"},
        "56823": {"name": "타케다", "nationality": "일본"},
    },
}


def lead_token(career):
    """career 선두 토큰 반환 (공백/하이픈 기준). 예) '도미니카-LG' -> '도미니카'."""
    if not career:
        return ""
    return re.split(r"[\s\-]+", career.strip())[0]


def detect_nationality(career):
    """career 가 국가명으로 시작하면 그 국가명, 아니면 None."""
    tok = lead_token(career)
    return tok if tok in FOREIGN_COUNTRIES else None


def classify_player(player_id, career, season=2026):
    """(nationality, is_foreign, player_type) 반환.

    nationality: '대한민국' | 국가명 | None(외국인이나 국적 미상 → 검토 대상)
    is_foreign : 0 | 1
    player_type: '국내' | '외국인' | '아시아쿼터'
    """
    pid = str(player_id)
    quota = ASIA_QUOTA_BY_SEASON.get(season, {})
    nat = detect_nationality(career)

    # 1) 재일/재미 교포 등 국내 오버라이드 (career 가 국가명으로 시작해도 국내)
    if pid in KOREAN_OVERRIDES:
        return ("대한민국", 0, "국내")

    # 2) 현 시즌 아시아쿼터 보유자 (외국인의 하위 분류)
    if pid in quota:
        return (nat or quota[pid].get("nationality"), 1, "아시아쿼터")

    # 3) career 선두 국가명 → 외국인 + 국적
    if nat:
        return (nat, 1, "외국인")

    # 4) career 가 공란/팀명뿐인 외국인 수동 오버라이드
    if pid in FOREIGN_OVERRIDES:
        return (FOREIGN_OVERRIDES[pid], 1, "외국인")

    # (라틴 문자 휴리스틱은 한국 선수 career 의 팀코드 KT/LG/SSG/NC/KIA 를 외국인으로
    #  오탐하므로 쓰지 않는다. career 가 공란/팀명뿐인 잔여 외국인은 is_review_suspect 로
    #  surface 한 뒤 FOREIGN_OVERRIDES 에 등록한다.)

    # 5) 그 외 국내
    return ("대한민국", 0, "국내")


# career 에 한국 학교 진학 흔적이 있으면 명백한 국내 (검토 리스트 필터용)
_KR_SCHOOL = re.compile(r"초|중|고|대")


def is_review_suspect(player_id, career, season=2026):
    """국내로 분류됐으나 career 에 한국 학교 흔적이 없어 외국인 가능성이 있는 경우 True."""
    _, is_foreign, _ = classify_player(player_id, career, season)
    if is_foreign:
        return False
    return not (career and _KR_SCHOOL.search(career))
