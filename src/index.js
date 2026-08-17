import { createRouter } from './lib/router.js';
import { json, serverError } from './lib/respond.js';
import { standings } from './routes/standings.js';
import { schedule } from './routes/schedule.js';
import { futures } from './routes/futures.js';
import { news } from './routes/news.js';
import { leaders } from './routes/leaders.js';
import { teams } from './routes/teams.js';
import { dashboardStats } from './routes/dashboard.js';
import { playersSearch, playerDetail } from './routes/players.js';
import { statsSeasons, statsRegulation } from './routes/stats.js';
import { dbTables } from './routes/dbexplorer.js';
import {
  wrcSeasons, wrcByStadium, wrcLeaderboard,
  wrcTopChanges, wrcBatter, wrcBatterSearch,
} from './routes/wrc.js';

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
router.add('GET', '/teams', teams);
router.add('GET', '/dashboard/stats', dashboardStats);
router.add('GET', '/stats/seasons', statsSeasons);
router.add('GET', '/stats/regulation', statsRegulation);
router.add('GET', '/db/tables', dbTables);

// /players/search 를 :id 보다 먼저 등록합니다. 둘 다 2세그먼트라
// 순서가 뒤바뀌면 'search' 가 선수 ID 로 잡힙니다.
router.add('GET', '/players/search', playersSearch);
router.add('GET', '/players/:id', playerDetail);

router.add('GET', '/wrc/seasons', wrcSeasons);
router.add('GET', '/wrc/by-stadium', wrcByStadium);
router.add('GET', '/wrc/leaderboard', wrcLeaderboard);
router.add('GET', '/wrc/top-changes', wrcTopChanges);
// batter-search 를 batter/:id 보다 먼저 둡니다. 둘 다 3세그먼트입니다.
router.add('GET', '/wrc/batter-search', wrcBatterSearch);
router.add('GET', '/wrc/batter/:id', wrcBatter);

export default {
  async fetch(request, env, ctx) {
    try {
      return await router.handle(request, env, ctx);
    } catch (err) {
      return serverError(err);
    }
  },
};
