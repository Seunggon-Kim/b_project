/*
 * 팀 성적 탭의 상대 전적·월별 승률 표입니다. HTML 문자열만 만듭니다.
 * table.js·columns.js 가 먼저 로드되어야 합니다.
 */
(function (root) {
  'use strict';
  const TS = root.TeamStats = root.TeamStats || {};
  function esc(s) { return TS.table.esc(s); }
  function wl(v) { return v.d ? `${v.w}-${v.l}-${v.d}` : `${v.w}-${v.l}`; }

  /** 상대 전적입니다. 가로 줄 팀이 세로 칸 팀을 상대로 거둔 승-패(-무). */
  function h2hHtml(splits, order, highlight) {
    let h = '<div class="table-container ts-wrap"><table class="table ts-table ts-h2h"><thead><tr><th class="ts-team">팀</th>';
    order.forEach(function (t) { h += `<th>${esc(t)}</th>`; });
    h += '<th>합계</th></tr></thead><tbody>';
    order.forEach(function (t) {
      const s = splits[t];
      let W = 0, L = 0, D = 0;
      h += `<tr${highlight && highlight === t ? ' class="ts-hl"' : ''}><td class="ts-team">${esc(t)}</td>`;
      order.forEach(function (o) {
        if (o === t) { h += '<td class="ts-self">·</td>'; return; }
        const v = s && s.vs && s.vs[o];
        if (!v) { h += '<td>-</td>'; return; }
        W += v.w; L += v.l; D += v.d;
        const c = v.w > v.l ? 'ts-win' : v.w < v.l ? 'ts-loss' : '';
        h += `<td${c ? ` class="${c}"` : ''}>${wl(v)}</td>`;
      });
      h += `<td class="ts-total">${W}-${L}-${D}</td></tr>`;
    });
    return h + '</tbody></table></div>';
  }

  /** 월별 승률입니다. 3·4월은 묶고(키 4), 9·10월도 묶습니다(키 9). */
  function monthlyHtml(splits, order, highlight) {
    const months = [...new Set(order.flatMap(t => Object.keys((splits[t] && splits[t].month) || {}).map(Number)))]
      .sort((a, b) => a - b);
    let h = '<div class="table-container ts-wrap"><table class="table ts-table ts-month"><thead><tr><th class="ts-team">팀</th>';
    months.forEach(function (m) { h += `<th>${m === 4 ? '3·4월' : m === 9 ? '9·10월' : m + '월'}</th>`; });
    h += '</tr></thead><tbody>';
    order.forEach(function (t) {
      const mm = (splits[t] && splits[t].month) || {};
      h += `<tr${highlight && highlight === t ? ' class="ts-hl"' : ''}><td class="ts-team">${esc(t)}</td>`;
      months.forEach(function (m) {
        const v = mm[m];
        const pct = v && v.w + v.l > 0 ? v.w / (v.w + v.l) : null;
        h += `<td>${esc(TS.columns.fmt(pct, 'avg3'))}</td>`;
      });
      h += '</tr>';
    });
    return h + '</tbody></table></div>';
  }

  function noGamesHtml(season) {
    return `<p class="text-muted ts-sub">${esc(season)}년은 경기별 결과가 없어 볼 수 없습니다. 경기 결과는 2008년부터 있습니다.</p>`;
  }

  function gamesErrorHtml() {
    return '<p class="text-muted ts-sub">경기 결과 자료를 받지 못해 볼 수 없습니다. 잠시 뒤 다시 열어 주세요.</p>';
  }

  const api = { h2hHtml, monthlyHtml, noGamesHtml, gamesErrorHtml };
  TS.record = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
