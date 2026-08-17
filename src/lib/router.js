// 경로 매칭과 쿼리 파라미터 파서.
//
// 외부 라우팅 라이브러리를 쓰지 않습니다. 필요한 패턴이 `/a/b` 와 `/a/:id/b`
// 두 가지뿐이라, 의존성을 하나 늘릴 이유가 없습니다.

/**
 * 패턴과 경로를 맞춰 보고 파라미터 객체를 돌려줍니다. 안 맞으면 null 입니다.
 * 세그먼트 개수가 같아야 매칭됩니다. 그래야 `/db/table/:name` 이
 * `/db/table/players/csv` 를 잘못 먹지 않습니다.
 */
export function matchPath(pattern, pathname) {
  const p = pattern.split('/');
  const s = pathname.split('/');
  if (p.length !== s.length) return null;

  const params = {};
  for (let i = 0; i < p.length; i += 1) {
    if (p[i].startsWith(':')) {
      if (s[i] === '') return null;
      try {
        params[p[i].slice(1)] = decodeURIComponent(s[i]);
      } catch {
        params[p[i].slice(1)] = s[i];
      }
    } else if (p[i] !== s[i]) {
      return null;
    }
  }
  return params;
}

export function queryInt(url, name, fallback) {
  const raw = url.searchParams.get(name);
  if (raw === null || raw === '') return fallback;
  const n = Number.parseInt(raw, 10);
  return Number.isNaN(n) ? fallback : n;
}

export function queryStr(url, name, fallback) {
  const raw = url.searchParams.get(name);
  return raw === null ? fallback : raw;
}

export function createRouter() {
  const routes = [];
  return {
    add(method, pattern, handler) {
      routes.push({ method, pattern, handler });
      return this;
    },
    async handle(request, env, ctx) {
      const url = new URL(request.url);
      // 끝의 슬래시를 떼어 `/teams/` 와 `/teams` 를 같게 봅니다.
      const pathname = url.pathname.length > 1
        ? url.pathname.replace(/\/+$/, '')
        : url.pathname;

      let pathMatched = false;
      for (const r of routes) {
        const params = matchPath(r.pattern, pathname);
        if (params === null) continue;
        pathMatched = true;
        if (r.method !== request.method) continue;
        return r.handler(request, env, ctx, params);
      }
      // 경로는 있는데 메서드가 다르면 405, 경로 자체가 없으면 404.
      // FastAPI 가 그렇게 동작하므로 맞춥니다.
      return unmatched(pathMatched);
    },
  };
}

function unmatched(pathMatched) {
  const detail = pathMatched ? 'Method Not Allowed' : 'Not Found';
  return new Response(JSON.stringify({ detail }), {
    status: pathMatched ? 405 : 404,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'access-control-allow-origin': '*',
    },
  });
}
