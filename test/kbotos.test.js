import { test } from 'node:test';
import assert from 'node:assert/strict';

import { KBO_TOS_MESSAGE } from '../src/lib/respond.js';
import { futures } from '../src/routes/futures.js';
import { futuresStandings, futuresLeaders } from '../src/routes/futuresrecord.js';
import { futuresPlayer, futuresSearch } from '../src/routes/futuresplayer.js';

// 2026-10-14 시행 KBO 이용약관 제14조 차항(자동 수집·재배포 금지)에 따라
// KBO 사이트를 그때그때 읽던 퓨처스 경로는 외부 호출 없이 410 을 돌려줍니다.
// 1군 순위(/standings)는 네이버로 바꿨습니다(test/standings_parse.test.js).

const HANDLERS = {
  futures: () => futures(new Request('https://x/schedule/futures?date=2026-10-17')),
  futuresStandings: () => futuresStandings(),
  futuresLeaders: () => futuresLeaders(),
  futuresSearch: () => futuresSearch(new Request('https://x/futures/search?q=김')),
  futuresPlayer: () => futuresPlayer(new Request('https://x/futures/player/56443'), {}, {}, { id: '56443' }),
};

for (const [name, call] of Object.entries(HANDLERS)) {
  test(`${name}: KBO 사이트를 부르지 않고 410·no-store 를 돌려줍니다`, async () => {
    const realFetch = globalThis.fetch;
    let called = 0;
    globalThis.fetch = async () => { called += 1; throw new Error('호출하면 안 됩니다'); };
    try {
      const res = await call();
      assert.equal(res.status, 410);
      assert.equal(res.headers.get('cache-control'), 'no-store');
      assert.deepEqual(await res.json(), { error: KBO_TOS_MESSAGE });
      assert.equal(called, 0);
    } finally {
      globalThis.fetch = realFetch;
    }
  });
}
