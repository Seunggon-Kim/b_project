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

  const STATE_LABEL = { ok: '정상', fail: '실패', stale: '오래됨', none: '기록 없음', manual: '기준 표' };
  const KIND_LABEL = { collected: '받아 온 표', derived: '계산 표', manual: '기준 표' };
  const SUM_TIP = {
    ok: '이 표를 쓰는 작업의 마지막 실행이 성공했고 기준 시간 안에 갱신된 표입니다.',
    fail: '이 표를 쓰는 작업 가운데 마지막 실행이 실패한 것이 있는 표입니다.',
    stale: '기준 시간(daily·roster 36시간, weekly 8일, monthly 35일)보다 오래 갱신되지 않은 표입니다.',
    none: '이 표를 쓰는 작업의 실행 기록이 아직 없는 표입니다.',
    manual: '정기 수집 작업 없이 직접 채워 두는 기준 표(팀·구장 등)입니다. 상태 점을 붙이지 않습니다.',
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
  function summaryHtml(sum, active, lin) {
    if (!sum) return '';
    const rule = lin ? M().staleRuleText(lin) : '';
    const tip = k => (k === 'stale' && rule)
      ? `기준 시간(${rule})보다 오래 갱신되지 않은 표입니다.` : SUM_TIP[k];
    const btn = k => `<button type="button" class="lin-sum-btn${active === k ? ' on' : ''}" data-state="${k}" data-tooltip="${esc(tip(k))}">`
      + `<span class="lin-dot lin-${k}"></span>${STATE_LABEL[k]} <b>${sum[k]}</b></button>`;
    return ['ok', 'fail', 'stale', 'none'].map(btn).join('')
      + `<span class="lin-sum-manual" tabindex="0" data-tooltip="${esc(SUM_TIP.manual)}">기준 표 <b>${sum.manual}</b></span>`;
  }

  /** 상자 안 상태 표시(점 또는 '기준')입니다. 표·작업만 붙입니다. */
  function markHtml(n, lin, status) {
    if (!status) return '';
    const m = M();
    if (n.kind === 'manual') {
      return `<span class="lin-tag" data-tooltip="${esc(m.dotText(lin, { state: 'manual', items: [] }, n.ref.manual_note))}">기준</span>`;
    }
    let st = null;
    if (n.kind === 'collected' || n.kind === 'derived') st = status.tables[n.ref.name];
    if (n.kind === 'job') st = status.jobs[n.ref.id];
    if (!st) return '';
    return `<span class="lin-dot lin-${st.state}" data-tooltip="${esc(m.dotText(lin, st))}"></span>`;
  }

  /** 상자에 마우스를 올렸을 때 보이는 설명입니다. */
  function boxTip(n) {
    if (n.kind === 'collected' || n.kind === 'derived' || n.kind === 'manual') return n.ref.desc ? `${n.label}\n${n.ref.desc}` : n.label;
    if (n.kind === 'job') return `${n.label}: ${n.sub} 실행`;
    if (n.kind === 'page') return `${n.label} (${n.sub})`;
    if (n.kind === 'group') return n.sub === '접기' ? '누르면 기준 표를 접습니다.' : '누르면 기준 표를 펼칩니다.';
    return n.label;
  }

  function boxHtml(n, lin, status, style) {
    return `<button type="button" class="lin-box lin-k-${n.kind}" data-id="${esc(n.id)}"${style ? ` style="${style}"` : ''} data-tooltip="${esc(boxTip(n))}">`
      + markHtml(n, lin, status)
      + `<span class="lin-label">${esc(n.label).replace(/_/g, '_<wbr>')}</span>`
      + (n.sub && n.kind !== 'page' ? `<span class="lin-sub">${esc(n.sub)}</span>` : '')
      + '</button>';
  }

  /** 넓은 화면 그림입니다(칸 제목 + 선 SVG + 상자). */
  function graphHtml(graph, lay, lin, status) {
    const m = M();
    let h = `<div class="lin-layers" style="width:${lay.width}px">`;
    m.LAYERS.forEach(function (ly) {
      const i = m.COLS.indexOf(ly.col);
      h += `<div class="lin-layer lin-layer-${ly.id}" style="left:${Math.round(i * lay.colW)}px;width:${lay.boxW}px" tabindex="0" data-tooltip="${esc(ly.label + '\n' + ly.tip)}">${esc(ly.label)}</div>`;
    });
    h += `</div><div class="lin-heads" style="width:${lay.width}px">`;
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
      const ly = m.LAYERS.find(x => x.col === c && x.label !== m.COL_LABEL[c]);
      const tag = ly ? ` <span class="lin-layer-tag" tabindex="0" data-tooltip="${esc(ly.label + '\n' + ly.tip)}">${esc(ly.label)}</span>` : '';
      h += `<section class="lin-list-col"><h4>${esc(m.COL_LABEL[c])}${tag}</h4><ul class="lin-list">`;
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
      const rows = ctx.rows ? (ctx.rows[t.name] == null ? '-' : `${Number(ctx.rows[t.name]).toLocaleString('ko-KR')}행`) : '운영 정보 없음';
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
        body += `<dt>채우는 방법</dt><dd>${esc(t.manual_note || '정기 작업 없이 직접 채운 표입니다.')}</dd>`;
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
      if (m.hoursText(j.stale_hours)) body += `<dt>기준 시간</dt><dd>${esc(m.hoursText(j.stale_hours))} 넘게 갱신이 없으면 오래됨으로 봅니다.</dd>`;
      body += `<dt>마지막 실행</dt><dd>${st ? (st.items.length ? `<ul>${st.items.map(it => statusLine(lin, it)).join('')}</ul>` : '-') : '운영 정보 없음'}</dd>`;
      body += `<dt>단계</dt><dd>${listOrDash(steps)}</dd>`;
      body += `<dt>원천</dt><dd>${listOrDash(ins.map(id => `<li>${esc(label(id))}</li>`))}</dd>`;
      body += `<dt>쓰는 표</dt><dd>${listOrDash(outs.map(id => `<li><code>${esc(label(id))}</code></li>`))}</dd>`;
      body += '</dl>';
    } else if (node.kind === 'source') {
      const s = node.ref;
      body += '<dl class="lin-dl">';
      body += `<dt>주소</dt><dd>${/^https?:\/\//i.test(s.url) ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a>` : (s.url ? esc(s.url) : '-')}</dd>`;
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
    const dataBtn = node.kind === 'collected' || node.kind === 'derived' || node.kind === 'manual'
      ? `<button type="button" class="lin-close" data-show-table="${esc(node.ref.name)}">데이터 보기</button>`
      : '';
    return `<div class="card-header"><h3 class="card-title">${title}</h3>`
      + `<span class="lin-actions">${dataBtn}<button type="button" class="lin-close" data-close="1">닫기</button></span></div>`
      + `<div class="card-body">${body}</div>`;
  }

  // ===== 화면(브라우저에서만) =====

  const S = {
    lin: null, rows: null, details: null, linError: null, opsErrors: [],
    graph: null, status: null, sel: null, filter: null, manualOpen: false,
    loading: null, width: 0, mobile: false,
  };
  let tipHide = function () {};

  function $(id) { return document.getElementById(id); }

  let linOnce = null;
  /**
   * 계보 파일을 한 번만 받습니다. 데이터 탐색 탭의 수집 일정 표(schedule.js)도 이것을 씁니다.
   * 반환 Promise<{ ok, data } | { ok: false, error }>
   */
  function loadLineage() {
    if (!linOnce) linOnce = root.TeamStats.data.getJson('../data/table_lineage.json', 'tables');
    return linOnce;
  }

  /** 계보 파일과 운영 정보 두 가지(행 수·실행 기록)를 받습니다. 실패는 이유를 남깁니다. */
  async function load() {
    const D = root.TeamStats.data;
    const base = root.KBO_API_BASE;
    const res = await Promise.all([
      loadLineage(),
      D.getJson(`${base}/db/tables`, 'tables'),
      D.getJson(`${base}/jobs/status`, null),
    ]);
    if (res[0].ok) S.lin = res[0].data;
    else S.linError = res[0].error;
    // 운영 정보를 다루다 난 오류는 계보 그림을 가리지 않고 알림으로만 남깁니다.
    try {
      if (res[1].ok) {
        const rows = {};
        res[1].data.tables.forEach(t => { rows[t.name] = t.rows; });
        S.rows = rows;
      } else {
        S.opsErrors.push(`행 수: ${res[1].error}`);
      }
    } catch (e) {
      S.rows = null;
      S.opsErrors.push(`행 수: ${(e && e.message) || e}`);
    }
    try {
      const det = res[2].ok ? res[2].data.details : null;
      if (det && typeof det === 'object' && !Array.isArray(det)) {
        if (Object.keys(det).length) S.details = det;
        else S.opsErrors.push('실행 기록: details 가 비어 있습니다');
      } else {
        S.opsErrors.push(`실행 기록: ${res[2].ok ? 'details 가 없습니다' : res[2].error}`);
      }
    } catch (e) {
      S.details = null;
      S.opsErrors.push(`실행 기록: ${(e && e.message) || e}`);
    }
  }

  /** 지금 상태로 그림 전체를 다시 그립니다(데이터를 다시 받지 않음). */
  function render(refocus) {
    const box = $('lin-graph');
    if (!box) return;
    tipHide();
    if (S.linError || !S.lin) {
      $('lin-alerts').innerHTML = '';
      $('lin-summary').innerHTML = '';
      $('lin-detail').classList.add('hidden');
      box.innerHTML = `<div class="lin-alert">계보 자료를 불러오지 못했습니다 (${esc(S.linError || '빈 응답')}).</div>`;
      return;
    }
    const m = M();
    S.graph = m.buildGraph(S.lin, { manualOpen: S.manualOpen });
    if (S.sel && !S.graph.nodes[S.sel]) S.sel = null;
    try {
      S.status = statusMap(S.lin, S.details, Date.now());
      S.opsErrors = S.opsErrors.filter(x => x.indexOf('상태 계산:') !== 0);
    } catch (e) {
      console.error(e);
      S.status = null;
      const msg = `상태 계산: ${(e && e.message) || e}`;
      if (S.opsErrors.indexOf(msg) < 0) S.opsErrors.push(msg);
    }
    if (!S.status) S.filter = null;
    S.mobile = root.matchMedia('(max-width: 640px)').matches;
    S.width = box.clientWidth;
    $('lin-alerts').innerHTML = S.opsErrors.length
      ? `<div class="lin-alert">운영 정보 일부를 불러오지 못했습니다 (${esc(S.opsErrors.join(' / '))}). 받지 못한 정보(상태 점·행 수)는 감춥니다.</div>`
      : '';
    box.innerHTML = S.mobile
      ? listHtml(S.graph, S.lin, S.status)
      : graphHtml(S.graph, m.layout(S.graph, S.width), S.lin, S.status);
    applyFocus(refocus);
  }

  /** 누른 상자·요약 숫자에 맞춰 진하게/흐리게와 상세 카드를 바꿉니다. */
  function applyFocus(refocus) {
    tipHide();
    const box = $('lin-graph');
    let on = null, onEdges = null;
    if (S.sel) {
      const r = M().reach(S.graph, S.lin, S.sel);
      on = r.nodes;
      onEdges = r.edges;
    } else if (S.filter && S.status) {
      const by = S.status.sum.byTable;
      on = new Set(Object.keys(by).filter(n => by[n] === S.filter).map(n => 'table:' + n));
      onEdges = new Set();
    }
    const focus = !!on;
    box.classList.toggle('lin-focus', focus);
    box.querySelectorAll('.lin-box[data-id]').forEach(b => b.classList.toggle('on', focus && on.has(b.dataset.id)));
    box.querySelectorAll('.lin-edge').forEach(p => p.classList.toggle('on', focus && onEdges.has(Number(p.dataset.i))));
    $('lin-summary').innerHTML = summaryHtml(S.status && S.status.sum, S.filter, S.lin);
    const card = $('lin-detail');
    if (S.sel) {
      card.innerHTML = detailHtml(S.graph.nodes[S.sel], S.lin, { graph: S.graph, status: S.status, rows: S.rows });
      card.classList.remove('hidden');
    } else {
      card.classList.add('hidden');
      card.innerHTML = '';
    }
    if (refocus) {
      const el = document.querySelector(refocus);
      if (el) el.focus({ preventScroll: true });
    }
  }

  /** 설명 글 두 개를 줄바꿈으로 잇습니다(비면 건너뜀). 키보드 포커스 때 상자 설명에 점 설명을 덧붙입니다. */
  function joinTips(a, b) {
    return [a, b].filter(Boolean).join('\n');
  }

  /**
   * 설명 창 안 HTML 입니다. 두 줄 이상이면 공용 툴팁(js/chart-tip.js·선수 통계 표 툴팁)과 같게
   * 첫 줄 제목(굵게)·둘째 줄 내용·셋째 줄부터 흐린 글씨, 한 줄이면 그대로 둡니다.
   */
  function tipHtml(text) {
    const lines = String(text == null ? '' : text).split('\n').filter(s => s !== '');
    if (lines.length < 2) return esc(lines[0] || '');
    return lines.map((s, i) => i === 0 ? `<b>${esc(s)}</b>` : `<span${i >= 2 ? ' class="f"' : ''}>${esc(s)}</span>`).join('');
  }

  function bindTips(scope) {
    let box = null;
    function hide() { if (box) box.style.display = 'none'; }
    tipHide = hide;
    root.addEventListener('scroll', hide, { passive: true });
    $('lin-graph').addEventListener('scroll', hide, { passive: true });
    function show(el, text) {
      if (!box) {
        box = document.createElement('div');
        box.className = 'lin-tip';
        document.body.appendChild(box);
      }
      box.innerHTML = tipHtml(text);
      box.style.display = 'block';
      const r = el.getBoundingClientRect();
      box.style.left = Math.max(8, Math.min(r.left, root.innerWidth - box.offsetWidth - 12)) + 'px';
      const below = r.bottom + 6;
      box.style.top = (below + box.offsetHeight > root.innerHeight ? Math.max(8, r.top - box.offsetHeight - 6) : below) + 'px';
    }
    scope.addEventListener('mouseover', function (e) {
      const el = e.target.closest && e.target.closest('[data-tooltip]');
      if (!el || !scope.contains(el)) return;
      show(el, el.getAttribute('data-tooltip'));
    });
    scope.addEventListener('focusin', function (e) {
      const el = e.target.closest && e.target.closest('.lin-box[data-tooltip], .lin-sum-btn[data-tooltip], .lin-sum-manual[data-tooltip], .lin-layer[data-tooltip], .lin-layer-tag[data-tooltip]');
      if (!el || !scope.contains(el)) return;
      try { if (!el.matches(':focus-visible')) return; } catch (err) { /* :focus-visible 미지원이면 그대로 보임 */ }
      const mark = el.querySelector('.lin-dot[data-tooltip], .lin-tag[data-tooltip]');
      show(el, joinTips(el.getAttribute('data-tooltip'), mark && mark.getAttribute('data-tooltip')));
    });
    scope.addEventListener('focusout', function (e) {
      if (e.target.closest && e.target.closest('.lin-box, .lin-sum-btn, .lin-sum-manual, .lin-layer, .lin-layer-tag')) hide();
    });
    scope.addEventListener('mouseout', function (e) {
      if (e.target.closest && e.target.closest('[data-tooltip]')) hide();
    });
  }

  function bind() {
    const tab = $('tab-lineage');
    tab.addEventListener('click', function (e) {
      const sum = e.target.closest('.lin-sum-btn');
      if (sum) {
        const k = sum.dataset.state;
        S.sel = null;
        S.filter = S.filter === k ? null : k;
        applyFocus(`.lin-sum-btn[data-state="${k}"]`);
        return;
      }
      // 표 상세 카드의 '데이터 보기': 페이지(database-explorer.html)가 받아 데이터 탐색 탭에서 그 표를 엽니다.
      const show = e.target.closest('[data-show-table]');
      if (show) {
        root.dispatchEvent(new CustomEvent('lineage:show-table', { detail: { name: show.getAttribute('data-show-table') } }));
        return;
      }
      if (e.target.closest('[data-close]')) {
        S.sel = null;
        applyFocus();
        return;
      }
      const b = e.target.closest('.lin-box[data-id]');
      if (b) {
        const id = b.dataset.id;
        if (id === M().GROUP_ID) {
          S.manualOpen = !S.manualOpen;
          render(`.lin-box[data-id="${M().GROUP_ID}"]`);
          return;
        }
        S.filter = null;
        S.sel = S.sel === id ? null : id;
        applyFocus();
        if (S.sel && S.mobile) $('lin-detail').scrollIntoView({ block: 'nearest' });
        return;
      }
      // 그림의 빈 곳을 누르면 처음으로 돌아갑니다.
      if (e.target.closest('.lin-canvas')) {
        S.sel = null;
        S.filter = null;
        applyFocus();
      }
    });
    // 폭이 바뀌면(창 크기, 세로 스크롤바가 생겨 줄어듦 포함) 다시 그립니다.
    let t = null;
    function onResize() {
      clearTimeout(t);
      t = setTimeout(function () {
        const box = $('lin-graph');
        if (!box || !box.clientWidth) return;
        if (!S.lin) return;
        const mob = root.matchMedia('(max-width: 640px)').matches;
        if (mob !== S.mobile || (!mob && box.clientWidth !== S.width)) render();
      }, 150);
    }
    if (typeof root.ResizeObserver === 'function') new root.ResizeObserver(onResize).observe($('lin-graph'));
    else root.addEventListener('resize', onResize);
    bindTips(tab);
  }

  /** '계보에서 보기'로 연 표가 그림에 없을 때 알릴 문구입니다. 그림에 있으면 ''. */
  function missingTableNote(lin, id) {
    const name = String(id).replace(/^table:/, '');
    const t = ((lin && lin.tables) || []).find(x => x.name === name);
    if (!t) return `${name} 표는 아직 계보에 없습니다.`;
    if (t.kind === 'meta') return `${name} 표는 운영 기록 표라 계보 그림에 넣지 않습니다.`;
    return '';
  }

  /** 다른 탭에서 넘어올 때 표 하나를 고른 채 엽니다. 기준 표면 묶음을 펼칩니다. */
  function select(id) {
    const note = missingTableNote(S.lin, id);
    if (note) {
      S.sel = null;
      S.filter = null;
      render();
      // render 가 lin-alerts 를 다시 쓰므로 그 뒤에 붙입니다. 다음 render 때 사라집니다.
      $('lin-alerts').insertAdjacentHTML('beforeend', `<div class="lin-alert">${esc(note)}</div>`);
      return;
    }
    const t = S.lin.tables.find(x => 'table:' + x.name === id);
    if (t.kind === 'manual') S.manualOpen = true;
    S.filter = null;
    S.sel = id;
    render();
    const box = document.querySelector(`#lin-graph .lin-box[data-id="${root.CSS && root.CSS.escape ? root.CSS.escape(id) : id}"]`);
    if (box) box.scrollIntoView({ block: 'center', inline: 'center' });
  }

  /**
   * 탭을 열 때 부릅니다(database-explorer.html 의 switchTab). 처음이면 데이터를 받아
   * 그립니다. selectId('table:<이름>')를 주면 그 표를 고른 채 엽니다. 그 밖에 다시 열면
   * 그사이 폭이 바뀌었을 때만 다시 그립니다.
   */
  function open(selectId) {
    const first = !S.loading;
    if (first) {
      bind();
      $('lin-graph').innerHTML = typeof root.createLoadingSpinner === 'function' ? root.createLoadingSpinner() : '';
      S.loading = load().then(render).catch(function (e) {
        console.error(e);
        S.linError = String((e && e.message) || e);
        render();
      });
    }
    return S.loading.then(function () {
      if (selectId && S.lin) {
        select(selectId);
        return;
      }
      const box = $('lin-graph');
      if (!first && S.lin && box && box.clientWidth !== S.width) render();
    });
  }

  const api = { missingTableNote, esc, pageHref, statusMap, summaryHtml, graphHtml, listHtml, detailHtml, boxTip, joinTips, tipHtml, loadLineage, open, STATE_LABEL, SUM_TIP };
  L.view = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
