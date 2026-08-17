import { createRouter } from './lib/router.js';
import { json, serverError } from './lib/respond.js';
import { standings } from './routes/standings.js';
import { schedule } from './routes/schedule.js';
import { futures } from './routes/futures.js';
import { news } from './routes/news.js';
import { leaders } from './routes/leaders.js';
import { teams } from './routes/teams.js';
import { dashboardStats } from './routes/dashboard.js';
import {
  playersSearch, playerDetail, playerArsenal, playerUsage,
} from './routes/players.js';
import {
  statsSeasons, statsRegulation, statsBatters, statsPitchers,
} from './routes/stats.js';
import { dbTables, dbTable } from './routes/dbexplorer.js';
import { games } from './routes/games.js';
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
router.add('GET', '/players/:id/arsenal', playerArsenal);
router.add('GET', '/players/:id/usage', playerUsage);
router.add('GET', '/stats/team_range', statsTeamRange);
router.add('GET', '/stats/batters', statsBatters);
router.add('GET', '/stats/pitchers', statsPitchers);
router.add('GET', '/games', games);
router.add('GET', '/db/table/:name', dbTable);
router.add('GET', '/logo/:code', logo);

router.add('GET', '/wrc/seasons', wrcSeasons);
router.add('GET', '/wrc/by-stadium', wrcByStadium);
router.add('GET', '/wrc/leaderboard', wrcLeaderboard);
router.add('GET', '/wrc/top-changes', wrcTopChanges);
// batter-search 를 batter/:id 보다 먼저 둡니다. 둘 다 3세그먼트입니다.
router.add('GET', '/wrc/batter-search', wrcBatterSearch);
router.add('GET', '/wrc/batter/:id', wrcBatter);
router.add('GET', '/wrc/distribution', wrcDistribution);

// CPU 실측용 임시 엔드포인트입니다. Task 8 에서 제거합니다.
//
// Workers 는 호출당 CPU 10ms 입니다. fetch 대기는 세지 않지만 D1 결과를
// JS 에서 도는 시간은 셉니다. 무거운 엔드포인트가 한도를 넘는지 재 봅니다.
// 판정 기준은 wall_ms 숫자가 아니라 **요청이 성공하는지**입니다.
router.add('GET', '/probe/cpu', async (request, env) => {
  const which = new URL(request.url).searchParams.get('q') || '';
  const t0 = Date.now();
  let rows = 0;
  let note = '';

  if (which === 'pbp_scan') {
    // /stats/team_range 가 하는 대량 스캔과 비슷합니다.
    const r = await env.DB.prepare(
      'SELECT pa_result, inning_topbot, score_home, score_away, home, away '
      + 'FROM play_by_play WHERE game_date BETWEEN ? AND ?',
    ).bind(20250401, 20250430).all();
    rows = r.results.length;
    let n = 0;
    for (const x of r.results) if (x.pa_result) n += 1;
    note = 'pa ' + n;
  } else if (which === 'pbp_all') {
    // /db/table/play_by_play/csv?limit=0 이 하는 전량 읽기입니다.
    const r = await env.DB.prepare('SELECT * FROM play_by_play').all();
    rows = r.results.length;
    note = 'cols ' + (rows ? Object.keys(r.results[0]).length : 0);
  } else if (which === 'usage') {
    // /players/{id}/usage 와 비슷한 투수 단위 읽기입니다.
    const r = await env.DB.prepare(
      'SELECT pitch_type, stands, throws, balls, strikes, pa_result '
      + 'FROM play_by_play WHERE pitcher_ID = ?',
    ).bind('50030').all();
    rows = r.results.length;
    const m = new Map();
    for (const x of r.results) m.set(x.pitch_type, (m.get(x.pitch_type) || 0) + 1);
    note = 'kinds ' + m.size;
  } else if (which === 'wrc_all') {
    // /wrc/distribution 이 하는 정렬과 분위수 계산입니다.
    const r = await env.DB.prepare(
      'SELECT wRC_home, wRC_half, wRC_weighted FROM wrc_plus_comparison '
      + 'WHERE season = ? AND PA >= ?',
    ).bind(2025, 100).all();
    rows = r.results.length;
    const vals = r.results.map((x) => x.wRC_half).sort((a, b) => a - b);
    note = 'median ' + (vals[Math.floor(vals.length / 2)] ?? 'none');
  } else if (which === 'logo') {
    const r = await env.DB.prepare(
      "SELECT mime, image FROM team_logos WHERE code='LG'").first();
    rows = r ? 1 : 0;
    const img = r ? r.image : null;
    note = JSON.stringify({
      type: typeof img,
      ctor: img && img.constructor ? img.constructor.name : null,
      isArray: Array.isArray(img),
      isView: ArrayBuffer.isView(img),
      len: img && img.length !== undefined ? img.length
        : (img && img.byteLength !== undefined ? img.byteLength : null),
      head: Array.isArray(img) ? img.slice(0, 4)
        : (typeof img === 'string' ? img.slice(0, 12) : null),
    });
  } else {
    return json({ error: 'q 를 pbp_scan|pbp_all|usage|wrc_all|logo 중에서' }, 400);
  }

  return json({ q: which, rows, wall_ms: Date.now() - t0, note });
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
