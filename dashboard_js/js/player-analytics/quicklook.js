/*
 * 선수 분석 페이지의 한눈에 보기 표와 헤더 글자를 만드는 순수 함수입니다.
 * 화면(DOM)에는 손대지 않습니다.
 *
 * 합계·비율은 공용 TeamStats.metrics, 숫자 표시는 TeamStats.columns.fmt 를
 * 가져다 씁니다(호출할 때 읽으므로 불러오는 순서는 이 파일이 뒤면 됩니다).
 * 설계: docs/superpowers/specs/2026-10-04-player-analytics-fangraphs-header-design.md
 *
 * 원칙은 공용 모듈과 같습니다. 비율을 평균 내지 않고 합계에서 다시 셉니다.
 * 셀 수 없는 값은 '-' 입니다.
 */
(function (root) {
  'use strict';
  const PA = root.PlayerAnalytics = root.PlayerAnalytics || {};
  const TS = function () { return root.TeamStats; };

  // [라벨, 합계 키, 표시 형식]. 'pct' 는 소수 1자리 뒤에 % 를 붙입니다.
  // 투수는 무브먼트 카드 높이에 맞춰 줄을 더 둡니다(evan 의견).
  const ROWS = {
    pit: [
      ['W', 'w', 'int'], ['L', 'l', 'int'], ['SV', 'sv', 'int'], ['HLD', 'hld', 'int'],
      ['G', 'g', 'int'], ['GS', 'gs', 'int'], ['IP', 'outs', 'ip'],
      ['K%', 'kpct', 'pct'], ['BB%', 'bbpct', 'pct'], ['K-BB%', 'kbbpct', 'pct'], ['K/9', 'k9', 'f2'], ['BB/9', 'bb9', 'f2'], ['HR/9', 'hr9', 'f2'], ['BABIP', 'babip', 'avg3'], ['ERA', 'era', 'f2'], ['WHIP', 'whip', 'f2'],
    ],
    bat: [
      ['G', 'g', 'int'], ['PA', 'pa', 'int'], ['HR', 'hr', 'int'], ['R', 'r', 'int'], ['RBI', 'rbi', 'int'],
      ['BB%', 'bbpct', 'pct'], ['K%', 'kpct', 'pct'],
      ['AVG', 'avg', 'avg3'], ['OBP', 'obp', 'avg3'], ['SLG', 'slg', 'avg3'], ['OPS', 'ops', 'avg3'],
    ],
  };

  // 퓨처스 한눈에 보기 줄입니다. 퓨처스 응답의 칸 이름 그대로입니다.
  // wOBA·wRC+ 는 2군에 타석 단위 자료가 없어 만들 수 없습니다.
  const FUT = {
    batter: ['G', 'PA', 'AB', 'R', 'H', 'HR', 'RBI', 'AVG', 'OBP', 'SLG'],
    pitcher: ['W', 'L', 'ERA', 'G', 'SV', 'HLD', 'IP', 'H', 'BB', 'SO'],
  };

  function kindOf(player) {
    return player && player.position === '투수' ? 'pit' : 'bat';
  }

  function seasonRows(player, kind) {
    return (kind === 'pit' ? player.pitcher_seasons : player.batter_seasons) || [];
  }

  /**
   * 퀵룩 기준 연도입니다. 한국 시각 올해(kstYear)와 /stats/seasons 최신 시즌 중 작은 쪽입니다.
   * 비시즌(1~3월)에 기록 없는 새해가 나오고 실제 시즌 하나가 빠지던 것을 막습니다(2027 대비).
   */
  function baseYear(kstYear, seasonsRes) {
    const ys = ((seasonsRes && seasonsRes.seasons) || []).map(Number).filter(function (y) { return Number.isFinite(y); });
    return ys.length ? Math.min(kstYear, Math.max.apply(null, ys)) : kstYear;
  }

  /** 최근 3시즌입니다. 현역은 올해 기준, 은퇴는 마지막 활동 시즌 기준입니다. */
  function pickSeasons(player, thisYear) {
    const ys = [].concat(player.pitcher_seasons || [], player.batter_seasons || [])
      .map(function (s) { return Number(s.season); })
      .filter(function (y) { return Number.isFinite(y); });
    const last = ys.length ? Math.max.apply(null, ys) : thisYear;
    const a = player.is_active ? thisYear : last;
    return [a - 2, a - 1, a];
  }

  /**
   * 행 여러 개를 한 덩어리로 더하고 비율을 다시 셉니다. 행이 없으면 null.
   * 공용 합계 함수는 player_team 별로 묶으므로 팀을 같은 값으로 바꾼 사본을
   * 넘깁니다. 출장 경기(games)는 공용 합계 키에 없어 따로 더합니다.
   */
  function total(rows, kind) {
    if (!rows || !rows.length) return null;
    const M = TS().metrics;
    const flat = rows.map(function (r) { return Object.assign({}, r, { player_team: '_' }); });
    const t = (kind === 'pit' ? M.sumPitching(flat) : M.sumBatting(flat))._;
    t.g = rows.reduce(function (s, r) { return s + M.num(r.games); }, 0);
    return Object.assign(t, kind === 'pit' ? M.pitchingRates(t) : M.battingRates(t));
  }

  function teamsOf(rows) {
    const out = [];
    rows.forEach(function (r) {
      if (r.player_team && out.indexOf(r.player_team) === -1) out.push(r.player_team);
    });
    return out.length ? out.join('/') : '-';
  }

  function cell(v, kind) {
    const fmt = TS().columns.fmt;
    if (kind === 'pct') {
      const s = fmt(v, 'f1');
      return s === '-' ? s : s + '%';
    }
    return fmt(v, kind);
  }

  /** 1군 한눈에 보기 입니다. 칸은 최근 3시즌 + 통산입니다. */
  function build(player, thisYear) {
    const kind = kindOf(player);
    const all = seasonRows(player, kind);
    const cols = pickSeasons(player, thisYear).map(function (y) {
      const rs = all.filter(function (s) { return Number(s.season) === y; });
      return { head: String(y), team: rs.length ? teamsOf(rs) : '-', t: total(rs, kind) };
    });
    cols.push({ head: '통산', team: '-', t: total(all, kind) });
    // 리그(1군·퓨처스) 줄은 두지 않습니다. 위의 1군·퓨처스 전환이 이미 알려 줍니다(evan 결정).
    const rows = [['팀'].concat(cols.map(function (c) { return c.team; }))];
    ROWS[kind].forEach(function (d) {
      rows.push([d[0]].concat(cols.map(function (c) { return c.t ? cell(c.t[d[1]], d[2]) : '-'; })));
    });
    return { head: ['시즌'].concat(cols.map(function (c) { return c.head; })), rows: rows, career: true };
  }

  function text(x) {
    return x === null || x === undefined || x === '' ? '-' : String(x);
  }

  /** 퓨처스 한눈에 보기 입니다. 응답은 최신 시즌이 앞이고, 통산 칸은 없습니다. */
  function buildFutures(seasons, kind) {
    const use = (seasons || []).slice(0, 3).reverse();
    if (!use.length) return null;
    const metrics = FUT[kind] || FUT.batter;
    const rows = [['팀'].concat(use.map(function (s) { return text(s.team); }))];
    metrics.forEach(function (m) {
      rows.push([m].concat(use.map(function (s) { return text(s[m]); })));
    });
    return { head: ['시즌'].concat(use.map(function (s) { return String(s.season); })), rows: rows, career: false };
  }

  /** 연도별 기록이 없는 퓨처스 선수의 올 시즌 요약입니다. */
  function summary(columns, cells) {
    const rows = [];
    (columns || []).forEach(function (c, i) { rows.push([c, text(cells && cells[i])]); });
    return { head: ['시즌', '올해'], rows: rows, career: false };
  }

  // 프로필 카드 아래 '시즌 타일' 지표입니다. [라벨, 합계 키, 표시 형식]
  const TILES = {
    pit: [['ERA', 'era', 'f2'], ['IP', 'outs', 'ip'], ['K%', 'kpct', 'pct'], ['K-BB%', 'kbbpct', 'pct']],
    bat: [['AVG', 'avg', 'avg3'], ['OPS', 'ops', 'avg3'], ['HR', 'hr', 'int'], ['RBI', 'rbi', 'int']],
  };
  // 퓨처스 응답에는 OPS 가 없어 타자는 OBP·SLG 를 씁니다.
  const FUT_TILES = { pitcher: ['ERA', 'IP', 'SO', 'G'], batter: ['AVG', 'OBP', 'SLG', 'HR'] };

  /**
   * 기록이 있는 가장 최근 1군 시즌의 핵심 숫자 넷입니다. 기록이 없으면 null.
   * 비시즌·은퇴 선수도 빈 타일이 되지 않도록 '올해' 가 아니라 마지막 기록 시즌을 씁니다.
   */
  function seasonTiles(player) {
    const kind = kindOf(player);
    const all = seasonRows(player, kind);
    const ys = all.map(function (s) { return Number(s.season); }).filter(Number.isFinite);
    if (!ys.length) return null;
    const y = Math.max.apply(null, ys);
    const t = total(all.filter(function (s) { return Number(s.season) === y; }), kind);
    return {
      title: y + ' 시즌',
      items: TILES[kind].map(function (d) { return { label: d[0], value: cell(t[d[1]], d[2]) }; }),
    };
  }

  /** 퓨처스 최신 시즌(응답 맨 앞)의 핵심 숫자 넷입니다. 기록이 없으면 null. */
  function futuresTiles(seasons, kind) {
    const s = (seasons || [])[0];
    if (!s) return null;
    return {
      title: s.season + ' 퓨처스',
      items: (FUT_TILES[kind] || FUT_TILES.batter).map(function (k) { return { label: k, value: text(s[k]) }; }),
    };
  }

  /** 타일 묶음 HTML 입니다. null 이면 빈 글자입니다. */
  function tilesHtml(t) {
    if (!t) return '';
    return '<div class="pa-tiles"><div class="pa-tiles-title">' + esc(t.title) + '</div><div class="pa-tiles-grid">'
      + t.items.map(function (i) {
        return '<div class="pa-tile"><div class="pa-tile-label">' + esc(i.label)
          + '</div><div class="pa-tile-value">' + esc(i.value) + '</div></div>';
      }).join('')
      + '</div></div>';
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  /** Model 을 촘촘한 세로 표 HTML 로 바꿉니다. 첫 칸은 라벨, 통산 칸은 강조입니다. */
  function tableHtml(m) {
    const last = m.head.length - 1;
    const one = function (x, i, tag) {
      const cls = i === 0 ? 'pa-ql-label' : (m.career && i === last ? 'pa-ql-career' : '');
      return '<' + tag + (cls ? ' class="' + cls + '"' : '') + '>' + esc(x) + '</' + tag + '>';
    };
    return '<div class="pa-ql-wrap"><table class="pa-ql"><thead><tr>'
      + m.head.map(function (x, i) { return one(x, i, 'th'); }).join('')
      + '</tr></thead><tbody>'
      + m.rows.map(function (r) {
        return '<tr>' + r.map(function (x, i) { return one(x, i, 'td'); }).join('') + '</tr>';
      }).join('')
      + '</tbody></table></div>';
  }

  /** 만 나이(년·개월)입니다. 생일은 YYYYMMDD. 못 읽거나 미래면 null. */
  function ageParts(birthday, today) {
    const s = String(birthday === null || birthday === undefined ? '' : birthday);
    if (!/^\d{8}$/.test(s)) return null;
    const y = Number(s.slice(0, 4)), mo = Number(s.slice(4, 6)), d = Number(s.slice(6, 8));
    let months = (today.getFullYear() - y) * 12 + (today.getMonth() + 1 - mo);
    if (today.getDate() < d) months--;
    if (months < 0) return null;
    return { years: Math.floor(months / 12), months: months % 12 };
  }

  /** 생년월일 글자(YYYY.MM.DD)입니다. YYYYMMDD 가 아니면 null. */
  function dobText(birthday) {
    const s = String(birthday === null || birthday === undefined ? '' : birthday);
    return /^\d{8}$/.test(s) ? s.slice(0, 4) + '.' + s.slice(4, 6) + '.' + s.slice(6, 8) : null;
  }

  const api = { ROWS, FUT, kindOf, baseYear, pickSeasons, total, build, buildFutures, summary, tableHtml, ageParts, dobText,
    TILES, FUT_TILES, seasonTiles, futuresTiles, tilesHtml };
  PA.quicklook = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
