/*
 * 팀·선수 통계 데이터 받기입니다.
 *
 * 응답이 이상하면(HTTP 오류, detail·error 필드, 빈 목록) 가리지 않고
 * errors 에 이유를 담아 돌려줍니다. 화면은 그것을 표 위에 알립니다.
 * 실패한 응답은 sessionStorage 에 넣지 않습니다.
 * 넣어 둔 값은 6시간이 지나면 다시 받습니다(CACHE_TTL_MS).
 */
(function (root) {
  'use strict';
  const TS = root.TeamStats = root.TeamStats || {};

  /** 응답이 이상하면 이유, 괜찮으면 null 입니다. listKey 가 있으면 그 목록이 비어도 이상입니다. */
  function badReason(json, listKey) {
    if (json === null || json === undefined || typeof json !== 'object') return '응답이 비어 있습니다';
    if (json.detail) return String(json.detail);
    if (json.error) return String(json.error);
    if (listKey) {
      const v = json[listKey];
      if (!Array.isArray(v)) return `${listKey} 목록이 없습니다`;
      if (!v.length) return `${listKey} 목록이 비어 있습니다`;
    }
    return null;
  }

  async function getJson(url, listKey, fetchImpl) {
    const f = fetchImpl || root.fetch.bind(root);
    try {
      const res = await f(url);
      if (!res.ok) return { ok: false, error: `HTTP ${res.status}` };
      const json = await res.json();
      const why = badReason(json, listKey);
      return why ? { ok: false, error: why } : { ok: true, data: json };
    } catch (e) {
      return { ok: false, error: String((e && e.message) || e) };
    }
  }

  function storeOf(opts) {
    if (opts && opts.store) return opts.store;
    try { return root.sessionStorage || null; } catch (e) { return null; }
  }
  function nowOf(opts) {
    return opts && typeof opts.now === 'number' ? opts.now : Date.now();
  }

  // 저장 캐시 유효기간입니다. 탭을 오래 열어 두어도 시즌 목록·참조 표가 반나절 넘게 낡지 않게 둡니다.
  const CACHE_TTL_MS = 6 * 3600000;

  // 저장 모양은 { t: 넣은 시각(ms), v: 값 } 입니다. 유효기간이 지났거나 모양이 다르면 없는 것으로 봅니다.
  function cacheGet(key, opts) {
    try {
      const s = storeOf(opts);
      const raw = s ? s.getItem(key) : null;
      if (!raw) return null;
      const o = JSON.parse(raw);
      if (!o || typeof o !== 'object' || typeof o.t !== 'number' || !('v' in o)) return null;
      const age = nowOf(opts) - o.t;
      return age >= 0 && age < CACHE_TTL_MS ? o.v : null;
    } catch (e) { return null; }
  }
  function cacheSet(key, val, opts) {
    try {
      const s = storeOf(opts);
      if (s) s.setItem(key, JSON.stringify({ t: nowOf(opts), v: val }));
    } catch (e) { /* 저장 공간이 없으면 넘어갑니다 */ }
  }

  // 시즌과 상관없는 참조 표입니다. 데이터 탐색 주소(/db/table)로 받습니다.
  // 팀 통계용 전용 주소가 생기면 여기만 바꿉니다(설계 문서 10장).
  const REF_TABLES = {
    weights: 'kbo_woba_weights_by_season',
    pf: 'self_park_factor',
    stadium: 'team_stadium_by_season',
    rank: 'team_season_rank',
  };
  const REF_LABEL = { weights: 'wOBA 가중치', pf: '파크팩터', stadium: '팀 홈구장', rank: '순위표' };

  // /db/table 은 한 번에 500행까지 줍니다(서버 상한). 표가 커져도 잘리지 않게 끝까지 이어 받습니다.
  const PAGE_ROWS = 500;
  // 2만 행에서 멈춥니다. 서버가 offset 을 무시해 같은 쪽을 계속 주더라도 끝없이 돌지 않게 합니다.
  const MAX_PAGES = 40;

  /**
   * /db/table/<name> 을 500행씩 끝까지 받습니다. 반환 { ok: true, data: 행 목록 } | { ok: false, error }.
   * 응답의 total 에 닿거나 덜 찬 쪽이 오면 멈춥니다. 중간 쪽이 실패하면 표 전체를 실패로
   * 돌려줍니다(반쪽 표를 쓰지 않음). 첫 쪽이 비면 실패입니다(지금까지와 같음).
   */
  async function getTable(base, name, opts) {
    opts = opts || {};
    const rows = [];
    for (let i = 0; i < MAX_PAGES; i++) {
      const offset = i * PAGE_ROWS;
      const r = await getJson(`${base}/db/table/${name}?limit=${PAGE_ROWS}&offset=${offset}`, i === 0 ? 'rows' : null, opts.fetch);
      if (!r.ok) return { ok: false, error: i === 0 ? r.error : `${r.error} · ${offset + 1}행부터` };
      const page = r.data.rows;
      if (!Array.isArray(page)) return { ok: false, error: `rows 목록이 없습니다 · ${offset + 1}행부터` };
      for (const row of page) rows.push(row);
      const total = r.data.total;
      if (page.length < PAGE_ROWS || (typeof total === 'number' && rows.length >= total)) return { ok: true, data: rows };
    }
    return { ok: false, error: `${PAGE_ROWS * MAX_PAGES}행이 넘어 끝까지 받지 못했습니다` };
  }

  async function loadRefs(base, opts) {
    opts = opts || {};
    const out = { errors: [] };
    await Promise.all(Object.keys(REF_TABLES).map(async function (k) {
      const name = REF_TABLES[k];
      const key = `ts_ref_${name}_v2`;
      const hit = cacheGet(key, opts);
      if (Array.isArray(hit) && hit.length) { out[k] = hit; return; }
      const r = await getTable(base, name, opts);
      if (r.ok) {
        out[k] = r.data;
        cacheSet(key, r.data, opts);
      } else {
        out[k] = [];
        out.errors.push({ what: REF_LABEL[k], error: r.error });
      }
    }));
    return out;
  }

  // 주소는 지금 페이지(API.getBatterStats(season, 2000, 0, ''))와 같게 둡니다.
  // 같은 주소라야 엣지 캐시를 같이 씁니다.
  async function loadSeason(base, season, opts) {
    opts = opts || {};
    const res = await Promise.all([
      getJson(`${base}/stats/batters?season=${season}&limit=2000&min_pa=0`, 'batters', opts.fetch),
      getJson(`${base}/stats/pitchers?season=${season}&limit=2000&min_ip=0`, 'pitchers', opts.fetch),
    ]);
    const b = res[0], p = res[1];
    const errors = [];
    if (!b.ok) errors.push({ what: '타자 기록', error: b.error });
    if (!p.ok) errors.push({ what: '투수 기록', error: p.error });
    return { batters: b.ok ? b.data.batters : [], pitchers: p.ok ? p.data.pitchers : [], errors: errors };
  }

  async function loadGames(base, season, opts) {
    const r = await getJson(`${base}/games?season=${season}&limit=1000`, 'games', (opts || {}).fetch);
    return { games: r.ok ? r.data.games : [], errors: r.ok ? [] : [{ what: '경기 결과', error: r.error }] };
  }

  // 기간에 경기가 없으면 빈 목록이 정상이라 listKey 를 주지 않습니다.
  async function loadRange(base, start, end, opts) {
    const url = `${base}/stats/team_range?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`;
    const r = await getJson(url, null, (opts || {}).fetch);
    return { data: r.ok ? r.data : null, errors: r.ok ? [] : [{ what: '기간별 기록', error: r.error }] };
  }

  /**
   * 실시간 순위(올해)입니다. 저장된 순위표는 시즌 중 갱신이 늦을 수 있어
   * 올해는 이것을 씁니다. 이 주소는 실패해도 200 과 error 필드를 줍니다.
   */
  async function loadStandings(base, opts) {
    const r = await getJson(`${base}/standings`, 'teams', (opts || {}).fetch);
    return { teams: r.ok ? r.data.teams : [], errors: r.ok ? [] : [{ what: '실시간 순위', error: r.error }] };
  }

  /**
   * 시즌 목록을 못 받았을 때 쓰는 목록입니다. 한국 시각 올해부터(4월 전이면 작년부터) 1982 까지입니다.
   * 4월 전에는 새 시즌 기록이 아직 없어, 빈 시즌이 기본으로 뜨지 않게 합니다.
   * (js/stats/season.js 를 싣지 않는 페이지도 이 파일을 써서 한국 시각을 여기서 셉니다.)
   */
  function fallbackSeasons(now) {
    const t = new Date((typeof now === 'number' ? now : Date.now()) + 9 * 3600000);
    const top = t.getUTCMonth() < 3 ? t.getUTCFullYear() - 1 : t.getUTCFullYear();
    const list = [];
    for (let y = top; y >= 1982; y--) list.push(y);
    return list;
  }

  /** 공식 기록이 있는 시즌(내림차순)과 오류 목록입니다. 실패하면 fallbackSeasons 와 오류 한 건을 돌려줍니다. */
  async function loadSeasons(base, opts) {
    opts = opts || {};
    const KEY = 'teamstats_seasons_v3';
    const desc = list => list.map(Number).filter(Number.isFinite).sort((a, b) => b - a);
    const hit = cacheGet(KEY, opts);
    if (Array.isArray(hit) && hit.length) return { seasons: desc(hit), errors: [] };
    const r = await getJson(`${base}/stats/seasons`, 'seasons', opts.fetch);
    if (r.ok) {
      cacheSet(KEY, r.data.seasons, opts);
      return { seasons: desc(r.data.seasons), errors: [] };
    }
    return { seasons: fallbackSeasons(nowOf(opts)), errors: [{ what: '시즌 목록', error: r.error }] };
  }

  /**
   * 시즌별 공통 규정(/stats/regulation)입니다. 순위표에 없는 팀이 있을 때만
   * 씁니다. 모양: { 'YYYY': { team_games, qual_pa, qual_ip } }
   */
  async function loadRegulation(base, opts) {
    const r = await getJson(`${base}/stats/regulation`, null, (opts || {}).fetch);
    const reg = r.ok ? r.data.regulation : null;
    if (reg && typeof reg === 'object' && !Array.isArray(reg)) return { regulation: reg, errors: [] };
    return { regulation: {}, errors: [{ what: '규정 기준', error: r.ok ? 'regulation 이 없습니다' : r.error }] };
  }

  const api = { CACHE_TTL_MS, badReason, getJson, getTable, loadRefs, loadSeason, loadGames, loadRange, loadStandings, loadSeasons, fallbackSeasons, loadRegulation };
  TS.data = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
