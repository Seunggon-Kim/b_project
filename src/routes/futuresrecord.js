import { json } from '../lib/respond.js';
import { ttlCache } from '../lib/cache.js';
import { stripTags } from '../lib/html.js';

// 퓨처스(2군) 팀 순위와 개인 기록입니다.
//
// 1군 순위(`routes/standings.js`)와 같은 방식으로 KBO 사이트를 그때그때
// 읽습니다. D1 에 쌓지 않는 이유는 화면이 늘 최신만 보여 주면 되고,
// 쌓으면 daily 에 단계가 하나 더 늘기 때문입니다.
//
// 퓨처스는 **북부·남부 두 리그**로 나뉩니다. 페이지도 둘입니다.

const cache = ttlCache(300); // 1군 순위와 같은 5분

const BASE = 'https://www.koreabaseball.com/Futures';
const UA = { 'user-agent': 'Mozilla/5.0' };

// 퓨처스 팀 -> 엠블럼 코드입니다. 1군에 없는 팀이 셋 있습니다.
//
//     상무   국군체육부대. 1군에 대응 팀이 없습니다.
//     고양   히어로즈 2군. 1군은 '키움' 입니다.
//     울산   롯데 2군. 1군은 '롯데' 입니다.
//
// 로고가 없는 팀은 빈 문자열로 두고 화면이 팀 코드 글자로 물러섭니다
// (`emblemError`).
export const FUTURES_TEAM_CODE = {
  LG: 'LG', KT: 'KT', 두산: 'OB', 삼성: 'SS', KIA: 'HT',
  롯데: 'LT', SSG: 'SK', NC: 'NC', 키움: 'WO', 한화: 'HH',
  // 2군 연고지 이름으로 나오는 팀입니다.
  고양: 'WO', 울산: 'LT',
  // 상무는 군 팀이라 대응하는 구단 로고가 없습니다.
  상무: '',
};

/**
 * 순위표를 읽습니다. 1군과 컬럼이 같습니다.
 *
 * 이 페이지에는 표가 둘입니다. 순위표와 팀간 상대전적입니다. 상대전적
 * 표는 첫 칸이 팀 이름이라 `cells[0]` 이 숫자인지 보는 것으로 걸러집니다.
 */
function parseRank(page) {
  const teams = [];
  for (const tbl of page.matchAll(/<table[^>]*>([\s\S]*?)<\/table>/g)) {
    const tbody = /<tbody>([\s\S]*?)<\/tbody>/.exec(tbl[1]);
    const body = tbody ? tbody[1] : tbl[1];
    for (const tr of body.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)) {
      const cells = [...tr[1].matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)]
        .map((m) => stripTags(m[1]).trim());
      if (cells.length < 8) continue;
      if (!/^\d+$/.test(cells[0])) continue;
      const name = cells[1];
      teams.push({
        rank: Number.parseInt(cells[0], 10),
        team: name,
        code: FUTURES_TEAM_CODE[name] ?? '',
        games: cells[2],
        wins: cells[3],
        losses: cells[4],
        draws: cells[5],
        pct: cells[6],
        gb: cells[7],
        last10: cells.length > 8 ? cells[8] : '',
        streak: cells.length > 9 ? cells[9] : '',
      });
    }
    // 순위표를 찾았으면 더 볼 필요가 없습니다. 뒤 표는 상대전적입니다.
    if (teams.length) break;
  }
  return teams;
}

/**
 * 퓨처스 팀 순위입니다. 북부·남부를 함께 돌려줍니다.
 *
 * 두 페이지를 나란히 부릅니다. 줄 세우면 응답이 두 배 느려지는데
 * 서로 다른 페이지라 순서가 결과에 영향을 주지 않습니다.
 */
export async function futuresStandings() {
  try {
    const hit = cache.get('rank');
    if (hit) return json(hit);

    const [north, south] = await Promise.all([
      fetch(`${BASE}/TeamRank/North.aspx`, { headers: UA }),
      fetch(`${BASE}/TeamRank/South.aspx`, { headers: UA }),
    ]);
    if (!north.ok || !south.ok) {
      throw new Error(`HTTP ${north.status}/${south.status}`);
    }
    const groups = [
      { league: '북부', teams: parseRank(await north.text()) },
      { league: '남부', teams: parseRank(await south.text()) },
    ];
    const count = groups.reduce((n, g) => n + g.teams.length, 0);
    const result = { count, groups, source: 'koreabaseball.com' };
    // 비면 캐시하지 않습니다. 일시 실패를 5분간 물고 있지 않으려는 것입니다.
    if (count) cache.set('rank', result);
    return json(result);
  } catch (err) {
    return json({
      count: 0,
      groups: [],
      error: String(err && err.message ? err.message : err),
    });
  }
}

/**
 * 개인 기록 한 장을 읽어 (헤더, 행) 으로 돌려줍니다.
 *
 * **선수 이름 칸에 `playerId` 가 있습니다.**
 *
 *     <td><a href="HitterDetail.aspx?playerId=54156">손용준</a></td>
 *
 * 1군 기록실과 같은 체계라 우리 `players.player_id` 와 그대로 맞습니다.
 * 그래서 이름으로 짝지을 필요가 없고 동명이인 문제도 없습니다.
 *
 * 행은 `{ cells, playerId }` 로 돌려줍니다. 화면이 이름 칸만 링크로
 * 감싸면 됩니다.
 */
async function parseLeaders(path) {
  const res = await fetch(`${BASE}/Player/${path}`, { headers: UA });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const page = await res.text();

  const tbl = /<table[^>]*>([\s\S]*?)<\/table>/.exec(page);
  if (!tbl) return { columns: [], rows: [] };
  const columns = [...tbl[1].matchAll(/<th[^>]*>([\s\S]*?)<\/th>/g)]
    .map((m) => stripTags(m[1]).trim());
  const tbody = /<tbody>([\s\S]*?)<\/tbody>/.exec(tbl[1]);
  const body = tbody ? tbody[1] : tbl[1];

  const rows = [];
  for (const tr of body.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)) {
    const raw = [...tr[1].matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)].map((m) => m[1]);
    const cells = raw.map((c) => stripTags(c).trim());
    if (cells.length < 4) continue;
    if (!/^\d+$/.test(cells[0])) continue;
    // 이름 칸(두 번째)의 링크에서 ID 를 꺼냅니다. 없으면 null 이고
    // 화면은 링크 없이 이름만 보여 줍니다.
    const m = /playerId=(\d+)/.exec(raw[1] || '');
    rows.push({ cells, playerId: m ? Number.parseInt(m[1], 10) : null });
  }
  return { columns, rows };
}

/**
 * 퓨처스 개인 기록입니다. 타자·투수를 함께 돌려줍니다.
 *
 * **wOBA·wRC+ 는 없습니다.** 그 지표는 play_by_play 로 계산하는데
 * 퓨처스는 타석 단위 자료가 공개되지 않습니다. 화면은 대신 안타·홈런을
 * 보여 줍니다.
 */
export async function futuresLeaders() {
  try {
    const hit = cache.get('leaders');
    if (hit) return json(hit);

    const [batter, pitcher] = await Promise.all([
      parseLeaders('Hitter.aspx'),
      parseLeaders('Pitcher.aspx'),
    ]);
    const result = { batter, pitcher, source: 'koreabaseball.com' };
    if (batter.rows.length || pitcher.rows.length) {
      cache.set('leaders', result);
    }
    return json(result);
  } catch (err) {
    return json({
      batter: { columns: [], rows: [] },
      pitcher: { columns: [], rows: [] },
      error: String(err && err.message ? err.message : err),
    });
  }
}
