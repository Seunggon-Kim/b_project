# -*- coding: utf-8 -*-
"""주간 파이프라인이 쓰는 표가 러너에 실제로 내려오는지 봅니다.

러너에는 D1 에서 받은 표만 있습니다. 목록(`PIPELINE_TABLES`)에 없으면
그 표는 존재하지 않습니다. 그런데 파크팩터 스크립트들은 덮어쓰기 전에
**롤링 백업**을 뜹니다.

    CREATE TABLE kbo_run_values_by_season_bak AS
      SELECT * FROM kbo_run_values_by_season

표가 없으면 여기서 `no such table` 로 죽습니다. 실제로 주간 워크플로가
44분을 돌고 마지막 단계에서 이렇게 실패했습니다. 로컬에서는 제가 미리
표를 만들어 둬서 재현되지 않았습니다.

반대쪽도 봅니다. 만든 표를 `DERIVED_TABLES`(올리기 목록)에 넣지 않으면
계산만 하고 D1 에는 아무것도 안 올라갑니다. 이 역시 조용합니다.
"""
import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PULL = ROOT / "migration" / "d1_to_sqlite.py"
PUSH = ROOT / "migration" / "sqlite_to_d1.py"
PARK = ROOT / "park_factors"


def const(path, name):
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    pytest.fail("%s 에서 %s 를 찾지 못했습니다" % (path.name, name))


def scripts():
    return sorted(p for p in PARK.glob("*.py") if not p.name.startswith("_"))


def backed_up(src):
    """롤링 백업(`*_bak`)을 뜨는 대상 표 이름들입니다.

    파일에 `_bak` 이 있다고 아무 리스트나 잡으면 컬럼 이름 목록까지
    걸립니다(실제로 `inning`, `outs` 가 잡혔습니다). 백업 구문
    **가까이에 있는** 리스트만 봅니다.
    """
    out = set()

    # (1) `for t in [...]:` 또는 `for t in (...):` 뒤 200자 안에
    #     백업 구문이 있는 경우입니다. 리스트와 튜플 둘 다 씁니다.
    loop_vars = set()
    for m in re.finditer(r"for\s+(\w+)\s+in\s+([\[(][^\])]+[\])])\s*:", src):
        near = src[m.end():m.end() + 200]
        if "BACKUP_SUFFIX" not in near and "_bak" not in near:
            continue
        loop_vars.add(m.group(1))
        try:
            names = ast.literal_eval(m.group(2))
        except (ValueError, SyntaxError):
            continue
        out |= {x for x in names
                if isinstance(x, str) and x.isidentifier()}

    # (2) 표 이름을 직접 쓴 경우입니다. f-string 의 `{t}` 는 (1) 에서
    #     이미 잡았으므로 반복 변수 이름은 빼야 합니다. 안 그러면
    #     't' 라는 표가 있는 것처럼 보입니다.
    for m in re.finditer(
            r'CREATE TABLE\s+["\'{]?(\w+)[}"\']?_bak\s+AS', src):
        out.add(m.group(1))

    return out - loop_vars


def test_백업하는_표는_내려받기_목록에_있습니다():
    """없으면 `no such table` 로 죽습니다. 실제로 겪었습니다."""
    pull = set(const(PULL, "PIPELINE_TABLES"))
    missing = {}
    for p in scripts():
        src = p.read_text(encoding="utf-8")
        for t in backed_up(src):
            if t not in pull:
                missing.setdefault(p.name, set()).add(t)
    assert not missing, (
        "이 표들이 PIPELINE_TABLES 에 없어 러너에서 백업이 실패합니다: %s"
        % {k: sorted(v) for k, v in missing.items()})


@pytest.mark.parametrize("table", [
    "kbo_run_values_by_season",
    "re24_matrix_by_season",
    "kbo_woba_weights_by_season",
    "self_park_factor",
    "wrc_plus_comparison",
    "weighted_pf_by_batter_season",
])
def test_파생표가_내려받기와_올리기_양쪽에_있습니다(table):
    """내려받지 않으면 백업이 죽고, 올리지 않으면 D1 이 안 바뀝니다."""
    assert table in const(PULL, "PIPELINE_TABLES"), \
        "%s 가 PIPELINE_TABLES(내려받기)에 없습니다" % table
    assert table in const(PUSH, "DERIVED_TABLES"), \
        "%s 가 DERIVED_TABLES(올리기)에 없습니다" % table


def test_RE24_스크립트가_표를_스스로_만듭니다():
    """처음 도는 환경에서도 죽지 않아야 합니다."""
    src = (PARK / "build_re24_run_values.py").read_text(encoding="utf-8")
    body = src[src.index("=== WRITING ==="):]
    for t in ("kbo_run_values_by_season", "re24_matrix_by_season"):
        assert "CREATE TABLE IF NOT EXISTS %s" % t in body, \
            "%s 를 만들지 않습니다" % t
    assert body.index("CREATE TABLE IF NOT EXISTS") < body.index("BACKUP_SUFFIX"), \
        "표를 만들기 전에 백업을 뜹니다"


def test_주간_워크플로_단계가_앞_단계_성공에_걸려_있습니다():
    """앞이 실패했는데 뒤가 돌면 낡은 값으로 D1 을 덮습니다."""
    s = re.sub(r"\\\s*\n\s*", " ",
               (ROOT / ".github" / "workflows" / "weekly.yml").read_text(
                   encoding="utf-8"))
    for step in ("woba", "wrc", "re24", "push", "csv"):
        assert "steps.%s.outcome == 'success'" % step in s, \
            "steps.%s 성공 조건을 쓰는 단계가 없습니다" % step
