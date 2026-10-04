// 두 API 의 응답을 같은 URL 목록으로 견줍니다(3단계).
//
//   node scripts/api_compare.mjs --a https://kbo-api.bstats-baseball.workers.dev \
//     --b https://kbo-api-stg-my.bstats-baseball.workers.dev --out docs/mysql-migration/api-compare-mysql.md
//
// --unordered 를 붙이면 배열을 순서 없는 다중집합으로 견줍니다(동점 행의
// 순서처럼 DB 마다 다를 수 있는 순서만 다른 경우를 가려냅니다). 기본은
// 순서까지 견줍니다. 운영 ↔ 스테이징 대조는 기본(순서 있음)으로 돌립니다.
//
// 캐시를 피하려고 URL 마다 `_cmp=<시각>` 을 붙입니다(라우트는 모르는
// 매개변수를 무시합니다). 그만큼 양쪽 모두 DB(MySQL)를 실제로 읽습니다.
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

// 숫자 허용 오차: 크기 1 미만에서는 절대 1e-9, 그 이상에서는 상대 1e-9 입니다.
const REL = 1e-9;
const TIMEOUT_MS = 30000;

function isNum(x) { return typeof x === 'number' && Number.isFinite(x); }

// --unordered 정렬 키에서 실수를 반올림하는 유효 자릿수입니다. 허용 오차
// (REL)보다 거칠게 잡아, 허용 오차 안에서만 다른 두 값이 같은 키가 되게
// 합니다. 그래야 끝자리 차이로 정렬 순서가 갈려 짝이 어긋나지 않습니다.
const KEY_DIGITS = 12;

function keyReplacer(_k, v) {
  return isNum(v) && !Number.isInteger(v) ? Number(v.toPrecision(KEY_DIGITS)) : v;
}

/**
 * 값을 정해진 모양으로 바꿉니다(원본은 그대로 둡니다).
 *
 * 객체는 키를 정렬하고, 배열은 원소마다 이 모양으로 바꾼 뒤 그 JSON 글자
 * (canonicalKey)로 정렬합니다. 중첩 배열도 같습니다. 순서만 다른 두 값은
 * 같은 모양이 되고, 원소 개수는 그대로라 다중집합으로 견주게 됩니다.
 */
export function canonicalize(v) {
  if (Array.isArray(v)) {
    return v
      .map((x) => {
        const c = canonicalize(x);
        return { c, k: JSON.stringify(c, keyReplacer) };
      })
      .sort((p, q) => (p.k < q.k ? -1 : p.k > q.k ? 1 : 0))
      .map((e) => e.c);
  }
  if (v && typeof v === 'object') {
    const out = {};
    for (const k of Object.keys(v).sort()) {
      // '__proto__' 같은 키도 자기 속성으로 둡니다(대입하면 프로토타입이 바뀜).
      Object.defineProperty(out, k, {
        value: canonicalize(v[k]), enumerable: true, writable: true, configurable: true,
      });
    }
    return out;
  }
  return v;
}

/** 정렬 키입니다. 순서만 다른 두 값은 같은 글자가 됩니다. */
export function canonicalKey(v) {
  return JSON.stringify(canonicalize(v), keyReplacer);
}

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
    // `in` 은 상속한 이름('constructor' 등)도 있다고 봅니다. 자기 속성만 봅니다.
    for (const k of Object.keys(a)) {
      if (!Object.hasOwn(b, k)) out.push(`${path}.${k}: B 에 없음`);
      else diffJson(a[k], b[k], `${path}.${k}`, out);
    }
    for (const k of Object.keys(b)) if (!Object.hasOwn(a, k)) out.push(`${path}.${k}: A 에 없음`);
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
  if (body && typeof body === 'object' && Object.hasOwn(body, '_sha256')) {
    const { _head, ...rest } = body;
    return rest;
  }
  return body;
}

/**
 * 응답 두 개의 차이 줄 목록입니다. 둘 다 기대 상태와 같아야 본문을 견줍니다.
 *
 * unordered 이면 배열을 다중집합으로 견줍니다(canonicalize). 그때 차이 줄의
 * 배열 번호는 정렬한 뒤의 번호입니다.
 */
export function compareResponses(ra, rb, expect = 200, { unordered = false } = {}) {
  if (ra.status !== expect || rb.status !== expect) {
    return [`상태 A=${ra.status} B=${rb.status} (기대 ${expect})`];
  }
  const a = stripHead(ra.body);
  const b = stripHead(rb.body);
  return unordered ? diffJson(canonicalize(a), canonicalize(b)) : diffJson(a, b);
}

function arg(name, dflt) {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : dflt;
}

async function main() {
  const a = arg('a'); const b = arg('b');
  if (!a || !b) {
    console.error('사용법: node scripts/api_compare.mjs --a <기준 URL> --b <비교 URL> [--urls 파일] [--out 파일] [--unordered]');
    process.exitCode = 2;
    return;
  }
  const urls = readFileSync(arg('urls', 'scripts/api_compare_urls.txt'), 'utf8')
    .split(/\r?\n/).map((s) => s.trim()).filter((s) => s && !s.startsWith('#')).map(parseUrlLine);
  const unordered = process.argv.includes('--unordered');
  const tag = Date.now();
  const lines = [`# API 대조`, '', `- A: ${a}`, `- B: ${b}`, `- URL ${urls.length}개`,
    `- 배열 순서: ${unordered ? '무시(--unordered, 다중집합)' : '견줌'}`, ''];
  // 다른 URL 수를 머리말 끝(빈 줄 앞)에 끼웁니다.
  const headEnd = lines.length - 1;
  let bad = 0;
  for (const { path: u, expect } of urls) {
    let d;
    try {
      const [ra, rb] = await Promise.all([fetchJson(a, u, tag), fetchJson(b, u, tag)]);
      d = compareResponses(ra, rb, expect, { unordered });
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
  lines.splice(headEnd, 0, `- 다른 URL ${bad}개`);
  const text = lines.join('\n') + '\n';
  const out = arg('out');
  if (out) writeFileSync(out, text);
  console.log(text);
  process.exitCode = bad ? 1 : 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
