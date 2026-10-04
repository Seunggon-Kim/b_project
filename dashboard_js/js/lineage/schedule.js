/*
 * 데이터 탐색 탭의 '자동 수집 스케줄' 표입니다. 계보 파일(table_lineage.json)의
 * 작업·단계·스크립트와 /jobs/status 실행 기록으로 만듭니다. 손으로 적은 표는
 * 수집 작업이 바뀔 때마다 어긋나서 이것으로 바꿨습니다.
 *
 * 위쪽 HTML 을 만드는 함수는 Node 로 검증하고, mount() 만 브라우저에서 돕니다.
 * 근거: docs/superpowers/specs/2026-10-04-explorer-schedule-from-lineage-design.md
 */
(function (root) {
  'use strict';
  const L = root.Lineage = root.Lineage || {};

  // 표에 싣지 않는 거들기 단계입니다(실행 기록 남기기·DB 연결).
  const HELPER = /(^|\/)(record_job_run\.py|ci_proxy\.sh)$/;
  // 작업을 보여 줄 순서입니다(하루 흐름: 새벽 daily → 오후 roster → 주간 → 월간).
  const JOB_ORDER = ['daily', 'roster', 'weekly', 'monthly'];

  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/[&<>"]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m]));
  }

  function baseName(path) { return String(path || '').split('/').pop(); }

  function jobRank(id) {
    const i = JOB_ORDER.indexOf(id);
    return i < 0 ? JOB_ORDER.length : i;
  }

  /**
   * 표의 줄입니다. 스크립트 하나에 한 줄이고, 처음 나오는 작업·단계 순서를 따릅니다.
   * 반환 [{ path, name, desc, runs: [{ job, schedule, key }] }]
   *   desc: scripts[].desc 가 있으면 그것, 없으면 단계 이름들(겹치면 한 번)과 note
   *   runs: 그 스크립트가 도는 작업마다 하나. key 는 그 작업에서 그 스크립트 단계의 기록 키(없으면 null)
   */
  function scheduleRows(lin) {
    const jobs = (lin && lin.jobs ? lin.jobs.slice() : [])
      .sort((a, b) => jobRank(a.id) - jobRank(b.id) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
    const scripts = {};
    ((lin && lin.scripts) || []).forEach(s => { scripts[s.path] = s; });
    const rows = [];
    const byPath = {};
    jobs.forEach(function (j) {
      (j.steps || []).forEach(function (st) {
        if (!st.script || HELPER.test(st.script)) return;
        let row = byPath[st.script];
        if (!row) {
          row = byPath[st.script] = { path: st.script, name: baseName(st.script), stepNames: [], runs: [] };
          rows.push(row);
        }
        if (st.name && !row.stepNames.includes(st.name)) row.stepNames.push(st.name);
        let run = row.runs.find(r => r.job === j.id);
        if (!run) {
          run = { job: j.id, schedule: j.schedule_kst || '', key: null };
          row.runs.push(run);
        }
        if (!run.key && st.status_key) run.key = st.status_key;
      });
    });
    return rows.map(function (r) {
      const s = scripts[r.path] || {};
      const desc = s.desc ? String(s.desc) : [r.stepNames.join(' · '), s.note || ''].filter(Boolean).join('. ');
      return { path: r.path, name: r.name, desc: desc, runs: r.runs };
    });
  }

  const RESULT = { ok: '', skip: ' (건너뜀)', fail: ' (실패)' };

  /**
   * 마지막 업데이트 칸 한 줄입니다. 실행 기록을 따로 남기지 않는 단계와 실행 기록을
   * 못 받았을 때는 '-' 입니다(표 아래 안내문이 뜻을 적어 둡니다).
   */
  function runText(run, details) {
    if (!run.key || !details) return `${run.schedule}: -`;
    const rec = details[run.key];
    if (!rec) return `${run.schedule}: 아직 기록 없음`;
    const st = rec.status === null || rec.status === undefined ? '' : String(rec.status);
    const mark = st === '' ? '' : (Object.prototype.hasOwnProperty.call(RESULT, st) ? RESULT[st] : ` (${st})`);
    return `${run.schedule}: ${rec.last_run_at || '-'}${mark}`;
  }

  /** 표 몸통(tbody 안) HTML 입니다. */
  function scheduleHtml(rows, details) {
    return rows.map(function (r) {
      const sched = r.runs.map(x => esc(x.schedule)).join('<br>');
      const upd = r.runs.map(function (x) {
        const t = runText(x, details);
        const fail = details && x.key && details[x.key] && details[x.key].status === 'fail';
        const note = details && x.key && details[x.key] && details[x.key].note;
        return `<span class="dbx-run${fail ? ' fail' : ''}"${note ? ` title="${esc(note)}"` : ''}>${esc(t)}</span>`;
      }).join('<br>');
      return '<tr>'
        + `<td class="dbx-cron-mods">${esc(r.name)}<span class="sub">${esc(r.path)}</span></td>`
        + `<td class="dbx-cron-desc">${esc(r.desc)}</td>`
        + `<td class="dbx-cron-kst">${sched}</td>`
        + `<td class="dbx-cron-upd">${upd}</td>`
        + '</tr>';
    }).join('');
  }

  /** 카드 제목 옆 요약입니다. 예: '총 20개 스크립트 · 작업 4개' */
  function scheduleSummary(rows, lin) {
    return `총 ${rows.length}개 스크립트 · 작업 ${((lin && lin.jobs) || []).length}개`;
  }

  // ===== 화면(브라우저에서만) =====

  /**
   * 표를 채웁니다. opts = { tbody, summary, lineage: Promise<{ok,data|error}>, jobs: Promise<{ok,data|error}> }
   * 계보 파일을 못 받으면 표 자리에 이유를 보이고, 실행 기록만 못 받으면 마지막 업데이트를 '-' 로 둡니다.
   */
  async function mount(opts) {
    const tbody = opts.tbody;
    try {
      const jobsP = Promise.resolve(opts.jobs).catch(function (e) { console.error(e); return { ok: false, error: String((e && e.message) || e) }; });
      const res = await Promise.all([opts.lineage, jobsP]);
      const lin = res[0];
      if (!lin || !lin.ok) {
        tbody.innerHTML = `<tr><td colspan="4" class="dbx-cron-error">수집 일정을 불러오지 못했습니다 (${esc((lin && lin.error) || '빈 응답')}).</td></tr>`;
        return;
      }
      const js = res[1];
      const det = js && js.ok && js.data && js.data.details && typeof js.data.details === 'object' ? js.data.details : null;
      const rows = scheduleRows(lin.data);
      tbody.innerHTML = scheduleHtml(rows, det);
      if (opts.summary) opts.summary.textContent = scheduleSummary(rows, lin.data);
    } catch (e) {
      console.error(e);
      tbody.innerHTML = `<tr><td colspan="4" class="dbx-cron-error">수집 일정을 불러오지 못했습니다 (${esc(String((e && e.message) || e))}).</td></tr>`;
    }
  }

  const api = { HELPER, JOB_ORDER, scheduleRows, runText, scheduleHtml, scheduleSummary, mount };
  L.schedule = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
