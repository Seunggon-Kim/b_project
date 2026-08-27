import { json } from '../lib/respond.js';
import { ttlCache } from '../lib/cache.js';
import { stripTags } from '../lib/html.js';

// 원본 api/main.py:1399-1402 의 _KBO_TEAM_CODE 입니다.
// KBO 표기명 -> 대시보드 엠블럼 코드(assets/logos/{code}.png).
export const KBO_TEAM_CODE = {
  LG: 'LG', KT: 'KT', 두산: 'OB', 삼성: 'SS', KIA: 'HT',
  롯데: 'LT', SSG: 'SK', NC: 'NC', 키움: 'WO', 한화: 'HH',

  // 옛 이름입니다. 1982~2014 기록을 넣으면서 필요해졌습니다.
  //
  // 프랜차이즈 코드는 그대로라 로고 파일도 그대로 씁니다(MBC 는
  // LG.png, 해태는 HT.png). 이름만 그 시즌 것으로 다릅니다.
  //
  // 이게 없으면 홈 화면 개인 순위에서 옛 시즌을 골랐을 때 코드가
  // 빈 문자열이 되어 **로고가 조용히 안 나옵니다.** 오류가 아니라
  // 그냥 안 보이는 종류입니다.
  //
  // 변천은 KBO 기록실 드롭다운에서 읽었습니다
  // (migration/teams_by_season.json).
  MBC: 'LG',                              // 1982~1989, 이후 LG
  OB: 'OB',                               // 1982~1998, 이후 두산
  해태: 'HT',                              // 1982~2000, 이후 KIA
  빙그레: 'HH',                            // 1986~1993, 이후 한화
  SK: 'SK',                               // 2000~2020, 이후 SSG
  우리: 'WO', 히어로즈: 'WO', 넥센: 'WO',    // 2008~2018, 이후 키움

  // 해체팀 둘입니다. 현대 로고는 KBO CDN 에 남아 있어 받아 두었고,
  // 쌍방울은 어디에도 없어 이름만 나옵니다.
  삼미: 'HD', 청보: 'HD', 태평양: 'HD', 현대: 'HD',  // 1982~2007
  쌍방울: 'SB',                                    // 1991~1999
};

// 역매핑. 원본 1406 행의 _KBO_CODE_TO_TEAM 입니다.
// /schedule 의 투수 이름을 players.player_id 로 맞출 때 팀을 좁히는 데 씁니다.
//
// **여기는 반드시 현재 팀명이어야 합니다.** 위 표를 그대로 뒤집으면
// 한 코드에 이름이 여럿이라 마지막 것이 이깁니다. 옛 이름을 더한
// 뒤에 실제로 `LG -> MBC`, `HT -> 해태`, `WO -> 넥센` 이 되었습니다.
// 그러면 오늘 경기의 투수를 "MBC 소속" 으로 찾게 되어 링크가 통째로
// 깨집니다. 오류는 안 나고 이름만 안 눌립니다.
//
// 옛 이름은 로고를 찾는 한 방향(이름 -> 코드)에만 쓰고, 되돌아오는
// 쪽은 현재 팀으로 고정합니다.
export const KBO_CODE_TO_TEAM = {
  LG: 'LG', KT: 'KT', OB: '두산', SS: '삼성', HT: 'KIA',
  LT: '롯데', SK: 'SSG', NC: 'NC', WO: '키움', HH: '한화',
};

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
