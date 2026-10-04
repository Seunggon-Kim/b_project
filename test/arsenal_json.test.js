// 구종(/players/:id/arsenal)의 MySQL 길: 공을 GROUP_CONCAT(JSON_ARRAY(...)) 한
// 칸으로 받아 푸는 것이 보통 질의(mysql2 글자 프로토콜)와 같은 응답을 내는지,
// 못 풀면 보통 질의로 물러서는지 봅니다. D1 길은 예전 SQL 그대로입니다.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import path from 'node:path';

import {
  playerArsenal, arsenalFromJson, arsenalJsonSql, ARSENAL_COLUMNS, ARSENAL_JSON_MAX,
} from '../src/routes/players.js';
import { MysqlDb, MYSQL_OPTIONS } from '../src/lib/mysqldb.js';

const require = createRequire(import.meta.url);
const root = path.dirname(require.resolve('mysql2'));
const Packet = require(path.join(root, 'lib/packets/packet.js'));
const staticParser = require(path.join(root, 'lib/parsers/static_text_parser.js'));
const Types = require(path.join(root, 'lib/constants/types.js'));

// 실제 열 형(play_by_play): 글자 둘, DOUBLE 아홉, INT(game_date) 하나.
const TYPES = {
  pitch_type: Types.VAR_STRING, pitch_result: Types.VAR_STRING, game_date: Types.LONG,
};
const FIELDS = ARSENAL_COLUMNS.map((name) => ({
  name, orgName: '', orgTable: '', columnType: TYPES[name] || Types.DOUBLE,
  characterSet: TYPES[name] === Types.VAR_STRING ? 255 : 63,
  encoding: TYPES[name] === Types.VAR_STRING ? 'utf8' : 'binary', flags: 0, decimals: 31,
}));

// 같은 공 두 개를 글자 프로토콜 칸과 MySQL 의 JSON_ARRAY 글자로 적습니다.
const TEXT_ROWS = [
  ['직구', '0.433', '1.79', '144', '스트라이크', '-5.485', '11.636', '20190323', '-1.8', '5.965', '3.491', '1.711'],
  ['투심', '-0.203', '3.571', '144', '볼', '-9.1', '7.25', '20190323', '-1.795', '5.9', '3.4', '1.6'],
];
const JSON_TEXT = '["직구", 0.433, 1.79, 144.0, "스트라이크", -5.485, 11.636, 20190323, -1.8, 5.965, 3.491, 1.711],'
  + '["투심", -0.203, 3.571, 144.0, "볼", -9.1, 7.25, 20190323, -1.795, 5.9, 3.4, 1.6]';

function viaMysql2(data) {
  const cell = (s) => {
    const b = Buffer.from(s, 'utf8');
    return Buffer.concat([Buffer.from([b.length]), b]);
  };
  const p = staticParser(FIELDS, MYSQL_OPTIONS, MYSQL_OPTIONS);
  const rows = data.map((cells) => {
    const b = Buffer.concat([Buffer.alloc(4), ...cells.map(cell)]);
    const pk = new Packet(0, b, 0, b.length);
    pk.offset = 4;
    return p.next(pk, FIELDS, MYSQL_OPTIONS);
  });
  const db = new MysqlDb(async () => null);
  return db.rowsOf(rows, FIELDS, db.textKeysOf(FIELDS));
}

test('arsenalFromJson 은 보통 질의(mysql2)와 같은 객체를 같은 키 순서로 만듭니다', () => {
  const viaJson = arsenalFromJson({ n: 2, j: JSON_TEXT });
  const viaText = viaMysql2(TEXT_ROWS);
  assert.deepEqual(viaJson, viaText);
  assert.equal(JSON.stringify(viaJson), JSON.stringify(viaText));
  assert.deepEqual(Object.keys(viaJson[0]), ARSENAL_COLUMNS);
});

test('arsenalFromJson: 공이 없으면 빈 배열, 못 풀거나 수가 다르면 null', () => {
  assert.deepEqual(arsenalFromJson({ n: 0, j: null }), []);
  assert.equal(arsenalFromJson({ n: 3, j: null }), null);
  assert.equal(arsenalFromJson({ n: 3, j: JSON_TEXT }), null);
  // group_concat_max_len 에서 잘린 글자입니다.
  assert.equal(arsenalFromJson({ n: 2, j: JSON_TEXT.slice(0, 50) }), null);
  assert.equal(arsenalFromJson({ n: 2, j: [1, 2] }), null);
  assert.equal(arsenalFromJson(null), null);
});

test('arsenalJsonSql 은 길이 한도를 늘리고 pbp_id 순서로 잇습니다', () => {
  const sql = arsenalJsonSql();
  assert.match(sql, new RegExp(`SET_VAR\\(group_concat_max_len = ${ARSENAL_JSON_MAX}\\)`));
  assert.match(sql, /COUNT\(\*\) AS n/);
  assert.match(sql, /GROUP_CONCAT\(JSON_ARRAY\(pbp\.pitch_type, pbp\.px, .*pbp\.sz_bot\) ORDER BY pbp\.pbp_id SEPARATOR ','\) AS j/);
  assert.match(sql, /pbp\.gameID NOT LIKE '3333%'/);
});

/** SQL 을 보고 답하는 가짜 MySQL 어댑터입니다(prepare/bind/all/first). */
function fakeDb(answer) {
  const seen = [];
  return {
    seen,
    prepare(sql) {
      let params = [];
      return {
        bind(...p) { params = p; return this; },
        async all() { seen.push(sql); return { results: answer(sql, params) }; },
        async first() { seen.push(sql); return answer(sql, params)[0] || null; },
      };
    },
  };
}

const PLAYER = { player_id: '65543', player_name: '투수' };

test('JSON 한 칸으로 읽고, 응답은 보통 질의와 같습니다', async () => {
  const db = fakeDb((sql) => {
    if (sql.includes('FROM players')) return [PLAYER];
    if (sql.includes('GROUP_CONCAT')) return [{ n: 2, j: JSON_TEXT }];
    throw new Error(`예상 밖 질의: ${sql}`);
  });
  const env = { DB: db };
  const res = await playerArsenal(new Request('https://x/players/65543/arsenal?season=2019'), env, {}, { id: '65543' });
  const body = await res.text();
  assert.equal(body, JSON.stringify({ player_id: '65543', arsenal: viaMysql2(TEXT_ROWS), count: 2 }));
  assert.equal(db.seen.filter((s) => s.includes('GROUP_CONCAT')).length, 1);
});

test('묶은 글자를 못 풀면 pbp_id 순서의 보통 질의로 다시 읽습니다', async () => {
  const plain = viaMysql2(TEXT_ROWS);
  const db = fakeDb((sql) => {
    if (sql.includes('FROM players')) return [PLAYER];
    if (sql.includes('GROUP_CONCAT')) return [{ n: 2, j: JSON_TEXT.slice(0, 150) }];
    if (sql.includes('ORDER BY pbp.pbp_id')) return plain;
    throw new Error(`예상 밖 질의: ${sql}`);
  });
  const warn = console.warn;
  const warned = [];
  console.warn = (...a) => warned.push(a);
  try {
    const env = { DB: db };
    const res = await playerArsenal(new Request('https://x/players/65543/arsenal?season=2019'), env, {}, { id: '65543' });
    assert.deepEqual(await res.json(), { player_id: '65543', arsenal: plain, count: 2 });
  } finally {
    console.warn = warn;
  }
  assert.equal(warned.length, 1);
});

