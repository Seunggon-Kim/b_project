// 화면 스크립트(UMD)를 vm 으로 불러 시험합니다. dashboard_js/*.js 는 script 태그용이라
// import 할 수 없습니다(package.json 의 type=module 과 무관).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

function load(...files) {
  const ctx = {};
  ctx.window = ctx;
  vm.createContext(ctx);
  for (const f of files) vm.runInContext(readFileSync(f, 'utf8'), ctx, { filename: f });
  return ctx;
}
const ctx = load('dashboard_js/js/lineage/model.js', 'dashboard_js/js/dataops/model.js');
const M = ctx.DataOps.model;
const L = ctx.Lineage.model;

test('용량 글자', () => {
  assert.equal(M.fmtBytes(2480000000), '2.48 GB');
  assert.equal(M.fmtBytes(7500000), '7.5 MB');
  assert.equal(M.fmtBytes(18000), '18 KB');
  assert.equal(M.fmtBytes(null), '-');
});

test('비교 칸은 네 가지와 정보 없음뿐입니다', () => {
  const my = { name: 'games', rows: 12688 };
  assert.deepEqual({ ...M.compare(my, { rows: 12688, status: 'ok' }, true) }, { kind: 'same', diff: 0 });
  assert.deepEqual({ ...M.compare(my, { rows: 12684, status: 'ok' }, true) }, { kind: 'diff', diff: 4 });
  assert.equal(M.compare(my, { rows: 12000, status: 'fail' }, true).kind, 'fail');
  assert.equal(M.compare(my, undefined, true).kind, 'missing');
  assert.equal(M.compare(my, undefined, false).kind, 'unknown');
});

const STORAGE = {
  mysql: {
    tables: Array.from({ length: 12 }, (_, i) => ({
      name: 't' + String(i).padStart(2, '0'), category: '', rows: 10, rows_updated_at: null,
      data_bytes: 1000 - i, index_bytes: 0,
    })),
    total_rows: 120, total_bytes: 11934,
  },
  bigquery: { last_copy_at: '2026-10-13 11:27', ok: 2, fail: 0,
    tables: [{ name: 't00', rows: 10, bytes: 500, status: 'ok' }, { name: 't01', rows: 9, bytes: 400, status: 'ok' }] },
};

test('저장소 줄과 접기', () => {
  const rows = M.storageRows(STORAGE);
  assert.equal(rows[0].cmp.kind, 'same');
  assert.equal(rows[1].cmp.kind, 'diff');
  assert.equal(rows[2].cmp.kind, 'missing');
  const { top, rest } = M.splitFold(rows);
  assert.equal(top.length, 10);
  assert.equal(rest.length, 2);
  const s = M.storageSummary(STORAGE, rows);
  assert.deepEqual({ ...s }, { totalRows: 120, totalBytes: 11934, tableCount: 12, same: 1,
    bqBytes: 900, lastCopyAt: '2026-10-13 11:27' });
});

test('빅쿼리 정보가 없으면 비교는 정보 없음입니다', () => {
  const rows = M.storageRows({ ...STORAGE, bigquery: null });
  assert.ok(rows.every(r => r.cmp.kind === 'unknown'));
  assert.equal(M.storageSummary({ ...STORAGE, bigquery: null }, rows).lastCopyAt, null);
});

const LIN = {
  sources: [
    { id: 'kbo_record', name: 'KBO 기록실', url: 'https://www.koreabaseball.com/Record/' },
    { id: 'naver_relay', name: '네이버 문자중계', url: 'https://sports.naver.com/kbaseball/' },
    { id: 'kbo_live', name: '네이버 실시간', url: 'https://m.sports.naver.com/kbaseball/' },
  ],
  scripts: [
    { path: 'data_collection/a.py', sources: ['kbo_record'], stopped: true },
    { path: 'data_collection/b.py', sources: ['kbo_record', 'naver_relay'], stopped: true },
    { path: 'data_collection/c.py', sources: ['naver_relay'], stopped: false },
  ],
  jobs: [
    { id: 'daily', schedule_kst: '매일 03:33', stale_hours: 36, stopped: false,
      steps: [{ name: 'PBP', status_key: 'pbp' }, { name: '기록', status_key: null }, { name: 'games', status_key: 'games' }] },
    { id: 'roster', schedule_kst: '멈춤', stale_hours: 36, stopped: true,
      steps: [{ name: '명단', status_key: 'roster_pm' }] },
  ],
};

test('출처 카드: 쓰는 스크립트가 모두 멈췄을 때만 수집 중단', () => {
  const cards = M.sourceCards(LIN, L.sourceStopped);
  assert.deepEqual(cards.map(c => [c.id, c.host, c.stopped, c.scripts.length]), [
    ['kbo_record', 'KBO 공식 사이트', true, 2],
    ['naver_relay', '네이버 스포츠', false, 2],
    ['kbo_live', '네이버 스포츠', false, 0],
  ]);
  assert.deepEqual([...cards[0].scripts], ['a.py', 'b.py']);
  assert.ok(!JSON.stringify(cards).includes('koreabaseball'));
});

test('작업 카드와 셈', () => {
  const now = Date.UTC(2026, 9, 17, 16, 0);   // KST 10-18 01:00
  const details = {
    pbp: { last_run_at: '2026-10-17 23:59', status: 'ok' },
    games: { last_run_at: '2026-10-15 23:59', status: 'ok' },
    roster_pm: { last_run_at: '2026-10-17 22:41', status: 'ok' },
  };
  const cards = M.jobCards(LIN, details, now, L.jobStatus);
  assert.deepEqual(cards.map(c => [c.id, c.state, c.items.length]), [['daily', 'stale', 2], ['roster', 'stopped', 1]]);
  assert.deepEqual({ ...M.jobCounts(cards) }, { ok: 1, run: 2, warn: 1, stopped: 1 });
});

test('이력은 최근 날짜부터, 같은 날은 파일 순서', () => {
  const ev = M.historyEvents({ events: [
    { date: '2026-10-14', what: 'a' }, { date: '2026-10-18', what: 'b' }, { date: '2026-10-18', what: 'c' },
  ] });
  assert.deepEqual(ev.map(e => e.what), ['b', 'c', 'a']);
  assert.deepEqual([...M.historyEvents(null)], []);
});
