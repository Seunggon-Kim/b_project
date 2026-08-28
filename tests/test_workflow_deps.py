# -*- coding: utf-8 -*-
"""워크플로가 쓰는 외부 패키지를 다 설치하는지 봅니다.

`tqdm` 이 빠져 있어서 매일 새벽 PBP 수집이 죽었습니다.

    File "crawler/download.py", line 5, in <module>
      from tqdm import tqdm, trange
    ModuleNotFoundError: No module named 'tqdm'

**import 를 따라가는 방식으로는 안 보입니다.** PBP 수집은 크롤러를
`subprocess` 로 부르기 때문입니다. 로컬에는 깔려 있어 재현도 안 됩니다.
러너에서만, 그것도 continue-on-error 에 가려 초록 체크로 보였습니다.

같은 이유로 monthly 에 pandas 가 빠져 있었습니다.

그래서 여기서는 **subprocess 로 부르는 파일까지 손으로 적어** 검사합니다.
"""
import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"

# pip 이름과 import 이름이 다른 것들입니다.
PIP_TO_IMPORT = {
    "beautifulsoup4": "bs4",
    "webdriver-manager": "webdriver_manager",
    "python-dateutil": "dateutil",
    "pillow": "PIL",
}

# pandas 가 끌고 오는 것들입니다. 따로 적지 않아도 깔립니다.
TRANSITIVE = {"numpy", "dateutil", "pytz", "six"}

# 워크플로마다 실제로 실행되는 파일입니다. subprocess 로 부르는 것도
# 포함합니다. 새 스크립트를 워크플로에 넣으면 여기에도 적으십시오.
ENTRYPOINTS = {
    "daily.yml": [
        "data_collection/daily_pbp_to_d1.py",
        "data_collection/daily_games_to_d1.py",
        "data_collection/futures_to_d1.py",
        # 공식 기록은 브라우저 없이 HTTP 로 읽습니다.
        "data_collection/official_stats_http.py",
        "data_collection/csv_to_d1.py",
        "data_collection/record_job_run.py",
        # 2008~2014 PBP 되채우기. 끝나면 워크플로에서 빼십시오.
        "migration/shard_backfill.py",
        # subprocess 로 부릅니다. import 로는 안 보입니다.
        "crawler/pbp.py",
        "crawler/download.py",
    ],
    "weekly.yml": [
        "migration/d1_to_sqlite.py",
        "park_factors/compute_self_park_factors.py",
        "park_factors/build_woba_weights.py",
        "park_factors/build_wrc_plus.py",
        "park_factors/build_re24_run_values.py",
        "migration/sqlite_to_d1.py",
        "migration/export_csv.py",
        "data_collection/record_job_run.py",
    ],
    "monthly.yml": [
        "migration/d1_to_sqlite.py",
        "data_collection/player_info_scraper.py",
        "migration/sqlite_to_d1.py",
        "data_collection/record_job_run.py",
    ],
}

REPO_DIRS = ("crawler", "data_collection", "migration", "park_factors")


def _repo_module(name):
    """저장소 안의 모듈이면 그 경로입니다."""
    for d in REPO_DIRS:
        p = ROOT / d / (name + ".py")
        if p.exists():
            return p
    return None


def external_imports(rel_paths):
    """그 파일들과 그것들이 import 하는 저장소 모듈의 외부 패키지 전부."""
    std = set(sys.stdlib_module_names)
    seen, out = set(), set()
    stack = [ROOT / p for p in rel_paths]
    while stack:
        p = stack.pop()
        if not p.exists() or str(p) in seen:
            continue
        seen.add(str(p))
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            names = []
            if isinstance(n, ast.Import):
                names = [a.name.split(".")[0] for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                names = [n.module.split(".")[0]]
            for m in names:
                if m in std or m in REPO_DIRS:
                    continue
                local = _repo_module(m)
                if local:
                    stack.append(local)
                else:
                    out.add(m)
    return out


def installed(wf_name):
    """`pip install` 줄에서 import 이름 집합을 만듭니다."""
    src = (WF / wf_name).read_text(encoding="utf-8")
    got = set()
    for line in src.splitlines():
        m = re.search(r"pip install\s+(.+)$", line.strip())
        if not m or "--upgrade pip" in m.group(1):
            continue
        for pkg in m.group(1).split():
            if pkg.startswith("-"):
                continue
            base = re.split(r"[=<>\[]", pkg)[0].strip()
            got.add(PIP_TO_IMPORT.get(base, base.replace("-", "_")))
    return got


@pytest.mark.parametrize("wf", sorted(ENTRYPOINTS))
def test_워크플로가_필요한_패키지를_다_설치합니다(wf):
    need = external_imports(ENTRYPOINTS[wf])
    have = installed(wf) | TRANSITIVE
    missing = sorted(need - have)
    assert not missing, (
        "%s 가 %s 를 설치하지 않습니다. 러너에서 ModuleNotFoundError 로 "
        "죽습니다. 설치 목록: %s" % (wf, ", ".join(missing), sorted(installed(wf)))
    )


def test_daily_가_tqdm_을_설치합니다():
    """실제로 났던 고장입니다. 못을 박아 둡니다."""
    assert "tqdm" in installed("daily.yml"), (
        "crawler/download.py 가 tqdm 을 씁니다. 크롤러를 subprocess 로 "
        "부르므로 import 만 봐서는 안 보입니다.")


def test_적어_둔_진입점이_실제로_있습니다():
    for wf, paths in ENTRYPOINTS.items():
        for rel in paths:
            assert (ROOT / rel).exists(), "%s: %s 가 없습니다" % (wf, rel)


def test_워크플로가_부르는_파이썬이_진입점에_다_적혀_있습니다():
    """워크플로에 새 스크립트를 넣고 여기 안 적으면 검사에서 샙니다."""
    for wf, listed in ENTRYPOINTS.items():
        src = (WF / wf).read_text(encoding="utf-8")
        called = set(re.findall(r"python\s+([A-Za-z0-9_/]+\.py)", src))
        missing = sorted(called - set(listed))
        assert not missing, (
            "%s 가 %s 를 부르는데 ENTRYPOINTS 에 없습니다"
            % (wf, ", ".join(missing)))
