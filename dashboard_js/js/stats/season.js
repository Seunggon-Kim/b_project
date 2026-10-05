/*
 * 시즌 진행 중 판단입니다(2027 대비 시즌 하드코딩 정리).
 *
 * 진행 중 = 정규시즌이 끝날 때까지입니다. 시즌 Y 는 (Y = 한국 시각 올해)이고
 * (Y 의 가장 최근 경기가 '정규시즌')이면 진행 중입니다. 그해 포스트시즌 첫
 * 경기가 들어오면 끝난 시즌입니다(정규시즌 기록은 그때부터 바뀌지 않음).
 * 순위결정전은 '정규시즌'으로 들어옵니다. 판단은 화면에서 하고 API 는 그대로 둡니다.
 *
 * 위쪽 순수 함수는 Node 로 검증하고, loadSeasonState 만 서버(/games)를 부릅니다.
 * data.js 에 기대지 않아 어느 페이지에서나 혼자 실을 수 있습니다.
 * 근거: docs/superpowers/specs/2026-10-05-season-hardcoding-cleanup-design.md
 */
(function (root) {
  'use strict';
  const TS = root.TeamStats = root.TeamStats || {};

  // /games 에서 한 번에 받을 경기 수입니다. 포스트시즌(많아야 20경기쯤)을 넘어 마지막
  // 정규시즌 경기까지 닿고, 시즌이 2주쯤 지나기 전이면 첫 경기까지 다 들어옵니다.
  const LIMIT = 80;
  const KST_OFFSET_MS = 9 * 3600000;
  // 진행 중 판단을 못 받았을 때 팀·선수 통계 알림 줄에 띄우는 말입니다(설계 6장).
  const FAIL_TEXT = '진행 중 여부를 확인하지 못해 올해 시즌을 진행 중으로 봅니다.';

  const z = n => String(n).padStart(2, '0');

  /** 한국 시각 오늘 { y, m, d, iso: 'YYYY-MM-DD' } 입니다. now 는 ms 숫자나 Date(없으면 지금)입니다. */
  function kstToday(now) {
    let ms = Date.now();
    if (typeof now === 'number') ms = now;
    else if (now && typeof now.getTime === 'function') ms = now.getTime();
    const t = new Date(ms + KST_OFFSET_MS);
    const y = t.getUTCFullYear(), m = t.getUTCMonth() + 1, d = t.getUTCDate();
    return { y: y, m: m, d: d, iso: `${y}-${z(m)}-${z(d)}` };
  }

  /** 경기 날짜(YYYYMMDD) → 'YYYY-MM-DD' 입니다. 모양이 다르면 null 입니다. */
  function isoOf(n) {
    const s = String(n === null || n === undefined ? '' : n);
    return /^\d{8}$/.test(s) ? `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}` : null;
  }

  /**
   * 진행 중인지입니다(순수). state = { kstYear, lastGame }.
   * season 이 한국 시각 올해이고, lastGame 이 그 시즌의 '정규시즌' 경기면 true 입니다.
   */
  function isLive(season, state) {
    const y = Number(season);
    const g = state && state.lastGame;
    return !!g && y === state.kstYear && Number(g.season) === y && g.game_type === '정규시즌';
  }

  /**
   * /games?season=Y 의 경기 목록을 요약합니다(순수). 서버는 최신순으로 주지만 순서에 기대지 않습니다.
   * 반환 { live, lastGame, lastRegularDate, firstDate }
   *   lastGame: 가장 최근 경기(없으면 null)
   *   lastRegularDate: 가장 최근 '정규시즌' 경기 날짜 'YYYY-MM-DD'(없으면 null)
   *   firstDate: 받은 경기가 LIMIT 보다 적으면(시즌 처음부터 다 받음) 가장 이른 날짜, 아니면 null
   */
  function summarize(season, games, kstYear) {
    const raw = Array.isArray(games) ? games : [];
    const list = raw.filter(g => g && isoOf(g.game_date))
      .sort((a, b) => Number(b.game_date) - Number(a.game_date));
    const lastGame = list.length ? list[0] : null;
    const reg = list.find(g => g.game_type === '정규시즌');
    return {
      live: isLive(season, { kstYear: kstYear, lastGame: lastGame }),
      lastGame: lastGame,
      lastRegularDate: reg ? isoOf(reg.game_date) : null,
      firstDate: list.length && raw.length < LIMIT ? isoOf(list[list.length - 1].game_date) : null,
    };
  }

  /**
   * 그 시즌의 진행 중 판단 재료를 받습니다(브라우저). /games?season=Y&limit=80 한 번입니다.
   * opts = { fetch, now }. 실패해도 reject 하지 않고 { failed: true, error, live: season === kstYear }
   * 를 돌려줍니다('올해면 진행 중'은 이 판단을 넣기 전 동작과 같습니다).
   */
  async function loadSeasonState(base, season, opts) {
    opts = opts || {};
    const y = Number(season);
    const kstYear = kstToday(opts.now).y;
    const f = opts.fetch || root.fetch.bind(root);
    try {
      const res = await f(`${base}/games?season=${y}&limit=${LIMIT}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      if (!json || typeof json !== 'object') throw new Error('응답이 비어 있습니다');
      if (json.detail || json.error) throw new Error(String(json.detail || json.error));
      if (!Array.isArray(json.games)) throw new Error('games 목록이 없습니다');
      return Object.assign({ season: y, kstYear: kstYear, failed: false }, summarize(y, json.games, kstYear));
    } catch (e) {
      return {
        season: y, kstYear: kstYear, failed: true, error: String((e && e.message) || e),
        live: y === kstYear, lastGame: null, lastRegularDate: null, firstDate: null,
      };
    }
  }

  const api = { LIMIT, FAIL_TEXT, kstToday, isoOf, isLive, summarize, loadSeasonState };
  TS.season = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
