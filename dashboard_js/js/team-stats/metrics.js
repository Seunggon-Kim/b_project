/*
 * 팀 통계 계산입니다. 화면(DOM)에는 손대지 않습니다.
 *
 * 브라우저에서는 window.TeamStats.metrics 로, Node 검증 스크립트에서는
 * require 로 씁니다. 식의 근거는 docs/superpowers/specs/
 * 2026-10-03-team-stats-fangraphs-design.md 3장입니다.
 *
 * 원칙: 선수 비율을 평균 내지 않습니다. 팀 합계(성분)에서 다시 셉니다.
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

  const api = {
    num, div, clean, ipOuts, BAT_SUM, BAT_KEYS, sumBy, sumBatting, battingRates,
  };
  TS.metrics = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
