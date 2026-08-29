import { json } from '../lib/respond.js';
import { ttlCache } from '../lib/cache.js';
import { kstToday } from '../lib/kst.js';

// KBO 퓨처스리그 일정/결과 (실시간 스코어보드 프록시).
//
// 원본 api/main.py:1230-1371 의 _futures_teams_map / _futures_scoreboard /
// _futures_int / get_futures_schedule 을 옮긴 것입니다.
//
// Schedule.asmx(스케줄 리스트)는 진행 중 경기를 0:0으로만 표시(라이브 스코어
// 없음)하므로, 1군(Naver)처럼 실시간 스코어보드 GetKboGameList(leId=2)를
// 프록시합니다. 라이브 스코어·현재 이닝·등판 투수·승/패/세이브까지 제공하며
// 과거 날짜·교류전도 동일하게 처리합니다.
// (data_collection/futures_schedule.py + futures_games 테이블은 분석용
// 웨어하우스로 별도 유지됩니다.)

const cache = ttlCache(30); // 원본 _FUTURES_SCHED_TTL = 30 (라이브 갱신)

// 원본 _FUTURES_STATE 입니다. GAME_STATE_SC -> status 문자열.
const FUTURES_STATE = { 1: 'scheduled', 2: 'live', 3: 'final' };
const FUTURES_SRID = '0,9,10'; // 0=정규, 10=교류전 (모두 포함)
const FUTURES_SB_URL = 'https://www.koreabaseball.com/ws/Main.asmx/GetKboGameList';

/**
 * 원본 _futures_teams_map 입니다. code -> {display_name, division}
 * (futures_teams 마스터).
 *
 * 원본은 요청마다 SQLite 를 열어 읽으므로 여기서도 요청(캐시 미스)마다
 * D1 을 한 번 읽습니다. 13행짜리 작은 표라 쿼리 1개면 됩니다.
 */
async function futuresTeamsMap(env) {
  const { results } = await env.DB.prepare(
    'SELECT code, display_name, division FROM futures_teams',
  ).all();
  return new Map(results.map((r) => [r.code, r]));
}

/**
 * 원본 _futures_scoreboard(ymd) 입니다.
 * GetKboGameList(leId=2, date=YYYYMMDD) -> game 리스트 (BOM 처리).
 *
 * 원본은 requests.post(data={...}) 로 application/x-www-form-urlencoded 를
 * 보냅니다. body 에 URLSearchParams 를 주면 fetch 가 같은 content-type 으로
 * 같은 인코딩(쉼표도 %2C)을 만들어 보냅니다.
 *
 * 응답 선두에 BOM 이 붙어 있어 원본은 utf-8-sig 로 디코드합니다. 여기서는
 * text() 로 받아 앞의 \uFEFF 를 지운 뒤 JSON.parse 합니다.
 */
async function futuresScoreboard(ymd) {
  const res = await fetch(FUTURES_SB_URL, {
    method: 'POST',
    body: new URLSearchParams({ leId: '2', srId: FUTURES_SRID, date: ymd }),
    headers: {
      'user-agent': 'Mozilla/5.0',
      referer: 'https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx',
      'x-requested-with': 'XMLHttpRequest',
    },
    signal: AbortSignal.timeout(8000), // 원본 timeout=8
  });
  // 원본 raise_for_status() 자리입니다. 예외 메시지 문구만 다릅니다.
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const text = (await res.text()).replace(/^\uFEFF/, '');
  const data = JSON.parse(text);
  // 원본 data.get("game") or [] 입니다. game 이 null 이어도 빈 리스트입니다.
  return data.game || [];
}

/**
 * 원본 _futures_int 입니다. 파이썬 int(v) 와 같게 동작합니다.
 * 정수(정수 문자열 포함)만 숫자로 읽고, 그 외("", null 등)는 전부 null
 * 입니다. 변환 실패가 0 이 아니라 null 인 것이 계약입니다. 예정·취소
 * 경기의 점수를 0:0 으로 보이게 하지 않기 위함입니다.
 */
function futuresInt(v) {
  if (typeof v === 'number' && Number.isFinite(v)) return Math.trunc(v);
  if (typeof v === 'string' && /^\s*[+-]?\d+\s*$/.test(v)) {
    return Number.parseInt(v, 10);
  }
  return null;
}

/**
 * 원본 get_futures_schedule (api/main.py:1276-1371) 입니다.
 * KBO 퓨처스리그 일정/결과 (실시간 스코어보드 프록시). date=YYYY-MM-DD
 * (미지정 시 KST 오늘). 30초 캐시. 실패 시 500 이 아니라 200 + error
 * 필드를 돌려줍니다.
 */
/**
 * 경기 목록에 나온 선수 이름을 모읍니다(중복·빈 값 제외).
 *
 * 퓨처스 카드의 선수 이름에 링크가 없었습니다. 1군 카드는 선발·승패
 * 투수가 모두 링크인데 퓨처스만 그냥 글자였습니다. KBO 퓨처스 피드가
 * 이름만 주고 선수 ID 를 주지 않기 때문입니다.
 */
export function collectNames(games) {
  const out = [];
  const seen = new Set();
  for (const g of games || []) {
    const d = g.decisions || {};
    for (const v of [d.win, d.lose, d.save, g.currentPitcher, g.currentBatter]) {
      const name = String(v || '').trim();
      if (!name || seen.has(name)) continue;
      seen.add(name);
      out.push(name);
    }
  }
  return out;
}

/**
 * 이름으로 선수 ID 를 고릅니다. 못 고르면 null 입니다.
 *
 * 이름이 겹치면 팀으로 좁힙니다. 팀으로도 못 좁히면 **링크를 걸지
 * 않습니다.** 엉뚱한 선수로 보내느니 글자로 두는 편이 낫습니다.
 */
export function pickPlayerId(candidates, name, teamName) {
  const key = String(name || '').trim();
  if (!key) return null;
  const hits = (candidates || []).filter(
    (c) => String(c.player_name || '').trim() === key);
  if (hits.length === 1) return hits[0].player_id;
  if (!hits.length) return null;
  const team = String(teamName || '').trim();
  if (!team) return null;
  const byTeam = hits.filter((c) => String(c.team || '').trim() === team);
  return byTeam.length === 1 ? byTeam[0].player_id : null;
}

export async function futures(request, env) {
  let date = null;
  try {
    date = new URL(request.url).searchParams.get('date');
    if (!date) date = kstToday();

    const hit = cache.get(date);
    if (hit) return json(hit);

    const rawGames = await futuresScoreboard(date.replace(/-/g, ''));
    const teams = await futuresTeamsMap(env);

    const games = [];
    for (const g of rawGames) {
      const state = String(g.GAME_STATE_SC || '');
      // CANCEL_SC_ID 가 "0"/""/누락이면 정상, 그 외("1" 등)면 취소입니다.
      const cancel = !['0', ''].includes(String(g.CANCEL_SC_ID || '0'));
      const status = cancel ? 'canceled' : (FUTURES_STATE[state] || 'scheduled');
      const final = status === 'final';
      const live = status === 'live';
      const show = final || live;

      const ac = g.AWAY_ID || '';
      const hc = g.HOME_ID || '';
      const at = teams.get(ac) || {};
      const ht = teams.get(hc) || {};
      // 스코어보드의 T=초 공격(원정), B=말 공격(홈)입니다.
      const aSc = show ? futuresInt(g.T_SCORE_CN) : null;
      const hSc = show ? futuresInt(g.B_SCORE_CN) : null;

      let winner = '';
      if (final && aSc !== null && hSc !== null) {
        winner = aSc > hSc ? 'AWAY' : (hSc > aSc ? 'HOME' : '');
      }

      let inning = '';
      if (live && g.GAME_INN_NO) {
        inning = `${g.GAME_INN_NO}회${g.GAME_TB_SC_NM || ''}`;
      }

      const sr = futuresInt(g.SR_ID);
      const statusInfo = cancel ? '취소'
        : (live ? inning : (final ? '종료' : '경기예정'));

      // 라이브 현재 타석. KBO 스코어보드의 T_P/B_P는 '투수/타자' 고정이
      // 아니라 공격측 기준 선수(원정=T_P, 홈=B_P)이고, 이닝 초/말
      // (GAME_TB_SC)에 따라 타자·투수가 뒤바뀝니다(초=원정 공격, 말=홈 공격).
      //   초(T): 타자=T_P(원정), 투수=B_P(홈 수비)
      //   말(B): 타자=B_P(홈),   투수=T_P(원정 수비)
      const tb = String(g.GAME_TB_SC || '');
      const tP = (g.T_P_NM || '').trim();
      const bP = (g.B_P_NM || '').trim();
      const curBatter = live ? (tb === 'T' ? tP : bP) : '';
      const curPitcher = live ? (tb === 'T' ? bP : tP) : '';

      games.push({
        // 파이썬은 키가 없으면 None 을 내보냅니다. JS 의 undefined 는
        // JSON.stringify 에서 키째 사라지므로 null 로 고정합니다.
        gameId: g.G_ID ?? null,
        time: g.G_TM || '',
        stadium: g.S_NM || '',
        seriesId: sr !== null ? sr : 0,
        series: sr === 10 ? '교류전' : '퓨처스리그',
        status,
        final,
        live,
        cancel,
        showScore: show,
        winner,
        currentInning: inning,
        statusInfo,
        currentPitcher: curPitcher,
        currentBatter: curBatter,
        away: {
          code: ac,
          name: at.display_name || g.AWAY_NM || ac,
          division: at.division || '',
          score: aSc,
        },
        home: {
          code: hc,
          name: ht.display_name || g.HOME_NM || hc,
          division: ht.division || '',
          score: hSc,
        },
        decisions: {
          win: final ? (g.W_PIT_P_NM || '') : '',
          lose: final ? (g.L_PIT_P_NM || '') : '',
          save: final ? (g.SV_PIT_P_NM || '') : '',
        },
      });
    }

    // 선수 ID 를 붙입니다. 이름만으로는 화면에서 링크를 걸 수 없습니다.
    //
    // 원천은 `futures_season_stats`(올 시즌 2군 기록)입니다. 이름이
    // 겹치면 팀으로 좁히고, 그래도 못 좁히면 링크를 걸지 않습니다.
    //
    // 이름을 한 번에 모아 한 번만 질의합니다. 경기마다 두드리면 하루
    // 다섯 경기에 열 번이 넘습니다.
    await attachPlayerIds(games, env);

    // 파이썬 튜플 정렬 (time, gameId) 그대로입니다. 둘 다 ASCII 라
    // 코드포인트 비교(<, >)로 결과가 같습니다.
    games.sort((a, b) => {
      const ta = a.time || '';
      const tb2 = b.time || '';
      if (ta !== tb2) return ta < tb2 ? -1 : 1;
      const ga = a.gameId || '';
      const gb = b.gameId || '';
      if (ga !== gb) return ga < gb ? -1 : 1;
      return 0;
    });

    const result = {
      date, count: games.length, games, source: 'koreabaseball.com',
    };
    cache.set(date, result);
    return json(result);
  } catch (err) {
    // 원본은 예외 시 200 과 함께 error 필드를 돌려줍니다. 500 이 아닙니다.
    return json({
      date,
      count: 0,
      games: [],
      error: String(err && err.message ? err.message : err),
    });
  }
}


/**
 * 경기 목록의 선수 이름에 ID 를 붙입니다.
 *
 * 실패해도 조용히 넘어갑니다. 링크가 없을 뿐 경기 카드는 그대로
 * 보여야 합니다.
 */
async function attachPlayerIds(games, env) {
  const names = collectNames(games);
  if (!names.length || !env || !env.DB) return;
  try {
    const marks = names.map(() => '?').join(',');
    const { results } = await env.DB.prepare(
      'SELECT player_id, player_name, team FROM futures_season_stats '
      + `WHERE season = (SELECT MAX(season) FROM futures_season_stats) `
      + `AND player_name IN (${marks})`,
    ).bind(...names).all();
    const cands = results || [];
    for (const g of games) {
      const d = g.decisions || {};
      // 승리투수는 이긴 팀, 패전투수는 진 팀입니다. 세이브는 이긴
      // 팀입니다. 그 팀으로 동명이인을 가립니다.
      const winTeam = g.winner === 'away' ? g.away?.name : g.home?.name;
      const loseTeam = g.winner === 'away' ? g.home?.name : g.away?.name;
      d.winId = pickPlayerId(cands, d.win, winTeam);
      d.loseId = pickPlayerId(cands, d.lose, loseTeam);
      d.saveId = pickPlayerId(cands, d.save, winTeam);
      // 진행 중인 경기는 어느 팀인지 알 수 없어 이름만으로 찾습니다.
      // 겹치면 링크가 안 걸립니다.
      g.currentPitcherId = pickPlayerId(cands, g.currentPitcher, null);
      g.currentBatterId = pickPlayerId(cands, g.currentBatter, null);
    }
  } catch {
    // 표가 아직 없는 환경입니다. 링크 없이 갑니다.
  }
}
