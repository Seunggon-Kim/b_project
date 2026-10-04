import { json } from '../lib/respond.js';
import { queryInt } from '../lib/router.js';
import {
  csvExportPlan, csvRow, csvRowsFromArrays, isRealType,
} from '../lib/csv.js';
import { countOf, countsOf } from '../lib/counts.js';
import { tableNames, tableColumns, columnCounts } from '../lib/schema.js';
import { columnDict, tableMeta } from '../lib/coldict.js';
import { idFixer, idFixFlags, intIdOrSame } from '../lib/ids.js';

/**
 * 화면에 보일 표 이름 전부입니다.
 *
 * 원본과 같은 이름순(JS 글자 순서)으로 다시 정렬합니다. MySQL 의
 * ORDER BY 는 글자 비교 규칙(대소문자 무시 등)이 달라 순서가 다를 수
 * 있습니다.
 */
export async function visibleTableNames(env) {
  const names = await tableNames(env);
  return names.sort();
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

// 한 번에 내보낼 수 있는 최대 행 수입니다.
//
// 실측으로 정했습니다. play_by_play(229,667행)를 스트리밍하면 오류 없이
// 중간에 끊깁니다. 더 나쁜 것은 **끊기는 지점이 매번 다르다**는 점입니다.
//
//   요청 전량 → 80,000행에서 끊김
//   limit=50000 → 40,000행에서 끊김
//   limit=30000 → 한 번은 30,000행 완전, 한 번은 10,000행에서 끊김
//   limit=20000 → 두 번 다 완전
//
// 누적 CPU 한도로 보입니다. 비결정적이라 "이 값이면 안전하다"고 말할 수
// 있는 상한은 원리적으로 없고, 실측으로 확률을 낮출 뿐입니다.
//
// 그래도 상한이 필요한 이유는 **잘린 CSV 를 완전한 것처럼 내주는 것이
// 가장 나쁘기 때문**입니다. 사용자는 그것이 전부인 줄 알고 분석에 씁니다.
// HTTP 는 200 으로 시작한 응답의 상태를 되돌릴 수 없으므로, 스트림을 열기
// 전에 행 수를 세어 넘으면 아예 열지 않고 413 으로 이유를 알립니다.
//
// 전량 내려받기는 R2 사전 생성본으로 옮깁니다(계획 D). 그때까지는 offset
// 으로 나눠 받는 것이 유일한 방법입니다.
const CSV_MAX_ROWS = 20000;

// 전량 내려받기를 두는 곳입니다. 태그는 고정이고 자산만 매주 바뀝니다.
// R2 를 쓰려 했지만 결제수단 등록이 필요해 예산 조건에 걸립니다.
// 공개 저장소의 Releases 는 무료이고 저장소 용량에도 잡히지 않습니다.
const DOWNLOAD_URL =
  'https://github.com/Seunggon-Kim/b_project/releases/tag/data-latest';

// 한 번에 읽어 올 행 수입니다.
//
// D1 은 Worker 호출당 쿼리 50개까지만 받습니다. 229,667행을 2,000행씩
// 나누면 115회라 한도를 넘습니다. 10,000행씩이면 23회로 여유가 있습니다.
// 그렇다고 더 키우면 한 번에 올라오는 메모리가 커집니다.
const CSV_PAGE = 10000;

/**
 * 원본 api/main.py:719-760 입니다. 표를 CSV 로 내려받습니다.
 *
 * 원본은 커서를 점진적으로 순회하며 흘려보냅니다. D1 은 결과를 한 번에
 * 돌려주므로 같은 방식을 쓸 수 없습니다. 대신 LIMIT/OFFSET 으로 나눠 읽으며
 * ReadableStream 으로 밀어냅니다.
 *
 * **전량을 한 번에 읽으면 죽습니다.** 실측했습니다. play_by_play 를
 * `SELECT *` 로 통째로 읽으면 60,000행까지는 되고 100,000행부터 Workers 가
 * error 1102(자원 한도)로 끊습니다. 229,667행은 어림도 없습니다.
 * 나눠 읽는 것이 선택이 아니라 필수입니다.
 */
export async function dbTableCsv(request, env, ctx, params) {
  const db = env.MYSQL;
  const tableName = params.name;

  const names = await visibleTableNames(env);
  if (!names.includes(tableName)) {
    return json({ detail: 'Table not found' }, 404);
  }

  const info = await tableColumns(env, tableName);
  const columns = info.map((c) => c.name);
  // REAL 컬럼은 정수값이라도 `150.0` 처럼 써야 파이썬 출력과 바이트가
  // 같아집니다. 자세한 사정은 lib/csv.js 의 csvCell 주석에 있습니다.
  const realFlags = info.map((c) => isRealType(c.type));

  const url = new URL(request.url);
  const lim = queryInt(url, 'limit', 0);
  // offset 은 원본에 없습니다. 원본은 전량을 한 번에 흘려보낼 수 있었기에
  // 필요가 없었습니다. Workers 에서는 큰 표를 나눠 받아야 하는데, 시작
  // 위치를 못 정하면 몇 번을 받아도 같은 앞부분만 옵니다. 나눠 받으라는
  // 안내를 실행 가능하게 만들려면 이 파라미터가 있어야 합니다.
  // 정답지는 offset 을 보내지 않으므로 원본과의 재현 비교에는 영향이 없습니다.
  const off = queryInt(url, 'offset', 0);

  // 내보낼 행 수를 미리 셉니다. 한도를 넘으면 잘린 파일을 주는 대신
  // 이유를 알립니다. 스트림을 연 뒤에는 상태 코드를 바꿀 수 없으니
  // 반드시 열기 전에 판단해야 합니다.
  const totalCount = await countOf(db, tableName);
  const total = totalCount === null ? 0 : totalCount;
  const plan = csvExportPlan(total, lim, off, CSV_MAX_ROWS);
  const startAt = plan.startAt;
  if (plan.tooLarge) {
    const { parts } = plan;
    return json({
      detail: '표가 너무 커서 한 번에 내려받을 수 없습니다.',
      table: tableName,
      rows: total,
      max_rows: CSV_MAX_ROWS,
      // 전량은 미리 만들어 둔 파일로 받는 것이 낫습니다.
      // 매주 자동으로 갱신됩니다(.github/workflows/weekly.yml).
      // 136번 나눠 받으라는 안내만 있으면 사실상 못 받습니다.
      download: DOWNLOAD_URL,
      download_hint: '전량은 미리 만들어 둔 gzip CSV 로 받으십시오. '
        + `${tableName} 은 시즌별로 나뉘어 있습니다.`,
      hint: `여기서 바로 받으려면 limit 과 offset 으로 ${parts}번에 나눠 받으십시오.`,
      example: `/db/table/${tableName}/csv`
        + `?limit=${CSV_MAX_ROWS}&offset=0`,
    }, 413);
  }

  const encoder = new TextEncoder();

  // 행을 배열로 받아(raw) 객체를 만들지 않고 곧장 CSV 로 씁니다.
  // 2만 행이면 칸이 150만 개라, 행마다 객체를 만들고 다시 열 이름으로 꺼내는
  // 일이 Worker CPU 의 큰 몫이었습니다(무료 플랜은 요청당 10ms). 칸 값은 객체
  // 길과 같습니다: 어댑터가 같은 규칙으로 값을 바꾸고(lib/mysqldb.js), ID 되돌리기도
  // idFixer 와 같은 열에만 씁니다(idFixFlags).
  const fixFlags = idFixFlags(tableName, columns);

  let offset = startAt;
  let sent = 0;
  let done = false;

  const stream = new ReadableStream({
    start(controller) {
      // 엑셀에서 한글이 깨지지 않도록 UTF-8 BOM 을 먼저 넣습니다.
      // 원본도 같은 이유로 넣습니다(api/main.py:747).
      controller.enqueue(encoder.encode('﻿' + csvRow(columns)));
    },
    async pull(controller) {
      if (done) return;

      let take = CSV_PAGE;
      if (lim > 0) {
        take = Math.min(CSV_PAGE, lim - sent);
        if (take <= 0) {
          controller.close();
          done = true;
          return;
        }
      }

      const [names, ...rows] = await db
        .prepare(`SELECT * FROM \`${tableName}\` LIMIT ? OFFSET ?`)
        .bind(take, offset)
        .raw({ columnNames: true });
      const n = rows.length;
      const chunk = csvRowsFromArrays(names, rows, columns, realFlags, fixFlags, intIdOrSame);

      if (!n) {
        controller.close();
        done = true;
        return;
      }

      controller.enqueue(encoder.encode(chunk));

      offset += n;
      sent += n;
      if (n < take) {
        controller.close();
        done = true;
      }
    },
  });

  return new Response(stream, {
    headers: {
      'content-type': 'text/csv; charset=utf-8',
      'content-disposition': `attachment; filename="${tableName}.csv"`,
      'access-control-allow-origin': '*',
    },
  });
}
