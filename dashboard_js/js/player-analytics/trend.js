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
    'pd_n', 'sw', 'wh', 'ct', 'cs', 'z_n', 'o_n', 'z_sw', 'o_sw', 'z_ct', 'o_ct', 'edge_n', 'fp_n', 'fp_str',
    // 구종별 시즌 표(wOBA)용입니다. API 가 아직 안 주면 0 입니다.
    'hbp', 'sf',
    // Meatball(Gameday Zone 5) 공 수와 그 공에 스윙한 수입니다(Plate Discipline 표).
    'mb_n', 'mb_sw'];

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
  /** wOBA 입니다(선수 통계 metrics.wobaOf 와 같은 식, BB 는 고의4구 포함). 가중치 w 가 없거나 분모가 0 이면 null. */
  function wobaValue(s, w) {
    const den = s.ab + s.bb + s.sf + s.hbp;
    if (!w || !(den > 0)) return null;
    const v = (num(w.fg_wBB) * s.bb + num(w.fg_wHBP) * s.hbp + num(w.fg_w1B) * s.b1
      + num(w.fg_w2B) * s.b2 + num(w.fg_w3B) * s.b3 + num(w.fg_wHR) * s.hr) / den;
    return Number.isFinite(v) ? v : null;
  }

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
    { key: 'woba', group: '결과', label: 'wOBA', needsW: true,
      tip: '가중 출루율입니다. 시즌 가중치는 선수 통계와 같습니다. 계산식: (wBB·BB + wHBP·HBP + w1B·1B + w2B·2B + w3B·3B + wHR·HR) ÷ (AB + BB + SF + HBP)',
      v: function (s, total, w) { return wobaValue(s, w); },
      note: function (s) { return comma(s.ab + s.bb + s.sf + s.hbp) + ' (AB + BB + SF + HBP)'; } },
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

  // 던지기 전 볼카운트 12가지입니다(볼 3 이상은 3, 스트라이크 2 이상은 2, API bc).
  const COUNTS = ['0-0', '0-1', '0-2', '1-0', '1-1', '1-2', '2-0', '2-1', '2-2', '3-0', '3-1', '3-2'];
  function isExact(cnt) { return /^[0-3]-[0-2]$/.test(cnt); }

  /**
   * 카운트 고르기 칸의 option 글자입니다. 응답에 카운트별 값(bc)이 있으면 묶음 3개 + 카운트 12개,
   * 없으면(API 배포 전) 묶음 4개(풀카운트 포함)입니다. 묶음은 투수 기준(FanGraphs).
   */
  function countOptionsHtml(data) {
    const hasBc = ((data && data.rows) || []).some(function (r) { return r.bc; });
    let h = '<option value="">모든 카운트</option><optgroup label="묶음">'
      + '<option value="ahead">유리한 카운트</option><option value="behind">불리한 카운트</option><option value="even">같은 카운트</option>';
    if (!hasBc) return h + '<option value="full">풀카운트 (3-2)</option></optgroup>';
    h += '</optgroup><optgroup label="카운트별">';
    COUNTS.forEach(function (c) { h += '<option value="' + c + '">' + c + '</option>'; });
    return h + '</optgroup>';
  }

  /** 이 지표를 지금 고른 카운트로 쓸 수 있는지(구종 가치는 카운트별 값이 없음). */
  function metricOk(key, cnt) { return !(key === 'rv' && cnt); }

  function emptySums() {
    const s = { rv: 0, rv_n: 0, n_r: 0, n_l: 0, ts_n: 0, ts_so: 0 };
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
      if (cnt && (isExact(cnt) ? r.bc !== cnt : r.cnt !== cnt)) return;
      const S = seasonOf(y), t = nameOf(r.pitch_type);
      const s = S.types[t] || (S.types[t] = emptySums());
      SUMS.forEach(function (k) { s[k] += num(r[k]) || 0; });
      const rn = num(r.n) || 0;
      S.total += rn;
      if (r.bat_side === 'R') s.n_r += rn; else if (r.bat_side === 'L') s.n_l += rn;
      // 2스트라이크(bc 끝이 -2) 공과 그 삼진: PutAway% 입니다(삼진은 늘 2스트라이크에서 나옴).
      if (r.bc && /-2$/.test(r.bc)) { s.ts_n += rn; s.ts_so += num(r.so) || 0; }
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
  function series(agg, key, weights) {
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
          const v = m.v(s, S.total, weights ? weights[y] : null);
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
    if (key === 'ba' || key === 'slg' || key === 'woba') { const s = v.toFixed(3); return s.charAt(0) === '0' ? s.slice(1) : s; }
    if (key === 'rv') return (v > 0 ? '+' : '') + v.toFixed(1);
    if (key === 'n' || key === 'h' || key === 'b1' || key === 'b2' || key === 'b3' || key === 'hr' || key === 'bbe') return comma(Math.round(v));
    return v.toFixed(1);
  }
  function tickFmt(key, t) {
    const r = Math.round(t * 1000) / 1000;
    if (isPct(key)) return r + '%';
    if (key === 'ba' || key === 'slg' || key === 'woba') return fmt(key, r);
    if (key === 'rv') return (r > 0 ? '+' : '') + r;
    return comma(r);
  }

  // 0 부터 그리는 지표(비율·개수)입니다. 나머지(무브먼트·구속·가치)는 값 범위에 맞춥니다.
  const FROM_ZERO = { pct: 1, n: 1, h: 1, b1: 1, b2: 1, b3: 1, hr: 1, bbe: 1, bb_pct: 1, k_pct: 1, ba: 1, slg: 1, woba: 1 };
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
   * 선 그래프 SVG 글자입니다. 점에는 data-tip(시즌 · 구종 · 값 (바탕 수))을 둡니다(공용 흰 바탕 툴팁 js/chart-tip.js).
   * size({w, h})는 viewBox 크기입니다. 화면이 실제 폭을 넘기면 글자가 늘거나 줄지 않습니다(기본 760×300).
   */
  function chartSvg(sr, seasons, key, size) {
    const W = Math.max(320, Math.round((size && size.w) || 760)), H = Math.round((size && size.h) || 300);
    const vals = [];
    sr.forEach(function (s) { s.points.forEach(function (p) { vals.push(p.v); }); });
    let out = '<svg class="pa-tr-svg" viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="시즌별 ' + esc(metric(key).label) + '">';
    if (!vals.length || !seasons.length) return out + '</svg>';
    // 가로축은 첫 시즌부터 마지막 시즌까지 모든 해입니다. 기록 없는 해는 점이 없고 선도 끊깁니다(Savant, evan).
    const lo = Math.min.apply(null, seasons), hi = Math.max.apply(null, seasons);
    seasons = [];
    for (let y = lo; y <= hi; y++) seasons.push(y);
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
        out += '<circle class="pa-tr-pt" cx="' + f(X(p.season)) + '" cy="' + f(Y(p.v)) + '" r="4" fill="' + s.color + '"'
          + ' data-tip="' + esc(s.type + ' · ' + p.season + '\n' + metric(key).label + ': ' + fmt(key, p.v) + (p.note ? '\n' + p.note : '')) + '"/>';
      });
    });
    return out + '</svg>';
  }

  function legendHtml(sr) {
    return '<div class="pa-tr-legend">' + sr.map(function (s) {
      return '<span class="pa-tr-key"><i style="background:' + s.color + '"></i>' + esc(s.type) + '</span>';
    }).join('') + '</div>';
  }

  // ---- 구종별 시즌 표(Savant detailedPitches 참고, evan) ----
  // 타구 속도 기반(xBA·xSLG·xwOBA·EV·LA)·회전수·익스텐션은 데이터에 없어 두지 않습니다(evan).
  // [머리글, 강조할 지표 key, 설명, 값(합계, 그 시즌 전체 공, 가중치) → 글자]
  function i0(v) { return comma(Math.round(v)); }
  function p1(a, b) { return b > 0 ? (100 * a / b).toFixed(1) : '-'; }
  function r3(a, b) { if (!(b > 0)) return '-'; const t = (a / b).toFixed(3); return t.charAt(0) === '0' ? t.slice(1) : t; }
  const TCOLS = [
    ['#', 'n', '#\n이 구종으로 던진 공 수입니다.', function (s) { return i0(s.n); }],
    ['# RHB', null, '# RHB\n우타자에게 던진 공 수입니다.', function (s) { return i0(s.n_r); }],
    ['# LHB', null, '# LHB\n좌타자에게 던진 공 수입니다.', function (s) { return i0(s.n_l); }],
    ['%', 'pct', '%\n그 시즌 전체 공 가운데 이 구종의 비율입니다.', function (s, t) { return p1(s.n, t); }],
    ['km/h', 'spd', 'km/h\n평균 구속입니다.', function (s) { return s.spd_n > 0 ? (s.spd_sum / s.spd_n).toFixed(1) : '-'; }],
    ['수직(cm)', 'pfx_z', '수직(cm)\n중력 영향을 뺀 위아래 움직임 평균입니다(Induced). + 는 솟는 쪽입니다.', function (s) { return s.pfx_n > 0 ? (s.pfx_z_sum / s.pfx_n * IN2CM).toFixed(1) : '-'; }],
    ['수평(cm)', 'pfx_x', '수평(cm)\n중력 영향을 뺀 좌우 움직임 평균입니다. 포수 시점, + 는 1루 쪽입니다.', function (s) { return s.pfx_n > 0 ? (s.pfx_x_sum / s.pfx_n * IN2CM).toFixed(1) : '-'; }],
    ['PA', null, 'PA\n이 구종으로 끝난 타석 수입니다.', function (s) { return i0(s.pa); }],
    ['AB', null, 'AB\n타수입니다(볼넷·몸에 맞는 볼·희생타 제외).', function (s) { return i0(s.ab); }],
    ['H', 'h', 'H\n안타입니다.', function (s) { return i0(s.h); }],
    ['1B', 'b1', '1B\n1루타입니다(내야안타·번트 안타 포함).', function (s) { return i0(s.b1); }],
    ['2B', 'b2', '2B\n2루타입니다.', function (s) { return i0(s.b2); }],
    ['3B', 'b3', '3B\n3루타입니다.', function (s) { return i0(s.b3); }],
    ['HR', 'hr', 'HR\n홈런입니다.', function (s) { return i0(s.hr); }],
    ['SO', 'k_pct', 'SO\n삼진입니다(낫아웃 출루 포함).', function (s) { return i0(s.so); }],
    ['BBE', 'bbe', 'BBE\n타구 수입니다(삼진·볼넷·몸에 맞는 볼 제외).', function (s) { return i0(s.bbe); }],
    ['BA', 'ba', 'BA\n타율입니다.\n계산식: H ÷ AB', function (s) { return r3(s.h, s.ab); }],
    ['SLG', 'slg', 'SLG\n장타율입니다.\n계산식: (1B + 2×2B + 3×3B + 4×HR) ÷ AB', function (s) { return r3(s.b1 + 2 * s.b2 + 3 * s.b3 + 4 * s.hr, s.ab); }],
    ['wOBA', 'woba', 'wOBA\n가중 출루율입니다. 시즌 가중치는 선수 통계와 같습니다.\n계산식: (wBB·BB + wHBP·HBP + w1B·1B + w2B·2B + w3B·3B + wHR·HR) ÷ (AB + BB + SF + HBP)', function (s, t, w) { const v = wobaValue(s, w); return v === null ? '-' : r3(v, 1); }],
    ['Whiff%', 'whiff', 'Whiff%\n헛스윙 ÷ 스윙 × 100 입니다.', function (s) { return p1(s.wh, s.sw); }],
    ['PutAway%', null, 'PutAway%\n2스트라이크에서 던진 공 가운데 삼진으로 끝난 비율입니다(Savant).\n계산식: 2스트라이크 삼진 ÷ 2스트라이크 공 × 100', function (s) { return p1(s.ts_so, s.ts_n); }],
  ];
  const TB_SEASONS = 3;

  /**
   * 구종별 시즌 표입니다. 위 고르기(타자 손 side·카운트 cnt)와 연동하고, 고른 지표(metricKey) 열을 칠합니다.
   * 시즌은 최근 순, 구종은 그 시즌에 많이 던진 순입니다. showAll 이 아니면 최근 3시즌만.
   * weights 는 { 시즌: kbo_woba_weights_by_season 행 } 입니다. 응답에 hbp 가 없거나 가중치가 없으면 wOBA 열을,
   * bc(카운트별)가 없으면 PutAway% 열을 숨깁니다(데이터에 없는 값은 두지 않음).
   */
  function tableHtml(data, side, cnt, metricKey, showAll, weights) {
    const rows = (data && data.rows) || [];
    const hasBc = rows.some(function (r) { return r.bc; });
    const hasHbp = rows.some(function (r) { return r.hbp !== undefined && r.hbp !== null; });
    const hasW = !!weights && Object.keys(weights).length > 0;
    const cols = TCOLS.filter(function (c) {
      if (c[0] === 'PutAway%') return hasBc;
      if (c[0] === 'wOBA') return hasHbp && hasW;
      return true;
    });
    const agg = aggregate(data, side, cnt);
    const seasons = agg.seasons.slice().sort(function (a, b) { return b - a; });
    const shown = showAll ? seasons : seasons.slice(0, TB_SEASONS);
    const th = function (label, tip, key) {
      return '<th' + (key && key === metricKey ? ' class="pa-tb-on"' : '') + ' data-tip="' + esc(tip) + '">' + esc(label) + '</th>';
    };
    let h = '<div class="pa-tb-wrap"><table class="pa-tb"><thead><tr>'
      + '<th data-tip="시즌\n정규시즌입니다.">시즌</th><th data-tip="구종\n화면 구종 이름입니다(직구 → 포심 패스트볼, 투심 → 싱커).">구종</th>';
    cols.forEach(function (c) { h += th(c[0], c[2], c[1]); });
    h += '</tr></thead><tbody>';
    shown.forEach(function (y) {
      const S = agg.bySeason[y];
      const types = Object.keys(S.types).filter(function (t) { return S.types[t].n > 0; })
        .sort(function (a, b) { return S.types[b].n - S.types[a].n || (a < b ? -1 : 1); });
      types.forEach(function (t, i) {
        const s = S.types[t], w = weights ? weights[y] : null;
        h += '<tr class="pa-tb-row' + (i === 0 ? ' pa-tb-first' : '') + '"><td>' + y + '</td>'
          + '<td class="pa-tb-type" style="--c:' + colorOf(t) + '">' + esc(t) + '</td>';
        cols.forEach(function (c) {
          h += '<td' + (c[1] && c[1] === metricKey ? ' class="pa-tb-on"' : '') + '>' + esc(c[3](s, S.total, w)) + '</td>';
        });
        h += '</tr>';
      });
    });
    h += '</tbody></table></div>';
    if (seasons.length > TB_SEASONS) {
      h += '<button type="button" class="pa-tb-more" data-all="' + (showAll ? '1' : '0') + '">'
        + (showAll ? '최근 3시즌만' : '시즌 더 보기 (' + (seasons.length - TB_SEASONS) + ')') + '</button>';
    }
    return h;
  }

  // ---- 구종별 Run Value 표(Savant Run Values by Pitch Type, evan) ----
  // 위 고르기(타자 손·카운트)와 연동하지 않고 늘 모든 공 기준입니다. x 계열·Hard-Hit% 는 데이터에 없어 두지 않습니다.
  // RV/100 = 구종 가치 ÷ 그 가치를 잰 공 수 × 100. 가치는 투수 쪽 부호(실점을 막으면 +)입니다.
  function signed(v, d) { return (v > 0 ? '+' : '') + v.toFixed(d); }
  function rvCls(v) { return 'pa-rv' + (v > 0 ? ' pa-rv--pos' : v < 0 ? ' pa-rv--neg' : ''); }
  const RVCOLS = [
    ['RV/100', 'RV/100\n공 100개당 구종 가치입니다. 실점을 막으면 + 입니다.\n계산식: Run Value ÷ 공 × 100', function (s) { return s.rv_n > 0 ? 100 * s.rv / s.rv_n : null; }, 2],
    ['Run Value', 'Run Value\n이 구종으로 던진 공의 득점 가치 합입니다. 볼카운트·주자·아웃별 기대 득점으로 셉니다(폭투·포일·보크 제외).', function (s) { return s.rv_n > 0 ? s.rv : null; }, 1],
  ];
  const RVSTAT = [
    ['Pitches', 'Pitches\n이 구종으로 던진 공 수입니다.', function (s) { return i0(s.n); }],
    ['%', '%\n그 시즌 전체 공 가운데 이 구종의 비율입니다.', function (s, t) { return p1(s.n, t); }],
    ['PA', 'PA\n이 구종으로 끝난 타석 수입니다.', function (s) { return i0(s.pa); }],
    ['BA', 'BA\n타율입니다.\n계산식: H ÷ AB', function (s) { return r3(s.h, s.ab); }],
    ['SLG', 'SLG\n장타율입니다.\n계산식: (1B + 2×2B + 3×3B + 4×HR) ÷ AB', function (s) { return r3(s.b1 + 2 * s.b2 + 3 * s.b3 + 4 * s.hr, s.ab); }],
    ['wOBA', 'wOBA\n가중 출루율입니다. 시즌 가중치는 선수 통계와 같습니다.', function (s, t, w) { const v = wobaValue(s, w); return v === null ? '-' : r3(v, 1); }],
    ['Whiff%', 'Whiff%\n헛스윙 ÷ 스윙 × 100 입니다.', function (s) { return p1(s.wh, s.sw); }],
    ['K%', 'K%\n삼진 ÷ 이 구종으로 끝난 타석 × 100 입니다.', function (s) { return p1(s.so, s.pa); }],
    ['PutAway%', 'PutAway%\n2스트라이크 공 가운데 삼진으로 끝난 비율입니다.\n계산식: 2스트라이크 삼진 ÷ 2스트라이크 공 × 100', function (s) { return p1(s.ts_so, s.ts_n); }],
  ];

  /** 구종별 Run Value 표입니다. 최근 순 시즌, 그 시즌 많이 던진 구종 순. showAll 이 아니면 최근 3시즌만. */
  function rvTableHtml(data, showAll, weights) {
    const rows = (data && data.rows) || [];
    const hasBc = rows.some(function (r) { return r.bc; });
    const hasHbp = rows.some(function (r) { return r.hbp !== undefined && r.hbp !== null; });
    const hasW = !!weights && Object.keys(weights).length > 0;
    const stats = RVSTAT.filter(function (c) {
      if (c[0] === 'PutAway%') return hasBc;
      if (c[0] === 'wOBA') return hasHbp && hasW;
      return true;
    });
    const agg = aggregate(data, '', '');
    const seasons = agg.seasons.slice().sort(function (a, b) { return b - a; });
    const shown = showAll ? seasons : seasons.slice(0, TB_SEASONS);
    let h = '<div class="pa-tb-wrap"><table class="pa-tb pa-rvt"><thead><tr>'
      + '<th data-tip="시즌\n정규시즌입니다.">시즌</th><th data-tip="구종\n화면 구종 이름입니다(직구 → 포심 패스트볼, 투심 → 싱커).">구종</th>';
    RVCOLS.concat(stats).forEach(function (c) { h += '<th data-tip="' + esc(c[1]) + '">' + esc(c[0]) + '</th>'; });
    h += '</tr></thead><tbody>';
    shown.forEach(function (y) {
      const S = agg.bySeason[y];
      const types = Object.keys(S.types).filter(function (t) { return S.types[t].n > 0; })
        .sort(function (a, b) { return S.types[b].n - S.types[a].n || (a < b ? -1 : 1); });
      types.forEach(function (t, i) {
        const s = S.types[t], w = weights ? weights[y] : null;
        h += '<tr class="pa-tb-row' + (i === 0 ? ' pa-tb-first' : '') + '"><td>' + y + '</td>'
          + '<td class="pa-tb-type" style="--c:' + colorOf(t) + '">' + esc(t) + '</td>';
        RVCOLS.forEach(function (c) {
          const v = c[2](s);
          h += v === null ? '<td>-</td>' : '<td class="' + rvCls(v) + '">' + signed(v, c[3]) + '</td>';
        });
        stats.forEach(function (c) { h += '<td>' + esc(c[2](s, S.total, w)) + '</td>'; });
        h += '</tr>';
      });
    });
    h += '</tbody></table></div>';
    if (seasons.length > TB_SEASONS) {
      h += '<button type="button" class="pa-tb-more pa-rvt-more" data-all="' + (showAll ? '1' : '0') + '">'
        + (showAll ? '최근 3시즌만' : '시즌 더 보기 (' + (seasons.length - TB_SEASONS) + ')') + '</button>';
    }
    return h;
  }

  // ---- Plate Discipline 표(Savant 투수 Plate Discipline, evan) ----
  // 시즌 한 줄(모든 구종·타자 손·카운트 합)이고 위 고르기와 연동하지 않습니다. Savant 처럼 모든 시즌과 통산 줄.
  // 존 기준 지표라 공 위치 추적이 절반쯤인 2016 은 뺍니다(evan).
  // Meatball 은 Gameday Zone 5(존 한가운데, evan)이고, 응답에 mb_n 이 있을 때만 두 열을 둡니다.
  const PD_FIRST = 2017;
  const PDCOLS = [
    ['Pitches', 'Pitches\n그 시즌 던진 공 수입니다.', function (s) { return i0(s.n); }],
    ['Zone %', 'Zone %\n스트라이크 존 안 공 ÷ 위치가 있는 공 × 100 입니다. 존 폭은 공 반지름을 더한 20인치입니다.', function (s) { return p1(s.z_n, s.z_n + s.o_n); }],
    ['Zone Swing %', 'Zone Swing %\n존 안 공에 스윙 ÷ 존 안 공 × 100 입니다(Z-Swing%).', function (s) { return p1(s.z_sw, s.z_n); }],
    ['Zone Contact %', 'Zone Contact %\n존 안 컨택 ÷ 존 안 스윙 × 100 입니다(Z-Contact%).', function (s) { return p1(s.z_ct, s.z_sw); }],
    ['Chase %', 'Chase %\n존 밖 공에 스윙 ÷ 존 밖 공 × 100 입니다(O-Swing%).', function (s) { return p1(s.o_sw, s.o_n); }],
    ['Chase Contact %', 'Chase Contact %\n존 밖 컨택 ÷ 존 밖 스윙 × 100 입니다(O-Contact%).', function (s) { return p1(s.o_ct, s.o_sw); }],
    ['Edge %', 'Edge %\n존 끝 근처(Shadow) 공 ÷ 위치가 있는 공 × 100 입니다.', function (s) { return p1(s.edge_n, s.z_n + s.o_n); }],
    ['1st Pitch Strike %', '1st Pitch Strike %\n0-0 에서 볼이 아닌 공 ÷ 0-0 공 × 100 입니다(F-Strike%).', function (s) { return p1(s.fp_str, s.fp_n); }],
    ['Swing %', 'Swing %\n스윙 ÷ 공 × 100 입니다.', function (s) { return p1(s.sw, s.pd_n); }],
    ['Whiff %', 'Whiff %\n헛스윙 ÷ 스윙 × 100 입니다.', function (s) { return p1(s.wh, s.sw); }],
    ['Meatball %', 'Meatball %\n존 한가운데(Gameday Zone 5)로 들어온 공 ÷ 위치가 있는 공 × 100 입니다.', function (s) { return p1(s.mb_n, s.z_n + s.o_n); }, 'mb'],
    ['Meatball Swing %', 'Meatball Swing %\n존 한가운데(Zone 5) 공에 스윙 ÷ 존 한가운데 공 × 100 입니다.', function (s) { return p1(s.mb_sw, s.mb_n); }, 'mb'],
    ['CStr %', 'CStr %\n루킹 스트라이크 ÷ 공 × 100 입니다.', function (s) { return p1(s.cs, s.pd_n); }],
    ['CSW %', 'CSW %\n(루킹 스트라이크 + 헛스윙) ÷ 공 × 100 입니다.', function (s) { return p1(s.cs + s.wh, s.pd_n); }],
  ];

  /** 그 시즌 모든 구종을 더한 합계입니다. */
  function seasonSums(S) {
    const t = emptySums();
    Object.keys(S.types).forEach(function (k) {
      const s = S.types[k];
      Object.keys(t).forEach(function (f) { t[f] += s[f] || 0; });
    });
    return t;
  }

  /** Plate Discipline 표입니다. 최근 순 모든 시즌(2017~) 한 줄씩과 맨 아래 통산 줄입니다. */
  function pdTableHtml(data) {
    const rows = (data && data.rows) || [];
    const hasMb = rows.some(function (r) { return r.mb_n !== undefined && r.mb_n !== null; });
    const cols = PDCOLS.filter(function (c) { return c[3] !== 'mb' || hasMb; });
    const agg = aggregate(data, '', '');
    const seasons = agg.seasons.filter(function (y) { return y >= PD_FIRST; }).sort(function (a, b) { return b - a; });
    let h = '<div class="pa-tb-wrap"><table class="pa-tb pa-pdt"><thead><tr><th data-tip="시즌\n정규시즌입니다(2016 은 공 위치 추적이 절반쯤이라 뺍니다).">시즌</th>';
    cols.forEach(function (c) { h += '<th data-tip="' + esc(c[1]) + '">' + esc(c[0]) + '</th>'; });
    h += '</tr></thead><tbody>';
    const total = emptySums();
    seasons.forEach(function (y) {
      const s = seasonSums(agg.bySeason[y]);
      Object.keys(total).forEach(function (f) { total[f] += s[f] || 0; });
      h += '<tr class="pa-tb-row"><td>' + y + '</td>';
      cols.forEach(function (c) { h += '<td>' + esc(c[2](s)) + '</td>'; });
      h += '</tr>';
    });
    if (seasons.length) {
      h += '<tr class="pa-tb-total"><td data-tip="통산\n위 시즌(2017~)을 모두 더해 다시 계산한 값입니다.">통산</td>';
      cols.forEach(function (c) { h += '<td>' + esc(c[2](total)) + '</td>'; });
      h += '</tr>';
    }
    return h + '</tbody></table></div>';
  }

  /** 지표 고르기 칸의 option 글자입니다(묶음은 optgroup). */
  function metricOptionsHtml(hasWoba) {
    let html = '', group = null;
    METRICS.forEach(function (m) {
      if (m.needsW && !hasWoba) return;  // wOBA: 응답에 hbp 가 있고 시즌 가중치를 받았을 때만
      if (m.group !== group) {
        if (group) html += '</optgroup>';
        group = m.group;
        if (group) html += '<optgroup label="' + esc(group) + '">';
      }
      // 항목 설명(title)은 두지 않습니다. 열린 목록에는 브라우저 기본(검은) 툴팁만 뜨고, 같은 설명이 고르기 아래 줄에 나옵니다.
      html += '<option value="' + m.key + '">' + esc(m.label) + '</option>';
    });
    return html + (group ? '</optgroup>' : '');
  }

  const api = { METRICS, metric, metricOk, aggregate, series, fmt, chartSvg, legendHtml, metricOptionsHtml, countOptionsHtml, tableHtml, rvTableHtml, pdTableHtml };
  PA.trend = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
