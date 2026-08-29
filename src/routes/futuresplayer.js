import { json } from '../lib/respond.js';
import { ttlCache } from '../lib/cache.js';
import { stripTags } from '../lib/html.js';
import { FUTURES_TEAM_CODE } from './futuresrecord.js';

// 퓨처스(2군) 선수 한 명의 프로필과 올 시즌 기록입니다.
//
// ## 왜 필요한가
//
// 1군 기록이 한 번도 없는 선수는 우리 `players` 표에 아예 없습니다.
// 그 표는 1군 공식 기록에서 만들기 때문입니다. 그래서 `/players/:id`
// 가 404 를 돌려주고 선수 분석 화면이 통째로 비었습니다.
//
//     https://bstats.pages.dev/pages/player-analytics?id=56443
//
// 홈 화면 퓨처스 개인 순위에서 선수를 눌러 들어가면 그렇게 됩니다.
// 퓨처스 상위권 42명 중 10명이 여기에 해당합니다.
//
// KBO 퓨처스 선수 페이지 한 장에 프로필과 올 시즌 기록이 다 있어서
// 그것으로 채웁니다.
//
// ## D1 에 쌓지 않습니다
//
// `routes/futuresrecord.js`(퓨처스 순위·개인 기록)와 같은 방식입니다.
// 화면이 늘 최신만 보여 주면 되고, 쌓으면 daily 에 단계가 하나 더
// 늘기 때문입니다.
//
// ## 없는 것
//
// **시즌별 기록이 없습니다.** KBO 퓨처스 선수 페이지는 올 시즌 요약과
// 최근 경기만 줍니다. 1군 화면의 연도별 표에 해당하는 자료가 없습니다.
//
// wOBA·wRC+ 도 없습니다. 그 지표는 play_by_play 로 계산하는데 퓨처스는
// 타석 단위 자료가 공개되지 않습니다. 구종 분석과 투구 위치도 같은
// 이유로 만들 수 없습니다. 화면이 퓨처스 모드에서 그 카드들을 숨깁니다.

const cache = ttlCache(300); // 퓨처스 순위와 같은 5분

const BASE = 'https://www.koreabaseball.com/Futures/Player';
const UA = { 'user-agent': 'Mozilla/5.0' };

// 프로필 항목입니다. ASP.NET 컨트롤 id 의 꼬리로 찾습니다.
//
// 앞부분(`cphContents_cphContents_cphContents_ucPlayerProfile_`)은
// 페이지마다 달라질 수 있어 쓰지 않습니다.
const PROFILE_FIELDS = {
  name: 'lblName',
  back_number: 'lblBackNo',
  birthday: 'lblBirthday',
  position: 'lblPosition',
  height_weight: 'lblHeightWeight',
  career: 'lblCareer',
  salary: 'lblSalary',
  draft: 'lblDraft',
};

function labelValue(page, id) {
  const re = new RegExp(`ucPlayerProfile_${id}"[^>]*>([\\s\\S]*?)</span>`);
  const m = re.exec(page);
  if (!m) return null;
  const v = stripTags(m[1]).trim();
  return v === '' ? null : v;
}

/**
 * '2002년 06월 04일' 을 '20020604' 로 바꿉니다.
 *
 * 1군 `players.birthday` 와 같은 모양이라 화면의 나이 계산 코드를
 * 그대로 쓸 수 있습니다.
 */
function birthdayYmd(text) {
  if (!text) return null;
  const m = /(\d{4})\D+(\d{1,2})\D+(\d{1,2})/.exec(text);
  if (!m) return null;
  return m[1] + m[2].padStart(2, '0') + m[3].padStart(2, '0');
}

// 투타 표기를 1군 `players.throw` / `players.bat` 과 같은 한 글자로
// 바꿉니다. 화면의 formatThrowBat 이 'R'/'L'/'S' 를 기대합니다.
const HAND = { 우: 'R', 좌: 'L', 양: 'S' };

/**
 * '내야수(우투좌타)' 를 갈라 냅니다.
 *
 * 괄호가 없거나 모양이 다르면 손대지 않고 null 을 돌려줍니다. KBO 가
 * 표기를 바꿔도 화면이 '-' 를 보일 뿐 깨지지 않습니다.
 */
function splitPosition(text) {
  if (!text) return { position_name: null, throw: null, bat: null };
  const m = /^\s*([^(]+?)\s*\(\s*(.)투\s*(.)타\s*\)/.exec(text);
  if (!m) return { position_name: text.trim() || null, throw: null, bat: null };
  return {
    position_name: m[1].trim(),
    throw: HAND[m[2]] ?? null,
    bat: HAND[m[3]] ?? null,
  };
}

/** '185cm/87kg' 을 숫자 둘로 바꿉니다. */
function splitHeightWeight(text) {
  if (!text) return { height: null, weight: null };
  const m = /(\d+)\s*cm\s*\/\s*(\d+)\s*kg/.exec(text);
  if (!m) return { height: null, weight: null };
  return { height: Number(m[1]), weight: Number(m[2]) };
}

/**
 * '3000만원' 을 30000000 으로 바꿉니다.
 *
 * 화면의 formatMoney 가 숫자를 받아 세 자리마다 쉼표를 찍습니다.
 * '1억 5000만원' 같은 표기도 더해서 셉니다.
 */
function salaryWon(text) {
  if (!text) return null;
  let won = 0;
  let seen = false;
  const eok = /(\d+)\s*억/.exec(text);
  if (eok) { won += Number(eok[1]) * 100000000; seen = true; }
  const man = /(\d+)\s*만/.exec(text);
  if (man) { won += Number(man[1]) * 10000; seen = true; }
  if (!seen) {
    const plain = /(\d[\d,]*)\s*원/.exec(text);
    if (plain) { won = Number(plain[1].replace(/,/g, '')); seen = true; }
  }
  return seen ? won : null;
}

/**
 * 선수 프로필입니다. 없는 값은 null 입니다.
 *
 * KBO 표기 그대로인 값(`position`, `height_weight`, `salary`)과, 1군
 * `players` 행과 같은 모양으로 바꾼 값(`position_name`, `throw`, `bat`,
 * `height`, `weight`, `salary_won`)을 함께 돌려줍니다. 화면이 1군 선수를
 * 그리던 코드를 그대로 쓸 수 있게 하려는 것입니다.
 */
export function parseProfile(page) {
  const out = {};
  for (const [key, id] of Object.entries(PROFILE_FIELDS)) {
    out[key] = labelValue(page, id);
  }
  out.birthday_ymd = birthdayYmd(out.birthday);

  // **등번호 자리가 현재 등록 여부를 알려 줍니다.**
  //
  //     '29'  등록된 선수            김광현(SSG)
  //     '#'   은퇴                   이대호, 유민상, 전상렬
  //     ''    등록 안 됨(계약 종료)  타무라(56218, 26 두산 아시아쿼터)
  //
  // 계약이 끝난 선수에게 옛 소속을 그대로 보여 주면 아직 그 팀에
  // 있는 것처럼 읽힙니다. 화면이 소속과 등번호를 감춥니다.
  //
  // '00' 은 실제로 있는 등번호입니다. 숫자로 바꾸면 0 이 되어
  // 사라지므로 문자열 그대로 둡니다.
  if (out.back_number === '#') out.back_number = null;
  out.registered = out.back_number != null;

  Object.assign(out, splitPosition(out.position));
  Object.assign(out, splitHeightWeight(out.height_weight));
  out.salary_won = salaryWon(out.salary);

  // 선수 사진입니다. KBO 가 `//host/...` 로 줘서 그대로 쓰면
  // 화면에서 깨집니다. 같은 호스트에 스크립트도 있어 경로로 거릅니다.
  const img = /src="(\/\/[^"]*KBO_IMAGE\/person\/[^"]+)"/.exec(page);
  out.photo = img ? `https:${img[1]}` : null;
  return out;
}

/** 표 안의 `<th>` 들입니다. */
function headersOf(table) {
  return [...table.matchAll(/<th[^>]*>([\s\S]*?)<\/th>/g)]
    .map((m) => stripTags(m[1]).trim());
}

/** 표 본문의 행들입니다. 각 행은 셀 문자열 배열입니다. */
function bodyRows(table) {
  const tbody = /<tbody>([\s\S]*?)<\/tbody>/.exec(table);
  const body = tbody ? tbody[1] : table;
  const rows = [];
  for (const tr of body.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)) {
    const cells = [...tr[1].matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)]
      .map((m) => stripTags(m[1]).trim());
    if (cells.length) rows.push(cells);
  }
  return rows;
}

function tablesOf(page) {
  return [...page.matchAll(/<table[^>]*>([\s\S]*?)<\/table>/g)].map((m) => m[0]);
}

/**
 * 올 시즌 요약 한 줄입니다. 첫 번째 표입니다.
 *
 * 타자는 `팀명 AVG G AB R H ...`, 투수는 `팀명 ERA G W L SV ...` 입니다.
 * 컬럼을 우리가 정하지 않고 페이지에 있는 그대로 돌려줍니다. KBO 가
 * 항목을 바꿔도 화면이 따라갑니다.
 */
export function parseSeasonRow(page) {
  const tables = tablesOf(page);
  if (!tables.length) return { columns: [], cells: [] };
  const columns = headersOf(tables[0]);
  const rows = bodyRows(tables[0]);

  // **안내 한 줄은 기록이 아닙니다.** 기록이 없는 쪽 페이지에도 표는
  // 있고, KBO 가 그 자리에 문구를 한 칸으로 넣습니다.
  //
  //     <tr><td colspan="16">기록이 없습니다.</td></tr>
  //
  // 이것을 기록으로 세는 바람에 투수를 타자로 판정했습니다. 타자·투수
  // 두 페이지를 다 부르고 기록이 있는 쪽을 고르는데, 없는 쪽이 먼저
  // 잡혔습니다. 화면에는 값이 전부 '-' 인 타자 표가 나왔고 팀 이름
  // 자리에 '기록이 없습니다.' 가 찍혔습니다.
  const first = rows.length ? rows[0] : [];
  const real = first.length >= columns.length;
  return { columns, cells: real ? first : [] };
}

/**
 * 최근 경기별 기록입니다. 두 번째 표입니다.
 *
 * **헤더 행에 합계까지 붙어 있습니다.** KBO 가 `일자 구분 상대 ... GDP`
 * 뒤에 `합계` 와 그 숫자들을 같은 `<th>` 로 넣습니다. 그대로 쓰면
 * 컬럼이 데이터보다 많아져 화면이 밀립니다. `합계` 에서 자릅니다.
 */
export function parseRecentGames(page) {
  const tables = tablesOf(page);
  if (tables.length < 2) return { columns: [], rows: [] };
  const all = headersOf(tables[1]);
  const cut = all.indexOf('합계');
  const columns = cut === -1 ? all : all.slice(0, cut);
  return { columns, rows: bodyRows(tables[1]) };
}

// KBO 이름 검색 결과의 컬럼입니다. 순서가 고정입니다.
//
//     등번호 선수명 팀명 포지션 생년월일 체격 출신교
const SEARCH_COLUMNS = ['back_number', 'player_name', 'team_id',
                        'position', 'birthday', 'size', 'career'];

/**
 * KBO 이름 검색 결과를 읽습니다.
 *
 * `players` 표는 1군 공식 기록에서 만들어서 2군에만 있는 선수는 아예
 * 없습니다. 이름을 쳐도 "검색 결과가 없습니다" 만 나왔습니다.
 *
 * 우리 표와 같은 필드 이름으로 맞춰 돌려줍니다. 화면이 1군 검색 결과와
 * 같은 코드로 그릴 수 있습니다.
 *
 * 선수 ID 가 없는 줄은 버립니다. 눌러도 열 수가 없습니다.
 */
export function parseSearchRows(page) {
  const out = [];
  for (const tb of page.matchAll(/<table[^>]*>([\s\S]*?)<\/table>/g)) {
    const tbody = /<tbody>([\s\S]*?)<\/tbody>/.exec(tb[1]);
    const body = tbody ? tbody[1] : tb[1];
    for (const tr of body.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)) {
      const raw = [...tr[1].matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)].map((m) => m[1]);
      if (raw.length < SEARCH_COLUMNS.length) continue;
      const idm = /playerId=(\d+)/.exec(tr[1]);
      if (!idm) continue;

      const row = { player_id: Number.parseInt(idm[1], 10) };
      raw.forEach((cell, i) => {
        const key = SEARCH_COLUMNS[i];
        if (!key) return;
        const v = stripTags(cell).trim();
        row[key] = v === '' ? null : v;
      });

      // 생년월일은 '1999-09-15' 로 옵니다. 1군 players.birthday 와 같은
      // YYYYMMDD 로 맞춥니다.
      row.birthday = birthdayYmd(row.birthday);
      // 체격은 '188cm, 86kg' 입니다. 값이 없으면 'cm, kg' 만 옵니다.
      const sz = /(\d+)\s*cm\s*,?\s*(\d+)\s*kg/.exec(row.size || '');
      row.height = sz ? Number(sz[1]) : null;
      row.weight = sz ? Number(sz[2]) : null;
      delete row.size;
      // 화면이 2군 화면으로 열도록 표시해 둡니다.
      row.futures = true;
      out.push(row);
    }
  }
  return out;
}

/**
 * 이름으로 선수를 찾습니다. 1군·2군을 모두 돌려줍니다.
 *
 * 화면은 우리 `players` 검색이 빈손일 때만 이리로 옵니다. 대부분의
 * 검색은 D1 안에서 끝나고, 못 찾을 때만 KBO 를 한 번 더 봅니다.
 */
export async function futuresSearch(request, env) {
  const q = (new URL(request.url).searchParams.get('q') || '').trim();
  if (!q) return json({ players: [] });
  try {
    const key = `search:${q}`;
    const hit = cache.get(key);
    if (hit) return json(hit);

    const res = await fetch(
      'https://www.koreabaseball.com/Player/Search.aspx?searchWord='
      + encodeURIComponent(q),
      { headers: UA },
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const players = parseSearchRows(await res.text());
    const result = { players, source: 'koreabaseball.com' };
    if (players.length) cache.set(key, result);
    return json(result);
  } catch (err) {
    return json({
      players: [],
      error: String(err && err.message ? err.message : err),
    });
  }
}

/**
 * 퓨처스 선수 한 명입니다.
 *
 * 타자·투수 어느 쪽인지 모르니 두 경로를 나란히 부르고 기록이 있는
 * 쪽을 씁니다. 둘 다 비면 프로필이 잡힌 쪽을 씁니다. 줄 세우면
 * 응답이 두 배 느려지는데 서로 다른 페이지라 순서가 결과에 영향을
 * 주지 않습니다.
 */
export async function futuresPlayer(request, env, ctx, params) {
  const id = String(params.id || '').trim();
  if (!/^\d+$/.test(id)) {
    return json({ error: 'bad player id' }, 400);
  }
  try {
    const hit = cache.get(id);
    if (hit) return json(hit);

    const [hitRes, pitRes] = await Promise.all([
      fetch(`${BASE}/HitterDetail.aspx?playerId=${id}`, { headers: UA }),
      fetch(`${BASE}/PitcherDetail.aspx?playerId=${id}`, { headers: UA }),
    ]);
    const pages = {
      batter: hitRes.ok ? await hitRes.text() : '',
      pitcher: pitRes.ok ? await pitRes.text() : '',
    };

    const parsed = {};
    for (const kind of ['batter', 'pitcher']) {
      if (!pages[kind]) continue;
      parsed[kind] = {
        profile: parseProfile(pages[kind]),
        season: parseSeasonRow(pages[kind]),
        recent: parseRecentGames(pages[kind]),
      };
    }

    // 기록이 있는 쪽이 그 선수의 자리입니다. 둘 다 없으면 이름이라도
    // 잡힌 쪽을 씁니다. 그래야 화면이 프로필만이라도 보여 줍니다.
    const withStats = ['batter', 'pitcher']
      .filter((k) => parsed[k] && parsed[k].season.cells.length);
    const withName = ['batter', 'pitcher']
      .filter((k) => parsed[k] && parsed[k].profile.name);
    const kind = withStats[0] || withName[0] || null;

    if (!kind) {
      return json({ found: false, player_id: Number(id) }, 404);
    }

    const picked = parsed[kind];
    const teamName = picked.season.cells[0] || null;
    const result = {
      found: true,
      player_id: Number(id),
      kind,                       // 'batter' | 'pitcher'
      ...picked.profile,
      team: teamName,
      team_code: teamName ? (FUTURES_TEAM_CODE[teamName] ?? '') : '',
      season: picked.season,
      recent: picked.recent,
      source: 'koreabaseball.com',
    };
    cache.set(id, result);
    return json(result);
  } catch (err) {
    return json({
      found: false,
      player_id: Number(id),
      error: String(err && err.message ? err.message : err),
    });
  }
}
