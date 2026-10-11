/*
 * 선수 분석 Pitch Distribution 카드(Savant 참고, 구속별 투구 빈도)를 만드는 순수 함수입니다.
 * 화면(DOM)에는 손대지 않습니다. 공은 투구 분포 카드와 같은 /players/{id}/arsenal 응답입니다.
 *
 * Savant 와 같은 방식입니다(player-update index.js, serverVals.pitchDistribution).
 * - 구속을 1 단위(여기선 km/h)로 묶습니다.
 * - 비율은 그 시즌 모든 공 대비입니다. 그래서 구종 선의 합이 그 구종 구사율이고, All 의 합이 100% 입니다.
 * - 구종 선은 값 있는 칸만 잇고 앞뒤에 0 한 칸을 붙입니다. All 은 빈 칸을 0 으로 채웁니다.
 * - 선은 B-spline(d3 curveBasis)이고, All Pitches 는 빨간 점선입니다.
 */
(function (root) {
  'use strict';
  const PA = root.PlayerAnalytics = root.PlayerAnalytics || {};

  const ALL_COLOR = '#f00';          // Savant All Pitches 색
  const ML = 52, MR = 14, MT = 28, MB = 46;

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
  function comma(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
  function f(n) { return Math.round(n * 10) / 10; }
  function nameOf(raw) {
    const M = PA.movement;
    return M && M.pitchName ? M.pitchName(raw) : raw;
  }
  function colorOf(type) {
    const M = PA.movement;
    return M && M.colorOf ? M.colorOf(type) : '#3b82f6';
  }

  /**
   * 구속별 묶음입니다. 구속이 0 보다 큰 숫자인 공만 셉니다(소수는 반올림).
   * { total, lo, hi, types: [{ type, color, n, points: [{ kmh, n, freq }] }], all: { points } }
   * 구종은 많이 던진 순, 같으면 이름 순입니다. lo·hi 는 앞뒤 0 칸까지 넣은 범위입니다.
   */
  function bins(pitches) {
    const by = Object.create(null), all = Object.create(null);
    let total = 0;
    (pitches || []).forEach(function (p) {
      const v = num(p && p.speed);
      if (v === null || v <= 0) return;
      const k = Math.round(v);
      const t = nameOf(p.pitch_type);
      if (!by[t]) by[t] = Object.create(null);
      by[t][k] = (by[t][k] || 0) + 1;
      all[k] = (all[k] || 0) + 1;
      total++;
    });
    if (!total) return { total: 0, lo: null, hi: null, types: [], all: { points: [] } };
    const pt = function (k, n) { return { kmh: k, n: n, freq: n / total }; };
    const types = Object.keys(by).map(function (t) {
      const ks = Object.keys(by[t]).map(Number).sort(function (a, b) { return a - b; });
      const points = [pt(ks[0] - 1, 0)].concat(ks.map(function (k) { return pt(k, by[t][k]); }), [pt(ks[ks.length - 1] + 1, 0)]);
      const n = ks.reduce(function (a, k) { return a + by[t][k]; }, 0);
      return { type: t, color: colorOf(t), n: n, points: points };
    }).sort(function (a, b) { return b.n - a.n || (a.type < b.type ? -1 : a.type > b.type ? 1 : 0); });
    const ks = Object.keys(all).map(Number);
    const lo = Math.min.apply(null, ks) - 1, hi = Math.max.apply(null, ks) + 1;
    const points = [];
    for (let k = lo; k <= hi; k++) points.push(pt(k, all[k] || 0));
    return { total: total, lo: lo, hi: hi, types: types, all: { points: points } };
  }

  /** d3-shape curveBasis 와 같은 SVG 경로입니다(점 [[x, y], ...], 좌표는 0.1 단위). */
  function basisPath(pts) {
    if (!pts.length) return '';
    let d = 'M' + f(pts[0][0]) + ' ' + f(pts[0][1]);
    if (pts.length === 1) return d;
    if (pts.length === 2) return d + 'L' + f(pts[1][0]) + ' ' + f(pts[1][1]);
    let x0 = pts[0][0], y0 = pts[0][1], x1 = pts[1][0], y1 = pts[1][1];
    d += 'L' + f((5 * x0 + x1) / 6) + ' ' + f((5 * y0 + y1) / 6);
    const bez = function (x, y) {
      d += 'C' + f((2 * x0 + x1) / 3) + ' ' + f((2 * y0 + y1) / 3) + ' ' + f((x0 + 2 * x1) / 3) + ' ' + f((y0 + 2 * y1) / 3)
        + ' ' + f((x0 + 4 * x1 + x) / 6) + ' ' + f((y0 + 4 * y1 + y) / 6);
      x0 = x1; y0 = y1; x1 = x; y1 = y;
    };
    for (let i = 2; i < pts.length; i++) bez(pts[i][0], pts[i][1]);
    bez(x1, y1);
    return d + 'L' + f(x1) + ' ' + f(y1);
  }

  /** 세로축 눈금(%)입니다. 5칸 이하가 되는 가장 작은 간격, 맨 위는 그 간격의 배수. */
  function yTicks(maxPct) {
    const steps = [0.5, 1, 2, 5, 10, 20, 25, 50];
    let step = steps[steps.length - 1];
    for (let i = 0; i < steps.length; i++) { if (Math.ceil(maxPct / steps[i]) <= 5) { step = steps[i]; break; } }
    const top = Math.max(step, Math.ceil(maxPct / step) * step);
    const out = [];
    for (let v = 0; v <= top + 1e-9; v += step) out.push(Math.round(v * 10) / 10);
    return out;
  }
  function pctFmt(v) { return (v * 100).toFixed(1) + '%'; }

  /** 그래프 SVG 입니다. size = { w, h } (카드 실제 폭). 구속 칸마다 투명 칸에 툴팁(data-tip)을 둡니다. */
  function chartSvg(data, size) {
    const W = Math.max(320, Math.round((size && size.w) || 760)), H = Math.round((size && size.h) || 340);
    let out = '<svg class="pa-tr-svg pa-pdist-svg" viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="구속별 투구 비율">';
    if (!data || !data.total) return out + '</svg>';
    const pw = W - ML - MR, ph = H - MT - MB;
    const lo = data.lo, hi = data.hi, per = pw / (hi - lo);
    const X = function (k) { return ML + (k - lo) * per; };
    let maxPct = 0;
    data.all.points.forEach(function (q) { maxPct = Math.max(maxPct, q.freq * 100); });
    data.types.forEach(function (t) { t.points.forEach(function (q) { maxPct = Math.max(maxPct, q.freq * 100); }); });
    const yt = yTicks(maxPct), top = yt[yt.length - 1];
    const Y = function (pct) { return MT + ph * (1 - pct / top); };
    yt.forEach(function (t) {
      out += '<line class="pa-tr-grid' + (t === 0 ? ' pa-tr-zero' : '') + '" x1="' + ML + '" x2="' + (W - MR) + '" y1="' + f(Y(t)) + '" y2="' + f(Y(t)) + '"/>'
        + '<text class="pa-tr-tick" x="' + (ML - 8) + '" y="' + f(Y(t) + 4) + '" text-anchor="end">' + t + '%</text>';
    });
    // 가로 눈금: 5·10·20 km/h 가운데 글자가 겹치지 않는(44px 이상) 가장 작은 간격
    let step = 20;
    [5, 10, 20].some(function (s) { if (s * per >= 44) { step = s; return true; } return false; });
    for (let k = Math.ceil(lo / step) * step; k <= hi; k += step) {
      out += '<line class="pa-tr-grid" x1="' + f(X(k)) + '" x2="' + f(X(k)) + '" y1="' + MT + '" y2="' + f(Y(0)) + '"/>'
        + '<text class="pa-tr-tick" x="' + f(X(k)) + '" y="' + f(Y(0) + 18) + '" text-anchor="middle">' + k + '</text>';
    }
    out += '<text class="pa-tr-tick pa-pdist-axis" x="' + f(ML + pw / 2) + '" y="' + (H - 4) + '" text-anchor="middle">구속 (km/h)</text>'
      + '<text class="pa-tr-tick pa-pdist-axis" x="' + (ML - 8) + '" y="12" text-anchor="end">공 비율</text>';
    const path = function (points) {
      return basisPath(points.map(function (q) { return [X(q.kmh), Y(q.freq * 100)]; }));
    };
    data.types.forEach(function (t, i) {
      out += '<path class="pa-pdist-line" data-k="' + i + '" d="' + path(t.points) + '" stroke="' + t.color + '"/>';
    });
    out += '<path class="pa-pdist-line pa-pdist-all" data-k="all" d="' + path(data.all.points) + '" stroke="' + ALL_COLOR + '"/>';
    // 구속 칸 툴팁: 첫 줄 구속, 둘째 줄 모든 공, 셋째 줄부터 그 구속을 던진 구종(많은 순)
    data.all.points.forEach(function (q) {
      if (!q.n) return;
      const rows = [];
      data.types.forEach(function (t) {
        const hit = t.points.find(function (r) { return r.kmh === q.kmh && r.n > 0; });
        if (hit) rows.push({ type: t.type, n: hit.n, freq: hit.freq });
      });
      rows.sort(function (a, b) { return b.n - a.n; });
      const tip = q.kmh + ' km/h\n모든 공의 ' + pctFmt(q.freq) + ' (' + comma(q.n) + '구)'
        + rows.map(function (r) { return '\n' + r.type + ' ' + pctFmt(r.freq) + ' (' + comma(r.n) + '구)'; }).join('');
      out += '<rect class="pa-pdist-hit" x="' + f(X(q.kmh) - per / 2) + '" y="' + MT + '" width="' + f(per) + '" height="' + f(ph) + '" data-tip="' + esc(tip) + '"/>';
    });
    return out + '</svg>';
  }

  /** 범례입니다. data-k 가 선(path)의 data-k 와 짝이라, 페이지가 올린 범례의 선만 남깁니다. */
  function legendHtml(data) {
    const keys = (data && data.types || []).map(function (t, i) {
      return '<span class="pa-pdist-key" data-k="' + i + '" tabindex="0"><i style="background:' + t.color + '"></i>' + esc(t.type) + '</span>';
    });
    keys.push('<span class="pa-pdist-key" data-k="all" tabindex="0"><i class="pa-pdist-dash"></i>All Pitches</span>');
    return '<div class="pa-tr-legend pa-pdist-legend">' + keys.join('') + '</div>';
  }

  const api = { bins: bins, basisPath: basisPath, yTicks: yTicks, chartSvg: chartSvg, legendHtml: legendHtml };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  PA.speed = api;
})(typeof window !== 'undefined' ? window : globalThis);
