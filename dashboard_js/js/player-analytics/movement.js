/*
 * 선수 분석 무브먼트 카드(Savant Movement Profile 참고)를 만드는 순수 함수입니다.
 * 화면(DOM)에는 손대지 않습니다. 설계:
 * docs/superpowers/specs/2026-10-04-player-analytics-movement-card-design.md
 *
 * 응답 pfx_x·pfx_z 는 인치입니다. 화면은 cm(× 2.54), 포수 시점입니다.
 * 아래쪽 기존 Movement Profile 카드와 같은 단위·방향·색입니다.
 */
(function (root) {
  'use strict';
  const PA = root.PlayerAnalytics = root.PlayerAnalytics || {};

  // 기존 카드(player-analytics.html renderMovementProfile)의 색표와 같습니다.
  const COLORS = {
    '너클볼': '#3C44CD', '스위퍼': '#DDB33A', '슬러브': '#93AFD4',
    '싱커': '#FE9D00', '투심': '#FE9D00', '직구': '#D22D49',
    '체인지업': '#1DBE3A', '커브': '#00D1ED', '커터': '#933F2C',
    '포크': '#3BACAC', '스플리터': '#3BACAC', '슬라이더': '#EEE716',
  };
  const FALLBACK = '#3b82f6';
  const IN2CM = 2.54;
  const C = 200;           // 그림 중심(px)
  const PX_PER_CM = 3;     // 60cm 가 반지름 180px
  const RINGS = [15, 30, 45, 60];
  const FIRST_SEASON = 2016;

  function colorOf(type) {
    return Object.prototype.hasOwnProperty.call(COLORS, type) ? COLORS[type] : FALLBACK;
  }

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

  /** 시즌별 전체 투구 수입니다. pitcher_seasons 의 number_of_pitchers 합. 값 없는 시즌은 뺍니다. */
  function totalsFor(player) {
    const out = {};
    ((player && player.pitcher_seasons) || []).forEach(function (s) {
      const y = Number(s.season);
      const n = s.number_of_pitchers;
      if (!Number.isFinite(y) || n === null || n === undefined || n === '' || !Number.isFinite(Number(n))) return;
      out[y] = (out[y] || 0) + Number(n);
    });
    return out;
  }

  function comma(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }

  /** 무브먼트 값이 있는 공만 고릅니다. */
  function valid(pitches) {
    return (pitches || []).filter(function (p) {
      return p && p.pitch_type && num(p.pfx_x) !== null && num(p.pfx_z) !== null;
    });
  }

  /** 구종별 요약입니다. 많이 던진 순, 같으면 구종 이름 순입니다. */
  function summarize(pitches) {
    const vs = valid(pitches);
    const by = {};
    vs.forEach(function (p) {
      const g = by[p.pitch_type] || (by[p.pitch_type] = { type: p.pitch_type, n: 0, sx: 0, sz: 0, sv: 0, nv: 0 });
      g.n++;
      g.sx += num(p.pfx_x) * IN2CM;
      g.sz += num(p.pfx_z) * IN2CM;
      const v = num(p.speed);
      if (v !== null && v > 0) { g.sv += v; g.nv++; }
    });
    return Object.keys(by).map(function (k) {
      const g = by[k];
      return {
        type: g.type, color: colorOf(g.type), n: g.n, pct: g.n * 100 / vs.length,
        x: g.sx / g.n, z: g.sz / g.n, speed: g.nv ? g.sv / g.nv : null,
      };
    }).sort(function (a, b) {
      return b.n - a.n || (a.type < b.type ? -1 : a.type > b.type ? 1 : 0);
    });
  }

  /** 연도 고르기 목록입니다. 1군 투수 기록 시즌 중 2016 이상(그 앞은 추적 데이터 없음), 최신순. */
  function seasonsFor(player) {
    const out = [];
    ((player && player.pitcher_seasons) || []).forEach(function (s) {
      const y = Number(s.season);
      if (Number.isFinite(y) && y >= FIRST_SEASON && out.indexOf(y) === -1) out.push(y);
    });
    return out.sort(function (a, b) { return b - a; });
  }

  function f1(v) { return v.toFixed(1); }
  function px(cmX) { return f1(C + cmX * PX_PER_CM); }
  function py(cmZ) { return f1(C - cmZ * PX_PER_CM); }

  /** 원형 무브먼트 그림입니다. 유효한 공이 없으면 빈 글자입니다. */
  function svgHtml(pitches, summary) {
    const vs = valid(pitches);
    if (!vs.length) return '';
    const R = RINGS[RINGS.length - 1] * PX_PER_CM;
    let s = '<svg class="pa-mv-svg" viewBox="0 0 400 400" role="img" aria-label="구종별 무브먼트">'
      + '<defs><clipPath id="pa-mv-clip"><circle cx="200" cy="200" r="' + R + '"/></clipPath></defs>'
      + '<circle class="pa-mv-bg" cx="200" cy="200" r="' + R + '"/>';
    RINGS.forEach(function (cm) {
      s += '<circle class="pa-mv-ring' + (cm % 30 ? ' pa-mv-ring--minor' : '') + '" cx="200" cy="200" r="' + cm * PX_PER_CM + '"/>';
    });
    s += '<line class="pa-mv-axis" x1="' + (C - R) + '" y1="200" x2="' + (C + R) + '" y2="200"/>'
      + '<line class="pa-mv-axis" x1="200" y1="' + (C - R) + '" x2="200" y2="' + (C + R) + '"/>';
    [30, 60].forEach(function (cm) {
      s += '<text class="pa-mv-tick" x="204" y="' + (C - cm * PX_PER_CM + 12) + '">' + cm + '</text>';
    });
    s += '<g clip-path="url(#pa-mv-clip)">';
    vs.forEach(function (p) {
      s += '<circle class="pa-mv-pt" cx="' + px(num(p.pfx_x) * IN2CM) + '" cy="' + py(num(p.pfx_z) * IN2CM)
        + '" r="2.5" fill="' + colorOf(p.pitch_type) + '"/>';
    });
    (summary || []).forEach(function (g) {
      s += '<circle class="pa-mv-avg" cx="' + px(g.x) + '" cy="' + py(g.z) + '" r="9" fill="' + g.color + '">'
        + '<title>' + esc(g.type) + ' ' + f1(g.pct) + '% · 수직 ' + f1(g.z) + 'cm · 수평 ' + f1(g.x) + 'cm</title></circle>';
    });
    return s + '</g></svg>';
  }

  /** 구종 표입니다. 빈 배열이면 빈 글자입니다. */
  function legendHtml(summary) {
    if (!summary || !summary.length) return '';
    return '<table class="pa-mv-legend"><thead><tr><th>구종</th><th>비율</th><th>구속(km/h)</th><th>수직(cm)</th><th>수평(cm)</th></tr></thead><tbody>'
      + summary.map(function (g) {
        return '<tr><td><span class="pa-mv-dot" style="background:' + g.color + '"></span>' + esc(g.type) + '</td>'
          + '<td>' + f1(g.pct) + '%</td><td>' + (g.speed === null ? '-' : f1(g.speed)) + '</td>'
          + '<td>' + f1(g.z) + '</td><td>' + f1(g.x) + '</td></tr>';
      }).join('')
      + '</tbody></table>';
  }

  /** 카드 본문입니다. 그림 + 안내 줄 + 표. 데이터가 없으면 안내 문구입니다. */
  function bodyHtml(pitches, total) {
    const vs = valid(pitches);
    if (!vs.length) return '<p class="pa-mv-empty">이 시즌은 투구 추적 데이터가 없습니다.</p>';
    const summary = summarize(vs);
    return svgHtml(vs, summary)
      + '<p class="pa-mv-note">포수 시점 · 수평 +는 1루 쪽 · 수직 +는 위</p>'
      + '<p class="pa-mv-note">공 ' + comma(vs.length) + '개 추적'
      + (total > 0 ? ' (정규시즌 ' + comma(total) + '구 대비 ' + Math.min(100, Math.round(vs.length * 100 / total)) + '%)' : '') + '</p>'
      + (total > 0 ? '<p class="pa-mv-note pa-mv-note--sub">추적 공에는 시범경기·포스트시즌이 섞일 수 있습니다.</p>' : '')
      + legendHtml(summary);
  }

  const api = { COLORS, colorOf, summarize, seasonsFor, totalsFor, svgHtml, legendHtml, bodyHtml };
  PA.movement = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
