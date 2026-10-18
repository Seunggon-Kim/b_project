import { json } from '../lib/respond.js';
import { queryInt } from '../lib/router.js';
import { countOf, countsOf } from '../lib/counts.js';
import { tableNames, tableColumns, columnCounts } from '../lib/schema.js';
import { columnDict, tableMeta } from '../lib/coldict.js';
import { idFixer } from '../lib/ids.js';
import { KBO_TOS_HIDDEN_TABLES } from '../lib/tos.js';

/**
 * 데이터 탐색에서 빼는 표입니다(목록에 없고, 표를 열면 404).
 *
 * KBO 사이트에서만 받아 온 표입니다. 2026-10-14 시행 KBO 이용약관 제14조 차항이
 * 자동 수집과 수집한 데이터의 재배포를 금지해 수집을 멈췄고, 남아 있는 옛 값도
 * 더 내보내지 않습니다. 네이버로 대신한 표(공식 기록·팀 순위·선수)는 그대로
 * 보입니다. 표 자체는 DB 에 남겨 둡니다(지울지는 따로 정합니다).
 */
export { KBO_TOS_HIDDEN_TABLES };

/**
 * 화면에 보일 표 이름 전부입니다.
 *
 * 원본과 같은 이름순(JS 글자 순서)으로 다시 정렬합니다. MySQL 의
 * ORDER BY 는 글자 비교 규칙(대소문자 무시 등)이 달라 순서가 다를 수
 * 있습니다. KBO_TOS_HIDDEN_TABLES 는 뺍니다.
 */
export async function visibleTableNames(env) {
  const names = await tableNames(env);
  return names.filter((n) => !KBO_TOS_HIDDEN_TABLES.has(n)).sort();
}

/**
 * 원본 api/main.py:646-670 입니다.
 * 표 목록에 행 수·컬럼 수와 사전의 분류·설명·갱신주기를 붙입니다.
 */
export async function dbTables(request, env) {
  const db = env.MYSQL;
  const meta = columnDict();
  const tmeta = meta.tables || {};
  const names = await visibleTableNames(env);

  // 원본은 표마다 `COUNT(*)` 를 돌렸습니다. 18개 표를 합쳐 한 번에 약
  // 24만 행을 읽었고 그 95% 가 play_by_play 였습니다. 미리 적어 둔 값을
  // 한 번에 읽습니다. 자세한 사정은 lib/counts.js 주석에 있습니다.
  const known = await countsOf(db, names);
  // 열 수도 한 번에 읽습니다. 표마다 열 정보를 따로 물으면 질의가
  // 표 수만큼 나가고, 질의마다 드는 Worker CPU 가 쌓입니다(무료 플랜은
  // 요청당 10ms).
  const ncols = await columnCounts(env);

  const result = [];
  for (const name of names) {
    // 메타에 없는 표는 개별로 셉니다. 새로 만든 표에서도 화면이 동작해야
    // 합니다. 원본과 같이 실패하면 0 이 아니라 null 입니다.
    const n = known.has(name) ? known.get(name) : await countOf(db, name);
    const columns = ncols.has(name)
      ? ncols.get(name)
      : (await tableColumns(env, name)).length;
    const m = tmeta[name] || {};
    result.push({
      name,
      rows: n,
      columns,
      category: m.category || '',
      table_desc: m.table_desc || '',
      update_freq: m.update_freq || '',
    });
  }

  return json({
    tables: result,
    count: result.length,
    categories: meta.categories || [],
  });
}

/**
 * 원본 api/main.py:673-716 입니다. 표 하나의 스키마와 페이지네이션된 행.
 *
 * 표 이름이 SQL 에 그대로 들어가는 자리라, **반드시 표 목록(lib/schema.js)으로
 * 확인한 뒤에만** 조회합니다. 원본이 그렇게 하고 있고 그 확인이 곧 방어입니다.
 */
export async function dbTable(request, env, ctx, params) {
  const db = env.MYSQL;
  const tableName = params.name;

  const names = await visibleTableNames(env);
  if (!names.includes(tableName)) {
    return json({ detail: 'Table not found' }, 404);
  }

  const url = new URL(request.url);
  // 원본: limit = max(1, min(int(limit), 500)), offset = max(0, int(offset))
  const limit = Math.max(1, Math.min(queryInt(url, 'limit', 50), 500));
  const offset = Math.max(0, queryInt(url, 'offset', 0));

  const tmeta = tableMeta(tableName);
  const cdesc = tmeta.columns || {};

  const info = await tableColumns(env, tableName);
  const schema = info.map((c) => ({
    name: c.name,
    type: c.type || '',
    pk: Boolean(c.pk),
    notnull: Boolean(c.notnull),
    desc: cdesc[c.name] || '',
  }));
  const columns = info.map((c) => c.name);

  const total = await countOf(db, tableName);
  const r = await db
    .prepare(`SELECT * FROM \`${tableName}\` LIMIT ? OFFSET ?`)
    .bind(limit, offset).all();
  const rows = r.results.map(idFixer(tableName));

  return json({
    table: tableName,
    schema,
    columns,
    rows,
    total: total === null ? 0 : total,
    limit,
    offset,
    table_desc: tmeta.table_desc || '',
    update_freq: tmeta.update_freq || '',
    category: tmeta.category || '',
  });
}

/**
 * 표 전체 내려받기(CSV)입니다. 모든 표에 410 을 돌려주고 캐시하지 않습니다.
 *
 * 예전에는 표를 나눠 읽어 CSV 로 흘려보내고, 큰 표는 GitHub Release 의
 * 미리 만든 파일로 안내했습니다. 데이터 출처(KBO·네이버) 이용약관이 수집한 데이터의
 * 재배포를 막아(KBO 이용약관 제14조 차항, 2026-10-14 시행) 표 전체 내려받기를
 * 닫았습니다. Release 도 지웁니다. 선수·팀 통계 화면의 CSV 단추는 화면에 보이는
 * 표만 브라우저에서 만들어 이 경로를 쓰지 않습니다.
 */
export const CSV_CLOSED_MESSAGE = '표 전체 내려받기는 제공하지 않습니다(데이터 출처 이용약관).';

export function dbTableCsv() {
  const res = json({ error: CSV_CLOSED_MESSAGE }, 410);
  res.headers.set('cache-control', 'no-store');
  return res;
}
