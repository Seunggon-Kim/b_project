# -*- coding: utf-8 -*-
"""워크플로에서 도는 코드가 러너(리눅스)에서도 도는지 봅니다.

`subprocess.run(["npx", "--yes", ...], shell=True)` 가 문제였습니다.
윈도우는 리스트를 이어붙여 실행하지만 **POSIX 는 첫 항목만 실행하고
나머지를 $0, $1... 로 넘깁니다.** 러너에서는 `npx` 만 돌고 끝났습니다.

이 고장은 눈에 안 보였습니다.

  - 0.x초 만에 실패해서 오래 걸리는 단계처럼 보이지도 않았고
  - 워크플로 단계가 continue-on-error 라 초록 체크로 표시됐고
  - 로컬(윈도우) 수동 실행은 멀쩡히 되니 재현도 안 됐습니다

결과만 "성공했는데 데이터가 안 들어옴" 이었습니다. 사람이 D1 행 수를
직접 세 보기 전에는 모릅니다.

문자열 + shell=True 는 두 플랫폼 다 정상입니다. 리스트일 때만 막습니다.
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# 워크플로가 부르는 스크립트와 그것들이 쓰는 모듈입니다.
WORKFLOW_CODE = [
    "data_collection/collect_player_news.py",
    "data_collection/csv_to_d1.py",
    "data_collection/d1_load.py",
    "data_collection/daily_games_to_d1.py",
    "data_collection/daily_pbp_to_d1.py",
    "data_collection/futures_to_d1.py",
    "data_collection/player_info_scraper.py",
    "data_collection/record_job_run.py",
    "migration/d1_to_sqlite.py",
    "migration/sqlite_to_d1.py",
]


def subprocess_calls(tree):
    """subprocess.run / Popen / call 호출을 모두 찾습니다."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = None
        if isinstance(f, ast.Attribute):
            name = f.attr
            root = f.value
            if not (isinstance(root, ast.Name) and root.id == "subprocess"):
                continue
        if name in ("run", "Popen", "call", "check_call", "check_output"):
            yield node


def literal_true_shell(call):
    for kw in call.keywords:
        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) \
                and kw.value.value is True:
            return True
    return False


def _kind(node):
    """값이 리스트인지 문자열인지 봅니다. 모르면 None 입니다."""
    if isinstance(node, (ast.List, ast.Tuple)):
        return "list"
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return "str"
    if isinstance(node, ast.JoinedStr):          # f-string
        return "str"
    if isinstance(node, ast.BinOp):              # '...' % (...) 또는 '..'+'..'
        return _kind(node.left)
    return None


def assigned_kinds(tree, name):
    """그 이름에 무엇이 대입되는지 모읍니다.

    변수라고 무조건 리스트로 보면 안 됩니다. collect_player_news.py 는
    문자열을 변수에 담아 넘기는데, 문자열 + shell=True 는 두 플랫폼 다
    정상입니다. 그걸 막으면 멀쩡한 코드를 고치게 됩니다.
    """
    kinds = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    kinds.add(_kind(node.value))
    return kinds


def first_arg_is_list(call, tree):
    if not call.args:
        return False
    a = call.args[0]
    if isinstance(a, (ast.List, ast.Tuple)):
        return True
    if isinstance(a, ast.Name):
        kinds = assigned_kinds(tree, a.id)
        # 대입을 못 찾았으면 모르는 것이니 막는 쪽으로 둡니다.
        return "list" in kinds or not kinds
    return False


@pytest.mark.parametrize("rel", WORKFLOW_CODE)
def test_리스트에_shell_True_를_같이_쓰지_않습니다(rel):
    path = ROOT / rel
    if not path.exists():
        pytest.skip("%s 가 없습니다" % rel)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad = []
    for call in subprocess_calls(tree):
        if literal_true_shell(call) and first_arg_is_list(call, tree):
            bad.append(call.lineno)
    assert not bad, (
        "%s:%s 에서 리스트에 shell=True 를 썼습니다. "
        "POSIX 러너에서는 첫 항목만 실행되고 조용히 실패합니다. "
        "shell=USE_SHELL(os.name == 'nt') 로 두거나 문자열로 넘기십시오."
        % (rel, ", ".join(str(n) for n in bad))
    )


def test_고친_두_파일이_플랫폼을_봅니다():
    """되돌아가지 않게 못을 박습니다."""
    for rel in ("data_collection/d1_load.py", "migration/d1_to_sqlite.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert 'USE_SHELL = os.name == "nt"' in src, \
            "%s 에 USE_SHELL 정의가 없습니다" % rel
        assert "shell=USE_SHELL" in src, \
            "%s 가 USE_SHELL 을 쓰지 않습니다" % rel


def test_판정기가_실제로_잡습니다():
    """테스트가 헛돌지 않는지 스스로 확인합니다."""
    tree = ast.parse(
        "import subprocess\n"
        "subprocess.run(['npx', 'a'], shell=True)\n")
    calls = list(subprocess_calls(tree))
    assert len(calls) == 1
    assert literal_true_shell(calls[0]) and first_arg_is_list(calls[0], tree)

    ok = ast.parse(
        "import subprocess\n"
        "subprocess.run('npx a', shell=True)\n"
        "subprocess.run(['npx', 'a'], shell=False)\n")
    for c in subprocess_calls(ok):
        assert not (literal_true_shell(c) and first_arg_is_list(c, ok))

    # 문자열을 변수에 담아 넘기는 모양도 통과해야 합니다.
    strvar = ast.parse(
        "import subprocess\n"
        "cmd = 'npx wrangler d1 execute %s' % db\n"
        "subprocess.run(cmd, shell=True)\n")
    for c in subprocess_calls(strvar):
        assert not (literal_true_shell(c) and first_arg_is_list(c, strvar))
