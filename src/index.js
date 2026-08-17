import { createRouter } from './lib/router.js';
import { json, serverError } from './lib/respond.js';
import { standings } from './routes/standings.js';
import { schedule } from './routes/schedule.js';

const router = createRouter();

// 원본 api/main.py:78-80 의 루트 응답입니다. 문구를 바꾸지 마십시오.
router.add('GET', '/', () => json({
  message: 'KBO Baseball Analytics API Active',
  version: '1.0.7',
}));

router.add('GET', '/standings', standings);
router.add('GET', '/schedule', schedule);

// 위험 2 판정용 임시 엔드포인트입니다. 판정이 끝나면 Task 8 에서 제거합니다.
//
// 설계 문서는 이 위험을 "네이버가 Cloudflare 엣지를 차단할 수 있다" 로 적었지만,
// 실제 외부 대상은 세 곳입니다. 도메인마다 대응이 다르므로 각각 판정합니다.
router.add('GET', '/probe/external', async () => {
  const targets = [
    {
      name: 'naver',
      url: 'https://api-gw.sports.naver.com/schedule/calendar'
         + '?upperCategoryId=kbaseball&categoryIds=kbo&date=2025-04-01',
      method: 'GET',
    },
    {
      name: 'kbo_html',
      url: 'https://www.koreabaseball.com/Record/TeamRank/TeamRank.aspx',
      method: 'GET',
    },
    {
      name: 'kbo_json',
      url: 'https://www.koreabaseball.com/ws/Main.asmx/GetKboGameList',
      method: 'POST',
      body: 'leId=2&srId=0,9,10&date=20250401',
      headers: {
        'content-type': 'application/x-www-form-urlencoded',
        referer: 'https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx',
        'x-requested-with': 'XMLHttpRequest',
      },
    },
    {
      name: 'google_news',
      url: 'https://news.google.com/rss/search'
         + '?q=%EC%95%BC%EA%B5%AC&hl=ko&gl=KR&ceid=KR:ko',
      method: 'GET',
    },
  ];

  const results = [];
  for (const t of targets) {
    const started = Date.now();
    try {
      const res = await fetch(t.url, {
        method: t.method,
        body: t.body,
        headers: { 'user-agent': 'Mozilla/5.0', ...(t.headers || {}) },
      });
      const text = await res.text();
      results.push({
        name: t.name,
        status: res.status,
        length: text.length,
        ms: Date.now() - started,
        head: text.slice(0, 160).replace(/\s+/g, ' '),
      });
    } catch (err) {
      results.push({
        name: t.name,
        status: 0,
        error: String(err && err.message ? err.message : err),
        ms: Date.now() - started,
      });
    }
  }
  return json({ results });
});

export default {
  async fetch(request, env, ctx) {
    try {
      return await router.handle(request, env, ctx);
    } catch (err) {
      return serverError(err);
    }
  },
};
