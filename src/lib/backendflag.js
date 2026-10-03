// 지금 MySQL 을 읽는지 봅니다. 의존이 없어 어디서든 import 해도 순환이
// 생기지 않습니다(backend.js 는 shard.js 를 import 합니다).
export function isMysql(env) {
  return Boolean(env) && env.DB_BACKEND === 'mysql';
}
