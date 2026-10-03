/*
 * 팀 통계 페이지 조립입니다. 상태(탭·묶음·시즌·팀·기간·정렬·칸)와 주소,
 * 화면 그리기, 이벤트를 맡습니다.
 *
 * 계산은 metrics.js, 칸 정의는 columns.js, 데이터는 data.js, 표는
 * table.js, 상대 전적·월별은 record.js 가 합니다. 위쪽 순수 함수는 Node
 * 로 검증하고, 아래 화면 부분은 브라우저에서만 돕니다.
 */
(function (root) {
  'use strict';
  const TS = root.TeamStats = root.TeamStats || {};

  const TABS = ['bat', 'pit', 'rec'];
  const GROUP_KEYS = ['dash', 'std', 'adv', 'custom'];
  const PBP_MIN = 2008;

  const okKey = k => /^[a-z0-9]+$/.test(k || '');
  const okDate = d => /^\d{4}-\d{2}-\d{2}$/.test(d || '');

  /** 주소의 ?… 를 상태로 읽습니다. 잘못된 값은 기본값으로 둡니다. */
  function parseState(search) {
    const p = new URLSearchParams(search || '');
    const g = k => p.get(k) || '';
    return {
      tab: TABS.includes(g('tab')) ? g('tab') : 'bat',
      group: GROUP_KEYS.includes(g('group')) ? g('group') : 'dash',
      season: /^\d{4}$/.test(g('season')) ? Number(g('season')) : null,
      team: g('team'),
      start: okDate(g('start')) ? g('start') : '',
      end: okDate(g('end')) ? g('end') : '',
      sort: okKey(g('sort')) ? g('sort') : '',
      dir: g('dir') === 'asc' || g('dir') === 'desc' ? g('dir') : '',
      cols: g('cols').split(',').filter(okKey),
    };
  }

  /** 상태를 주소의 ?… 로 씁니다. */
  function toSearch(s) {
    const p = new URLSearchParams();
    p.set('tab', s.tab);
    if (s.tab !== 'rec') p.set('group', s.group);
    if (s.season) p.set('season', String(s.season));
    if (s.team) p.set('team', s.team);
    if (s.start && s.end) { p.set('start', s.start); p.set('end', s.end); }
    if (s.sort) { p.set('sort', s.sort); p.set('dir', s.dir || 'desc'); }
    if (s.tab !== 'rec' && s.group === 'custom' && s.cols && s.cols.length) p.set('cols', s.cols.join(','));
    return '?' + p.toString();
  }

  /** 지금 보일 칸입니다. */
  function visibleKeys(tab, group, mode, season, custom) {
    const C = TS.columns;
    let keys;
    if (tab === 'rec') keys = C.REC_KEYS.slice();
    else if (group === 'custom') keys = (custom && custom.length ? custom : C.GROUPS[tab].dash).slice();
    else keys = C.GROUPS[tab][group].slice();
    // 2007 이전은 wRC+ 가 비므로 대시보드에 OPS+ 를 붙입니다.
    if (tab === 'bat' && group === 'dash' && season < PBP_MIN && !keys.includes('opsp')) {
      const i = keys.indexOf('wrcp');
      keys.splice(i < 0 ? keys.length : i + 1, 0, 'opsp');
    }
    if (mode === 'range' && tab !== 'rec') {
      keys = keys.map(k => (tab === 'pit' && k === 'era' ? 'ra9' : k));
      keys = keys.filter((k, i) => keys.indexOf(k) === i);
      keys = keys.filter(k => { const d = C.def(tab, k); return d && d.range; });
    }
    return keys.filter(k => C.def(tab, k));
  }

  const SORT_PREF = {
    bat: [['wrcp', 'desc'], ['opsp', 'desc'], ['avg', 'desc'], ['ops', 'desc']],
    pit: [['era', 'asc'], ['ra9', 'asc'], ['fip', 'asc'], ['whip', 'asc']],
    rec: [['pct', 'desc']],
  };

  // rows 를 주면 모든 팀이 값 없음(null)인 칸(예: 2007년 이전 wRC+)은 기본 정렬에서 건너뜁니다.
  function defaultSort(tab, keys, rows) {
    const has = k => !rows || !rows.length || rows.some(r => r && r[k] != null && !Number.isNaN(r[k]));
    for (const [k, d] of SORT_PREF[tab]) if (keys.includes(k) && has(k)) return { key: k, dir: d };
    return { key: keys[0], dir: 'desc' };
  }

  function pickSort(st, keys, rows) {
    if (st.sort && keys.includes(st.sort)) return { key: st.sort, dir: st.dir || 'desc' };
    return defaultSort(st.tab, keys, rows);
  }

  function csvName(st, mode) {
    const what = { bat: 'batting', pit: 'pitching', rec: 'record' }[st.tab];
    const when = mode === 'range' ? `${st.start}_${st.end}` : String(st.season);
    return ['bstats', 'team', what, st.tab === 'rec' ? '' : st.group, when].filter(Boolean).join('_') + '.csv';
  }

  // ===== 화면(브라우저에서만) =====

  const SEASON_CAVEAT = '출처: KBO 공식 선수 기록을 팀별로 합산해 계산합니다. 비율 지표는 성분에서 다시 계산합니다. 시즌 중 트레이드된 선수는 그 시즌 기록 전체가 한 팀으로 잡혀 팀 합산이 조금 어긋날 수 있습니다.';
  const LIVE_SEASON_CAVEAT = ' 진행 중인 시즌은 최신 일일 갱신 기준이라 KBO 실시간과 1~2경기 차이가 날 수 있습니다.';
  const OLD_CAVEAT = ' 2007년 이전은 파크팩터가 없어 OPS+·ERA-·FIP-를 구장 보정 없이 계산했고, wOBA·wRC+는 2008년부터 있습니다.';
  const RANGE_CAVEAT = '선택한 기간 안에 끝난 경기의 경기 기록(PBP)을 집계합니다. 시즌 누적과 산출 방식이 달라 수치가 다를 수 있습니다.';
  const REC_CAVEAT = '승패는 공식 순위표입니다. 득점·실점과 홈·원정·1점차·월별·상대 전적은 정규시즌 경기 결과에서 셉니다(2008년부터). 2007년 이전 득점·실점은 공식 선수 기록 합계입니다.';
  const REC_RANGE_CAVEAT = '선택한 기간의 정규시즌 경기 결과로 승패·득실을 셉니다.';
  const LEAGUE2_CAVEAT = ' 1999·2000년은 드림·매직 양대 리그라 승차는 리그 안에서 잰 값입니다.';
  const LIVE_CAVEAT = ' 올해 승패와 경기 수는 KBO 실시간 순위입니다.';

  const S = {
    st: null, seasons: [], refs: { errors: [] },
    season: {}, games: {}, range: {}, standings: null,
    custom: { bat: null, pit: null }, panelOpen: false,
    seasonErrors: [], seq: 0, last: null, pbpMax: new Date().getFullYear(),
  };

  let tipHide = function () {};

  function $(id) { return document.getElementById(id); }
  function mode() { return S.st.start && S.st.end ? 'range' : 'season'; }
  function ymd(d) { return Number(String(d).replace(/-/g, '')); }
  function fmtDate(dt) {
    const z = n => String(n).padStart(2, '0');
    return `${dt.getFullYear()}-${z(dt.getMonth() + 1)}-${z(dt.getDate())}`;
  }
  function fmtYmd(n) {
    const s = String(n === null || n === undefined ? '' : n);
    return s.length === 8 ? `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}` : s;
  }
  function teamHref(t) {
    return typeof root.teamRecordHref === 'function' ? root.teamRecordHref(t, '') : null;
  }
  function keysNow() {
    return visibleKeys(S.st.tab, S.st.group, mode(), S.st.season, S.custom[S.st.tab]);
  }

  function writeUrl(replace) {
    const st = S.st;
    st.cols = st.tab !== 'rec' && st.group === 'custom' ? (S.custom[st.tab] || []) : [];
    const url = location.pathname + toSearch(st);
    if (replace) history.replaceState(null, '', url);
    else history.pushState(null, '', url);
  }

  /** 상태를 받은 시즌 목록에 맞춥니다. */
  function normalize() {
    const st = S.st;
    if (!st.season || !S.seasons.includes(st.season)) st.season = S.seasons[0];
    if (mode() === 'range') {
      const y = String(st.season);
      const ok = st.season >= PBP_MIN && st.start.slice(0, 4) === y && st.end.slice(0, 4) === y;
      if (!ok) { st.start = ''; st.end = ''; }
      else if (st.start > st.end) { const t = st.start; st.start = st.end; st.end = t; }
    }
    if (st.group === 'custom' && st.cols.length) S.custom[st.tab] = st.cols.slice();
  }

  /** 기간 입력을 고른 시즌에 묶습니다. 경기 기록이 없는 시즌이면 막습니다. */
  function syncRange() {
    const y = S.st.season;
    const a = $('range-start'), b = $('range-end'), go = $('range-go'), note = $('range-note');
    const has = y >= PBP_MIN && y <= S.pbpMax;
    [a, b, go].forEach(el => { el.disabled = !has; });
    go.title = has ? '' : '이 시즌은 경기 기록이 없습니다';
    $('range-clear').hidden = mode() !== 'range';
    if (!has) {
      a.value = '';
      b.value = '';
      note.textContent = `${y} 시즌은 경기 기록이 없어 기간별로 볼 수 없습니다 (경기 기록은 ${PBP_MIN}년부터입니다)`;
      return;
    }
    a.min = b.min = `${y}-01-01`;
    a.max = b.max = `${y}-12-31`;
    if (mode() === 'range') { a.value = S.st.start; b.value = S.st.end; return; }
    // 기본 두 주입니다. 올해면 오늘까지, 지난 시즌이면 9월 말까지입니다.
    const now = new Date();
    const end = y === now.getFullYear() ? now : new Date(y, 8, 30);
    a.value = fmtDate(new Date(end.getTime() - 13 * 86400000));
    b.value = fmtDate(end);
    note.textContent = '';
  }

  /** 지금 화면에 필요한 데이터를 받습니다. 받은 것은 기억하고, 실패한 것은 다시 받습니다. */
  async function ensureData() {
    const st = S.st, y = st.season, D = TS.data, base = root.KBO_API_BASE;
    const need = { season: false, games: false, range: false };
    if (mode() === 'range') {
      if (st.tab === 'rec') need.games = true; else need.range = true;
    } else {
      need.season = true;
      if (st.tab === 'rec' && y >= PBP_MIN) need.games = true;
    }
    const stale = x => !x || x.errors.length > 0;
    const jobs = [];
    if (need.season && stale(S.season[y])) jobs.push(D.loadSeason(base, y).then(r => { S.season[y] = r; }));
    if (need.games && stale(S.games[y])) jobs.push(D.loadGames(base, y).then(r => { S.games[y] = r; }));
    const rk = st.start + '|' + st.end;
    if (need.range && stale(S.range[rk])) jobs.push(D.loadRange(base, st.start, st.end).then(r => { S.range[rk] = r; }));
    // 올해(가장 최근 시즌)는 승패·경기 수를 실시간 순위로 받습니다.
    if (need.season && y === S.pbpMax && stale(S.standings)) jobs.push(D.loadStandings(base).then(r => { S.standings = r; }));
    await Promise.all(jobs);
  }

  /**
   * 올해면 실시간 순위, 아니면 null(저장된 순위표를 씀)입니다.
   * 실시간 순위를 못 받으면 알림을 남기고 저장된 순위표로 돌아갑니다.
   */
  function liveRank(alerts) {
    if (S.st.season !== S.pbpMax || !S.standings) return null;
    if (S.standings.errors.length || !S.standings.teams.length) {
      errAlerts(alerts, S.standings.errors);
      alerts.push({ kind: 'warn', text: '실시간 순위를 받지 못해 저장된 순위표를 씁니다. 저장된 순위표는 시즌 중 갱신이 늦을 수 있습니다.' });
      return null;
    }
    return TS.metrics.rankFromStandings(S.standings.teams);
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

  function titleText() {
    const st = S.st;
    const what = st.tab === 'bat' ? '팀 타격' : st.tab === 'pit' ? '팀 투구' : '승패와 득실';
    if (mode() === 'range') return `${what} (기간별)`;
    return `${what} (${st.season} 시즌${st.tab === 'rec' ? '' : ' 누적'})`;
  }

  function fillTeams(names) {
    const el = $('team-select');
    const list = [...new Set(names.filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ko'));
    if (S.st.team && !list.includes(S.st.team)) S.st.team = '';
    el.innerHTML = '<option value="">전체</option>'
      + list.map(t => `<option value="${TS.table.esc(t)}">${TS.table.esc(t)}</option>`).join('');
    el.value = S.st.team;
  }

  function fillSeasons() {
    const el = $('season-select');
    el.innerHTML = S.seasons.map(y => `<option value="${y}">${y}</option>`).join('');
    el.value = String(S.st.season);
  }

  function syncTabs() {
    const st = S.st;
    document.querySelectorAll('#ts-tabs [data-tab]').forEach(b => b.classList.toggle('active', b.dataset.tab === st.tab));
    document.querySelectorAll('#ts-groups [data-group]').forEach(b => b.classList.toggle('active', b.dataset.group === st.group));
    $('ts-groups').hidden = st.tab === 'rec';
    $('ts-rec-extra').hidden = st.tab !== 'rec';
    $('col-panel').classList.toggle('hidden', !(st.tab !== 'rec' && st.group === 'custom' && S.panelOpen));
  }

  function syncRecordLink() {
    const a = $('team-record-link');
    const t = S.st.team;
    const href = t ? teamHref(t) : null;
    a.href = href ? `${href}&name=${encodeURIComponent(t)}` : 'team-record';
    a.textContent = t ? `${t} 기록실` : '기록실';
  }

  function renderColPanel() {
    const tab = S.st.tab;
    if (tab === 'rec') return;
    const C = TS.columns, esc = TS.table.esc;
    const on = new Set(S.custom[tab] || C.GROUPS[tab].dash);
    const defs = C.ORDER[tab].map(k => C.def(tab, k));
    const isRange = mode() === 'range';
    $('col-list').innerHTML = defs.map(function (d) {
      const na = isRange && !d.range;
      const cls = [on.has(d.key) ? '' : 'off', na ? 'na' : ''].filter(Boolean).join(' ');
      return `<label class="${cls}" title="${esc(d.desc)}"><input type="checkbox" data-col="${d.key}"`
        + `${on.has(d.key) ? ' checked' : ''}${na ? ' disabled' : ''}>${esc(d.label)}</label>`;
    }).join('');
    $('col-count').textContent = `${on.size}개 / ${defs.length}개`;
  }

  /** 지금 상태를 그리는 데 필요한 데이터가 다 왔는지 봅니다. */
  function dataReady(st, store) {
    const y = st.season;
    if (st.start && st.end) {
      return st.tab === 'rec' ? !!store.games[y] : !!store.range[st.start + '|' + st.end];
    }
    if (!store.season[y]) return false;
    return !(st.tab === 'rec' && y >= PBP_MIN && !store.games[y]);
  }

  /** 받은 데이터로 지금 탭을 그립니다. 서버를 부르지 않습니다. 데이터가 아직이면 그리지 않습니다(받는 중인 refresh 가 그립니다). */
  function render() {
    if (!dataReady(S.st, S)) return;
    tipHide();
    const st = S.st, C = TS.columns, M = TS.metrics, T = TS.table, R = TS.record;
    const y = st.season, m = mode();
    const alerts = [];
    errAlerts(alerts, S.seasonErrors);
    errAlerts(alerts, S.refs.errors);
    syncTabs();
    $('ts-title').textContent = titleText();

    const keys = keysNow();
    const cols = keys.map(k => C.def(st.tab, k));
    let rows = [], league = null, splits = null, caveat = '', gamesFailed = false;

    if (st.tab === 'rec') {
      if (m === 'range') {
        const g = S.games[y];
        errAlerts(alerts, g.errors);
        splits = M.gameSplits(g.games, ymd(st.start), ymd(st.end));
        rows = M.recordFromGames(splits);
        const n = rows.reduce((a, r) => a + r.g, 0) / 2;
        if (n) $('range-note').textContent = `반영: ${st.start} ~ ${st.end}, ${n}경기`;
        else $('range-note').textContent = g.errors.length ? '' : '해당 기간 경기 없음';
        caveat = REC_RANGE_CAVEAT;
      } else {
        const sd = S.season[y];
        errAlerts(alerts, sd.errors);
        const live = liveRank(alerts);
        const v = M.seasonView({ batters: sd.batters, pitchers: sd.pitchers, refs: S.refs, season: y, rank: live || undefined });
        if (y >= PBP_MIN) {
          const g = S.games[y];
          errAlerts(alerts, g.errors);
          if (g.errors.length) gamesFailed = true;
          else if (g.games.length) splits = M.gameSplits(g.games);
        }
        rows = M.recordTable(v.rank, v.batTotals, v.pitTotals, splits);
        // 경기 결과를 못 받았으면 득실 칸을 공식 합으로 몰래 바꾸지 않고 비웁니다.
        if (gamesFailed) {
          rows = rows.map(r => Object.assign({}, r, { r: null, ra: null, diff: null, pyth: null, expw: null, luck: null, runsFrom: 'none' }));
        }
        // 끝난 시즌에서 경기 결과가 공식 순위표와 다르면 알립니다. 진행 중
        // 시즌은 실시간 순위와 하루 차이가 정상이라 알리지 않습니다.
        if (splits && y < S.pbpMax) {
          let mm = M.recordMismatches(v.rank, splits);
          if (st.team) mm = mm.filter(x => x.team === st.team);
          if (mm.length) {
            alerts.push({
              kind: 'info',
              text: '경기 결과 원천이 공식 기록과 다른 경기(빠지거나 끊기거나 결과가 다른 경기)가 있어, 아래 팀의 득실·홈·원정·1점차·월별·상대 전적이 공식 기록과 조금 다릅니다: '
                + mm.map(x => `${x.team}(공식 ${x.official.w}-${x.official.l}-${x.official.d}, 경기 결과 ${x.games.w}-${x.games.l}-${x.games.d})`).join(', ') + '.',
            });
          }
        }
        if (!rows.length && !S.refs.errors.length) alerts.push({ kind: 'warn', text: `순위표에 ${y} 시즌이 없습니다.` });
        caveat = REC_CAVEAT + (y === 1999 || y === 2000 ? LEAGUE2_CAVEAT : '') + (live ? LIVE_CAVEAT : '');
      }
    } else if (m === 'range') {
      const rr = S.range[st.start + '|' + st.end];
      errAlerts(alerts, rr.errors);
      const ix = M.indexRefs(S.refs);
      const tbl = st.tab === 'bat' ? M.rangeBattingTable(rr.data, y, ix) : M.rangePitchingTable(rr.data, y, ix);
      rows = tbl.rows;
      league = rows.length ? tbl.league : null;
      alerts.push({ kind: 'info', text: '기간별은 경기 기록으로 세서 RBI·ERA·FIP 등은 없습니다. 계산할 수 없는 칸은 숨겼습니다.' });
      const d = rr.data || {};
      $('range-note').textContent = d.games ? `반영: ${fmtYmd(d.date_min)} ~ ${fmtYmd(d.date_max)}, ${d.games}경기` : (rr.errors.length ? '' : '해당 기간 경기 없음');
      caveat = d.note || RANGE_CAVEAT;
    } else {
      const sd = S.season[y];
      errAlerts(alerts, sd.errors);
      const live = liveRank(alerts);
      const v = M.seasonView({ batters: sd.batters, pitchers: sd.pitchers, refs: S.refs, season: y, rank: live || undefined });
      if (v.unmatched.length) {
        alerts.push({ kind: 'warn', text: `순위표와 선수 기록의 팀 이름이 맞지 않습니다: ${v.unmatched.join(', ')}. 이 팀의 경기 수는 '-'로 둡니다.` });
      }
      const tbl = st.tab === 'bat' ? v.bat : v.pit;
      rows = tbl.rows;
      league = rows.length ? tbl.league : null;
      caveat = SEASON_CAVEAT + (y === S.pbpMax ? LIVE_SEASON_CAVEAT : '') + (y < PBP_MIN ? OLD_CAVEAT : '') + (live ? LIVE_CAVEAT : '');
    }

    fillTeams(rows.map(r => r.team));
    const shown = st.team ? rows.filter(r => r.team === st.team) : rows;
    const sort = pickSort(st, keys, rows);
    // 팀을 골랐을 때 # 는 전체 팀을 같은 정렬로 세운 순위입니다.
    let rankOf;
    if (st.team) {
      const sc = cols.find(c => c.key === sort.key);
      const rankMap = {};
      (sc ? T.sortRows(rows, sc.key, sort.dir, sc.kind) : rows).forEach((r, i) => { rankMap[r.team] = i + 1; });
      rankOf = r => rankMap[r.team];
    }
    S.last = { cols: cols, rows: shown, league: league, sort: sort, rankOf: rankOf };
    $('ts-table').innerHTML = shown.length
      ? T.renderTable({ cols: cols, rows: shown, league: league, sort: sort, teamHref: teamHref, rankOf: rankOf })
      : createEmptyState(m === 'range' ? '해당 기간 기록이 없습니다.' : '해당 시즌 기록이 없습니다.');

    if (st.tab === 'rec') {
      const order = rows.slice().sort((a, b) => (b.pct || 0) - (a.pct || 0)).map(r => r.team);
      $('ts-h2h').innerHTML = splits ? R.h2hHtml(splits, order, st.team) : (gamesFailed ? R.gamesErrorHtml() : R.noGamesHtml(y));
      $('ts-monthly').innerHTML = splits ? R.monthlyHtml(splits, order, st.team) : (gamesFailed ? R.gamesErrorHtml() : R.noGamesHtml(y));
    }
    $('caveat-note').textContent = caveat;
    renderAlerts(alerts);
    syncRecordLink();
    if (!$('col-panel').classList.contains('hidden')) renderColPanel();
  }

  /** 주소를 쓰고, 필요한 데이터를 받은 뒤 그립니다. 늦게 온 이전 응답은 버립니다. */
  async function refresh(opt) {
    opt = opt || {};
    const seq = ++S.seq;
    if (!opt.noUrl) writeUrl(opt.replace);
    $('ts-table').innerHTML = createLoadingSpinner();
    try {
      await ensureData();
    } catch (e) {
      if (seq !== S.seq) return;
      console.error(e);
      $('ts-table').innerHTML = createErrorMessage('팀 기록을 불러오는데 실패했습니다.');
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
    a.download = csvName(S.st, mode());
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
      const d = TS.columns.def(S.st.tab, el.dataset.col);
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

  function bind() {
    $('ts-tabs').addEventListener('click', function (e) {
      const b = e.target.closest('[data-tab]');
      if (!b || b.dataset.tab === S.st.tab) return;
      S.st.tab = b.dataset.tab;
      S.st.sort = '';
      S.st.dir = '';
      refresh();
    });
    $('ts-groups').addEventListener('click', function (e) {
      const b = e.target.closest('[data-group]');
      if (!b) return;
      const g = b.dataset.group;
      if (g === 'custom') S.panelOpen = S.st.group === 'custom' ? !S.panelOpen : true;
      if (g !== S.st.group) { S.st.group = g; S.st.sort = ''; S.st.dir = ''; }
      writeUrl();
      render();
    });
    $('season-select').addEventListener('change', function (e) {
      S.st.season = Number(e.target.value);
      S.st.start = '';
      S.st.end = '';
      syncRange();
      refresh();
    });
    $('team-select').addEventListener('change', function (e) {
      S.st.team = e.target.value;
      writeUrl();
      render();
    });
    $('range-go').addEventListener('click', function () {
      const a = $('range-start').value, b = $('range-end').value;
      if (!a || !b) return;
      const yy = String(S.st.season) + '-';
      if (!a.startsWith(yy) || !b.startsWith(yy)) {
        $('range-note').textContent = `기간은 ${S.st.season}년 안에서 골라 주세요.`;
        return;
      }
      S.st.start = a <= b ? a : b;
      S.st.end = a <= b ? b : a;
      S.st.sort = '';
      S.st.dir = '';
      syncRange();
      refresh();
    });
    $('range-clear').addEventListener('click', function () {
      S.st.start = '';
      S.st.end = '';
      syncRange();
      refresh();
    });
    $('csv-btn').addEventListener('click', downloadCsv);
    $('link-btn').addEventListener('click', copyLink);
    $('ts-table').addEventListener('click', function (e) {
      const th = e.target.closest('th.sortable');
      if (!th) return;
      const k = th.dataset.key;
      const cur = pickSort(S.st, keysNow(), S.last && S.last.rows);
      if (cur.key === k) S.st.dir = cur.dir === 'asc' ? 'desc' : 'asc';
      else {
        const d = TS.columns.def(S.st.tab, k);
        S.st.dir = d && d.better === 'low' ? 'asc' : 'desc';
      }
      S.st.sort = k;
      render();
      writeUrl(true);
    });
    $('col-list').addEventListener('change', function (e) {
      const k = e.target.getAttribute('data-col');
      if (!k) return;
      const tab = S.st.tab;
      const on = new Set(S.custom[tab] || TS.columns.GROUPS[tab].dash);
      if (e.target.checked) on.add(k); else on.delete(k);
      S.custom[tab] = TS.columns.ORDER[tab].filter(x => on.has(x));
      writeUrl(true);
      render();
    });
    document.querySelectorAll('[data-col-preset]').forEach(function (b) {
      b.addEventListener('click', function () {
        const tab = S.st.tab;
        S.custom[tab] = b.dataset.colPreset === 'all' ? TS.columns.ORDER[tab].slice() : TS.columns.GROUPS[tab].dash.slice();
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
      fillSeasons();
      syncRange();
      refresh({ noUrl: true });
    });
    bindTips();
  }

  async function init() {
    try {
      S.st = parseState(location.search);
      $('ts-table').innerHTML = createLoadingSpinner();
      const base = root.KBO_API_BASE;
      const got = await Promise.all([TS.data.loadSeasons(base), TS.data.loadRefs(base)]);
      S.seasons = got[0].seasons;
      S.seasonErrors = got[0].errors;
      S.refs = got[1];
      S.pbpMax = S.seasons[0];
      normalize();
      if (S.st.group === 'custom') S.panelOpen = true;
      fillSeasons();
      syncRange();
      bind();
      await refresh({ replace: true });
    } catch (e) {
      console.error(e);
      $('ts-table').innerHTML = createErrorMessage('팀 기록을 불러오는데 실패했습니다.');
    }
  }

  const api = { parseState, toSearch, visibleKeys, defaultSort, pickSort, csvName, dataReady };
  TS.page = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document.getElementById('ts-table')) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
})(typeof window !== 'undefined' ? window : globalThis);
