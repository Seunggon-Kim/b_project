/*
 * 선수 분석 "시즌별 구종 추이" 카드(Savant Pitch % by Season 참고)를 만드는 순수 함수입니다.
 * /players/{id}/pitch_trend 응답(시즌 × 구종 × 타자 손 × 카운트 합계)을 받아
 * 고른 타자 손·카운트로 합치고, 고른 지표의 시즌별 선 그래프(SVG 글자)를 만듭니다.
 * 데이터에 없는 지표(회전수·타구 속도·xBA 등)는 두지 않습니다(evan). 화면(DOM)에는 손대지 않습니다.
 */
(function (root) {
  'use strict';
  const PA = root.PlayerAnalytics = root.PlayerAnalytics || {};

  const IN2CM = 2.54;
  const SUMS = ['n', 'pa', 'ab', 'h', 'b1', 'b2', 'b3', 'hr', 'bbe', 'bb', 'so',
    'spd_sum', 'spd_n', 'pfx_x_sum', 'pfx_z_sum', 'pfx_n', 'px_sum', 'pz_sum', 'loc_n',
    // 선구(Plate Discipline) 개수입니다. 고의 볼·피치클락 위반은 API 가 뺍니다.
    'pd_n', 'sw', 'wh', 'ct', 'cs', 'z_n', 'o_n', 'z_sw', 'o_sw', 'z_ct', 'o_ct', 'edge_n', 'fp_n', 'fp_str'];

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
  function nameOf(t) { const M = PA.movement; return M && M.pitchName ? M.pitchName(t) : t; }
  function colorOf(t) { const M = PA.movement; return M && M.colorOf ? M.colorOf(t) : '#3b82f6'; }
  function ratio(a, b) { return b > 0 ? a / b : null; }

  // 지표 목록입니다. 묶음(group)은 고르기 칸의 optgroup 이고, tip 은 마우스를 올리면 나오는 설명입니다.
  // v(합계, 그 시즌 전체 공 수) → 값(없으면 null), note(합계) → 툴팁의 바탕 수.
  /** 선구 지표 하나(비율 %). part(합계) → [분자, 분모]. 분모가 0 이면 점을 두지 않습니다. */
  function pdm(key, label, tip, part, unit) {
    return { key: key, group: '선구 (Plate Discipline)', label: label, tip: tip, pct: true,
      v: function (s) { const p = part(s); return p[1] > 0 ? 100 * p[0] / p[1] : null; },
      note: function (s) { const p = part(s); return comma(p[0]) + ' / ' + comma(p[1]) + unit; } };
  }

  const METRICS = [
    { key: 'pct', group: '', label: '구종 비율 (%)', tip: '그 시즌(고른 타자 손·카운트 안) 전체 공 가운데 이 구종의 비율입니다.',
      v: function (s, total) { return total > 0 && s.n > 0 ? 100 * s.n / total : null; },
      note: function (s, total) { return comma(s.n) + '구 / 그 시즌 ' + comma(total) + '구'; } },
    { key: 'n', group: '', label: '투구 수', tip: '이 구종으로 던진 공 수입니다.',
      v: function (s) { return s.n > 0 ? s.n : null; }, note: function () { return ''; } },
    { key: 'h', group: '기본', label: '안타', tip: '이 구종으로 끝난 타석에서 맞은 안타 수입니다(1루타·2루타·3루타·홈런).',
      v: function (s) { return s.pa > 0 ? s.h : null; }, note: function (s) { return comma(s.pa) + '타석'; } },
    { key: 'b1', group: '기본', label: '1루타', tip: '이 구종으로 끝난 타석에서 맞은 1루타 수입니다(내야안타·번트 안타 포함).',
      v: function (s) { return s.pa > 0 ? s.b1 : null; }, note: function (s) { return comma(s.pa) + '타석'; } },
    { key: 'b2', group: '기본', label: '2루타', tip: '이 구종으로 끝난 타석에서 맞은 2루타 수입니다.',
      v: function (s) { return s.pa > 0 ? s.b2 : null; }, note: function (s) { return comma(s.pa) + '타석'; } },
    { key: 'b3', group: '기본', label: '3루타', tip: '이 구종으로 끝난 타석에서 맞은 3루타 수입니다.',
      v: function (s) { return s.pa > 0 ? s.b3 : null; }, note: function (s) { return comma(s.pa) + '타석'; } },
    { key: 'hr', group: '기본', label: '홈런', tip: '이 구종으로 끝난 타석에서 맞은 홈런 수입니다.',
      v: function (s) { return s.pa > 0 ? s.hr : null; }, note: function (s) { return comma(s.pa) + '타석'; } },
    { key: 'bbe', group: '기본', label: '타구 수', tip: '이 구종으로 끝난 타석 가운데 공이 맞아 나간 수입니다(삼진·볼넷·몸에 맞는 볼 제외).',
      v: function (s) { return s.pa > 0 ? s.bbe : null; }, note: function (s) { return comma(s.pa) + '타석'; } },
    { key: 'bb_pct', group: '기본', label: '볼넷% (%)', tip: '볼넷 ÷ 이 구종으로 끝난 타석 × 100 입니다. 고의4구 포함, 몸에 맞는 볼 제외.',
      v: function (s) { const r = ratio(s.bb, s.pa); return r === null ? null : 100 * r; }, note: function (s) { return comma(s.pa) + '타석'; } },
    { key: 'k_pct', group: '기본', label: '삼진% (%)', tip: '삼진 ÷ 이 구종으로 끝난 타석 × 100 입니다. 낫아웃 출루 포함.',
      v: function (s) { const r = ratio(s.so, s.pa); return r === null ? null : 100 * r; }, note: function (s) { return comma(s.pa) + '타석'; } },
    { key: 'pfx_x', group: '무브먼트', label: '수평 무브먼트 (cm)', tip: '중력 영향을 뺀 좌우 움직임 평균입니다. 포수 시점, + 는 1루 쪽입니다.',
      v: function (s) { const r = ratio(s.pfx_x_sum, s.pfx_n); return r === null ? null : r * IN2CM; }, note: function (s) { return comma(s.pfx_n) + '구'; } },
    { key: 'pfx_z', group: '무브먼트', label: '수직 무브먼트 (Induced, cm)', tip: '중력 영향을 뺀 위아래 움직임 평균입니다. + 는 솟는 쪽입니다.',
      v: function (s) { const r = ratio(s.pfx_z_sum, s.pfx_n); return r === null ? null : r * IN2CM; }, note: function (s) { return comma(s.pfx_n) + '구'; } },
    { key: 'ba', group: '결과', label: '타율', tip: '안타 ÷ 타수 입니다(이 구종으로 끝난 타석).',
      v: function (s) { return ratio(s.h, s.ab); }, note: function (s) { return comma(s.ab) + '타수'; } },
    { key: 'slg', group: '결과', label: '장타율', tip: '루타 ÷ 타수 입니다(1루타 1, 2루타 2, 3루타 3, 홈런 4).',
      v: function (s) { return ratio(s.b1 + 2 * s.b2 + 3 * s.b3 + 4 * s.hr, s.ab); }, note: function (s) { return comma(s.ab) + '타수'; } },
    { key: 'spd', group: '투구', label: '평균 구속 (km/h)', tip: '이 구종의 평균 구속입니다.',
      v: function (s) { return ratio(s.spd_sum, s.spd_n); }, note: function (s) { return comma(s.spd_n) + '구'; } },
    // 선구(Plate Discipline): FanGraphs·Savant 정의. 존은 투구 분포와 같은 20인치 존(공 반지름 포함)입니다.
    pdm('swing', '스윙% (Swing%)', '스윙 ÷ 공 × 100 입니다. 번트 시도도 스윙으로 셉니다(Savant).', function (s) { return [s.sw, s.pd_n]; }, '구'),
    pdm('whiff', '헛스윙/스윙 (Whiff%)', '헛스윙 ÷ 스윙 × 100 입니다(Savant Swing & Miss %).', function (s) { return [s.wh, s.sw]; }, '스윙'),
    pdm('swstr', '헛스윙% (SwStr%)', '헛스윙 ÷ 공 × 100 입니다(FanGraphs).', function (s) { return [s.wh, s.pd_n]; }, '구'),
    pdm('contact', '컨택% (Contact%)', '컨택(파울·타격) ÷ 스윙 × 100 입니다.', function (s) { return [s.ct, s.sw]; }, '스윙'),
    pdm('zone', '존% (Zone%)', '스트라이크 존 안 공 ÷ 위치가 있는 공 × 100 입니다. 존 폭은 공 반지름을 더한 20인치입니다.', function (s) { return [s.z_n, s.z_n + s.o_n]; }, '구'),
    pdm('edge', '엣지% (Edge%)', '존 끝 근처(Shadow, 존 끝 100% 기준 67~133%) 공 ÷ 위치가 있는 공 × 100 입니다(Savant).', function (s) { return [s.edge_n, s.z_n + s.o_n]; }, '구'),
    pdm('z_swing', '존 스윙% (Z-Swing%)', '존 안 공에 스윙 ÷ 존 안 공 × 100 입니다.', function (s) { return [s.z_sw, s.z_n]; }, '구'),
    pdm('o_swing', '체이스% (O-Swing%)', '존 밖 공에 스윙 ÷ 존 밖 공 × 100 입니다(Savant Chase %).', function (s) { return [s.o_sw, s.o_n]; }, '구'),
    pdm('z_contact', '존 컨택% (Z-Contact%)', '존 안 컨택 ÷ 존 안 스윙 × 100 입니다.', function (s) { return [s.z_ct, s.z_sw]; }, '스윙'),
    pdm('o_contact', '존 밖 컨택% (O-Contact%)', '존 밖 컨택 ÷ 존 밖 스윙 × 100 입니다.', function (s) { return [s.o_ct, s.o_sw]; }, '스윙'),
    pdm('f_strike', '초구 스트라이크% (F-Strike%)', '0-0 에서 볼이 아닌 공(루킹·헛스윙·파울·타격) ÷ 0-0 공 × 100 입니다.', function (s) { return [s.fp_str, s.fp_n]; }, '초구'),
    pdm('cstr', '루킹 스트라이크% (CStr%)', '루킹 스트라이크 ÷ 공 × 100 입니다.', function (s) { return [s.cs, s.pd_n]; }, '구'),
    pdm('csw', 'CSW%', '(루킹 스트라이크 + 헛스윙) ÷ 공 × 100 입니다.', function (s) { return [s.cs + s.wh, s.pd_n]; }, '구'),
    { key: 'rv', group: '구종 가치', label: '구종 가치 (점)', tip: '이 구종으로 던진 공의 득점 가치 합입니다. 실점을 막으면 + 입니다. 카운트를 고르면 쓸 수 없습니다.',
      v: function (s) { return s.rv_n > 0 ? s.rv : null; }, note: function (s) { return comma(s.rv_n) + '구'; } },
  ];
  function metric(key) { return METRICS.find(function (m) { return m.key === key; }) || METRICS[0]; }

  /** 이 지표를 지금 고른 카운트로 쓸 수 있는지(구종 가치는 카운트별 값이 없음). */
  function metricOk(key, cnt) { return !(key === 'rv' && cnt); }

  function emptySums() {
    const s = { rv: 0, rv_n: 0 };
    SUMS.forEach(function (k) { s[k] = 0; });
    return s;
  }

  /**
   * 응답을 고른 타자 손(''·'L'·'R')과 카운트(''·'ahead'·'behind'·'even'·'full')로 합칩니다.
   * 구종 이름은 화면 이름으로 바꿔 합칩니다(투심+싱커 → 싱커 등).
   */
  function aggregate(data, side, cnt) {
    const bySeason = {};
    const seasonOf = function (y) {
      if (!bySeason[y]) bySeason[y] = { total: 0, types: {} };
      return bySeason[y];
    };
    ((data && data.rows) || []).forEach(function (r) {
      const y = num(r.season);
      if (y === null) return;
      if (side && r.bat_side !== side) return;
      if (cnt && r.cnt !== cnt) return;
      const S = seasonOf(y), t = nameOf(r.pitch_type);
      const s = S.types[t] || (S.types[t] = emptySums());
      SUMS.forEach(function (k) { s[k] += num(r[k]) || 0; });
      S.total += num(r.n) || 0;
    });
    if (!cnt) {
      ((data && data.values) || []).forEach(function (r) {
        const y = num(r.season);
        if (y === null || !bySeason[y]) return;
        const t = nameOf(r.pitch_type), s = bySeason[y].types[t];
        if (!s) return;
        const nl = num(r.n_l) || 0, nr = num(r.n_r) || 0, rl = num(r.rv_l) || 0, rr = num(r.rv_r) || 0;
        if (side !== 'R') { s.rv += rl; s.rv_n += nl; }
        if (side !== 'L') { s.rv += rr; s.rv_n += nr; }
      });
    }
    const seasons = Object.keys(bySeason).map(Number).filter(function (y) { return bySeason[y].total > 0; })
      .sort(function (a, b) { return a - b; });
    return { seasons: seasons, bySeason: bySeason };
  }

  /** 고른 지표의 구종별 선입니다. 많이 던진 구종 먼저. 값이 없는 시즌은 점을 두지 않습니다. */
  function series(agg, key) {
    const m = metric(key), tot = {};
    agg.seasons.forEach(function (y) {
      const types = agg.bySeason[y].types;
      Object.keys(types).forEach(function (t) { tot[t] = (tot[t] || 0) + types[t].n; });
    });
    return Object.keys(tot).filter(function (t) { return tot[t] > 0; })
      .sort(function (a, b) { return tot[b] - tot[a] || (a < b ? -1 : 1); })
      .map(function (t) {
        const points = [];
        agg.seasons.forEach(function (y) {
          const S = agg.bySeason[y], s = S.types[t];
          if (!s || !(s.n > 0)) return;
          const v = m.v(s, S.total);
          if (v === null || !Number.isFinite(v)) return;
          points.push({ season: y, v: v, note: m.note(s, S.total) });
        });
        return { type: t, color: colorOf(t), points: points };
      });
  }

  function isPct(key) { return key === 'pct' || key === 'bb_pct' || key === 'k_pct' || !!metric(key).pct; }

  function fmt(key, v) {
    if (v === null || v === undefined) return '-';
    if (isPct(key)) return v.toFixed(1) + '%';
    if (key === 'ba' || key === 'slg') { const s = v.toFixed(3); return s.charAt(0) === '0' ? s.slice(1) : s; }
    if (key === 'rv') return (v > 0 ? '+' : '') + v.toFixed(1);
    if (key === 'n' || key === 'h' || key === 'b1' || key === 'b2' || key === 'b3' || key === 'hr' || key === 'bbe') return comma(Math.round(v));
    return v.toFixed(1);
  }
  function tickFmt(key, t) {
    const r = Math.round(t * 1000) / 1000;
    if (isPct(key)) return r + '%';
    if (key === 'ba' || key === 'slg') return fmt(key, r);
    if (key === 'rv') return (r > 0 ? '+' : '') + r;
    return comma(r);
  }

  // 0 부터 그리는 지표(비율·개수)입니다. 나머지(무브먼트·구속·가치)는 값 범위에 맞춥니다.
  const FROM_ZERO = { pct: 1, n: 1, h: 1, b1: 1, b2: 1, b3: 1, hr: 1, bbe: 1, bb_pct: 1, k_pct: 1, ba: 1, slg: 1 };
  function niceStep(span) {
    const raw = span / 4, p = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
  }
  function ticks(key, vals) {
    let lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
    if (FROM_ZERO[key] || metric(key).pct) lo = Math.min(0, lo);
    if (key === 'rv') { lo = Math.min(0, lo); hi = Math.max(0, hi); }
    if (hi === lo) { hi += 1; if (!FROM_ZERO[key] && !metric(key).pct) lo -= 1; }
    const step = niceStep(hi - lo), a = Math.floor(lo / step) * step, b = Math.ceil(hi / step) * step, out = [];
    for (let t = a; t <= b + step / 2; t += step) out.push(Math.round(t / step) * step);
    return out;
  }

  const ML = 52, MR = 16, MT = 14, MB = 34;

  /**
   * 선 그래프 SVG 글자입니다. 점에는 <title>(시즌 · 구종 · 값 (바탕 수))을 둡니다.
   * size({w, h})는 viewBox 크기입니다. 화면이 실제 폭을 넘기면 글자가 늘거나 줄지 않습니다(기본 760×300).
   */
  function chartSvg(sr, seasons, key, size) {
    const W = Math.max(320, Math.round((size && size.w) || 760)), H = Math.round((size && size.h) || 300);
    const vals = [];
    sr.forEach(function (s) { s.points.forEach(function (p) { vals.push(p.v); }); });
    let out = '<svg class="pa-tr-svg" viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="시즌별 ' + esc(metric(key).label) + '">';
    if (!vals.length || !seasons.length) return out + '</svg>';
    const tk = ticks(key, vals), y0 = tk[0], y1 = tk[tk.length - 1];
    const pw = W - ML - MR, ph = H - MT - MB;
    const X = function (y) {
      const i = seasons.indexOf(y);
      return seasons.length === 1 ? ML + pw / 2 : ML + pw * i / (seasons.length - 1);
    };
    const Y = function (v) { return MT + ph * (1 - (v - y0) / (y1 - y0)); };
    const f = function (n) { return Math.round(n * 10) / 10; };
    tk.forEach(function (t) {
      out += '<line class="pa-tr-grid' + (t === 0 ? ' pa-tr-zero' : '') + '" x1="' + ML + '" x2="' + (W - MR) + '" y1="' + f(Y(t)) + '" y2="' + f(Y(t)) + '"/>'
        + '<text class="pa-tr-tick" x="' + (ML - 8) + '" y="' + f(Y(t) + 4) + '" text-anchor="end">' + esc(tickFmt(key, t)) + '</text>';
    });
    // 시즌 사이가 좁으면(휴대폰) 2016 → ’16 으로 줄입니다.
    const short = seasons.length > 1 && pw / (seasons.length - 1) < 44;
    seasons.forEach(function (y) {
      out += '<text class="pa-tr-tick" x="' + f(X(y)) + '" y="' + (H - 10) + '" text-anchor="middle">' + (short ? '’' + String(y).slice(2) : y) + '</text>';
    });
    sr.forEach(function (s) {
      // 이웃한 시즌끼리만 잇습니다(중간에 안 던진 시즌이 있으면 끊음).
      let d = '', prev = null;
      s.points.forEach(function (p) {
        const i = seasons.indexOf(p.season);
        const xy = f(X(p.season)) + ' ' + f(Y(p.v));
        if (prev !== null && i === prev + 1) { d += 'L' + xy; } else { d += 'M' + xy; }
        prev = i;
      });
      if (/L/.test(d)) out += '<path class="pa-tr-line" d="' + d + '" stroke="' + s.color + '"/>';
    });
    sr.forEach(function (s) {
      s.points.forEach(function (p) {
        out += '<circle class="pa-tr-pt" cx="' + f(X(p.season)) + '" cy="' + f(Y(p.v)) + '" r="4" fill="' + s.color + '">'
          + '<title>' + p.season + ' · ' + esc(s.type) + ' · ' + esc(fmt(key, p.v)) + (p.note ? ' (' + esc(p.note) + ')' : '') + '</title></circle>';
      });
    });
    return out + '</svg>';
  }

  function legendHtml(sr) {
    return '<div class="pa-tr-legend">' + sr.map(function (s) {
      return '<span class="pa-tr-key"><i style="background:' + s.color + '"></i>' + esc(s.type) + '</span>';
    }).join('') + '</div>';
  }

  /** 지표 고르기 칸의 option 글자입니다(묶음은 optgroup). */
  function metricOptionsHtml() {
    let html = '', group = null;
    METRICS.forEach(function (m) {
      if (m.group !== group) {
        if (group) html += '</optgroup>';
        group = m.group;
        if (group) html += '<optgroup label="' + esc(group) + '">';
      }
      html += '<option value="' + m.key + '" title="' + esc(m.tip) + '">' + esc(m.label) + '</option>';
    });
    return html + (group ? '</optgroup>' : '');
  }

  const api = { METRICS, metric, metricOk, aggregate, series, fmt, chartSvg, legendHtml, metricOptionsHtml };
  PA.trend = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
