// 경로별 캐시 수명을 정합니다.
//
// Workers Cache(2026-07-06)는 전 플랜 무료이고 workers.dev 에서도 돕니다.
// **캐시에 맞으면 Worker 가 아예 실행되지 않아 D1 읽기가 0 입니다.**
// 읽기 한도(하루 500만 행)를 지키는 가장 강한 수단입니다.
//
// 응답에 `Cache-Control` 이 있어야 캐시가 걸립니다. 그래서 라우트마다
// 붙이지 않고 여기서 경로를 보고 한 번에 붙입니다.
//
// 수명은 데이터가 바뀌는 주기에 맞춥니다. 너무 길면 갱신이 늦게 보이고,
// 너무 짧으면 캐시가 무의미합니다.

// 실시간으로 바뀌는 것입니다. 원본도 캐시를 짧게 걸어 두었습니다
// (leaders 600초, standings 300초, schedule 30초 - src/lib/cache.js).
// 그 값보다 길게 잡으면 화면이 원본보다 늦게 갱신됩니다.
const LIVE = [
  ['/schedule', 30],
  ['/standings', 300],
  ['/games', 300],
  ['/leaders', 600],
];

// 거의 바뀌지 않는 것입니다. 로고는 D1 BLOB 이고 시즌 중에 바뀔 일이
// 없습니다.
const STATIC_LONG = ['/logo/'];

// 나머지는 수집이 하루 한 번 도므로 한 시간이면 충분합니다.
// stale-while-revalidate 를 붙여, 만료 직후 요청은 낡은 값을 즉시 주고
// 뒤에서 갱신합니다. 사용자가 기다리지 않습니다.
const DEFAULT_TTL = 3600;
const SWR = 86400;

/**
 * 이 경로에 붙일 Cache-Control 값입니다. 붙이지 않을 곳이면 null 입니다.
 *
 * **200 응답에만 붙이십시오.** 오류를 캐시하면 한 번의 실패가 한 시간
 * 동안 굳습니다. 판단은 부르는 쪽이 합니다.
 */
export function cacheControlFor(pathname) {
  for (const [prefix, ttl] of LIVE) {
    if (pathname === prefix || pathname.startsWith(`${prefix}/`)) {
      return `public, max-age=${ttl}`;
    }
  }
  for (const prefix of STATIC_LONG) {
    if (pathname.startsWith(prefix)) {
      return 'public, max-age=604800';
    }
  }
  return `public, max-age=${DEFAULT_TTL}, stale-while-revalidate=${SWR}`;
}

/**
 * 응답에 Cache-Control 을 붙여 돌려줍니다.
 *
 * 원래 응답을 바꾸지 않고 새로 만듭니다. Response 는 헤더가 봉인될 수
 * 있어 그 자리에서 고치면 실패할 때가 있습니다.
 *
 * 스트리밍 응답(CSV)도 body 를 그대로 넘기므로 흐름이 끊기지 않습니다.
 */
export function withCache(response, pathname) {
  // 200 이 아니면 캐시하지 않습니다. 404·413·500 이 굳으면 고친 뒤에도
  // 한동안 옛 응답이 나갑니다.
  if (response.status !== 200) return response;
  // 이미 정해 둔 것이 있으면 존중합니다.
  if (response.headers.has('cache-control')) return response;

  const value = cacheControlFor(pathname);
  if (!value) return response;

  const headers = new Headers(response.headers);
  headers.set('cache-control', value);
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}
