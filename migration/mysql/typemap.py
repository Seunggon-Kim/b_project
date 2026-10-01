# -*- coding: utf-8 -*-
"""SQLite 열 하나를 MySQL 타입으로 옮기는 규칙입니다.

D1(SQLite)은 선언과 다른 타입의 값도 받습니다. 그래서 같은 열에 숫자와
빈 문자열이 섞여 있습니다(플레이 기록 숫자 열 18개에 약 4%가 ''). 선수
ID 일부는 '78513.0' 처럼 소수점이 붙은 글자입니다. MySQL 엄격 모드는
그런 값을 거부합니다. 여기서 열마다 실제 값을 훑어(프로파일) 타입을
고르고, 옮길 때 값을 고칩니다.

규칙의 요지(로드맵 1단계와 같습니다):
- 숫자로 선언된 열의 '' 와 '-' 는 NULL 입니다.
- 선수 ID 열은 값이 모두 정수 모양이면 INT UNSIGNED 입니다.
- 글자로 선언된 열은 글자로 둡니다('00' 과 '0' 을 지킵니다). 다만 값이
  모두 YYYY-MM-DD 면 DATE, YYYY-MM-DD HH:MM:SS 면 DATETIME 입니다.
- game_date 처럼 DATE 로 선언됐지만 YYYYMMDD 정수인 열은 INT 입니다.
"""
import re

EMPTY_TEXT = {"", "-"}
INT_LIKE = re.compile(r"^[+-]?\d+(\.0+)?$")
NUM_LIKE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")
DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_TIME = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
PLAYER_ID = re.compile(
    r"^(player_id|batter_id|pitcher_id|on_[123]b_id|pos_[1-9]_id)$",
    re.IGNORECASE)
VARCHAR_STEPS = (16, 32, 64, 128, 255, 512, 1024)
KEY_VARCHAR_MAX = 768          # utf8mb4 인덱스 한도 3072바이트 / 4바이트
KEY_MAX_CHARS = 600            # 이보다 긴 키는 설계를 다시 봐야 하는 신호입니다
INT32 = (-2 ** 31, 2 ** 31 - 1)
BLOB_MEDIUM_MAX = 16 * 1024 * 1024 - 1
TEXT_MAX_CHARS = 16000         # TEXT 65,535바이트 / utf8mb4 4바이트, 여유를 둠


def new_profile():
    return {"nonnull": 0, "ints": 0, "reals": 0, "blobs": 0, "texts": 0,
            "int_texts": 0, "num_texts": 0, "dotzero": 0, "empties": 0,
            "dates": 0, "datetimes": 0, "max_len": 0,
            "int_min": None, "int_max": None}


def _widen(p, v):
    p["int_min"] = v if p["int_min"] is None else min(p["int_min"], v)
    p["int_max"] = v if p["int_max"] is None else max(p["int_max"], v)


def observe_text(p, s, n=1):
    """글자 값 하나(가 n 번)를 프로파일에 반영합니다. nonnull 은 그대로 둡니다."""
    t = s.strip()
    if t in EMPTY_TEXT:
        p["empties"] += n
    elif INT_LIKE.match(t):
        p["int_texts"] += n
        if "." in t:
            p["dotzero"] += n
        _widen(p, int(t.split(".")[0]))
    elif NUM_LIKE.match(t):
        p["num_texts"] += n
    else:
        p["texts"] += n
        if DATE_ONLY.match(t):
            p["dates"] += n
        elif DATE_TIME.match(t):
            p["datetimes"] += n


def profile_column(con, table, column):
    """SQLite 스냅샷에서 열 하나의 프로파일을 만듭니다.

    큰 표(플레이 기록 약 400만 행)도 감당하도록 개수·길이는 SQL 로 세고,
    글자 값은 서로 다른 값만 꺼내 분류합니다.
    """
    c, t = '"%s"' % column, '"%s"' % table
    row = con.execute(
        "SELECT COUNT({c}), "
        "SUM(typeof({c})='integer'), SUM(typeof({c})='real'), "
        "SUM(typeof({c})='blob'), "
        "MIN(CASE WHEN typeof({c})='integer' THEN {c} END), "
        "MAX(CASE WHEN typeof({c})='integer' THEN {c} END), "
        "MAX(CASE WHEN typeof({c})='blob' THEN length({c}) "
        "         WHEN {c} IS NOT NULL THEN length(CAST({c} AS TEXT)) END) "
        "FROM {t}".format(c=c, t=t)).fetchone()
    p = new_profile()
    p["nonnull"] = row[0]
    p["ints"], p["reals"], p["blobs"] = row[1] or 0, row[2] or 0, row[3] or 0
    if row[4] is not None:
        _widen(p, row[4])
        _widen(p, row[5])
    p["max_len"] = row[6] or 0
    for value, n in con.execute(
            "SELECT {c}, COUNT(*) FROM {t} WHERE typeof({c})='text' "
            "GROUP BY {c}".format(c=c, t=t)):
        observe_text(p, value, n)
    return p


def _date_kind(p):
    """값이 전부 날짜(또는 일시) 모양 글자면 그 종류입니다."""
    if (p["texts"] == 0 or p["ints"] or p["reals"] or p["blobs"]
            or p["int_texts"] or p["num_texts"] or p["empties"]):
        return None
    if p["dates"] == p["texts"]:
        return "date"
    if p["datetimes"] == p["texts"]:
        return "datetime"
    return None


def column_kind(column, decl, p):
    """'int' 'double' 'date' 'datetime' 'blob' 'text' 중 하나를 고릅니다."""
    d = (decl or "").upper()
    # 빈 문자열은 NULL 로 바뀌므로 숫자 열을 막지 않습니다.
    numeric_only = p["texts"] == 0 and p["blobs"] == 0
    integral = numeric_only and p["reals"] == 0 and p["num_texts"] == 0
    if PLAYER_ID.match(column):
        return "int" if integral else "text"
    if "BLOB" in d:
        return "blob"
    if "INT" in d:
        if integral:
            return "int"
        return "double" if numeric_only else "text"
    if any(k in d for k in ("REAL", "FLOA", "DOUB", "NUMERIC", "DECIMAL")):
        return "double" if numeric_only else "text"
    if "DATE" in d or "TIME" in d:
        # game_date 는 DATE 로 선언됐지만 YYYYMMDD 정수로 쌓고 비교합니다.
        if integral and (p["ints"] or p["int_texts"]):
            return "int"
        return _date_kind(p) or "text"
    if not d:
        if p["blobs"] and p["blobs"] == p["nonnull"]:
            return "blob"
        if numeric_only and (p["ints"] or p["reals"] or p["int_texts"]
                             or p["num_texts"]):
            return "int" if integral else "double"
    # 글자로 선언된 열은 글자로 둡니다. back_number 의 '00' 과 '0' 을 지킵니다.
    return _date_kind(p) or "text"


def mysql_type(kind, p, is_key=False, column=""):
    """값 종류와 프로파일로 MySQL 열 타입을 고릅니다."""
    if kind == "int":
        lo, hi = p["int_min"], p["int_max"]
        if PLAYER_ID.match(column) and (lo is None or lo >= 0):
            return "INT UNSIGNED"
        if lo is None or (INT32[0] <= lo and hi <= INT32[1]):
            return "INT"
        return "BIGINT"
    if kind == "double":
        return "DOUBLE"
    if kind == "date":
        return "DATE"
    if kind == "datetime":
        return "DATETIME"
    if kind == "blob":
        return "MEDIUMBLOB" if p["max_len"] <= BLOB_MEDIUM_MAX else "LONGBLOB"
    want = max(16, p["max_len"] * 2)
    for step in VARCHAR_STEPS:
        if step >= want:
            if is_key and step > KEY_VARCHAR_MAX:
                break
            return "VARCHAR(%d)" % step
    if is_key:
        if p["max_len"] <= KEY_MAX_CHARS:
            return "VARCHAR(%d)" % KEY_VARCHAR_MAX
        raise ValueError("키 열 %s 가 너무 깁니다(%d자)" % (column, p["max_len"]))
    return "TEXT" if p["max_len"] < TEXT_MAX_CHARS else "MEDIUMTEXT"


def normalize(value, kind):
    """스냅샷 값 하나를 MySQL 에 넣을 값으로 바꿉니다. 못 바꾸면 ValueError."""
    if value is None:
        return None
    if kind == "text":
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value if isinstance(value, str) else str(value)
    if kind == "blob":
        return value if isinstance(value, bytes) else str(value).encode("utf-8")
    if isinstance(value, bytes):
        raise ValueError("바이트 값을 %s 로 바꿀 수 없습니다" % kind)
    if isinstance(value, str):
        t = value.strip()
        if t in EMPTY_TEXT:
            return None
        if kind == "int":
            if not INT_LIKE.match(t):
                raise ValueError("정수가 아닙니다: %r" % value)
            return int(t.split(".")[0])
        if kind == "double":
            if not NUM_LIKE.match(t):
                raise ValueError("숫자가 아닙니다: %r" % value)
            return float(t)
        return t                    # date / datetime: 프로파일에서 모양을 확인했습니다
    if kind == "int":
        if isinstance(value, float):
            if not value.is_integer():
                raise ValueError("정수가 아닙니다: %r" % value)
            return int(value)
        return value
    if kind == "double":
        return float(value)
    raise ValueError("%s 열에 숫자 %r 가 있습니다" % (kind, value))
