import { json } from '../lib/respond.js';
import { ttlCache } from '../lib/cache.js';
import { stripTags } from '../lib/html.js';

// 원본 api/main.py:1399-1402 의 _KBO_TEAM_CODE 입니다.
// KBO 표기명 -> 대시보드 엠블럼 코드(assets/logos/{code}.png).
export const KBO_TEAM_CODE = {
  LG: 'LG', KT: 'KT', 두산: 'OB', 삼성: 'SS', KIA: 'HT',
  롯데: 'LT', SSG: 'SK', NC: 'NC', 키움: 'WO', 한화: 'HH',
};

// 역매핑. 원본 1406 행의 _KBO_CODE_TO_TEAM 입니다.
// /schedule 의 투수 이름을 players.player_id 로 맞출 때 팀을 좁히는 데 씁니다.
export const KBO_CODE_TO_TEAM = Object.fromEntries(
  Object.entries(KBO_TEAM_CODE).map(([team, code]) => [code, team]),
);

const cache = ttlCache(300); // 원본 _STANDINGS_TTL = 300

/**
 * TeamRank.aspx 의 순위표를 읽습니다.
 *
 * summary="순위..." 인 표만 봅니다. 같은 페이지에 summary="팀간승패표" 인
 * 표가 또 있어서, 그걸 같이 읽으면 행이 두 배가 됩니다.
 */
export function parseStandings(page) {
  const table = /<table[^>]*summary="순위[^"]*"[^>]*>([\s\S]*?)<\/table>/.exec(page);
  if (!table) return [];

  const tbody = /<tbody>([\s\S]*?)<\/tbody>/.exec(table[1]);
  const body = tbody ? tbody[1] : table[1];

  const teams = [];
  for (const tr of body.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)) {
    const cells = [...tr[1].matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)]
      .map((m) => stripTags(m[1]).trim());
    // 원본 조건: len(cells) >= 8 and cells[0].isdigit()
    if (cells.length < 8) continue;
    if (!/^\d+$/.test(cells[0])) continue;

    const name = cells[1];
    teams.push({
      rank: Number.parseInt(cells[0], 10),
      team: name,
      code: KBO_TEAM_CODE[name] || '',
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
  return teams;
}

export async function standings() {
  try {
    const hit = cache.get('rank');
    if (hit) return json(hit);

    const res = await fetch(
      'https://www.koreabaseball.com/Record/TeamRank/TeamRank.aspx',
      { headers: { 'user-agent': 'Mozilla/5.0' } },
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const page = await res.text();

    const teams = parseStandings(page);
    const result = {
      count: teams.length,
      teams,
      source: 'koreabaseball.com',
    };
    // 원본도 teams 가 비면 캐시하지 않습니다. 일시 실패를 5분간 물고 있지
    // 않으려는 것입니다.
    if (teams.length) cache.set('rank', result);
    return json(result);
  } catch (err) {
    // 원본은 예외 시 200 과 함께 error 필드를 돌려줍니다. 500 이 아닙니다.
    return json({
      count: 0,
      teams: [],
      error: String(err && err.message ? err.message : err),
    });
  }
}
