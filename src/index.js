import { createRouter } from './lib/router.js';
import { json, serverError } from './lib/respond.js';
import { standings } from './routes/standings.js';
import { schedule } from './routes/schedule.js';
import { futures } from './routes/futures.js';
import { news } from './routes/news.js';
import { leaders } from './routes/leaders.js';

const router = createRouter();

// 원본 api/main.py:78-80 의 루트 응답입니다. 문구를 바꾸지 마십시오.
router.add('GET', '/', () => json({
  message: 'KBO Baseball Analytics API Active',
  version: '1.0.7',
}));

router.add('GET', '/standings', standings);
router.add('GET', '/schedule', schedule);
router.add('GET', '/schedule/futures', futures);
router.add('GET', '/players/:id/news', news);
router.add('GET', '/leaders', leaders);

export default {
  async fetch(request, env, ctx) {
    try {
      return await router.handle(request, env, ctx);
    } catch (err) {
      return serverError(err);
    }
  },
};
