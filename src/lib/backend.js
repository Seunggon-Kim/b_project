// 요청마다 MySQL(Hyperdrive) 어댑터를 하나 만들어 env.DB 자리에 끼웁니다.
//
// 라우트는 env.DB.prepare(sql).bind(...).all()/.first() 를 부릅니다
// (lib/mysqldb.js). 연결은 첫 질의 때 열고, 응답을 보낸 뒤 닫습니다.
import { hyperdriveDb } from './mysqldb.js';
import { dbError } from './respond.js';

export function withBackend(env, make = hyperdriveDb) {
  const db = make(env);
  return { env: { ...env, DB: db }, done: () => db.close(), db };
}

/**
 * 라우트가 돌려준 응답을 마지막으로 확인합니다.
 *
 * MySQL 연결이 끊긴 적이 있으면(db.failed) 라우트 응답 대신 503·no-store
 * 를 돌려줍니다. 몇몇 라우트는 질의 오류를 삼키고 0·빈칸을 내는데, 그것이
 * 200 으로 나가면 엣지가 한 시간 동안 그 값을 보여 줍니다.
 *
 * 연결이 멀쩡하면 받은 응답을 그대로(같은 객체) 돌려줍니다.
 */
export function finalizeResponse(res, backend) {
  const failed = backend && backend.db ? backend.db.failed : null;
  if (!failed) return res;
  // 버리는 본문(CSV 스트림 등)은 닫아 더 읽지 않게 합니다.
  if (res && res.body) res.body.cancel().catch(() => {});
  return dbError(failed);
}

/**
 * MySQL 연결을 닫을 때를 정합니다.
 *
 * CSV 내려받기는 본문을 흘려보내는 동안 질의를 계속 합니다. 응답을
 * 돌려주자마자 닫으면 중간에 끊기므로 본문을 끝까지 보낸 뒤 닫습니다.
 *
 * 그 밖의 응답(JSON·이미지)은 본문이 이미 다 만들어져 있습니다. 감싸면
 * 청크 전송이 되고 손님이 다 받을 때까지 연결을 붙잡으므로, 응답은 그대로
 * (같은 객체) 돌려주고 닫기만 예약합니다.
 */
export function closeAfterBody(res, done, ctx) {
  const type = (res.headers.get('content-type') || '').toLowerCase();
  if (!res.body || !type.startsWith('text/csv')) {
    ctx.waitUntil(done());
    return res;
  }
  const ts = new TransformStream({
    flush() { ctx.waitUntil(done()); },
  });
  return new Response(res.body.pipeThrough(ts), res);
}
