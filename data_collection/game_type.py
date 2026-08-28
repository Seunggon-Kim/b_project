# -*- coding: utf-8 -*-
"""경기가 정규시즌인지 포스트시즌인지 판정합니다.

## 전에는 날짜로 갈랐습니다

`PLAYOFF_START` 라는 표가 있었습니다. 시즌마다 "몇 월 며칠부터
포스트시즌" 을 손으로 적어 두고 그 날짜와 비교했습니다.

세 가지가 문제였습니다.

첫째, 매년 사람이 넣어야 합니다. 안 넣으면 10월부터 적재가 멈춥니다.
둘째, 일정이 나오기 전에는 넣을 값을 모릅니다. 우천 순연으로 정규시즌이
밀리면 값이 또 바뀝니다.
셋째, **실제로 틀렸습니다.** 아래 아홉 경기가 정규시즌으로 들어가
있었습니다.

    2016-10-10, 10-11  와일드카드   LG vs KIA
    2016-10-13 ~ 10-17 준플레이오프 LG vs 넥센
    2017-10-05         와일드카드   NC vs SK
    2017-10-08, 10-09  준플레이오프 NC vs 롯데

## 지금은 경기 ID 로 봅니다

정규시즌 경기 ID 는 날짜로 시작합니다(`20260415...`). 포스트시즌은
시리즈 코드로 시작합니다. 추측이 아니라 원천이 그렇게 줍니다.

2008~2025 열여덟 시즌을 전부 훑어 네이버 `roundCode` 와 맞춰
확인했습니다.

    3333  kbo_ps_sp   준플레이오프
    4444  kbo_ps_wd   와일드카드
    5555  kbo_ps_po   플레이오프
    7777  kbo_ps_ks   한국시리즈
    6666  kbo_p       **정규시즌**
    9999  (올스타전)   집계 대상이 아닙니다

## 6666 을 조심하십시오

`6666` 은 순위결정전입니다. 2021년 1위 결정전(KT-삼성)과 2024년 5위
결정전(SSG-KT) 두 경기입니다. 네이버가 `kbo_p` 로 주고, KBO 도 이
경기를 정규시즌 기록에 넣습니다. 접두어 모양만 보고 포스트시즌으로
묶으면 안 됩니다.

이 파일이 판정 규칙의 유일한 자리입니다. 두 곳에 복사해 두고 어긋나지
않기를 바라던 예전 방식으로 돌아가지 마십시오.
"""

# 포스트시즌 시리즈 코드입니다. 6666(순위결정전)은 여기 없습니다.
POSTSEASON_PREFIXES = ("3333", "4444", "5555", "7777")

# 정규시즌으로 보는 비날짜 접두어입니다. 순위결정전입니다.
REGULAR_PREFIXES = ("6666",)

# 올스타전입니다. 팀이 '나눔'·'드림' 이라 teams 에 없고 구단 성적도
# 아닙니다. 넣으면 FK 위반으로 적재가 통째로 막힙니다.
SKIP_PREFIXES = ("9999",)

REGULAR = "정규시즌"
POSTSEASON = "포스트시즌"

# 네이버가 주는 `roundCode` 입니다. **경기 ID 보다 정확합니다.**
#
# 경기 ID 로는 시범경기를 못 걸러냅니다. 시범경기도 정규시즌처럼
# 날짜로 시작하기 때문입니다(`20130309HHHT0`). 실제로 시범경기 53건이
# 정규시즌으로 들어가 2013 이 팀당 128경기가 아니라 139경기로
# 보였습니다.
#
#     kbo_r       정규시즌        2008~2026 의 기본값입니다
#     kbo_p       정규시즌        2020 과 순위결정전이 이 값입니다
#     kbo_ps_wd   와일드카드      \
#     kbo_ps_sp   준플레이오프     |  포스트시즌
#     kbo_ps_po   플레이오프       |
#     kbo_ps_ks   한국시리즈      /
#     kbo_e       시범경기        집계 대상이 아닙니다
#
# **정규시즌 값이 하나가 아닙니다.** `kbo_p` 만 정규시즌으로 보게
# 짰다가 열아홉 시즌을 훑어 보고 알았습니다. 그대로 뒀으면 정규시즌
# 경기를 거의 다 버렸을 것입니다. 그래서 아래 `classify_game` 은
# 모르는 값을 만나면 버리지 않고 경기 ID 판정으로 넘깁니다.
ROUND_REGULAR = ("kbo_r", "kbo_p")
ROUND_POSTSEASON_PREFIX = "kbo_ps_"
ROUND_EXHIBITION = "kbo_e"


def prefix(game_id):
    """경기 ID 앞 네 자리입니다. 값이 이상하면 빈 문자열입니다."""
    s = str(game_id or "").strip()
    return s[:4] if len(s) >= 4 else ""


def is_skippable(game_id):
    """올스타전처럼 구단 성적이 아닌 경기입니다."""
    return prefix(game_id) in SKIP_PREFIXES


def classify(game_id):
    """`정규시즌` 또는 `포스트시즌` 을 돌려줍니다.

    모르는 접두어는 정규시즌으로 둡니다. 포스트시즌 코드는 위 다섯
    개로 닫혀 있고, 새 값이 생기면 그때 여기에 적는 편이 낫습니다.
    잘못 포스트시즌으로 묶으면 순위표에서 경기가 빠집니다.

    **시범경기는 못 걸러냅니다.** 시범경기도 날짜로 시작합니다.
    `roundCode` 를 쓸 수 있으면 `classify_game` 을 쓰십시오.
    """
    return POSTSEASON if prefix(game_id) in POSTSEASON_PREFIXES else REGULAR


def classify_game(game_id, round_code=None):
    """`roundCode` 가 있으면 그걸 믿고, 없으면 경기 ID 로 봅니다.

    집계 대상이 아니면 `None` 입니다. 시범경기(`kbo_e`)와 올스타전이
    여기 걸립니다.

    네이버 API 를 부르는 쪽은 `roundCode` 를 이미 받고 있으므로 이걸
    쓰십시오. PBP CSV 에서 도출하는 쪽은 그 값이 없어 `classify` 를
    씁니다(크롤러가 개막일부터 받아 시범경기가 애초에 안 들어옵니다).
    """
    rc = str(round_code or "").strip()
    if rc == ROUND_EXHIBITION:
        return None                      # 시범경기
    if rc.startswith(ROUND_POSTSEASON_PREFIX):
        return POSTSEASON
    if is_skippable(game_id):
        return None                      # 올스타전
    # `kbo_r`·`kbo_p` 는 물론이고 **모르는 값도** 여기로 옵니다.
    # 버리지 않고 경기 ID 로 판정합니다. 모른다고 버리면 새 코드가
    # 하나 생겼을 때 시즌 전체가 조용히 사라집니다.
    return classify(game_id)
