# -*- coding: utf-8 -*-
"""계보 손 파일이 실제 코드와 맞는지 봅니다(설계서 테스트 1~4).

새 워크플로 단계를 더하고 계보를 잊거나, 어떤 작업도 쓰지 않는 표가 생기면
여기서 실패합니다. 2026-10-03 팀 순위표가 한 번 채운 뒤 한 달 넘게 멈춰 있던
일을 다시 놓치지 않으려는 것입니다.
"""
import json
import re
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


import build_lineage as bl  # noqa: E402

OUT = ROOT / "dashboard_js" / "data" / "table_lineage.json"


def test_결과_파일이_지금_코드로_만든_것과_같습니다():
    want = bl.build(ROOT)
    got = json.loads(OUT.read_text(encoding="utf-8"))
    assert got == want, "py scripts/build_lineage.py 로 다시 만드십시오."


def test_결과_모양():
    d = bl.build(ROOT)
    assert d["version"] == 1
    assert [j["id"] for j in d["jobs"]] == ["daily", "monthly", "roster", "weekly"]
    daily = next(j for j in d["jobs"] if j["id"] == "daily")
    assert daily["schedule_kst"] == "매일 03:33" and daily["stale_hours"] == 36
    tr = next(t for t in d["tables"] if t["name"] == "team_season_rank")
    assert tr["kind"] == "collected" and tr["written_by"] == ["data_collection/team_ranks.py"]
    for name in ("games", "players", "play_by_play"):
        assert next(t for t in d["tables"] if t["name"] == name)["kind"] == "collected", name
    wrc = next(t for t in d["tables"] if t["name"] == "wrc_plus_comparison")
    assert wrc["kind"] == "derived" and "play_by_play" in wrc["derived_from"]
    assert {"from": "job:daily", "to": "table:team_season_rank"} in d["edges"]
    assert {"from": "table:play_by_play", "to": "table:wrc_plus_comparison"} in d["edges"]
    # api.js 를 싣기만 하고 부르지 않는 주소가 페이지에 붙지 않습니다.
    stats = next(p for p in d["pages"] if p["path"] == "pages/player-stats.html")
    assert "/db/tables" not in stats["routes"] and "/jobs/status" not in stats["routes"]
    explorer = next(p for p in d["pages"] if p["path"] == "pages/database-explorer.html")
    assert explorer["explorer"] is True
    assert not any(e["to"] == "page:pages/database-explorer.html" for e in d["edges"])
    assert all(t["kind"] == "meta" for t in d["tables"] if t["name"].startswith("meta_"))
    assert not any(e["to"].startswith("table:meta_") or e["from"].startswith("table:meta_")
                   for e in d["edges"])
    # 정렬·결정성
    assert d["edges"] == sorted(d["edges"], key=lambda e: (e["from"], e["to"]))
    assert bl.build(ROOT) == d


def scheduled_workflows():
    """`schedule:` 이 있는 워크플로 파일 이름(확장자 뺌)입니다."""
    base = ROOT / ".github" / "workflows"
    return {p.stem for p in [*base.glob("*.yml"), *base.glob("*.yaml")]
            if re.search(r"^\s*schedule:", p.read_text(encoding="utf-8"), re.M)}


def test_정해진_시각에_도는_워크플로를_모두_봅니다():
    # 새 예약 워크플로를 만들고 계보 목록에 넣지 않으면, 그 작업이 쓰는 표가
    # 조용히 빠집니다.
    assert set(WORKFLOWS) == set(bl.WORKFLOWS) == scheduled_workflows()


def test_작업마다_한국_시각_일정이_있습니다():
    bad = [j["id"] for j in bl.build(ROOT)["jobs"] if not j["schedule_kst"]]
    assert not bad, "cron 을 읽지 못한 작업: %s" % bad


def test_손_파일의_스크립트가_실제_파일입니다():
    missing = sorted(p for p in HAND["scripts"] if not (ROOT / p).is_file())
    assert not missing, "없는 파일: %s" % missing


def test_표를_쓰는_스크립트는_예약_워크플로에서_돕니다():
    # 손 파일에 writes 를 적어도 아무 작업도 부르지 않으면 그 표는 갱신되지 않습니다.
    steps = {s["script"] for w in WORKFLOWS for s in lx.parse_workflow(wf_text(w))["steps"]}
    idle = sorted(p for p, s in HAND["scripts"].items() if s.get("writes") and p not in steps)
    assert not idle, "어떤 예약 워크플로도 부르지 않는 쓰기 스크립트: %s" % idle


def test_받아_오거나_계산하는_표는_실행_기록이_있습니다():
    # 실행 기록이 없으면 화면의 상태 점이 늘 회색이라, 멈춰도 티가 나지 않습니다.
    d = bl.build(ROOT)
    by_path = {s["path"]: s for s in d["scripts"]}
    ok = HAND.get("no_status_ok", {})
    bad = []
    for t in d["tables"]:
        if t["kind"] not in ("collected", "derived") or t["name"] in ok:
            continue
        if not any(by_path[p]["status_keys"].get(w)
                   for p in t["written_by"] for w in by_path[p]["jobs"]):
            bad.append(t["name"])
    assert not bad, (
        "도는 작업에서 실행 기록 키(status_keys)를 남기는 스크립트가 없는 표: %s\n"
        "워크플로에 record_job_run.py 단계를 더하거나 no_status_ok 에 이유를 적으십시오." % bad)
    stale = sorted(set(ok) - {t["name"] for t in d["tables"] if t["kind"] in ("collected", "derived")})
    assert not stale, "no_status_ok 에 받아 오거나 계산하는 표가 아닌 이름: %s" % stale


def test_실행_기록_키가_그_워크플로의_단계와_맞습니다():
    steps = {w: {s["script"] for s in lx.parse_workflow(wf_text(w))["steps"]} for w in WORKFLOWS}
    keys = {w: lx.job_keys(wf_text(w)) for w in WORKFLOWS}
    bad = []
    for p, s in HAND["scripts"].items():
        for w, k in s.get("status_keys", {}).items():
            if w not in keys:
                bad.append("%s: 없는 워크플로 %s" % (p, w))
                continue
            if k not in keys[w]:
                bad.append("%s: %s.yml 이 남기지 않는 키 %s" % (p, w, k))
            if p not in steps[w]:
                bad.append("%s: %s.yml 이 부르지 않는 스크립트" % (p, w))
    assert not bad, bad
    used = {(w, k) for s in HAND["scripts"].values() for w, k in s.get("status_keys", {}).items()}
    exempt = set(HAND.get("job_keys_without_tables", {}))
    unused = sorted("%s.yml: %s" % (w, k) for w in WORKFLOWS for k in keys[w]
                    if (w, k) not in used and k not in exempt)
    assert not unused, (
        "손 파일 어느 스크립트의 status_keys 에도 없는 실행 기록 키: %s\n"
        "그 단계의 스크립트에 적거나, 표와 무관한 키면 job_keys_without_tables 에 이유를 적으십시오."
        % unused)


def test_팀_통계가_참조_표_4개와_주소를_읽습니다():
    # js/stats/data.js 를 다른 페이지도 싣게 되어도(라이브러리) 팀 통계가 부르는
    # loadRefs 의 표 이름과 주소는 팀 통계에 남아야 합니다.
    d = bl.build(ROOT)
    ts = next(p for p in d["pages"] if p["path"] == "pages/team-stats.html")
    assert {"/db/table/:name", "/games", "/standings", "/stats/batters", "/stats/pitchers",
            "/stats/seasons", "/stats/team_range"} <= set(ts["routes"])
    for name in ("kbo_woba_weights_by_season", "self_park_factor",
                 "team_stadium_by_season", "team_season_rank"):
        t = next(x for x in d["tables"] if x["name"] == name)
        assert "pages/team-stats.html" in t["pages"], name


def test_표마다_설명이_있습니다():
    # 계보 탭과 데이터 탐색 페이지가 표 설명을 column_descriptions.json 에서 읽습니다.
    tables = json.loads((ROOT / "database" / "column_descriptions.json")
                        .read_text(encoding="utf-8"))["tables"]
    missing = sorted(t for t in KNOWN if not t.startswith("meta_")
                     and not (tables.get(t, {}).get("table_desc") or "").strip())
    assert not missing, "database/column_descriptions.json 에 table_desc 가 없는 표: %s" % missing


def test_표_항목에_update_freq_를_두지_않습니다():
    # 일정은 jobs[].schedule_kst 하나로 봅니다(손으로 적은 주기 글자와 어긋나지 않게).
    assert not [t["name"] for t in bl.build(ROOT)["tables"] if "update_freq" in t]


def integrity_problems(d):
    """결과 JSON 안의 이름이 서로 가리키는 것이 실제로 있는지 봅니다."""
    out = []
    routes = {r["path"]: r for r in d["routes"]}
    pages = {p["path"]: p for p in d["pages"]}
    scripts = {s["path"] for s in d["scripts"]}
    tables = {t["name"] for t in d["tables"]}
    for p in d["pages"]:
        for r in p["routes"]:
            if r not in routes:
                out.append("페이지 %s 의 주소 %s 가 routes 에 없습니다" % (p["path"], r))
            elif p["path"] not in routes[r]["pages"]:
                out.append("routes[%s].pages 에 %s 가 없습니다" % (r, p["path"]))
    for r in d["routes"]:
        for p in r["pages"]:
            if p not in pages or r["path"] not in pages[p]["routes"]:
                out.append("pages[%s].routes 에 %s 가 없습니다" % (p, r["path"]))
    for t in d["tables"]:
        out += ["표 %s 의 written_by %s 가 scripts 에 없습니다" % (t["name"], s)
                for s in t["written_by"] if s not in scripts]
        out += ["표 %s 의 derived_from %s 가 tables 에 없습니다" % (t["name"], s)
                for s in t["derived_from"] if s not in tables]
    ids = ({"source:" + s["id"] for s in d["sources"]} | {"job:" + j["id"] for j in d["jobs"]}
           | {"table:" + t for t in tables} | {"page:" + p for p in pages})
    out += ["선의 끝 %s 가 없습니다" % x for e in d["edges"] for x in (e["from"], e["to"])
            if x not in ids]
    return out


def test_결과_안의_이름이_서로_맞습니다():
    assert not integrity_problems(bl.build(ROOT))


def test_이름_검사가_어긋남을_잡습니다():
    import copy
    d = bl.build(ROOT)
    breaks = [
        lambda x: x["pages"][0]["routes"].append("/nowhere"),
        lambda x: next(r for r in x["routes"] if r["pages"])["pages"].pop(),
        lambda x: x["tables"][0]["written_by"].append("nope.py"),
        lambda x: x["tables"][0]["derived_from"].append("nope_table"),
        lambda x: x["edges"].append({"from": "job:nope", "to": "table:games"}),
    ]
    for i, brk in enumerate(breaks):
        bad = copy.deepcopy(d)
        brk(bad)
        assert integrity_problems(bad), "어긋남 %d 을 잡지 못했습니다" % i


def test_등록된_GET_주소는_어느_화면이든_씁니다():
    d = bl.build(ROOT)
    used = {r for p in d["pages"] for r in p["routes"]}
    pats = lx.route_patterns((ROOT / "src" / "index.js").read_text(encoding="utf-8"))
    ok = HAND.get("unused_routes", {})
    unused = sorted(p for p in pats if p not in used and p not in ok)
    assert not unused, (
        "어느 화면도 부르지 않는 주소: %s\n화면이 부르는 꼴을 못 읽은 것인지 보고, "
        "정말 안 쓰면 unused_routes 에 이유를 적으십시오." % unused)
    stale = sorted(p for p in ok if p not in pats or p in used)
    assert not stale, "unused_routes 에 있는데 없거나 쓰이는 주소: %s" % stale


def test_표를_읽는_주소는_표가_하나_이상입니다():
    d = bl.build(ROOT)
    ok = HAND.get("routes_without_tables", {})
    empty = sorted(r["path"] for r in d["routes"]
                   if not r["live"] and not r["reads_all_tables"] and not r["tables"]
                   and r["path"] not in ok)
    assert not empty, (
        "표를 하나도 찾지 못한 주소: %s\nSQL 을 못 읽은 것인지 보고, 정말 표가 없으면 "
        "routes_without_tables 에 이유를 적으십시오." % empty)
    stale = sorted(p for p in ok if not any(r["path"] == p and not r["tables"] for r in d["routes"]))
    assert not stale, "routes_without_tables 에 있는데 표가 있거나 없는 주소: %s" % stale
