import { test } from 'node:test';
import assert from 'node:assert/strict';

import { pickPlayerId, collectNames } from '../src/routes/futures.js';

// 퓨처스 경기 카드의 선수 이름에 링크가 없었습니다. 1군 카드는 선발·
// 승패 투수가 모두 링크인데 퓨처스만 그냥 글자였습니다. 응답에 이름만
// 있고 선수 ID 가 없었기 때문입니다.
//
// ID 원천은 `futures_season_stats` 입니다(2026 시즌 2군 기록). 이름이
// 겹치면 팀으로 좁힙니다.

const CANDS = [
  { player_id: 1, player_name: '김철수', team: '한화' },
  { player_id: 2, player_name: '김철수', team: '두산' },
  { player_id: 3, player_name: '박영희', team: '삼성' },
];

test('이름이 하나면 그대로 찾습니다', () => {
  assert.equal(pickPlayerId(CANDS, '박영희', null), 3);
});

test('이름이 겹치면 팀으로 좁힙니다', () => {
  assert.equal(pickPlayerId(CANDS, '김철수', '한화'), 1);
  assert.equal(pickPlayerId(CANDS, '김철수', '두산'), 2);
});

test('팀을 몰라 겹치면 링크를 걸지 않습니다', () => {
  // 엉뚱한 선수로 보내느니 링크가 없는 편이 낫습니다.
  assert.equal(pickPlayerId(CANDS, '김철수', null), null);
  assert.equal(pickPlayerId(CANDS, '김철수', 'LG'), null);
});

test('없는 이름은 null 입니다', () => {
  assert.equal(pickPlayerId(CANDS, '이몽룡', '한화'), null);
  assert.equal(pickPlayerId(CANDS, '', '한화'), null);
  assert.equal(pickPlayerId(CANDS, null, null), null);
});

test('이름 앞뒤 공백을 무시합니다', () => {
  assert.equal(pickPlayerId(CANDS, ' 박영희 ', null), 3);
});

test('경기 목록에서 이름을 모읍니다', () => {
  const games = [
    { decisions: { win: '김철수', lose: '박영희', save: '' },
      currentPitcher: '', currentBatter: '' },
    { decisions: { win: '', lose: '', save: '' },
      currentPitcher: '이몽룡', currentBatter: '성춘향' },
  ];
  const got = collectNames(games).sort();
  assert.deepEqual(got, ['김철수', '박영희', '성춘향', '이몽룡']);
});

test('빈 이름과 중복은 빠집니다', () => {
  const games = [
    { decisions: { win: '김철수', lose: '김철수', save: '' },
      currentPitcher: null, currentBatter: '' },
  ];
  assert.deepEqual(collectNames(games), ['김철수']);
});

test('경기가 없으면 빈 목록입니다', () => {
  assert.deepEqual(collectNames([]), []);
  assert.deepEqual(collectNames(null), []);
});
