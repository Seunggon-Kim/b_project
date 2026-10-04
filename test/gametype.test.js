import { test } from 'node:test';
import assert from 'node:assert/strict';

import { regularSeasonSql, NON_REGULAR_PREFIXES } from '../src/lib/gametype.js';
import { playerArsenal } from '../src/routes/players.js';

test('정규시즌 조건은 포스트시즌·올스타전 경기 ID 를 뺍니다', () => {
  const sql = regularSeasonSql('pbp');
  for (const p of ['3333', '4444', '5555', '7777', '9999']) {
    assert.ok(sql.includes(`pbp.gameID NOT LIKE '${p}%'`), p);
  }
  // 순위결정전(6666)은 KBO 가 개인 기록을 정규시즌에 넣으므로 남깁니다.
  assert.ok(!NON_REGULAR_PREFIXES.includes('6666'));
});

test('구종 구사율 질의는 정규시즌 공만 셉니다', async () => {
  const seen = [];
  const db = {
    prepare(sql) {
      return {
        bind() { return this; },
        async first() {
          seen.push(sql);
          if (sql.includes('FROM players')) return { player_id: '65933', player_name: '구창모' };
          // 구종 질의(GROUP_CONCAT 한 칸)는 공이 없으면 n=0, j=NULL 입니다.
          return sql.includes('GROUP_CONCAT') ? { n: 0, j: null } : null;
        },
        async all() { seen.push(sql); return { results: [] }; },
      };
    },
  };
  const env = { DB: db };
  const req = new Request('https://x/players/65933/arsenal?season=2026');
  const res = await playerArsenal(req, env, {}, { id: '65933' });
  assert.equal(res.status, 200);
  const arsenalSql = seen.find((s) => s.includes('FROM play_by_play'));
  assert.ok(arsenalSql, 'play_by_play 질의가 있어야 합니다');
  assert.ok(arsenalSql.includes(regularSeasonSql('pbp')));
});
