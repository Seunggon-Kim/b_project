/*
 * 선수 통계 페이지 조립입니다. 상태(탭·묶음·시즌·팀·포지션·최소·정렬·쪽·칸)와
 * 주소, 화면 그리기, 이벤트를 맡습니다.
 *
 * 계산은 stats/metrics.js, 칸 정의는 stats/columns.js(pdef·PGROUPS·PORDER),
 * 데이터는 stats/data.js, 표는 stats/table.js 가 합니다. 위쪽 순수 함수는
 * Node 로 검증하고, 아래 화면 부분은 브라우저에서만 돕니다.
 *
 * 설명 창·CSV·링크 복사는 팀 통계 page.js 와 비슷하지만, 팀 통계를
 * 건드리지 않으려고 따로 둡니다(설계 6장).
 */
(function (root) {
  'use strict';
  const TS = root.TeamStats = root.TeamStats || {};

  const TABS = ['bat', 'pit'];
  const GROUPS_BY_TAB = { bat: ['dash', 'std', 'adv', 'sit', 'custom'], pit: ['dash', 'std', 'adv', 'custom'] };
  const MIN_STEPS = { bat: [50, 100, 200, 300], pit: [10, 30, 50, 100] };
  const SIZES = [50, 100, 0];
  const POS_ORDER = ['포수', '내야수', '외야수', '지명타자', '투수'];
  const PBP_MIN = 2008;

  const okKey = k => /^[a-z0-9]+$/.test(k || '');

  // 앞 칸입니다. 이름은 선수 분석 페이지로 갑니다(같은 pages/ 폴더).
  const ID_COLS = [
    {
      key: 'name', label: '이름', cls: 'ts-name',
      href: r => (r.id === null || r.id === undefined || r.id === '' ? null : 'player-analytics?id=' + encodeURIComponent(r.id)),
    },
    { key: 'team', label: '팀', cls: 'ts-pteam' },
  ];

  /** 주소의 ?… 를 상태로 읽습니다. 잘못된 값은 기본값으로 둡니다. */
  function parseState(search) {
    const p = new URLSearchParams(search || '');
    const g = k => p.get(k) || '';
    const tab = TABS.includes(g('tab')) ? g('tab') : 'bat';
    const m = g('min');
    let min = 'q';
    if (m === 'all') min = 'all';
    else if (/^\d+$/.test(m) && MIN_STEPS[tab].includes(Number(m))) min = Number(m);
    const pageNo = /^\d{1,4}$/.test(g('page')) ? Number(g('page')) : 1;
    return {
      tab: tab,
      group: GROUPS_BY_TAB[tab].includes(g('group')) ? g('group') : 'dash',
      season: /^\d{4}$/.test(g('season')) ? Number(g('season')) : null,
      team: g('team'),
      pos: tab === 'bat' ? g('pos') : '',
      min: min,
      sort: okKey(g('sort')) ? g('sort') : '',
      dir: g('dir') === 'asc' || g('dir') === 'desc' ? g('dir') : '',
      page: pageNo >= 1 ? pageNo - 1 : 0,
      size: g('size') === '100' ? 100 : g('size') === 'all' ? 0 : 50,
      cols: g('cols').split(',').filter(okKey),
    };
  }

  /** 상태를 주소의 ?… 로 씁니다. 기본값은 적지 않습니다. */
  function toSearch(s) {
    const p = new URLSearchParams();
    p.set('tab', s.tab);
    p.set('group', s.group);
    if (s.season) p.set('season', String(s.season));
    if (s.team) p.set('team', s.team);
    if (s.tab === 'bat' && s.pos) p.set('pos', s.pos);
    if (s.min !== 'q') p.set('min', String(s.min));
    if (s.sort) { p.set('sort', s.sort); p.set('dir', s.dir || 'desc'); }
    if (s.page > 0) p.set('page', String(s.page + 1));
    if (s.size !== 50) p.set('size', s.size ? String(s.size) : 'all');
    if (s.group === 'custom' && s.cols && s.cols.length) p.set('cols', s.cols.join(','));
    return '?' + p.toString();
  }

  /** 지금 보일 칸입니다. */
  function visibleKeys(tab, group, season, custom) {
    const C = TS.columns;
    const G = C.PGROUPS[tab];
    let keys;
    if (group === 'custom') keys = (custom && custom.length ? custom : G.dash).slice();
    else keys = (G[group] || G.dash).slice();
    // 2007 이전은 wRC+ 가 비므로 대시보드에 OPS+ 를 붙입니다(팀 통계와 같음).
    if (tab === 'bat' && group === 'dash' && season < PBP_MIN && !keys.includes('opsp')) {
      const i = keys.indexOf('wrcp');
      keys.splice(i < 0 ? keys.length : i + 1, 0, 'opsp');
    }
    return keys.filter(k => C.pdef(tab, k));
  }

  const SORT_PREF = {
    bat: [['wrcp', 'desc'], ['opsp', 'desc'], ['avg', 'desc'], ['ops', 'desc']],
    sit: [['risp', 'desc']],
    pit: [['era', 'asc'], ['fip', 'asc'], ['whip', 'asc']],
  };

  // rows 를 주면 모든 선수가 값 없음(null)인 칸(예: 2007년 이전 wRC+)은 기본 정렬에서 건너뜁니다.
  function defaultSort(tab, group, keys, rows) {
    const has = k => !rows || !rows.length || rows.some(r => r && r[k] != null && !Number.isNaN(r[k]));
    const pref = tab === 'bat' && group === 'sit' ? SORT_PREF.sit : SORT_PREF[tab];
    for (const [k, d] of pref) if (keys.includes(k) && has(k)) return { key: k, dir: d };
    return { key: keys[0], dir: 'desc' };
  }

  function pickSort(st, keys, rows) {
    if (st.sort && keys.includes(st.sort)) return { key: st.sort, dir: st.dir || 'desc' };
    return defaultSort(st.tab, st.group, keys, rows);
  }

  /**
   * 고른 조건(팀·포지션·최소)에 맞는 선수입니다. 규정 이상(min 'q')은
   * qualOf(row) 가 준 기준 { pa, outs } 로 보고, 기준을 모르면(null) 뺍니다.
   * 투수는 이닝을 아웃 수(outs)로 비교하고 포지션은 보지 않습니다.
   */
  function filterRows(rows, st, qualOf) {
    return (rows || []).filter(function (r) {
      if (st.team && r.team !== st.team) return false;
      if (st.tab === 'bat' && st.pos && r.pos !== st.pos) return false;
      if (st.min === 'all') return true;
      if (typeof st.min === 'number') return st.tab === 'bat' ? r.pa >= st.min : r.outs >= st.min * 3;
      const q = qualOf(r);
      if (!q) return false;
      return st.tab === 'bat' ? r.pa >= q.pa : r.outs >= q.outs;
    });
  }

  /** 순위표에 경기 수가 없는 팀이 있으면 true 입니다(그때만 시즌 공통 규정을 받습니다). */
  function needRegulation(teams, rank) {
    return (teams || []).some(t => !(rank && rank[t] && rank[t].g > 0));
  }

  function teamsOf(rows) {
    return [...new Set((rows || []).map(r => r.team).filter(Boolean))].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
  }

  function positionsOf(rows) {
    const order = p => { const i = POS_ORDER.indexOf(p); return i < 0 ? POS_ORDER.length : i; };
    return [...new Set((rows || []).map(r => r.pos).filter(Boolean))]
      .sort((a, b) => order(a) - order(b) || a.localeCompare(b, 'ko'));
  }

  function minOptions(tab) {
    const unit = tab === 'bat' ? '타석' : '이닝';
    return [{ v: 'q', label: '규정 이상' }, { v: 'all', label: '전체' }]
      .concat(MIN_STEPS[tab].map(n => ({ v: n, label: `${n}${unit}` })));
  }

  function minLabel(tab, min) {
    if (min === 'q') return '규정 이상';
    if (min === 'all') return '전체';
    return `${min}${tab === 'bat' ? '타석' : '이닝'} 이상`;
  }

  /** 표 제목입니다. 예: 타자 (2026, 규정 이상 62명) */
  function titleText(st, n) {
    const parts = [String(st.season)];
    if (st.team) parts.push(st.team);
    if (st.tab === 'bat' && st.pos) parts.push(st.pos);
    parts.push(`${minLabel(st.tab, st.min)} ${n}명`);
    return `${st.tab === 'bat' ? '타자' : '투수'} (${parts.join(', ')})`;
  }

  function csvName(st) {
    return ['bstats', 'player', st.tab === 'bat' ? 'batting' : 'pitching', st.group, String(st.season)].join('_') + '.csv';
  }

  /** 표 아래 쪽 넘기기 줄입니다. pg 는 table.pageOf 결과, size 는 한 쪽 인원(0 = 전체)입니다. */
  function pagerHtml(pg, total, size) {
    const btn = (k, label, off) => `<button type="button" class="tabbtn" data-page="${k}"${off ? ' disabled' : ''}>${label}</button>`;
    let h = `<span class="text-muted">${total}명 중 ${total ? pg.start + 1 : 0}~${pg.end}</span>`;
    if (pg.count > 1) {
      h += btn('prev', '이전', pg.index === 0)
        + `<span class="ts-pager-no">${pg.index + 1} / ${pg.count}쪽</span>`
        + btn('next', '다음', pg.index >= pg.count - 1);
    }
    h += '<label for="page-size">한 쪽</label><select id="page-size" class="input">'
      + SIZES.map(v => `<option value="${v}"${v === size ? ' selected' : ''}>${v ? v + '명' : '전체'}</option>`).join('')
      + '</select>';
    return h;
  }

  const CAVEAT = '출처: KBO 공식 선수 기록입니다. 비율 지표는 성분에서 다시 계산합니다. 리그 평균 행은 고른 조건과 상관없이 그 시즌 리그 전체 선수의 합으로 셉니다.';
  const TRADE_CAVEAT = ' 시즌 중 트레이드된 선수는 공식 기록이 한 줄이라 마지막 팀으로 보이고, 구장 보정도 마지막 팀 홈구장 기준입니다.';
  const QUAL_CAVEAT = ' 규정 이상은 타석이 소속팀 경기 수 × 3.1(반올림) 이상, 이닝이 소속팀 경기 수 이상인 선수입니다.';
  const LIVE_QUAL_CAVEAT = ' 올해 소속팀 경기 수는 KBO 실시간 순위입니다.';
  const LIVE_SEASON_CAVEAT = ' 진행 중인 시즌은 최신 일일 갱신 기준이라 KBO 실시간과 1~2경기 차이가 날 수 있습니다.';
  const OLD_CAVEAT = ' 2007년 이전은 파크팩터가 없어 OPS+·ERA-·FIP-를 구장 보정 없이 계산했고, wOBA·wRC+는 2008년부터 있습니다.';
  const SIT_CAVEAT = ' 상황 묶음(득점권·대타·결승타·멀티히트·XR·GPA·P/PA)은 KBO 공식 기록 값 그대로라 리그 평균은 비워 둡니다.';

  /** 표 아래 출처·주의 문구입니다. latest 는 가장 최근 시즌, live 는 실시간 순위로 규정을 셌는지입니다. */
  function caveatText(st, latest, live) {
    return CAVEAT + TRADE_CAVEAT
      + (st.min === 'q' ? QUAL_CAVEAT + (live ? LIVE_QUAL_CAVEAT : '') : '')
      + (st.season === latest ? LIVE_SEASON_CAVEAT : '')
      + (st.season < PBP_MIN ? OLD_CAVEAT : '')
      + (st.group === 'sit' ? SIT_CAVEAT : '');
  }

  /** 지금 상태를 그리는 데 필요한 시즌 기록이 왔는지 봅니다. */
  function dataReady(st, store) {
    return !!(store.season && store.season[st.season]);
  }

  // ===== 화면(브라우저에서만) =====

  const api = {
    ID_COLS, parseState, toSearch, visibleKeys, defaultSort, pickSort, filterRows, needRegulation,
    teamsOf, positionsOf, minOptions, minLabel, titleText, csvName, pagerHtml, caveatText, dataReady,
  };
  TS.playerPage = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
