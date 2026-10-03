import { test } from 'node:test';
import assert from 'node:assert/strict';

import { tableNames, tableColumns, tableExists, sqliteTypeOf } from '../src/lib/schema.js';

function fakeDb(answers) {
  const seen = [];
  return {
    seen,
    prepare(sql) {
      return {
        params: [],
        bind(...p) { this.params = p; return this; },
        async all() { seen.push([sql, this.params]); for (const [k, v] of answers) if (sql.includes(k)) return { results: v }; return { results: [] }; },
        async first() { const { results } = await this.all(); return results[0] || null; },
      };
    },
  };
}

test('MySQL 표 목록은 information_schema 에서, meta_ 표는 뺍니다', async () => {
  const db = fakeDb([['information_schema.tables', [{ name: 'games' }, { name: 'play_by_play' }]]]);
  const names = await tableNames({ DB: db, DB_BACKEND: 'mysql' });
  assert.deepEqual(names, ['games', 'play_by_play']);
  assert.ok(db.seen[0][0].includes("NOT LIKE 'meta"));
});

test('MySQL 열 정보는 D1 PRAGMA 와 같은 모양입니다', async () => {
  const db = fakeDb([['information_schema.columns', [
    { name: 'player_id', dtype: 'int', ckey: 'PRI', nullable: 'NO' },
    { name: 'speed', dtype: 'double', ckey: '', nullable: 'YES' },
    { name: 'as_of', dtype: 'date', ckey: '', nullable: 'NO' },
  ]]]);
  const cols = await tableColumns({ DB: db, DB_BACKEND: 'mysql' }, 'players');
  assert.deepEqual(cols, [
    { name: 'player_id', type: 'INTEGER', pk: 1, notnull: 1 },
    { name: 'speed', type: 'REAL', pk: 0, notnull: 0 },
    { name: 'as_of', type: 'TEXT', pk: 0, notnull: 1 },
  ]);
  assert.deepEqual(db.seen[0][1], ['players']);
});

test('D1 열 정보는 PRAGMA 행을 그대로 돌려줍니다', async () => {
  const row = { cid: 0, name: 'a', type: 'TEXT', notnull: 0, dflt_value: null, pk: 1 };
  const db = fakeDb([['PRAGMA table_info', [row]]]);
  const cols = await tableColumns({ DB: db }, 'games');
  assert.deepEqual(cols, [row]);
  assert.match(db.seen[0][0], /PRAGMA table_info\(`games`\)/);
});

test('샤드 DB 를 따로 줄 수 있습니다', async () => {
  const shardDb = fakeDb([['PRAGMA table_info', [{ name: 'pbp_id' }]]]);
  const cols = await tableColumns({ DB: fakeDb([]) }, 'play_by_play', shardDb);
  assert.deepEqual(cols, [{ name: 'pbp_id' }]);
});

test('표가 있는지 봅니다', async () => {
  const yes = fakeDb([['information_schema.tables', [{ x: 1 }]]]);
  assert.equal(await tableExists({ DB: yes, DB_BACKEND: 'mysql' }, 'wrc_plus_comparison'), true);
  const no = fakeDb([]);
  assert.equal(await tableExists({ DB: no, DB_BACKEND: 'mysql' }, 'nope'), false);
});

test('MySQL 타입 이름을 SQLite 식으로 바꿉니다', () => {
  assert.equal(sqliteTypeOf('int'), 'INTEGER');
  assert.equal(sqliteTypeOf('bigint'), 'INTEGER');
  assert.equal(sqliteTypeOf('double'), 'REAL');
  assert.equal(sqliteTypeOf('varchar'), 'TEXT');
  assert.equal(sqliteTypeOf('datetime'), 'TEXT');
  assert.equal(sqliteTypeOf('mediumblob'), 'BLOB');
});

test('D1 표 목록 SQL 은 ESCAPE 한 글자 역슬래시를 그대로 보냅니다', async () => {
  const db = fakeDb([['sqlite_master', [{ name: 'games' }, { name: 'players' }]]]);
  const names = await tableNames({ DB: db });
  assert.deepEqual(names, ['games', 'players']);
  const sql = db.seen[0][0];
  assert.ok(sql.includes("NOT LIKE '\\_cf\\_%' ESCAPE '\\'"));
  assert.ok(sql.includes("NOT LIKE 'meta\\_%' ESCAPE '\\'"));
  assert.ok(!sql.includes("ESCAPE ''"));
});

test('D1 표 존재 확인은 sqlite_master 에 이름을 묶어 묻습니다', async () => {
  const yes = fakeDb([['sqlite_master', [{ x: 1 }]]]);
  assert.equal(await tableExists({ DB: yes }, 'games'), true);
  assert.match(yes.seen[0][0], /sqlite_master/);
  assert.deepEqual(yes.seen[0][1], ['games']);
  assert.equal(await tableExists({ DB: fakeDb([]) }, 'nope'), false);
});
