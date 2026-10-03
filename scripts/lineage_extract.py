# -*- coding: utf-8 -*-
"""테이블 계보의 재료를 코드에서 뽑습니다.

설계: docs/superpowers/specs/2026-10-04-table-lineage-design.md

뽑기 쉬운 것만 여기서 뽑습니다. 수집 스크립트가 어떤 표에 쓰는지는 SQL 을
조립해 만드는 곳이 많아 기계로 뽑으면 틀리기 쉽습니다. 그건 손 파일
(database/lineage_writes.json)에 적고, 테스트가 실제 코드와 맞는지 봅니다.
"""
import re

DOW = ["일", "월", "화", "수", "목", "금", "토"]

CRON = re.compile(r"cron:\s*'([^']+)'")
STEP = re.compile(r"^\s*-\s*name:\s*(.+?)\s*$")
PY_CALL = re.compile(r"\bpython3?\s+(?:-m\s+([A-Za-z_][\w.]*)|([A-Za-z0-9_./-]+\.py))")
JOB_KEY = re.compile(r"record_job_run\.py\s+--job\s+([a-z_]+)")
TABLE = re.compile(r"CREATE TABLE `([A-Za-z0-9_]+)`")


def cron_to_kst(cron):
    """UTC cron 다섯 칸을 한국 시각 문구로 바꿉니다. 모르는 꼴이면 원문 그대로입니다.

    한국은 UTC+9 이고 서머타임이 없습니다. 9시간을 더해 날을 넘기면 요일·날짜도
    하루 밉니다(weekly 의 월 20:47 UTC 는 한국 화 05:47).
    """
    parts = cron.split()
    if len(parts) != 5:
        return cron
    mi, hr, dom, mon, dow = parts
    if not (mi.isdigit() and hr.isdigit()) or mon != "*":
        return cron
    h = int(hr) + 9
    next_day = h >= 24
    hm = "%02d:%02d" % (h % 24, int(mi))
    if dom == "*" and dow == "*":
        return "매일 " + hm
    if dom == "*" and dow.isdigit():
        return "매주 %s %s" % (DOW[(int(dow) + (1 if next_day else 0)) % 7], hm)
    if dow == "*" and dom.isdigit():
        return "매월 %d일 %s" % (int(dom) + (1 if next_day else 0), hm)
    return cron


def parse_workflow(text):
    """워크플로 YAML 글자에서 실행 시각과 (단계 이름, 스크립트) 목록을 뽑습니다.

    `python 경로.py` 와 `python -m 모듈` 을 모두 스크립트로 봅니다(모듈은 경로로
    바꿈). `pip` 은 뺍니다. 주석 줄(#)은 건너뜁니다. 같은 (단계, 스크립트)는
    한 번만 넣습니다.
    """
    m = CRON.search(text)
    steps, seen, name = [], set(), None
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        s = STEP.match(line)
        if s:
            name = s.group(1).strip().strip("'\"")
            continue
        for mod, path in PY_CALL.findall(line):
            if mod == "pip":
                continue
            script = mod.replace(".", "/") + ".py" if mod else path
            if (name, script) not in seen:
                seen.add((name, script))
                steps.append({"name": name, "script": script})
    return {"cron_utc": m.group(1) if m else None, "steps": steps}


def job_keys(text):
    """워크플로가 `record_job_run.py --job <키>` 로 남기는 실행 기록 키입니다."""
    return set(JOB_KEY.findall(text))


def schema_tables(schema_sql):
    """MySQL 스키마(migration/mysql/schema.sql)의 표 이름입니다."""
    return set(TABLE.findall(schema_sql))
