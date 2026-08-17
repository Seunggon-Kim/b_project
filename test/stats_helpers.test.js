import { test } from 'node:test';
import assert from 'node:assert/strict';

import { teamIdsClause } from '../src/routes/stats.js';

test('쉼표로 나눠 자리표시자를 만듭니다', () => {
  const r = teamIdsClause('LG,KT', 'p.team_id');
  assert.equal(r.sql, ' AND p.team_id IN (?,?)');
  assert.deepEqual(r.binds, ['LG', 'KT']);
});

test('값을 SQL 에 직접 넣지 않습니다', () => {
  // 이 자리에 값이 그대로 들어가면 주입 통로가 됩니다.
  const r = teamIdsClause("LG'; DROP TABLE players; --", 'p.team_id');
  assert.ok(!r.sql.includes('DROP'));
  assert.equal(r.binds.length, 1);
});

test('앞뒤 공백을 떼어 냅니다', () => {
  const r = teamIdsClause(' LG , KT ', 'p.team_id');
  assert.deepEqual(r.binds, ['LG', 'KT']);
});

test('빈 조각은 버립니다', () => {
  const r = teamIdsClause('LG,,KT,', 'p.team_id');
  assert.deepEqual(r.binds, ['LG', 'KT']);
});

test('값이 없으면 조건을 붙이지 않습니다', () => {
  for (const v of ['', null, undefined, ' , , ']) {
    const r = teamIdsClause(v, 'p.team_id');
    assert.equal(r.sql, '', String(v));
    assert.deepEqual(r.binds, []);
  }
});

test('하나만 있어도 됩니다', () => {
  const r = teamIdsClause('SSG', 'p.team_id');
  assert.equal(r.sql, ' AND p.team_id IN (?)');
  assert.deepEqual(r.binds, ['SSG']);
});
