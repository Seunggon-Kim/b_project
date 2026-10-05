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
import { playerArsenal, playerUsage, defaultPitchSeason } from '../src/routes/players.js';

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

/**
 * 구종·구사율 라우트용 가짜 DB 입니다. 공식 기록의 마지막 시즌을 maxSeason 으로
 * 답하고, play_by_play 질의에 넘어온 값(선수, from, to)을 모아 둡니다.
 */
function pitchDb(maxSeason) {
  const seen = [];
  const pbpBinds = [];
  return {
    seen,
    pbpBinds,
    prepare(sql) {
      let params = [];
      return {
        bind(...p) { params = p; return this; },
        async first() {
          seen.push(sql);
          if (sql.includes('FROM players')) return { player_id: '65933', player_name: '투수' };
          if (sql.includes('MAX(s) AS s')) return { s: maxSeason };
          if (sql.includes('FROM play_by_play')) {
            pbpBinds.push(params);
            return { n: 0, j: null };
          }
          throw new Error(`예상 밖 질의: ${sql}`);
        },
        async all() {
          seen.push(sql);
          if (sql.includes('FROM play_by_play')) {
            pbpBinds.push(params);
            return { results: [] };
          }
          throw new Error(`예상 밖 질의: ${sql}`);
        },
      };
    },
  };
}

const ARSENAL = (q = '') => new Request(`https://x/players/65933/arsenal${q}`);
const USAGE = (q = '') => new Request(`https://x/players/65933/usage${q}`);
const P = { id: '65933' };

for (const [name, route, req] of [['arsenal', playerArsenal, ARSENAL], ['usage', playerUsage, USAGE]]) {
  test(`${name}: season 이 없으면 기록이 있는 최근 시즌입니다(날짜별)`, async () => {
    const cases = [
      // [오늘, 공식 기록의 마지막 시즌, 기대 시즌]
      [TODAY, 2026, 2026],
      [OFF, 2026, 2026], // 비시즌: 2027 은 아직 비어 있어 2026 을 봅니다.
      [IN, 2027, 2027], // 개막 뒤 첫 적재부터 2027 입니다.
    ];
    for (const [today, max, want] of cases) {
      const db = pitchDb(max);
      const res = await route(req(), { MYSQL: db }, {}, P, today);
      assert.equal(res.status, 200, today);
      assert.deepEqual(db.pbpBinds, [['65933', want * 10000, (want + 1) * 10000]], today);
    }
  });

  test(`${name}: 오늘은 season 없이 불러도 ?season=2026 과 같은 응답입니다`, async () => {
    const a = await (await route(req(), { MYSQL: pitchDb(2026) }, {}, P, TODAY)).text();
    const b = await (await route(req('?season=2026'), { MYSQL: pitchDb(2026) }, {}, P, TODAY)).text();
    assert.equal(a, b);
  });

  test(`${name}: season 을 주면 마지막 시즌을 묻지 않습니다`, async () => {
    const db = pitchDb(2026);
    await route(req('?season=2025'), { MYSQL: db }, {}, P, TODAY);
    assert.ok(!db.seen.some((s) => s.includes('MAX(s) AS s')));
    assert.deepEqual(db.pbpBinds, [['65933', 20250000, 20260000]]);
  });

  test(`${name}: 2027 은 오늘은 없는 시즌이고 개막 뒤에는 있는 시즌입니다`, async () => {
    const before = pitchDb(2026);
    await route(req('?season=2027'), { MYSQL: before }, {}, P, TODAY);
    assert.deepEqual(before.pbpBinds, []);
    const after = pitchDb(2027);
    await route(req('?season=2027'), { MYSQL: after }, {}, P, IN);
    assert.deepEqual(after.pbpBinds, [['65933', 20270000, 20280000]]);
  });
}

test('구종 기본 시즌: 공식 기록이 비었으면 한국 날짜의 올해입니다', async () => {
  assert.equal(await defaultPitchSeason(pitchDb(null), TODAY), 2026);
  assert.equal(await defaultPitchSeason(pitchDb(null), OFF), 2027);
  assert.equal(await defaultPitchSeason(pitchDb(2026), OFF), 2026);
});
