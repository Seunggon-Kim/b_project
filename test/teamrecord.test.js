import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  inningsExpr, careerOf, championsOf, mergeSeasons,
  scopeOf, scopeSeasons,
} from '../src/routes/teamrecord.js';

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


// 한국시리즈 우승입니다. 1985년에는 한국시리즈가 열리지 않았습니다.
// 삼성이 전기·후기를 모두 1위로 끝내 통합우승했기 때문입니다.
// 우승으로 세되 그 사실을 따로 남겨 화면에서 밝힐 수 있게 합니다.
test('championsOf 는 우승 횟수와 연도를 셉니다', () => {
  const got = championsOf([
    { season: 2005, note: '' },
    { season: 2002, note: '' },
  ]);
  assert.equal(got.count, 2);
  assert.deepEqual(got.seasons, [2002, 2005]);
  assert.deepEqual(got.no_series, []);
});

test('championsOf 는 한국시리즈가 없던 해를 따로 셉니다', () => {
  const got = championsOf([
    { season: 1985, note: '전·후기 통합우승으로 한국시리즈가 열리지 않았습니다' },
    { season: 2002, note: '' },
  ]);
  assert.equal(got.count, 2, '통합우승도 우승으로 셉니다');
  assert.deepEqual(got.no_series, [1985]);
});

test('championsOf 는 우승이 없어도 터지지 않습니다', () => {
  // 키움과 쌍방울은 우승이 없습니다.
  assert.deepEqual(championsOf([]), { count: 0, seasons: [], no_series: [] });
  assert.deepEqual(championsOf(null), { count: 0, seasons: [], no_series: [] });
});


// 옛 이름을 고르면 그 이름일 때의 기록만 보여야 합니다.
//
// 계보로 묶은 통산 전적은 '현대' 를 골랐을 때는 맞지만 '청보' 를
// 골랐을 때는 틀립니다. 청보는 세 시즌만 뛰었는데 화면에 1466승이
// 뜨면 삼미·태평양·현대의 성적까지 얹힌 값입니다.
const HD = [
  { season: 1987, team_name: '청보', wins: 41, losses: 65, draws: 2, rank: 7 },
  { season: 1986, team_name: '청보', wins: 32, losses: 74, draws: 2, rank: 6 },
  { season: 1985, team_name: '청보', wins: 39, losses: 70, draws: 1, rank: 6 },
  { season: 1984, team_name: '삼미', wins: 38, losses: 58, draws: 4, rank: 5 },
  { season: 1996, team_name: '현대', wins: 70, losses: 55, draws: 1, rank: 2 },
];

test('scopeSeasons 는 고른 이름의 시즌만 남깁니다', () => {
  const got = scopeSeasons(HD, '청보');
  assert.deepEqual(got.map((r) => r.season), [1987, 1986, 1985]);
});

test('scopeSeasons 는 이름이 없으면 전부 돌려줍니다', () => {
  assert.equal(scopeSeasons(HD, '').length, HD.length);
  assert.equal(scopeSeasons(HD, null).length, HD.length);
});

test('scopeOf 는 그 이름이 뛴 기간을 냅니다', () => {
  assert.deepEqual(scopeOf(HD, '청보'),
    { name: '청보', first_season: 1985, last_season: 1987 });
});

test('scopeOf 는 이름이 없거나 못 찾으면 null 입니다', () => {
  assert.equal(scopeOf(HD, ''), null);
  assert.equal(scopeOf(HD, '없는이름'), null);
});

test('좁힌 시즌으로 센 통산 전적은 그 이름 것만입니다', () => {
  const got = careerOf(scopeSeasons(HD, '청보'));
  assert.equal(got.wins, 112, '41 + 32 + 39');
  assert.equal(got.losses, 209);
  assert.equal(got.seasons, 3);
});

test('championsOf 는 준 시즌 안에서만 셉니다', () => {
  // 현대는 1998·2000·2003·2004 에 우승했습니다. 청보는 없습니다.
  const rows = [1998, 2000, 2003, 2004].map((season) => ({ season, note: '' }));
  assert.equal(championsOf(rows).count, 4, '계보 전체');
  assert.equal(championsOf(rows, [1985, 1986, 1987]).count, 0, '청보 때');
  assert.equal(championsOf(rows, [1998, 1999, 2000]).count, 2);
});
