// 어느 DB 를 읽을지 정합니다.
//
// wrangler.toml 의 vars.DB_BACKEND 가 'mysql' 이면 env.DB 와 샤드 바인딩
// 6개를 같은 MySQL 어댑터로 바꿔 끼웁니다. 라우트는 바뀌지 않습니다.
// 되돌리기는 이 값을 'd1' 로 바꿔 다시 배포하는 것입니다.
import { SHARDS } from './shard.js';
import { hyperdriveDb } from './mysqldb.js';
import { isMysql } from './backendflag.js';

export { isMysql };

export function withBackend(env, make = hyperdriveDb) {
  // D1 이면 아무것도 바꾸지 않습니다(done 이 null 이면 index.js 가 응답을
  // 감싸지 않습니다). 운영 동작을 전환 전과 똑같이 둡니다.
  if (!isMysql(env)) return { env, done: null };
  const db = make(env);
  const swapped = { ...env, DB: db };
  for (const s of SHARDS) swapped[s.binding] = db;
  return { env: swapped, done: () => db.close() };
}

/**
 * 응답 본문을 끝까지 보낸 뒤 연결을 닫습니다.
 *
 * CSV 내려받기는 본문을 흘려보내는 동안 질의를 계속 합니다. 응답을
 * 돌려주자마자 닫으면 중간에 끊깁니다.
 */
export function closeAfterBody(res, done, ctx) {
  if (!res.body) {
    ctx.waitUntil(done());
    return res;
  }
  const ts = new TransformStream({
    flush() { ctx.waitUntil(done()); },
  });
  return new Response(res.body.pipeThrough(ts), res);
}
