import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';

import {
  MysqlDb, MYSQL_OPTIONS, TEXT_ID_COLUMNS, TEXT_ID_TABLES,
} from '../src/lib/mysqldb.js';

function fakeConn(rows, fields = []) {
  const calls = [];
  return {
    calls,
    ended: false,
    async query(sql, params) { calls.push([sql, params]); return [rows, fields]; },
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

test('열 정보(fields)가 없으면 열 이름으로 글자 ID 를 정합니다', async () => {
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

test('연결을 못 열면 failed 에 그 오류를 남깁니다', async () => {
  const boom = new Error('connect ECONNREFUSED');
  const db = new MysqlDb(async () => { throw boom; });
  assert.equal(db.failed, null);
  await assert.rejects(db.prepare('SELECT 1').all(), /ECONNREFUSED/);
  assert.equal(db.failed, boom);
  // 두 번째 질의도 같은 실패이고, 처음 오류를 그대로 둡니다.
  await assert.rejects(db.prepare('SELECT 2').first());
  assert.equal(db.failed, boom);
});

test('open 이 바로 던져도 failed 에 남깁니다', async () => {
  const db = new MysqlDb(() => { throw new TypeError('hd is undefined'); });
  await assert.rejects(db.prepare('SELECT 1').all(), TypeError);
  assert.ok(db.failed instanceof TypeError);
});

test('연결 수준(fatal) 질의 오류는 failed 에 남깁니다', async () => {
  const err = Object.assign(new Error('Connection lost'), { fatal: true, code: 'PROTOCOL_CONNECTION_LOST' });
  const conn = { async query() { throw err; }, async end() {} };
  const db = new MysqlDb(async () => conn);
  await assert.rejects(db.prepare('SELECT 1').all(), /Connection lost/);
  assert.equal(db.failed, err);
});

test('표가 없는 것 같은 보통 오류는 failed 에 남기지 않습니다', async () => {
  const err = Object.assign(new Error("Table 'x' doesn't exist"), { code: 'ER_NO_SUCH_TABLE', fatal: false });
  const conn = { async query() { throw err; }, async end() {} };
  const db = new MysqlDb(async () => conn);
  await assert.rejects(db.prepare('SELECT 1 FROM x').all(), /doesn't exist/);
  assert.equal(db.failed, null);
});

// mysql2 의 열 정보 모양입니다. orgTable·orgName 은 원래 표·열 이름이고
// name 은 결과 행의 키(별칭)입니다. 계산한 열은 orgTable 이 빈 글자입니다.
function field(name, orgTable = '', orgName = name) {
  return { name, orgName: orgTable ? orgName : '', table: orgTable, orgTable, db: orgTable ? 'bstats' : '' };
}

test('D1 에서 TEXT 였던 표의 ID 열만 글자로 돌려줍니다', async () => {
  const fields = [
    field('player_id', 'players'),
    field('batter_ID', 'play_by_play'),
    field('pitcher_ID', 'play_by_play'),
    field('season', 'kbo_official_batter_stats'),
  ];
  const db = new MysqlDb(async () => fakeConn(
    [{ player_id: 72133, batter_ID: 65357, pitcher_ID: null, season: 2025 }], fields));
  const row = await db.prepare('SELECT 1').first();
  assert.deepEqual(row, { player_id: '72133', batter_ID: '65357', pitcher_ID: null, season: 2025 });
  for (const t of ['players', 'kbo_official_batter_stats', 'kbo_official_pitcher_stats',
    'futures_season_stats', 'play_by_play']) assert.ok(TEXT_ID_TABLES.has(t), t);
});

test('D1 에서도 INTEGER 였던 표(명단·wRC)의 같은 이름 열은 숫자로 둡니다', async () => {
  const fields = [
    field('player_id', 'kbo_roster'),
    field('batter_ID', 'wrc_plus_comparison'),
    field('pid', 'kbo_roster_moves', 'player_id'),
  ];
  const db = new MysqlDb(async () => fakeConn([{ player_id: 52630, batter_ID: 74163, pid: 1 }], fields));
  assert.deepEqual(await db.prepare('SELECT 1').first(), { player_id: 52630, batter_ID: 74163, pid: 1 });
});

test('별칭이 달라도 원래 열이 TEXT ID 면 글자로 돌려줍니다', async () => {
  const fields = [field('pid', 'players', 'player_id')];
  const db = new MysqlDb(async () => fakeConn([{ pid: 72133 }], fields));
  assert.deepEqual(await db.prepare('SELECT 1').first(), { pid: '72133' });
});

test('계산한 열(orgTable 없음)은 열 이름 규칙으로 물러섭니다', async () => {
  const fields = [field('player_id'), field('n')];
  const db = new MysqlDb(async () => fakeConn([{ player_id: 72133, n: 3 }], fields));
  assert.deepEqual(await db.prepare('SELECT 1').first(), { player_id: '72133', n: 3 });
});

test('이름이 겹치면 마지막 열(mysql2 가 행에 남기는 값)을 따릅니다', async () => {
  const rosterLast = [field('player_id', 'players'), field('player_id', 'kbo_roster')];
  const db1 = new MysqlDb(async () => fakeConn([{ player_id: 1 }], rosterLast));
  assert.deepEqual(await db1.prepare('SELECT 1').first(), { player_id: 1 });
  const playersLast = [field('player_id', 'kbo_roster'), field('player_id', 'players')];
  const db2 = new MysqlDb(async () => fakeConn([{ player_id: 1 }], playersLast));
  assert.deepEqual(await db2.prepare('SELECT 1').first(), { player_id: '1' });
});

test('글자로 바꿀 열 목록은 행마다가 아니라 질의마다 한 번 만듭니다', async () => {
  let reads = 0;
  const f = field('player_id', 'players');
  const counted = {
    name: f.name,
    orgName: f.orgName,
    get orgTable() { reads += 1; return 'players'; },
  };
  const rows = [{ player_id: 1 }, { player_id: 2 }, { player_id: 3 }];
  const db = new MysqlDb(async () => fakeConn(rows, [counted]));
  const { results } = await db.prepare('SELECT 1').all();
  assert.deepEqual(results.map((r) => r.player_id), ['1', '2', '3']);
  assert.equal(reads, 1);
});

test('close 는 연결을 못 열었어도 던지지 않습니다', async () => {
  const db = new MysqlDb(async () => { throw new Error('connect ETIMEDOUT'); });
  await assert.rejects(db.prepare('SELECT 1').all());
  await db.close();
});

test('close 는 end() 가 실패해도 던지지 않습니다', async () => {
  const conn = fakeConn([]);
  conn.end = async () => { throw new Error('Connection lost'); };
  const db = new MysqlDb(async () => conn);
  await db.prepare('SELECT 1').all();
  await db.close();
});

test('질의 사이에 연결이 끊긴 오류 이벤트는 던지지 않고 failed 에 남깁니다', async () => {
  const conn = Object.assign(new EventEmitter(), fakeConn([{ a: 1 }]));
  const db = new MysqlDb(async () => conn);
  await db.prepare('SELECT 1').all();
  const err = Object.assign(new Error('Connection lost: The server closed the connection.'), { fatal: true });
  // 듣는 쪽이 없으면 EventEmitter 가 이 오류를 던져 Worker 가 죽습니다.
  conn.emit('error', err);
  assert.equal(db.failed, err);
});

test('BLOB(Buffer·Uint8Array)은 D1 처럼 숫자 배열로 돌려줍니다', async () => {
  const fields = [field('code', 'team_logos'), field('image', 'team_logos'), field('raw')];
  const db = new MysqlDb(async () => fakeConn(
    [{ code: 'HT', image: Buffer.from([137, 80, 78, 71]), raw: new Uint8Array([0, 255]) }], fields));
  const row = await db.prepare('SELECT 1').first();
  assert.ok(Array.isArray(row.image));
  assert.deepEqual(row, { code: 'HT', image: [137, 80, 78, 71], raw: [0, 255] });
  assert.equal(JSON.stringify(row.image), '[137,80,78,71]');
  // CSV 칸도 D1 과 같게 쉼표로 이은 숫자가 됩니다.
  assert.equal(String(row.image), '137,80,78,71');
});
