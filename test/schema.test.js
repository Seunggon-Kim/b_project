import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  tableNames, tableColumns, tableExists, sqliteTypeOf, columnCounts,
} from '../src/lib/schema.js';

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

test('표 목록은 information_schema 에서, meta_ 표는 뺍니다', async () => {
  const db = fakeDb([['information_schema.tables', [{ name: 'games' }, { name: 'play_by_play' }]]]);
  const names = await tableNames({ MYSQL: db });
  assert.deepEqual(names, ['games', 'play_by_play']);
  assert.ok(db.seen[0][0].includes("NOT LIKE 'meta"));
});

test('열 정보는 D1 시절 PRAGMA 와 같은 모양입니다', async () => {
  const db = fakeDb([['information_schema.columns', [
    { name: 'player_id', dtype: 'int', ckey: 'PRI', nullable: 'NO' },
    { name: 'speed', dtype: 'double', ckey: '', nullable: 'YES' },
    { name: 'as_of', dtype: 'date', ckey: '', nullable: 'NO' },
  ]]]);
  const cols = await tableColumns({ MYSQL: db }, 'players');
  assert.deepEqual(cols, [
    { name: 'player_id', type: 'INTEGER', pk: 1, notnull: 1 },
    { name: 'speed', type: 'REAL', pk: 0, notnull: 0 },
    { name: 'as_of', type: 'TEXT', pk: 0, notnull: 1 },
  ]);
  assert.deepEqual(db.seen[0][1], ['players']);
});

test('표가 있는지 information_schema 에 이름을 묶어 묻습니다', async () => {
  const yes = fakeDb([['information_schema.tables', [{ x: 1 }]]]);
  assert.equal(await tableExists({ MYSQL: yes }, 'wrc_plus_comparison'), true);
  assert.match(yes.seen[0][0], /information_schema\.tables/);
  assert.deepEqual(yes.seen[0][1], ['wrc_plus_comparison']);
  const no = fakeDb([]);
  assert.equal(await tableExists({ MYSQL: no }, 'nope'), false);
});

test('MySQL 타입 이름을 SQLite 식으로 바꿉니다', () => {
  assert.equal(sqliteTypeOf('int'), 'INTEGER');
  assert.equal(sqliteTypeOf('bigint'), 'INTEGER');
  assert.equal(sqliteTypeOf('double'), 'REAL');
  assert.equal(sqliteTypeOf('varchar'), 'TEXT');
  assert.equal(sqliteTypeOf('datetime'), 'TEXT');
  assert.equal(sqliteTypeOf('mediumblob'), 'BLOB');
});

test('열 수는 한 번의 질의로 표마다 셉니다', async () => {
  const db = fakeDb([['information_schema.columns', [{ name: 'games', n: 9 }, { name: 'players', n: 12 }]]]);
  const m = await columnCounts({ MYSQL: db });
  assert.deepEqual([...m], [['games', 9], ['players', 12]]);
  assert.equal(db.seen.length, 1);
  assert.match(db.seen[0][0], /GROUP BY table_name/);
});

