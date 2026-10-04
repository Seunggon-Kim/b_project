# -*- coding: utf-8 -*-
"""MySQL 로 옮길 표와 옮기지 않을 표를 가릅니다.

MySQL 이관 1단계에서 D1 내려받기(지금은 지운 `migration/d1_to_sqlite.py
--all-tables`)와 스키마 생성(`migration/mysql/ddl.py`)이 같은 기준을 썼습니다.
지금은 ddl.py 가 씁니다.
"""
import re

# sqlite_* 와 _cf_* 는 SQLite·D1 내부 표입니다. d1_migrations 는 D1
# 마이그레이션 기록입니다. _bak 은 손으로 만든 백업입니다.
_SKIP = re.compile(r"^(sqlite_|_cf_)|^d1_migrations$|_bak($|_)")

# 공용 DB 에 없고 샤드에만 있는 표입니다.
SHARD_ONLY = ("play_by_play",)


def is_migrated(name):
    """옮길 표면 True 입니다."""
    return not _SKIP.search(name)


def migrated_tables(names):
    """공용 DB 표 이름에서 옮길 것만 고르고, 샤드 전용 표를 한 번 더합니다."""
    out = sorted(n for n in names if is_migrated(n))
    for t in SHARD_ONLY:
        if t not in out:
            out.append(t)
    return out
