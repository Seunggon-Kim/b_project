/*
 * 선수 분석 타자 Percentile Rankings 카드(Savant MLB Percentile Rankings 참고)를 만드는 순수 함수입니다.
 * 화면(DOM)에는 손대지 않습니다.
 *
 * 그 시즌 /stats/batters 행(모든 타자)과, 있으면 /stats/batter_values 행(Batting Run Value·선구 개수)을 받아
 * 지표마다 "안정 표본 이상인 타자끼리" 백분위를 냅니다. 기준은 KBO 안정화 글(yagongso, 2009~2017,
 * 무작위 두 표본 R²≥0.5)입니다. 기준에 못 미치면 값은 보여 주되 Savant 처럼 빗금(표본 부족)으로 둡니다.
 * 타구(타구 속도·발사각·xStat)·주루·수비는 데이터가 없어 두지 않고, AVG 는 580타수가 필요해 뺍니다(evan).
 */
(function (root) {
  'use strict';
  const PA = root.PlayerAnalytics = root.PlayerAnalytics || {};

  function num(v) {
    if (v === null || v === undefined || v === '') return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function r3(v) { const t = v.toFixed(3); return t.charAt(0) === '0' ? t.slice(1) : t.replace('-0.', '-.'); }
  function pct1(v) { return v.toFixed(1) + '%'; }

  // 분모 단위 → 글자입니다(기준·지금 표본 글에 씁니다).
  const UNITS = { pa: '타석', ab: '타수', o_n: '개(존 밖 공)', sw: '번(스윙)' };

  // [key, 묶음, 이름, 분모, 기준, 좋은 쪽, 글자, 설명]. 기준이 null 이면 아직 정하지 않아 숨깁니다.
  // wRC+·Batting Run Value 는 wOBA 와 같은 420타석입니다(셋 다 타석당 득점 기여, 화면 세션 결정).
  // Chase%·Whiff% 기준은 API 세션이 같은 방법으로 우리 데이터에서 재면 넣습니다.
  const METRICS = [
    ['brv', 'Value', 'Batting Run Value', 'pa', 420, 'high', function (v) { return (v > 0 ? '+' : '') + v.toFixed(1); },
      '공마다 볼카운트·주자·아웃별 기대 득점이 얼마나 바뀌었는지 더한 값입니다. 득점을 만들면 + 입니다(투수 구종 가치와 같은 계산, 부호 반대).'],
    ['woba', 'Batting', 'wOBA', 'pa', 420, 'high', r3, '가중 출루율입니다. 계산식: (wBB·BB + wHBP·HBP + w1B·1B + w2B·2B + w3B·3B + wHR·HR) ÷ (AB + BB + SF + HBP)'],
    ['wrc', 'Batting', 'wRC+', 'pa', 420, 'high', function (v) { return String(Math.round(v)); }, '리그 평균을 100 으로 둔 득점 생산력입니다. 구장 영향을 고쳤습니다.'],
    ['obp', 'Batting', 'OBP', 'pa', 420, 'high', r3, '출루율입니다. 계산식: (H + BB + HBP) ÷ (AB + BB + HBP + SF)'],
    ['slg', 'Batting', 'SLG', 'ab', 300, 'high', r3, '장타율입니다. 계산식: 루타 ÷ AB'],
    ['iso', 'Batting', 'ISO', 'ab', 240, 'high', r3, '순장타율입니다. 계산식: SLG − AVG'],
    ['bb', 'Plate Discipline', 'BB%', 'pa', 400, 'high', pct1, '볼넷 ÷ 타석 × 100 입니다(고의4구 포함).'],
    ['k', 'Plate Discipline', 'K%', 'pa', 200, 'low', pct1, '삼진 ÷ 타석 × 100 입니다. 낮을수록 좋습니다.'],
    ['chase', 'Plate Discipline', 'Chase%', 'o_n', null, 'low', pct1, '존 밖 공에 스윙 ÷ 존 밖 공 × 100 입니다(O-Swing%). 낮을수록 좋습니다.'],
    ['whiff', 'Plate Discipline', 'Whiff%', 'sw', null, 'low', pct1, '헛스윙 ÷ 스윙 × 100 입니다. 낮을수록 좋습니다.'],
  ].map(function (a) { return { key: a[0], group: a[1], label: a[2], unit: a[3], min: a[4], better: a[5], fmt: a[6], tip: a[7] }; });
  const GROUPS = ['Value', 'Batting', 'Plate Discipline'];

  /** 행 하나(/stats/batters)와 확장 값(/stats/batter_values, 없으면 null)의 지표 값과 분모입니다. */
  function values(row, extra) {
    const pa = num(row.plate_appearance) || 0, ab = num(row.at_bat) || 0;
    const avg = num(row.batting_average), slg = num(row.slugging_percentage);
    const x = extra || {};
    const o_n = num(x.o_n), sw = num(x.sw);
    return {
      n: { pa: pa, ab: ab, o_n: o_n || 0, sw: sw || 0 },
      brv: num(x.rv),
      woba: num(row.woba),
      wrc: num(row.wrc_plus),
      obp: num(row.on_base_percentage),
      slg: slg,
      iso: slg !== null && avg !== null ? slg - avg : null,
      bb: pa > 0 ? 100 * (num(row.base_on_balls) || 0) / pa : null,
      k: pa > 0 ? 100 * (num(row.strikeout) || 0) / pa : null,
      chase: o_n > 0 && num(x.o_sw) !== null ? 100 * num(x.o_sw) / o_n : null,
      whiff: sw > 0 && num(x.wh) !== null ? 100 * num(x.wh) / sw : null,
    };
  }

  /**
   * 진행 중인 시즌의 진도입니다(evan: Savant 처럼 시즌 중엔 진도에 맞춰 기준을 낮춤).
   * 팀 평균 치른 경기 ÷ 정규 경기 수, 0~1. 값이 없으면 1(낮추지 않음).
   */
  function paceScale(teamGames, fullGames) {
    const g = num(teamGames), f = num(fullGames);
    if (!(g > 0) || !(f > 0)) return 1;
    return Math.min(1, g / f);
  }

  /**
   * 한 타자의 지표별 결과입니다. rows = 그 시즌 /stats/batters 행 모두, extra = { player_id: batter_values 행 } 또는 null.
   * scale(0~1, 없으면 1)은 진행 중 시즌 진도이고, 기준 = 올림(안정 표본 × scale) 입니다.
   * [{ key, label, group, value, qualified, pct, pos, n, min, fullMin, unit, have, better }]. 기준이 없거나 값이 없는 지표는 뺍니다.
   */
  function rank(rows, extra, playerId, scale) {
    const sc = scale > 0 && scale < 1 ? scale : 1;
    const all = (rows || []).map(function (r) {
      return { id: String(r.player_id), v: values(r, extra ? extra[String(r.player_id)] : null) };
    });
    const me = all.find(function (a) { return a.id === String(playerId); });
    if (!me) return [];
    const P = PA.percentile;
    return METRICS.filter(function (m) { return m.min !== null && me.v[m.key] !== null; }).map(function (m) {
      const min = Math.max(1, Math.ceil(m.min * sc));
      const pool = all.filter(function (a) { return a.v.n[m.unit] >= min && a.v[m.key] !== null; })
        .map(function (a) { return a.v[m.key]; }).sort(function (a, b) { return a - b; });
      const value = me.v[m.key], have = me.v.n[m.unit], qualified = have >= min;
      const better = pool.filter(function (x) { return m.better === 'low' ? x < value : x > value; }).length;
      return {
        key: m.key, label: m.label, group: m.group, value: value, qualified: qualified,
        pct: qualified ? P.percentile(value, pool, m.better) : null,
        pos: qualified ? better + 1 : null, n: pool.length, min: min, fullMin: m.min, unit: m.unit, have: have, better: m.better,
      };
    });
  }

  /** Savant 막대 색입니다. 0 파랑 · 50 회색 · 100 빨강 사이를 곧게 섞습니다. */
  const C0 = [54, 97, 173], C50 = [180, 207, 209], C100 = [216, 33, 41];
  function color(p) {
    const t = Math.max(0, Math.min(100, p));
    const a = t <= 50 ? C0 : C50, b = t <= 50 ? C50 : C100, k = t <= 50 ? t / 50 : (t - 50) / 50;
    return 'rgb(' + [0, 1, 2].map(function (i) { return Math.round(a[i] + (b[i] - a[i]) * k); }).join(', ') + ')';
  }

  function metricOf(key) { return METRICS.find(function (m) { return m.key === key; }); }

  function rowHtml(r, season) {
    const m = metricOf(r.key), u = UNITS[r.unit], val = m.fmt(r.value);
    const lowered = r.fullMin && r.min < r.fullMin;
    if (!r.qualified) {
      const tip = m.label + '\n' + val + ' · 지금 ' + r.have + u + '\n' + r.min + u + ' 이상인 타자끼리 비교합니다(KBO 안정 표본'
        + (lowered ? ' ' + r.fullMin + u + ', 진행 중인 시즌이라 진도에 맞춰 낮춤' : '') + '). ' + m.tip;
      return '<div class="pa-bp-row pa-bp-nq" tabindex="0" data-tip="' + esc(tip) + '">'
        + '<span class="pa-bp-name">' + esc(m.label) + '</span>'
        + '<span class="pa-bp-bar"><span class="pa-bp-nqtext">표본 부족</span></span>'
        + '<span class="pa-bp-val">' + esc(val) + '</span></div>';
    }
    const shown = Math.max(1, Math.round(r.pct)), c = color(r.pct);
    const tip = m.label + '\n' + val + ' · ' + season + '년 ' + r.min + u + ' 이상 ' + r.n + '명 중 ' + r.pos + '위 ('
      + PA.percentile.label(r.pct) + ')'
      + (lowered ? '\n진행 중인 시즌이라 ' + r.fullMin + u + ' 기준을 진도에 맞춰 ' + r.min + u + '으로 낮췄습니다.' : '')
      + '\n' + m.tip;
    return '<div class="pa-bp-row" tabindex="0" data-tip="' + esc(tip) + '">'
      + '<span class="pa-bp-name">' + esc(m.label) + '</span>'
      + '<span class="pa-bp-bar"><span class="pa-bp-fill" style="width:' + shown + '%;background:' + c + '"></span>'
      + '<span class="pa-bp-dot" style="left:' + shown + '%;background:' + c + '">' + shown + '</span></span>'
      + '<span class="pa-bp-val">' + esc(val) + '</span></div>';
  }

  /**
   * 카드 본문입니다. 묶음(Value·Batting·Plate Discipline) 순, 값이 있는 지표만.
   * pace = { teamGames, fullGames } 이면(진행 중 시즌에 기준을 낮췄을 때) 위에 안내 한 줄을 둡니다.
   */
  function cardHtml(results, season, pace) {
    if (!results || !results.length) return '<p class="pa-bp-empty">이 시즌 기록이 없습니다.</p>';
    let h = '<div class="pa-bp">';
    if (pace && paceScale(pace.teamGames, pace.fullGames) < 1) {
      h += '<p class="pa-bp-note">진행 중인 시즌이라 기준을 진도(팀 평균 ' + Math.round(pace.teamGames) + '/' + pace.fullGames
        + '경기)에 맞춰 낮췄습니다. 시즌이 끝나면 KBO 안정 표본 기준으로 돌아갑니다.</p>';
    }
    h += '<div class="pa-bp-scale" aria-hidden="true"><span>나쁨</span><span>평균</span><span>좋음</span></div>';
    GROUPS.forEach(function (g) {
      const rs = results.filter(function (r) { return r.group === g; });
      if (!rs.length) return;
      h += '<div class="pa-bp-group">' + esc(g) + '</div>' + rs.map(function (r) { return rowHtml(r, season); }).join('');
    });
    return h + '</div>';
  }

  const api = { METRICS, UNITS, values, paceScale, rank, color, cardHtml };
  PA.batpct = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
