# -*- coding: utf-8 -*-
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import lineage_extract as lx  # noqa: E402


def test_cron_to_kst():
    assert lx.cron_to_kst("33 18 * * *") == "매일 03:33"
    assert lx.cron_to_kst("7 7 * * *") == "매일 16:07"
    assert lx.cron_to_kst("47 20 * * 1") == "매주 화 05:47"
    assert lx.cron_to_kst("13 4 1 * *") == "매월 1일 13:13"
    assert lx.cron_to_kst("*/5 * * * *") == "*/5 * * * *"


WF = """
on:
  schedule:
    - cron: '33 18 * * *'
jobs:
  run:
    steps:
      - name: 의존성 설치
        run: python -m pip install -r requirements.txt
      - name: PBP 수집·적재
        id: pbp
        run: python data_collection/daily_pbp_to_d1.py
      # - name: 꺼 둔 단계
      #   run: python data_collection/old.py
      - name: 결과 기록
        run: |
          python data_collection/record_job_run.py --job pbp \\
            --status ok
          python data_collection/record_job_run.py --job games --status ok
      - name: D1·MySQL 대조
        run: python -m migration.mysql.reconcile --days 3
"""


def test_parse_workflow():
    w = lx.parse_workflow(WF)
    assert w["cron_utc"] == "33 18 * * *"
    assert w["steps"] == [
        {"name": "PBP 수집·적재", "script": "data_collection/daily_pbp_to_d1.py"},
        {"name": "결과 기록", "script": "data_collection/record_job_run.py"},
        {"name": "D1·MySQL 대조", "script": "migration/mysql/reconcile.py"},
    ]


def test_job_keys():
    assert lx.job_keys(WF) == {"pbp", "games"}


def test_schema_tables():
    sql = "CREATE TABLE `games` (\n  `a` INT\n);\nCREATE TABLE `meta_job_runs` (x INT);\n"
    assert lx.schema_tables(sql) == {"games", "meta_job_runs"}
