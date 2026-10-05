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


def test_cron_to_kst_month_end_rollover_keeps_raw():
    # 28일 이후에 한국 시각으로 날을 넘기면 "32일" 같은 없는 날이 나옵니다.
    assert lx.cron_to_kst("30 20 28 * *") == "30 20 28 * *"
    assert lx.cron_to_kst("30 20 31 * *") == "30 20 31 * *"
    assert lx.cron_to_kst("30 10 28 * *") == "매월 28일 19:30"
    assert lx.cron_to_kst("30 20 27 * *") == "매월 28일 05:30"


def test_parse_workflow_cron_double_quotes():
    assert lx.parse_workflow('on:\n  schedule:\n    - cron: "47 20 * * 1"\n')["cron_utc"] == "47 20 * * 1"


WF_FORMS = """
on:
  schedule:
    - cron: '33 18 * * *'
jobs:
  run:
    steps:
      - name: 여러 꼴
        run: |
          python -u data_collection/a.py --x 1
          python3.12 data_collection/b.py
          python -X utf8 ./data_collection/c.py
          python \
            data_collection/d.py --flag
          python -X utf8 -m migration.mysql.e --days 3
          python -m pip install -r requirements.txt  # pip 은 뺍니다 z.py
      - name: MySQL 연결
        run: bash migration/mysql/ci_proxy.sh
"""


def test_parse_workflow_interpreter_forms():
    w = lx.parse_workflow(WF_FORMS)
    assert w["steps"] == [
        {"name": "여러 꼴", "script": "data_collection/a.py"},
        {"name": "여러 꼴", "script": "data_collection/b.py"},
        {"name": "여러 꼴", "script": "data_collection/c.py"},
        {"name": "여러 꼴", "script": "data_collection/d.py"},
        {"name": "여러 꼴", "script": "migration/mysql/e.py"},
        {"name": "MySQL 연결", "script": "migration/mysql/ci_proxy.sh"},
    ]


WF_NAMES = """
jobs:
  run:
    steps:
      - name: 첫 단계
        run: python a.py
      - run: python b.py
      - id: c
        name: 셋째 단계
        run: python c.py
      - id: d
        run: python d.py
      - name: 올리기
        uses: actions/upload-artifact@v4
        with:
          name: not-a-step-name
      - run: python e.py
"""


def test_parse_workflow_step_name_resets_per_item():
    # 이름 없는 단계가 앞 단계의 이름을 물려받지 않습니다.
    assert lx.parse_workflow(WF_NAMES)["steps"] == [
        {"name": "첫 단계", "script": "a.py"},
        {"name": None, "script": "b.py"},
        {"name": "셋째 단계", "script": "c.py"},
        {"name": None, "script": "d.py"},
        {"name": None, "script": "e.py"},
    ]


# 두 페이지가 같이 싣는 라이브러리입니다(js/stats/data.js 와 같은 꼴). 주석·정규식의
# 따옴표, 안쪽 화살표 함수, 내보내기 객체가 계보를 흐리지 않아야 합니다.
LIB_DATA = """
(function (root) {
  'use strict';
  const TS = root.TeamStats = root.TeamStats || {};
  function clean(s) { return String(s).replace(/["'{]/g, ''); }  // it's a regex
  async function getJson(url, listKey) { const res = await fetch(url); return res.json(); }
  const REF_TABLES = {
    weights: 'kbo_woba_weights_by_season',
    pf: 'self_park_factor',
  };
  async function loadRefs(base, opts) {
    const out = {};
    await Promise.all(Object.keys(REF_TABLES).map(async function (k) {
      const name = REF_TABLES[k];
      const r = await getJson(`${base}/db/table/${name}?limit=500`, 'rows');
      out[k] = r;
    }));
    return out;
  }
  async function loadGames(base, season) {
    const desc = list => list.sort((a, b) => b - a);
    const r = await getJson(`${base}/games?season=${season}`, 'games');
    return desc(r.games);
  }
  /** 규정(/stats/regulation)입니다. Don't read 'stadium_dim' here. */
  async function loadRegulation(base) {
    return getJson(`${base}/stats/regulation`, null);
  }
  const api = { clean, getJson, loadRefs, loadGames, loadRegulation };
  TS.data = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
"""

LIB_NAV = """
function init() { fetch('/standings'); }
function loadAll() { return fetch('/db/tables'); }
document.addEventListener('DOMContentLoaded', init);
if (typeof module !== 'undefined') module.exports = { init, loadAll };
"""


def _site(tmp_path, files):
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp_path


def test_page_texts_library_members_go_only_to_callers(tmp_path):
    site = _site(tmp_path, {
        "js/data.js": LIB_DATA,
        "js/nav.js": LIB_NAV,
        # 한 페이지만 싣는 파일은 라이브러리가 아니라 그 페이지 코드입니다.
        "js/a-page.js": "function unused() { return fetch(`${B}/stats/regulation`); }",
        "pages/a.html": ('<script src="../js/nav.js"></script><script src="../js/data.js"></script>'
                         '<script src="../js/a-page.js"></script>'
                         '<script>const D = TS.data; D.loadGames(base, 2025);</script>'),
        "pages/b.html": ('<script src="../js/nav.js"></script><script src="../js/data.js"></script>'
                         '<script>TS.data.loadRefs(base);</script>'),
    })
    a, b = site / "pages" / "a.html", site / "pages" / "b.html"
    texts = lx.page_texts([a, b])
    pats = ["/games", "/db/table/:name", "/stats/regulation", "/standings", "/db/tables"]
    known = {"kbo_woba_weights_by_season", "self_park_factor", "games", "stadium_dim"}
    # 맨 위 코드가 넘기는 콜백(init)은 모든 페이지 몫이고, 내보내기 객체에만 있는
    # 멤버(loadAll)는 아무 페이지에도 붙지 않습니다.
    assert lx.source_routes(texts[a], pats, {}) == {"/games", "/stats/regulation", "/standings"}
    # 'games' 는 a 가 부르는 loadGames 안의 글자입니다. 주석 속 'stadium_dim' 은 셈하지 않습니다.
    assert lx.quoted_tables(texts[a], known) == {"games"}
    assert lx.source_routes(texts[b], pats, {}) == {"/db/table/:name", "/standings"}
    assert lx.quoted_tables(texts[b], known) == {"kbo_woba_weights_by_season", "self_park_factor"}


LIB_FORMS = """
function plain() { return fetch(`${B}/r1`); }
async function asyncFn() { return fetch(`${B}/r2`); }
class Api {
    static async method(a = 1, b = f(2)) { return fetch(`${B}/r3`); }
}
const obj = {
    colon: function (x) { return fetch(`${B}/r4`); },
    arrow: async (x) => fetch(`${B}/r5`),
};
const assigned = (x) => { return fetch(`${B}/r6`); };
const assignedAsync = async (x) => fetch(`${B}/r7`);
"""


def test_page_texts_member_forms(tmp_path):
    site = _site(tmp_path, {
        "js/lib.js": LIB_FORMS,
        "pages/a.html": ('<script src="../js/lib.js"></script>'
                         '<script>plain(); Api.method(); obj.arrow(1); assignedAsync(2);'
                         ' function asyncFn() {}</script>'),
        "pages/b.html": ('<script src="../js/lib.js"></script>'
                         '<script>asyncFn(); obj.colon(1); assigned(3);</script>'),
    })
    a, b = site / "pages" / "a.html", site / "pages" / "b.html"
    texts = lx.page_texts([a, b])
    pats = ["/r1", "/r2", "/r3", "/r4", "/r5", "/r6", "/r7"]
    # a 의 `function asyncFn() {}` 는 정의라 부른 것으로 치지 않습니다.
    assert lx.source_routes(texts[a], pats, {}) == {"/r1", "/r3", "/r5", "/r7"}
    assert lx.source_routes(texts[b], pats, {}) == {"/r2", "/r4", "/r6"}


def test_page_texts_api_js_is_always_a_library(tmp_path):
    site = _site(tmp_path, {
        "js/api.js": API_JS,
        "pages/x.html": '<script src="../js/api.js"></script><script>API.getGames(2025);</script>',
    })
    x = site / "pages" / "x.html"
    texts = lx.page_texts([x], always={(site / "js" / "api.js").resolve()})
    assert lx.source_routes(texts[x], ["/games", "/players/:id/arsenal"], {}) == {"/games"}


def test_예약_시각이_여럿이면_모두_읽습니다():
    # roster 는 GitHub 가 예약 실행을 빼먹는 날이 있어 하루 두 번 돕니다(2026-10-05).
    text = ("on:\n  schedule:\n    - cron: '7 7 * * *'\n    - cron: '7 10 * * *'\n"
            "  # - cron: '0 0 * * *'  (주석은 빼고 봅니다)\n")
    w = lx.parse_workflow(text)
    assert w["crons"] == ["7 7 * * *", "7 10 * * *"]
    assert w["cron_utc"] == "7 7 * * *"
    assert lx.schedule_kst(w["crons"]) == "매일 16:07·19:07"
    assert lx.schedule_kst(["33 18 * * *"]) == "매일 03:33"
    assert lx.schedule_kst(["47 20 * * 1", "7 7 * * *"]) == "매주 화 05:47 · 매일 16:07"
    assert lx.schedule_kst([]) is None
