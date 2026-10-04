// API Worker 에 D1 이 다시 들어오지 않게 막습니다.
//
// D1 은 2026-10-04 에 Worker 에서 걷어냈습니다. Worker 는 MySQL(Hyperdrive)만
// 읽습니다. wrangler.toml 에 D1 바인딩이 있거나, src/ 에 D1 시절 이름(env.DB,
// DB_BACKEND 스위치, isMysql, 샤드 바인딩·모듈)이 있으면 지운 D1 을 부르다가
// 배포 뒤에야 실패하거나, 없는 스위치를 믿고 되돌리기를 시도하게 됩니다.
//
// 꼭 남겨야 하는 줄이 생기면 ALLOW 에 '경로' 와 까닭을 적으십시오.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));

// 이름 -> 찾는 글자. 주석도 봅니다(지운 길을 가리키는 설명이 남지 않게).
const WORDS = [
  ['env.DB', /\benv\.DB\b/],
  ['DB 바인딩 자리', /(?:\[\s*['"]DB['"]\s*\]|[{,]\s*DB\s*:)/],
  ['DB_BACKEND', /DB_BACKEND/],
  ['isMysql', /\bisMysql\b/],
  ['shard', /shard/i],
  ['샤드 바인딩', /\bDB_\d{4}_\d{4}\b/],
  ['sqlite_master', /sqlite_master/i],
  ['PRAGMA', /\bPRAGMA\b/],
];

// 'src/…' 경로 -> 남겨야 하는 까닭. 지금은 없습니다.
const ALLOW = {};

function jsFiles(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...jsFiles(p));
    else if (name.endsWith('.js')) out.push(p);
  }
  return out;
}

function hitsIn(rel, text) {
  const out = [];
  text.split(/\r?\n/).forEach((line, i) => {
    for (const [name, re] of WORDS) {
      if (re.test(line)) out.push(`${rel}:${i + 1} ${name}`);
    }
  });
  return out;
}

test('wrangler.toml 에 D1 바인딩과 DB_BACKEND 가 없습니다', () => {
  const toml = readFileSync(join(ROOT, 'wrangler.toml'), 'utf8');
  // 주석이 아닌 줄만 봅니다.
  const lines = toml.split(/\r?\n/).filter((l) => !/^\s*#/.test(l));
  const body = lines.join('\n');
  assert.doesNotMatch(body, /d1_databases/i);
  assert.doesNotMatch(body, /DB_BACKEND/);
  assert.doesNotMatch(body, /binding\s*=\s*"DB/);
  assert.doesNotMatch(body, /database_id/);
  // MySQL 을 읽는 Hyperdrive 는 남아 있어야 합니다.
  assert.match(body, /\[\[hyperdrive\]\]\s*\nbinding = "HYPERDRIVE"/);
});

test('src/ 에 D1 시절 이름(env.DB·DB_BACKEND·isMysql·샤드)이 없습니다', () => {
  const files = jsFiles(join(ROOT, 'src'));
  assert.ok(files.length > 30, '검사가 헛돌지 않습니다');
  const bad = [];
  for (const f of files) {
    const rel = relative(ROOT, f).split(sep).join('/');
    if (rel in ALLOW) continue;
    bad.push(...hitsIn(rel, readFileSync(f, 'utf8')));
  }
  assert.deepEqual(bad, [], `D1 흔적이 남아 있습니다(꼭 남겨야 하면 ALLOW 에 까닭을 적으십시오):\n${bad.join('\n')}`);
});

test('검사기가 실제로 잡습니다', () => {
  const text = [
    "const db = env.DB;",
    "if (env.DB_BACKEND === 'mysql') {}",
    "import { isMysql } from './backendflag.js';",
    "import { shardOf } from './shard.js';",
    "const x = env.DB_2024_2026;",
    "await db.prepare('PRAGMA table_info(t)').all();",
    "return { env: { ...env, DB: db } };",
    "const ok = env.MYSQL; // MySQL 어댑터",
  ].join('\n');
  assert.deepEqual(hitsIn('x.js', text), [
    'x.js:1 env.DB',
    'x.js:2 DB_BACKEND',
    'x.js:3 isMysql',
    'x.js:4 shard',
    'x.js:5 샤드 바인딩',
    'x.js:6 PRAGMA',
    'x.js:7 DB 바인딩 자리',
  ]);
});

test('허용 목록의 파일은 실제로 있습니다', () => {
  for (const p of Object.keys(ALLOW)) {
    assert.ok(statSync(join(ROOT, p)).isFile(), p);
  }
});
