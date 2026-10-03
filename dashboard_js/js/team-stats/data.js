/*
 * 팀 통계 데이터 받기입니다.
 *
 * 응답이 이상하면(HTTP 오류, detail·error 필드, 빈 목록) 가리지 않고
 * errors 에 이유를 담아 돌려줍니다. 화면은 그것을 표 위에 알립니다.
 * 실패한 응답은 sessionStorage 에 넣지 않습니다.
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
  function cacheGet(key, opts) {
    try {
      const s = storeOf(opts);
      const v = s ? s.getItem(key) : null;
      return v ? JSON.parse(v) : null;
    } catch (e) { return null; }
  }
  function cacheSet(key, val, opts) {
    try {
      const s = storeOf(opts);
      if (s) s.setItem(key, JSON.stringify(val));
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

  async function loadRefs(base, opts) {
    opts = opts || {};
    const out = { errors: [] };
    await Promise.all(Object.keys(REF_TABLES).map(async function (k) {
      const name = REF_TABLES[k];
      const key = `ts_ref_${name}_v1`;
      const hit = cacheGet(key, opts);
      if (Array.isArray(hit) && hit.length) { out[k] = hit; return; }
      const r = await getJson(`${base}/db/table/${name}?limit=500`, 'rows', opts.fetch);
      if (r.ok) {
        out[k] = r.data.rows;
        cacheSet(key, r.data.rows, opts);
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

  /** 공식 기록이 있는 시즌(내림차순)과 오류 목록입니다. 실패하면 올해~1982 와 오류 한 건을 돌려줍니다. */
  async function loadSeasons(base, opts) {
    opts = opts || {};
    const KEY = 'teamstats_seasons_v2';
    const desc = list => list.map(Number).filter(Number.isFinite).sort((a, b) => b - a);
    const hit = cacheGet(KEY, opts);
    if (Array.isArray(hit) && hit.length) return { seasons: desc(hit), errors: [] };
    const r = await getJson(`${base}/stats/seasons`, 'seasons', opts.fetch);
    if (r.ok) {
      cacheSet(KEY, r.data.seasons, opts);
      return { seasons: desc(r.data.seasons), errors: [] };
    }
    const list = [];
    for (let y = new Date().getFullYear(); y >= 1982; y--) list.push(y);
    return { seasons: list, errors: [{ what: '시즌 목록', error: r.error }] };
  }

  const api = { badReason, getJson, loadRefs, loadSeason, loadGames, loadRange, loadStandings, loadSeasons };
  TS.data = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
