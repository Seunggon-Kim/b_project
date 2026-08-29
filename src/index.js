import { createRouter } from './lib/router.js';
import { json, serverError } from './lib/respond.js';
import { withCache } from './lib/cachepolicy.js';
import { standings } from './routes/standings.js';
import { schedule } from './routes/schedule.js';
import { futures } from './routes/futures.js';
import { leaders } from './routes/leaders.js';
import { teams } from './routes/teams.js';
import { dashboardStats } from './routes/dashboard.js';
import {
  playersSearch, playerDetail, playerArsenal, playerUsage,
} from './routes/players.js';
import {
  statsSeasons, statsRegulation, statsBatters, statsPitchers,
} from './routes/stats.js';
import { dbTables, dbTable, dbTableCsv } from './routes/dbexplorer.js';
import { purgeCache } from './routes/admin.js';
import { jobsStatus } from './routes/jobs.js';
import { games } from './routes/games.js';
import { roster, rosterMoves } from './routes/roster.js';
import { futuresStandings, futuresLeaders } from './routes/futuresrecord.js';
import { futuresPlayer, futuresSearch } from './routes/futuresplayer.js';
import { logo } from './routes/logo.js';
import { statsTeamRange } from './routes/teamrange.js';
import {
  wrcSeasons, wrcByStadium, wrcLeaderboard,
  wrcTopChanges, wrcBatter, wrcBatterSearch, wrcDistribution,
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
// 퓨처스 순위·개인 기록입니다. KBO 사이트를 그때그때 읽습니다(5분 캐시).
// `/schedule/futures` 보다 뒤에 둬도 경로가 겹치지 않습니다.
router.add('GET', '/futures/standings', futuresStandings);
router.add('GET', '/futures/leaders', futuresLeaders);
// 퓨처스 선수 한 명입니다. 1군 기록이 한 번도 없는 선수는 players 표에
// 아예 없어서 /players/:id 가 404 를 줍니다. 그때 화면이 이리로 옵니다.
// 이름으로 2군 선수를 찾습니다. players 표는 1군 기록에서 만들어서
// 2군 전용 선수가 없습니다. 화면은 우리 검색이 빈손일 때만 부릅니다.
router.add('GET', '/futures/search', futuresSearch);
router.add('GET', '/futures/player/:id', futuresPlayer);
// `/players/:id/news` 는 없앴습니다. 뉴스 수집을 그만두기로 했습니다.
// 1982년까지 선수를 넣으면서 대상이 562명에서 1,745명으로 늘었고,
// 구글 뉴스는 은퇴 선수에게 쓸 만한 결과를 주지 못합니다. 매일 25분을
// 쓰면서 러너 IP 가 걸려 자주 실패하기도 했습니다.
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
router.add('GET', '/players/:id/arsenal', playerArsenal);
router.add('GET', '/players/:id/usage', playerUsage);
router.add('GET', '/stats/team_range', statsTeamRange);
router.add('GET', '/stats/batters', statsBatters);
router.add('GET', '/stats/pitchers', statsPitchers);
router.add('GET', '/games', games);
// 1군 등록·말소입니다. KBO 는 오늘 것만 보여 줘서 daily 가 매일 쌓습니다.
router.add('GET', '/roster', roster);
router.add('GET', '/roster/moves', rosterMoves);
router.add('GET', '/db/table/:name', dbTable);
router.add('GET', '/db/table/:name/csv', dbTableCsv);
router.add('GET', '/logo/:code', logo);

router.add('GET', '/wrc/seasons', wrcSeasons);
router.add('GET', '/wrc/by-stadium', wrcByStadium);
router.add('GET', '/wrc/leaderboard', wrcLeaderboard);
router.add('GET', '/wrc/top-changes', wrcTopChanges);
// batter-search 를 batter/:id 보다 먼저 둡니다. 둘 다 3세그먼트입니다.
router.add('GET', '/wrc/batter-search', wrcBatterSearch);
router.add('GET', '/wrc/batter/:id', wrcBatter);
router.add('GET', '/wrc/distribution', wrcDistribution);

// 원본에 없던 관리 엔드포인트입니다. 적재가 끝나면 캐시를 비웁니다.
// POST 로 둡니다. 상태를 바꾸는 일이고, GET 이면 브라우저 프리페치나
// 링크 미리보기가 실수로 부를 수 있습니다.
router.add('POST', '/admin/purge-cache', purgeCache);

// 수집이 마지막으로 언제 돌았는지 알려줍니다. 원본에는 없고, EC2 의
// cron_status.json 정적 파일을 대신합니다.
router.add('GET', '/jobs/status', jobsStatus);

export default {
  async fetch(request, env, ctx) {
    try {
      const res = await router.handle(request, env, ctx);
      // Cache-Control 을 여기서 한 번에 붙입니다. 라우트마다 붙이면
      // 빠뜨리기 쉽고, 빠뜨린 곳은 캐시가 안 걸려 D1 을 그대로 읽습니다.
      // 정책은 lib/cachepolicy.js 에 있습니다.
      return withCache(res, new URL(request.url).pathname);
    } catch (err) {
      return serverError(err);
    }
  },
};
