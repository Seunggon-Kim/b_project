import { test } from 'node:test';
import assert from 'node:assert/strict';

import { MysqlDb, MYSQL_OPTIONS, TEXT_ID_COLUMNS } from '../src/lib/mysqldb.js';

function fakeConn(rows) {
  const calls = [];
  return {
    calls,
    ended: false,
    async query(sql, params) { calls.push([sql, params]); return [rows, []]; },
    async end() { this.ended = true; },
  };
}

test('D1 과 같은 모양으로 results 를 돌려줍니다', async () => {
  const conn = fakeConn([{ season: 2026, n: 3 }]);
  const db = new MysqlDb(async () => conn);
  const { results } = await db.prepare('SELECT season, n FROM t WHERE x = ? LIMIT ?').bind('a', 5).all();
  assert.deepEqual(results, [{ season: 2026, n: 3 }]);
  assert.deepEqual(conn.calls[0], ['SELECT season, n FROM t WHERE x = ? LIMIT ?', ['a', 5]]);
});

test('first 는 첫 행이나 null 입니다', async () => {
  const db1 = new MysqlDb(async () => fakeConn([{ a: 1 }, { a: 2 }]));
  assert.deepEqual(await db1.prepare('SELECT 1').first(), { a: 1 });
  const db0 = new MysqlDb(async () => fakeConn([]));
  assert.equal(await db0.prepare('SELECT 1').first(), null);
});

test('연결은 한 번만 엽니다', async () => {
  let opened = 0;
  const conn = fakeConn([]);
  const db = new MysqlDb(async () => { opened += 1; return conn; });
  await db.prepare('SELECT 1').all();
  await db.prepare('SELECT 2').all();
  assert.equal(opened, 1);
  await db.close();
  assert.equal(conn.ended, true);
});

test('D1 에서 글자였던 ID 열은 글자로 돌려줍니다', async () => {
  const db = new MysqlDb(async () => fakeConn([{ player_id: 72133, season: 2026, batter_ID: null }]));
  const row = await db.prepare('SELECT 1').first();
  assert.equal(row.player_id, '72133');
  assert.equal(row.season, 2026);
  assert.equal(row.batter_ID, null);
  assert.ok(TEXT_ID_COLUMNS.has('pitcher_ID'));
});

test('연결 옵션은 Workers·응답 모양에 맞춥니다', () => {
  assert.equal(MYSQL_OPTIONS.disableEval, true);
  assert.equal(MYSQL_OPTIONS.dateStrings, true);
  assert.equal(MYSQL_OPTIONS.decimalNumbers, true);
});

test('close 는 연결을 연 적이 없으면 아무것도 하지 않습니다', async () => {
  const db = new MysqlDb(async () => { throw new Error('열면 안 됩니다'); });
  await db.close();
});
