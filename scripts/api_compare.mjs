// 두 API 의 응답을 같은 URL 목록으로 견줍니다(3단계).
//
//   node scripts/api_compare.mjs --a https://kbo-api.bstats-baseball.workers.dev \
//     --b https://kbo-api-stg-my.bstats-baseball.workers.dev --out docs/mysql-migration/api-compare-mysql.md
//
// 캐시를 피하려고 URL 마다 `_cmp=<시각>` 을 붙입니다(라우트는 모르는
// 매개변수를 무시합니다). 그만큼 DB 를 실제로 읽으니 D1 쪽은 하루 한도를
// 보고 돌립니다.
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

// 숫자 허용 오차: 크기 1 미만에서는 절대 1e-9, 그 이상에서는 상대 1e-9 입니다.
const REL = 1e-9;
const TIMEOUT_MS = 30000;

function isNum(x) { return typeof x === 'number' && Number.isFinite(x); }

export function diffJson(a, b, path = '$', out = []) {
  if (isNum(a) && isNum(b)) {
    const scale = Math.max(1, Math.abs(a), Math.abs(b));
    if (Math.abs(a - b) > REL * scale) out.push(`${path}: ${a} ≠ ${b}`);
    return out;
  }
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) out.push(`${path}: 길이 ${a.length} ≠ ${b.length}`);
    for (let i = 0; i < Math.min(a.length, b.length); i += 1) diffJson(a[i], b[i], `${path}[${i}]`, out);
    return out;
  }
  if (a && b && typeof a === 'object' && typeof b === 'object' && !Array.isArray(a) && !Array.isArray(b)) {
    for (const k of Object.keys(a)) {
      if (!(k in b)) out.push(`${path}.${k}: B 에 없음`);
      else diffJson(a[k], b[k], `${path}.${k}`, out);
    }
    for (const k of Object.keys(b)) if (!(k in a)) out.push(`${path}.${k}: A 에 없음`);
    return out;
  }
  if (a !== b) out.push(`${path}: ${JSON.stringify(a)} ≠ ${JSON.stringify(b)}`);
  return out;
}

async function fetchJson(base, path, tag) {
  const sep = path.includes('?') ? '&' : '?';
  const res = await fetch(`${base}${path}${sep}_cmp=${tag}`, { signal: AbortSignal.timeout(TIMEOUT_MS) });
  const bytes = Buffer.from(await res.arrayBuffer());
  const text = bytes.toString('utf8');
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    // JSON 이 아니면(CSV·이미지) 전체 바이트의 해시로 견줍니다. _head 는 보고용입니다.
    body = {
      _type: res.headers.get('content-type') || '',
      _sha256: createHash('sha256').update(bytes).digest('hex'),
      _bytes: bytes.length,
      _head: text.slice(0, 120),
    };
  }
  return { status: res.status, body };
}

/** 'URL 파일 한 줄' 을 읽습니다. 앞에 세 자리 상태 코드를 붙이면 기대 상태입니다. */
export function parseUrlLine(line) {
  const m = /^(\d{3})\s+(\S.*)$/.exec(line.trim());
  return m ? { path: m[2].trim(), expect: Number(m[1]) } : { path: line.trim(), expect: 200 };
}

function stripHead(body) {
  if (body && typeof body === 'object' && '_sha256' in body) {
    const { _head, ...rest } = body;
    return rest;
  }
  return body;
}

/** 응답 두 개의 차이 줄 목록입니다. 둘 다 기대 상태와 같아야 본문을 견줍니다. */
export function compareResponses(ra, rb, expect = 200) {
  if (ra.status !== expect || rb.status !== expect) {
    return [`상태 A=${ra.status} B=${rb.status} (기대 ${expect})`];
  }
  return diffJson(stripHead(ra.body), stripHead(rb.body));
}

function arg(name, dflt) {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : dflt;
}

async function main() {
  const a = arg('a'); const b = arg('b');
  if (!a || !b) {
    console.error('사용법: node scripts/api_compare.mjs --a <기준 URL> --b <비교 URL> [--urls 파일] [--out 파일]');
    process.exitCode = 2;
    return;
  }
  const urls = readFileSync(arg('urls', 'scripts/api_compare_urls.txt'), 'utf8')
    .split(/\r?\n/).map((s) => s.trim()).filter((s) => s && !s.startsWith('#')).map(parseUrlLine);
  const tag = Date.now();
  const lines = [`# API 대조`, '', `- A: ${a}`, `- B: ${b}`, `- URL ${urls.length}개`, ''];
  let bad = 0;
  for (const { path: u, expect } of urls) {
    let d;
    try {
      const [ra, rb] = await Promise.all([fetchJson(a, u, tag), fetchJson(b, u, tag)]);
      d = compareResponses(ra, rb, expect);
    } catch (e) {
      d = [`요청 실패: ${e && e.message ? e.message : e}`];
    }
    if (d.length) {
      bad += 1;
      lines.push(`## ${u}`, '', `차이 ${d.length}건${d.length > 20 ? '(앞 20건)' : ''}`, '');
      for (const x of d.slice(0, 20)) lines.push(`- ${x}`);
      lines.push('');
    }
  }
  lines.splice(5, 0, `- 다른 URL ${bad}개`);
  const text = lines.join('\n') + '\n';
  const out = arg('out');
  if (out) writeFileSync(out, text);
  console.log(text);
  process.exitCode = bad ? 1 : 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
