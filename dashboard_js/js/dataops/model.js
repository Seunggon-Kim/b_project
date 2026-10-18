/*
 * 데이터 관리 화면 계산입니다. 화면(DOM)에는 손대지 않습니다.
 *
 * 브라우저에서는 window.DataOps.model, 시험(test/dataops_model.test.js)에서는 vm 으로
 * 불러 씁니다. 수집 상태와 출처 멈춤 판정은 계보 화면의 함수(window.Lineage.model 의
 * jobStatus·sourceStopped)를 인자로 받아 씁니다. 같은 규칙을 두 번 쓰지 않으려는 것입니다.
 * 설계: docs/superpowers/specs/2026-10-18-data-ops-tab-design.md §5
 */
(function (root) {
  'use strict';
  const D = root.DataOps = root.DataOps || {};
  const FOLD = 10;

  function fmtBytes(n) {
    if (n === null || n === undefined || !Number.isFinite(Number(n))) return '-';
    const v = Number(n);
    if (v >= 1e9) return (v / 1e9).toFixed(2) + ' GB';
    if (v >= 1e6) return (v / 1e6).toFixed(1) + ' MB';
    return Math.round(v / 1e3) + ' KB';
  }

  /** MySQL 행 수와 빅쿼리 사본을 견줍니다. 해석은 붙이지 않습니다. */
  function compare(my, bq, hasBq) {
    if (!hasBq) return { kind: 'unknown', diff: null };
    if (!bq) return { kind: 'missing', diff: null };
    if (bq.status !== 'ok') return { kind: 'fail', diff: null };
    const diff = (my.rows || 0) - (bq.rows || 0);
    return diff === 0 ? { kind: 'same', diff: 0 } : { kind: 'diff', diff: diff };
  }

  function storageRows(storage) {
    const hasBq = !!(storage && storage.bigquery);
    const bq = new Map(((hasBq && storage.bigquery.tables) || []).map(t => [t.name, t]));
    return ((storage && storage.mysql && storage.mysql.tables) || []).map(function (t) {
      const b = bq.get(t.name);
      return Object.assign({}, t, {
        bytes: (t.data_bytes || 0) + (t.index_bytes || 0),
        bq: b || null,
        cmp: compare(t, b, hasBq),
      });
    });
  }

  function splitFold(rows, n) {
    const k = n === undefined ? FOLD : n;
    return { top: rows.slice(0, k), rest: rows.slice(k) };
  }

  function storageSummary(storage, rows) {
    const bq = storage && storage.bigquery;
    return {
      totalRows: storage.mysql.total_rows,
      totalBytes: storage.mysql.total_bytes,
      tableCount: rows.length,
      same: rows.filter(r => r.cmp.kind === 'same').length,
      bqBytes: bq ? bq.tables.reduce((s, t) => s + (t.bytes || 0), 0) : null,
      lastCopyAt: bq ? bq.last_copy_at : null,
    };
  }

  /** 바깥 사이트 주소는 화면에 쓰지 않고 이름만 씁니다. */
  function hostName(url) {
    const u = String(url || '');
    if (/naver\.com/.test(u)) return '네이버 스포츠';
    if (/koreabaseball\.com/.test(u)) return 'KBO 공식 사이트';
    return '바깥 사이트';
  }

  function sourceCards(lin, sourceStopped) {
    return ((lin && lin.sources) || []).map(function (s) {
      const scripts = ((lin.scripts) || []).filter(x => (x.sources || []).includes(s.id))
        .map(x => String(x.path).split('/').pop()).sort();
      return { id: s.id, name: s.name, host: hostName(s.url), stopped: !!sourceStopped(lin, s.id), scripts: scripts };
    });
  }

  function jobCards(lin, details, nowMs, jobStatus) {
    return ((lin && lin.jobs) || []).map(function (j) {
      const st = jobStatus(lin, j, details, nowMs);
      return { id: j.id, schedule: j.schedule_kst, stopped: !!j.stopped, staleHours: j.stale_hours,
        state: st.state, items: st.items };
    });
  }

  function jobCounts(cards) {
    const out = { ok: 0, run: 0, warn: 0, stopped: 0 };
    cards.forEach(function (c) {
      c.items.forEach(function (it) {
        if (c.stopped) { out.stopped += 1; return; }
        out.run += 1;
        if (it.state === 'ok') out.ok += 1; else out.warn += 1;
      });
    });
    return out;
  }

  function historyEvents(hist) {
    const ev = ((hist && hist.events) || []).map((e, i) => ({ e: e, i: i }));
    ev.sort((a, b) => (a.e.date < b.e.date ? 1 : a.e.date > b.e.date ? -1 : a.i - b.i));
    return ev.map(x => x.e);
  }

  const api = { FOLD, fmtBytes, compare, storageRows, splitFold, storageSummary, hostName,
    sourceCards, jobCards, jobCounts, historyEvents };
  D.model = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
