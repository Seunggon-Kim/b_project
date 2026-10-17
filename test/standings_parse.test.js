import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  KBO_TEAM_CODE, KBO_CODE_TO_TEAM, parseNaverStandings, standings,
} from '../src/routes/standings.js';

// 네이버 statistics/categories/kbo/seasons/{year}/teams 응답 일부입니다
// (2026-10-18 에 받은 값에서 필요한 칸만 남김, 순서는 일부러 섞음).
const NAVER = {
  code: 200,
  result: {
    seasonTeamStats: [
      {
        teamId: 'SS', teamName: '삼성', ranking: 2, gameCount: 144, winGameCount: 83,
        loseGameCount: 58, drawnGameCount: 3, wra: 0.589, gameBehind: 8.0,
        continuousGameResult: '4패', lastFiveGames: 'WLLLL',
      },
      {
        teamId: 'KT', teamName: 'KT', ranking: 1, gameCount: 144, winGameCount: 90,
        loseGameCount: 49, drawnGameCount: 5, wra: 0.647, gameBehind: 0.0,
        continuousGameResult: '10승', lastFiveGames: 'WWWWW',
      },
      {
        teamId: 'HT', teamName: 'KIA', ranking: 3, gameCount: 144, winGameCount: 79,
        loseGameCount: 63, drawnGameCount: 2, wra: 0.5, gameBehind: 12.5,
        continuousGameResult: null,
      },
    ],
  },
};

test('네이버 팀 기록을 예전 순위 행 모양으로 바꿉니다', () => {
  const rows = parseNaverStandings(NAVER);
  assert.deepEqual(rows[0], {
    rank: 1, team: 'KT', code: 'KT', games: '144', wins: '90', losses: '49',
    draws: '5', pct: '0.647', gb: '0', last10: '', streak: '10승',
  });
});

test('순위대로 정렬하고 팀 이름은 현재 이름입니다', () => {
  const rows = parseNaverStandings(NAVER);
  assert.deepEqual(rows.map((r) => r.rank), [1, 2, 3]);
  assert.deepEqual(rows.map((r) => r.team), ['KT', '삼성', 'KIA']);
  assert.deepEqual(rows.map((r) => r.code), ['KT', 'SS', 'HT']);
});

test('승률은 소수 셋째 자리, 게임차는 글자, 연속 기록이 없으면 빈 문자열입니다', () => {
  const kia = parseNaverStandings(NAVER)[2];
  assert.equal(kia.pct, '0.500');
  assert.equal(kia.gb, '12.5');
  assert.equal(kia.streak, '');
  // 네이버는 최근 열 경기를 주지 않습니다. 지어내지 않습니다.
  assert.equal(kia.last10, '');
});

test('결과가 없으면 빈 배열입니다', () => {
  assert.deepEqual(parseNaverStandings({}), []);
  assert.deepEqual(parseNaverStandings({ result: { seasonTeamStats: [] } }), []);
  assert.deepEqual(parseNaverStandings(null), []);
});

test('/standings 는 네이버를 Referer 와 함께 부르고 KBO 사이트는 부르지 않습니다', async () => {
  const realFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), headers: init.headers });
    return new Response(JSON.stringify(NAVER), { status: 200 });
  };
  try {
    const res = await standings();
    const body = await res.json();
    assert.equal(res.status, 200);
    assert.equal(body.source, 'sports.naver.com');
    assert.equal(body.count, 3);
    assert.equal(body.teams[0].code, 'KT');
    assert.equal(calls.length, 1);
    assert.match(calls[0].url,
      /^https:\/\/api-gw\.sports\.naver\.com\/statistics\/categories\/kbo\/seasons\/\d{4}\/teams$/);
    assert.equal(calls[0].headers.referer, 'https://m.sports.naver.com/');
    assert.ok(calls.every((c) => !c.url.includes('koreabaseball')));
  } finally {
    globalThis.fetch = realFetch;
  }
});

test('현재 열 팀이 원본과 같은 코드를 씁니다', () => {
  // 원본 api/main.py:1399-1402 와 같아야 합니다. 하나라도 다르면
  // 로고가 깨지고 /standings 의 code 필드가 어긋납니다.
  const now = {
    LG: 'LG', KT: 'KT', 두산: 'OB', 삼성: 'SS', KIA: 'HT',
    롯데: 'LT', SSG: 'SK', NC: 'NC', 키움: 'WO', 한화: 'HH',
  };
  for (const [team, code] of Object.entries(now)) {
    assert.equal(KBO_TEAM_CODE[team], code, team);
  }
});

test('옛 이름도 같은 프랜차이즈 코드를 씁니다', () => {
  // 1982~2014 기록을 넣으면서 더했습니다. 이게 없으면 홈 화면 개인
  // 순위에서 옛 시즌을 골랐을 때 코드가 빈 문자열이 되어 로고가
  // 조용히 안 나옵니다. 로고 파일은 코드별이라 그대로 씁니다.
  const old = {
    MBC: 'LG', OB: 'OB', 해태: 'HT', 빙그레: 'HH', SK: 'SK',
    우리: 'WO', 히어로즈: 'WO', 넥센: 'WO',
    삼미: 'HD', 청보: 'HD', 태평양: 'HD', 현대: 'HD', 쌍방울: 'SB',
  };
  for (const [team, code] of Object.entries(old)) {
    assert.equal(KBO_TEAM_CODE[team], code, team);
  }
});

test('역매핑은 현재 팀명으로 돌아옵니다', () => {
  // 이름->코드 표를 그대로 뒤집으면 한 코드에 이름이 여럿이라
  // 마지막 것이 이깁니다. 실제로 `LG -> MBC`, `HT -> 해태`,
  // `WO -> 넥센` 이 되었습니다. 그러면 일정 카드가 오늘 경기의
  // 투수를 "MBC 소속" 으로 찾아 링크가 통째로 깨집니다.
  assert.equal(Object.keys(KBO_CODE_TO_TEAM).length, 10);
  assert.equal(KBO_CODE_TO_TEAM['LG'], 'LG');
  assert.equal(KBO_CODE_TO_TEAM['HT'], 'KIA');
  assert.equal(KBO_CODE_TO_TEAM['WO'], '키움');
  assert.equal(KBO_CODE_TO_TEAM['SK'], 'SSG');
  assert.equal(KBO_CODE_TO_TEAM['OB'], '두산');
});

test('역매핑 결과가 다시 같은 코드로 돌아옵니다', () => {
  // 왕복이 어긋나면 링크가 조용히 깨집니다.
  for (const [code, team] of Object.entries(KBO_CODE_TO_TEAM)) {
    assert.equal(KBO_TEAM_CODE[team], code, `${code} -> ${team}`);
  }
});
