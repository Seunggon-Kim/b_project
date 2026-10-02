import sqlite3

import pytest

from migration.mysql import typemap as tm


def _profile(values, decl="TEXT", column="c"):
    con = sqlite3.connect(":memory:")
    con.execute('CREATE TABLE t ("%s" %s)' % (column, decl))
    con.executemany("INSERT INTO t VALUES (?)", [(v,) for v in values])
    return tm.profile_column(con, "t", column)


def test_profile_counts_empty_text_and_float_style_ids():
    p = _profile(["78513.0", "12", "", None], column="batter_ID")
    assert p["nonnull"] == 3
    assert p["int_texts"] == 2 and p["dotzero"] == 1 and p["empties"] == 1
    assert (p["int_min"], p["int_max"]) == (12, 78513)


def test_player_id_text_column_becomes_unsigned_int():
    p = _profile(["78513.0", "12", ""], column="batter_ID")
    kind = tm.column_kind("batter_ID", "TEXT", p)
    assert kind == "int"
    assert tm.mysql_type(kind, p, column="batter_ID") == "INT UNSIGNED"


def test_player_id_with_names_stays_text():
    p = _profile(["78513", "홍길동"], column="pos_1_id")
    assert tm.column_kind("pos_1_id", "TEXT", p) == "text"


def test_real_column_with_empty_strings_stays_double():
    p = _profile([1.5, "", 2.0], decl="REAL", column="px")
    assert tm.column_kind("px", "REAL", p) == "double"


def test_back_number_text_keeps_leading_zeros():
    p = _profile(["00", "0", "12"], column="back_number")
    kind = tm.column_kind("back_number", "TEXT", p)
    assert kind == "text"
    assert tm.normalize("00", kind) == "00"


def test_game_date_declared_date_but_stored_as_int_stays_int():
    p = _profile([20260930, 20260929], decl="DATE", column="game_date")
    assert tm.column_kind("game_date", "DATE", p) == "int"


def test_text_dates_become_date_and_datetimes_become_datetime():
    p = _profile(["2026-09-30", "2026-09-28"], column="move_date")
    assert tm.column_kind("move_date", "TEXT", p) == "date"
    p = _profile(["2026-09-30 07:31:00"], column="updated_at")
    assert tm.column_kind("updated_at", "TEXT", p) == "datetime"


def test_minutes_only_timestamps_stay_text():
    p = _profile(["2026-10-01 07:31"], column="last_run_at")
    assert tm.column_kind("last_run_at", "TEXT", p) == "text"


def test_int_column_with_other_values_falls_back():
    p = _profile([1, "2.5"], decl="INTEGER", column="n")
    assert tm.column_kind("n", "INTEGER", p) == "double"
    p = _profile([1, "abc"], decl="INTEGER", column="n")
    assert tm.column_kind("n", "INTEGER", p) == "text"


def test_blob_column():
    p = _profile([b"\x89PNG"], decl="BLOB", column="img")
    assert tm.column_kind("img", "BLOB", p) == "blob"
    assert tm.mysql_type("blob", p) == "MEDIUMBLOB"


def test_varchar_steps_and_key_limit():
    p = tm.new_profile()
    p["max_len"] = 5
    assert tm.mysql_type("text", p) == "VARCHAR(16)"
    p["max_len"] = 100
    assert tm.mysql_type("text", p) == "VARCHAR(255)"
    p["max_len"] = 600
    assert tm.mysql_type("text", p) == "TEXT"
    assert tm.mysql_type("text", p, is_key=True) == "VARCHAR(768)"
    p["max_len"] = 900
    with pytest.raises(ValueError):
        tm.mysql_type("text", p, is_key=True, column="k")


def test_bigint_when_out_of_int32():
    p = tm.new_profile()
    p["int_min"], p["int_max"] = 0, 3_000_000_000
    assert tm.mysql_type("int", p, column="n") == "BIGINT"


@pytest.mark.parametrize("value,kind,expected", [
    ("78513.0", "int", 78513), ("", "int", None), ("-", "double", None),
    (" 1.25 ", "double", 1.25), (3.0, "int", 3), (7, "text", "7"),
    ("2026-09-30", "date", "2026-09-30"), (None, "int", None),
    (b"ab", "blob", b"ab"),
])
def test_normalize(value, kind, expected):
    assert tm.normalize(value, kind) == expected


def test_normalize_rejects_non_numbers():
    with pytest.raises(ValueError):
        tm.normalize("abc", "int")
    with pytest.raises(ValueError):
        tm.normalize(2.5, "int")


def test_invalid_dates_stay_text():
    """달력에 없는 날짜는 text로 남습니다."""
    p = _profile(["2026-09-30", "2026-02-30"], column="move_date")
    assert tm.column_kind("move_date", "TEXT", p) == "text"
    p = _profile(["0000-00-00"], column="date_col")
    assert tm.column_kind("date_col", "TEXT", p) == "text"


def test_invalid_datetimes_stay_text():
    """달력에 없는 시간은 text로 남습니다."""
    p = _profile(["2026-09-30 25:00:00"], column="updated_at")
    assert tm.column_kind("updated_at", "TEXT", p) == "text"


def test_fullwidth_digits_stay_text():
    """전각 숫자는 text로 남습니다."""
    p = _profile(["２０２６-０９-３０"], column="date_col")
    assert tm.column_kind("date_col", "TEXT", p) == "text"
    p = _profile(["２０２６"], decl="INTEGER", column="n")
    assert tm.column_kind("n", "INTEGER", p) == "text"


def test_player_id_out_of_uint32_becomes_bigint():
    """선수 ID가 UINT32 범위를 초과하면 BIGINT입니다."""
    p = tm.new_profile()
    p["int_min"], p["int_max"] = 0, 5_000_000_000
    assert tm.mysql_type("int", p, column="batter_ID") == "BIGINT"


def test_player_id_with_negative_stays_int():
    """선수 ID가 음수를 포함하면 INT입니다."""
    p = tm.new_profile()
    p["int_min"], p["int_max"] = -1, 10
    assert tm.mysql_type("int", p, column="batter_ID") == "INT"


def test_integer_out_of_bigint64_raises():
    """정수가 BIGINT 범위를 초과하면 ValueError입니다."""
    p = tm.new_profile()
    p["int_min"], p["int_max"] = 0, 2 ** 63
    with pytest.raises(ValueError):
        tm.mysql_type("int", p, column="n")
