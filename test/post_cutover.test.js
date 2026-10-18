import { test } from 'node:test';
import assert from 'node:assert/strict';

import { readFileSync } from 'node:fs';
import { intIdOrSame, intIdRow, idFixer } from '../src/lib/ids.js';
import { roster, rosterMoves } from '../src/routes/roster.js';
import {
  robustPlayerLookup, playerDetail, playerArsenal, playerUsage,
} from '../src/routes/players.js';
import { wrcBatter, wrcLeaderboard, wrcTopChanges } from '../src/routes/wrc.js';
import { TEXT_ID_COLUMNS, TEXT_ID_TABLES } from '../src/lib/mysqldb.js';

// 질의 글자에 맞는 답을 주는 가짜 DB 입니다. 부른 질의를 calls 에 남깁니다.
function fakeDb(handler) {
  const calls = [];
  return {
    calls,
    prepare(sql) {
      return {
        params: [],
        bind(...p) { this.params = p; return this; },
        async all() {
          calls.push(sql);
          return { results: handler(sql, this.params) || [] };
        },
        async first() {
          calls.push(sql);
          const r = handler(sql, this.params) || [];
          return r[0] || null;
        },
      };
    },
  };
}

const req = (path) => new Request(`https://x.test${path}`);

test('intIdOrSame: 숫자 글자만 숫자로, 나머지는 그대로입니다', () => {
  assert.equal(intIdOrSame('53609'), 53609);
  assert.equal(intIdOrSame(53609), 53609);
  assert.equal(intIdOrSame(null), null);
  assert.equal(intIdOrSame(undefined), undefined);
  assert.equal(intIdOrSame('53609.0'), '53609.0');
  assert.equal(intIdOrSame('abc'), 'abc');
  assert.equal(intIdOrSame(''), '');
});

test('intIdRow: ID 열만 바꾸고 원본은 건드리지 않습니다', () => {
  const row = { player_id: '7', name: '123', batter_ID: '8' };
  const out = intIdRow(row);
  assert.deepEqual(out, { player_id: 7, name: '123', batter_ID: 8 });
  assert.equal(row.player_id, '7');
});

// /roster·/roster/moves 는 KBO 이용약관(2026-10-14 시행)으로 멈춘 표(kbo_roster·
// kbo_roster_moves)를 내보냈습니다. 이제 표를 읽지 않고 410·no-store 입니다.
for (const [name, fn] of [['/roster', roster], ['/roster/moves', rosterMoves]]) {
  test(`${name}: 표를 읽지 않고 410 입니다`, async () => {
    const db = fakeDb(() => [{ player_id: '1' }]);
    const res = await fn(req(name), { MYSQL: db });
    assert.equal(res.status, 410);
    assert.equal(res.headers.get('cache-control'), 'no-store');
    assert.equal(db.calls.length, 0);
  });
}

test('robustPlayerLookup: 숫자 모양이 아닌 입력은 질의 없이 null 입니다', async () => {
  const db = fakeDb(() => [{ player_id: '73153' }]);
  assert.equal(await robustPlayerLookup(db, '73153x'), null);
  assert.equal(await robustPlayerLookup(db, 'abc'), null);
  assert.equal(await robustPlayerLookup(db, ''), null);
  assert.equal(db.calls.length, 0);
});

test('robustPlayerLookup: 숫자와 .0 꼬리는 그대로 찾습니다', async () => {
  const db = fakeDb(() => [{ player_id: '73153' }]);
  assert.deepEqual(await robustPlayerLookup(db, '73153'), { player_id: '73153' });
  assert.deepEqual(await robustPlayerLookup(db, '73153.0'), { player_id: '73153' });
  assert.deepEqual(await robustPlayerLookup(db, 73153), { player_id: '73153' });
});

test('/players/:id, arsenal, usage: 숫자 모양이 아니면 D1 의 없는 선수 응답입니다', async () => {
  const env = { MYSQL: fakeDb(() => [{ player_id: '73153' }]) };
  const p = { id: '73153x' };
  const d = await playerDetail(req('/players/73153x'), env, {}, p);
  assert.equal(d.status, 404);
  assert.deepEqual(await d.json(), { detail: 'Player not found' });
  const a = await playerArsenal(req('/players/73153x/arsenal'), env, {}, p);
  assert.equal(a.status, 200);
  assert.deepEqual(await a.json(), { error: 'Player not found' });
  const u = await playerUsage(req('/players/73153x/usage'), env, {}, p);
  assert.equal(u.status, 200);
  assert.deepEqual(await u.json(), { error: 'Player not found' });
  assert.equal(env.MYSQL.calls.length, 0);
});

test('/wrc/batter/:id: 숫자 모양이 아니면 D1 의 없는 타자 응답입니다', async () => {
  const env = { MYSQL: fakeDb(() => [{ season: 2025 }]) };
  const res = await wrcBatter(req('/wrc/batter/74163x'), env, {}, { id: '74163x' });
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), {
    batter_id: '74163x', player_name: null, history: [], stadium_distribution: [],
  });
  assert.equal(env.MYSQL.calls.length, 0);
});

test('/wrc/leaderboard, top-changes: batter_ID 가 숫자로 돌아옵니다', async () => {
  const rows = [{ batter_ID: '74163', player_name: 'a', season: 2025, PA: 500 }];
  const env = { MYSQL: fakeDb((sql) => (sql.includes('FROM games') ? [{ g: 100 }] : rows)) };
  const lb = await (await wrcLeaderboard(req('/wrc/leaderboard?season=2025&min_pa=1'), env)).json();
  assert.equal(lb[0].batter_ID, 74163);
  const tc = await (await wrcTopChanges(req('/wrc/top-changes?season=2025&min_pa=1'), env)).json();
  assert.equal(tc[0].batter_ID, 74163);
});

// dbexplorer.js 는 JSON 을 import 해 node --test 에서 직접 못 읽습니다.
// 행 변환은 idFixer 로 떼어 검증하고, 경로가 쓰는지는 원문으로 봅니다.
test('idFixer: ID 가 INTEGER 였던 표는 숫자로 바꿉니다', () => {
  assert.equal(TEXT_ID_TABLES.has('kbo_roster'), false);
  const fix = idFixer('kbo_roster');
  assert.deepEqual(fix({ player_id: '53609', name: 'a' }), { player_id: 53609, name: 'a' });
});

test('idFixer: TEXT 였던 표는 같은 행 객체를 그대로 돌려줍니다', () => {
  const row = { player_id: '53609', name: 'a' };
  for (const t of TEXT_ID_TABLES) {
    assert.equal(idFixer(t)(row), row);
  }
});

test('dbexplorer: 표 보기는 idFixer 를 씁니다', () => {
  const src = readFileSync(new URL('../src/routes/dbexplorer.js', import.meta.url), 'utf8');
  assert.ok(src.includes('r.results.map(idFixer(tableName))'));
});

// 데이터 출처 이용약관(KBO 이용약관 제14조 차항, 2026-10-14 시행)으로 표 전체
// 내려받기를 닫고, KBO 사이트에서만 받은 표는 데이터 탐색에서 뺐습니다.
// dbexplorer.js 는 JSON 을 import 해 node --test 가 직접 못 읽어 원문으로 봅니다.
test('dbexplorer: CSV 는 모든 표에 410·no-store 이고 표를 읽지 않습니다', () => {
  const src = readFileSync(new URL('../src/routes/dbexplorer.js', import.meta.url), 'utf8');
  assert.match(src, /export function dbTableCsv\(\) \{\s*const res = json\(\{ error: CSV_CLOSED_MESSAGE \}, 410\);\s*res\.headers\.set\('cache-control', 'no-store'\);/);
  assert.ok(src.includes("'표 전체 내려받기는 제공하지 않습니다(데이터 출처 이용약관).'"));
  assert.ok(!src.includes('data-latest'));
  assert.ok(!src.includes('ReadableStream'));
});

test('dbexplorer: KBO 사이트에서만 받은 표 다섯은 목록·표 보기에서 빠집니다', () => {
  const src = readFileSync(new URL('../src/routes/dbexplorer.js', import.meta.url), 'utf8');
  for (const t of ['futures_games', 'futures_season_stats', 'futures_teams', 'kbo_roster', 'kbo_roster_moves']) {
    assert.ok(src.includes(`'${t}'`), t);
  }
  assert.ok(src.includes('names.filter((n) => !KBO_TOS_HIDDEN_TABLES.has(n)).sort()'));
});

test('TEXT_ID_COLUMNS 에 player_id 가 있습니다', () => {
  assert.ok(TEXT_ID_COLUMNS.has('player_id'));
});
