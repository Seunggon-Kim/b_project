# -*- coding: utf-8 -*-
"""선수 뉴스 정확도 필터.

구글 뉴스 검색은 질의어를 느슨하게 맞춥니다. `KIA 타이거즈 김도영 야구` 로
물어도 선수 이름이 제목에 없는 기사, 같은 이름의 다른 종목 선수 기사가
섞여 옵니다. 실측에서 여덟 건 중 두 건이 그랬습니다.

여기서 거르는 기준은 세 가지입니다.

1. 선수 이름이 제목이나 설명에 실제로 들어 있어야 합니다.
2. 다른 종목 낱말이 있는데 야구 낱말이 하나도 없으면 버립니다.
3. 이름이 겹치는 선수(585명 중 20조)는 팀 표시가 있어야 인정합니다.

3번을 모든 선수에 적용하지 않는 이유가 있습니다. 은퇴하거나 이적한 선수는
등록된 소속팀이 기사에 나오지 않습니다. 박병호가 삼성 소속으로 등록돼 있어도
키움 은퇴식 기사가 나오는 식입니다. 팀을 강제하면 맞는 기사를 버립니다.
"""

# 야구 맥락을 알려 주는 낱말입니다. 다른 종목 낱말과 겹치면 안 됩니다.
BASEBALL_WORDS = (
    "야구", "KBO", "프로야구", "구단", "홈런", "타율", "타점", "출루",
    "투수", "타자", "포수", "내야수", "외야수", "선발", "불펜", "마무리",
    "이닝", "삼진", "볼넷", "안타", "도루", "세이브", "평균자책",
    "타석", "등판", "완봉", "완투", "구속", "구종", "타선", "덕아웃",
    "1군", "2군", "퓨처스", "올스타", "포스트시즌", "한국시리즈",
)

# 다른 종목 낱말입니다. 이것만 있고 야구 낱말이 없으면 남의 기사입니다.
OTHER_SPORT_WORDS = (
    "축구", "골프", "배구", "농구", "테니스", "핸드볼", "탁구", "씨름",
    "복싱", "격투기", "UFC", "e스포츠", "롤드컵", "배드민턴", "펜싱",
    "양궁", "수영", "육상", "체조", "스키", "스케이팅", "컬링",
)


# 언론사가 아닌 출처입니다. 구글 뉴스에 블로그와 카페 글이 섞여 들어옵니다.
# 실측에서 30건 중 2건이 `Naver Blog` 였습니다. 목록에 없는 이름은 통과시킵니다.
# 지역지와 전문지를 다 열거할 수 없어, 막을 것만 적는 방식이 안전합니다.
NON_PRESS_SOURCES = (
    "naver blog", "네이버 블로그", "블로그", "blog",
    "tistory", "티스토리", "brunch", "브런치",
    "cafe", "카페", "네이버 포스트", "naver post",
    "youtube", "유튜브", "namu.wiki", "나무위키",
)


def is_news_source(press):
    """출처가 언론사인지 봅니다. 블로그·카페면 거짓입니다.

    출처를 못 읽어 빈 문자열인 경우는 통과시킵니다. 모르는 것과 블로그인 것은
    다릅니다.
    """
    if not press:
        return True
    lowered = str(press).strip().lower()
    return not any(bad in lowered for bad in NON_PRESS_SOURCES)


def clean_title(raw):
    """구글 뉴스 제목에서 끝의 ' - 언론사' 를 떼어 (본문, 언론사) 로 나눕니다.

    제목 안에 하이픈이 여러 번 나올 수 있어 마지막 것만 자릅니다.
    원본 api/main.py 의 `rsplit(" - ", 1)` 과 같은 동작입니다.
    """
    text = (raw or "").strip()
    cut = text.rfind(" - ")
    if cut == -1:
        return text, ""
    return text[:cut].strip(), text[cut + 3:].strip()


def team_tokens(team_id, team_name):
    """기사에서 팀을 알아볼 만한 문자열들을 모읍니다.

    `LG` 와 `LG 트윈스` 뿐 아니라 `트윈스` 단독으로도 쓰이므로 함께 넣습니다.
    """
    tokens = set()
    if team_id:
        tokens.add(team_id.strip())
    if team_name:
        name = team_name.strip()
        tokens.add(name)
        # 'LG 트윈스' -> '트윈스'. 구단 애칭만 쓰는 제목이 흔합니다.
        parts = name.split()
        if len(parts) > 1:
            tokens.add(parts[-1])
    return {t for t in tokens if t}


def _has_any(text, words):
    return any(w in text for w in words)


def is_relevant(title, description, player_name, tokens, ambiguous):
    """이 기사가 그 선수의 것인지 판정합니다.

    (통과 여부, 사유) 를 돌려줍니다. 사유는 걸러진 까닭을 사람이 읽기 위한
    것으로, 수집 로그에 남겨 나중에 기준을 손볼 때 씁니다.
    """
    text = "%s %s" % (title or "", description or "")

    if not player_name or player_name not in text:
        return False, "이름이 없습니다"

    if _has_any(text, OTHER_SPORT_WORDS) and not _has_any(text, BASEBALL_WORDS):
        return False, "다른 종목 기사로 보입니다"

    if ambiguous:
        # 기사가 팀 약칭을 소문자로 쓰는 일이 흔합니다. 'kt 김민수' 같은
        # 맞는 기사를 대소문자 때문에 버리지 않도록 양쪽을 낮춰 비교합니다.
        # 영문 약칭을 쓰는 구단이 KT·KIA·LG·SSG·NC 다섯이라 영향이 큽니다.
        lowered = text.lower()
        if not any(t.lower() in lowered for t in tokens):
            return False, "이름이 겹치는 선수인데 팀 표시가 없습니다"

    return True, "통과"


def dedupe(items):
    """같은 기사를 한 번만 남깁니다. 들어온 순서를 유지합니다.

    통신사 기사를 여러 매체가 그대로 싣는 일이 잦아 링크뿐 아니라 제목으로도
    거릅니다.
    """
    seen_link = set()
    seen_title = set()
    out = []
    for it in items:
        link = (it.get("link") or "").strip()
        title = (it.get("title") or "").strip()
        if link and link in seen_link:
            continue
        if title and title in seen_title:
            continue
        if link:
            seen_link.add(link)
        if title:
            seen_title.add(title)
        out.append(it)
    return out
