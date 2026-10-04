// 행을 JSON 배열 글자 한 칸으로 받아 D1 과 같은 모양의 객체로 만듭니다(MySQL 전용).
//
// 왜: Worker 무료 플랜은 요청당 CPU 10ms 입니다. 열이 50개 남짓인 시즌 기록을
// 수백 행 받으면 mysql2 가 행·칸마다 해석기를 부르는 일이 CPU 의 큰 몫입니다
// (/stats/batters?limit=-1 은 400행 x 50칸). 행을 JSON_ARRAY(...) 로 만들어
// GROUP_CONCAT 으로 이은 글자 한 칸(jsonRowsOnce)으로 받으면 mysql2 는 한
// 행만 읽고, 값은 런타임의 JSON.parse 한 번이 풉니다. 행마다 한 칸(jsonRows)
// 은 그 물러설 길입니다(행마다 받기만으로는 CPU 가 거의 줄지 않았습니다).
//
// 값이 보통 질의와 같은 이유:
// - 정수·글자·NULL 은 JSON 에서도 같은 값입니다.
// - 저장된 DOUBLE 은 소수 몇 자리인 짧은 값이라, MySQL 이 JSON 에 적은 글자를
//   JSON.parse 가 읽은 값과 mysql2 가 글자 프로토콜에서 읽은 값이 같습니다
//   (play_by_play 실수 열 227만 행 x 9칸, 시즌 기록 표 전 시즌을 대조).
// - DATETIME 은 JSON 에서 소수 초가 붙으므로(…00.000000) CAST(… AS CHAR) 로
//   글자 프로토콜과 같은 'YYYY-MM-DD HH:MM:SS' 를 받습니다(col.datetime).
// - 계산한 실수(나눗셈 등)는 다릅니다. 글자 프로토콜은 17자리까지 보내고,
//   mysql2 는 17글자 이하를 자릿수를 곱해 쌓은 뒤 10의 거듭제곱으로 나눠
//   읽습니다. 2^53 을 넘는 자릿수에서는 이 값이 JSON.parse(올바른 반올림)와
//   끝자리가 다릅니다(예: 9.559939301972683 과 …685). 그런 열은 col.float 로
//   글자(CAST AS CHAR)로 받아 mysqlTextFloat 로 mysql2 와 똑같이 읽습니다.
// - 글자 ID 되돌리기는 어댑터(mysqldb.js rowsOf)의 이름 규칙과 같습니다.
//   Hyperdrive 는 열 정보에 원래 표(orgTable)를 주지 않아 어댑터도 이름
//   규칙을 씁니다.
// - 이름이 겹치면 뒤 열 값이 앞 열을 덮고 키 자리는 처음 자리입니다(rowsOf 와 같음).
import { TEXT_ID_COLUMNS } from './mysqldb.js';

/**
 * 열 목록을 `CAST(JSON_ARRAY(...) AS CHAR)` 식으로 만듭니다.
 *
 * cols 는 { expr, name, datetime?, float? } 들입니다. expr 은 SQL 식, name 은 응답
 * 키입니다. 글자(CHAR)로 받는 것은 mysql2 가 JSON 형(바이너리 문자셋)을
 * 칸마다 따로 풀지 않고, 여러 행을 한 번에 풀게 하려는 것입니다.
 */
export function jsonArraySql(cols) {
  const exprs = cols.map((c) => (c.datetime || c.float ? `CAST(${c.expr} AS CHAR)` : c.expr));
  return `CAST(JSON_ARRAY(${exprs.join(', ')}) AS CHAR)`;
}

/**
 * 글자 프로토콜의 실수 글자를 mysql2(3.x) 의 Packet.parseFloat 와 똑같이 읽습니다.
 *
 * 17글자를 넘거나 지수(e)가 있으면 Number.parseFloat 이고, 아니면 숫자를
 * 하나씩 곱해 더한 뒤 소수 자릿수만큼의 10의 거듭제곱으로 나눕니다. 연산
 * 순서까지 mysql2 와 같아야 같은 값이 나옵니다. NULL 은 null 입니다.
 */
export function mysqlTextFloat(s) {
  if (s === null || s === undefined) return null;
  const len = s.length;
  if (len === 0) return 0;
  if (len > 17) return Number.parseFloat(s);
  let i = 0;
  let result = 0;
  let factor = 1;
  let pastDot = false;
  if (s.charCodeAt(i) === 45) { // '-'
    i += 1;
    factor = -1;
  }
  if (s.charCodeAt(i) === 43) i += 1; // '+'
  for (; i < len; i += 1) {
    const c = s.charCodeAt(i);
    if (c === 46) { // '.'
      pastDot = true;
    } else if (c === 101 || c === 69) { // 'e' 'E'
      return Number.parseFloat(s);
    } else {
      result *= 10;
      result += c - 48;
      if (pastDot) factor *= 10;
    }
  }
  return result / factor;
}

/**
 * JSON 배열 글자들을 객체 배열로 바꿉니다.
 *
 * texts 는 행마다 jsonArraySql 의 결과 글자, names 는 cols 의 name 순서입니다.
 * floats 는 칸마다 mysqlTextFloat 로 읽을지(col.float)입니다. 행 수만큼
 * JSON.parse 를 부르지 않고 한 번에 풉니다.
 */
export function objectsFromJsonTexts(texts, names, textColumns = TEXT_ID_COLUMNS, floats = null) {
  if (!texts.length) return [];
  const arrs = JSON.parse(`[${texts.join(',')}]`);
  const n = names.length;
  const toText = names.map((name) => textColumns.has(name));
  const toFloat = names.map((_, i) => Boolean(floats && floats[i]));
  const out = new Array(arrs.length);
  for (let r = 0; r < arrs.length; r += 1) {
    const a = arrs[r];
    if (!Array.isArray(a) || a.length !== n) {
      throw new Error(`JSON 행의 칸 수가 다릅니다: ${Array.isArray(a) ? a.length : typeof a} != ${n}`);
    }
    const o = {};
    for (let i = 0; i < n; i += 1) {
      let v = a[i];
      if (toFloat[i]) v = mysqlTextFloat(v);
      if (toText[i] && typeof v === 'number') v = String(v);
      o[names[i]] = v;
    }
    out[r] = o;
  }
  return out;
}

/**
 * `SELECT <JSON 배열> AS j <rest>` 를 보내고 객체 배열을 돌려줍니다.
 *
 * rest 는 FROM 부터 끝(ORDER BY·LIMIT 포함)까지입니다. 행 순서는 보통
 * 질의와 같이 rest 의 ORDER BY 가 정합니다.
 */
export async function jsonRows(db, cols, rest, binds) {
  const rows = await db.prepare(`SELECT ${jsonArraySql(cols)} AS j ${rest}`)
    .bind(...binds).raw();
  const texts = new Array(rows.length);
  for (let i = 0; i < rows.length; i += 1) texts[i] = rows[i][0];
  return objectsFromJsonTexts(
    texts, cols.map((c) => c.name), TEXT_ID_COLUMNS, cols.map((c) => Boolean(c.float)));
}

// GROUP_CONCAT 결과 길이 한도(바이트)입니다. 기본값(1024)이면 잘려 이 질의에서만
// SET_VAR 힌트로 늘립니다. 결과 한 행은 max_allowed_packet(32MB)을 넘을 수 없어
// 그보다 크게 잡을 뜻은 없습니다.
export const JSON_CONCAT_MAX = 32 * 1024 * 1024;

/**
 * jsonRows 와 같지만 모든 행을 GROUP_CONCAT 으로 이은 한 행으로 받습니다.
 *
 * 행마다 받으면 mysql2 가 행마다 패킷·해석기를 거치고 긴 글자를 하나씩
 * 풉니다. 시즌 기록(400행 x 50칸)에서는 그 몫이 칸 해석을 줄인 이득과
 * 비슷해 CPU 가 거의 줄지 않았습니다(스테이징 A/B 32 -> 30ms). 한 행으로
 * 받으면 37 -> 22ms 였습니다.
 *
 * 순서: orderSql 은 from 의 ORDER BY 와 같은 식입니다. 안쪽 질의가 그
 * 순서로 ROW_NUMBER() 를 매기고(from 의 ORDER BY ... LIMIT 가 행을 고름)
 * 바깥 GROUP_CONCAT 이 그 번호 순으로 잇습니다. GROUP_CONCAT 의 ORDER BY
 * 에 원래 키를 그대로 쓰면 NULL 을 0 과 같게 놓아 보통 ORDER BY(NULL 은
 * 가장 작음)와 순서가 달라집니다(타율 NULL·0 이 섞임, 실제로 확인). 번호는
 * NULL 이 없어 그런 일이 없습니다. 키가 행 하나를 정해야(동점 없음) 순서가
 * 보통 질의와 같습니다.
 *
 * 행 수가 다르거나 글자를 못 풀면(잘림) 경고를 남기고 jsonRows 로 다시
 * 읽습니다.
 */
export async function jsonRowsOnce(db, cols, from, binds, orderSql) {
  const row = await db.prepare(
    `SELECT /*+ SET_VAR(group_concat_max_len = ${JSON_CONCAT_MAX}) */ COUNT(*) AS n, `
    + "GROUP_CONCAT(t.j ORDER BY t.rn SEPARATOR ',') AS j "
    + `FROM (SELECT ${jsonArraySql(cols)} AS j, ROW_NUMBER() OVER (ORDER BY ${orderSql}) AS rn `
    + `${from}) AS t`,
  ).bind(...binds).first();
  const n = row ? Number(row.n) : -1;
  if (n === 0 && (row.j === null || row.j === undefined)) return [];
  if (row && typeof row.j === 'string') {
    let rows = null;
    try {
      rows = objectsFromJsonTexts(
        [row.j], cols.map((c) => c.name), TEXT_ID_COLUMNS, cols.map((c) => Boolean(c.float)));
    } catch {
      rows = null;
    }
    if (rows && rows.length === n) return rows;
  }
  // 응답은 같고 CPU 만 더 듭니다. tail 에서 보이게 남깁니다.
  console.warn('jsonRowsOnce: GROUP_CONCAT 결과를 못 풀어 행마다 읽습니다');
  return jsonRows(db, cols, from, binds);
}
