import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// components.js 는 브라우저용 전역 스크립트라 import 가 안 됩니다.
// 필요한 두 함수만 떼어 평가합니다.
const src = readFileSync('dashboard_js/js/components.js', 'utf8');
const grab = (name) => {
  const at = src.indexOf(`function ${name}(`);
  assert.notEqual(at, -1, `${name} 를 찾지 못했습니다`);
  let depth = 0;
  let i = src.indexOf('{', at);
  const start = at;
  for (; i < src.length; i += 1) {
    if (src[i] === '{') depth += 1;
    else if (src[i] === '}') { depth -= 1; if (!depth) break; }
  }
  return src.slice(start, i + 1);
};
const colorTable = (() => {
  const at = src.indexOf('const TEAM_COLORS');
  const end = src.indexOf('};', at) + 2;
  return src.slice(at, end);
})();

// eslint-disable-next-line no-new-func
const { teamColor, textOn, TEAM_COLORS } = new Function(
  `${colorTable}\n${grab('teamColor')}\n${grab('textOn')}\n`
  + 'return { teamColor, textOn, TEAM_COLORS };')();

test('없어진 구단 색은 위키백과 틀을 따릅니다', () => {
  // 위키백과 '야구 주요 색' 틀의 배경색1 입니다.
  assert.equal(TEAM_COLORS['쌍방울'], '#FFC81E');
  assert.equal(TEAM_COLORS['현대'], '#007F55');
  assert.equal(TEAM_COLORS['삼미'], '#88B7E1');
  assert.equal(TEAM_COLORS['청보'], '#E72025');
  assert.equal(TEAM_COLORS['태평양'], '#224433');
  assert.equal(TEAM_COLORS['MBC'], '#1552F8');
});

test('옛 이름은 계보를 따라 지금 구단 색을 씁니다', () => {
  // 위키백과 틀에 없는 팀들입니다. 지금 구단의 이전 이름이라 그렇습니다.
  assert.equal(TEAM_COLORS['해태'], TEAM_COLORS['KIA']);
  assert.equal(TEAM_COLORS['OB'], TEAM_COLORS['두산']);
  assert.equal(TEAM_COLORS['빙그레'], TEAM_COLORS['한화']);
  assert.equal(TEAM_COLORS['SK'], TEAM_COLORS['SSG']);
  assert.equal(TEAM_COLORS['넥센'], TEAM_COLORS['키움']);
});

test('밝은 배경에는 검은 글자를 올립니다', () => {
  // 쌍방울은 노랑, 삼미는 하늘색입니다. 흰 글자를 올리면 안 읽힙니다.
  assert.equal(textOn('#FFC81E'), '#111111');
  assert.equal(textOn('#88B7E1'), '#111111');
});

test('어두운 배경에는 흰 글자를 올립니다', () => {
  assert.equal(textOn('#EA0029'), '#ffffff');  // KIA
  assert.equal(textOn('#000000'), '#ffffff');  // KT
  assert.equal(textOn('#224433'), '#ffffff');  // 태평양
});

test('색을 모르면 흰 글자로 둡니다', () => {
  assert.equal(textOn(''), '#ffffff');
  assert.equal(textOn(null), '#ffffff');
  assert.equal(textOn('#abc'), '#ffffff');
});

test('teamColor 는 모르는 팀에 기본 남색을 줍니다', () => {
  assert.equal(teamColor('없는팀'), '#1e293b');
  assert.equal(teamColor(''), '#1e293b');
});
