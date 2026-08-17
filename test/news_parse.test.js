import { test } from 'node:test';
import assert from 'node:assert/strict';

import { parseRssItems } from '../src/routes/news.js';

const RSS = `<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>채널 제목입니다</title>
  <item>
    <title>김선수 홈런 - 스포츠조선</title>
    <link>https://example.com/a</link>
    <source url="https://sportschosun.com">스포츠조선</source>
  </item>
  <item>
    <title>제목에 하이픈 - 이 - 여럿 - 매일경제</title>
    <link>https://example.com/b</link>
    <source url="https://mk.co.kr">매일경제</source>
  </item>
  <item>
    <title>출처 없는 기사</title>
    <link>https://example.com/c</link>
  </item>
</channel></rss>`;

test('item 만 읽고 채널 제목은 건너뜁니다', () => {
  const items = parseRssItems(RSS);
  assert.equal(items.length, 3);
  assert.ok(!items.some((i) => i.title === '채널 제목입니다'));
});

test('제목 끝의 " - 언론사" 를 뗍니다', () => {
  const [first] = parseRssItems(RSS);
  assert.equal(first.title, '김선수 홈런');
});

test('하이픈이 여럿이면 마지막 것만 뗍니다', () => {
  // 원본은 rsplit(" - ", 1) 을 씁니다. 앞쪽 하이픈은 남아야 합니다.
  const items = parseRssItems(RSS);
  assert.equal(items[1].title, '제목에 하이픈 - 이 - 여럿');
});

test('source 가 없으면 Google News 입니다', () => {
  const items = parseRssItems(RSS);
  assert.equal(items[2].press, 'Google News');
});

test('link 를 읽습니다', () => {
  const [first] = parseRssItems(RSS);
  assert.equal(first.link, 'https://example.com/a');
});

test('item 이 없으면 빈 배열입니다', () => {
  assert.deepEqual(parseRssItems('<rss><channel></channel></rss>'), []);
});

test('제목의 엔티티를 풉니다', () => {
  const xml = `<rss><channel><item>
    <title>A&amp;B 승리 - 연합</title><link>x</link></item></channel></rss>`;
  const [first] = parseRssItems(xml);
  assert.equal(first.title, 'A&B 승리');
});

test('CDATA 로 감싼 제목을 읽습니다', () => {
  const xml = `<rss><channel><item>
    <title><![CDATA[대괄호 제목 - 언론]]></title><link>x</link></item></channel></rss>`;
  const [first] = parseRssItems(xml);
  assert.equal(first.title, '대괄호 제목');
});

test('하이픈이 없으면 제목을 그대로 둡니다', () => {
  const xml = `<rss><channel><item>
    <title>하이픈없는제목</title><link>x</link></item></channel></rss>`;
  const [first] = parseRssItems(xml);
  assert.equal(first.title, '하이픈없는제목');
});
