/*
 * 선수 분석 투구 분포 카드(Savant Pitch Distribution 참고)를 만드는 순수 함수입니다.
 * 화면(DOM)에는 손대지 않습니다. 등고선 계산(d3)은 contours() 만 쓰고,
 * 그림(cardSvg)은 계산된 등고선 목록을 받아 그립니다.
 */
(function (root) {
  'use strict';
  const PA = root.PlayerAnalytics = root.PlayerAnalytics || {};

  const SIZE = 300;                 // viewBox 한 변
  const X_MAX = 3;                  // 좌우 ±3ft
  const Z_TOP = 5.5;                // 높이 -0.5~5.5ft (존이 가운데)
  const K = SIZE / (X_MAX * 2);     // ft → 좌표(50)
  const HALF_ZONE = 17 / 12 / 2;    // 0.708ft
  const MIN_CONTOUR_N = 15;
  const LEVELS = 5;

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
  function r1(n) { return Math.round(n * 10) / 10; }
  function colorOf(type) {
    const M = PA.movement;
    return M && M.colorOf ? M.colorOf(type) : '#3b82f6';
  }

  /** 구종별 묶음입니다. 위치(px·pz)가 숫자인 공만. 많이 던진 순, 같으면 이름 순. */
  function groups(pitches) {
    const by = {};
    (pitches || []).forEach(function (p) {
      if (num(p.px) === null || num(p.pz) === null) return;
      const t = p.pitch_type;
      if (t === null || t === undefined || t === '') return;
      (by[t] = by[t] || []).push(p);
    });
    const total = Object.keys(by).reduce(function (s, t) { return s + by[t].length; }, 0);
    return Object.keys(by).map(function (t) {
      return { type: t, color: colorOf(t), n: by[t].length, pct: total ? by[t].length / total * 100 : 0, pitches: by[t] };
    }).sort(function (a, b) { return b.n - a.n || (a.type < b.type ? -1 : a.type > b.type ? 1 : 0); });
  }

  /** 스트라이크 존 위·아래(ft)입니다. sz_top·sz_bot 평균, 없으면 3.5/1.5. */
  function zone(pitches) {
    function avg(key, dflt) {
      let s = 0, c = 0;
      (pitches || []).forEach(function (p) { const v = num(p[key]); if (v !== null) { s += v; c++; } });
      return c ? s / c : dflt;
    }
    return { top: avg('sz_top', 3.5), bot: avg('sz_bot', 1.5) };
  }

  /** 피트(px, pz) → viewBox 좌표입니다. view 'pitcher' 면 좌우를 뒤집습니다. */
  function toXY(px, pz, view) {
    const x = (view === 'pitcher' ? -px : px) * K + SIZE / 2;
    const y = (Z_TOP - pz) * K;
    return [x, y];
  }
  /** 보이는 범위 밖 공은 가장자리(3px 안쪽)에 붙여 둡니다. 빼지 않습니다. */
  function clampXY(xy) {
    const m = 3;
    return [Math.min(SIZE - m, Math.max(m, xy[0])), Math.min(SIZE - m, Math.max(m, xy[1]))];
  }
  function scale() { return { size: SIZE, k: K }; }

  function titleHtml(g) {
    return '<div class="pa-ars-title">' + esc(g.type) + '<span>' + comma(g.n) + '구 (' + r1(g.pct).toFixed(1) + '%)</span></div>';
  }

  function ringsPath(coordinates) {
    let d = '';
    (coordinates || []).forEach(function (poly) {
      poly.forEach(function (ring) {
        ring.forEach(function (pt, i) { d += (i ? 'L' : 'M') + r1(pt[0]) + ' ' + r1(pt[1]); });
        d += 'Z';
      });
    });
    return d;
  }

  /** 홈플레이트(납작한 오각형)입니다. 좌표는 viewBox. */
  function plateD() {
    const cx = SIZE / 2, w = HALF_ZONE * K, y0 = SIZE - 44, y1 = y0 + 9, y2 = y0 + 20;
    return 'M' + r1(cx - w) + ' ' + y0 + 'L' + r1(cx + w) + ' ' + y0 + 'L' + r1(cx + w) + ' ' + y1 +
      'L' + cx + ' ' + y2 + 'L' + r1(cx - w) + ' ' + y1 + 'Z';
  }

  /**
   * 카드 그림입니다. mode 'point' 면 점, 아니면 contours({value, coordinates} 목록, 좌표는 viewBox)로 등고선.
   * 등고선이 없으면(공이 적거나 d3 없음) 점으로 그립니다.
   */
  function cardSvg(g, z, mode, view, contours) {
    const zt = toXY(0, z.top, view)[1], zb = toXY(0, z.bot, view)[1];
    const zx = SIZE / 2 - HALF_ZONE * K, zw = HALF_ZONE * 2 * K;
    let s = '<svg class="pa-ars-svg" viewBox="0 0 ' + SIZE + ' ' + SIZE + '" role="img" aria-label="' + esc(g.type) + ' 투구 위치 분포">';
    s += '<path class="pa-ars-plate" d="' + plateD() + '"/>';
    s += '<rect class="pa-ars-zone" x="' + r1(zx) + '" y="' + r1(zt) + '" width="' + r1(zw) + '" height="' + r1(zb - zt) + '"/>';
    const useContour = mode !== 'point' && contours && contours.length;
    if (useContour) {
      const n = contours.length;
      contours.forEach(function (c, i) {
        const op = 0.12 + 0.68 * (i + 1) / n;
        s += '<path class="pa-ars-contour" d="' + ringsPath(c.coordinates) + '" fill="' + g.color + '" fill-opacity="' + op.toFixed(2) + '"/>';
      });
    } else {
      (g.pitches || []).forEach(function (p) {
        const px = num(p.px), pz = num(p.pz);
        if (px === null || pz === null) return;
        const raw = toXY(px, pz, view), xy = clampXY(raw);
        const edge = xy[0] !== raw[0] || xy[1] !== raw[1];
        s += '<circle class="pa-ars-pt" cx="' + r1(xy[0]) + '" cy="' + r1(xy[1]) + '" r="3" fill="' + g.color + '"' + (edge ? ' class="pa-ars-pt pa-ars-pt--edge" stroke="currentColor"' : '') + '/>';
      });
    }
    return s + '</svg>';
  }

  /** d3.contourDensity 로 등고선을 계산합니다(d3 없거나 공이 적으면 null → 점). */
  function contours(g, view, d3) {
    if (!d3 || !d3.contourDensity || g.n < MIN_CONTOUR_N) return null;
    const data = g.pitches.map(function (p) { return clampXY(toXY(num(p.px), num(p.pz), view)); });
    const out = d3.contourDensity().x(function (d) { return d[0]; }).y(function (d) { return d[1]; })
      .size([SIZE, SIZE]).bandwidth(9).thresholds(LEVELS + 1)(data);
    return out.length > LEVELS ? out.slice(out.length - LEVELS) : out;
  }

  const api = { groups, zone, toXY, scale, cardSvg, titleHtml, contours, MIN_CONTOUR_N };
  PA.arsenal = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
