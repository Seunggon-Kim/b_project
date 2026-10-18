// src/routes/ops.js
// GET /ops/storage — 공개 '데이터 관리' 화면의 저장소 현황입니다.
// 계산은 lib/opsstorage.js 에 있습니다(이 파일은 컬럼 사전 JSON 을 import 해서
// node:test 가 직접 읽지 못합니다).

import { json, dbError } from '../lib/respond.js';
import { columnDict } from '../lib/coldict.js';
import { storageBody, SIZE_SQL, COUNT_SQL, BQ_SQL } from '../lib/opsstorage.js';

export async function opsStorage(request, env) {
  const db = env.MYSQL;
  let sizes;
  let counts;
  try {
    sizes = (await db.prepare(SIZE_SQL).all()).results || [];
    counts = (await db.prepare(COUNT_SQL).all()).results || [];
  } catch (err) {
    return dbError(err);
  }
  // 표가 아직 없거나(첫 주간 실행 전) 읽기에 실패해도 MySQL 부분은 보여 줍니다.
  let bq = null;
  try {
    bq = (await db.prepare(BQ_SQL).all()).results || [];
  } catch {
    bq = null;
  }
  return json(storageBody({ sizes, counts, bq, tables: columnDict().tables || {}, now: new Date() }));
}
