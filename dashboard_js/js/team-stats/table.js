/*
 * 팀 통계 표 그리기입니다. HTML 문자열을 만들 뿐 DOM 에 붙이지는 않습니다
 * (붙이는 일은 page.js). columns.js 가 먼저 로드되어야 합니다.
 */
(function (root) {
  'use strict';
  const TS = root.TeamStats = root.TeamStats || {};
  function C() { return TS.columns; }

  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/[&<>"]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m]));
  }

  function missing(v) {
    return v === null || v === undefined || (typeof v === 'number' && !Number.isFinite(v));
  }

  /**
   * 지수 칸 색 단계입니다. 리그 평균 100 에서 좋은 쪽으로 2·5·10 이상
   * 떨어지면 ts-up1·2·3, 나쁜 쪽이면 ts-down1·2·3 입니다.
   */
  function indexClass(v, dir) {
    if (missing(v)) return '';
    const d = (v - 100) * (dir === 'low' ? -1 : 1);
    const a = Math.abs(d);
    const lv = a >= 10 ? 3 : a >= 5 ? 2 : a >= 2 ? 1 : 0;
    if (!lv) return '';
    return (d > 0 ? 'ts-up' : 'ts-down') + lv;
  }

  function wlPct(o) {
    const t = o.w + o.l;
    return t ? o.w / t : 0;
  }

  /** 정렬입니다. 값이 없는 행은 방향과 상관없이 맨 아래로 갑니다. */
  function sortRows(rows, key, dir, kind) {
    const sign = dir === 'asc' ? 1 : -1;
    return rows.slice().sort(function (a, b) {
      const av = a[key], bv = b[key];
      const an = missing(av), bn = missing(bv);
      if (an && bn) return 0;
      if (an) return 1;
      if (bn) return -1;
      if (kind === 'wl') return sign * (wlPct(av) - wlPct(bv));
      if (typeof av === 'string' || typeof bv === 'string') {
        return sign * String(av).localeCompare(String(bv), 'ko');
      }
      return sign * (av - bv);
    });
  }

  function sorted(opt) {
    const col = opt.cols.find(c => c.key === opt.sort.key);
    return col ? sortRows(opt.rows, col.key, opt.sort.dir, col.kind) : opt.rows.slice();
  }

  function rowHtml(r, rank, opt, isLeague) {
    const showRank = opt.rank !== false;
    const href = !isLeague && opt.teamHref ? opt.teamHref(r.team) : null;
    const name = isLeague ? '리그 평균' : r.team;
    const tcell = href ? `<a class="player-link" href="${esc(href)}">${esc(name)}</a>` : esc(name);
    const cls = isLeague ? ' class="ts-league"' : (opt.highlight && opt.highlight === r.team ? ' class="ts-hl"' : '');
    let h = `<tr${cls}>`;
    if (showRank) h += `<td class="ts-rank">${rank}</td>`;
    h += `<td class="ts-team">${tcell}</td>`;
    for (const c of opt.cols) {
      const v = r[c.key];
      const k = [];
      if (c.index && !isLeague) k.push(indexClass(v, c.index));
      if ((c.kind === 'signed0' || c.kind === 'signed1') && !missing(v)) k.push(v > 0 ? 'ts-pos' : v < 0 ? 'ts-neg' : '');
      const cl = k.filter(Boolean).join(' ');
      h += `<td${cl ? ` class="${cl}"` : ''}>${esc(C().fmt(v, c.kind))}</td>`;
    }
    return h + '</tr>';
  }

  /** 표 HTML 입니다. 리그 평균 행은 정렬과 상관없이 맨 아래입니다. */
  function renderTable(opt) {
    const showRank = opt.rank !== false;
    let h = '<div class="table-container ts-wrap"><table class="table ts-table"><thead><tr>';
    if (showRank) h += '<th class="ts-rank">#</th>';
    h += '<th class="ts-team">팀</th>';
    for (const c of opt.cols) {
      const on = opt.sort && opt.sort.key === c.key;
      const ind = on ? `<span class="sort-ind">${opt.sort.dir === 'asc' ? '▲' : '▼'}</span>` : '';
      h += `<th class="sortable${on ? ' sorted' : ''}" data-key="${esc(c.key)}">`
        + `<span class="ts-term" data-col="${esc(c.key)}">${esc(c.label)}</span>${ind}</th>`;
    }
    h += '</tr></thead><tbody>';
    sorted(opt).forEach(function (r, i) { h += rowHtml(r, i + 1, opt, false); });
    if (opt.league) h += rowHtml(opt.league, '', opt, true);
    return h + '</tbody></table></div>';
  }

  function csvCell(s) {
    s = String(s);
    return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }

  /** 지금 보이는 표 그대로의 CSV 입니다. 엑셀용 BOM 을 붙입니다. */
  function toCsv(opt) {
    const lines = [['#', '팀'].concat(opt.cols.map(c => c.label))];
    sorted(opt).forEach(function (r, i) {
      lines.push([i + 1, r.team].concat(opt.cols.map(c => C().fmt(r[c.key], c.kind))));
    });
    if (opt.league) lines.push(['', '리그 평균'].concat(opt.cols.map(c => C().fmt(opt.league[c.key], c.kind))));
    return '\uFEFF' + lines.map(l => l.map(csvCell).join(',')).join('\r\n') + '\r\n';
  }

  /** 머리글에 마우스를 올렸을 때 뜨는 설명 창 내용입니다. */
  function tipHtml(d) {
    if (!d) return '';
    let h = `<b>${esc(d.label)}</b>${esc(d.desc)}`;
    if (d.formula) h += `<span class="f">계산식: ${esc(d.formula)}</span>`;
    if (d.since) h += `<span class="f">${d.since}년부터 있습니다.</span>`;
    return h;
  }

  const api = { esc, indexClass, sortRows, renderTable, toCsv, tipHtml };
  TS.table = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
