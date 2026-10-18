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
    // 오류 원문(권한 오류의 계정·주소 등)은 공개 응답에 싣지 않습니다.
    return dbError(err, { detail: '저장소 현황을 읽지 못했습니다.' });
  }
  // 표가 아직 없거나(첫 주간 실행 전) 읽기에 실패해도 MySQL 부분은 보여 줍니다.
  let bq = null;
  try {
    bq = (await db.prepare(BQ_SQL).all()).results || [];
  } catch (err) {
    // 원문은 남기지 않고 오류 코드만 한 줄 남깁니다.
    console.warn('ops/storage: meta_bq_tables 읽기 실패', err && err.code);
    bq = null;
  }
  return json(storageBody({ sizes, counts, bq, tables: columnDict().tables || {}, now: new Date() }));
}
