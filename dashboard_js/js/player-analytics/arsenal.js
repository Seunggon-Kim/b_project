/*
 * 선수 분석 투구 분포 카드(Savant Pitch Distribution 참고)를 만드는 순수 함수입니다.
 * 화면(DOM)에는 손대지 않습니다. 등고선 계산(d3)은 contours() 만 쓰고,
 * 그림(cardSvg)은 계산된 등고선 목록을 받아 그립니다.
 */
(function (root) {
  'use strict';
  const PA = root.PlayerAnalytics = root.PlayerAnalytics || {};

  const SIZE = 300;                 // viewBox 한 변
  const X_MAX = 4;                  // 좌우 ±4ft (밖으로 나가 끝에 붙는 공을 줄이려고 넓힘, evan)
  const Z_TOP = 6.5;                // 높이 -1.5~6.5ft (존이 가운데)
  const K = SIZE / (X_MAX * 2);     // ft → 좌표(37.5)
  const HALF_ZONE = 17 / 12 / 2;    // 0.708ft
  const MIN_CONTOUR_N = 15;
  // 등고선 단계: 바깥 줄부터 이 비율의 공을 감쌉니다(evan). 선수·구종마다 바깥 줄 의미가 같아집니다.
  const SHARES = [0.9, 0.7, 0.5, 0.3, 0.1];
  const CELL = 4;                   // 밀도 격자 한 칸(viewBox 단위)
  const SIGMA = 0.18 * K;           // 밀도 번짐 정도(약 0.18ft, 공 900구 이상일 때)
  const SIGMA_N = 900;              // 공이 이보다 적으면 (900/n)^(1/6) 배로 넓힘(실버만 규칙). 적은 공이 조각나지 않게

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
      if (p.pitch_type === null || p.pitch_type === undefined || p.pitch_type === '') return;
      const M = PA.movement;
      const t = M && M.pitchName ? M.pitchName(p.pitch_type) : p.pitch_type;
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
  function inRange(xy) { return xy[0] >= 0 && xy[0] <= SIZE && xy[1] >= 0 && xy[1] <= SIZE; }
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
    const cx = SIZE / 2, w = HALF_ZONE * K, y0 = (Z_TOP - 0.38) * K, y1 = y0 + 0.18 * K, y2 = y0 + 0.4 * K;  // 높이 약 0.4ft, 범위와 함께 줄어듦
    return 'M' + r1(cx - w) + ' ' + y0 + 'L' + r1(cx + w) + ' ' + y0 + 'L' + r1(cx + w) + ' ' + y1 +
      'L' + cx + ' ' + y2 + 'L' + r1(cx - w) + ' ' + y1 + 'Z';
  }

  /**
   * 카드 그림입니다. mode 'point' 면 점, 'both' 면 등고선 위에 모든 공, 그 밖은 contours({value, coordinates} 목록, 좌표는 viewBox)로 등고선.
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
    }
    (g.pitches || []).forEach(function (p) {
      const px = num(p.px), pz = num(p.pz);
      if (px === null || pz === null) return;
      const raw = toXY(px, pz, view);
      const out = !inRange(raw);
      if (useContour && !out && mode !== 'both') return;  // 등고선만이면 범위 밖 공만 표시, both 면 모든 공
      const xy = clampXY(raw);
      const small = mode === 'both' && !out;  // 등고선 위에 얹는 공은 작게(등고선이 보이게)
      s += '<circle class="pa-ars-pt' + (out ? ' pa-ars-pt--edge' : '') + (small ? ' pa-ars-pt--over' : '') + '" cx="' + r1(xy[0]) + '" cy="' + r1(xy[1]) + '" r="' + (small ? 1.6 : 3) + '" fill="' + g.color + '"/>';
    });
    return s + '</svg>';
  }

  /** 밀도 계산용 좌표입니다. 보이는 범위 안의 공만(가장자리에 붙인 공은 넣지 않습니다). */
  function densityData(g, view) {
    return g.pitches.map(function (p) { return toXY(num(p.px), num(p.pz), view); }).filter(inRange);
  }

  /** 공 위치를 격자에 세고 가우스로 번지게 한 밀도 격자입니다(가로·세로 따로 번짐). */
  function densityGrid(data) {
    const n = SIZE / CELL, raw = new Float64Array(n * n), tmp = new Float64Array(n * n), out = new Float64Array(n * n);
    const cl = function (v) { return Math.min(n - 1, Math.max(0, Math.floor(v / CELL))); };
    data.forEach(function (d) { raw[cl(d[1]) * n + cl(d[0])] += 1; });
    const sg = SIGMA * Math.max(1, Math.pow(SIGMA_N / Math.max(1, data.length), 1 / 6)) / CELL, r = Math.ceil(sg * 3), kern = [];
    for (let d = -r; d <= r; d++) kern.push(Math.exp(-d * d / (2 * sg * sg)));
    const blur = function (src, dst, horiz) {
      for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) {
        let v = 0;
        for (let d = -r; d <= r; d++) {
          const ii = horiz ? i + d : i, jj = horiz ? j : j + d;
          if (ii >= 0 && ii < n && jj >= 0 && jj < n) v += kern[d + r] * src[jj * n + ii];
        }
        dst[j * n + i] = v;
      }
    };
    blur(raw, tmp, true);
    blur(tmp, out, false);
    return { n: n, values: out };
  }
  /** 격자 밀도를 점 위치에서 읽습니다(칸 가운데 사이를 직선으로 이음, 등고선과 같은 방식). */
  function densityAt(grid, x, y) {
    const n = grid.n, v = grid.values;
    const fx = Math.min(n - 1, Math.max(0, x / CELL - 0.5)), fy = Math.min(n - 1, Math.max(0, y / CELL - 0.5));
    const i = Math.min(n - 2, Math.floor(fx)), j = Math.min(n - 2, Math.floor(fy)), tx = fx - i, ty = fy - j;
    const a = v[j * n + i], b = v[j * n + i + 1], c = v[(j + 1) * n + i], d = v[(j + 1) * n + i + 1];
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty;
  }

  /** 등고선을 계산합니다. 단계마다 SHARES 비율의 공을 감싸게 높이를 고릅니다(d3 없거나 범위 안 공이 적으면 null → 점). */
  function contours(g, view, d3) {
    if (!d3 || !d3.contours) return null;
    const data = densityData(g, view);
    if (data.length < MIN_CONTOUR_N) return null;
    const grid = densityGrid(data);
    const dens = data.map(function (d) { return densityAt(grid, d[0], d[1]); }).sort(function (a, b) { return a - b; });
    const ts = SHARES.map(function (p) { return dens[Math.min(dens.length - 1, Math.floor((1 - p) * dens.length))]; });
    const out = d3.contours().size([grid.n, grid.n]).thresholds(ts)(Array.from(grid.values));
    return out.map(function (c) {
      return { value: c.value, coordinates: c.coordinates.map(function (poly) {
        return poly.map(function (ring) { return ring.map(function (pt) { return [pt[0] * CELL, pt[1] * CELL]; }); });
      }) };
    });
  }

  // ---- 공 고르기·존 고르기(Savant 투구 분포 참고, evan) ----
  // 존 폭은 공 반지름을 더한 20인치(±10인치)입니다(Tango·Savant). 높이는 그 공의 sz_top·sz_bot.
  const ZONE_HW = 10 / 12;

  function zoneOf(p) {
    const px = num(p.px), pz = num(p.pz);
    if (px === null || pz === null) return null;
    const top = num(p.sz_top), bot = num(p.sz_bot);
    const t = top !== null && bot !== null && top > bot ? top : 3.5, b = top !== null && bot !== null && top > bot ? bot : 1.5;
    return { x: px, z: pz, top: t, bot: b };
  }

  /** Savant 게임데이 존(포수 시점): 1~9 는 존 안 3×3(1 = 왼쪽 위), 11~14 는 존 밖을 가운데 선으로 나눈 네 귀퉁이. */
  function gameZone(p) {
    const q = zoneOf(p);
    if (!q) return null;
    const h = q.top - q.bot, mid = (q.top + q.bot) / 2;
    if (Math.abs(q.x) <= ZONE_HW && q.z >= q.bot && q.z <= q.top) {
      const col = q.x < -ZONE_HW / 3 ? 0 : q.x <= ZONE_HW / 3 ? 1 : 2;
      const row = q.z > q.top - h / 3 ? 0 : q.z >= q.bot + h / 3 ? 1 : 2;
      return row * 3 + col + 1;
    }
    return (q.z > mid ? 11 : 13) + (q.x < 0 ? 0 : 1);
  }

  /** Tango·Savant 공격 존: 존 가운데 0%, 존 끝 100%. 하트 <67%, 쉐도우 <133%, 체이스 <200%, 그 밖 웨이스트. */
  function attackZone(p) {
    const q = zoneOf(p);
    if (!q) return null;
    const r = Math.max(Math.abs(q.x) / ZONE_HW, Math.abs(q.z - (q.top + q.bot) / 2) / ((q.top - q.bot) / 2));
    return r < 0.67 ? 'heart' : r < 1.33 ? 'shadow' : r < 2 ? 'chase' : 'waste';
  }

  /** 던지기 전 볼카운트 묶음(투수 기준, FanGraphs). 3-2(full)는 유리·불리·같음 어디에도 넣지 않습니다. */
  function countGroup(balls, strikes) {
    const b = num(balls), k = num(strikes);
    if (b === null || k === null) return null;
    if (b === 3 && k === 2) return 'full';
    return k > b ? 'ahead' : b > k ? 'behind' : 'even';
  }

  const PICKS = [
    ['', '모든 공', null],
    ['swing', '헛스윙', null],
    ['hit', '안타', 'is_hit'],
    ['rhb', '우타자 상대', 'bat_side'],
    ['lhb', '좌타자 상대', 'bat_side'],
    ['ahead', '유리한 카운트', 'balls'],
    ['behind', '불리한 카운트', 'balls'],
    ['even', '같은 카운트', 'balls'],
    ['ts', '2스트라이크', 'strikes'],
  ];
  /** 고를 수 있는 공 고르기 항목입니다. 응답에 그 값이 없으면(API 배포 전) 빼 둡니다. */
  function pickOptions(rows) {
    const has = function (k) { return (rows || []).some(function (p) { return p[k] !== undefined && p[k] !== null; }); };
    return PICKS.filter(function (o) { return !o[2] || has(o[2]); }).map(function (o) { return [o[0], o[1]]; });
  }
  function zoneOptions() {
    const o = [['', '모든 존']];
    [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14].forEach(function (z) { o.push([String(z), '존 ' + z]); });
    return o.concat([['iz', '존 안'], ['ooz', '존 밖'], ['heart', '하트'], ['shadow', '쉐도우'], ['chase', '체이스'], ['waste', '웨이스트']]);
  }

  function pickOk(p, pick) {
    switch (pick) {
      case 'swing': return p.pitch_result === '헛스윙' || p.pitch_result === '번트헛스윙';
      case 'hit': return Number(p.is_hit) === 1;
      case 'rhb': return p.bat_side === 'R';
      case 'lhb': return p.bat_side === 'L';
      case 'ahead': case 'behind': case 'even': return countGroup(p.balls, p.strikes) === pick;
      case 'ts': return num(p.strikes) === 2;
      default: return true;
    }
  }
  function zoneOk(p, zone) {
    if (!zone) return true;
    if (zone === 'heart' || zone === 'shadow' || zone === 'chase' || zone === 'waste') return attackZone(p) === zone;
    const z = gameZone(p);
    if (z === null) return false;
    if (zone === 'iz') return z <= 9;
    if (zone === 'ooz') return z >= 11;
    return z === Number(zone);
  }
  /** 공 고르기(pick)와 존 고르기(zone)를 함께 적용합니다. 빈 값은 거르지 않음. */
  function filterPitches(rows, pick, zone) {
    return (rows || []).filter(function (p) { return pickOk(p, pick) && zoneOk(p, zone); });
  }

  const api = { groups, zone, toXY, scale, cardSvg, titleHtml, contours, densityData, MIN_CONTOUR_N,
    gameZone, attackZone, countGroup, pickOptions, zoneOptions, filterPitches };
  PA.arsenal = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
