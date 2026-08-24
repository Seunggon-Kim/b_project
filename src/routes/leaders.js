import { json } from '../lib/respond.js';
import { ttlCache } from '../lib/cache.js';
import { KBO_TEAM_CODE } from './standings.js';

const cache = ttlCache(600); // 원본 _LEADERS_TTL = 600

// 원본 api/main.py:1529-1546 의 _WOBA_CONST 입니다.
// 출처는 research/data/statiz_yearly_constants.csv 이고,
// (woba_scale, ebb, single_w, double_w, triple_w, hr_w) 순서입니다.
export const WOBA_CONST = {
  2011: [1.081, 0.407, 0.581, 0.972, 1.168, 1.364],
  2012: [1.134, 0.395, 0.565, 0.947, 1.162, 1.377],
  2013: [1.235, 0.314, 0.479, 0.821, 1.134, 1.442],
  2014: [1.094, 0.334, 0.513, 0.853, 1.169, 1.430],
  2015: [1.107, 0.375, 0.505, 0.808, 1.071, 1.419],
  2016: [1.095, 0.354, 0.502, 0.859, 1.258, 1.424],
  2017: [1.097, 0.353, 0.507, 0.869, 1.081, 1.398],
  2018: [1.074, 0.370, 0.509, 0.831, 1.167, 1.440],
  2019: [1.196, 0.357, 0.493, 0.802, 1.170, 1.433],
  2020: [1.109, 0.378, 0.516, 0.879, 1.081, 1.431],
  2021: [1.169, 0.362, 0.499, 0.867, 1.063, 1.460],
  2022: [1.211, 0.361, 0.484, 0.804, 1.210, 1.441],
  2023: [1.198, 0.355, 0.495, 0.865, 1.191, 1.408],
  2024: [1.093, 0.389, 0.519, 0.852, 1.046, 1.418],
  2025: [1.173, 0.371, 0.502, 0.801, 1.131, 1.406],
  2026: [1.191, 0.364, 0.493, 0.802, 1.175, 1.411],
};

/**
 * 원본 _ip_to_outs(api/main.py:1549-1564): '68 1/3' -> 205
 *
 * 빈 조각을 걸러 내는 것이 중요합니다. Python 의 `str.split()` 은 공백만
 * 있는 자리에서 빈 조각을 내지 않지만, JS 의 `split(/\s+/)` 는 앞뒤 공백에서
 * 빈 문자열을 냅니다. 그 빈 조각이 `parseInt('') = NaN` 을 거쳐 whole 을
 * 0 으로 덮어써, ' 68 1/3 ' 이 205 가 아니라 1 이 되어 버립니다.
 */
export function ipToOuts(s) {
  let whole = 0;
  let frac = 0;
  const text = s === null || s === undefined ? '' : String(s);
  for (const part of text.trim().split(/\s+/).filter(Boolean)) {
    if (part.includes('/')) {
      const n = Number.parseInt(part.split('/')[0], 10);
      frac = Number.isNaN(n) ? 0 : n;
    } else {
      const n = Number.parseInt(part, 10);
      whole = Number.isNaN(n) ? 0 : n;
    }
  }
  return whole * 3 + frac;
}

/**
 * 원본의 `"%.3f" % float(val)` 과 같은 문자열을 만듭니다.
 * 값이 없으면 '-' 입니다. 0 은 값이 있는 것이므로 '-' 가 아닙니다.
 */
export function fmt3(val) {
  if (val === null || val === undefined) return '-';
  return Number(val).toFixed(3);
}

/** 팀 표기명을 엠블럼 코드로 바꿉니다. 원본 _code 헬퍼입니다. */
export function teamCode(team) {
  return KBO_TEAM_CODE[team || ''] || '';
}

/**
 * Python round() 는 .5 에서 짝수 쪽으로 갑니다(은행가 반올림).
 * Math.round 는 .5 에서 항상 올림이라, 3.1 * team_g 가 부동소수점상
 * 정확히 x.5 로 떨어지는 경기 수(예: 75경기 -> 232.5)에서 규정타석이
 * 1 어긋납니다. 원본 round(3.1 * team_g) 와 같게 맞춥니다.
 */
export function pyRound(x) {
  const floor = Math.floor(x);
  if (x - floor === 0.5) return floor % 2 === 0 ? floor : floor + 1;
  return Math.round(x);
}

/**
 * 원본의 float(v) 를 흉내 냅니다. 변환 실패(TypeError/ValueError 에 해당)는
 * null 로 알립니다. Number(null) 이 0 이 되는 JS 함정을 피하기 위함입니다.
 */
function pyFloat(v) {
  if (typeof v === 'number') return v;
  if (v === null || v === undefined) return null;
  const s = String(v).trim();
  if (s === '') return null;
  const n = Number(s);
  return Number.isNaN(n) ? null : n;
}

/**
 * 원본의 int(v) 를 흉내 냅니다. int(15.7) 은 15 로 절삭하고,
 * int('15.0') / int(None) 은 실패라 null 로 알립니다.
 */
function pyInt(v) {
  if (typeof v === 'number') return Number.isFinite(v) ? Math.trunc(v) : null;
  if (v === null || v === undefined) return null;
  const s = String(v).trim();
  if (!/^[+-]?\d+$/.test(s)) return null;
  return Number.parseInt(s, 10);
}

/** 원본의 `"%.1f" % val` 입니다. 값이 없으면 '-' 입니다. */
function fmt1(val) {
  if (val === null || val === undefined) return '-';
  return Number(val).toFixed(1);
}

/**
 * 원본 get_leaders (api/main.py:1594-1742) 입니다.
 *
 * KBO 개인 순위 Top5. 타자: 타율/출루율/장타율/OPS/wOBA/wRC+,
 * 투수: 이닝/탈삼진/ERA/K%/BB%/K-BB%.
 * 타율·출루율·장타율·OPS·wOBA·wRC+·ERA·K%·BB%·K-BB% 는 규정타석/규정이닝
 * (팀 최다경기 기준) 충족자만, 이닝·탈삼진은 누적입니다. 10분 캐시입니다.
 * wRC+/wOBA 는 wrc_plus_comparison 테이블(자체 파크팩터 3년 산식)을 직접
 * 읽습니다. 원본 파일의 _team_park_factors(1567-1593, games 테이블 사용)는
 * get_leaders 가 호출하지 않는 함수라 옮기지 않았습니다.
 * 실패 시 원본처럼 500 이 아니라 200 + error 필드를 돌려줍니다.
 */
export async function leaders(request, env) {
  // FastAPI 의 `season: int = None` 파라미터입니다. 정수로 못 읽는 값은
  // 원본에서 엔드포인트 본문에 들어가기 전에 pydantic v2 검증(422)에
  // 걸립니다. 그 응답 형태(fastapi 0.115 + pydantic 2.12)를 따릅니다.
  let season = null;
  const raw = new URL(request.url).searchParams.get('season');
  if (raw !== null) {
    const s = raw.trim();
    if (!/^[+-]?\d+$/.test(s)) {
      return json({
        detail: [{
          type: 'int_parsing',
          loc: ['query', 'season'],
          msg: 'Input should be a valid integer, unable to parse string as an integer',
          input: raw,
        }],
      }, 422);
    }
    season = Number.parseInt(s, 10);
  }

  try {
    if (season === null) {
      const row = await env.DB
        .prepare('SELECT MAX(season) AS s FROM kbo_official_batter_stats')
        .first();
      season = row && row.s ? row.s : 2026;
    }

    const ckey = String(season);
    const hit = cache.get(ckey);
    if (hit) return json(hit);

    const grow = await env.DB
      .prepare('SELECT MAX(games) AS g FROM kbo_official_batter_stats WHERE season=?')
      .bind(season)
      .first();
    const teamG = grow && grow.g ? grow.g : 0;
    const qualPa = pyRound(3.1 * teamG);
    const qualOuts = teamG * 3; // 규정이닝 = 1.0 IP/경기

    // 타율/출루율/장타율/OPS: 규정타석 충족자, 해당 컬럼 내림차순 Top5.
    // 동점자 순서는 원본과 같이 SQL(ORDER BY ... DESC LIMIT 5)이 준 순서를
    // 그대로 씁니다. JS 에서 다시 정렬하지 않습니다.
    // (orderCol 은 아래 네 호출의 고정 컬럼명만 들어옵니다. 외부 입력이 아닙니다.)
    // 팀과 이름은 그 시즌 기록 행에서 먼저 가져옵니다. `players` 는 지금
    // 명단이라 2016 리더보드에 2026 소속이 붙고, 은퇴 선수는 팀이
    // 빈칸이 됩니다. 조인도 LEFT 로 둡니다. 이너로 두면 명단에 없는
    // 선수가 순위에서 통째로 빠져 **"그해 상위 5명"이 아니라 "지금도
    // 명단에 남은 사람 중 상위 5명"** 이 됩니다. 비어 있는 것보다
    // 나쁩니다. 틀렸는데 맞아 보입니다.
    const batterTop = async (orderCol) => {
      const { results } = await env.DB.prepare(
        'SELECT b.player_id AS player_id, COALESCE(p.player_name, b.player_name) AS name, '
        + 'COALESCE(b.player_team, p.team_id) AS team, b.' + orderCol + ' AS val '
        + 'FROM kbo_official_batter_stats b LEFT JOIN players p ON b.player_id=p.player_id '
        + 'WHERE b.season=? AND b.plate_appearance >= ? '
        + 'ORDER BY b.' + orderCol + ' DESC LIMIT 5',
      ).bind(season, qualPa).all();
      return results.map((d) => ({
        player_id: d.player_id ?? null,
        name: d.name,
        team: d.team,
        code: teamCode(d.team),
        value: fmt3(d.val),
      }));
    };

    const avgTop = await batterTop('batting_average');
    const obpTop = await batterTop('on_base_percentage');
    const slgTop = await batterTop('slugging_percentage');
    const opsTop = await batterTop('on_base_plus_slugging');

    // wRC+ 와 wOBA 는 wrc_plus_comparison(자체 파크팩터 3년 산식, half-PF)
    // 에서 직접 Top5 를 뽑습니다. 'wRC+ 강건성' 페이지와 동일 출처입니다.
    //
    // 그 표에는 이름도 팀도 없고 `batter_ID` 만 있습니다. 그래서 두 곳을
    // 더 붙입니다. 그해 공식 기록(b)이 우선이고 지금 명단(p)이 보조입니다.
    // 둘 다 LEFT 입니다. 이너로 두면 명단에 없는 옛 선수가 순위에서
    // 사라집니다. 이 표는 2015년부터 있어서 이미 그렇게 새고 있었습니다.
    // 자릿수는 원본대로 SQL 의 ROUND 가 냅니다. JS 의 toFixed 만 쓰면
    // 두 번 반올림하는 자리에서 값이 어긋날 수 있습니다. 정렬은 원본과
    // 같이 반올림 전 값으로 합니다.
    const wrcTopBy = async (metricCol, digits, alias) => {
      const { results } = await env.DB.prepare(
        'SELECT CAST(w.batter_ID AS TEXT) AS player_id, '
        + 'COALESCE(b.player_name, p.player_name) AS name, '
        + 'COALESCE(b.player_team, p.team_id) AS team, '
        + 'ROUND(w.' + metricCol + ', ' + digits + ') AS ' + alias + ' '
        + 'FROM wrc_plus_comparison w '
        + 'LEFT JOIN players p ON p.player_id = CAST(w.batter_ID AS TEXT) '
        + 'LEFT JOIN kbo_official_batter_stats b '
        + 'ON b.player_id = CAST(w.batter_ID AS TEXT) AND b.season = w.season '
        + 'WHERE w.season=? AND w.PA >= ? '
        + 'ORDER BY w.' + metricCol + ' DESC LIMIT 5',
      ).bind(season, qualPa).all();
      return results;
    };

    const wrcTop = (await wrcTopBy('wRC_half', 1, 'wrc')).map((d) => ({
      player_id: d.player_id ?? null,
      name: d.name,
      team: d.team,
      code: teamCode(d.team),
      value: fmt1(d.wrc),
    }));

    const wobaTop = (await wrcTopBy('wOBA', 3, 'woba')).map((d) => ({
      player_id: d.player_id ?? null,
      name: d.name,
      team: d.team,
      code: teamCode(d.team),
      value: fmt3(d.woba),
    }));

    // 투수는 지표마다 정렬 기준이 달라 원본처럼 전 행을 받아 여기서 고릅니다.
    // 타자 쪽과 같은 이유로 시즌 행의 값을 먼저 쓰고 LEFT 로 조인합니다.
    const pitRows = (await env.DB.prepare(
      'SELECT ps.player_id AS player_id, COALESCE(p.player_name, ps.player_name) AS name, '
      + 'COALESCE(ps.player_team, p.team_id) AS team, ps.earned_run_average AS era, '
      + 'ps.innings_pitched AS ip, ps.strikeout AS k, '
      // K%·BB% 는 저장된 컬럼이 아니라 여기서 셉니다.
      //
      // `strikeout_per_pa`·`base_on_balls_per_pa` 는 **2025 에만 값이
      // 있습니다.** 나머지 열한 시즌은 전부 NULL 입니다. KBO 기록실이
      // 이 값을 주지 않아 수집기가 채울 수 없고(셀레니움 때도 없었습니다),
      // 2025 값은 옛 파이프라인이 남긴 것입니다. 그래서 K%·BB%·K-BB%
      // 순위가 2025 말고는 전부 비어 있었습니다.
      //
      // 상대타자(TBF)로 나누면 그대로 나옵니다. 2025 저장값과 대조해
      // 확인했습니다(폰세 36.2 vs 36.155, 라일리 30.5 vs 30.465).
      // 컬럼을 새로 채우지 않는 이유는 team_id·is_active 와 같습니다.
      // 아무도 갱신하지 않는 컬럼은 곧 낡습니다.
      + 'CASE WHEN ps.total_batters_faced > 0 '
      + 'THEN ps.strikeout * 100.0 / ps.total_batters_faced END AS kpct, '
      + 'CASE WHEN ps.total_batters_faced > 0 '
      + 'THEN ps.base_on_balls * 100.0 / ps.total_batters_faced END AS bbpct '
      + 'FROM kbo_official_pitcher_stats ps LEFT JOIN players p ON ps.player_id=p.player_id '
      + 'WHERE ps.season=?',
    ).bind(season).all()).results;

    const pit = pitRows.map((d) => {
      const era = pyFloat(d.era);
      const k = pyInt(d.k);
      return {
        ...d,
        _outs: ipToOuts(d.ip),
        _era: era === null ? 999.0 : era, // 원본: float() 실패 시 999.0
        _k: k === null ? 0 : k, // 원본: int() 실패 시 0
        _kpct: pyFloat(d.kpct), // 실패는 null 로 남겨 해당 목록에서 뺍니다
        _bbpct: pyFloat(d.bbpct),
      };
    });

    const pitEntry = (d, val) => ({
      player_id: d.player_id ?? null,
      name: d.name,
      team: d.team,
      code: teamCode(d.team),
      value: val,
    });

    // 이닝/탈삼진: 누적(규정 미적용). ERA/K%/BB%/K-BB%: 규정이닝 충족자.
    // Python sorted() 와 JS sort() 는 둘 다 안정 정렬이라 동점자는 SQL 이 준
    // 원래 순서를 유지합니다. 다만 JS sort() 는 제자리 정렬이라, 다음 지표가
    // 원래 순서를 잃지 않도록 매번 복사본([...])을 정렬합니다.
    const qualPit = pit.filter((x) => x._outs >= qualOuts);
    const ipTop = [...pit].sort((a, b) => b._outs - a._outs).slice(0, 5)
      .map((d) => pitEntry(d, String(d.ip || '').trim()));
    const kTop = [...pit].sort((a, b) => b._k - a._k).slice(0, 5)
      .map((d) => pitEntry(d, String(d._k)));
    const eraTop = [...qualPit].sort((a, b) => a._era - b._era).slice(0, 5)
      .map((d) => pitEntry(d, d._era.toFixed(2)));
    // K% 는 높을수록, BB% 는 낮을수록 상위입니다.
    const kpctTop = qualPit.filter((x) => x._kpct !== null)
      .sort((a, b) => b._kpct - a._kpct).slice(0, 5)
      .map((d) => pitEntry(d, d._kpct.toFixed(1) + '%'));
    const bbpctTop = qualPit.filter((x) => x._bbpct !== null)
      .sort((a, b) => a._bbpct - b._bbpct).slice(0, 5)
      .map((d) => pitEntry(d, d._bbpct.toFixed(1) + '%'));
    // K-BB% = K% - BB% (높을수록 상위), 규정이닝 충족자입니다.
    const kbb = (x) => (x._kpct === null || x._bbpct === null ? null : x._kpct - x._bbpct);
    const kbbTop = qualPit.filter((x) => kbb(x) !== null)
      .sort((a, b) => kbb(b) - kbb(a)).slice(0, 5)
      .map((d) => pitEntry(d, kbb(d).toFixed(1) + '%'));

    const result = {
      season,
      qual_pa: qualPa,
      qual_ip: teamG,
      wrc_pf_season: season,
      batter: {
        avg: avgTop, obp: obpTop, slg: slgTop,
        ops: opsTop, woba: wobaTop, wrc: wrcTop,
      },
      pitcher: {
        ip: ipTop, k: kTop, era: eraTop,
        kpct: kpctTop, bbpct: bbpctTop, kbb: kbbTop,
      },
    };
    cache.set(ckey, result);
    return json(result);
  } catch (err) {
    // 원본은 예외 시 200 과 함께 error 필드를 돌려줍니다. 500 이 아닙니다.
    // qual_pa/qual_ip/wrc_pf_season 은 원본 except 분기에도 없으므로 뺍니다.
    // season 은 그 시점까지 확정된 값(기본값 해석 전이면 null)입니다.
    return json({
      season,
      batter: { avg: [], obp: [], slg: [], ops: [], woba: [], wrc: [] },
      pitcher: { ip: [], k: [], era: [], kpct: [], bbpct: [], kbb: [] },
      error: String(err && err.message ? err.message : err),
    });
  }
}

export { cache as leadersCache };
