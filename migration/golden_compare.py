# -*- coding: utf-8 -*-
"""두 응답 집합을 비교합니다.

설계 문서 10장의 비교 규칙:
  - 부동소수점은 상대 오차 1e-9 이내면 같다고 봅니다.
  - 정수·문자열은 타입까지 완전 일치를 요구합니다.
  - 배열 순서는 그대로 비교합니다.
  - null, 빈 문자열, 0 을 구분합니다.

라이브 응답은 구조만 봅니다
---------------------------
`/standings`, `/schedule`, `/players/{id}/news` 는 네이버에서 실시간으로 받아
옵니다. 정답지를 뜬 순간과 이식본을 호출한 순간의 값이 다를 수밖에 없어, 값을
그대로 비교하면 늘 불일치로 잡힙니다. 이런 응답은 값 대신 **구조**(키 이름과
타입)를 비교합니다. 숫자가 문자열로 바뀌는 이식 사고는 이 방식으로도 잡힙니다.
"""
import argparse
import json
import math
import sys
from pathlib import Path

# 파일 이름이 이 접두어로 시작하면 라이브 응답으로 봅니다.
# golden_matrix.safe_name 이 '/' 를 '_' 로 바꾸므로 이 형태가 됩니다.
LIVE_PREFIXES = ("standings", "schedule")

# 선수 뉴스도 라이브입니다. 이름 가운데에 들어가 접두어로는 못 잡습니다.
LIVE_SUFFIXES = ("_news",)


def is_live_path(name):
    """파일 이름이 라이브 응답인지 판정합니다."""
    stem = name[:-5] if name.endswith(".json") else name
    return stem.startswith(LIVE_PREFIXES) or stem.endswith(LIVE_SUFFIXES)


def shape_of(value):
    """값을 타입 이름으로 바꿔 구조만 남깁니다.

    리스트는 첫 원소의 구조만 남깁니다. 길이가 달라도 같다고 보기 위함입니다.
    """
    if isinstance(value, dict):
        return {k: shape_of(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [shape_of(value[0])] if value else []
    return type(value).__name__


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def compare_values(expected, actual, path="", rel_tol=1e-9, structural=False,
                   numeric_loose=False):
    """두 값을 비교하고 차이 설명 목록을 반환합니다."""
    if structural:
        e = shape_of(expected)
        a = shape_of(actual)
        if e == a:
            return []
        return ["%s: 구조가 다릅니다.\n      기대 %s\n      실제 %s"
                % (path or "(root)",
                   json.dumps(e, ensure_ascii=False)[:300],
                   json.dumps(a, ensure_ascii=False)[:300])]

    loc = path or "(root)"

    # 부동소수점 허용 오차. 단 int 와 float 의 혼용은 타입 차이로 봅니다.
    if _is_number(expected) and _is_number(actual):
        # SQLite REAL 에 든 85.0 을 파이썬은 85.0 으로, JS 는 85 로 씁니다.
        # JS 의 Number 는 정수와 실수를 구분하지 않아 JSON.stringify(85.0) 이
        # 늘 85 입니다. 이식으로 고칠 수 있는 차이가 아니고 값도 같습니다.
        # numeric_loose 를 켜면 그 경우만 통과시킵니다. 85.5 대 85 는 그대로
        # 잡힙니다.
        if (numeric_loose and float(expected) == float(actual)
                and type(expected) is not type(actual)):
            return []
        if isinstance(expected, float) or isinstance(actual, float):
            if isinstance(expected, float) and isinstance(actual, float):
                if math.isclose(expected, actual, rel_tol=rel_tol, abs_tol=1e-12):
                    return []
                return ["%s: 기대 %r, 실제 %r" % (loc, expected, actual)]
            return ["%s: 타입이 다릅니다. 기대 %s(%r), 실제 %s(%r)"
                    % (loc, type(expected).__name__, expected,
                       type(actual).__name__, actual)]
        if expected == actual:
            return []
        return ["%s: 기대 %r, 실제 %r" % (loc, expected, actual)]

    if type(expected) is not type(actual):
        return ["%s: 타입이 다릅니다. 기대 %s(%r), 실제 %s(%r)"
                % (loc, type(expected).__name__, expected,
                   type(actual).__name__, actual)]

    if isinstance(expected, dict):
        diffs = []
        for key in sorted(set(expected) | set(actual)):
            child = "%s.%s" % (path, key) if path else key
            if key not in actual:
                diffs.append("%s: 응답에 없습니다" % child)
            elif key not in expected:
                diffs.append("%s: 정답지에 없습니다" % child)
            else:
                diffs.extend(
                    compare_values(expected[key], actual[key], child, rel_tol,
                                   structural, numeric_loose))
        return diffs

    if isinstance(expected, list):
        if len(expected) != len(actual):
            return ["%s: 길이가 다릅니다. 기대 %d, 실제 %d"
                    % (loc, len(expected), len(actual))]
        diffs = []
        for i, (e, a) in enumerate(zip(expected, actual)):
            diffs.extend(compare_values(e, a, "%s[%d]" % (path, i), rel_tol,
                                        structural, numeric_loose))
        return diffs

    if expected == actual:
        return []
    return ["%s: 기대 %r, 실제 %r" % (loc, expected, actual)]


def compare_dirs(expected_dir, actual_dir, rel_tol=1e-9, numeric_loose=True):
    """두 디렉터리의 같은 이름 JSON 파일들을 비교합니다."""
    expected_dir = Path(expected_dir)
    actual_dir = Path(actual_dir)
    same = 0
    live = 0
    different = []
    missing = []
    for ef in sorted(expected_dir.glob("*.json")):
        af = actual_dir / ef.name
        if not af.exists():
            missing.append(ef.name)
            continue
        e = json.loads(ef.read_text(encoding="utf-8"))
        a = json.loads(af.read_text(encoding="utf-8"))
        structural = is_live_path(ef.name)
        diffs = compare_values(e, a, "", rel_tol, structural=structural,
                               numeric_loose=numeric_loose)
        if diffs:
            different.append("%s%s\n    %s" % (
                ef.name, " (구조 비교)" if structural else "",
                "\n    ".join(diffs[:5])))
        else:
            same += 1
            if structural:
                live += 1
    return {"same": same, "live": live, "different": different,
            "missing": missing}


def main():
    ap = argparse.ArgumentParser(description="골든 응답을 비교합니다")
    ap.add_argument("expected_dir")
    ap.add_argument("actual_dir")
    ap.add_argument("--rel-tol", type=float, default=1e-9)
    args = ap.parse_args()

    result = compare_dirs(args.expected_dir, args.actual_dir, args.rel_tol)
    print("일치 %d건 (그중 라이브 구조 비교 %d건)" % (result["same"], result["live"]))
    if result["missing"]:
        print()
        print("응답 파일 없음 %d건" % len(result["missing"]))
        for name in result["missing"]:
            print("  " + name)
    if result["different"]:
        print()
        print("불일치 %d건" % len(result["different"]))
        for entry in result["different"]:
            print("  " + entry)
    return 1 if (result["different"] or result["missing"]) else 0


if __name__ == "__main__":
    sys.exit(main())
