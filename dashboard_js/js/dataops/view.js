/*
 * 데이터 관리 화면 그리기입니다. 계산은 dataops/model.js 에 있습니다.
 * 네 가지를 따로 불러오고, 하나가 실패해도 나머지는 그립니다(설계 §5).
 *   /ops/storage, /jobs/status (Worker), ../data/table_lineage.json, ../data/source_history.json
 * api.js 는 쓰지 않습니다. 툴팁 모양은 bstats 공용(첫 줄 굵게, 둘째 보통, 셋째부터 흐림).
 */
(function () {
  'use strict';
  const M = window.DataOps.model;
  const L = window.Lineage.model;
  const API = window.KBO_API_BASE;
  const STATE = { ok: ['정상', 'ok'], stale: ['오래됨', 'warn'], fail: ['실패', 'bad'], none: ['기록 없음', 'none'] };

  function esc(s) {
    return String(s === null || s === undefined ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  }
  function tip() { return ' tabindex="0" data-tip="' + esc(Array.from(arguments).join('\n')) + '"'; }
  function num(n) { return n === null || n === undefined ? '-' : Number(n).toLocaleString('ko-KR'); }
  function $(id) { return document.getElementById(id); }
  function getJson(url) { return fetch(url).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }); }
  function fail(id, what) { $(id).innerHTML = '<p class="ops-msg">' + esc(what) + '을(를) 불러오지 못했습니다.</p>'; }

  // ---- 저장소 ----
  function cmpChip(c) {
    if (c.kind === 'same') return '<span class="chip same">같음</span>';
    if (c.kind === 'diff') return '<span class="chip diff">차이 ' + (c.diff > 0 ? '+' : '') + num(c.diff) + '행</span>';
    if (c.kind === 'fail') return '<span class="chip bad">복사 실패</span>';
    if (c.kind === 'missing') return '<span class="chip none">빅쿼리에 없음</span>';
    return '<span class="chip none">정보 없음</span>';
  }
  function storageRow(r, maxBytes, folded) {
    const t = tip(r.name,
      (r.category || '분류 없음') + ' · MySQL ' + num(r.rows) + '행 · 빅쿼리 ' + (r.bq ? num(r.bq.rows) + '행' : '-'),
      'MySQL 용량 ' + M.fmtBytes(r.bytes) + ' = 데이터 ' + M.fmtBytes(r.data_bytes) + ' + 인덱스 ' + M.fmtBytes(r.index_bytes),
      '행 수 갱신 ' + (r.rows_updated_at || '-') + ' · 빅쿼리 마지막 성공 ' + ((r.bq && r.bq.last_ok_at) || '-'),
      '차이 = MySQL 행 수 − 빅쿼리 행 수. 빅쿼리는 주 1회 사본입니다.');
    const w = Math.max(r.bytes / (maxBytes || 1) * 100, 0.6).toFixed(1);
    return '<tr' + t + (folded ? ' class="fold"' : '') + '><th scope="row"><code>' + esc(r.name) + '</code></th>'
      + '<td class="cat">' + esc(r.category || '-') + '</td><td>' + num(r.rows) + '</td>'
      + '<td class="szc"><span class="sz">' + M.fmtBytes(r.bytes) + '</span><span class="szbar"><span style="width:' + w + '%"></span></span></td>'
      + '<td>' + (r.bq ? num(r.bq.rows) : '-') + '</td><td>' + (r.bq ? M.fmtBytes(r.bq.bytes) : '-') + '</td>'
      + '<td>' + cmpChip(r.cmp) + '</td></tr>';
  }
  function renderStorage(storage) {
    const rows = M.storageRows(storage);
    const s = M.storageSummary(storage, rows);
    const maxBytes = rows.length ? rows[0].bytes : 1;
    const parts = M.splitFold(rows);
    $('ops-st-body').innerHTML = parts.top.map(r => storageRow(r, maxBytes, false)).join('')
      + parts.rest.map(r => storageRow(r, maxBytes, true)).join('');
    $('ops-st-total').innerHTML = '<th scope="row">합계</th><td></td><td>' + num(s.totalRows) + '</td><td>'
      + M.fmtBytes(s.totalBytes) + '</td><td></td><td>' + (s.bqBytes === null ? '-' : M.fmtBytes(s.bqBytes)) + '</td><td></td>';
    $('ops-st-sub').textContent = 'MySQL 용량이 큰 표부터 ' + parts.top.length + '개 · 합계는 전체 ' + rows.length
      + '개 기준 · 빅쿼리 마지막 복사 ' + (s.lastCopyAt || '정보 없음');
    const btn = $('ops-st-fold');
    if (parts.rest.length) {
      btn.hidden = false;
      const label = () => ($('ops-st').classList.contains('open') ? '용량 큰 ' + parts.top.length + '개만 보기' : '나머지 ' + parts.rest.length + '개 표 보기');
      btn.textContent = label();
      btn.onclick = () => { $('ops-st').classList.toggle('open'); btn.textContent = label(); };
    }
    $('ops-t-my').innerHTML = num(s.totalRows) + '<small>행</small>';
    $('ops-t-my-f').textContent = '표 ' + s.tableCount + '개 · 용량 약 ' + M.fmtBytes(s.totalBytes);
    if (storage.bigquery) {
      $('ops-t-bq').innerHTML = s.same + '<small>/ ' + s.tableCount + ' 표 같음</small>';
      $('ops-t-bq-f').textContent = '마지막 복사 ' + (s.lastCopyAt || '-') + ' · 용량 약 ' + M.fmtBytes(s.bqBytes);
    } else {
      $('ops-t-bq').innerHTML = '-';
      $('ops-t-bq-f').textContent = '빅쿼리 정보 없음';
    }
  }

  // ---- 수집 작업 ----
  // 계보의 멈춤 사유에서 괄호 속 바깥 사이트 주소를 뺍니다(공개 화면에 주소를 싣지 않음).
  function stopReason(lin) {
    return String(L.stoppedReason(lin) || '').replace(/\s*\([a-z0-9.-]+\.(com|net|kr|org)\)/gi, '');
  }
  function renderJobs(lin, details) {
    const cards = M.jobCards(lin, details, Date.now(), L.jobStatus);
    $('ops-jobs').innerHTML = cards.map(function (c) {
      const lis = c.items.map(function (it) {
        const st = c.stopped ? ['멈춤', 'stop'] : (STATE[it.state] || STATE.none);
        // 멈춘 작업은 시각을 보이지 않습니다. 같은 기록 키를 다른 작업이 함께 써서
        // (예: add_new_players 는 daily 와 멈춘 roster 가 같이 씀) 남의 실행 시각이 섞이기 때문입니다.
        const t = tip(it.step + ' · ' + it.key, c.stopped ? st[0] : st[0] + ' · 마지막 실행 ' + (it.at || '-'),
          c.stopped ? '' : (it.note ? '메모: ' + it.note : ''),
          c.stopped ? stopReason(lin) : '오래됨 기준: 마지막 실행 뒤 ' + c.staleHours + '시간이 지나면 오래됨으로 봅니다.');
        return '<li' + t + '><span class="dot ' + st[1] + '"></span><span class="sn">' + esc(it.step)
          + '</span><span class="sw">' + esc(c.stopped ? '멈춤' : (it.at ? it.at.slice(5) : '-')) + '</span></li>';
      }).join('');
      return '<div class="job' + (c.stopped ? ' stopped' : '') + '"><div class="jh"><b>' + esc(c.id) + '</b>'
        + (c.stopped ? '<span class="chip stop">예약 멈춤</span>' : '') + '<span class="js">' + esc(c.schedule) + '</span></div>'
        + '<ul>' + lis + '</ul></div>';
    }).join('');
    const n = M.jobCounts(cards);
    $('ops-t-job').innerHTML = n.ok + '<small>/ ' + n.run + ' 정상</small>';
    $('ops-t-job-f').textContent = '확인 필요 ' + n.warn + ' · 예약 멈춤 ' + n.stopped;
  }

  // ---- 출처·이력 ----
  function renderSources(lin) {
    const cards = M.sourceCards(lin, L.sourceStopped);
    const off = cards.filter(c => c.stopped).length;
    $('ops-src').innerHTML = cards.map(function (c) {
      const t = tip(c.name, (c.stopped ? '수집 중단' : '사용 중') + ' · ' + c.host,
        '이 출처를 쓰는 수집 스크립트: ' + (c.scripts.join(', ') || '없음(API 가 그때그때 읽음)'),
        "상태 규칙: 이 출처를 쓰는 수집 스크립트가 모두 멈췄으면 '수집 중단'입니다(계보 파일 기준).");
      return '<div class="src' + (c.stopped ? ' off' : '') + '"' + t + '><div class="sh"><b>' + esc(c.name) + '</b>'
        + (c.stopped ? '<span class="chip stop">수집 중단</span>' : '<span class="chip ok">사용 중</span>')
        + '</div><div class="sm">' + esc(c.host) + ' · 스크립트 ' + c.scripts.length + '개</div></div>';
    }).join('');
    $('ops-src-sub').textContent = '사용 중 ' + (cards.length - off) + ' · 수집 중단 ' + off;
    $('ops-t-src').innerHTML = (cards.length - off) + '<small>사용 중</small>';
    $('ops-t-src-f').textContent = '수집 중단 ' + off;
  }
  function renderHistory(hist) {
    const KIND = { '중단': 'bad', '대체': 'ok', '재개': 'ok', '알림': 'none' };
    $('ops-hist').innerHTML = M.historyEvents(hist).map(e =>
      '<li><span class="hd">' + esc(e.date) + '</span><span class="chip ' + (KIND[e.kind] || 'none') + '">' + esc(e.kind)
      + '</span><div class="hb"><b>' + esc(e.what) + '</b><p>' + esc(e.detail || '') + '</p><p class="why">이유: '
      + esc(e.reason) + '</p></div></li>').join('');
  }

  // ---- 툴팁 ----
  function renderTip(text) {
    return text.split('\n').filter(Boolean).map((l, i) =>
      '<div class="' + (i === 0 ? 'l1' : i === 1 ? 'l2' : 'lx') + '">' + esc(l) + '</div>').join('');
  }
  let cur = null;
  function hide() { if (cur) { cur.remove(); cur = null; } }
  function show(el) {
    hide();
    const t = document.createElement('div');
    t.className = 'tip';
    t.setAttribute('role', 'tooltip');
    t.innerHTML = renderTip(el.getAttribute('data-tip'));
    document.body.appendChild(t);
    const r = el.getBoundingClientRect();
    const x = Math.max(8, Math.min(r.left + r.width / 2 - t.offsetWidth / 2, innerWidth - t.offsetWidth - 8));
    let y = r.top - t.offsetHeight - 8;
    if (y < 8) y = r.bottom + 8;
    t.style.left = x + 'px';
    t.style.top = y + 'px';
    cur = t;
  }
  document.addEventListener('mouseover', e => { const el = e.target.closest('[data-tip]'); if (el) show(el); else hide(); });
  document.addEventListener('focusin', e => { const el = e.target.closest('[data-tip]'); if (el) show(el); });
  document.addEventListener('focusout', hide);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') hide(); });
  addEventListener('scroll', hide, true);

  // ---- 불러오기 ----
  const lin = getJson('../data/table_lineage.json');
  getJson(API + '/ops/storage').then(renderStorage).catch(() => {
    fail('ops-st-msg', '저장소 현황');
    $('ops-t-my').textContent = '-';
    $('ops-t-bq').textContent = '-';
  });
  Promise.all([lin, getJson(API + '/jobs/status')])
    .then(([l, js]) => renderJobs(l, js.details || {}))
    .catch(() => fail('ops-jobs', '수집 작업 상태'));
  lin.then(renderSources).catch(() => fail('ops-src', '출처'));
  getJson('../data/source_history.json').then(renderHistory).catch(() => fail('ops-hist', '수집 중단 이력'));
})();
