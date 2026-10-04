# -*- coding: utf-8 -*-
"""수집 쪽에 D1 흔적(wrangler·D1 스위치)이 다시 들어오지 않게 막습니다.

D1 은 2026-10-04 에 수집 쪽에서 걷어냈습니다. 수집은 Cloud SQL(MySQL)에만
씁니다. 아래 세 곳 어디에도 wrangler 를 부르거나 D1 스위치(BSTATS_D1·저장소
변수 D1_WRITE)를 보는 글자가 있으면 안 됩니다. 남아 있으면 지운 D1 을
부르다가 러너에서야 실패하거나, 없는 스위치를 믿고 되돌리기를 시도하게 됩니다.

꼭 남겨야 하는 파일이 생기면 ALLOW 에 경로와 까닭을 적으십시오.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIRS = ["data_collection", "migration", ".github/workflows"]
WORDS = re.compile(r"wrangler|BSTATS_D1|D1_WRITE", re.I)
TEXT_SUFFIXES = {".py", ".sh", ".yml", ".yaml", ".json", ".md", ".sql", ".txt", ".toml", ".cfg", ".ini"}
SKIP_DIRS = {"__pycache__", "out", "golden", "push"}

# 경로(저장소 기준, / 구분) -> 남겨야 하는 까닭. 지금은 없습니다.
ALLOW = {}


def _tracked(root):
    """git 이 추적하는 파일만 봅니다. 로컬에만 있는 산출물·로그는 보지 않습니다.

    git 저장소가 아니면(테스트용 임시 폴더) None 입니다.
    """
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--"] + DIRS,
                           capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return {root / p for p in r.stdout.decode("utf-8").split("\0") if p}


def scanned_files(root=ROOT):
    tracked = _tracked(root)
    for d in DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if any(part in SKIP_DIRS for part in p.relative_to(root).parts):
                continue
            if tracked is not None and p not in tracked:
                continue
            yield p


def hits(root=ROOT):
    out = []
    for p in scanned_files(root):
        rel = p.relative_to(root).as_posix()
        if rel in ALLOW:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            m = WORDS.search(line)
            if m:
                out.append("%s:%d %s" % (rel, n, m.group(0)))
    return out


def test_수집_코드에_wrangler_와_D1_스위치가_없습니다():
    bad = hits()
    assert not bad, (
        "D1 흔적이 남아 있습니다(수집은 MySQL 에만 씁니다). 꼭 남겨야 하면 "
        "tests/test_no_d1_left.py 의 ALLOW 에 까닭을 적으십시오:\n  " + "\n  ".join(bad))


def test_검사가_헛돌지_않습니다():
    files = {p.relative_to(ROOT).as_posix() for p in scanned_files()}
    for must in ("data_collection/d1_load.py", "data_collection/mysql_sink.py",
                 "migration/sqlite_to_d1.py", "migration/mysql/ci_proxy.sh",
                 ".github/workflows/daily.yml", ".github/workflows/monthly.yml"):
        assert must in files, must


def test_검사기가_실제로_잡습니다(tmp_path):
    (tmp_path / "data_collection").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / "data_collection" / "x.py").write_text(
        "cmd = ['npx', 'Wrangler@4']\n", encoding="utf-8")
    (tmp_path / ".github" / "workflows" / "a.yml").write_text(
        "env:\n  BSTATS_D1: ${{ vars.D1_WRITE }}\n", encoding="utf-8")
    got = hits(tmp_path)
    assert got == ["data_collection/x.py:1 Wrangler", ".github/workflows/a.yml:2 BSTATS_D1"], got


def test_허용_목록의_파일은_실제로_있습니다():
    missing = [p for p in ALLOW if not (ROOT / p).is_file()]
    assert not missing, missing
