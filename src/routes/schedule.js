import { json } from '../lib/respond.js';
import { ttlCache } from '../lib/cache.js';
import { kstToday } from '../lib/kst.js';
import { KBO_CODE_TO_TEAM } from './standings.js';

// KBO 경기 일정/결과 (Naver 스포츠 API 프록시).
//
// 원본 api/main.py:1083-1227 의 _kbo_fetch_json / _kbo_game_meta /
// _kbo_normalize_game / _kbo_game_decisions / get_schedule 과,
// 1409-1471 의 _players_has_col / _resolve_pitcher_id / _attach_pitcher_ids
// 를 옮긴 것입니다.

const cache = ttlCache(30); // 원본 _SCHEDULE_TTL = 30

/**
 * 원본 _kbo_fetch_json(url, timeout=8) 입니다.
 *
 * requests 의 timeout=8 은 연결·읽기 단위이고 AbortSignal.timeout 은 전체
 * 경과 시간이라 엄밀히는 다르지만, 8초를 넘겨 정상 응답이 오는 경우가
 * 없어 실질적인 차이는 없습니다.
 */
async function kboFetchJson(url) {
  const res = await fetch(url, {
    headers: { 'user-agent': 'Mozilla/5.0' },
    signal: AbortSignal.timeout(8000),
  });
  // 원본 raise_for_status() 자리입니다. 예외 메시지 문구만 다릅니다.
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// 원본 _kbo_game_meta 입니다. 실패한 경기는 null 로 두고 건너뜁니다.
async function kboGameMeta(gameId) {
  try {
    return await kboFetchJson(
      'https://api-gw.sports.naver.com/schedule/games/' + gameId,
    );
  } catch {
    return null;
  }
}

/**
 * 원본 _kbo_normalize_game 입니다. 응답 필드 이름이 여기서 정해집니다.
 *
 * score 는 값이 없으면 0 이 아니라 null 입니다. 예정 경기(showScore=false)의
 * 점수를 0:0 으로 보이게 하지 않기 위한 계약입니다.
 */
function kboNormalizeGame(meta) {
  const g = ((meta || {}).result || {}).game || {};
  // 파이썬 `if not g` 는 빈 dict 도 걸러냅니다. JS 의 빈 객체는 truthy 라
  // 키 개수로 같은 판정을 만듭니다.
  if (Object.keys(g).length === 0) return null;

  const status = g.statusCode || '';
  const final = status === 'RESULT' || status === 'ENDED';
  const live = status === 'LIVE' || status === 'PLAYING' || status === 'STARTED';
  const showScore = final || live;
  const dt = g.gameDateTime || '';
  const timeStr = dt.length >= 16 ? dt.slice(11, 16) : '';

  // 파이썬 int(v) 와 같게 동작합니다. 정수(정수 문자열 포함)만 숫자로 읽고,
  // 그 외("", null, "3.5" 등)는 전부 null 입니다.
  const score = (v) => {
    if (typeof v === 'number' && Number.isFinite(v)) return Math.trunc(v);
    if (typeof v === 'string' && /^\s*[+-]?\d+\s*$/.test(v)) {
      return Number.parseInt(v, 10);
    }
    return null;
  };

  const team = (prefix) => ({
    name: g[prefix + 'TeamName'] || '',
    code: g[prefix + 'TeamCode'] || '',
    emblem: g[prefix + 'TeamEmblemUrl'] || '',
    score: showScore ? score(g[prefix + 'TeamScore']) : null,
    starter: g[prefix + 'StarterName'] || '',
    // 진행 중인 경기에서 현재 마운드에 등판 중인 투수 (예정·종료 시엔 빈 문자열)
    currentPitcher: live ? (g[prefix + 'CurrentPitcherName'] || '') : '',
  });

  return {
    // 파이썬은 키가 없으면 None 을 내보냅니다. JS 의 undefined 는
    // JSON.stringify 에서 키째 사라지므로 null 로 고정합니다.
    gameId: g.gameId ?? null,
    datetime: dt,
    time: timeStr,
    stadium: g.stadium || '',
    statusCode: status,
    statusInfo: g.statusInfo || '',
    currentInning: g.currentInning || '',
    broadChannel: g.broadChannel || '',
    cancel: Boolean(g.cancel),
    final,
    live,
    showScore,
    winner: g.winner || '',
    home: team('home'),
    away: team('away'),
    // 종료 경기의 승/패/세이브 투수 (schedule 본체에서 record 엔드포인트로 채움)
    decisions: { win: '', lose: '', save: '' },
  };
}

/**
 * 원본 _kbo_game_decisions 입니다. 종료 경기의 승리/패전/세이브 투수.
 * record 엔드포인트 pitchingResult[].wls (W=승, L=패, S=세이브, H=홀드)에서
 * 추출합니다. 세이브 투수는 정의상 승리팀 소속이므로 별도 팀 판별이
 * 필요 없습니다. 실패하면 원본처럼 조용히 빈 값을 돌려줍니다.
 */
async function kboGameDecisions(gameId) {
  const out = { win: '', lose: '', save: '' };
  try {
    const data = await kboFetchJson(
      'https://api-gw.sports.naver.com/schedule/games/' + gameId + '/record',
    );
    const pr = (((data || {}).result || {}).recordData || {}).pitchingResult || [];
    for (const p of pr) {
      const wls = (p.wls || '').toUpperCase();
      const name = p.name || '';
      if (wls === 'W' && !out.win) out.win = name;
      else if (wls === 'L' && !out.lose) out.lose = name;
      else if (wls === 'S' && !out.save) out.save = name;
    }
  } catch {
    // 원본과 같이 무시합니다.
  }
  return out;
}

// 원본 _players_cols_cache 입니다. isolate 가 살아 있는 동안만 유지됩니다.
let playersColsCache = null;

/**
 * 원본 _players_has_col 입니다. players 테이블에 컬럼이 있는지(스키마 캐시).
 * is_active 등 신규 컬럼이 없는 구버전 DB 스냅샷에서도 안전하게 동작하기
 * 위함입니다. D1 은 PRAGMA table_info 를 지원합니다.
 */
async function playersHasCol(env, col) {
  if (playersColsCache === null) {
    const { results } = await env.DB.prepare('PRAGMA table_info(players)').all();
    playersColsCache = new Set(results.map((r) => r.name));
  }
  return playersColsCache.has(col);
}

/**
 * 원본 _resolve_pitcher_id 의 판정부입니다.
 *
 * 경기 카드 투수 이름 + 팀 엠블럼 코드 -> players.player_id.
 * is_active 컬럼이 있으면 현역만 후보로 둡니다(은퇴/동명 중복 선수로의
 * 오링크 방지). 단일 매칭이면 그 id, 동명이인이면 투수(position='투수')로
 * 1명만 좁혀질 때만 반환합니다. 미매칭·모호 시 null 입니다(프론트는 일반
 * 텍스트, 딥링크 없음).
 *
 * 원본은 이 안에서 SELECT 를 날리지만, 여기서는 attachPitcherIds 가 미리
 * 한 번에 가져온 행을 이름+팀으로 걸러 씁니다. 결과는 같습니다.
 */
function resolvePitcherId(byNameTeam, hasActive, name, code) {
  if (!name || !code) return null;
  const teamId = KBO_CODE_TO_TEAM[code];
  if (!teamId) return null;
  // 키 구분자는 이름·팀명에 절대 못 들어가는 NUL 문자입니다(공백은 외국인
  // 등록명에 들어갈 수 있어 피합니다).
  let rows = byNameTeam.get(name + '\u0000' + teamId) || [];
  if (hasActive) rows = rows.filter((r) => r.is_active === 1); // 현역만 링크
  if (rows.length === 0) return null;
  if (rows.length === 1) return rows[0].player_id;
  const pitchers = rows.filter((r) => (r.position || '') === '투수');
  return pitchers.length === 1 ? pitchers[0].player_id : null;
}

// 경기 하나에서 (투수 이름, 팀 코드) 쌍을 뽑습니다. attachPitcherIds 의
// 수집 단계와 부착 단계가 같은 팀 판별을 쓰도록 한곳에 모았습니다.
// 팀 판별: 선발/현재투수=원정·홈 각 팀, 승=승리팀·패=패전팀·세=승리팀.
function pitcherPairsOf(game) {
  const home = game.home || {};
  const away = game.away || {};
  const winner = (game.winner || '').toUpperCase();
  const winCode = winner === 'HOME' ? home.code : (winner === 'AWAY' ? away.code : null);
  const loseCode = winner === 'HOME' ? away.code : (winner === 'AWAY' ? home.code : null);
  const d = game.decisions || {};
  return [
    [away.starter, away.code],
    [home.starter, home.code],
    [away.currentPitcher, away.code],
    [home.currentPitcher, home.code],
    [d.win, winCode],
    [d.lose, loseCode],
    [d.save, winCode],
  ];
}

/**
 * 원본 _attach_pitcher_ids 입니다. schedule 응답의 각 경기 투수 이름에
 * player_id 를 부착합니다(매칭된 것만, 캐시 저장 전에 호출).
 *
 * 원본과 다른 점: 원본은 이름마다 SELECT 를 한 번씩 날립니다(경기 5개면
 * 20회 이상). Workers 는 호출당 D1 쿼리 50개 한도가 있어, 이름을 전부
 * 모아 IN 절 한 번으로 가져온 뒤 메모리에서 이름+팀으로 거릅니다.
 * WHERE player_name=? AND team_id=? 를 "이름 IN + JS 팀 필터"로 바꾼
 * 것이라 (이름, 팀)별 후보 행 집합은 원본과 같습니다.
 * 하루 최대 10경기 x 이름 7개 = 70개 미만이라 D1 바인딩 한도(100개)
 * 안입니다.
 */
async function attachPitcherIds(env, games) {
  if (!games.length) return;

  // 조회가 필요한 이름을 모읍니다. 이름·팀 코드가 비거나 코드가 팀으로
  // 안 풀리면 원본도 쿼리 없이 null 이므로 후보에서 뺍니다.
  const names = new Set();
  for (const g of games) {
    for (const [name, code] of pitcherPairsOf(g)) {
      if (name && code && KBO_CODE_TO_TEAM[code]) names.add(name);
    }
  }

  const byNameTeam = new Map();
  let hasActive = false;
  if (names.size) {
    hasActive = await playersHasCol(env, 'is_active');
    const list = [...names];
    const sel = 'SELECT player_id, player_name, team_id, position'
      + (hasActive ? ', is_active' : '')
      + ' FROM players WHERE player_name IN ('
      + list.map(() => '?').join(',') + ')';
    const { results } = await env.DB.prepare(sel).bind(...list).all();
    for (const r of results) {
      const key = r.player_name + '\u0000' + r.team_id;
      const arr = byNameTeam.get(key);
      if (arr) arr.push(r);
      else byNameTeam.set(key, [r]);
    }
  }

  for (const g of games) {
    const home = g.home || {};
    const away = g.away || {};
    const pairs = pitcherPairsOf(g);
    const id = (i) => resolvePitcherId(byNameTeam, hasActive, pairs[i][0], pairs[i][1]);
    away.starterId = id(0);
    home.starterId = id(1);
    away.currentPitcherId = id(2);
    home.currentPitcherId = id(3);
    const d = g.decisions || {};
    d.winId = id(4);
    d.loseId = id(5);
    d.saveId = id(6);
    g.decisions = d;
  }
}

/**
 * 원본 get_schedule (api/main.py:1177-1227) 입니다.
 * KBO 경기 일정/결과 (Naver 스포츠 API 프록시). date=YYYY-MM-DD (미지정 시
 * KST 오늘). 실패 시 500 이 아니라 200 + error 필드를 돌려줍니다.
 */
export async function schedule(request, env) {
  let date = null;
  try {
    date = new URL(request.url).searchParams.get('date');
    if (!date) date = kstToday();
    const target = date.replace(/-/g, '');

    const hit = cache.get(date);
    if (hit) return json(hit);

    const cal = await kboFetchJson(
      'https://api-gw.sports.naver.com/schedule/calendar'
      + '?upperCategoryId=kbaseball&categoryIds=kbo&date=' + date,
    );
    const gids = [];
    for (const d of (cal.result || {}).dates || []) {
      const dkey = String(d.ymd || d.date || '').replace(/-/g, '');
      if (dkey === target) {
        for (const gi of d.gameInfos || []) {
          if (gi.gameId) gids.push(gi.gameId);
        }
        break;
      }
    }

    const games = [];
    if (gids.length) {
      // 원본은 ThreadPoolExecutor(max_workers=8) 입니다. fetch 대기는
      // Workers CPU 시간에 세지 않으므로 Promise.all 로 한 번에 보냅니다.
      const metas = await Promise.all(gids.map(kboGameMeta));
      for (const m of metas) {
        const ng = kboNormalizeGame(m);
        if (ng) games.push(ng);
      }

      // 종료 경기는 승/패/세이브 투수를 record 엔드포인트에서 병렬로 보강합니다.
      const finals = games.filter((ng) => ng.final && ng.gameId);
      if (finals.length) {
        const decs = await Promise.all(
          finals.map((ng) => kboGameDecisions(ng.gameId)),
        );
        finals.forEach((ng, i) => { ng.decisions = decs[i]; });
      }

      // 파이썬 튜플 정렬 (datetime, gameId) 그대로입니다. 둘 다 ASCII 라
      // 코드포인트 비교(<, >)로 결과가 같습니다.
      games.sort((a, b) => {
        const da = a.datetime || '';
        const db = b.datetime || '';
        if (da !== db) return da < db ? -1 : 1;
        const ga = a.gameId || '';
        const gb = b.gameId || '';
        if (ga !== gb) return ga < gb ? -1 : 1;
        return 0;
      });
    }

    await attachPitcherIds(env, games); // 투수 이름 -> player_id 부착(캐시 저장 전)
    const result = { date, count: games.length, games };
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
