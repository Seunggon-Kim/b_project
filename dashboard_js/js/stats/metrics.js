/*
 * 팀·선수 통계 계산입니다. 화면(DOM)에는 손대지 않습니다.
 *
 * 브라우저에서는 window.TeamStats.metrics 로, Node 검증 스크립트에서는
 * vm 으로 불러 씁니다. 식의 근거는 docs/superpowers/specs/ 의
 * 2026-10-03-team-stats-fangraphs-design.md 3장과
 * 2026-10-04-player-stats-fangraphs-design.md 3장입니다.
 *
 * 원칙: 선수 비율을 평균 내지 않습니다. 합계(성분)에서 다시 셉니다.
 * 계산할 수 없는 값은 0 이 아니라 null 입니다. 화면에서 '-' 가 됩니다.
 */
(function (root) {
  'use strict';
  const TS = root.TeamStats = root.TeamStats || {};

  /** 서버가 숫자를 문자열로 줄 때가 있습니다. 비거나 못 읽으면 0 입니다. */
  function num(v) {
    if (v === null || v === undefined || v === '') return 0;
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  }

  /** 나눗셈입니다. 분모가 0 이하이거나 결과가 숫자가 아니면 null 입니다. */
  function div(a, b) {
    const r = a / b;
    return b > 0 && Number.isFinite(r) ? r : null;
  }

  /** 객체 안의 숫자가 아닌 값(NaN·Infinity)을 null 로 바꿉니다. */
  function clean(o) {
    for (const k of Object.keys(o)) {
      if (typeof o[k] === 'number' && !Number.isFinite(o[k])) o[k] = null;
    }
    return o;
  }

  /**
   * 이닝 글자를 아웃 수로 바꿉니다. '81 1/3' → 244, '7' → 21.
   *
   * '2/3' 처럼 분수만 있는 이닝도 읽습니다. 예전 페이지는 이것을 0 으로
   * 읽어 2025 투수 4명의 이닝이 빠졌습니다.
   */
  function ipOuts(s) {
    const t = String(s === null || s === undefined ? '' : s).trim();
    const m = t.match(/^(?:(\d+))?\s*(?:([12])\/3)?$/);
    if (!m || (!m[1] && !m[2])) return 0;
    return (m[1] ? Number(m[1]) * 3 : 0) + (m[2] ? Number(m[2]) : 0);
  }

  // 공식 타자 기록 칸 → 팀 합계 키입니다.
  // `single` 칸의 실제 값은 안타(H)입니다(수집기가 KBO 의 H 를 넣습니다).
  const BAT_SUM = {
    pa: 'plate_appearance', ab: 'at_bat', r: 'run', h: 'single',
    d2: 'double', d3: 'triple', hr: 'home_run', tb: 'total_bases',
    rbi: 'run_batted_in', bb: 'base_on_balls', ibb: 'intentional_base_on_balls',
    hbp: 'hit_by_pitch', so: 'strikeout', sf: 'sacrifice_fly', sh: 'sacrifice_bunts',
    gdp: 'ground_into_double_play', multi: 'multi_hits', xbh: 'extra_base_hits',
    go: 'ground_outs', ao: 'air_outs', gw: 'gw_rbi',
  };
  const BAT_KEYS = Object.keys(BAT_SUM);

  /** 선수 행을 팀별로 더합니다. extra(a, r) 로 칸을 더 셀 수 있습니다. */
  function sumBy(rows, map, extra) {
    const out = {};
    for (const r of rows || []) {
      const team = r.player_team;
      if (!team) continue;
      const a = out[team] || (out[team] = { team: team });
      for (const k in map) a[k] = (a[k] || 0) + num(r[map[k]]);
      if (extra) extra(a, r);
    }
    return out;
  }

  function sumBatting(rows) {
    return sumBy(rows, BAT_SUM);
  }

  /** 타격 비율입니다. 모두 합계에서 다시 셉니다. */
  function battingRates(t) {
    const o = {
      single: t.h - t.d2 - t.d3 - t.hr,
      avg: div(t.h, t.ab),
      obp: div(t.h + t.bb + t.hbp, t.ab + t.bb + t.hbp + t.sf),
      slg: div(t.tb, t.ab),
      babip: div(t.h - t.hr, t.ab - t.so - t.hr + t.sf),
      kpct: div(t.so * 100, t.pa),
      bbpct: div(t.bb * 100, t.pa),
      bbk: div(t.bb, t.so),
      goao: div(t.go, t.ao),
    };
    o.ops = o.obp === null || o.slg === null ? null : o.obp + o.slg;
    o.iso = o.slg === null || o.avg === null ? null : o.slg - o.avg;
    return clean(o);
  }

  /**
   * 참조 표를 찾기 쉬운 모양으로 바꿉니다.
   * refs = { weights, pf, stadium, rank } (각 /db/table 의 rows)
   */
  function indexRefs(refs) {
    refs = refs || {};
    const ix = { weights: {}, pf: {}, home: {}, pfOk: false };
    for (const r of refs.weights || []) ix.weights[num(r.season)] = r;
    for (const r of refs.pf || []) ix.pf[num(r.season) + '|' + r.stadium] = num(r.run_pf);
    for (const r of refs.stadium || []) ix.home[r.player_team + '|' + num(r.season)] = r.stadium;
    ix.pfOk = (refs.pf || []).length > 0 && (refs.stadium || []).length > 0;
    return ix;
  }

  /**
   * 반 구장 보정입니다. 선수 wRC+ 의 pf_half 와 같습니다.
   *   (홈구장 run_pf + 1000) / 2000
   * 2008 전은 파크팩터가 없어 1(보정 없음)입니다. 참조 표를 못 받았으면
   * null 입니다. 홈구장이나 값이 없으면 선수 wRC+ 계산기처럼 중립(1000)
   * 으로 봅니다(park_factors/build_wrc_plus.py).
   */
  function pfHalf(ix, team, season) {
    if (season < 2008) return 1;
    if (!ix || !ix.pfOk) return null;
    const st = ix.home[team + '|' + season];
    const run = st ? ix.pf[season + '|' + st] : 0;
    return ((run > 0 ? run : 1000) + 1000) / 2000;
  }

  /**
   * wOBA 입니다. 선수 wOBA 와 같은 식입니다(BB 는 고의4구 포함).
   *   (wBB·BB + wHBP·HBP + w1B·1B + w2B·2B + w3B·3B + wHR·HR) / (AB + BB + SF + HBP)
   */
  function wobaOf(t, w) {
    if (!w) return null;
    const one = t.h - t.d2 - t.d3 - t.hr;
    const den = t.ab + t.bb + t.sf + t.hbp;
    if (!(den > 0)) return null;
    const v = (num(w.fg_wBB) * t.bb + num(w.fg_wHBP) * t.hbp + num(w.fg_w1B) * one
      + num(w.fg_w2B) * t.d2 + num(w.fg_w3B) * t.d3 + num(w.fg_wHR) * t.hr) / den;
    return Number.isFinite(v) ? v : null;
  }

  /** 여러 합계 객체를 keys 만 더합니다. */
  function sumObjects(list, keys) {
    const s = {};
    for (const k of keys) s[k] = 0;
    for (const o of list) for (const k of keys) s[k] += num(o[k]);
    return s;
  }

  /**
   * 타격 리그 기준값입니다. lg 는 리그 합계(성분)입니다. 팀 표와 선수 표가
   * 같은 기준값을 쓰도록 한 곳에서 셉니다.
   */
  function battingCtx(lg, season, ix) {
    const w = (ix && ix.weights[season]) || null;
    return {
      lgR: battingRates(lg),
      w: w,
      lgWoba: wobaOf(lg, w),
      L: div(lg.r, lg.pa),
      scale: w ? num(w.wOBA_scale) : 0,
    };
  }

  /** 표의 ctx 로 내보내는 리그 기준값입니다. */
  function battingCtxOut(c) {
    return { lgWoba: c.lgWoba, L: c.L, scale: c.scale, lgObp: c.lgR.obp, lgSlg: c.lgR.slg, hasWeights: !!c.w };
  }

  /**
   * 한 줄(팀 하나 또는 선수 한 명)의 타격 지표입니다. t 는 합계(성분)이고,
   * team 은 구장 보정에 쓸 팀입니다.
   */
  function battingRow(t, team, season, ix, c) {
    const row = Object.assign({}, t, battingRates(t));
    const pf = pfHalf(ix, team, season);
    row.woba = wobaOf(t, c.w);
    row.wraa = null;
    row.wrc = null;
    row.wrcp = null;
    if (row.woba !== null && c.lgWoba !== null && c.scale > 0 && t.pa > 0) {
      row.wraa = (row.woba - c.lgWoba) / c.scale * t.pa;
      if (c.L !== null) {
        row.wrc = (row.wraa / t.pa + c.L) * t.pa;
        // 선수 wRC+ 와 같은 식: K + (2 - PF) * 100, K = (wRAA/PA) / L * 100
        if (pf !== null) row.wrcp = (row.wraa / t.pa) / c.L * 100 + (2 - pf) * 100;
      }
    }
    row.opsp = (row.obp !== null && row.slg !== null && c.lgR.obp > 0 && c.lgR.slg > 0 && pf)
      ? 100 * (row.obp / c.lgR.obp + row.slg / c.lgR.slg - 1) / pf
      : null;
    return row;
  }

  /**
   * 타격 표입니다. totals 는 sumBatting 결과(또는 기간별 합계)입니다.
   * keys 는 합계 키 목록입니다(기간별은 응답에 있는 칸만).
   */
  function battingTable(totals, season, ix, keys) {
    keys = keys || BAT_KEYS;
    const teams = Object.values(totals || {});
    const lg = sumObjects(teams, keys);
    const c = battingCtx(lg, season, ix);
    const rows = teams.map(t => battingRow(t, t.team, season, ix, c));

    const n = teams.length || 1;
    const league = { team: '리그 평균', isLeague: true };
    for (const k of keys) league[k] = lg[k] / n;
    Object.assign(league, c.lgR);
    league.single = c.lgR.single === null ? null : c.lgR.single / n;
    league.woba = c.lgWoba;
    league.wraa = c.lgWoba === null ? null : 0;
    league.wrc = c.lgWoba !== null && c.L !== null ? c.L * lg.pa / n : null;
    league.wrcp = rows.some(r => r.wrcp !== null) ? 100 : null;
    league.opsp = rows.some(r => r.opsp !== null) ? 100 : null;

    return { rows: rows, league: league, ctx: battingCtxOut(c) };
  }

  // 공식 투수 기록 칸 → 팀 합계 키입니다. 이닝은 sumPitching 이 outs 로 셉니다.
  const PIT_SUM = {
    h: 'hits', r: 'run', er: 'earned_run', bb: 'base_on_balls', so: 'strikeout',
    hr: 'home_run', w: 'wins', l: 'losses', sv: 'save', hld: 'hold',
    hbp: 'hit_by_pitch', ibb: 'intentional_base_on_balls', cg: 'complete_game',
    sho: 'shutout', qs: 'quality_start', bs: 'blown_save', tbf: 'total_batters_faced',
    np: 'number_of_pitchers', d2: 'double', d3: 'triple', wp: 'wild_pitch', bk: 'balk',
    gs: 'games_started', gf: 'games_finished', svo: 'save_opportunity',
    gidp: 'ground_into_double_play', go: 'ground_outs', ao: 'air_outs',
    sh: 'sacrifice_bunts', sf: 'sacrifice_fly',
  };
  const PIT_KEYS = Object.keys(PIT_SUM).concat(['outs']);

  function sumPitching(rows) {
    return sumBy(rows, PIT_SUM, function (a, r) {
      a.outs = (a.outs || 0) + ipOuts(r.innings_pitched);
    });
  }

  /** 투구 비율입니다. 응답에 없는 칸이 있으면 그 지표는 null 입니다. */
  function pitchingRates(t) {
    const outs = t.outs;
    const per9 = function (x) { return div(x * 27, outs); };
    const o = {
      era: per9(t.er),
      ra9: per9(t.r),
      whip: div((t.h + t.bb) * 3, outs),
      k9: per9(t.so),
      bb9: per9(t.bb),
      h9: per9(t.h),
      hr9: per9(t.hr),
      kbb: div(t.so, t.bb),
      kpct: div(t.so * 100, t.tbf),
      bbpct: div(t.bb * 100, t.tbf),
      // 피안타율: 상대 타수 = TBF - BB - HBP - SH - SF (투수 기록의 BB 는 고의4구 포함)
      oavg: div(t.h, t.tbf - t.bb - t.hbp - t.sh - t.sf),
      babip: div(t.h - t.hr, t.tbf - t.bb - t.hbp - t.sh - t.so - t.hr),
      lobpct: div((t.h + t.bb + t.hbp - t.r) * 100, t.h + t.bb + t.hbp - 1.4 * t.hr),
      pip: div(t.np * 3, outs),
      goao: div(t.go, t.ao),
    };
    o.kbbpct = o.kpct === null || o.bbpct === null ? null : o.kpct - o.bbpct;
    return clean(o);
  }

  /** FIP 의 상수 앞부분입니다: (13·HR + 3·(BB − IBB + HBP) − 2·SO) / IP */
  function fipCore(t) {
    return div((13 * t.hr + 3 * (t.bb - t.ibb + t.hbp) - 2 * t.so) * 3, t.outs);
  }

  /** 투구 리그 기준값입니다. FIP 상수는 그해 리그 합으로 직접 셉니다. */
  function pitchingCtx(lg) {
    const lgR = pitchingRates(lg);
    const lgCore = fipCore(lg);
    return { lgR: lgR, cfip: lgR.era !== null && lgCore !== null ? lgR.era - lgCore : null };
  }

  /** 한 줄(팀 하나 또는 선수 한 명)의 투구 지표입니다. team 은 구장 보정에 쓸 팀입니다. */
  function pitchingRow(t, team, season, ix, c) {
    const row = Object.assign({}, t, pitchingRates(t));
    const core = fipCore(t);
    const pf = pfHalf(ix, team, season);
    const lgEra = c.lgR.era;
    row.fip = core !== null && c.cfip !== null ? core + c.cfip : null;
    row.ef = row.era !== null && row.fip !== null ? row.era - row.fip : null;
    row.erap = row.era !== null && lgEra > 0 && pf !== null
      ? 100 * row.era * (2 - pf) / lgEra : null;
    row.fipp = row.fip !== null && lgEra > 0 && pf !== null
      ? 100 * row.fip * (2 - pf) / lgEra : null;
    return row;
  }

  /**
   * 투구 표입니다. FIP 상수는 그해 리그 합으로 직접 셉니다.
   *   cFIP = 리그 ERA − 리그 fipCore
   * 그래서 리그 평균 FIP = 리그 ERA 입니다.
   */
  function pitchingTable(totals, season, ix, keys) {
    keys = keys || PIT_KEYS;
    const teams = Object.values(totals || {});
    const lg = sumObjects(teams, keys);
    const c = pitchingCtx(lg);
    const rows = teams.map(t => pitchingRow(t, t.team, season, ix, c));

    const n = teams.length || 1;
    const league = { team: '리그 평균', isLeague: true };
    for (const k of keys) league[k] = lg[k] / n;
    Object.assign(league, c.lgR);
    league.fip = c.cfip !== null ? c.lgR.era : null;
    league.ef = league.fip !== null ? 0 : null;
    league.erap = rows.some(r => r.erap !== null) ? 100 : null;
    league.fipp = rows.some(r => r.fipp !== null) ? 100 : null;

    return { rows: rows, league: league, ctx: { lgEra: c.lgR.era, cfip: c.cfip } };
  }

  /** 공식 승률 문자열(예 '0.603')을 숫자로 읽습니다. 비었거나 숫자가 아니면 W÷(W+L)입니다. */
  function officialPct(p, w, l) {
    if (p !== null && p !== undefined && String(p).trim() !== '') {
      const n = Number(p);
      if (Number.isFinite(n)) return n;
    }
    return div(w, w + l);
  }

  /**
   * 그 시즌의 공식 순위표입니다. 팀-시즌 한 줄씩입니다(1982~1988 도 시즌
   * 합계). 1999·2000 은 드림·매직 양대 리그라 승차는 리그 안 값입니다.
   */
  function rankFor(rankRows, season) {
    const out = {};
    for (const r of rankRows || []) {
      if (num(r.season) !== season) continue;
      const w = num(r.wins), l = num(r.losses), d = num(r.draws);
      out[r.team_name] = {
        team: r.team_name,
        rank: num(r.rank),
        league: r.league || '단일',
        g: num(r.games),
        w: w, l: l, d: d,
        pct: officialPct(r.pct, w, l),
        gb: r.gb === null || r.gb === undefined || r.gb === '' ? null : num(r.gb),
      };
    }
    return out;
  }

  /**
   * 실시간 순위(/standings)를 rankFor 와 같은 모양으로 바꿉니다. 올해만
   * 씁니다. 저장된 순위표는 시즌 중 갱신이 늦을 수 있습니다(2026 은 8월
   * 말 값에 멈춰 있었습니다).
   */
  function rankFromStandings(teams) {
    const out = {};
    for (const t of teams || []) {
      if (!t || !t.team) continue;
      const w = num(t.wins), l = num(t.losses), d = num(t.draws);
      out[t.team] = {
        team: t.team,
        rank: num(t.rank),
        league: '단일',
        g: num(t.games),
        w: w, l: l, d: d,
        pct: officialPct(t.pct, w, l),
        gb: t.gb === null || t.gb === undefined || t.gb === '' ? null : num(t.gb),
      };
    }
    return out;
  }

  /** 피타고리안 기대 승률입니다. R^1.83 / (R^1.83 + RA^1.83) */
  function pythag(r, ra) {
    if (!(r > 0) || !(ra > 0)) return null;
    const a = Math.pow(r, 1.83), b = Math.pow(ra, 1.83);
    return a / (a + b);
  }

  function emptyWL() { return { w: 0, l: 0, d: 0 }; }
  function addWL(o, my, opp) {
    if (my > opp) o.w++;
    else if (my < opp) o.l++;
    else o.d++;
  }

  /**
   * 경기 결과로 팀별 승패·득실·홈/원정·1점차·월별·상대 전적을 셉니다.
   * 정규시즌만 셉니다. 점수가 같으면 무승부입니다.
   * start·end 는 YYYYMMDD 숫자이고, 없으면 전체입니다.
   * 월은 3·4월을 묶어 키 4 로, 9·10월도 묶어 키 9 로 둡니다.
   */
  function gameSplits(games, start, end) {
    const out = {};
    function get(t) {
      return out[t] || (out[t] = {
        team: t, g: 0, w: 0, l: 0, d: 0, r: 0, ra: 0,
        home: emptyWL(), away: emptyWL(), onerun: emptyWL(), month: {}, vs: {},
      });
    }
    for (const x of games || []) {
      if (x.game_type !== '정규시즌') continue;
      // 순위결정전(game_id 가 '6666' 으로 시작)은 정규시즌 개인 기록에는
      // 들어가지만 팀 순위(승패)에는 들어가지 않습니다. 팀 성적에서는 뺍니다.
      if (String(x.game_id || '').startsWith('6666')) continue;
      const day = num(x.game_date);
      if (start && day < start) continue;
      if (end && day > end) continue;
      if (x.home_score === null || x.home_score === undefined
        || x.away_score === null || x.away_score === undefined) continue;
      const hs = num(x.home_score), as = num(x.away_score);
      const month = Math.floor(day / 100) % 100;
      const mk = month <= 4 ? 4 : (month >= 9 ? 9 : month);
      const sides = [
        [x.home_team_id, hs, as, 'home', x.away_team_id],
        [x.away_team_id, as, hs, 'away', x.home_team_id],
      ];
      for (const s of sides) {
        const a = get(s[0]), my = s[1], opp = s[2];
        a.g++;
        a.r += my;
        a.ra += opp;
        addWL(a, my, opp);
        addWL(a[s[3]], my, opp);
        if (Math.abs(my - opp) === 1) addWL(a.onerun, my, opp);
        addWL(a.month[mk] || (a.month[mk] = emptyWL()), my, opp);
        addWL(a.vs[s[4]] || (a.vs[s[4]] = emptyWL()), my, opp);
      }
    }
    return out;
  }

  /**
   * 시즌 팀 성적 표입니다. 승패는 순위표입니다.
   *
   * 득실은 경기 결과(2008~)가 있으면 경기 점수 합입니다. 공식 선수 기록
   * 합은 트레이드된 선수의 시즌 득점을 마지막 팀에 몰아 잡아, 트레이드한
   * 팀의 득실이 틀립니다(2025 KIA 공식 619 vs 경기 668). 경기 결과가 없는
   * 2007 이전만 공식 기록 합을 씁니다.
   */
  function recordTable(rank, batTotals, pitTotals, splits) {
    return Object.keys(rank).map(function (team) {
      const k = rank[team];
      const b = batTotals && batTotals[team], p = pitTotals && pitTotals[team];
      const s = splits && splits[team];
      const fromGames = !!(s && s.g > 0);
      const r = fromGames ? s.r : (b ? b.r : null);
      const ra = fromGames ? s.ra : (p ? p.r : null);
      const py = pythag(r, ra);
      const expw = py === null ? null : py * (k.w + k.l);
      return Object.assign({}, k, {
        r: r, ra: ra,
        runsFrom: fromGames ? 'games' : 'official',
        diff: r !== null && ra !== null ? r - ra : null,
        pyth: py,
        expw: expw,
        luck: expw === null ? null : k.w - expw,
        home: s ? s.home : null,
        away: s ? s.away : null,
        onerun: s ? s.onerun : null,
      });
    });
  }

  /** 기간별 팀 성적 표입니다. 모두 경기 결과에서 셉니다. */
  function recordFromGames(splits) {
    const rows = Object.values(splits || {}).map(function (s) {
      const py = pythag(s.r, s.ra);
      const expw = py === null ? null : py * (s.w + s.l);
      return {
        team: s.team, g: s.g, w: s.w, l: s.l, d: s.d,
        pct: div(s.w, s.w + s.l), gb: null,
        r: s.r, ra: s.ra, diff: s.r - s.ra,
        pyth: py, expw: expw, luck: expw === null ? null : s.w - expw,
        home: s.home, away: s.away, onerun: s.onerun,
      };
    });
    const top = rows.slice().sort((a, b) => (b.pct || 0) - (a.pct || 0))[0];
    rows.forEach(function (r) {
      r.gb = top ? ((top.w - r.w) + (r.l - top.l)) / 2 : null;
    });
    return rows;
  }

  /**
   * 경기 결과로 센 승·패·무가 공식 순위표와 다른 팀입니다. 원천 기록이
   * 빠지거나 끊긴 경기가 있으면 생깁니다. 화면은 끝난 시즌에서만 알립니다.
   */
  function recordMismatches(rank, splits) {
    const out = [];
    if (!rank || !splits) return out;
    for (const team of Object.keys(splits)) {
      const k = rank[team], s = splits[team];
      if (!k || !s) continue;
      if (k.w !== s.w || k.l !== s.l || k.d !== s.d) {
        out.push({
          team: team,
          official: { w: k.w, l: k.l, d: k.d, g: k.g },
          games: { w: s.w, l: s.l, d: s.d, g: s.g },
        });
      }
    }
    return out;
  }

  /** 시즌 보기 전체입니다. 팀 행의 g 는 순위표 경기 수로 바꿉니다. */
  function seasonView(input) {
    const season = num(input.season);
    const ix = indexRefs(input.refs);
    const batTotals = sumBatting(input.batters);
    const pitTotals = sumPitching(input.pitchers);
    const rank = input.rank || rankFor(input.refs && input.refs.rank, season);
    const bat = battingTable(batTotals, season, ix);
    const pit = pitchingTable(pitTotals, season, ix);
    [bat, pit].forEach(function (tbl) {
      tbl.rows.forEach(function (r) { r.g = rank[r.team] ? rank[r.team].g : null; });
      const gs = tbl.rows.map(r => r.g).filter(v => v !== null);
      tbl.league.g = gs.length ? gs.reduce((a, b) => a + b, 0) / gs.length : null;
    });
    const names = Object.keys(rank);
    const unmatched = names.length
      ? names.filter(t => !batTotals[t]).concat(Object.keys(batTotals).filter(t => !rank[t]))
      : [];
    return { season, ix, bat, pit, rank, batTotals, pitTotals, unmatched };
  }

  // /stats/team_range 칸 → 내부 키입니다. 응답에 없는 칸(RBI·ER 등)은 넣지
  // 않습니다. 그래야 그 지표가 0 이 아니라 null 이 됩니다.
  const RANGE_BAT = {
    g: 'G', pa: 'PA', ab: 'AB', r: 'R', h: 'H', d2: '2B', d3: '3B', hr: 'HR',
    bb: 'BB', hbp: 'HBP', so: 'SO', sh: 'SH', sf: 'SF', tb: 'TB',
  };
  const RANGE_PIT = { g: 'G', outs: 'IP_outs', h: 'H', r: 'R', bb: 'BB', so: 'SO', hr: 'HR' };

  function rangeTotals(list, map) {
    const out = {};
    for (const x of list || []) {
      if (!x || !x.team) continue;
      const a = { team: x.team };
      for (const k in map) a[k] = num(x[map[k]]);
      out[x.team] = a;
    }
    return out;
  }

  /** 기간별 타격 표입니다. 리그 기준값은 같은 기간 리그 합입니다. */
  function rangeBattingTable(resp, season, ix) {
    return battingTable(rangeTotals(resp && resp.batting, RANGE_BAT), season, ix, Object.keys(RANGE_BAT));
  }

  /** 기간별 투구 표입니다. 피안타율은 응답의 AB_against 로 셉니다. */
  function rangePitchingTable(resp, season, ix) {
    const list = (resp && resp.pitching) || [];
    const tbl = pitchingTable(rangeTotals(list, RANGE_PIT), season, ix, Object.keys(RANGE_PIT));
    const by = {};
    let H = 0, AB = 0;
    for (const x of list) {
      by[x.team] = x;
      H += num(x.H);
      AB += num(x.AB_against);
    }
    tbl.rows.forEach(function (r) {
      const x = by[r.team];
      r.oavg = x ? div(num(x.H), num(x.AB_against)) : null;
    });
    tbl.league.oavg = div(H, AB);
    return tbl;
  }


  // ===== 선수 표 =====

  /** 선수 한 명의 공식 기록을 합계와 같은 모양으로 읽습니다. */
  function pick(r, map) {
    const a = {};
    for (const k in map) a[k] = num(r[map[k]]);
    return a;
  }

  /** 값이 없거나 숫자가 아니면 null 입니다. num 과 달리 0 으로 바꾸지 않습니다. */
  function numOrNull(v) {
    if (v === null || v === undefined || v === '') return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  // 선수 상황 기록입니다. 성분이 없어 다시 셀 수 없으므로 공식 값 그대로 씁니다.
  const PLAYER_BAT_RAW = {
    risp: 'runners_in_scoring_position', ph: 'pinch_hit_batting_average',
    xr: 'extended_runs', gpa: 'gross_production_average', ppa: 'p_pa',
  };

  /**
   * 그 시즌 모든 선수에서 값이 0 이거나 없는 칸은 기록이 없는 칸입니다(옛 시즌
   * API 는 없는 기록을 null 이 아니라 0 으로 채웁니다). 그런 칸을 행과 리그 행에서
   * null 로 바꿉니다. 표시용 칸만 바꾸고 지표 계산은 이미 끝난 뒤입니다.
   * 반환값은 비운 칸 목록입니다.
   */
  function blankUnrecorded(rows, league, keys) {
    const blanked = [];
    if (!rows.length) return blanked;
    for (const k of keys) {
      if (!rows.every(r => r[k] === null || r[k] === undefined || r[k] === 0)) continue;
      for (const r of rows) r[k] = null;
      if (league && k in league) league[k] = null;
      blanked.push(k);
    }
    return blanked;
  }

  /**
   * 선수 타격 표입니다. 리그 기준값은 팀 표와 같게, 팀이 있는 선수 전체의
   * 합으로 셉니다. 행은 선수 한 명씩이고 id·name·team·pos·g 를 붙입니다.
   *
   * 리그 평균 행은 비율과 지수만 둡니다. 선수마다 출장이 달라 누적 숫자의
   * 평균은 뜻이 없어 비웁니다(화면 '-'). wRAA 는 리그 평균 선수가 0 이라
   * 0 으로 둡니다.
   */
  function playerBatting(batters, season, ix) {
    const list = (batters || []).filter(p => p && p.player_team);
    const parts = list.map(p => pick(p, BAT_SUM));
    const c = battingCtx(sumObjects(parts, BAT_KEYS), season, ix);
    const rows = list.map(function (p, i) {
      const row = battingRow(parts[i], p.player_team, season, ix, c);
      row.id = p.player_id;
      row.name = p.player_name;
      row.team = p.player_team;
      row.pos = p.position || '';
      row.g = num(p.games);
      for (const k in PLAYER_BAT_RAW) row[k] = numOrNull(p[PLAYER_BAT_RAW[k]]);
      return row;
    });
    const league = Object.assign({ name: '리그 평균', team: '', isLeague: true }, c.lgR);
    league.single = null;
    league.woba = c.lgWoba;
    league.wraa = c.lgWoba === null ? null : 0;
    league.wrcp = rows.some(r => r.wrcp !== null) ? 100 : null;
    league.opsp = rows.some(r => r.opsp !== null) ? 100 : null;
    blankUnrecorded(rows, league, ['risp', 'ph', 'gw', 'multi', 'xr', 'gpa', 'ppa', 'ibb']);
    return { rows: rows, league: league, ctx: battingCtxOut(c) };
  }

  /** 선수 투구 표입니다. 리그 기준값(리그 ERA·FIP 상수)은 팀 표와 같습니다. */
  function playerPitching(pitchers, season, ix) {
    const list = (pitchers || []).filter(p => p && p.player_team);
    const parts = list.map(p => Object.assign(pick(p, PIT_SUM), { outs: ipOuts(p.innings_pitched) }));
    const c = pitchingCtx(sumObjects(parts, PIT_KEYS));
    const rows = list.map(function (p, i) {
      const row = pitchingRow(parts[i], p.player_team, season, ix, c);
      row.id = p.player_id;
      row.name = p.player_name;
      row.team = p.player_team;
      row.g = num(p.games);
      return row;
    });
    const league = Object.assign({ name: '리그 평균', team: '', isLeague: true }, c.lgR);
    league.fip = c.cfip !== null ? c.lgR.era : null;
    league.ef = league.fip !== null ? 0 : null;
    league.erap = rows.some(r => r.erap !== null) ? 100 : null;
    league.fipp = rows.some(r => r.fipp !== null) ? 100 : null;
    // P/IP 는 투구 수(np)로 만든 칸이라 np 가 비면 0 이 되어 같이 비워집니다.
    blankUnrecorded(rows, league, ['gs', 'hld', 'bs', 'wp', 'np', 'pip', 'qs', 'ibb']);
    return { rows: rows, league: league, ctx: { lgEra: c.lgR.era, cfip: c.cfip } };
  }

  /**
   * 파이썬 round 와 같습니다(.5 는 짝수 쪽). 서버 src/routes/leaders.js 의
   * pyRound 와 같은 식이라 규정타석이 서버와 같게 나옵니다.
   */
  function pyRound(x) {
    const f = Math.floor(x);
    if (x - f === 0.5) return f % 2 === 0 ? f : f + 1;
    return Math.round(x);
  }

  /**
   * 그 팀 선수의 규정 기준 { pa, outs, from } 입니다. 모르면 null 입니다.
   *   규정타석 = 팀 경기 수 × 3.1(파이썬식 반올림), 규정이닝 = 팀 경기 수
   * 팀 경기 수는 rank(rankFor·rankFromStandings 결과)에서 읽습니다. 그 팀이
   * 없으면 reg(/stats/regulation 의 그 시즌 한 줄 {team_games, qual_pa,
   * qual_ip})를 씁니다.
   */
  function qualFor(team, rank, reg) {
    const k = rank && rank[team];
    if (k && k.g > 0) return { pa: pyRound(3.1 * k.g), outs: k.g * 3, from: 'rank' };
    if (reg && num(reg.team_games) > 0) {
      return { pa: num(reg.qual_pa), outs: num(reg.qual_ip) * 3, from: 'regulation' };
    }
    return null;
  }

  const api = {
    num, div, clean, ipOuts, BAT_SUM, BAT_KEYS, sumBy, sumBatting, battingRates,
    indexRefs, pfHalf, wobaOf, sumObjects, battingTable,
    PIT_SUM, PIT_KEYS, sumPitching, pitchingRates, fipCore, pitchingTable,
    rankFor, rankFromStandings, pythag, gameSplits, recordTable, recordFromGames, recordMismatches, seasonView,
    RANGE_BAT, RANGE_PIT, rangeTotals, rangeBattingTable, rangePitchingTable,
    playerBatting, playerPitching, pyRound, qualFor,
  };
  TS.metrics = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
