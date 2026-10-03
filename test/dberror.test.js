import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { dbError } from '../src/lib/respond.js';
import { withCache } from '../src/lib/cachepolicy.js';

test('DB 오류는 503 이고 캐시하지 않습니다', async () => {
  const res = withCache(dbError(new Error('D1_ERROR: export')), '/dashboard/stats');
  assert.equal(res.status, 503);
  assert.equal(res.headers.get('cache-control'), 'no-store');
  assert.equal(res.headers.get('access-control-allow-origin'), '*');
  assert.match((await res.json()).detail, /export/);
});

test('본문을 그대로 줄 수 있습니다', async () => {
  const res = dbError(new Error('x'), { error: 'x', traceback: '' });
  assert.equal(res.status, 503);
  assert.deepEqual(await res.json(), { error: 'x', traceback: '' });
});

test('DB 오류를 200 으로 내던 4곳이 dbError 를 씁니다', () => {
  const count = (f) => (readFileSync(f, 'utf8').match(/return dbError\(err, \{/g) || []).length;
  assert.equal(count('src/routes/dashboard.js'), 1);
  assert.equal(count('src/routes/players.js'), 2);
  assert.equal(count('src/routes/leaders.js'), 1);
});
