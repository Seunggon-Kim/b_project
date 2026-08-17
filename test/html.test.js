import { test } from 'node:test';
import assert from 'node:assert/strict';

import { decodeEntities, stripTags } from '../src/lib/html.js';

test('이름 있는 엔티티를 풉니다', () => {
  assert.equal(decodeEntities('a&amp;b'), 'a&b');
  assert.equal(decodeEntities('&lt;tag&gt;'), '<tag>');
  assert.equal(decodeEntities('&quot;x&quot;'), '"x"');
});

test('nbsp 를 보통 공백으로 바꿉니다', () => {
  // KBO 순위표의 게임차 칸에 nbsp 가 들어갑니다. 그대로 두면
  // trim 이 먹지 않아 값이 어긋납니다.
  assert.equal(decodeEntities('a&nbsp;b'), 'a b');
});

test('십진 수치 참조를 풉니다', () => {
  assert.equal(decodeEntities('&#39;'), "'");
});

test('십육진 수치 참조를 풉니다', () => {
  assert.equal(decodeEntities('&#x27;'), "'");
});

test('엔티티가 없으면 원문 그대로입니다', () => {
  assert.equal(decodeEntities('평범한 문자열'), '평범한 문자열');
});

test('태그를 지웁니다', () => {
  assert.equal(stripTags('<td><a href="x">LG</a></td>'), 'LG');
});

test('태그를 지우면서 엔티티도 풉니다', () => {
  assert.equal(stripTags('<td>3&nbsp;.5</td>'), '3 .5');
});

test('속성 안의 부등호에 속지 않습니다', () => {
  // 정규식 파싱의 한계를 명시적으로 남겨 둡니다. 원본 Python 도
  // re.sub(r'<[^>]+>', '', c) 라 똑같이 동작합니다.
  // 원본과 같게 두는 것이 목적이므로 고치지 않습니다.
  assert.equal(stripTags('<td class="a>b">값</td>'), 'b">값');
});
