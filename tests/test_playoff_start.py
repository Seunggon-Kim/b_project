# -*- coding: utf-8 -*-
"""포스트시즌 시작일 표가 두 파일에서 갈라지지 않게 합니다.

`PLAYOFF_START` 는 그 시즌 몇 월 며칠부터를 포스트시즌으로 볼지 정합니다.
같은 표가 `games_from_pbp.py` 와 `load_year_pbp.py` 두 곳에 복사돼
있습니다. 한쪽만 고치면 어긋나고, 어긋나면 같은 경기가 도구에 따라
정규시즌이 됐다 포스트시즌이 됐다 합니다. 눈으로는 못 잡습니다.

새 시즌을 넣을 때는 **두 파일 모두** 고쳐야 합니다. 이 테스트가
그것을 강제합니다.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [
    ROOT / "data_collection" / "games_from_pbp.py",
    ROOT / "data_collection" / "load_year_pbp.py",
]


def read_table(path):
    """모듈을 실행하지 않고 PLAYOFF_START 만 읽습니다.

    load_year_pbp.py 는 최상위에서 DB 를 열고 적재를 시작하므로
    import 하면 안 됩니다.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == "PLAYOFF_START":
                return ast.literal_eval(node.value)
    raise AssertionError("%s 에 PLAYOFF_START 가 없습니다" % path.name)


def test_두_파일의_표가_같습니다():
    tables = {p.name: read_table(p) for p in SOURCES}
    names = list(tables)
    a, b = tables[names[0]], tables[names[1]]
    only_a = {k: a[k] for k in sorted(set(a) - set(b))}
    only_b = {k: b[k] for k in sorted(set(b) - set(a))}
    diff = {k: (a[k], b[k]) for k in sorted(set(a) & set(b)) if a[k] != b[k]}
    assert a == b, (
        "포스트시즌 시작일이 갈라졌습니다.\n"
        "  %s 에만: %s\n  %s 에만: %s\n  값이 다름: %s"
        % (names[0], only_a, names[1], only_b, diff)
    )


def test_시즌은_문자열_키_에_MMDD_값입니다():
    for p in SOURCES:
        for season, mmdd in read_table(p).items():
            assert isinstance(season, str) and season.isdigit() and len(season) == 4, (
                "%s: 시즌 키가 'YYYY' 문자열이 아닙니다: %r" % (p.name, season))
            assert isinstance(mmdd, int) and 101 <= mmdd <= 1231, (
                "%s: %s 의 값이 MMDD 정수가 아닙니다: %r" % (p.name, season, mmdd))
            assert mmdd // 100 in (9, 10, 11), (
                "%s: %s 의 포스트시즌이 9~11월이 아닙니다: %r"
                % (p.name, season, mmdd))


def test_연도가_빠짐없이_이어집니다():
    years = sorted(int(y) for y in read_table(SOURCES[0]))
    for x, y in zip(years, years[1:]):
        assert y == x + 1, "%d 과 %d 사이 시즌이 빠졌습니다" % (x, y)
