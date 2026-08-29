# -*- coding: utf-8 -*-
"""네이버 gameId 에서 시즌 연도와 저장 파일명을 얻습니다.

## 형식이 셋입니다

    20080418SKOB0        정규시즌          13자, 앞 4자리가 연도
    33331008SSLT0        ~2015 포스트시즌  13자, **연도가 없습니다**
    33331013LGWO02016    2016~ 포스트시즌  17자, 뒤 4자리가 연도

앞 4자리는 경기 종류입니다.

    3333 준플레이오프   4444 와일드카드   5555 플레이오프
    6666 순위결정전     7777 한국시리즈   8888 이벤트   9999 올스타

**6666(순위결정전)은 포스트시즌이 아니라 정규시즌입니다.** 8888 과
9999 는 games 에 없어서 넣으면 FK 가 깨집니다. 여기서 None 을 돌려
부르는 쪽이 거르게 합니다.

## 왜 이 파일이 생겼나

크롤러가 연도를 `gid[-4:]` 로만 얻었습니다. 13자 포스트시즌에서는
'SLT0' 이 나와 `int()` 가 터졌고, 그 예외를 `continue` 로 삼켜
**2015년까지의 포스트시즌이 통째로 조용히 빠졌습니다.** 2008~2014 만
103경기입니다. 로그도 남지 않아 오래 몰랐습니다.

13자에서 연도를 아는 길은 하나뿐입니다. 캘린더를 돌 때 이미 알던
연도를 같이 들고 오는 것입니다. 그래서 `fallback_year` 가 있습니다.

download.py 와 game_parse.py 가 함께 씁니다. 두 파일이 서로를
import 하는 사이라 규칙을 한쪽에 두면 순환이 됩니다. 그래서 아무것도
import 하지 않는 이 파일에 둡니다.
"""

# games 에 없는 경기입니다. 넣으면 FK 가 깨집니다.
NON_LEAGUE_PREFIXES = ('8888', '9999')


def game_id_year(game_id, fallback_year=None):
    """시즌 연도입니다. 알 수 없으면 None 입니다.

    None 은 '버려라' 가 아니라 '모른다' 입니다. 다만 8888·9999 는
    확실히 빼야 하는 경기라 같은 None 을 씁니다.

    gameId 안에 연도가 있으면 그 값이 언제나 정본입니다.
    `fallback_year` 는 gameId 가 연도를 안 담은 13자 포스트시즌에만
    쓰입니다.
    """
    gid = str(game_id or '')
    if len(gid) < 8:
        return None

    head = gid[:4]
    if not head.isdigit():
        return None
    if head in NON_LEAGUE_PREFIXES:
        return None

    n = int(head)
    if n < 3000:
        # 정규시즌입니다. 앞 4자리가 연도입니다.
        return n

    # 포스트시즌·순위결정전입니다. 2016년부터 뒤에 연도가 붙습니다.
    tail = gid[-4:]
    if len(gid) > 13 and tail.isdigit():
        return int(tail)

    # 2015년까지입니다. gameId 로는 알 수 없습니다.
    return int(fallback_year) if fallback_year else None


def save_stem(game_id, year):
    """저장 파일명입니다(확장자 없음).

    **CSV 안의 `gameID` 컬럼과 다릅니다.** 파일명은 날짜로 고르려고
    연도를 앞에 붙인 값이고, gameID 는 네이버 원본 그대로입니다.

        파일명   20081008SSLT0.csv
        gameID   33331008SSLT0

    games 와 play_by_play 는 원본 gameId 로 이어집니다. 파일명을
    조인 키로 쓰면 포스트시즌에서 어긋납니다.

    앞 8자리가 늘 경기 날짜(YYYYMMDD)가 되게 맞춥니다. 2016년 이후
    포스트시즌이 이미 이 규칙으로 저장돼 있어 그대로 따릅니다.
    """
    gid = str(game_id)
    return '%d%s' % (int(year), gid[4:])
