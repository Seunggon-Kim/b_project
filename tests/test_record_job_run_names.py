# -*- coding: utf-8 -*-
"""record_job_run 의 작업 이름 목록은 계보 손 파일의 status_keys 에서 옵니다.

예전에는 화면 HTML 의 data-job 과 맞춘 손 목록이라 낡았습니다(team_ranks·
roster_pm 등이 빠져 경고만 찍혔습니다). 이제 워크플로가 부르는 이름이 모두
계보 파일에 있어야 화면 수집 일정 표에 실행 기록이 붙습니다.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import record_job_run as rj  # noqa: E402


def test_작업_이름은_계보_파일에서_읽습니다(tmp_path):
    p = tmp_path / "hand.json"
    p.write_text('{"scripts": {"a.py": {"status_keys": {"daily": "x", "roster": "y"}},'
                 ' "b.py": {}}}', encoding="utf-8")
    assert rj.known_jobs(p) == {"x", "y"}


def test_워크플로가_기록하는_이름이_모두_계보_파일에_있습니다():
    used = set()
    for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
        used |= set(re.findall(r"record_job_run\.py\s+--job\s+([A-Za-z_]+)",
                               wf.read_text(encoding="utf-8")))
    assert used, "워크플로에서 record_job_run 호출을 못 찾았습니다"
    assert not used - rj.KNOWN_JOBS, sorted(used - rj.KNOWN_JOBS)
