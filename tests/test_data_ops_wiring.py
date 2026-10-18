"""데이터 관리 화면이 기대는 연결(스키마·주간 작업)을 봅니다."""
from pathlib import Path

import yaml

from migration.mysql import record_bq_snapshot as r

ROOT = Path(__file__).resolve().parents[1]


def weekly_steps():
    wf = yaml.safe_load((ROOT / ".github/workflows/weekly.yml").read_text(encoding="utf-8"))
    job = next(iter(wf["jobs"].values()))
    return job["steps"]


def test_schema_sql_에_현황_표가_설계와_같이_있습니다():
    schema = (ROOT / "migration/mysql/schema.sql").read_text(encoding="utf-8")
    assert r.DDL in schema


def test_빅쿼리_복사가_결과_파일을_남깁니다():
    step = next(s for s in weekly_steps() if s.get("id") == "bq_copy")
    assert '--result-json "$RUNNER_TEMP/bq_result.json"' in step["run"]


def test_현황_기록은_복사_뒤에_돌고_실패해도_판정을_바꾸지_않습니다():
    steps = weekly_steps()
    names = [s.get("name") for s in steps]
    i_copy = next(i for i, s in enumerate(steps) if s.get("id") == "bq_copy")
    i_rec = names.index("빅쿼리 현황 기록")
    rec = steps[i_rec]
    assert i_rec > i_copy
    assert rec.get("continue-on-error") is True
    assert rec.get("id") == "bq_snapshot"
    assert "always()" in rec["if"]
    assert "python -m migration.mysql.record_bq_snapshot" in rec["run"]
    assert '[ -f "$RUNNER_TEMP/bq_result.json" ]' in rec["run"]


def test_요약에_현황_기록_줄이_있습니다():
    summary = next(s for s in weekly_steps() if s.get("name") == "요약")
    assert "| 빅쿼리 현황 기록 | ${{ steps.bq_snapshot.outcome }} |" in summary["run"]


import json
import re


def test_이력_파일_모양():
    data = json.loads((ROOT / "dashboard_js/data/source_history.json").read_text(encoding="utf-8"))
    lin = json.loads((ROOT / "dashboard_js/data/table_lineage.json").read_text(encoding="utf-8"))
    ids = {s["id"] for s in lin["sources"]}
    assert data["events"]
    for e in data["events"]:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", e["date"])
        assert e["kind"] in {"중단", "대체", "재개", "알림"}
        assert set(e.get("sources", [])) <= ids
        assert e["what"] and e["reason"]


def test_페이지는_KBO_주소를_싣지_않고_api_js_를_쓰지_않습니다():
    page = (ROOT / "dashboard_js/pages/data-ops.html").read_text(encoding="utf-8")
    view = (ROOT / "dashboard_js/js/dataops/view.js").read_text(encoding="utf-8")
    hist = (ROOT / "dashboard_js/data/source_history.json").read_text(encoding="utf-8")
    for text in (page, view, hist):
        assert "koreabaseball" not in text
    assert "js/api.js" not in page
    for src in ("../js/config.js", "../js/lineage/model.js", "../js/dataops/model.js", "../js/dataops/view.js"):
        assert src in page
    assert "'/ops/storage'" in view and "'/jobs/status'" in view
