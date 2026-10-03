# -*- coding: utf-8 -*-
"""테이블 계보 JSON 을 만듭니다.

    py scripts/build_lineage.py

손 파일(database/lineage_writes.json)과 코드에서 뽑은 재료를 합쳐
dashboard_js/data/table_lineage.json 을 씁니다. 데이터 탐색 페이지의
"테이블 계보" 탭이 이 파일을 읽습니다.

작업·표·API·화면을 바꾸면 손 파일을 고치고 이 스크립트를 다시 돌립니다.
잊으면 tests/test_lineage.py 가 실패합니다.
CI 는 pytest 를 돌리지 않습니다. 다시 만든 뒤 `py -m pytest tests` 를 직접 돌리십시오.
설계: docs/superpowers/specs/2026-10-04-table-lineage-design.md
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lineage_extract as lx  # noqa: E402

ROOT = HERE.parent
WORKFLOWS = ["daily", "roster", "weekly", "monthly"]
STALE_HOURS = {"daily": 36, "roster": 36, "weekly": 8 * 24, "monthly": 35 * 24}
EXPLORER_PAGE = "pages/database-explorer.html"
ALL_TABLE_ROUTE_FILES = {"src/routes/dbexplorer.js"}
OUT = ROOT / "dashboard_js" / "data" / "table_lineage.json"


def _read(root, rel):
    return (root / rel).read_text(encoding="utf-8")


def _pages(root):
    """dashboard_js 아래 모든 HTML(하위 폴더 포함)입니다."""
    base = root / "dashboard_js"
    return sorted(base.rglob("*.html"), key=lambda p: p.relative_to(base).as_posix())


def build(root=ROOT):
    root = Path(root)
    hand = json.loads(_read(root, "database/lineage_writes.json"))
    known = lx.schema_tables(_read(root, "migration/mysql/schema.sql"))
    coldict = json.loads(_read(root, "database/column_descriptions.json")).get("tables", {})
    visible = {t for t in known if not t.startswith("meta_")}

    # 작업 → 스크립트
    jobs, script_jobs = [], {}
    for w in WORKFLOWS:
        wf = lx.parse_workflow(_read(root, ".github/workflows/%s.yml" % w))
        steps = []
        for s in wf["steps"]:
            keys = hand["scripts"].get(s["script"], {}).get("status_keys", {})
            steps.append({"name": s["name"], "script": s["script"], "status_key": keys.get(w)})
            script_jobs.setdefault(s["script"], set()).add(w)
        jobs.append({
            "id": w, "workflow": w + ".yml", "cron_utc": wf["cron_utc"],
            "schedule_kst": lx.cron_to_kst(wf["cron_utc"]) if wf["cron_utc"] else None,
            "stale_hours": STALE_HOURS[w], "steps": steps,
        })

    scripts = []
    for path in sorted(hand["scripts"]):
        s = hand["scripts"][path]
        scripts.append({
            "path": path, "jobs": sorted(script_jobs.get(path, [])),
            "sources": sorted(s.get("sources", [])), "writes": sorted(s.get("writes", [])),
            "reads": sorted(s.get("reads", [])), "status_keys": s.get("status_keys", {}),
            "note": s.get("note"),
        })

    # API 주소 → 표
    index_js = _read(root, "src/index.js")
    patterns = lx.route_patterns(index_js)
    files = lx.route_files(index_js)
    live_files = set(hand.get("live_route_files", []))
    route_tables, all_routes, live_routes = {}, set(), set()
    for path, f in files.items():
        if f in ALL_TABLE_ROUTE_FILES:
            all_routes.add(path)
            route_tables[path] = set(visible)
        else:
            route_tables[path] = lx.sql_tables(_read(root, f), visible)
        if f in live_files:
            live_routes.add(path)

    # 화면 → API 주소, 화면이 /db/table/<이름> 으로 읽는 표
    # 여러 페이지가 싣는 JS(와 늘 js/api.js)는 라이브러리입니다. 그 글자를 통째로
    # 넣으면 싣는 페이지마다 쓰지도 않는 주소가 붙습니다. 페이지가 부르는 멤버
    # (API.getGames, TS.data.loadRefs …)의 글자만 셉니다(lx.page_texts).
    page_list = _pages(root)
    texts = lx.page_texts(page_list, always={root / "dashboard_js" / "js" / "api.js"})
    pages, page_routes, page_db = [], {}, {}
    for p in page_list:
        html = p.read_text(encoding="utf-8")
        text = texts[p]
        rel = p.relative_to(root / "dashboard_js").as_posix()
        routes = lx.source_routes(text, patterns)
        page_routes[rel] = routes
        if "/db/table/:name" in routes and rel != EXPLORER_PAGE:
            page_db[rel] = lx.quoted_tables(text, visible)
        pages.append({"path": rel, "title": lx.page_title(html), "routes": sorted(routes),
                      "explorer": rel == EXPLORER_PAGE})

    routes = []
    for path in sorted(route_tables):
        routes.append({
            "path": path, "file": files[path], "tables": sorted(route_tables[path]),
            "reads_all_tables": path in all_routes, "live": path in live_routes,
            "pages": sorted(p for p, rs in page_routes.items() if path in rs),
        })

    # 표
    tables = []
    for t in sorted(known):
        writers = sorted(p for p, s in hand["scripts"].items() if t in s.get("writes", []))
        derived = sorted({r for p in writers for r in hand["scripts"][p].get("reads", [])} - {t})
        t_routes = sorted(r["path"] for r in routes
                          if t in r["tables"] and not r["reads_all_tables"])
        t_pages = {p for r in routes if r["path"] in t_routes for p in r["pages"]}
        t_pages |= {p for p, ts in page_db.items() if t in ts}
        t_pages.discard(EXPLORER_PAGE)
        # 원천에서 받아 오는 스크립트가 하나라도 쓰면 "받아 온 표"입니다. players 는
        # 명단(kbo_roster)에서 소속을 고치기도 하지만 기본은 KBO 선수 페이지에서
        # 받습니다. 원천 없이 다른 표만 읽어 계산하는 표가 "계산 표"입니다.
        collects = any(hand["scripts"][p].get("sources") for p in writers)
        if t.startswith("meta_"):
            kind = "meta"
        elif not writers and t in hand.get("manual_tables", {}):
            kind = "manual"
        elif derived and not collects:
            kind = "derived"
        else:
            kind = "collected"
        meta = coldict.get(t, {})
        tables.append({
            "name": t, "kind": kind, "category": meta.get("category"),
            "desc": meta.get("table_desc"),
            "written_by": writers, "derived_from": derived, "routes": t_routes,
            "pages": sorted(t_pages), "manual_note": hand.get("manual_tables", {}).get(t),
        })

    # 그림의 선(4칸)
    edges = set()
    by_path = {s["path"]: s for s in scripts}
    for j in jobs:
        for step in j["steps"]:
            s = by_path.get(step["script"], {})
            for src in s.get("sources", []):
                edges.add(("source:" + src, "job:" + j["id"]))
            for t in s.get("writes", []):
                if not t.startswith("meta_"):
                    edges.add(("job:" + j["id"], "table:" + t))
    for t in tables:
        if t["kind"] == "meta":
            continue
        for src in t["derived_from"]:
            if not src.startswith("meta_"):
                edges.add(("table:" + src, "table:" + t["name"]))
        for p in t["pages"]:
            edges.add(("table:" + t["name"], "page:" + p))
    for r in routes:
        if r["live"]:
            for p in r["pages"]:
                if p != EXPLORER_PAGE:
                    edges.add(("source:kbo_live", "page:" + p))

    sources = [{"id": k, "name": v["name"], "url": v.get("url")}
               for k, v in sorted(hand["sources"].items())]
    return {
        "version": 1,
        "sources": sources,
        "jobs": sorted(jobs, key=lambda j: j["id"]),
        "scripts": scripts,
        "tables": tables,
        "routes": routes,
        "pages": sorted(pages, key=lambda p: p["path"]),
        "edges": [{"from": a, "to": b} for a, b in sorted(edges)],
    }


def dumps(data):
    return json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(dumps(build(ROOT)), encoding="utf-8", newline="\n")
    print("썼습니다: %s" % OUT.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
