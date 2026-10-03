/*
 * 테이블 계보 탭 화면입니다(database-explorer.html #lineage).
 *
 * 계산은 model.js 가 합니다. 위쪽 HTML 을 만드는 함수는 DOM 을 건드리지 않아
 * Node 로 검증하고, 아래 화면 부분(데이터 받기·그리기·누르기)은 브라우저에서만
 * 돕니다. 데이터 받기는 js/stats/data.js 의 getJson 을 씁니다.
 */
(function (root) {
  'use strict';
  const L = root.Lineage = root.Lineage || {};
  function M() { return L.model; }

  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/[&<>"]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m]));
  }

  const STATE_LABEL = { ok: '정상', fail: '실패', stale: '오래됨', none: '기록 없음', manual: '손 작업' };
  const KIND_LABEL = { collected: '받아 온 표', derived: '계산 표', manual: '손 작업 표' };
  const SUM_TIP = {
    ok: '이 표를 쓰는 작업의 마지막 실행이 성공했고 기준 시간 안에 갱신된 표입니다.',
    fail: '이 표를 쓰는 작업 가운데 마지막 실행이 실패한 것이 있는 표입니다.',
    stale: '기준 시간(daily·roster 36시간, weekly 8일, monthly 35일)보다 오래 갱신되지 않은 표입니다.',
    none: '이 표를 쓰는 작업의 실행 기록이 아직 없는 표입니다.',
    manual: '수집 작업 없이 손으로 채운 표입니다. 상태 점을 붙이지 않습니다.',
  };

  /** 화면 경로(계보 파일의 pages[].path)를 pages/ 안에서 여는 주소로 바꿉니다. */
  function pageHref(path) {
    const p = String(path || '');
    return p.startsWith('pages/') ? p.slice(6) : '../' + p;
  }

  /**
   * 표·작업의 상태를 한 번에 셉니다. details 가 없으면(운영 정보를 못 받음) null.
   * 반환 { tables: {name: tableStatus 결과}, jobs: {id: jobStatus 결과}, sum: summarize 결과 }
   */
  function statusMap(lin, details, nowMs) {
    if (!details) return null;
    const m = M();
    const out = { tables: {}, jobs: {}, sum: m.summarize(lin, details, nowMs) };
    (lin.tables || []).forEach(t => { out.tables[t.name] = m.tableStatus(lin, t, details, nowMs); });
    (lin.jobs || []).forEach(j => { out.jobs[j.id] = m.jobStatus(lin, j, details, nowMs); });
    return out;
  }

  /** 요약 줄입니다. sum 이 없으면(운영 정보 없음) 빈 글자. active 는 켜진 상태 이름. */
  function summaryHtml(sum, active) {
    if (!sum) return '';
    const btn = k => `<button type="button" class="lin-sum-btn${active === k ? ' on' : ''}" data-state="${k}" data-tooltip="${esc(SUM_TIP[k])}">`
      + `<span class="lin-dot lin-${k}"></span>${STATE_LABEL[k]} <b>${sum[k]}</b></button>`;
    return ['ok', 'fail', 'stale', 'none'].map(btn).join('')
      + `<span class="lin-sum-manual" data-tooltip="${esc(SUM_TIP.manual)}">손 작업 <b>${sum.manual}</b></span>`;
  }

  /** 상자 안 상태 표시(점 또는 '손 작업')입니다. 표·작업만 붙입니다. */
  function markHtml(n, lin, status) {
    if (!status) return '';
    const m = M();
    if (n.kind === 'manual') {
      return `<span class="lin-tag" data-tooltip="${esc(m.dotText(lin, { state: 'manual', items: [] }, n.ref.manual_note))}">손 작업</span>`;
    }
    let st = null;
    if (n.kind === 'collected' || n.kind === 'derived') st = status.tables[n.ref.name];
    if (n.kind === 'job') st = status.jobs[n.ref.id];
    if (!st) return '';
    return `<span class="lin-dot lin-${st.state}" data-tooltip="${esc(m.dotText(lin, st))}"></span>`;
  }

  /** 상자에 마우스를 올렸을 때 보이는 설명입니다. */
  function boxTip(n) {
    if (n.kind === 'collected' || n.kind === 'derived' || n.kind === 'manual') return n.ref.desc || n.label;
    if (n.kind === 'job') return `${n.label}: ${n.sub} 실행`;
    if (n.kind === 'page') return `${n.label} (${n.sub})`;
    if (n.kind === 'group') return n.sub === '접기' ? '누르면 손 작업 표를 접습니다.' : '누르면 손 작업 표를 펼칩니다.';
    return n.label;
  }

  function boxHtml(n, lin, status, style) {
    return `<button type="button" class="lin-box lin-k-${n.kind}" data-id="${esc(n.id)}"${style ? ` style="${style}"` : ''} data-tooltip="${esc(boxTip(n))}">`
      + markHtml(n, lin, status)
      + `<span class="lin-label">${esc(n.label)}</span>`
      + (n.sub && n.kind !== 'page' ? `<span class="lin-sub">${esc(n.sub)}</span>` : '')
      + '</button>';
  }

  /** 넓은 화면 그림입니다(칸 제목 + 선 SVG + 상자). */
  function graphHtml(graph, lay, lin, status) {
    const m = M();
    let h = `<div class="lin-heads" style="width:${lay.width}px">`;
    m.COLS.forEach(function (c, i) {
      h += `<div class="lin-head" style="left:${Math.round(i * lay.colW)}px;width:${lay.boxW}px">${esc(m.COL_LABEL[c])}</div>`;
    });
    h += `</div><div class="lin-canvas" style="width:${lay.width}px;height:${lay.height}px">`;
    h += `<svg class="lin-svg" width="${lay.width}" height="${lay.height}" viewBox="0 0 ${lay.width} ${lay.height}" aria-hidden="true">`;
    graph.edges.forEach(function (e, i) {
      h += `<path class="lin-edge" data-i="${i}" d="${m.edgePath(lay, e)}"></path>`;
    });
    h += '</svg>';
    m.COLS.forEach(function (c) {
      graph.cols[c].forEach(function (n) {
        const b = lay.boxes[n.id];
        h += boxHtml(n, lin, status, `left:${b.x}px;top:${b.y}px;width:${b.w}px;height:${b.h}px`);
      });
    });
    return h + '</div>';
  }

  /** 휴대폰 목록입니다. 선 대신 상자마다 이어지는 곳을 적습니다. */
  function listHtml(graph, lin, status) {
    const m = M();
    const label = id => (graph.nodes[id] ? graph.nodes[id].label : id);
    let h = '';
    m.COLS.forEach(function (c) {
      h += `<section class="lin-list-col"><h4>${esc(m.COL_LABEL[c])}</h4><ul class="lin-list">`;
      graph.cols[c].forEach(function (n) {
        const out = graph.edges.filter(e => e.from === n.id).map(e => label(e.to));
        const inn = graph.edges.filter(e => e.to === n.id).map(e => label(e.from));
        const next = out.length ? `→ 이어지는 곳: ${out.join(', ')}` : (inn.length ? `← 가져오는 곳: ${inn.join(', ')}` : '');
        h += `<li>${boxHtml(n, lin, status, '')}${next ? `<div class="lin-next">${esc(next)}</div>` : ''}</li>`;
      });
      h += '</ul></section>';
    });
    return h;
  }

  function statusLine(lin, it) {
    return `<li><span class="lin-status"><span class="lin-dot lin-${it.state}"></span>${esc(M().itemText(lin, it))}</span></li>`;
  }

  function listOrDash(items) {
    return items.length ? `<ul>${items.join('')}</ul>` : '-';
  }

  /**
   * 상세 카드 안쪽 HTML 입니다. ctx = { graph, status(statusMap 결과 또는 null), rows({표: 행 수} 또는 null) }
   */
  function detailHtml(node, lin, ctx) {
    const m = M();
    const g = ctx.graph;
    const label = id => (g.nodes[id] ? g.nodes[id].label : m.nodeName(id));
    const ins = g.edges.filter(e => e.to === node.id).map(e => e.from);
    const outs = g.edges.filter(e => e.from === node.id).map(e => e.to);
    const pageLink = id => {
      const p = g.nodes[id] && g.nodes[id].ref;
      return p ? `<li><a href="${esc(pageHref(p.path))}">${esc(m.pageLabel(p))}</a></li>` : '';
    };
    let title = esc(node.label);
    let body = '';

    if (node.kind === 'collected' || node.kind === 'derived' || node.kind === 'manual') {
      const t = node.ref;
      title += `<span class="lin-kind">${KIND_LABEL[t.kind] || ''}</span>`;
      const rows = ctx.rows ? (ctx.rows[t.name] === undefined ? '-' : `${Number(ctx.rows[t.name]).toLocaleString('ko-KR')}행`) : '운영 정보 없음';
      const st = ctx.status ? ctx.status.tables[t.name] : null;
      const writers = (t.written_by || []).map(function (path) {
        const s = (lin.scripts || []).find(x => x.path === path);
        const jobs = s ? (s.jobs || []).map(j => {
          const jb = (lin.jobs || []).find(x => x.id === j);
          return jb ? `${j}(${jb.schedule_kst})` : j;
        }).join(', ') : '';
        return `<li><code>${esc(path)}</code>${jobs ? ' · ' + esc(jobs) : ''}</li>`;
      });
      const notes = (t.written_by || []).map(p => (lin.scripts || []).find(x => x.path === p)).filter(s => s && s.note).map(s => `<li>${esc(s.note)}</li>`);
      body += `<p class="lin-desc">${esc(t.desc || '설명이 아직 없습니다.')}</p>`;
      if (t.category) body += `<p class="text-muted lin-cat">분류: ${esc(t.category)}</p>`;
      body += '<dl class="lin-dl">';
      body += `<dt>행 수</dt><dd>${esc(rows)}</dd>`;
      if (t.kind !== 'manual') {
        body += `<dt>쓰는 스크립트</dt><dd>${listOrDash(writers)}</dd>`;
        body += `<dt>마지막 실행</dt><dd>${st ? (st.items.length ? `<ul>${st.items.map(it => statusLine(lin, it)).join('')}</ul>` : '실행 기록을 남기는 단계가 없습니다.') : '운영 정보 없음'}</dd>`;
      } else {
        body += `<dt>손 작업</dt><dd>${esc(t.manual_note || '손으로 채운 표입니다.')}</dd>`;
      }
      if ((t.derived_from || []).length) body += `<dt>재료 표</dt><dd>${listOrDash(t.derived_from.map(x => `<li><code>${esc(x)}</code></li>`))}</dd>`;
      body += `<dt>읽는 API 주소</dt><dd>${(t.routes || []).length ? listOrDash(t.routes.map(r => `<li><code>${esc(r)}</code></li>`)) : '데이터 탐색 주소(/db/table)로 읽습니다.'}</dd>`;
      body += `<dt>쓰는 화면</dt><dd>${listOrDash((t.pages || []).map(p => pageLink('page:' + p)).filter(Boolean))}</dd>`;
      if (notes.length) body += `<dt>참고</dt><dd><ul>${notes.join('')}</ul></dd>`;
      body += '</dl>';
    } else if (node.kind === 'job') {
      const j = node.ref;
      const st = ctx.status ? ctx.status.jobs[j.id] : null;
      const byKey = {};
      if (st) st.items.forEach(it => { byKey[it.key] = it; });
      const steps = (j.steps || []).map(function (s) {
        const it = s.status_key && byKey[s.status_key];
        const mark = it ? ` <span class="lin-status"><span class="lin-dot lin-${it.state}"></span>${esc(STATE_LABEL[it.state])}</span>` : '';
        return `<li>${esc(s.name)} · <code>${esc(s.script)}</code>${s.status_key ? ` · 기록 키 <code>${esc(s.status_key)}</code>` : ''}${mark}</li>`;
      });
      body += '<dl class="lin-dl">';
      body += `<dt>실행 시각</dt><dd>${esc(j.schedule_kst)} (GitHub Actions <code>${esc(j.workflow)}</code>)</dd>`;
      body += `<dt>기준 시간</dt><dd>${esc(j.stale_hours)}시간 넘게 갱신이 없으면 오래됨으로 봅니다.</dd>`;
      body += `<dt>마지막 실행</dt><dd>${st ? (st.items.length ? `<ul>${st.items.map(it => statusLine(lin, it)).join('')}</ul>` : '-') : '운영 정보 없음'}</dd>`;
      body += `<dt>단계</dt><dd>${listOrDash(steps)}</dd>`;
      body += `<dt>원천</dt><dd>${listOrDash(ins.map(id => `<li>${esc(label(id))}</li>`))}</dd>`;
      body += `<dt>쓰는 표</dt><dd>${listOrDash(outs.map(id => `<li><code>${esc(label(id))}</code></li>`))}</dd>`;
      body += '</dl>';
    } else if (node.kind === 'source') {
      const s = node.ref;
      body += '<dl class="lin-dl">';
      body += `<dt>주소</dt><dd>${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a>` : '-'}</dd>`;
      body += `<dt>받는 작업</dt><dd>${listOrDash(outs.filter(id => m.nodeType(id) === 'job').map(id => `<li>${esc(label(id))}</li>`))}</dd>`;
      body += `<dt>바로 쓰는 화면</dt><dd>${listOrDash(outs.filter(id => m.nodeType(id) === 'page').map(pageLink).filter(Boolean))}</dd>`;
      body += '</dl>';
    } else if (node.kind === 'page') {
      const p = node.ref;
      title = `<a href="${esc(pageHref(p.path))}">${esc(node.label)}</a>`;
      body += '<dl class="lin-dl">';
      body += `<dt>경로</dt><dd><code>${esc(p.path)}</code></dd>`;
      body += `<dt>부르는 API 주소</dt><dd>${listOrDash((p.routes || []).map(r => `<li><code>${esc(r)}</code></li>`))}</dd>`;
      body += `<dt>읽는 표·원천</dt><dd>${listOrDash(ins.map(id => `<li>${esc(label(id))}</li>`))}</dd>`;
      body += '</dl>';
    }
    return `<div class="card-header"><h3 class="card-title">${title}</h3>`
      + '<button type="button" class="lin-close" data-close="1">닫기</button></div>'
      + `<div class="card-body">${body}</div>`;
  }

  // ===== 화면(브라우저에서만) =====

  const api = { esc, pageHref, statusMap, summaryHtml, graphHtml, listHtml, detailHtml, STATE_LABEL, SUM_TIP };
  L.view = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
