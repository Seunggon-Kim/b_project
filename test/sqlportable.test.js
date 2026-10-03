// D1 과 MySQL 양쪽에서 같은 뜻인 SQL 만 쓰는지 소스를 검사합니다(3단계).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';

const files = ['src/routes', 'src/lib']
  .flatMap((d) => readdirSync(d).filter((f) => f.endsWith('.js')).map((f) => `${d}/${f}`));
const src = Object.fromEntries(files.map((f) => [f, readFileSync(f, 'utf8')]));

function offenders(re) {
  return files.filter((f) => re.test(src[f]));
}

test('CAST 는 CHAR·SIGNED·DOUBLE 만 씁니다', () => {
  // CAST(ROUND(…) AS INT) 처럼 괄호가 겹쳐도 잡히게 "AS 타입)" 만 봅니다.
  assert.deepEqual(offenders(/\bAS (TEXT|INT|INTEGER|REAL)\)/), []);
});

test('스칼라 MIN(?, …) 을 쓰지 않습니다', () => {
  assert.deepEqual(offenders(/MIN\(\s*\?\s*,/), []);
});

test("date('now' …) 를 쓰지 않습니다", () => {
  assert.deepEqual(offenders(/date\('now'/i), []);
});

test('표 이름을 큰따옴표로 감싸지 않습니다', () => {
  // csv.js 의 셀 따옴표, 내려받기 파일 이름은 SQL 이 아니라 그대로 둡니다.
  assert.deepEqual(offenders(/(FROM|JOIN|table_info\()\s*"\$\{/), []);
});

test('정수 나눗셈 game_date / 10000 은 SIGNED 로 감쌉니다', () => {
  assert.deepEqual(offenders(/CAST\(game_date \/ 10000 AS (TEXT|CHAR)\)/), []);
});

test('sqlite_master·PRAGMA 는 schema.js 에만 있습니다', () => {
  const bad = offenders(/sqlite_master|PRAGMA/).filter((f) => !f.endsWith('lib/schema.js'));
  assert.deepEqual(bad, []);
});
