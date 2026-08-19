import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

// D1 은 자바스크립트 숫자를 SQLite REAL 로 바인딩합니다.
//
//   .bind(2026)  ->  typeof(?) = 'real',  CAST(? AS TEXT) = '2026.0'
//
// 그래서 `substr(gameID,1,4) = CAST(? AS TEXT)` 같은 문장은 언제나
// 거짓입니다. 오류가 나지 않고 빈 결과만 돌아와서, 화면에는 "그 해에는
// 기록이 없다"로 보입니다. 실제로 이 코드 때문에 투수 구종·구사율 탭이
// 계속 비어 있었습니다.
//
// 숫자로 시즌을 가릴 때는 `game_date >= 20260000 AND game_date < 20270000`
// 처럼 정수끼리 비교합니다(lib/shard.js 의 seasonDateRange).
// 문자열 비교가 꼭 필요하면 바인딩 전에 String() 으로 바꿉니다.

function jsFiles(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...jsFiles(p));
    else if (name.endsWith('.js')) out.push(p);
  }
  return out;
}

test('숫자 바인딩을 TEXT 로 캐스팅하는 문장이 없습니다', () => {
  const bad = [];
  for (const f of jsFiles('src')) {
    const src = readFileSync(f, 'utf8');
    src.split('\n').forEach((line, i) => {
      if (/CAST\(\?\d*\s+AS\s+TEXT\)/i.test(line)) {
        bad.push(`${f}:${i + 1}  ${line.trim()}`);
      }
    });
  }
  assert.deepEqual(bad, [], `D1 은 숫자를 REAL 로 바인딩합니다:\n${bad.join('\n')}`);
});
