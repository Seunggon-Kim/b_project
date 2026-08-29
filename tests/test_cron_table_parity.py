# -*- coding: utf-8 -*-
"""데이터 탐색 페이지의 수집 스케줄 표가 실제 워크플로와 같아야 합니다.

## 왜 필요한가

그 표는 손으로 적은 것입니다. 워크플로에 단계를 더해도 표는 그대로라
**조용히 낡습니다.** 실제로 1군 등록 현황·players 갱신·옛 시즌 되채우기
·사진 주소 보정 네 가지가 표에 없었고, 화면은 "총 7개 작업" 이라고
말하고 있었습니다.

낡은 안내는 없는 안내보다 나쁩니다. 읽는 사람이 그대로 믿습니다.

여기서 잡으면 다음에 단계를 더할 때 테스트가 먼저 알려 줍니다.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"
PAGE = ROOT / "dashboard_js" / "pages" / "database-explorer.html"

# 표에 적지 않아도 되는 것들입니다. 수집이 아니라 거들기입니다.
HELPERS = {
    "record_job_run.py",      # 실행 결과만 남깁니다
    "d1_to_sqlite.py",        # 계산 전에 내려받기
    "sqlite_to_d1.py",        # 계산 뒤 올리기
    "export_csv.py",          # 산출물 내보내기
    # park_factors 파이프라인 안쪽입니다. 표에 한 행으로 묶여 있습니다.
    "build_woba_weights.py",
    "build_wrc_plus.py",
    "build_re24_run_values.py",
    "compute_self_park_factors.py",
}


def workflow_scripts():
    """워크플로가 실제로 부르는 스크립트 파일 이름입니다."""
    names = set()
    for wf in ("daily.yml", "weekly.yml", "monthly.yml"):
        src = (WF / wf).read_text(encoding="utf-8")
        for path in re.findall(r"python\s+([A-Za-z0-9_/]+\.py)", src):
            names.add(path.split("/")[-1])
    return names - HELPERS


def test_워크플로_스크립트가_모두_표에_있습니다():
    page = PAGE.read_text(encoding="utf-8")
    missing = sorted(n for n in workflow_scripts() if n not in page)
    assert not missing, (
        "수집 스케줄 표에 없는 스크립트: %s\n"
        "dashboard_js/pages/database-explorer.html 의 표를 고치십시오."
        % ", ".join(missing))


def test_작업_수가_표와_맞습니다():
    page = PAGE.read_text(encoding="utf-8")
    m = re.search(r"총 (\d+)개 작업", page)
    assert m, "'총 N개 작업' 문구가 없습니다."
    rows = len(re.findall(r'class="dbx-cron-mods"', page))
    assert int(m.group(1)) == rows, (
        "표에 적힌 작업 수(%s)와 실제 행 수(%d)가 다릅니다."
        % (m.group(1), rows))


def test_park_factors_파이프라인은_한_행으로_묶습니다():
    # 안쪽 네 스크립트를 따로 세면 표가 길어지기만 합니다.
    page = PAGE.read_text(encoding="utf-8")
    assert "park_factors 파이프라인" in page
