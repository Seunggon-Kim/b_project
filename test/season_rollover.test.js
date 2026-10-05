// 2027 시즌이 와도 API 가 새 시즌을 보는지, 오늘(2026-10-05) 응답은 그대로인지
// 날짜를 넣어 봅니다(2026-10-05 검토).
//
//   2026-10-05  오늘. 응답이 예전(2026 고정)과 같아야 합니다.
//   2027-02-15  비시즌. 2027 자료가 아직 없습니다. 기본 시즌은 2026 이어야 합니다.
//   2027-04-15  개막 뒤. 2027 자료가 들어왔습니다. 2027 을 봐야 합니다.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';

import { wrcSeasons } from '../src/routes/wrc.js';

const TODAY = '2026-10-05';
const OFF = '2027-02-15';
const IN = '2027-04-15';

/** node:sqlite 를 어댑터(lib/mysqldb.js)처럼(prepare/bind/all/first) 감쌉니다. */
function sqliteDb(sqlite) {
  return {
    prepare(sql) {
      let params = [];
      return {
        bind(...p) { params = p; return this; },
        async all() { return { results: sqlite.prepare(sql).all(...params).map((r) => ({ ...r })) }; },
        async first() {
          const r = sqlite.prepare(sql).get(...params);
          return r ? { ...r } : null;
        },
      };
    },
  };
}

/** games 와 wrc_plus_comparison 을 seasons 만큼 채운 SQLite 입니다. */
function wrcDb(seasons) {
  const s = new DatabaseSync(':memory:');
  s.exec('CREATE TABLE games (game_id TEXT, season INTEGER)');
  s.exec('CREATE TABLE wrc_plus_comparison (batter_ID INTEGER, season INTEGER, PA INTEGER, '
    + 'wRC_home REAL, wRC_half REAL, wRC_weighted REAL)');
  const g = s.prepare('INSERT INTO games VALUES (?, ?)');
  const w = s.prepare('INSERT INTO wrc_plus_comparison VALUES (?, ?, ?, ?, ?, ?)');
  for (const season of seasons) {
    // 720경기면 규정타석이 446 입니다. min_pa=10 으로 부르면 10 이 문턱입니다.
    for (let i = 0; i < 720; i += 1) g.run(`${season}-${i}`, season);
    for (let b = 1; b <= 4; b += 1) {
      w.run(b, season, 100 * b, 90 + b, 95 + b * 2, 97 + b * 3);
    }
  }
  return sqliteDb(s);
}

async function wrcSeasonsBody(db, today) {
  const res = await wrcSeasons(new Request('https://x/wrc/seasons?min_pa=10'), { MYSQL: db }, {}, {}, today);
  return JSON.parse(await res.text());
}

test('wrc/seasons: 오늘은 2026 까지만 셉니다(예전 BETWEEN 2015 AND 2026 과 같음)', async () => {
  // 2027 행이 있다고 해도 오늘 날짜로는 예전처럼 빠집니다. 운영 응답과 같습니다.
  const body = await wrcSeasonsBody(wrcDb([2025, 2026, 2027]), TODAY);
  assert.deepEqual(body.map((r) => r.season), [2025, 2026]);
});

test('wrc/seasons: 비시즌(2027 자료 없음)에는 오늘과 같은 응답입니다', async () => {
  const db = wrcDb([2025, 2026]);
  assert.deepEqual(await wrcSeasonsBody(db, OFF), await wrcSeasonsBody(db, TODAY));
});

test('wrc/seasons: 2027 개막 뒤에는 2027 줄이 나옵니다', async () => {
  const body = await wrcSeasonsBody(wrcDb([2025, 2026, 2027]), IN);
  assert.deepEqual(body.map((r) => r.season), [2025, 2026, 2027]);
  const y27 = body.find((r) => r.season === 2027);
  assert.equal(y27.n_batters, 4);
  assert.equal(y27.min_pa, 10);
});
