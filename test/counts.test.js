import { test } from 'node:test';
import assert from 'node:assert/strict';

import { countOf } from '../src/lib/counts.js';

test('play_by_play 행 수는 메타 표에서 한 번만 읽습니다', async () => {
  const seen = [];
  const db = {
    prepare: (sql) => ({
      bind(...p) { seen.push([sql, p]); return this; },
      async first() { return { n: 3983367 }; },
    }),
  };
  assert.equal(await countOf(db, 'play_by_play'), 3983367);
  assert.deepEqual(seen, [['SELECT n FROM meta_table_counts WHERE name = ?', ['play_by_play']]]);
});
