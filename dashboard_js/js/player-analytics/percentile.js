/*
 * 선수 분석 페이지 Standard·Advanced 표의 백분위 색을 정하는 순수 함수입니다.
 * 화면(DOM)에는 손대지 않습니다.
 *
 * 우열이 분명한 비율 지표만 다룹니다. 그해 30이닝(90아웃) 이상 투수와 견줍니다.
 * 합계·비율은 공용 TeamStats.metrics 를 호출할 때 읽어 씁니다(불러오는 순서는 뒤면 됩니다).
 */
(function (root) {
  'use strict';
  const PA = root.PlayerAnalytics = root.PlayerAnalytics || {};
  const MIN_OUTS = 90;

  // 표 머리글 → 값 키와 우열 방향. BABIP 은 운 영향이 커서 뺍니다.
  const METRICS = {
    'ERA': { key: 'era', better: 'low' },
    'K/9': { key: 'k9', better: 'high' },
    'BB/9': { key: 'bb9', better: 'low' },
    'K/BB': { key: 'kbb', better: 'high' },
    'HR/9': { key: 'hr9', better: 'low' },
    'K%': { key: 'kpct', better: 'high' },
    'BB%': { key: 'bbpct', better: 'low' },
    'K-BB%': { key: 'kbbpct', better: 'high' },
    'AVG': { key: 'oavg', better: 'low' },
    'OBP': { key: 'obp', better: 'low' },
    'SLG': { key: 'slg', better: 'low' },
    'WHIP': { key: 'whip', better: 'low' },
  };

  function numOrNull(v) {
    if (v === null || v === undefined || v === '') return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  /** 행 하나의 지표 값입니다. { [머리글]: number|null, outs } */
  function rowValues(row) {
    const M = root.TeamStats.metrics;
    const flat = Object.assign({}, row, { player_team: '_' });
    const t = M.sumPitching([flat])._;
    const rates = M.pitchingRates(t);
    const src = Object.assign({}, rates, {
      obp: numOrNull(row.on_base_percentage),
      slg: numOrNull(row.slugging_percentage),
    });
    const out = { outs: t.outs };
    Object.keys(METRICS).forEach(function (h) {
      out[h] = numOrNull(src[METRICS[h].key]);
    });
    return out;
  }

  /** 90아웃 이상 행들의 지표별 오름차순 값 목록입니다. */
  function pool(rows, minOuts) {
    const min = minOuts === undefined ? MIN_OUTS : minOuts;
    const res = {};
    Object.keys(METRICS).forEach(function (h) { res[h] = []; });
    (rows || []).forEach(function (r) {
      const v = rowValues(r);
      if (!(v.outs >= min)) return;
      Object.keys(METRICS).forEach(function (h) {
        if (v[h] !== null) res[h].push(v[h]);
      });
    });
    Object.keys(res).forEach(function (h) { res[h].sort(function (a, b) { return a - b; }); });
    return res;
  }

  /** 0~100. 높을수록 좋음(better='high')이면 값보다 작은 비율, 'low' 면 값보다 큰 비율. 같은 값은 절반. */
  function percentile(value, sorted, better) {
    if (value === null || value === undefined || !sorted || !sorted.length) return null;
    let lt = 0, eq = 0, gt = 0;
    for (let i = 0; i < sorted.length; i++) {
      if (sorted[i] < value) lt++; else if (sorted[i] > value) gt++; else eq++;
    }
    const n = sorted.length;
    // 부동소수 오차(89.99999…)로 경계가 어긋나지 않게 소수 6자리로 맞춥니다.
    return Math.round(((better === 'low' ? gt : lt) + eq / 2) / n * 100 * 1e6) / 1e6;
  }

  /** 칸 제목 글자입니다. 올림이라 '상위 5%' 는 진한 단계(≥95)와만 맞습니다. */
  function label(pct) {
    return pct >= 50 ? '상위 ' + Math.max(1, Math.ceil(100 - pct)) + '%'
      : '하위 ' + Math.max(1, Math.ceil(pct)) + '%';
  }

  function tier(pct) {
    if (pct === null || pct === undefined || !Number.isFinite(pct)) return '';
    if (pct >= 95) return 'top2';
    if (pct >= 90) return 'top1';
    if (pct <= 5) return 'bot2';
    if (pct <= 10) return 'bot1';
    return '';
  }

  const api = { METRICS, MIN_OUTS, rowValues, pool, percentile, tier, label };
  PA.percentile = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
