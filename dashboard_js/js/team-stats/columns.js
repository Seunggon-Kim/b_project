/*
 * 팀 통계 표의 칸 정의입니다. 이름·형식·설명·계산식·시작 연도·기간별
 * 가능 여부를 한 곳에 둡니다. 화면(DOM)에는 손대지 않습니다.
 *
 *   kind   값 형식(fmt 참고)
 *   range  기간별(경기 기록)에서도 계산되면 true
 *   index  지수 칸(리그 평균 100). 'high' 는 높을수록, 'low' 는 낮을수록 좋음
 *   better 'low' 면 처음 정렬이 오름차순
 */
(function (root) {
  'use strict';
  const TS = root.TeamStats = root.TeamStats || {};

  const PF_NOTE = '구장 보정 = (홈구장 득점 파크팩터 + 1000) ÷ 2000';

  const BAT = {
    g: { label: 'G', kind: 'int', range: true, desc: '팀이 치른 경기 수입니다. 시즌은 공식 순위표, 기간별은 경기 기록에서 셉니다.' },
    pa: { label: 'PA', kind: 'int', range: true, desc: '타석입니다.' },
    ab: { label: 'AB', kind: 'int', range: true, desc: '타수입니다.' },
    h: { label: 'H', kind: 'int', range: true, desc: '안타입니다.' },
    single: { label: '1B', kind: 'int', range: true, desc: '단타입니다.', formula: 'H − 2B − 3B − HR' },
    d2: { label: '2B', kind: 'int', range: true, desc: '2루타입니다.' },
    d3: { label: '3B', kind: 'int', range: true, desc: '3루타입니다.' },
    hr: { label: 'HR', kind: 'int', range: true, desc: '홈런입니다.' },
    r: { label: 'R', kind: 'int', range: true, desc: '득점입니다.' },
    rbi: { label: 'RBI', kind: 'int', range: false, desc: '타점입니다.' },
    bb: { label: 'BB', kind: 'int', range: true, desc: '볼넷입니다. 고의4구를 포함합니다.' },
    ibb: { label: 'IBB', kind: 'int', range: false, desc: '고의4구입니다.' },
    so: { label: 'SO', kind: 'int', range: true, better: 'low', desc: '삼진입니다.' },
    hbp: { label: 'HBP', kind: 'int', range: true, desc: '몸에 맞는 공입니다.' },
    sf: { label: 'SF', kind: 'int', range: true, desc: '희생플라이입니다.' },
    sh: { label: 'SH', kind: 'int', range: true, desc: '희생번트입니다.' },
    gdp: { label: 'GDP', kind: 'int', range: false, better: 'low', desc: '병살타입니다.' },
    tb: { label: 'TB', kind: 'int', range: true, desc: '루타입니다.' },
    xbh: { label: 'XBH', kind: 'int', range: false, desc: '장타(2루타·3루타·홈런)입니다.' },
    multi: { label: '멀티히트', kind: 'int', range: false, desc: '한 경기에 안타 두 개 이상을 친 횟수의 합입니다.' },
    gw: { label: 'GW RBI', kind: 'int', range: false, desc: '결승타점입니다.' },
    go: { label: 'GO', kind: 'int', range: false, desc: '땅볼 아웃입니다.' },
    ao: { label: 'AO', kind: 'int', range: false, desc: '뜬공 아웃입니다.' },
    goao: { label: 'GO/AO', kind: 'f2', range: false, desc: '뜬공 아웃 하나당 땅볼 아웃입니다.', formula: 'GO ÷ AO' },
    avg: { label: 'AVG', kind: 'avg3', range: true, desc: '타율입니다.', formula: 'H ÷ AB' },
    obp: { label: 'OBP', kind: 'avg3', range: true, desc: '출루율입니다.', formula: '(H + BB + HBP) ÷ (AB + BB + HBP + SF)' },
    slg: { label: 'SLG', kind: 'avg3', range: true, desc: '장타율입니다.', formula: 'TB ÷ AB' },
    ops: { label: 'OPS', kind: 'avg3', range: true, desc: '출루율과 장타율의 합입니다.', formula: 'OBP + SLG' },
    iso: { label: 'ISO', kind: 'avg3', range: true, desc: '순수 장타력입니다.', formula: 'SLG − AVG' },
    babip: { label: 'BABIP', kind: 'avg3', range: true, desc: '인플레이 타구의 타율입니다. 삼진·홈런을 뺀 타구만 셉니다.', formula: '(H − HR) ÷ (AB − SO − HR + SF)' },
    kpct: { label: 'K%', kind: 'f1', range: true, better: 'low', desc: '타석 대비 삼진 비율입니다.', formula: 'SO ÷ PA × 100' },
    bbpct: { label: 'BB%', kind: 'f1', range: true, desc: '타석 대비 볼넷 비율입니다.', formula: 'BB ÷ PA × 100' },
    bbk: { label: 'BB/K', kind: 'f2', range: true, desc: '삼진 하나당 볼넷입니다.', formula: 'BB ÷ SO' },
    woba: { label: 'wOBA', kind: 'avg3', range: true, since: 2008, desc: '타격 결과마다 득점 가치를 달리 매긴 출루율입니다. 가중치는 KBO 경기 기록으로 시즌마다 구합니다.', formula: '(wBB·BB + wHBP·HBP + w1B·1B + w2B·2B + w3B·3B + wHR·HR) ÷ (AB + BB + SF + HBP)' },
    wraa: { label: 'wRAA', kind: 'f1', range: true, since: 2008, desc: '리그 평균 타선보다 더 만든 득점입니다. 0이 평균입니다.', formula: '(wOBA − 리그 wOBA) ÷ wOBA 척도 × PA' },
    wrc: { label: 'wRC', kind: 'int', range: true, since: 2008, desc: 'wOBA로 잰 팀 득점 생산량입니다.', formula: '(wRAA ÷ PA + 리그 득점/PA) × PA' },
    wrcp: { label: 'wRC+', kind: 'idx', range: true, since: 2008, index: 'high', desc: '타석당 득점 생산을 리그 평균 100에 맞춘 값입니다. 110이면 평균보다 10% 더 만듭니다. 홈구장 영향을 반만 덜어 냅니다(선수 wRC+와 같은 방식).', formula: '(wRAA ÷ PA) ÷ 리그 득점/PA × 100 + (2 − 구장 보정) × 100. ' + PF_NOTE },
    opsp: { label: 'OPS+', kind: 'idx', range: true, index: 'high', desc: 'OPS를 리그 평균 100에 맞춘 값입니다. 2008년부터 홈구장 영향을 반만 덜어 냅니다. 그 전은 파크팩터가 없어 보정하지 않습니다.', formula: '100 × (OBP ÷ 리그 OBP + SLG ÷ 리그 SLG − 1) ÷ 구장 보정. ' + PF_NOTE },
  };

  const PIT = {
    w: { label: 'W', kind: 'int', range: false, desc: '승리입니다.' },
    l: { label: 'L', kind: 'int', range: false, better: 'low', desc: '패배입니다.' },
    sv: { label: 'SV', kind: 'int', range: false, desc: '세이브입니다.' },
    hld: { label: 'HLD', kind: 'int', range: false, desc: '홀드입니다.' },
    bs: { label: 'BS', kind: 'int', range: false, better: 'low', desc: '블론 세이브입니다.' },
    svo: { label: 'SVO', kind: 'int', range: false, desc: '세이브 기회입니다.' },
    g: { label: 'G', kind: 'int', range: true, desc: '팀이 치른 경기 수입니다. 시즌은 공식 순위표, 기간별은 경기 기록에서 셉니다.' },
    gs: { label: 'GS', kind: 'int', range: false, desc: '선발 등판 수입니다.' },
    gf: { label: 'GF', kind: 'int', range: false, desc: '경기를 마무리한 횟수입니다.' },
    cg: { label: 'CG', kind: 'int', range: false, desc: '완투입니다.' },
    sho: { label: 'SHO', kind: 'int', range: false, desc: '완봉입니다.' },
    qs: { label: 'QS', kind: 'int', range: false, desc: '선발이 6이닝 이상 던지고 자책점 3점 이하로 막은 경기입니다.' },
    outs: { label: 'IP', kind: 'ip', range: true, desc: '던진 이닝입니다.' },
    tbf: { label: 'TBF', kind: 'int', range: false, desc: '상대한 타자 수입니다.' },
    np: { label: 'NP', kind: 'int', range: false, desc: '던진 공의 수입니다.' },
    h: { label: 'H', kind: 'int', range: true, better: 'low', desc: '내준 안타입니다.' },
    d2: { label: '2B', kind: 'int', range: false, better: 'low', desc: '내준 2루타입니다.' },
    d3: { label: '3B', kind: 'int', range: false, better: 'low', desc: '내준 3루타입니다.' },
    hr: { label: 'HR', kind: 'int', range: true, better: 'low', desc: '내준 홈런입니다.' },
    r: { label: 'R', kind: 'int', range: true, better: 'low', desc: '실점입니다.' },
    er: { label: 'ER', kind: 'int', range: false, better: 'low', desc: '자책점입니다.' },
    bb: { label: 'BB', kind: 'int', range: true, better: 'low', desc: '내준 볼넷입니다. 고의4구를 포함합니다.' },
    ibb: { label: 'IBB', kind: 'int', range: false, desc: '고의4구입니다.' },
    hbp: { label: 'HBP', kind: 'int', range: false, better: 'low', desc: '몸에 맞는 공입니다.' },
    so: { label: 'SO', kind: 'int', range: true, desc: '탈삼진입니다.' },
    wp: { label: 'WP', kind: 'int', range: false, better: 'low', desc: '폭투입니다.' },
    bk: { label: 'BK', kind: 'int', range: false, better: 'low', desc: '보크입니다.' },
    gidp: { label: 'GIDP', kind: 'int', range: false, desc: '유도한 병살입니다.' },
    go: { label: 'GO', kind: 'int', range: false, desc: '유도한 땅볼 아웃입니다.' },
    ao: { label: 'AO', kind: 'int', range: false, desc: '유도한 뜬공 아웃입니다.' },
    goao: { label: 'GO/AO', kind: 'f2', range: false, desc: '뜬공 아웃 하나당 땅볼 아웃입니다.', formula: 'GO ÷ AO' },
    era: { label: 'ERA', kind: 'f2', range: false, better: 'low', desc: '9이닝당 자책점입니다.', formula: 'ER × 9 ÷ IP' },
    ra9: { label: 'RA/9', kind: 'f2', range: true, better: 'low', desc: '9이닝당 실점입니다. 기간별은 자책점이 없어 ERA 대신 씁니다.', formula: 'R × 9 ÷ IP' },
    whip: { label: 'WHIP', kind: 'f2', range: true, better: 'low', desc: '이닝당 내준 안타와 볼넷입니다.', formula: '(H + BB) ÷ IP' },
    k9: { label: 'K/9', kind: 'f2', range: true, desc: '9이닝당 탈삼진입니다.', formula: 'SO × 9 ÷ IP' },
    bb9: { label: 'BB/9', kind: 'f2', range: true, better: 'low', desc: '9이닝당 볼넷입니다.', formula: 'BB × 9 ÷ IP' },
    h9: { label: 'H/9', kind: 'f2', range: true, better: 'low', desc: '9이닝당 피안타입니다.', formula: 'H × 9 ÷ IP' },
    hr9: { label: 'HR/9', kind: 'f2', range: true, better: 'low', desc: '9이닝당 피홈런입니다.', formula: 'HR × 9 ÷ IP' },
    kbb: { label: 'K/BB', kind: 'f2', range: true, desc: '볼넷 하나당 탈삼진입니다.', formula: 'SO ÷ BB' },
    kpct: { label: 'K%', kind: 'f1', range: false, desc: '상대 타자 대비 탈삼진 비율입니다.', formula: 'SO ÷ TBF × 100' },
    bbpct: { label: 'BB%', kind: 'f1', range: false, better: 'low', desc: '상대 타자 대비 볼넷 비율입니다.', formula: 'BB ÷ TBF × 100' },
    kbbpct: { label: 'K−BB%', kind: 'f1', range: false, desc: '탈삼진 비율에서 볼넷 비율을 뺀 값입니다.', formula: 'K% − BB%' },
    oavg: { label: 'AVG', kind: 'avg3', range: true, better: 'low', desc: '피안타율입니다.', formula: 'H ÷ (TBF − BB − HBP − SH − SF)' },
    babip: { label: 'BABIP', kind: 'avg3', range: false, better: 'low', desc: '인플레이 타구의 피안타율입니다.', formula: '(H − HR) ÷ (TBF − BB − HBP − SH − SO − HR)' },
    lobpct: { label: 'LOB%', kind: 'f1', range: false, desc: '잔루 처리율입니다. 내보낸 주자를 실점 없이 남긴 비율입니다.', formula: '(H + BB + HBP − R) ÷ (H + BB + HBP − 1.4 × HR) × 100' },
    pip: { label: 'P/IP', kind: 'f1', range: false, better: 'low', desc: '1이닝당 투구 수입니다.', formula: 'NP ÷ IP' },
    fip: { label: 'FIP', kind: 'f2', range: false, better: 'low', desc: '수비와 상관없는 홈런·볼넷·몸에 맞는 공·삼진만으로 매긴 평균자책점입니다. 리그 평균이 리그 ERA와 같도록 상수를 맞춥니다.', formula: '(13·HR + 3·(BB − IBB + HBP) − 2·SO) ÷ IP + 상수. 상수 = 리그 ERA − (13·리그 HR + 3·(리그 BB − 리그 IBB + 리그 HBP) − 2·리그 SO) ÷ 리그 IP' },
    ef: { label: 'E−F', kind: 'f2', range: false, desc: 'ERA에서 FIP를 뺀 값입니다. 양수면 수비나 운 때문에 실점이 더 났을 수 있습니다.', formula: 'ERA − FIP' },
    erap: { label: 'ERA-', kind: 'idx', range: false, index: 'low', better: 'low', desc: 'ERA를 리그 평균 100에 맞춘 값입니다. 낮을수록 좋습니다. 90이면 평균보다 10% 덜 내줍니다. 2008년부터 홈구장 영향을 반만 덜어 냅니다.', formula: '100 × ERA × (2 − 구장 보정) ÷ 리그 ERA. ' + PF_NOTE },
    fipp: { label: 'FIP-', kind: 'idx', range: false, index: 'low', better: 'low', desc: 'FIP를 리그 평균 100에 맞춘 값입니다. 낮을수록 좋습니다. 2008년부터 홈구장 영향을 반만 덜어 냅니다.', formula: '100 × FIP × (2 − 구장 보정) ÷ 리그 FIP. ' + PF_NOTE },
  };

  const REC = {
    g: { label: 'G', kind: 'int', range: true, desc: '치른 경기 수입니다.' },
    w: { label: 'W', kind: 'int', range: true, desc: '승리입니다.' },
    l: { label: 'L', kind: 'int', range: true, better: 'low', desc: '패배입니다.' },
    d: { label: 'D', kind: 'int', range: true, desc: '무승부입니다.' },
    pct: { label: '승률', kind: 'avg3', range: true, desc: '승률입니다. 시즌은 KBO 공식 승률입니다. 공식 승률은 시대마다 무승부를 다르게 셉니다(일부 옛 시즌은 0.5승, 2009·2010년은 패, 2011년부터는 뺍니다). 기간별은 무승부를 뺍니다.', formula: '기간별: W ÷ (W + L)' },
    gb: { label: '승차', kind: 'gb', range: true, better: 'low', desc: '1위와의 승차입니다. 시즌은 공식 순위표 값이고, 1999·2000년은 리그 안에서 잰 값입니다.', formula: '((1위 W − W) + (L − 1위 L)) ÷ 2' },
    r: { label: 'R', kind: 'int', range: true, desc: '팀 득점입니다. 2008년부터는 경기 점수 합이고, 그 전은 공식 타자 기록 합입니다.' },
    ra: { label: 'RA', kind: 'int', range: true, better: 'low', desc: '팀 실점입니다. 2008년부터는 경기 점수 합이고, 그 전은 공식 투수 기록 합입니다.' },
    diff: { label: '득실차', kind: 'signed0', range: true, desc: '득점에서 실점을 뺀 값입니다.', formula: 'R − RA' },
    pyth: { label: '피타고리안', kind: 'avg3', range: true, desc: '득점과 실점만으로 계산한 기대 승률입니다.', formula: 'R^1.83 ÷ (R^1.83 + RA^1.83)' },
    expw: { label: '기대 승', kind: 'f1', range: true, desc: '피타고리안 승률로 본 기대 승수입니다.', formula: '피타고리안 × (W + L)' },
    luck: { label: '승수 차', kind: 'signed1', range: true, desc: '실제 승수에서 기대 승수를 뺀 값입니다. 양수면 득실에 비해 많이 이겼습니다.', formula: 'W − 기대 승' },
    home: { label: '홈', kind: 'wl', range: true, since: 2008, desc: '홈 경기 승-패(-무)입니다.' },
    away: { label: '원정', kind: 'wl', range: true, since: 2008, desc: '원정 경기 승-패(-무)입니다.' },
    onerun: { label: '1점차', kind: 'wl', range: true, since: 2008, desc: '1점 차로 끝난 경기의 승-패입니다.' },
  };

  const GROUPS = {
    bat: {
      dash: ['g', 'pa', 'hr', 'r', 'rbi', 'bbpct', 'kpct', 'iso', 'babip', 'avg', 'obp', 'slg', 'woba', 'wrcp'],
      std: ['g', 'pa', 'ab', 'h', 'single', 'd2', 'd3', 'hr', 'r', 'rbi', 'bb', 'ibb', 'so', 'hbp', 'sf', 'sh', 'gdp', 'avg'],
      adv: ['pa', 'bbpct', 'kpct', 'bbk', 'avg', 'obp', 'slg', 'ops', 'iso', 'babip', 'woba', 'wraa', 'wrc', 'wrcp', 'opsp'],
    },
    pit: {
      dash: ['w', 'l', 'sv', 'g', 'gs', 'outs', 'k9', 'bb9', 'hr9', 'babip', 'lobpct', 'era', 'fip'],
      std: ['w', 'l', 'era', 'g', 'gs', 'cg', 'sho', 'sv', 'hld', 'bs', 'outs', 'tbf', 'h', 'r', 'er', 'hr', 'bb', 'ibb', 'hbp', 'wp', 'bk', 'so'],
      adv: ['k9', 'bb9', 'kbb', 'hr9', 'kpct', 'bbpct', 'kbbpct', 'oavg', 'whip', 'babip', 'lobpct', 'erap', 'fipp', 'fip', 'ef'],
    },
  };
  const REC_KEYS = Object.keys(REC);
  const ORDER = { bat: Object.keys(BAT), pit: Object.keys(PIT) };
  const TABLES = { bat: BAT, pit: PIT, rec: REC };

  /** 칸 정의를 key 를 붙여 돌려줍니다. 없으면 null. */
  function def(tab, key) {
    const t = TABLES[tab];
    const d = t && Object.prototype.hasOwnProperty.call(t, key) ? t[key] : null;
    return d ? Object.assign({ key: key }, d) : null;
  }

  /** 값을 화면 글자로 바꿉니다. 없거나 숫자가 아니면 '-'. */
  function fmt(v, kind) {
    if (v === null || v === undefined) return '-';
    if (kind === 'wl') {
      if (typeof v !== 'object') return '-';
      return v.d ? `${v.w}-${v.l}-${v.d}` : `${v.w}-${v.l}`;
    }
    const n = Number(v);
    if (!Number.isFinite(n)) return '-';
    // 반올림하면 0 이 되는 음수는 '-0.0' 대신 '0.0' 으로 보입니다.
    const noNegZero = s => (/^-[0.]+$/.test(s) ? s.slice(1) : s);
    switch (kind) {
      case 'avg3': return noNegZero(n.toFixed(3).replace(/^(-?)0\./, '$1.'));
      case 'f1': return noNegZero(n.toFixed(1));
      case 'f2': return noNegZero(n.toFixed(2));
      case 'idx': return String(Math.round(n));
      case 'ip': {
        const o = Math.round(n), w = Math.floor(o / 3), r = o % 3;
        return r ? `${w} ${r}/3` : String(w);
      }
      case 'signed0': {
        const s = Math.round(n);
        return s > 0 ? '+' + s : String(s === 0 ? 0 : s);
      }
      case 'signed1': {
        const s = n.toFixed(1);
        if (s === '-0.0' || s === '0.0') return '0.0';
        return n > 0 ? '+' + s : s;
      }
      case 'gb':
        if (n === 0) return '-';
        return Number.isInteger(n) ? String(n) : n.toFixed(1);
      case 'int':
      default:
        return String(Math.round(n));
    }
  }

  const api = { BAT, PIT, REC, ORDER, GROUPS, REC_KEYS, def, fmt };
  TS.columns = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
