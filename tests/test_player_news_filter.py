# -*- coding: utf-8 -*-
"""선수 뉴스 정확도 필터 테스트.

구글 뉴스 검색은 질의어를 느슨하게 맞춥니다. 선수 이름이 제목에 없는 기사,
동명이인 기사, 다른 종목 기사가 섞여 들어옵니다. 이 필터가 그것을 걸러
"이 선수의 뉴스"만 남기는 것이 목적입니다.
"""
import pytest

from data_collection.player_news_filter import (
    BASEBALL_WORDS,
    NON_PRESS_SOURCES,
    OTHER_SPORT_WORDS,
    clean_title,
    dedupe,
    is_news_source,
    is_relevant,
    team_tokens,
)


# --- 제목 정리 ---

def test_clean_title_strips_press_suffix():
    """구글 뉴스 제목은 끝에 ' - 언론사' 가 붙습니다."""
    assert clean_title("김도영 35호 홈런 - 연합뉴스") == ("김도영 35호 홈런", "연합뉴스")


def test_clean_title_keeps_earlier_hyphens():
    body, press = clean_title("가을야구 - 그리고 - 다음 시즌 - 스포츠조선")
    assert body == "가을야구 - 그리고 - 다음 시즌"
    assert press == "스포츠조선"


def test_clean_title_without_suffix():
    assert clean_title("하이픈없는제목") == ("하이픈없는제목", "")


# --- 팀 토큰 ---

def test_team_tokens_includes_short_and_full_name():
    tokens = team_tokens("LG", "LG 트윈스")
    assert "LG" in tokens
    assert "LG 트윈스" in tokens
    assert "트윈스" in tokens


def test_team_tokens_handles_missing_full_name():
    assert team_tokens("KT", None) == {"KT"}


def test_team_tokens_ignores_blank():
    assert team_tokens("", "") == set()


# --- 핵심 판정 ---

def test_accepts_when_name_in_title():
    ok, why = is_relevant("홈런 1위 KIA 김도영, 35호 홈런 발사", "",
                          "김도영", {"KIA", "타이거즈"}, ambiguous=False)
    assert ok, why


def test_rejects_when_name_missing_everywhere():
    """제목과 설명 어디에도 이름이 없으면 그 선수 기사라고 볼 수 없습니다."""
    ok, why = is_relevant("30홀드 이후 기나긴 부진 어떻게 이겨냈나", "",
                          "김민수", {"KT", "위즈"}, ambiguous=False)
    assert not ok
    assert "이름" in why


def test_accepts_when_name_only_in_description():
    ok, why = is_relevant("KT 불펜 상승세", "김민수가 2이닝 무실점으로 막았다",
                          "김민수", {"KT"}, ambiguous=False)
    assert ok, why


def test_rejects_other_sport_without_baseball_context():
    """같은 이름의 축구 선수 기사를 걸러 냅니다."""
    ok, why = is_relevant("축구 대표팀 김민수, 유럽 진출 확정", "",
                          "김민수", {"KT"}, ambiguous=False)
    assert not ok
    assert "종목" in why


def test_accepts_other_sport_word_when_baseball_context_present():
    """'농구장 같은 열기' 처럼 비유로 섞인 경우까지 버리면 과잉입니다."""
    ok, why = is_relevant("김민수 역투, 농구장 같은 열기의 잠실 야구장", "",
                          "김민수", {"KT"}, ambiguous=False)
    assert ok, why


# --- 동명이인 ---

def test_ambiguous_requires_team_token():
    """이름이 겹치는 선수는 팀 표시가 있어야 그 선수 기사로 인정합니다."""
    ok, why = is_relevant("김민수, 시즌 첫 홈런", "",
                          "김민수", {"LG", "트윈스"}, ambiguous=True)
    assert not ok
    assert "팀" in why


def test_ambiguous_accepts_with_team_token():
    ok, why = is_relevant("LG 김민수, 시즌 첫 홈런", "",
                          "김민수", {"LG", "트윈스"}, ambiguous=True)
    assert ok, why


def test_ambiguous_accepts_team_token_in_description():
    ok, why = is_relevant("김민수, 시즌 첫 홈런", "트윈스가 5연승을 달렸다",
                          "김민수", {"LG", "트윈스"}, ambiguous=True)
    assert ok, why


def test_ambiguous_team_token_is_case_insensitive():
    """기사가 팀 이름을 소문자로 쓰는 일이 흔합니다.

    실측에서 '프로야구 kt 어쩌나…핵심 불펜 주권·김민수 부상 이탈' 같은
    맞는 기사가 대소문자 때문에 버려졌습니다. KT·KIA·LG·SSG·NC 처럼 영문
    약칭을 쓰는 구단이 다섯이라 영향이 큽니다.
    """
    ok, why = is_relevant("프로야구 kt 어쩌나, 김민수 부상 이탈", "",
                          "김민수", {"KT", "위즈"}, ambiguous=True)
    assert ok, why


def test_ambiguous_team_token_matches_upper_in_text():
    ok, why = is_relevant("KT 김민수 역투", "",
                          "김민수", {"kt", "위즈"}, ambiguous=True)
    assert ok, why


def test_unambiguous_does_not_require_team():
    """이름이 유일하면 팀을 요구하지 않습니다.

    은퇴·이적 선수는 현 소속팀이 기사에 안 나옵니다. 박병호가 삼성 소속으로
    등록돼 있어도 키움 은퇴식 기사가 나오는 식입니다. 팀을 강제하면 오히려
    맞는 기사를 버립니다.
    """
    ok, why = is_relevant("박병호 은퇴식, 키움에서 열린다", "",
                          "박병호", {"삼성", "라이온즈"}, ambiguous=False)
    assert ok, why


# --- 출처가 언론사인가 ---

def test_rejects_blog_source():
    """구글 뉴스에 블로그가 섞여 들어옵니다. 실측에서 30건 중 2건이었습니다."""
    assert not is_news_source("Naver Blog")
    assert not is_news_source("네이버 블로그")


def test_rejects_cafe_and_tistory():
    assert not is_news_source("티스토리")
    assert not is_news_source("Daum 카페")


def test_accepts_real_press():
    for p in ("연합뉴스", "스포츠조선", "중앙일보", "뉴시스", "OSEN", "SPOTV NEWS"):
        assert is_news_source(p), p


def test_accepts_unknown_source():
    """모르는 이름은 통과시킵니다. 지역지·전문지를 다 열거할 수 없습니다."""
    assert is_news_source("처음보는스포츠신문")


def test_blank_source_passes():
    """출처를 못 읽은 것과 블로그인 것은 다릅니다."""
    assert is_news_source("")
    assert is_news_source(None)


def test_non_press_list_is_lowercase_comparable():
    """대소문자가 섞여 들어와도 걸러야 합니다."""
    assert not is_news_source("NAVER BLOG")
    assert not is_news_source("naver blog")


# --- 중복 제거 ---

def test_dedupe_by_link():
    items = [
        {"title": "A", "link": "http://x/1", "press": "가"},
        {"title": "B", "link": "http://x/1", "press": "나"},
        {"title": "C", "link": "http://x/2", "press": "다"},
    ]
    assert [i["title"] for i in dedupe(items)] == ["A", "C"]


def test_dedupe_by_title_across_press():
    """통신사 기사를 여러 매체가 그대로 싣는 경우가 많습니다."""
    items = [
        {"title": "같은 제목", "link": "http://x/1", "press": "가"},
        {"title": "같은 제목", "link": "http://x/2", "press": "나"},
    ]
    assert len(dedupe(items)) == 1


def test_dedupe_keeps_order():
    items = [
        {"title": "1", "link": "a", "press": ""},
        {"title": "2", "link": "b", "press": ""},
        {"title": "3", "link": "c", "press": ""},
    ]
    assert [i["title"] for i in dedupe(items)] == ["1", "2", "3"]


# --- 낱말 목록 ---

def test_word_lists_do_not_overlap():
    """같은 낱말이 양쪽에 있으면 판정이 뒤집힙니다."""
    assert not (set(BASEBALL_WORDS) & set(OTHER_SPORT_WORDS))


def test_baseball_words_cover_core_terms():
    for w in ("야구", "KBO", "홈런", "투수", "타자"):
        assert w in BASEBALL_WORDS


@pytest.mark.parametrize("word", ["축구", "골프", "배구", "농구"])
def test_other_sport_words_cover_major_sports(word):
    assert word in OTHER_SPORT_WORDS
