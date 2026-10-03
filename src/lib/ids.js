// D1 에서 INTEGER 였던 ID 를 MySQL 에서도 숫자로 돌려주는 도우미입니다.
//
// Hyperdrive 는 mysql2 의 열 정보 가운데 원래 표(orgTable)를 주지 않아,
// MysqlDb 가 열 이름 규칙(TEXT_ID_COLUMNS)으로 물러서면서 D1 에서도
// 숫자였던 ID(kbo_roster 의 player_id 등)까지 글자가 됩니다.
// 그런 값만 라우트에서 숫자로 되돌립니다.
import { TEXT_ID_COLUMNS, TEXT_ID_TABLES } from './mysqldb.js';
import { isMysql } from './backendflag.js';

/**
 * 숫자만으로 된 글자는 숫자로, 그 밖의 값은 그대로 돌려줍니다.
 * null·undefined·이미 숫자인 값은 바뀌지 않으므로, 값이 처음부터 숫자인
 * D1 에서는 항등 함수입니다.
 */
export function intIdOrSame(v) {
  if (typeof v === 'string' && /^\d+$/.test(v)) return Number(v);
  return v;
}

/** 행에서 TEXT_ID_COLUMNS 열만 intIdOrSame 으로 바꾼 사본입니다. */
export function intIdRow(row) {
  if (!row || typeof row !== 'object') return row;
  const out = { ...row };
  for (const c of TEXT_ID_COLUMNS) {
    if (Object.prototype.hasOwnProperty.call(out, c)) out[c] = intIdOrSame(out[c]);
  }
  return out;
}

/**
 * 데이터 탐색기용 행 변환입니다. MySQL 이고 D1 에서 INTEGER 였던 ID 를 가진
 * 표(TEXT_ID_TABLES 가 아닌 표)일 때만 intIdRow 이고, 그 밖에는(D1 포함)
 * 행을 건드리지 않는 항등 함수입니다.
 */
export function idFixer(env, tableName) {
  if (!isMysql(env) || TEXT_ID_TABLES.has(tableName)) return (r) => r;
  return intIdRow;
}
