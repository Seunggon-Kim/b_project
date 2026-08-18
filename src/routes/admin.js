// 관리용 엔드포인트입니다. 지금은 캐시 비우기 하나뿐입니다.
//
// ## 왜 필요한가
//
// Workers Cache 를 켜 두면 캐시에 맞는 동안 Worker 가 실행되지 않습니다.
// 읽기 한도를 지키는 데는 좋지만, 새 데이터를 D1 에 넣어도 캐시가 만료될
// 때까지(기본 한 시간) 화면은 어제 숫자를 보여 줍니다. 2026 시즌을 넣었을
// 때 실제로 겪은 문제입니다. 그래서 적재가 끝나면 캐시를 비웁니다.
//
// ## 왜 토큰으로 막는가
//
// 저장소가 공개이고 Worker 주소도 공개입니다. 막지 않으면 누구나 캐시를
// 계속 비울 수 있고, 그러면 모든 요청이 D1 로 내려가 하루 500만 행 읽기
// 한도를 태웁니다. 한도를 넘으면 느려지는 게 아니라 질의가 거부됩니다.
//
// 토큰은 Worker 시크릿으로 둡니다(코드·저장소에 두지 않습니다).
//
//     npx wrangler secret put ADMIN_TOKEN
//
// 부르는 쪽:
//
//     curl -X POST https://kbo-api.<sub>.workers.dev/admin/purge-cache \
//       -H "Authorization: Bearer $ADMIN_TOKEN"

import { json } from '../lib/respond.js';

/**
 * 두 문자열을 같은 시간으로 비교합니다.
 *
 * `a === b` 는 다른 글자가 나오는 즉시 끝나서, 응답 시간으로 토큰을
 * 한 글자씩 알아낼 여지가 있습니다. 실제로 뚫기는 어렵지만 몇 줄이면
 * 막을 수 있는 일을 굳이 남겨 둘 이유가 없습니다.
 */
function sameSecret(a, b) {
  const x = new TextEncoder().encode(a);
  const y = new TextEncoder().encode(b);
  // 길이가 다르면 어차피 다릅니다. 길이 자체는 숨기지 못하지만,
  // 비교는 끝까지 돌려 내용으로 시간이 갈리지 않게 합니다.
  let diff = x.length ^ y.length;
  const n = Math.max(x.length, y.length);
  for (let i = 0; i < n; i += 1) {
    diff |= (x[i] || 0) ^ (y[i] || 0);
  }
  return diff === 0;
}

function bearer(request) {
  const raw = request.headers.get('authorization') || '';
  // 'Bearer ' 로 시작하지 않으면 받지 않습니다. 형식을 느슨하게 받으면
  // 프록시나 로그에 토큰이 다른 모양으로 남아 추적이 어려워집니다.
  if (!raw.startsWith('Bearer ')) return null;
  return raw.slice(7);
}

export async function purgeCache(request, env, ctx) {
  const secret = env && env.ADMIN_TOKEN;
  // 시크릿을 안 걸어 뒀으면 잠급니다. 없을 때 통과시키면 공개 상태가
  // 됩니다.
  if (!secret) {
    return json({
      detail: 'ADMIN_TOKEN 시크릿이 없습니다. npx wrangler secret put ADMIN_TOKEN',
    }, 503);
  }

  const given = bearer(request);
  if (given === null || !sameSecret(given, secret)) {
    return json({ detail: 'Unauthorized' }, 401);
  }

  const cache = ctx && ctx.cache;
  if (!cache || typeof cache.purge !== 'function') {
    // 200 을 주면 워크플로가 성공으로 보고 넘어갑니다. 그러면 화면이
    // 계속 옛 숫자를 보여 주는데 아무도 모릅니다.
    return json({
      detail: 'ctx.cache.purge 를 쓸 수 없습니다. wrangler.toml 의 [cache] 와 '
        + 'compatibility_date 를 확인하십시오.',
    }, 501);
  }

  try {
    // 경로를 골라 비울 수도 있지만(pathPrefixes), 적재가 여러 표를
    // 건드리면 어떤 경로가 영향을 받는지 세기 어렵습니다. 하루 한 번
    // 도는 일이라 통째로 비워도 부담이 적습니다.
    await cache.purge({ purgeEverything: true });
  } catch (err) {
    return json({ detail: String(err && err.message ? err.message : err) }, 500);
  }

  return json({ purged: true, scope: 'everything' });
}
