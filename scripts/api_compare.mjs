// 두 API 의 응답을 같은 URL 목록으로 견줍니다(3단계).
//
//   node scripts/api_compare.mjs --a https://kbo-api.bstats-baseball.workers.dev \
//     --b https://kbo-api-stg-my.bstats-baseball.workers.dev --out docs/mysql-migration/api-compare-mysql.md
//
// 캐시를 피하려고 URL 마다 `_cmp=<시각>` 을 붙입니다(라우트는 모르는
// 매개변수를 무시합니다). 그만큼 DB 를 실제로 읽으니 D1 쪽은 하루 한도를
// 보고 돌립니다.
import { readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const REL = 1e-9;

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
  const res = await fetch(`${base}${path}${sep}_cmp=${tag}`);
  const text = await res.text();
  let body;
  try { body = JSON.parse(text); } catch { body = { _text: text.slice(0, 200) }; }
  return { status: res.status, body };
}

function arg(name, dflt) {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : dflt;
}

async function main() {
  const a = arg('a'); const b = arg('b');
  const urls = readFileSync(arg('urls', 'scripts/api_compare_urls.txt'), 'utf8')
    .split(/\r?\n/).map((s) => s.trim()).filter((s) => s && !s.startsWith('#'));
  const tag = Date.now();
  const lines = [`# API 대조`, '', `- A: ${a}`, `- B: ${b}`, `- URL ${urls.length}개`, ''];
  let bad = 0;
  for (const u of urls) {
    const [ra, rb] = await Promise.all([fetchJson(a, u, tag), fetchJson(b, u, tag)]);
    const d = ra.status !== rb.status ? [`상태 ${ra.status} ≠ ${rb.status}`] : diffJson(ra.body, rb.body);
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
