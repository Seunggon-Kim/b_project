import { test } from 'node:test';
import assert from 'node:assert/strict';

import { inningsExpr, careerOf, mergeSeasons } from '../src/routes/teamrecord.js';

// 공식 기록의 이닝은 **텍스트**입니다.
//
//     '98 1/3'   98와 3분의 1
//     '9 2/3'    9와 3분의 2
//     '5'        5
//
// 그대로 SUM 하면 SQLite 가 앞 숫자만 읽어 '98 1/3' 이 98 이 됩니다.
// 팀 ERA 가 그만큼 낮게 나옵니다. 조각을 나눠 더해야 합니다.

test('이닝 식이 정수부와 분수부를 모두 봅니다', () => {
  const e = inningsExpr('p.innings_pitched');
  // 정수부를 자르는 자리와 3분의 1·3분의 2 를 더하는 자리가 있어야 합니다.
  assert.ok(e.includes('1/3'));
  assert.ok(e.includes('2/3'));
  assert.ok(e.includes('p.innings_pitched'));
});

test('통산은 승패무를 더하고 승률을 다시 계산합니다', () => {
  const got = careerOf([
    { games: 100, wins: 60, losses: 38, draws: 2, rank: 1 },
    { games: 100, wins: 40, losses: 58, draws: 2, rank: 5 },
  ]);
  assert.equal(got.seasons, 2);
  assert.equal(got.wins, 100);
  assert.equal(got.losses, 96);
  assert.equal(got.draws, 4);
  // 승률은 무승부를 빼고 셉니다. KBO 방식입니다.
  assert.equal(got.pct, 100 / 196);
  assert.equal(got.first_place, 1);
});

test('빈 시즌 목록도 견딥니다', () => {
  const got = careerOf([]);
  assert.equal(got.seasons, 0);
  assert.equal(got.pct, null);
});

test('값이 비어도 통산이 깨지지 않습니다', () => {
  // 옛 시즌은 일부 칸이 빌 수 있습니다.
  const got = careerOf([{ games: null, wins: null, losses: null, draws: null }]);
  assert.equal(got.wins, 0);
  assert.equal(got.pct, null);
});

test('시즌 기록을 순위 행에 붙입니다', () => {
  const ranks = [
    { season: 2026, team_name: 'KIA', rank: 3 },
    { season: 1999, team_name: '해태', league: '매직리그', rank: 6 },
  ];
  const stats = new Map([
    [2026, { season: 2026, avg: 0.271, era: 4.12 }],
  ]);
  const got = mergeSeasons(ranks, stats);
  assert.equal(got[0].avg, 0.271);
  assert.equal(got[0].rank, 3);
  // 기록이 없는 시즌도 순위는 남아야 합니다.
  assert.equal(got[1].season, 1999);
  assert.equal(got[1].avg, undefined);
});

test('양대리그 해에는 두 행 모두 같은 팀 기록을 씁니다', () => {
  // 그 시즌 팀 전체 기록이라 양쪽에 같은 값이 붙는 것이 맞습니다.
  const ranks = [
    { season: 1999, team_name: '해태', league: '매직리그' },
    { season: 1999, team_name: '해태', league: '드림리그' },
  ];
  const stats = new Map([[1999, { season: 1999, avg: 0.268 }]]);
  const got = mergeSeasons(ranks, stats);
  assert.equal(got[0].avg, 0.268);
  assert.equal(got[1].avg, 0.268);
});
