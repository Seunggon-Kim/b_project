// test/opsstorage.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { storageBody, SIZE_SQL, COUNT_SQL, BQ_SQL } from '../src/lib/opsstorage.js';
import { cacheControlFor } from '../src/lib/cachepolicy.js';

const NOW = new Date(Date.UTC(2026, 9, 18, 12, 40));   // KST 21:40
const sizes = [
  { name: 'games', data_bytes: '3000000', index_bytes: 1000000 },
  { name: 'play_by_play', data_bytes: 1900000000, index_bytes: 600000000 },
  { name: 'teams', data_bytes: 16384, index_bytes: 0 },
];
const counts = [
  { name: 'games', n: 12688, updated_kst: '2026-10-18 00:05' },
  { name: 'play_by_play', n: 3991757, updated_kst: '2026-10-18 00:04' },
];
const tables = { games: { category: '수집 데이터' }, play_by_play: { category: '수집 데이터' } };
const bq = [
  { name: 'games', bq_rows: 12684, bq_bytes: 3100000, last_ok_at: '2026-10-13 11:27', last_try_at: '2026-10-13 11:27', status: 'ok', error: '숨김' },
  { name: 'play_by_play', bq_rows: 3990573, bq_bytes: 1540000000, last_ok_at: '2026-10-06 11:20', last_try_at: '2026-10-13 11:27', status: 'fail' },
];

test('MySQL 표는 용량 큰 순이고 행 수·분류·갱신 시각을 붙입니다', () => {
  const b = storageBody({ sizes, counts, bq, tables, now: NOW });
  assert.deepEqual(b.mysql.tables.map(t => t.name), ['play_by_play', 'games', 'teams']);
  assert.deepEqual(b.mysql.tables[1], {
    name: 'games', category: '수집 데이터', rows: 12688, rows_updated_at: '2026-10-18 00:05',
    data_bytes: 3000000, index_bytes: 1000000,
  });
  assert.equal(b.mysql.tables[2].rows, null);
  assert.equal(b.mysql.tables[2].category, '');
  assert.equal(b.mysql.total_rows, 12688 + 3991757);
  assert.equal(b.mysql.total_bytes, 3000000 + 1000000 + 1900000000 + 600000000 + 16384);
  assert.equal(b.generated_at, '2026-10-18 21:40');
});

test('빅쿼리 현황은 오류 원문을 내보내지 않습니다', () => {
  const b = storageBody({ sizes, counts, bq, tables, now: NOW });
  assert.equal(b.bigquery.ok, 1);
  assert.equal(b.bigquery.fail, 1);
  assert.equal(b.bigquery.last_copy_at, '2026-10-13 11:27');
  assert.deepEqual(b.bigquery.tables[0], {
    name: 'games', rows: 12684, bytes: 3100000,
    last_ok_at: '2026-10-13 11:27', last_try_at: '2026-10-13 11:27', status: 'ok',
  });
  assert.ok(!JSON.stringify(b).includes('숨김'));
});

test('빅쿼리 현황을 못 읽었으면 null 입니다', () => {
  const b = storageBody({ sizes, counts, bq: null, tables, now: NOW });
  assert.equal(b.bigquery, null);
});

test('SQL 은 meta_ 표를 빼고 시각을 글자로 받습니다', () => {
  assert.match(SIZE_SQL, /information_schema\.tables/);
  assert.match(SIZE_SQL, /NOT LIKE 'meta\\_%'/);
  assert.match(SIZE_SQL, /table_type = 'BASE TABLE'/);
  assert.match(COUNT_SQL, /DATE_ADD\(updated_at, INTERVAL 9 HOUR\)/);
  assert.match(BQ_SQL, /DATE_FORMAT\(last_try_at/);
  assert.ok(!/\berror\b/.test(BQ_SQL));
});

test('주소가 등록돼 있고 엣지에 한 시간 캐시합니다', () => {
  const index = readFileSync('src/index.js', 'utf8');
  assert.match(index, /router\.add\('GET', '\/ops\/storage', opsStorage\)/);
  assert.match(cacheControlFor('/ops/storage'), /s-maxage=3600,/);
});
