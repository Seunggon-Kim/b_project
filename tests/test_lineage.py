# -*- coding: utf-8 -*-
"""계보 손 파일이 실제 코드와 맞는지 봅니다(설계서 테스트 1~4).

새 워크플로 단계를 더하고 계보를 잊거나, 어떤 작업도 쓰지 않는 표가 생기면
여기서 실패합니다. 2026-10-03 팀 순위표가 한 번 채운 뒤 한 달 넘게 멈춰 있던
일을 다시 놓치지 않으려는 것입니다.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import lineage_extract as lx  # noqa: E402

WORKFLOWS = ["daily", "roster", "weekly", "monthly"]
HAND = json.loads((ROOT / "database" / "lineage_writes.json").read_text(encoding="utf-8"))
KNOWN = lx.schema_tables((ROOT / "migration" / "mysql" / "schema.sql").read_text(encoding="utf-8"))


def wf_text(name):
    return (ROOT / ".github" / "workflows" / (name + ".yml")).read_text(encoding="utf-8")


def test_워크플로가_부르는_스크립트가_손_파일에_다_있습니다():
    missing = []
    for w in WORKFLOWS:
        for s in lx.parse_workflow(wf_text(w))["steps"]:
            if s["script"] not in HAND["scripts"]:
                missing.append("%s: %s" % (w, s["script"]))
    assert not missing, "database/lineage_writes.json 에 없는 스크립트: %s" % missing


def test_손_파일의_표_이름이_실제_표입니다():
    bad = set()
    for path, s in HAND["scripts"].items():
        bad |= {t for t in s.get("writes", []) + s.get("reads", []) if t not in KNOWN}
    bad |= {t for t in HAND.get("manual_tables", {}) if t not in KNOWN}
    assert not bad, "schema.sql 에 없는 표: %s" % sorted(bad)


def test_어떤_작업도_쓰지_않는_표가_없습니다():
    written = set()
    for s in HAND["scripts"].values():
        written |= set(s.get("writes", []))
    orphans = sorted(t for t in KNOWN
                     if not t.startswith("meta_")
                     and t not in written and t not in HAND.get("manual_tables", {}))
    assert not orphans, (
        "쓰는 스크립트도 손 작업 설명도 없는 표: %s\n"
        "수집 작업이 쓰면 scripts 의 writes 에, 손으로 채운 표면 manual_tables 에 이유와 함께 적으십시오."
        % orphans)


def test_실행_기록_키가_워크플로에_있습니다():
    keys = set()
    for w in WORKFLOWS:
        keys |= lx.job_keys(wf_text(w))
    bad = sorted({k for s in HAND["scripts"].values() for k in s.get("status_keys", {}).values()} - keys)
    assert not bad, "record_job_run.py --job 에 없는 키: %s" % bad


def test_원천_id_와_외부_API_파일이_있습니다():
    ids = set(HAND["sources"])
    bad = sorted({sid for s in HAND["scripts"].values() for sid in s.get("sources", [])} - ids)
    assert not bad, "sources 에 정의되지 않은 원천: %s" % bad
    for f in HAND.get("live_route_files", []):
        assert (ROOT / f).exists(), f


def test_스크립트가_자기가_쓰는_표를_읽는다고_적지_않습니다():
    bad = sorted("%s: %s" % (p, t) for p, s in HAND["scripts"].items()
                 for t in set(s.get("reads", [])) & set(s.get("writes", [])))
    assert not bad, "reads 에는 계산에 들어가는 다른 표만 적습니다: %s" % bad
