# -*- coding: utf-8 -*-
"""수집 스크립트의 RSS 파싱 테스트.

파싱은 원래 Worker(JS)에 있었으나, 구글이 Cloudflare 엣지를 막아 수집을
GitHub Actions 로 옮기면서 여기로 왔습니다.
"""
from data_collection.collect_player_news import parse_items, sql_literal

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>채널 제목입니다</title>
  <item>
    <title>김도영 35호 홈런 - 연합뉴스</title>
    <link>https://example.com/a</link>
    <source url="https://yna.co.kr">연합뉴스</source>
    <pubDate>Sat, 16 Aug 2026 09:00:00 GMT</pubDate>
  </item>
  <item>
    <title>제목에 하이픈 - 이 - 여럿 - 매일경제</title>
    <link>https://example.com/b</link>
  </item>
  <item>
    <title><![CDATA[대괄호 제목 - 스포츠조선]]></title>
    <link>https://example.com/c</link>
  </item>
</channel></rss>"""


def test_parses_every_item():
    assert len(parse_items(RSS)) == 3


def test_skips_channel_title():
    titles = [i["title"] for i in parse_items(RSS)]
    assert "채널 제목입니다" not in titles


def test_strips_press_suffix_from_title():
    assert parse_items(RSS)[0]["title"] == "김도영 35호 홈런"


def test_keeps_earlier_hyphens():
    assert parse_items(RSS)[1]["title"] == "제목에 하이픈 - 이 - 여럿"


def test_reads_cdata_title():
    assert parse_items(RSS)[2]["title"] == "대괄호 제목"


def test_prefers_source_tag_for_press():
    """<source> 가 있으면 제목 꼬리보다 그쪽이 정확합니다."""
    assert parse_items(RSS)[0]["press"] == "연합뉴스"


def test_falls_back_to_title_suffix_for_press():
    assert parse_items(RSS)[1]["press"] == "매일경제"


def test_reads_link_and_pubdate():
    first = parse_items(RSS)[0]
    assert first["link"] == "https://example.com/a"
    assert first["pub_date"] == "Sat, 16 Aug 2026 09:00:00 GMT"


def test_missing_pubdate_is_empty():
    assert parse_items(RSS)[1]["pub_date"] == ""


def test_empty_feed_returns_empty_list():
    assert parse_items("<rss><channel></channel></rss>") == []


def test_sql_literal_escapes_quote():
    """기사 제목에 작은따옴표가 흔합니다. '김도영 시즌 35호포' 같은 것들입니다."""
    assert sql_literal("'김도영' 35호") == "'''김도영'' 35호'"


def test_sql_literal_handles_none():
    assert sql_literal(None) == "NULL"


def test_sql_literal_wraps_numbers_as_text():
    # rank 는 정수로 넣지만 이 함수는 문자열로 감쌉니다. SQLite 가 정수
    # 컬럼에 넣을 때 알아서 변환하므로 문제되지 않습니다.
    assert sql_literal(3) == "'3'"
