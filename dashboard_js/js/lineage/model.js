/*
 * 테이블 계보 계산입니다. 화면(DOM)에는 손대지 않습니다.
 *
 * 브라우저에서는 window.Lineage.model 로, Node 검증 스크립트에서는 vm 으로
 * 불러 씁니다. 근거는 docs/superpowers/specs/2026-10-04-table-lineage-screen-design.md
 * 입니다. 데이터는 dashboard_js/data/table_lineage.json(DB 세션 생성물)입니다.
 */
(function (root) {
  'use strict';
  const L = root.Lineage = root.Lineage || {};

  // 그림의 칸 순서입니다.
  const COLS = ['source', 'job', 'table', 'derived', 'page'];
  const COL_LABEL = { source: '원천', job: '수집 작업', table: '표', derived: '계산 표', page: '화면' };
  // 칸 위 층 띠입니다(evan 결정 2026-10-04, 설계 §3-1). 칸 이름은 그대로 두고 층에 해당하는 칸 위에만 그립니다.
  // 경계: 우리 공식으로 계산했으면 마트, 받은 것을 정리만 했으면 웨어하우스입니다(games·players 는 웨어하우스).
  const LAYERS = [
    { id: 'source', col: 'source', label: '원천', tip: '데이터를 받아 오는 바깥 사이트입니다(KBO 기록실, 네이버 중계 등). 우리 데이터베이스 밖에 있습니다.' },
    { id: 'dw', col: 'table', label: '데이터 웨어하우스', tip: '원천에서 받아 온 그대로이거나 정리만 한 표와, 손으로 관리하는 기준표(팀·구장 등)입니다. 우리 공식으로 계산하지 않은 표는 여기에 둡니다.' },
    { id: 'mart', col: 'derived', label: '데이터 마트', tip: '웨어하우스 표로 우리 공식(wOBA 가중치, wRC+, RE24, 파크팩터 등)을 계산해 저장한 표입니다. 화면 숫자 가운데 많은 수는 저장된 표 없이 API 주소가 웨어하우스 표를 바로 계산해 만들므로 이 칸에 다 나오지는 않습니다.' },
  ];
  const GROUP_ID = 'group:manual';

  function nodeType(id) { return String(id).slice(0, String(id).indexOf(':')); }
  function nodeName(id) { return String(id).slice(String(id).indexOf(':') + 1); }
  function byName(a, b) { return a < b ? -1 : a > b ? 1 : 0; }

  /** 화면 제목에서 ' - Bstats' 꼬리를 뗍니다. 제목이 없으면 경로입니다. */
  function pageLabel(p) {
    return String((p && (p.title || p.path)) || '').replace(/\s*-\s*Bstats\s*$/, '');
  }

  /**
   * 그림에 쓸 노드와 선입니다.
   *   opts.manualOpen  손 작업 표를 펼쳤으면 true
   * 반환 { cols: {source:[], job:[], table:[], derived:[], page:[]}, nodes: {id: node}, edges: [{from, to}] }
   *   node = { id, col, label, sub, kind, ref }   ref 는 계보 파일의 원래 항목
   * 숨김: kind 'meta' 표, explorer 페이지. 손 작업 표가 접혀 있으면 묶음 노드 하나로 바꾸고,
   * 펼쳐 있으면 묶음 노드(접기)를 맨 위에 두고 손 작업 표를 그 아래에 둡니다.
   */
  function buildGraph(lin, opts) {
    opts = opts || {};
    const cols = { source: [], job: [], table: [], derived: [], page: [] };
    const nodes = {};
    const add = function (n) { nodes[n.id] = n; cols[n.col].push(n); };
    const alias = {};   // 원래 id → 그림 id (접힌 손 작업 표 → 묶음)

    (lin.sources || []).slice().sort((a, b) => byName(a.id, b.id)).forEach(function (s) {
      add({ id: 'source:' + s.id, col: 'source', label: s.name, sub: '', kind: 'source', ref: s });
    });
    (lin.jobs || []).slice().sort((a, b) => byName(a.id, b.id)).forEach(function (j) {
      add({ id: 'job:' + j.id, col: 'job', label: j.id, sub: j.schedule_kst || '', kind: 'job', ref: j });
    });
    const tables = (lin.tables || []).slice().sort((a, b) => byName(a.name, b.name));
    tables.filter(t => t.kind === 'collected').forEach(function (t) {
      add({ id: 'table:' + t.name, col: 'table', label: t.name, sub: '', kind: 'collected', ref: t });
    });
    // 손 작업 표 묶음 상자는 접었을 때 '펼치기', 펼쳤을 때 '접기' 로 늘 둡니다(다시 접을 수 있게).
    const manual = tables.filter(t => t.kind === 'manual');
    if (manual.length) {
      add({ id: GROUP_ID, col: 'table', label: `손 작업 표 ${manual.length}개`, sub: opts.manualOpen ? '접기' : '펼치기', kind: 'group', ref: { members: manual.map(t => t.name) } });
    }
    manual.forEach(function (t) {
      if (opts.manualOpen) add({ id: 'table:' + t.name, col: 'table', label: t.name, sub: '', kind: 'manual', ref: t });
      else alias['table:' + t.name] = GROUP_ID;
    });
    tables.filter(t => t.kind === 'derived').forEach(function (t) {
      add({ id: 'table:' + t.name, col: 'derived', label: t.name, sub: '', kind: 'derived', ref: t });
    });
    (lin.pages || []).filter(p => !p.explorer).slice().sort((a, b) => byName(a.path, b.path)).forEach(function (p) {
      add({ id: 'page:' + p.path, col: 'page', label: pageLabel(p), sub: p.path, kind: 'page', ref: p });
    });

    const seen = new Set();
    const edges = [];
    (lin.edges || []).forEach(function (e) {
      const from = alias[e.from] || e.from;
      const to = alias[e.to] || e.to;
      if (!nodes[from] || !nodes[to] || from === to) return;
      const k = from + '>' + to;
      if (seen.has(k)) return;
      seen.add(k);
      edges.push({ from: from, to: to });
    });
    return { cols: cols, nodes: nodes, edges: edges };
  }

  /** 작업 job 에서 표 table 을 쓰는 스크립트들이 받는 원천 id 집합입니다. */
  function sourcesFor(lin, tableId, jobId) {
    const t = nodeName(tableId), j = nodeName(jobId);
    const out = new Set();
    (lin.scripts || []).forEach(function (s) {
      if ((s.writes || []).includes(t) && (s.jobs || []).includes(j)) {
        (s.sources || []).forEach(src => out.add('source:' + src));
      }
    });
    return out;
  }

  /** 작업 job 에서 원천 source 를 받는 스크립트들이 쓰는 표 id 집합입니다. */
  function tablesFor(lin, sourceId, jobId) {
    const src = nodeName(sourceId), j = nodeName(jobId);
    const out = new Set();
    (lin.scripts || []).forEach(function (s) {
      if ((s.sources || []).includes(src) && (s.jobs || []).includes(j)) {
        (s.writes || []).forEach(w => out.add('table:' + w));
      }
    });
    return out;
  }

  /**
   * 누른 노드에서 선을 따라 앞으로·뒤로 끝까지 이어진 노드와 선입니다.
   *
   * 원천 → 작업 → 표 구간은 스크립트 단위로 좁힙니다. 작업 하나가 여러 원천에서
   * 여러 표를 받으므로 선만 따라가면 games 를 눌렀을 때 퓨처스 원천까지 켜집니다.
   * 그래서 표에서 작업으로 거슬러 가면 그 표를 쓰는 스크립트의 원천만, 원천에서
   * 작업으로 내려가면 그 원천을 받는 스크립트가 쓰는 표만 따라갑니다. 작업 자체를
   * 누르면 그 작업의 원천과 표를 모두 켭니다. 스크립트에 원천이 적혀 있지 않으면 좁히지 않습니다.
   * 반환 { nodes: Set(id), edges: Set(선 번호) }
   */
  function reach(graph, lin, startId) {
    const edges = graph.edges;
    const nodes = new Set([startId]);
    const used = new Set();
    function walk(dir) {
      const todo = [{ id: startId, allow: null }];
      const seen = new Set();
      while (todo.length) {
        const cur = todo.pop();
        const key = cur.id + '|' + (cur.allow ? [...cur.allow].sort().join(',') : '*');
        if (seen.has(key)) continue;
        seen.add(key);
        edges.forEach(function (e, i) {
          const a = dir === 'down' ? e.from : e.to;
          const b = dir === 'down' ? e.to : e.from;
          if (a !== cur.id || (cur.allow && !cur.allow.has(b))) return;
          let allow = null;
          if (nodeType(b) === 'job' && dir === 'up' && nodeType(a) === 'table') allow = sourcesFor(lin, a, b);
          if (nodeType(b) === 'job' && dir === 'down' && nodeType(a) === 'source') allow = tablesFor(lin, a, b);
          // 스크립트가 원천을 적지 않았으면(예: sync_players_from_roster.py) 좁히지 않습니다. 빠뜨리는 것보다 넓게 보이는 편이 낫습니다.
          if (allow && !allow.size) allow = null;
          used.add(i);
          nodes.add(b);
          todo.push({ id: b, allow: allow });
        });
      }
    }
    walk('down');
    walk('up');
    return { nodes: nodes, edges: used };
  }

  // ===== 상태 =====

  // 나쁜 순서입니다. 숫자가 클수록 나쁩니다.
  const RANK = { ok: 0, none: 1, stale: 2, fail: 3 };

  /** 'YYYY-MM-DD HH:MM'(한국 시각) 글자를 ms 로 읽습니다. 못 읽으면 null. */
  function kstMs(s) {
    const m = String(s || '').match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
    if (!m) return null;
    return Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4] - 9, +m[5]);
  }

  /**
   * 기록 키 하나의 상태입니다. rec 는 /jobs/status 의 details[키](없으면 undefined).
   * 반환 { state: 'ok'|'fail'|'stale'|'none', at, status, note }
   *   - 실패: status 가 'fail'
   *   - 기록 없음: rec 가 없음
   *   - 오래됨: status 가 ok·skip 인데 last_run_at 이 staleHours 보다 오래됐거나 시각을 못 읽음,
   *            또는 화면이 모르는 status 값
   *   - 정상: status 가 ok·skip 이고 기준 시간 안
   */
  function keyState(rec, staleHours, nowMs) {
    if (!rec) return { state: 'none', at: null, status: null, note: null };
    const status = rec.status === null || rec.status === undefined ? '' : String(rec.status);
    const base = { at: rec.last_run_at || null, status: status, note: rec.note || null };
    if (status === 'fail') return Object.assign({ state: 'fail' }, base);
    if (status !== 'ok' && status !== 'skip') return Object.assign({ state: 'stale', unknown: true }, base);
    const at = kstMs(rec.last_run_at);
    const fresh = at !== null && nowMs - at <= staleHours * 3600 * 1000;
    return Object.assign({ state: fresh ? 'ok' : 'stale' }, base);
  }

  function worst(items) {
    if (!items.length) return 'none';
    return items.reduce((w, it) => (RANK[it.state] > RANK[w] ? it.state : w), 'ok');
  }

  function jobById(lin, id) { return (lin.jobs || []).find(j => j.id === id) || null; }
  function scriptByPath(lin, path) { return (lin.scripts || []).find(s => s.path === path) || null; }

  /**
   * 표의 상태입니다. 손 작업 표는 'manual'.
   * 반환 { state, items: [{ script, job, key, state, at, status, note, staleHours }] }
   * details 는 /jobs/status 의 details 객체입니다.
   */
  function tableStatus(lin, t, details, nowMs) {
    if (t.kind === 'manual') return { state: 'manual', items: [] };
    const items = [];
    (t.written_by || []).forEach(function (path) {
      const s = scriptByPath(lin, path);
      const keys = (s && s.status_keys) || {};
      Object.keys(keys).sort(byName).forEach(function (job) {
        const key = keys[job];
        if (!key) return;
        const j = jobById(lin, job);
        const staleHours = j ? j.stale_hours : 36;
        items.push(Object.assign({ script: path, job: job, key: key, staleHours: staleHours },
          keyState((details || {})[key], staleHours, nowMs)));
      });
    });
    return { state: worst(items), items: items };
  }

  /** 작업 상자의 상태입니다. 기록 키가 있는 단계만 봅니다(같은 키는 한 번). */
  function jobStatus(lin, job, details, nowMs) {
    const items = [];
    const seen = new Set();
    (job.steps || []).forEach(function (st) {
      const key = st.status_key;
      if (!key || seen.has(key)) return;
      seen.add(key);
      items.push(Object.assign({ step: st.name, script: st.script, job: job.id, key: key, staleHours: job.stale_hours },
        keyState((details || {})[key], job.stale_hours, nowMs)));
    });
    return { state: worst(items), items: items };
  }

  /** 요약 줄 숫자입니다. meta 를 빼고 셉니다. 반환 { ok, fail, stale, none, manual, byTable: {name: state} } */
  function summarize(lin, details, nowMs) {
    const out = { ok: 0, fail: 0, stale: 0, none: 0, manual: 0, byTable: {} };
    (lin.tables || []).forEach(function (t) {
      if (t.kind === 'meta') return;
      const st = tableStatus(lin, t, details, nowMs).state;
      out[st] += 1;
      out.byTable[t.name] = st;
    });
    return out;
  }

  /** 'YYYY-MM-DD HH:MM' → 'MM/DD HH:MM'. 못 읽으면 글자 그대로입니다. */
  function shortTime(s) {
    const m = String(s || '').match(/^\d{4}-(\d{2})-(\d{2})[ T](\d{2}:\d{2})/);
    return m ? `${m[1]}/${m[2]} ${m[3]}` : String(s || '');
  }

  const STATE_WORD = { ok: '성공', skip: '건너뜀', fail: '실패' };

  /** 기준 시간 글자입니다. 48시간 미만은 '36시간', 이상은 '8일'(나누어떨어지지 않으면 '7.5일'). */
  function hoursText(h) {
    if (h === null || h === undefined || h === '' || !isFinite(Number(h))) return '';
    h = Number(h);
    if (!(h >= 48)) return `${h}시간`;
    return `${Math.round(h / 24 * 10) / 10}일`;
  }

  /** 키 상태 하나를 사람이 읽는 문구로 바꿉니다. it 는 tableStatus/jobStatus 의 items 항목. */
  function itemText(lin, it) {
    if (it.state === 'none') return `${it.job} · ${it.key}: 실행 기록이 아직 없습니다`;
    if (it.state === 'fail') return `${it.job} · ${it.key}: 마지막 실행 실패 ${shortTime(it.at)}`;
    if (it.state === 'stale') {
      if (it.unknown) return `${it.job} · ${it.key}: 알 수 없는 상태(${it.status}) ${shortTime(it.at)}`;
      const j = jobById(lin, it.job);
      const ht = hoursText(it.staleHours);
      return `${it.job} · ${it.key}: ${ht ? ht + ' 넘게' : '기준 시간을 넘겨'} 갱신이 없습니다(기준: ${j ? j.schedule_kst : ''} 실행) · 마지막 ${shortTime(it.at)}`;
    }
    return `${it.job} · ${it.key}: 마지막 갱신 ${shortTime(it.at)} · ${STATE_WORD[it.status] || it.status}`;
  }

  /** 오래됨 기준 규칙 글자입니다. 같은 기준 시간끼리 작업 id 를 묶어 기준이 짧은 것부터 씁니다. */
  function staleRuleText(lin) {
    const groups = {};
    ((lin && lin.jobs) || []).forEach(j => {
      if (!hoursText(j.stale_hours)) return;
      (groups[Number(j.stale_hours)] = groups[Number(j.stale_hours)] || []).push(j.id);
    });
    return Object.keys(groups).map(Number).sort((a, b) => a - b)
      .map(h => `${groups[h].sort().join('·')} ${hoursText(h)}`).join(', ');
  }

  /** 점에 붙일 설명 문구입니다. st = tableStatus/jobStatus 결과. manualNote 는 손 작업 표 설명. */
  function dotText(lin, st, manualNote) {
    if (st.state === 'manual') return `손 작업으로 채운 표입니다${manualNote ? ': ' + manualNote : ''}`;
    if (!st.items.length) return '실행 기록이 아직 없습니다';
    return st.items.map(it => itemText(lin, it)).join('\n');
  }

  // ===== 배치 =====

  const BOX_H = 36;      // 상자 높이
  const GAP = 10;        // 상자 사이
  const HEAD = 0;        // 칸 제목은 그림 밖(HTML)에 둡니다
  const MIN_BOX_W = 150; // 상자 최소 폭
  const COL_PAD = 36;    // 칸 사이 여백(선이 지나갈 자리)
  const ARC = 26;        // 같은 칸 안 선이 오른쪽으로 부푸는 정도

  /**
   * 상자 좌표입니다. width = 그림을 그릴 폭(px).
   * 반환 { width, height, colW, boxW, boxes: {id: {x, y, w, h}} }
   * 칸이 좁으면 폭을 넓혀(가로로 밀어 볼 수 있게) 상자가 MIN_BOX_W 보다 좁아지지 않게 합니다.
   */
  function layout(graph, width) {
    const total = Math.max(Number(width) || 0, COLS.length * (MIN_BOX_W + COL_PAD));
    const colW = total / COLS.length;
    const boxW = colW - COL_PAD;
    const boxes = {};
    let rows = 0;
    COLS.forEach(function (c, ci) {
      graph.cols[c].forEach(function (n, ri) {
        boxes[n.id] = { x: Math.round(ci * colW), y: HEAD + ri * (BOX_H + GAP), w: Math.round(boxW), h: BOX_H };
      });
      rows = Math.max(rows, graph.cols[c].length);
    });
    const height = rows ? HEAD + rows * (BOX_H + GAP) - GAP : 0;
    return { width: Math.round(total), height: height, colW: colW, boxW: Math.round(boxW), boxes: boxes };
  }

  /**
   * 선 하나의 SVG path 글자입니다. 다른 칸이면 왼쪽 상자 오른쪽 가운데 → 오른쪽 상자
   * 왼쪽 가운데로 가는 3차 곡선, 같은 칸이면 두 상자 오른쪽을 잇는 오른쪽으로 부푼 곡선입니다.
   */
  function edgePath(lay, e) {
    const a = lay.boxes[e.from], b = lay.boxes[e.to];
    if (!a || !b) return '';
    const ay = a.y + a.h / 2, by = b.y + b.h / 2;
    if (a.x === b.x) {
      const x = a.x + a.w;
      return `M${x},${ay} C${x + ARC},${ay} ${x + ARC},${by} ${x},${by}`;
    }
    const x1 = a.x + a.w, x2 = b.x;
    const mid = (x1 + x2) / 2;
    return `M${x1},${ay} C${mid},${ay} ${mid},${by} ${x2},${by}`;
  }

  const api = {
    COLS, COL_LABEL, LAYERS, GROUP_ID, RANK, BOX_H, GAP, MIN_BOX_W, COL_PAD,
    nodeType, nodeName, pageLabel, buildGraph, reach,
    kstMs, keyState, tableStatus, jobStatus, summarize, shortTime, hoursText, staleRuleText, itemText, dotText,
    layout, edgePath,
  };
  L.model = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
