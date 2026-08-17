# -*- coding: utf-8 -*-
from migration.golden_compare import compare_values, is_live_path, shape_of


def test_identical_returns_no_difference():
    assert compare_values({"a": 1}, {"a": 1}) == []


def test_float_within_tolerance_is_same():
    assert compare_values({"a": 0.1 + 0.2}, {"a": 0.3}) == []


def test_float_beyond_tolerance_differs():
    diffs = compare_values({"a": 1.0}, {"a": 1.001})
    assert len(diffs) == 1
    assert "a" in diffs[0]


def test_int_and_string_are_different():
    """player_id 는 타입까지 같아야 합니다."""
    diffs = compare_values({"player_id": 1001}, {"player_id": "1001"})
    assert len(diffs) == 1


def test_int_and_float_are_different():
    """JS 이식에서 정수가 실수로 새어 나오는 것을 잡습니다."""
    diffs = compare_values({"n": 1}, {"n": 1.0})
    assert len(diffs) == 1


def test_null_and_empty_string_are_different():
    diffs = compare_values({"a": None}, {"a": ""})
    assert len(diffs) == 1


def test_null_and_zero_are_different():
    diffs = compare_values({"a": None}, {"a": 0})
    assert len(diffs) == 1


def test_missing_key_is_reported():
    diffs = compare_values({"a": 1, "b": 2}, {"a": 1})
    assert len(diffs) == 1
    assert "b" in diffs[0]


def test_extra_key_is_reported():
    diffs = compare_values({"a": 1}, {"a": 1, "b": 2})
    assert len(diffs) == 1
    assert "b" in diffs[0]


def test_list_order_matters():
    diffs = compare_values([1, 2], [2, 1])
    assert diffs != []


def test_list_length_difference_is_reported():
    diffs = compare_values([1, 2], [1])
    assert len(diffs) == 1


def test_nested_path_appears_in_message():
    diffs = compare_values({"rows": [{"x": 1}]}, {"rows": [{"x": 2}]})
    assert "rows[0].x" in diffs[0]


def test_bool_and_int_are_different():
    diffs = compare_values({"a": True}, {"a": 1})
    assert len(diffs) == 1


# --- 라이브 응답: 값이 아니라 구조만 비교합니다 ---

def test_is_live_path_flags_external_endpoints():
    """네이버에서 실시간으로 받아 오는 응답은 두 번 부르면 값이 달라집니다."""
    assert is_live_path("standings")
    assert is_live_path("schedule_date_20250401")
    assert is_live_path("players_50030_news")
    assert not is_live_path("wrc_leaderboard_season_2025")


def test_shape_of_replaces_scalars_with_type_names():
    assert shape_of({"a": 1, "b": "x"}) == {"a": "int", "b": "str"}


def test_shape_of_keeps_list_element_shape_only_once():
    """길이가 달라도 원소 구조가 같으면 같다고 봅니다."""
    assert shape_of([{"a": 1}, {"a": 2}]) == shape_of([{"a": 9}])


def test_live_responses_match_when_structure_is_same():
    a = {"count": 5, "games": [{"home": "LG", "score": 3}]}
    b = {"count": 9, "games": [{"home": "KT", "score": 7},
                               {"home": "NC", "score": 1}]}
    assert compare_values(a, b, structural=True) == []


def test_live_responses_still_catch_structural_change():
    a = {"count": 5, "games": [{"home": "LG"}]}
    b = {"count": 5, "games": [{"homeTeam": "LG"}]}
    assert compare_values(a, b, structural=True) != []


def test_live_responses_catch_type_change():
    """숫자가 문자열로 바뀌는 이식 사고는 구조 비교로도 잡힙니다."""
    a = {"count": 5}
    b = {"count": "5"}
    assert compare_values(a, b, structural=True) != []
