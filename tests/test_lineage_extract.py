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


INDEX_JS = """
import { json } from './lib/respond.js';
import { standings } from './routes/standings.js';
import {
  playersSearch, playerDetail as detail,
} from './routes/players.js';
router.add('GET', '/', () => json({ ok: 1 }));
router.add('GET', '/standings', standings);
router.add('GET', '/players/search', playersSearch);
router.add('GET', '/players/:id', detail);
router.add('POST', '/admin/purge-cache', purge);
"""


def test_route_files_and_patterns():
    assert lx.route_files(INDEX_JS) == {
        "/standings": "src/routes/standings.js",
        "/players/search": "src/routes/players.js",
        "/players/:id": "src/routes/players.js",
    }
    assert lx.route_patterns(INDEX_JS) == ["/", "/standings", "/players/search", "/players/:id"]


def test_sql_tables():
    js = """
      const a = await db.prepare('SELECT * FROM players WHERE x = ?');
      const b = `SELECT g.a FROM games g JOIN \\`teams\\` t ON 1
                 LEFT JOIN "kbo_roster" r ON 1 WHERE a IN (SELECT 1 FROM nope)`;
      import { x } from './y.js';  // from comments are lower-case and ignored
    """
    assert lx.sql_tables(js, {"players", "games", "teams", "kbo_roster"}) == {
        "players", "games", "teams", "kbo_roster"}


def test_match_route():
    pats = ["/players/search", "/players/:id", "/players/:id/arsenal", "/db/table/:name"]
    assert lx.match_route("/players/${playerId}/arsenal", pats) == "/players/:id/arsenal"
    assert lx.match_route("/players/search", pats) == "/players/search"
    assert lx.match_route("/players/${id}", pats) == "/players/:id"
    assert lx.match_route("/db/table/${name}", pats) == "/db/table/:name"
    assert lx.match_route("/nowhere", pats) is None
    assert lx.match_route("/players/", pats) is None


API_JS = """
class API {
    static async getGames(season = 2025, limit = 50) {
        const response = await fetch(`${API_BASE_URL}/games?season=${season}&limit=${limit}`);
    }
    static async getPitchArsenal(playerId) {
        const response = await fetch(`${API_BASE_URL}/players/${playerId}/arsenal`);
    }
}
"""


def test_api_methods():
    assert lx.api_methods(API_JS) == {
        "getGames": "/games", "getPitchArsenal": "/players/${playerId}/arsenal"}


def test_source_routes_and_tables():
    pats = ["/games", "/players/:id/arsenal", "/db/table/:name", "/stats/seasons"]
    methods = lx.api_methods(API_JS)
    page = """
      const g = await API.getGames(2025);
      const r = await getJson(`${base}/db/table/${name}?limit=500`);
      const s = await getJson(`${base}/stats/seasons`);
      const refs = ['kbo_woba_weights_by_season', "stadium_dim", 'not_a_table'];
      const other = `${dir}/file.txt`;
    """
    assert lx.source_routes(page, pats, methods) == {"/games", "/db/table/:name", "/stats/seasons"}
    assert lx.quoted_tables(page, {"kbo_woba_weights_by_season", "stadium_dim"}) == {
        "kbo_woba_weights_by_season", "stadium_dim"}


def test_page_sources_and_title(tmp_path):
    (tmp_path / "js").mkdir()
    (tmp_path / "pages").mkdir()
    (tmp_path / "js" / "api.js").write_text("x", encoding="utf-8")
    html = ('<title> 팀 통계 | bstats </title>'
            '<script src="../js/api.js"></script>'
            '<script src="https://cdn.example/x.js"></script>'
            '<script src="../js/missing.js"></script>')
    page = tmp_path / "pages" / "team-stats.html"
    # Windows 임시 폴더는 짧은 이름(8.3)·한글 사용자 폴더 때문에 경로 표기가 갈릴 수
    # 있어 양쪽을 resolve() 로 맞춰 비교합니다.
    assert [p.resolve() for p in lx.page_sources(page, html)] == [(tmp_path / "js" / "api.js").resolve()]
    assert lx.page_title(html) == "팀 통계 | bstats"


def test_page_sources_ignores_query_string(tmp_path):
    (tmp_path / "js").mkdir()
    (tmp_path / "pages").mkdir()
    (tmp_path / "js" / "api.js").write_text("x", encoding="utf-8")
    html = '<script src="../js/api.js?v=1.2"></script>'
    page = tmp_path / "pages" / "player-stats.html"
    assert [p.resolve() for p in lx.page_sources(page, html)] == [(tmp_path / "js" / "api.js").resolve()]


def test_source_routes_literal_paths():
    pats = ["/wrc/seasons", "/wrc/by-stadium", "/players/:id"]
    page = """
      const a = await fetchJSON('/wrc/seasons');
      const b = await fetchJSON(`/wrc/by-stadium?season=${s}`);
      const c = await fetchJSON("/players/${id}");
    """
    assert lx.source_routes(page, pats, {}) == {"/wrc/seasons", "/wrc/by-stadium", "/players/:id"}
    neg = """const l = '/pages/team-stats.html'; const i = '/assets/x.png'; const r = '/';"""
    assert lx.source_routes(neg, pats, {}) == set()


def test_source_routes_extra_shapes():
    pats = ["/teams", "/schedule", "/schedule/futures", "/logo/:code", "/db/table/:name/csv"]
    api = (
        "static async getTeams(s) { fetch(`${API_BASE_URL}/teams${q}`); }\n"
        "static dbCsvUrl(name) { return `${API_BASE_URL}/db/table/${encodeURIComponent(name)}/csv`; }\n"
    )
    methods = lx.api_methods(api)
    assert methods["getTeams"] == "/teams${q}"
    assert "dbCsvUrl" in methods
    page = """
      const m = { main: { ep: 'schedule' }, futures: { ep: 'schedule/futures' } };
      const img = `<img src="${API_BASE_URL}/logo/${code}" alt="">`;
      API.getTeams(2025); API.dbCsvUrl(t);
    """
    assert lx.source_routes(page, pats, methods) == set(pats)
