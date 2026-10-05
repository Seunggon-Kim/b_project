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
    sit: [['risp', 'desc'], ['pa', 'desc']],
    pit: [['era', 'asc'], ['fip', 'asc'], ['whip', 'asc']],
  };

  // rows 를 주면 모든 선수가 값 없음(null)인 칸(예: 2007년 이전 wRC+)은 기본 정렬에서 건너뜁니다.
  function hasValue(rows, k) {
    return !rows || !rows.length || rows.some(r => r && r[k] != null && !Number.isNaN(r[k]));
  }

  function defaultSort(tab, group, keys, rows) {
    const has = k => hasValue(rows, k);
    const pref = tab === 'bat' && group === 'sit' ? SORT_PREF.sit : SORT_PREF[tab];
    for (const [k, d] of pref) if (keys.includes(k) && has(k)) return { key: k, dir: d };
    return { key: keys[0], dir: 'desc' };
  }

  function pickSort(st, keys, rows) {
    if (st.sort && keys.includes(st.sort) && hasValue(rows, st.sort)) return { key: st.sort, dir: st.dir || 'desc' };
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

  // 팀 통계 고르개와 같은 순서입니다(한글 팀 먼저, 다음 영문 팀).
  function teamsOf(rows) {
    return [...new Set((rows || []).map(r => r.team).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ko'));
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
  const LIVE_QUAL_CAVEAT = ' 진행 중인 시즌의 소속팀 경기 수는 KBO 실시간 순위입니다.';
  const LIVE_SEASON_CAVEAT = ' 진행 중인 시즌은 최신 일일 갱신 기준이라 KBO 실시간과 1~2경기 차이가 날 수 있습니다.';
  const OLD_CAVEAT = ' 2007년 이전은 파크팩터가 없어 OPS+·ERA-·FIP-를 구장 보정 없이 계산했고, wOBA·wRC+는 2008년부터 있습니다.';
  const SIT_CAVEAT = ' 상황 묶음(득점권·대타·결승타·멀티히트·XR·GPA·P/PA)은 KBO 공식 기록 값 그대로라 리그 평균은 비워 둡니다. 대타로 나온 적이 없는 선수도 대타 타율이 .000으로 보입니다.';

  /**
   * 표 아래 출처·주의 문구입니다. liveSeason 은 진행 중인 시즌(없으면 null, js/stats/season.js 판단),
   * live 는 실시간 순위로 규정을 셌는지입니다.
   */
  function caveatText(st, liveSeason, live) {
    return CAVEAT + TRADE_CAVEAT
      + (st.min === 'q' ? QUAL_CAVEAT + (live ? LIVE_QUAL_CAVEAT : '') : '')
      + (liveSeason && st.season === liveSeason ? LIVE_SEASON_CAVEAT : '')
      + (st.season < PBP_MIN ? OLD_CAVEAT : '')
      + (st.group === 'sit' ? SIT_CAVEAT : '');
  }

  /** 지금 상태를 그리는 데 필요한 시즌 기록이 왔는지 봅니다. */
  function dataReady(st, store) {
    return !!(store.season && store.season[st.season]);
  }

  // ===== 화면(브라우저에서만) =====

  const S = {
    st: null, seasons: [], refs: { errors: [] },
    season: {}, standings: null, reg: null,
    custom: { bat: null, pit: null }, panelOpen: false,
    seasonErrors: [], seq: 0, last: null,
    // 한국 시각 올해 시즌의 진행 중 판단(js/stats/season.js loadSeasonState 결과)입니다. init 에서 채웁니다.
    liveState: null,
  };

  let tipHide = function () {};

  function $(id) { return document.getElementById(id); }
  function keysNow() { return visibleKeys(S.st.tab, S.st.group, S.st.season, S.custom[S.st.tab]); }

  /** 진행 중인 시즌(없으면 null)입니다. 한국 시각 올해 시즌만 진행 중일 수 있습니다. */
  function liveYear() {
    return S.liveState && S.liveState.live ? S.liveState.season : null;
  }

  function writeUrl(replace) {
    const st = S.st;
    st.cols = st.group === 'custom' ? (S.custom[st.tab] || []) : [];
    const url = location.pathname + toSearch(st);
    if (replace) history.replaceState(null, '', url);
    else history.pushState(null, '', url);
  }

  /** 상태를 받은 시즌 목록에 맞춥니다. */
  function normalize() {
    const st = S.st;
    if (!st.season || !S.seasons.includes(st.season)) st.season = S.seasons[0];
    if (st.group === 'custom' && st.cols.length) S.custom[st.tab] = st.cols.slice();
  }

  function errAlerts(list, errors) {
    (errors || []).forEach(function (e) {
      list.push({ kind: 'warn', text: `${e.what} 자료를 받지 못했습니다 (${e.error}). 이 자료가 필요한 칸은 '-'로 둡니다.` });
    });
  }

  function renderAlerts(list) {
    $('ts-alerts').innerHTML = list
      .map(a => `<div class="ts-alert ts-alert-${a.kind}">${TS.table.esc(a.text)}</div>`).join('');
  }

  /**
   * 규정에 쓸 순위표 { rank, live } 입니다. 진행 중인 시즌은 실시간 순위, 아니면 저장된
   * 순위표입니다. 실시간 순위를 못 받으면 alerts 에 알리고 저장된 순위표로 갑니다.
   */
  function rankNow(alerts) {
    const M = TS.metrics, y = S.st.season;
    if (y === liveYear() && S.standings) {
      if (!S.standings.errors.length && S.standings.teams.length) {
        return { rank: M.rankFromStandings(S.standings.teams), live: true };
      }
      if (alerts) {
        errAlerts(alerts, S.standings.errors);
        alerts.push({ kind: 'warn', text: '실시간 순위를 받지 못해 저장된 순위표의 팀 경기 수로 규정을 셉니다. 저장된 순위표는 시즌 중 갱신이 늦을 수 있습니다.' });
      }
    }
    return { rank: M.rankFor(S.refs.rank, y), live: false };
  }

  /** 지금 화면에 필요한 데이터를 받습니다. 받은 것은 기억하고, 실패한 것은 다시 받습니다. */
  async function ensureData() {
    const st = S.st, y = st.season, D = TS.data, base = root.KBO_API_BASE;
    const stale = x => !x || x.errors.length > 0;
    const jobs = [];
    if (stale(S.season[y])) jobs.push(D.loadSeason(base, y).then(r => { S.season[y] = r; }));
    if (st.min === 'q' && y === liveYear() && stale(S.standings)) jobs.push(D.loadStandings(base).then(r => { S.standings = r; }));
    await Promise.all(jobs);
    // 순위표에 경기 수가 없는 팀이 있을 때만 시즌 공통 규정을 받습니다.
    if (st.min === 'q' && stale(S.reg)) {
      const sd = S.season[y];
      const list = (st.tab === 'bat' ? sd.batters : sd.pitchers) || [];
      if (needRegulation(list.map(p => p.player_team).filter(Boolean), rankNow(null).rank)) {
        S.reg = await D.loadRegulation(base);
      }
    }
  }

  function fillSeasons() {
    const el = $('season-select');
    el.innerHTML = S.seasons.map(y => `<option value="${y}">${y}</option>`).join('');
    el.value = String(S.st.season);
  }

  /** 팀·포지션 고르개를 채웁니다. 주소에 있던 값이 목록에 없으면 '전체'로 둡니다. */
  function fillSelect(id, list, key) {
    const el = $(id), esc = TS.table.esc;
    if (S.st[key] && !list.includes(S.st[key])) S.st[key] = '';
    el.innerHTML = '<option value="">전체</option>'
      + list.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join('');
    el.value = S.st[key];
  }

  function fillMin() {
    const el = $('min-select');
    el.innerHTML = minOptions(S.st.tab).map(o => `<option value="${o.v}">${o.label}</option>`).join('');
    el.value = String(S.st.min);
  }

  function syncTabs() {
    const st = S.st;
    document.querySelectorAll('#ts-tabs [data-tab]').forEach(b => b.classList.toggle('active', b.dataset.tab === st.tab));
    document.querySelectorAll('#ts-groups [data-group]').forEach(b => b.classList.toggle('active', b.dataset.group === st.group));
    $('group-sit').hidden = st.tab !== 'bat';
    $('pos-group').hidden = st.tab !== 'bat';
    $('col-panel').classList.toggle('hidden', !(st.group === 'custom' && S.panelOpen));
  }

  /** 사용자 지정 칸입니다. 비어 있으면 대시보드 칸을 켠 것으로 봅니다(표와 패널이 같은 기준). */
  function customOrDash(tab) {
    const c = S.custom[tab];
    return c && c.length ? c : TS.columns.PGROUPS[tab].dash;
  }

  function renderColPanel() {
    const tab = S.st.tab, C = TS.columns, esc = TS.table.esc;
    const on = new Set(customOrDash(tab));
    const defs = C.PORDER[tab].map(k => C.pdef(tab, k));
    $('col-list').innerHTML = defs.map(d => `<label class="${on.has(d.key) ? '' : 'off'}" title="${esc(d.desc)}">`
      + `<input type="checkbox" data-col="${d.key}"${on.has(d.key) ? ' checked' : ''}>${esc(d.label)}</label>`).join('');
    $('col-count').textContent = `${defs.filter(d => on.has(d.key)).length}개 / ${defs.length}개`;
  }

  /** 받은 데이터로 지금 탭을 그립니다. 서버를 부르지 않습니다. 데이터가 아직이면 그리지 않습니다. */
  function render() {
    if (!dataReady(S.st, S)) return;
    tipHide();
    const st = S.st, C = TS.columns, M = TS.metrics, T = TS.table;
    const y = st.season;
    const alerts = [];
    errAlerts(alerts, S.seasonErrors);
    errAlerts(alerts, S.refs.errors);
    // 진행 중 판단을 못 받았으면 올해 시즌을 진행 중으로 보고 있음을 알립니다(올해 시즌을 볼 때만).
    if (S.liveState && S.liveState.failed && y === S.liveState.season) alerts.push({ kind: 'warn', text: TS.season.FAIL_TEXT });
    const sd = S.season[y];
    // 지금 탭에 필요한 기록의 실패만 알립니다.
    const otherTab = st.tab === 'bat' ? '투수 기록' : '타자 기록';
    errAlerts(alerts, (sd.errors || []).filter(e => e.what !== otherTab));
    syncTabs();

    const ix = M.indexRefs(S.refs);
    const tbl = st.tab === 'bat' ? M.playerBatting(sd.batters, y, ix) : M.playerPitching(sd.pitchers, y, ix);
    let qualOf = () => null;
    let live = false;
    if (st.min === 'q') {
      const rk = rankNow(alerts);
      live = rk.live;
      const reg = S.reg && S.reg.regulation ? S.reg.regulation[String(y)] || null : null;
      const miss = teamsOf(tbl.rows).filter(t => !(rk.rank[t] && rk.rank[t].g > 0));
      // 규정 기준은 순위표에 없는 팀이 있어 실제로 필요할 때만 알립니다.
      if (S.reg && miss.length) errAlerts(alerts, S.reg.errors);
      if (miss.length && reg) {
        alerts.push({ kind: 'info', text: `순위표에 없는 팀(${miss.join(', ')})은 그 시즌 공통 규정(${reg.qual_pa}타석, ${reg.qual_ip}이닝)으로 셉니다.` });
      } else if (miss.length) {
        alerts.push({ kind: 'warn', text: `규정을 셀 팀 경기 수를 몰라 ${miss.join(', ')} 선수는 규정 이상에서 빠집니다. 최소를 '전체'로 바꾸면 보입니다.` });
      }
      qualOf = r => M.qualFor(r.team, rk.rank, reg);
    }

    fillSelect('team-select', teamsOf(tbl.rows), 'team');
    if (st.tab === 'bat') fillSelect('pos-select', positionsOf(tbl.rows), 'pos');
    fillMin();

    const keys = keysNow();
    const cols = keys.map(k => C.pdef(st.tab, k));
    const shown = filterRows(tbl.rows, st, qualOf);
    const sort = pickSort(st, keys, tbl.rows);
    const league = tbl.rows.length ? tbl.league : null;
    const pg = T.pageOf(shown.length, { size: st.size, index: st.page });
    if (pg.index !== st.page) { st.page = pg.index; writeUrl(true); }

    S.last = { cols: cols, rows: shown, league: league, sort: sort, idCols: ID_COLS, all: tbl.rows };
    $('ts-title').textContent = titleText(st, shown.length);
    if (!tbl.rows.length) {
      $('ts-table').innerHTML = createEmptyState('해당 시즌 기록이 없습니다.');
    } else {
      $('ts-table').innerHTML = (shown.length ? '' : '<p class="text-muted ts-empty">조건에 맞는 선수가 없습니다.</p>')
        + T.renderTable({ cols: cols, rows: shown, league: league, sort: sort, idCols: ID_COLS, page: { size: st.size, index: st.page } });
    }
    $('ts-pager').innerHTML = shown.length ? pagerHtml(pg, shown.length, st.size) : '';
    $('caveat-note').textContent = caveatText(st, liveYear(), live);
    renderAlerts(alerts);
    if (!$('col-panel').classList.contains('hidden')) renderColPanel();
  }

  /** 주소를 쓰고, 필요한 데이터를 받은 뒤 그립니다. 늦게 온 이전 응답은 버립니다. */
  async function refresh(opt) {
    opt = opt || {};
    const seq = ++S.seq;
    if (!opt.noUrl) writeUrl(opt.replace);
    $('ts-table').innerHTML = createLoadingSpinner();
    $('ts-pager').innerHTML = '';
    try {
      await ensureData();
    } catch (e) {
      if (seq !== S.seq) return;
      console.error(e);
      $('ts-table').innerHTML = createErrorMessage('선수 기록을 불러오는데 실패했습니다.');
      return;
    }
    if (seq !== S.seq) return;
    render();
  }

  function downloadCsv() {
    if (!S.last) return;
    const csv = TS.table.toCsv(S.last);
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = csvName(S.st);
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function copyLink() {
    const btn = $('link-btn');
    try {
      await navigator.clipboard.writeText(location.href);
      btn.textContent = '복사됨';
    } catch (e) {
      root.prompt('이 주소를 복사해 주세요', location.href);
    }
    setTimeout(() => { btn.textContent = '링크 복사'; }, 1500);
  }

  function bindTips() {
    let box = null;
    function hideTip() { if (box) box.style.display = 'none'; }
    tipHide = hideTip;
    window.addEventListener('scroll', hideTip, { passive: true });
    document.addEventListener('touchstart', function (e) {
      if (!(e.target.closest && e.target.closest('.ts-term'))) hideTip();
    }, { passive: true });
    document.addEventListener('mouseover', function (e) {
      const el = e.target.closest && e.target.closest('.ts-term[data-col]');
      if (!el) return;
      const d = TS.columns.pdef(S.st.tab, el.dataset.col);
      if (!d) return;
      if (!box) {
        box = document.createElement('div');
        box.className = 'tip-box';
        document.body.appendChild(box);
      }
      box.innerHTML = TS.table.tipHtml(d);
      box.style.display = 'block';
      const r = el.getBoundingClientRect();
      box.style.left = Math.max(8, Math.min(r.left, window.innerWidth - box.offsetWidth - 12)) + 'px';
      box.style.top = (r.bottom + 6) + 'px';
    });
    document.addEventListener('mouseout', function (e) {
      if (e.target.closest && e.target.closest('.ts-term[data-col]')) hideTip();
    });
  }

  /** 정렬·쪽을 처음으로 돌립니다(탭·묶음을 바꿀 때). */
  function resetView() {
    S.st.sort = '';
    S.st.dir = '';
    S.st.page = 0;
  }

  function bind() {
    $('ts-tabs').addEventListener('click', function (e) {
      const b = e.target.closest('[data-tab]');
      if (!b || b.dataset.tab === S.st.tab) return;
      const st = S.st;
      st.tab = b.dataset.tab;
      if (!GROUPS_BY_TAB[st.tab].includes(st.group)) st.group = 'dash';
      // 숫자 최소값(50타석 등)은 탭마다 뜻이 달라 규정 이상으로 돌립니다.
      if (typeof st.min === 'number') st.min = 'q';
      if (st.tab !== 'bat') st.pos = '';
      resetView();
      refresh();
    });
    $('ts-groups').addEventListener('click', function (e) {
      const b = e.target.closest('[data-group]');
      if (!b) return;
      const g = b.dataset.group;
      if (g === 'custom') S.panelOpen = S.st.group === 'custom' ? !S.panelOpen : true;
      if (g !== S.st.group) { S.st.group = g; resetView(); writeUrl(); }
      render();
    });
    $('season-select').addEventListener('change', function (e) {
      S.st.season = Number(e.target.value);
      S.st.page = 0;
      refresh();
    });
    $('team-select').addEventListener('change', function (e) {
      S.st.team = e.target.value;
      S.st.page = 0;
      writeUrl();
      render();
    });
    $('pos-select').addEventListener('change', function (e) {
      S.st.pos = e.target.value;
      S.st.page = 0;
      writeUrl();
      render();
    });
    $('min-select').addEventListener('change', function (e) {
      const v = e.target.value;
      S.st.min = v === 'q' || v === 'all' ? v : Number(v);
      S.st.page = 0;
      refresh();
    });
    $('csv-btn').addEventListener('click', downloadCsv);
    $('link-btn').addEventListener('click', copyLink);
    $('ts-table').addEventListener('click', function (e) {
      const th = e.target.closest('th.sortable');
      if (!th) return;
      const k = th.dataset.key;
      const cur = pickSort(S.st, keysNow(), S.last && S.last.all);
      if (cur.key === k) S.st.dir = cur.dir === 'asc' ? 'desc' : 'asc';
      else {
        const d = TS.columns.pdef(S.st.tab, k);
        S.st.dir = d && d.better === 'low' ? 'asc' : 'desc';
      }
      S.st.sort = k;
      S.st.page = 0;
      render();
      writeUrl(true);
    });
    $('ts-pager').addEventListener('click', function (e) {
      const b = e.target.closest('[data-page]');
      if (!b || b.disabled) return;
      S.st.page += b.dataset.page === 'next' ? 1 : -1;
      writeUrl();
      render();
      // 표 위가 화면 밖이면 표 제목이 보이게 올립니다(위 고정 머리 높이만큼 띄움).
      const top = $('ts-title').getBoundingClientRect().top;
      if (top < 0) window.scrollBy(0, top - 80);
    });
    $('ts-pager').addEventListener('change', function (e) {
      if (e.target.id !== 'page-size') return;
      S.st.size = Number(e.target.value);
      S.st.page = 0;
      writeUrl();
      render();
    });
    $('col-list').addEventListener('change', function (e) {
      const k = e.target.getAttribute('data-col');
      if (!k) return;
      const tab = S.st.tab;
      const on = new Set(customOrDash(tab));
      if (e.target.checked) on.add(k); else on.delete(k);
      S.custom[tab] = TS.columns.PORDER[tab].filter(x => on.has(x));
      writeUrl(true);
      render();
    });
    document.querySelectorAll('[data-col-preset]').forEach(function (b) {
      b.addEventListener('click', function () {
        const tab = S.st.tab;
        S.custom[tab] = b.dataset.colPreset === 'all' ? TS.columns.PORDER[tab].slice() : TS.columns.PGROUPS[tab].dash.slice();
        writeUrl(true);
        render();
      });
    });
    $('col-close').addEventListener('click', function () {
      S.panelOpen = false;
      syncTabs();
    });
    window.addEventListener('popstate', function () {
      S.st = parseState(location.search);
      normalize();
      S.panelOpen = S.st.group === 'custom';
      fillSeasons();
      refresh({ noUrl: true });
    });
    bindTips();
  }

  async function init() {
    try {
      S.st = parseState(location.search);
      $('ts-table').innerHTML = createLoadingSpinner();
      const base = root.KBO_API_BASE;
      // 한국 시각 올해 시즌만 진행 중일 수 있어, 그 해 판단을 시즌 목록과 함께 받습니다.
      const kst = TS.season.kstToday();
      const got = await Promise.all([TS.data.loadSeasons(base), TS.data.loadRefs(base), TS.season.loadSeasonState(base, kst.y)]);
      S.seasons = got[0].seasons;
      S.seasonErrors = got[0].errors;
      S.refs = got[1];
      S.liveState = got[2];
      if (S.liveState.failed) console.warn(TS.season.FAIL_TEXT, S.liveState.error);
      normalize();
      if (S.st.group === 'custom') S.panelOpen = true;
      fillSeasons();
      bind();
      await refresh({ replace: true });
    } catch (e) {
      console.error(e);
      $('ts-table').innerHTML = createErrorMessage('선수 기록을 불러오는데 실패했습니다.');
    }
  }

  const api = {
    ID_COLS, parseState, toSearch, visibleKeys, defaultSort, pickSort, filterRows, needRegulation,
    teamsOf, positionsOf, minOptions, minLabel, titleText, csvName, pagerHtml, caveatText, dataReady,
  };
  TS.playerPage = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document.getElementById('ps-page')) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
})(typeof window !== 'undefined' ? window : globalThis);
