import { json } from '../lib/respond.js';
import { ttlCache } from '../lib/cache.js';
import { kstToday } from '../lib/kst.js';
import { kboFetchJson } from '../lib/naver.js';

// 1군 팀 순위입니다.
//
// 예전에는 KBO 기록실(koreabaseball.com TeamRank.aspx)을 그때그때 읽었습니다.
// 2026-10-14 시행 KBO 이용약관 제14조 차항(크롤링 등 자동화 수집 금지)에
// 따라 네이버 스포츠 API 로 바꿨습니다. 응답 모양은 그대로입니다. 다만
// 네이버는 최근 다섯 경기만 주고 최근 열 경기를 주지 않아 last10 은 빈
// 문자열입니다(지어내지 않습니다).

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

const NAVER_TEAMS_URL = 'https://api-gw.sports.naver.com/statistics/categories/kbo/seasons/%s/teams';
// 통계 주소는 브라우저 user-agent 와 Referer 가 있어야 답합니다.
const NAVER_HEADERS = {
  'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    + '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
  referer: 'https://m.sports.naver.com/',
};

// 숫자를 예전 KBO 표의 글자 모양으로 씁니다. 없으면 빈 문자열입니다.
function numText(v) {
  return v === null || v === undefined || v === '' ? '' : String(Number(v));
}

/**
 * 네이버 시즌 팀 기록(result.seasonTeamStats)을 예전 응답의 teams 로 바꿉니다.
 *
 * teamId 는 KBO 코드(KT·SS·OB·HT …)와 같습니다. 팀 이름은 KBO_CODE_TO_TEAM
 * (현재 팀 이름)으로 씁니다. 승률은 KBO 표처럼 소수 셋째 자리(0.500)입니다.
 */
export function parseNaverStandings(data) {
  const rows = (((data || {}).result || {}).seasonTeamStats) || [];
  return rows
    .filter((r) => r && r.teamId && Number.isFinite(Number(r.ranking)))
    .map((r) => ({
      rank: Number(r.ranking),
      team: KBO_CODE_TO_TEAM[r.teamId] || r.teamName || r.teamId,
      code: r.teamId,
      games: numText(r.gameCount),
      wins: numText(r.winGameCount),
      losses: numText(r.loseGameCount),
      draws: numText(r.drawnGameCount),
      pct: r.wra === null || r.wra === undefined ? '' : Number(r.wra).toFixed(3),
      gb: numText(r.gameBehind),
      last10: '',
      streak: r.continuousGameResult || '',
    }))
    .sort((a, b) => a.rank - b.rank || a.code.localeCompare(b.code));
}

/**
 * 1군 팀 순위입니다. 올해(한국 시각) 기록이 아직 없으면(개막 전) 지난해를
 * 돌려줍니다. 예전 KBO 기록실도 개막 전에는 지난 시즌 순위를 보여 줬습니다.
 */
export async function standings() {
  try {
    const hit = cache.get('rank');
    if (hit) return json(hit);

    const year = Number(kstToday().slice(0, 4));
    let teams = [];
    for (const y of [year, year - 1]) {
      teams = parseNaverStandings(
        await kboFetchJson(NAVER_TEAMS_URL.replace('%s', y), NAVER_HEADERS));
      if (teams.length) break;
    }
    const result = {
      count: teams.length,
      teams,
      source: 'sports.naver.com',
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

