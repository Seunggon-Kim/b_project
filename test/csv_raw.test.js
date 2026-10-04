// MySQL 에서 CSV 를 배열 행(raw)으로 쓰는 길이 예전 객체 길(all + idFixer +
// csvRow(columns.map …))과 바이트까지 같은지 봅니다.
//
// 라우트(dbexplorer.js)는 컬럼 사전 JSON 을 import 해서 node:test 가 읽지
// 못합니다(lib/csv.js 머리 주석). 라우트가 부르는 조각을 그대로 엮어 봅니다.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { MysqlDb } from '../src/lib/mysqldb.js';
import { idFixer, idFixFlags, intIdOrSame } from '../src/lib/ids.js';
import { csvRow, csvRowsFromArrays, isRealType } from '../src/lib/csv.js';

const f = (name) => ({ name, orgName: '', orgTable: '', table: '' });

// 표 두 개: play_by_play(ID 가 글자로 남는 표)와 kbo_roster(ID 를 숫자로 되돌리는 표).
const TABLES = {
  play_by_play: {
    cols: [['pbp_id', 'INTEGER'], ['pitcher_ID', 'INTEGER'], ['speed', 'REAL'],
      ['description', 'TEXT'], ['pos_1_id', 'INTEGER'], ['logo', 'BLOB']],
    rows: [
      [1, 70425, 145, '이용규 : "중견수", 앞', 97202, null],
      [2, null, 132.5, null, null, Buffer.from([1, 2])],
      [3, 60181, -0.25, '줄\n바꿈', 61102, null],
    ],
  },
  kbo_roster: {
    cols: [['id', 'INTEGER'], ['player_id', 'INTEGER'], ['name', 'TEXT'], ['weight', 'REAL']],
    rows: [[1, 52630, '김', 80], [2, 7, '이,박', 81.5], [3, null, null, null]],
  },
};

/** mysql2(rowsAsArray)처럼 매번 새 배열 행과 열 정보를 줍니다. */
function dbOf(table) {
  const t = TABLES[table];
  return new MysqlDb(async () => ({
    async query() { return [t.rows.map((r) => r.slice()), t.cols.map(([n]) => f(n))]; },
    async end() {},
  }));
}

for (const table of Object.keys(TABLES)) {
  test(`MySQL CSV(raw 길)는 예전 객체 길과 바이트가 같습니다: ${table}`, async () => {
    const env = { DB_BACKEND: 'mysql' };
    const columns = TABLES[table].cols.map(([n]) => n);
    const realFlags = TABLES[table].cols.map(([, ty]) => isRealType(ty));
    const sql = `SELECT * FROM \`${table}\` LIMIT ? OFFSET ?`;

    // 예전 길
    const { results } = await dbOf(table).prepare(sql).bind(100, 0).all();
    const fix = idFixer(env, table);
    let want = '';
    for (const r of results) {
      const row = fix(r);
      want += csvRow(columns.map((c) => row[c]), realFlags);
    }

    // raw 길
    const [names, ...rows] = await dbOf(table).prepare(sql).bind(100, 0).raw({ columnNames: true });
    const got = csvRowsFromArrays(names, rows, columns, realFlags,
      idFixFlags(env, table, columns), intIdOrSame);
    assert.equal(got, want);
  });
}

test('kbo_roster 의 player_id 는 숫자로, 실수 열의 정수는 .0 으로 씁니다', async () => {
  const columns = TABLES.kbo_roster.cols.map(([n]) => n);
  const [names, ...rows] = await dbOf('kbo_roster').prepare('SELECT 1').raw({ columnNames: true });
  const text = csvRowsFromArrays(names, rows, columns, [false, false, false, true],
    idFixFlags({ DB_BACKEND: 'mysql' }, 'kbo_roster', columns), intIdOrSame);
  assert.equal(text, '1,52630,김,80.0\r\n2,7,"이,박",81.5\r\n3,,,\r\n');
});

test('csvRowsFromArrays: 없는 열은 빈 칸, 겹친 이름은 뒤 열을 씁니다', () => {
  const text = csvRowsFromArrays(['a', 'b', 'a'], [[1, 2, 3]], ['a', 'x', 'b'], []);
  assert.equal(text, '3,,2\r\n');
});

test('idFixFlags 는 idFixer 와 같은 열·같은 경우에만 참입니다', () => {
  const cols = ['player_id', 'name', 'batter_ID'];
  assert.deepEqual(idFixFlags({ DB_BACKEND: 'mysql' }, 'kbo_roster', cols), [true, false, true]);
  assert.deepEqual(idFixFlags({ DB_BACKEND: 'mysql' }, 'play_by_play', cols), [false, false, false]);
  assert.deepEqual(idFixFlags({ DB_BACKEND: 'd1' }, 'kbo_roster', cols), [false, false, false]);
});
