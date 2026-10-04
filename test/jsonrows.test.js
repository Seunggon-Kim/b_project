// 행을 JSON 배열 한 칸으로 받는 MySQL 길(lib/jsonrows.js)이 보통 질의
// (mysql2 정적 해석기 + 어댑터 rowsOf)와 같은 값을 내는지 봅니다.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import path from 'node:path';

import {
  jsonArraySql, jsonRows, jsonRowsOnce, mysqlTextFloat, objectsFromJsonTexts, JSON_CONCAT_MAX,
} from '../src/lib/jsonrows.js';
import { MysqlDb, MYSQL_OPTIONS, TEXT_ID_COLUMNS } from '../src/lib/mysqldb.js';

const require = createRequire(import.meta.url);
const root = path.dirname(require.resolve('mysql2'));
const Packet = require(path.join(root, 'lib/packets/packet.js'));
const staticParser = require(path.join(root, 'lib/parsers/static_text_parser.js'));
const Types = require(path.join(root, 'lib/constants/types.js'));

/** mysql2 의 Packet.parseFloat 로 글자 하나를 읽습니다(글자 프로토콜 한 칸). */
function mysql2Float(s) {
  const b = Buffer.from(s, 'ascii');
  const pk = new Packet(0, b, 0, b.length);
  pk.offset = 0;
  return pk.parseFloat(b.length);
}

/** 글자 프로토콜 행들을 mysql2 정적 해석기(배열 모드)와 어댑터로 객체로 만듭니다. */
function viaMysql2(fields, data) {
  const cell = (s) => {
    if (s === null) return Buffer.from([0xfb]);
    const b = Buffer.from(s, 'utf8');
    return Buffer.concat([Buffer.from([b.length]), b]);
  };
  const opts = { ...MYSQL_OPTIONS };
  const p = staticParser(fields, opts, MYSQL_OPTIONS);
  const rows = data.map((cells) => {
    const b = Buffer.concat([Buffer.alloc(4), ...cells.map(cell)]);
    const pk = new Packet(0, b, 0, b.length);
    pk.offset = 4;
    return p.next(pk, fields, opts);
  });
  // Hyperdrive 는 orgTable 을 주지 않아 어댑터가 이름 규칙을 씁니다.
  const db = new MysqlDb(async () => null);
  return db.rowsOf(rows, fields, db.textKeysOf(fields));
}

const col = (name, columnType, characterSet = 63) => ({
  name, orgName: '', orgTable: '', columnType, characterSet,
  encoding: characterSet === 63 ? 'binary' : 'utf8', flags: 0, decimals: 0,
});

test('mysqlTextFloat 는 mysql2 의 Packet.parseFloat 와 똑같은 값을 냅니다', () => {
  const samples = [
    '0', '-0', '1', '144', '-5.485', '0.433', '+3.5', '36.155', '9.559939301972685',
    '9.420289855072465', '9.742647058823529', '9.900990099009901', '33.33333333333333',
    '0.1234567890123456', '-12.345678901234567', '123456789012345678', '1.5e-7', '-2E+3',
    '12345678901234567890.5', '0.30000000000000004', '100.0', '7.000000000000001',
  ];
  // 무작위 17자리 안팎 소수도 섞습니다(정해진 씨앗).
  let seed = 12345;
  const rnd = () => {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    return seed / 2147483648;
  };
  for (let i = 0; i < 2000; i += 1) {
    const v = (rnd() * 200 - 100) / (1 + Math.floor(rnd() * 97));
    samples.push(String(v), v.toPrecision(15), v.toPrecision(17).replace(/0+$/, ''));
  }
  for (const s of samples) {
    assert.ok(Object.is(mysqlTextFloat(s), mysql2Float(s)), s);
  }
  assert.equal(mysqlTextFloat(null), null);
  assert.equal(mysqlTextFloat(undefined), null);
  assert.equal(mysqlTextFloat(''), 0);
  // 17자리에서는 올바른 반올림(Number.parseFloat)과 다를 수 있다는 것이 이 함수의 이유입니다.
  assert.notEqual(mysqlTextFloat('9.559939301972685'), Number.parseFloat('9.559939301972685'));
});

test('jsonArraySql 은 DATETIME·계산 실수 열만 글자로 바꿉니다', () => {
  const sql = jsonArraySql([
    { expr: 'b.`player_id`', name: 'player_id' },
    { expr: 'b.`created_at`', name: 'created_at', datetime: true },
    { expr: 'x / y', name: 'r', float: true },
  ]);
  assert.equal(sql, 'CAST(JSON_ARRAY(b.`player_id`, CAST(b.`created_at` AS CHAR), CAST(x / y AS CHAR)) AS CHAR)');
});

test('JSON 배열 길은 mysql2 글자 프로토콜 길과 같은 객체(키 순서·글자 ID·이름 겹침·NULL)를 냅니다', () => {
  // MySQL 이 JSON 에 적는 모양(실수는 .0, 쉼표 뒤 공백)과 같은 행을 씁니다.
  const fields = [
    col('player_id', Types.LONG),
    col('season', Types.LONG),
    col('player_name', Types.VAR_STRING, 255),
    col('batting_average', Types.DOUBLE),
    col('speed', Types.DOUBLE),
    col('created_at', Types.DATETIME),
    col('player_name', Types.VAR_STRING, 255),
    col('kpct', Types.DOUBLE),
    col('pitcher_ID', Types.LONG),
    col('batter_ID', Types.LONG),
  ];
  const text = [
    ['72133', '2025', '김', '0.337', '144', '2026-10-04 03:12:45', '양의지', '9.559939301972685', '5', '74163'],
    ['1', '2008', null, null, '-0.1', null, '이', null, null, null],
  ];
  const json = [
    '[72133, 2025, "김", 0.337, 144.0, "2026-10-04 03:12:45", "양의지", "9.559939301972685", 5, 74163]',
    '[1, 2008, null, null, -0.1, null, "이", null, null, null]',
  ];
  const names = fields.map((f) => f.name);
  const floats = names.map((n) => n === 'kpct');
  const viaJson = objectsFromJsonTexts(json, names, TEXT_ID_COLUMNS, floats);
  const viaText = viaMysql2(fields, text);
  assert.deepEqual(viaJson, viaText);
  assert.equal(JSON.stringify(viaJson), JSON.stringify(viaText));
  assert.equal(viaJson[0].player_id, '72133');
  assert.equal(viaJson[0].pitcher_ID, '5');
  assert.equal(viaJson[0].player_name, '양의지');
  assert.deepEqual(Object.keys(viaJson[0]).slice(0, 4), ['player_id', 'season', 'player_name', 'batting_average']);
});

test('objectsFromJsonTexts: 빈 입력은 빈 배열, 칸 수가 다르면 던집니다', () => {
  assert.deepEqual(objectsFromJsonTexts([], ['a']), []);
  assert.throws(() => objectsFromJsonTexts(['[1, 2]'], ['a']), /칸 수/);
});

test('jsonRows 는 JSON 배열 한 칸을 raw() 로 받아 객체로 만듭니다', async () => {
  const calls = [];
  const db = {
    prepare(sql) {
      return {
        bind(...params) {
          calls.push([sql, params]);
          return this;
        },
        async raw() {
          return [['[7, "a", "1.25"]'], ['[8, null, null]']];
        },
      };
    },
  };
  const rows = await jsonRows(db, [
    { expr: 't.player_id', name: 'player_id' },
    { expr: 't.n', name: 'name' },
    { expr: 't.x / t.y', name: 'r', float: true },
  ], 'FROM t WHERE a = ? ORDER BY b LIMIT ?', [1, 5]);
  assert.equal(calls[0][0], 'SELECT CAST(JSON_ARRAY(t.player_id, t.n, CAST(t.x / t.y AS CHAR)) AS CHAR) AS j '
    + 'FROM t WHERE a = ? ORDER BY b LIMIT ?');
  assert.deepEqual(calls[0][1], [1, 5]);
  assert.deepEqual(rows, [{ player_id: '7', name: 'a', r: 1.25 }, { player_id: '8', name: null, r: null }]);
});

/** first()·raw() 를 SQL 로 갈라 답하는 가짜 어댑터입니다. */
function fakeDb({ once, rows }) {
  const calls = [];
  return {
    calls,
    prepare(sql) {
      return {
        bind(...params) { calls.push([sql, params]); return this; },
        async first() { return once; },
        async raw() { return rows; },
      };
    },
  };
}

const COLS = [
  { expr: 't.player_id', name: 'player_id' },
  { expr: 't.x / t.y', name: 'r', float: true },
];

test('jsonRowsOnce 는 ROW_NUMBER 순서의 GROUP_CONCAT 한 칸을 받아 풉니다', async () => {
  const db = fakeDb({ once: { n: 2, j: '[7, "1.25"],[8, null]' } });
  const rows = await jsonRowsOnce(db, COLS, 'FROM t WHERE a = ? ORDER BY t.k DESC, t.player_id LIMIT ?', [1, 5],
    't.k DESC, t.player_id');
  assert.deepEqual(rows, [{ player_id: '7', r: 1.25 }, { player_id: '8', r: null }]);
  assert.equal(db.calls.length, 1);
  assert.equal(db.calls[0][0],
    `SELECT /*+ SET_VAR(group_concat_max_len = ${JSON_CONCAT_MAX}) */ COUNT(*) AS n, `
    + "GROUP_CONCAT(t.j ORDER BY t.rn SEPARATOR ',') AS j "
    + 'FROM (SELECT CAST(JSON_ARRAY(t.player_id, CAST(t.x / t.y AS CHAR)) AS CHAR) AS j, '
    + 'ROW_NUMBER() OVER (ORDER BY t.k DESC, t.player_id) AS rn '
    + 'FROM t WHERE a = ? ORDER BY t.k DESC, t.player_id LIMIT ?) AS t');
  assert.deepEqual(db.calls[0][1], [1, 5]);
});

test('jsonRowsOnce: 행이 없으면 빈 배열입니다', async () => {
  const db = fakeDb({ once: { n: 0, j: null } });
  assert.deepEqual(await jsonRowsOnce(db, COLS, 'FROM t', [], 't.k'), []);
});

test('jsonRowsOnce: 잘렸거나 수가 다르면 경고를 남기고 행마다 읽습니다', async () => {
  const warn = console.warn;
  const warned = [];
  console.warn = (...a) => warned.push(a);
  try {
    for (const once of [{ n: 2, j: '[7, "1.25"],[8, nu' }, { n: 3, j: '[7, "1.25"],[8, null]' }, null]) {
      const db = fakeDb({ once, rows: [['[7, "1.25"]'], ['[8, null]']] });
      const rows = await jsonRowsOnce(db, COLS, 'FROM t', [], 't.k');
      assert.deepEqual(rows, [{ player_id: '7', r: 1.25 }, { player_id: '8', r: null }]);
      assert.equal(db.calls.length, 2);
      assert.match(db.calls[1][0], /^SELECT CAST\(JSON_ARRAY/);
    }
  } finally {
    console.warn = warn;
  }
  assert.equal(warned.length, 3);
});
