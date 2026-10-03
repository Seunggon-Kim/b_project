# 3단계 API 를 MySQL 로 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cloudflare Worker API(`src/`)가 D1 대신 Cloud SQL MySQL 을 Hyperdrive 로 읽게 하고, 응답이 D1 때와 같은지 대조한 뒤 운영을 전환합니다.

**Architecture:** 라우트는 지금처럼 `env.DB.prepare(sql).bind(...).all()/.first()` 를 부릅니다. Worker 입구(`src/index.js`)에서 `DB_BACKEND` 가 `mysql` 이면 `env.DB` 와 샤드 바인딩 6개를 같은 MySQL 어댑터(D1 과 같은 모양)로 바꿔 끼웁니다. SQL 은 **D1 과 MySQL 양쪽에서 같은 뜻**이 되게 고쳐(같은 코드를 두 백엔드로 돌려 비교할 수 있게), 스테이징 Worker 두 개(D1·MySQL)와 운영을 같은 URL 목록으로 대조합니다. 차이가 정리되면 운영의 `DB_BACKEND` 를 `mysql` 로 바꿔 배포하고, 되돌리기는 그 값을 `d1` 로 되돌리는 것입니다.

**Tech Stack:** Cloudflare Workers(ES modules, `node --test`), Hyperdrive(MySQL, 무료 하루 10만 질의), mysql2 ≥ 3.13.0(`disableEval: true`), Cloud SQL MySQL 8.4, wrangler 4

## Global Constraints

- 저장소 `Seunggon-Kim/b_project` 는 **공개**입니다. 서버 IP·비밀번호·키·`~/.bstats/` 내용을 코드·문서·커밋·로그에 넣지 않습니다. Hyperdrive 설정 ID 는 비밀이 아니므로 `wrangler.toml` 에 둡니다.
- 회사 계정(evan@delivered.co.kr)·회사 GCP 를 쓰지 않습니다. gcloud 는 늘 `--configuration=bstats --project=bstats-kbo`. Git Bash: `export CLOUDSDK_PYTHON="/c/Users/김승곤/AppData/Local/Google/Cloud SDK/google-cloud-sdk/platform/bundledpython/python.exe" PYTHONUTF8=1`.
- push·병합·배포(운영 Worker, 스테이징 Worker, Pages)는 건마다 evan 허락. GCP·Cloudflare 설정 변경(Task 1)도 evan 승인 뒤.
- **운영 동작은 Task 8 전까지 바뀌지 않습니다.** `wrangler.toml` 의 `DB_BACKEND` 기본값은 `d1` 입니다. Task 4 의 SQL 수정은 D1 에서도 같은 결과여야 합니다(Task 7 의 운영 ↔ 스테이징-D1 대조가 0 이어야 함).
- 화면 세션이 `dashboard_js/` 를 고치고 있습니다. 이 계획은 `src/`, `test/`, `scripts/`, `wrangler.toml`, `package.json`, 문서만 고칩니다.
- D1 읽기는 하루 500만 행 무료 한도를 공유합니다. 대조 전에 `PYTHONUTF8=1 py -m migration.mysql.d1_usage` 로 확인합니다. D1 `export` 는 그동안 사이트 질의를 막으므로 이 계획에서 쓰지 않습니다.
- JS 테스트: `npm test`(현재 324개 통과). Python 테스트: `PYTHONUTF8=1 py -m pytest tests -p no:cacheprovider -q`(알려진 실패 `tests/test_cron_table_parity.py` 1개). 새 실패 0.
- 커밋 메시지 끝: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- 사용자에게 보이는 한국어는 `습니다/합니다` 체, 이모지 금지.
- 작업 위치: `git -C C:/Users/김승곤/Desktop/b_project worktree add C:/tmp/b_project_3 -b feat/mysql-phase3-api origin/main`(Desktop/b_project 의 main 은 화면 세션이 씁니다).

## 정한 것(evan, 2026-10-03)

- 접속: Cloud SQL 공인 IP + 허용 네트워크에 **Cloudflare 공개 IPv4 대역만**(https://www.cloudflare.com/ips-v4). Hyperdrive 는 이 대역에서 접속합니다(Hyperdrive 문서 "Firewall and networking configuration").
- TLS: Hyperdrive 기본 `REQUIRED` 는 공개 인증서(WebPKI)만 믿어 Cloud SQL(구글 자체 CA)에 실패합니다. Cloud SQL 서버 CA 를 Cloudflare 에 올리고 `--sslmode VERIFY_CA` 로 붙습니다(`VERIFY_IDENTITY` 는 인증서 이름이 IP 가 아니라 실패).
- 계정: 읽기 전용 `bstats_api`(SELECT 만), `REQUIRE SSL`, 32자 비밀번호.

## 응답에서 달라져도 되는 것(데이터를 고친 결과)

1단계에서 고친 데이터 때문에 D1 과 MySQL 응답이 다를 수 있습니다. Task 7 대조에서 아래 원인으로 설명되는 차이는 받아들입니다. 그 밖의 차이는 코드로 맞춥니다.

| 원인 | 어디에 보이나 |
|---|---|
| 2008~2015 포스트시즌 26,450행의 `game_date` 를 고침(D1 은 'TOB00929' 같은 글자) | 시즌 날짜 범위로 PBP 를 고르는 응답(구종, 사용률, 구장 분포 등)에 그 시즌 포스트시즌 경기가 들어옵니다. 2016년 이후는 D1 도 이미 들어 있으므로 같은 규칙이 됩니다 |
| `'72133.0'` 같은 ID 를 정수로 통일 | 그 선수의 PBP 집계 행 수가 늘어날 수 있습니다(2008~2011, 2017, 2019, 2020, 2022) |
| 숫자 열의 `''`·`'-'` 를 NULL 로 | `speed`·`pitch_number` 평균 등 |
| MySQL `pbp_id` 를 새로 매김 | `pbp_id` 를 그대로 내보내는 응답(데이터 탐색기 play_by_play) |
| 표 정의 이름(MySQL `int`·`varchar` 등) | 데이터 탐색기의 열 타입 표시(Task 3 에서 SQLite 식 이름으로 바꿔 보여 줍니다) |

---

### Task 1: 측정·접속 준비(운영, evan 승인 뒤, 컨트롤러가 직접)

**Files:** 없음(설정만). 결과는 Task 8 의 문서에 남깁니다.

- [ ] **Step 1: 하루 질의 수 측정(Hyperdrive 무료 한도 10만/일 확인)**

D1 GraphQL 의 `readQueries` 합으로 최근 7일 하루 질의 수를 봅니다.

```bash
cd C:/tmp/b_project_3
PYTHONUTF8=1 py - <<'EOF'
import datetime, json
from migration.mysql import d1_usage as u
tok, accounts = u.fetch_accounts()
q = """query($acc:String!,$a:Date!,$b:Date!){viewer{accounts(filter:{accountTag:$acc}){
  d1AnalyticsAdaptiveGroups(limit:1000, filter:{date_geq:$a, date_leq:$b}){
    sum{ readQueries writeQueries } dimensions{ date } } }}}"""
b = datetime.date.today(); a = b - datetime.timedelta(days=7)
for acc in accounts:
    r = u._call(tok, u.API + "/graphql",
                {"query": q, "variables": {"acc": acc["id"], "a": str(a), "b": str(b)}})
    days = {}
    for g in r["data"]["viewer"]["accounts"][0]["d1AnalyticsAdaptiveGroups"]:
        d = g["dimensions"]["date"]; days[d] = days.get(d, 0) + g["sum"]["readQueries"]
    for d in sorted(days): print(d, days[d])
EOF
```

(`fetch_accounts()` 는 `(토큰, 계정 목록)`, `_call` 은 JSON 을 돌려줍니다. `migration/mysql/d1_usage.py` 의 `main()` 과 같은 방식입니다.) 이 수에는 수집 작업의 D1 질의도 들어 있어 API 질의 수의 위쪽 끝입니다. MySQL 로 바꾸면 샤드를 나눠 묻던 질의가 하나로 줄어 더 적어집니다. 기준: 하루 최대가 5만 미만이면 그대로 진행합니다. 5만 이상이면 멈추고 evan 에게 알립니다(유료 전환 또는 캐시 보강 판단).

- [ ] **Step 2: 읽기 전용 계정 `bstats_api`(root, 프록시 경유)**

프록시를 띄운 뒤(1·2단계와 같은 명령) 실행합니다.

```bash
PYTHONUTF8=1 py - <<'EOF'
import pathlib, secrets, string, pymysql
home = pathlib.Path.home() / ".bstats"
pw = home / "mysql_api_password.txt"
if not pw.exists():
    pw.write_text("".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32)), encoding="ascii")
con = pymysql.connect(host="127.0.0.1", port=3307, user="root",
                      password=(home / "cloudsql_root_password.txt").read_text().strip(),
                      server_public_key=(home / "mysql_server_rsa_pub.pem").read_bytes())
with con.cursor() as cur:
    cur.execute("CREATE USER IF NOT EXISTS 'bstats_api'@'%%' IDENTIFIED BY %s REQUIRE SSL",
                (pw.read_text().strip(),))
    cur.execute("GRANT SELECT ON `bstats`.* TO 'bstats_api'@'%'")
    cur.execute("SHOW GRANTS FOR 'bstats_api'@'%'")
    for r in cur.fetchall():
        print(r[0])
con.commit(); con.close()
EOF
```

Expected: `GRANT USAGE ON *.* … REQUIRE SSL` 계열과 `GRANT SELECT ON \`bstats\`.*` 두 줄. 첫 로그인이 PyMySQL 버그로 `AttributeError` 면 한 번 더 돌립니다.

- [ ] **Step 3: 허용 네트워크에 Cloudflare IPv4 대역**

```bash
export CLOUDSDK_PYTHON="/c/Users/김승곤/AppData/Local/Google/Cloud SDK/google-cloud-sdk/platform/bundledpython/python.exe" PYTHONUTF8=1
G="gcloud --configuration=bstats --project=bstats-kbo"
NETS=$(curl -fsSL https://www.cloudflare.com/ips-v4 | tr '\n' ',' | sed 's/,$//')
echo "$NETS" | tr ',' '\n' | wc -l
$G sql instances patch bstats-mysql --authorized-networks="$NETS" --quiet
$G sql instances describe bstats-mysql --format='value(settings.ipConfiguration.sslMode, settings.ipConfiguration.authorizedNetworks.len())'
```

Expected: 대역 15개 안팎, `ENCRYPTED_ONLY` 그대로. (`--authorized-networks` 는 목록을 통째로 바꿉니다. 지금 목록이 비어 있으므로 잃는 것이 없습니다.)

- [ ] **Step 4: Cloud SQL 서버 CA 를 Cloudflare 에 올리기**

```bash
cd C:/tmp/b_project_3
npx --yes wrangler@4 cert upload certificate-authority --ca-cert ~/.bstats/server-ca.pem --name bstats-cloudsql-ca
```

출력의 인증서 ID 를 `~/.bstats/cf_ca_cert_id.txt` 에 저장합니다.

- [ ] **Step 5: Hyperdrive 설정 만들기**

비밀번호가 화면·기록에 남지 않게 변수로만 넘깁니다.

```bash
HOST=$(cat ~/.bstats/mysql_host.txt); PW=$(cat ~/.bstats/mysql_api_password.txt); CA=$(cat ~/.bstats/cf_ca_cert_id.txt)
npx --yes wrangler@4 hyperdrive create bstats-mysql \
  --connection-string="mysql://bstats_api:${PW}@${HOST}:3306/bstats" \
  --ca-certificate-id "$CA" --sslmode VERIFY_CA 2>&1 | grep -v -i password
unset PW
```

출력의 Hyperdrive ID 를 기록합니다(비밀 아님, Task 2 에서 `wrangler.toml` 에 넣음). 실패하면(TLS·접속) 메시지를 evan 에게 보이고 멈춥니다.

---

### Task 2: MySQL 어댑터와 백엔드 스위치

**Files:**
- Create: `src/lib/backendflag.js`, `src/lib/mysqldb.js`, `src/lib/backend.js`
- Modify: `src/index.js`(fetch), `wrangler.toml`, `package.json`, `package-lock.json`
- Test: `test/mysqldb.test.js`, `test/backend.test.js`

**Interfaces:**
- Produces: `MysqlDb`(D1 모양 `prepare(sql).bind(...).all() → {results}`, `.first() → row|null`, `close()`), `hyperdriveDb(env, deps)`, `TEXT_ID_COLUMNS`(Set), `MYSQL_OPTIONS`
- Produces: `isMysql(env) → boolean`(`src/lib/backendflag.js`, 의존 없음. `shard.js`·`counts.js`·`pbpvirtual.js`·`schema.js` 는 여기서 import 합니다. `backend.js` 는 `shard.js` 를 import 하므로 거꾸로 import 하면 순환이 됩니다), `withBackend(env, make) → { env, done }`(D1 이면 `done` 이 `null`), `closeAfterBody(res, done, ctx) → Response`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`test/mysqldb.test.js`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { MysqlDb, MYSQL_OPTIONS, TEXT_ID_COLUMNS } from '../src/lib/mysqldb.js';

function fakeConn(rows) {
  const calls = [];
  return {
    calls,
    ended: false,
    async query(sql, params) { calls.push([sql, params]); return [rows, []]; },
    async end() { this.ended = true; },
  };
}

test('D1 과 같은 모양으로 results 를 돌려줍니다', async () => {
  const conn = fakeConn([{ season: 2026, n: 3 }]);
  const db = new MysqlDb(async () => conn);
  const { results } = await db.prepare('SELECT season, n FROM t WHERE x = ? LIMIT ?').bind('a', 5).all();
  assert.deepEqual(results, [{ season: 2026, n: 3 }]);
  assert.deepEqual(conn.calls[0], ['SELECT season, n FROM t WHERE x = ? LIMIT ?', ['a', 5]]);
});

test('first 는 첫 행이나 null 입니다', async () => {
  const db1 = new MysqlDb(async () => fakeConn([{ a: 1 }, { a: 2 }]));
  assert.deepEqual(await db1.prepare('SELECT 1').first(), { a: 1 });
  const db0 = new MysqlDb(async () => fakeConn([]));
  assert.equal(await db0.prepare('SELECT 1').first(), null);
});

test('연결은 한 번만 엽니다', async () => {
  let opened = 0;
  const conn = fakeConn([]);
  const db = new MysqlDb(async () => { opened += 1; return conn; });
  await db.prepare('SELECT 1').all();
  await db.prepare('SELECT 2').all();
  assert.equal(opened, 1);
  await db.close();
  assert.equal(conn.ended, true);
});

test('D1 에서 글자였던 ID 열은 글자로 돌려줍니다', async () => {
  const db = new MysqlDb(async () => fakeConn([{ player_id: 72133, season: 2026, batter_ID: null }]));
  const row = await db.prepare('SELECT 1').first();
  assert.equal(row.player_id, '72133');
  assert.equal(row.season, 2026);
  assert.equal(row.batter_ID, null);
  assert.ok(TEXT_ID_COLUMNS.has('pitcher_ID'));
});

test('연결 옵션은 Workers·응답 모양에 맞춥니다', () => {
  assert.equal(MYSQL_OPTIONS.disableEval, true);
  assert.equal(MYSQL_OPTIONS.dateStrings, true);
  assert.equal(MYSQL_OPTIONS.decimalNumbers, true);
});

test('close 는 연결을 연 적이 없으면 아무것도 하지 않습니다', async () => {
  const db = new MysqlDb(async () => { throw new Error('열면 안 됩니다'); });
  await db.close();
});
```

`test/backend.test.js`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { isMysql, withBackend, closeAfterBody } from '../src/lib/backend.js';
import { SHARDS } from '../src/lib/shard.js';

test('기본은 D1 이고 env 를 그대로 씁니다', () => {
  const env = { DB: 'd1', DB_BACKEND: undefined };
  const b = withBackend(env, () => { throw new Error('부르면 안 됩니다'); });
  assert.equal(isMysql(env), false);
  assert.equal(b.env, env);
  assert.equal(b.done, null);
});

test('mysql 이면 DB 와 샤드 바인딩을 같은 어댑터로 바꿉니다', async () => {
  let closed = false;
  const fake = { close: async () => { closed = true; } };
  const env = { DB: 'd1', DB_BACKEND: 'mysql', HYPERDRIVE: {} };
  const b = withBackend(env, () => fake);
  assert.equal(b.env.DB, fake);
  for (const s of SHARDS) assert.equal(b.env[s.binding], fake);
  assert.equal(env.DB, 'd1');
  await b.done();
  assert.equal(closed, true);
});

test('응답 본문을 다 보낸 뒤에 연결을 닫습니다', async () => {
  let closed = false;
  const waits = [];
  const ctx = { waitUntil: (p) => waits.push(p) };
  const res = closeAfterBody(new Response('abc', { status: 200, headers: { 'x-a': '1' } }),
    async () => { closed = true; }, ctx);
  assert.equal(closed, false);
  assert.equal(await res.text(), 'abc');
  await Promise.all(waits);
  assert.equal(closed, true);
  assert.equal(res.headers.get('x-a'), '1');
});
```

- [ ] **Step 2: 실패 확인**

Run: `npm test -- --test-name-pattern="모양|한 번만|글자로|옵션|기본은|어댑터|본문"`(또는 `node --test test/mysqldb.test.js test/backend.test.js`)
Expected: 모듈이 없어 FAIL.

- [ ] **Step 3: mysql2 설치**

```bash
npm install mysql2@^3.13.0
```

`package.json` 에 `"dependencies": { "mysql2": "^3.13.0" }` 이 생기고 `package-lock.json` 이 바뀝니다.

- [ ] **Step 4: `src/lib/mysqldb.js`**

```js
// MySQL(Hyperdrive)을 D1 과 같은 모양으로 감쌉니다.
//
// 라우트는 지금처럼 env.DB.prepare(sql).bind(...).all()/.first() 를
// 부릅니다. 백엔드가 mysql 이면 env.DB 자리에 이것이 들어갑니다
// (lib/backend.js). 질의는 mysql2 의 query() 로 보냅니다. execute() 는
// `LIMIT ?` 에 숫자를 묶으면 MySQL 8 이 거절합니다.
import { createConnection } from 'mysql2/promise';

export const MYSQL_OPTIONS = {
  // Workers 에서는 eval 을 못 써서 mysql2 가 이 옵션을 요구합니다(Hyperdrive 문서).
  disableEval: true,
  // DATE·DATETIME 을 D1 처럼 'YYYY-MM-DD' 글자로 받습니다.
  dateStrings: true,
  // SUM 의 DECIMAL 을 숫자로 받습니다. 글자로 오면 `R += row.runs` 가
  // 덧셈이 아니라 이어붙이기가 됩니다(teamrange).
  decimalNumbers: true,
  supportBigNumbers: true,
  bigNumberStrings: false,
};

// D1 에서 TEXT 였다가 MySQL 에서 정수가 된 ID 열입니다(1단계 스키마).
// 응답 모양을 지키려고 글자로 되돌립니다. kbo_roster(_moves).player_id 와
// wrc 표의 batter_ID 는 D1 에서도 정수였지만 이름이 같아 함께 글자가
// 됩니다. 그 차이는 Task 7 대조에서 라우트별로 판단합니다.
export const TEXT_ID_COLUMNS = new Set([
  'player_id', 'batter_ID', 'pitcher_ID', 'on_1b_id', 'on_2b_id', 'on_3b_id',
  'pos_1_id', 'pos_2_id', 'pos_3_id', 'pos_4_id', 'pos_5_id',
  'pos_6_id', 'pos_7_id', 'pos_8_id', 'pos_9_id',
]);

class Statement {
  constructor(db, sql) {
    this.db = db;
    this.sql = sql;
    this.params = [];
  }

  bind(...params) {
    this.params = params;
    return this;
  }

  async all() {
    const conn = await this.db.connection();
    const [rows] = await conn.query(this.sql, this.params);
    return { results: rows.map((r) => this.db.shape(r)) };
  }

  async first() {
    const { results } = await this.all();
    return results.length ? results[0] : null;
  }
}

export class MysqlDb {
  constructor(open, { textColumns = TEXT_ID_COLUMNS } = {}) {
    this.open = open;
    this.textColumns = textColumns;
    this.conn = null;
  }

  connection() {
    if (!this.conn) this.conn = this.open();
    return this.conn;
  }

  prepare(sql) {
    return new Statement(this, sql);
  }

  shape(row) {
    let out = row;
    for (const k of Object.keys(row)) {
      if (this.textColumns.has(k) && typeof row[k] === 'number') {
        if (out === row) out = { ...row };
        out[k] = String(row[k]);
      }
    }
    return out;
  }

  async close() {
    if (!this.conn) return;
    const c = await this.conn;
    await c.end();
  }
}

export function hyperdriveDb(env, deps = {}) {
  const hd = env.HYPERDRIVE;
  const connect = deps.createConnection || createConnection;
  return new MysqlDb(() => connect({
    host: hd.host,
    user: hd.user,
    password: hd.password,
    database: hd.database,
    port: hd.port,
    ...MYSQL_OPTIONS,
  }));
}
```

- [ ] **Step 5: `src/lib/backendflag.js`, `src/lib/backend.js`**

`src/lib/backendflag.js`:

```js
// 지금 MySQL 을 읽는지 봅니다. 의존이 없어 어디서든 import 해도 순환이
// 생기지 않습니다(backend.js 는 shard.js 를 import 합니다).
export function isMysql(env) {
  return Boolean(env) && env.DB_BACKEND === 'mysql';
}
```

`src/lib/backend.js`:

```js
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
```

- [ ] **Step 6: `src/index.js` 에 끼우기**

import 에 `import { withBackend, closeAfterBody } from './lib/backend.js';` 를 더하고 `fetch` 를 바꿉니다(기존 주석의 "D1 을 그대로 읽습니다" 는 "DB 를 그대로 읽습니다" 로).

```js
export default {
  async fetch(request, env, ctx) {
    const backend = withBackend(env);
    try {
      const res = await router.handle(request, backend.env, ctx);
      // Cache-Control 을 여기서 한 번에 붙입니다. 라우트마다 붙이면
      // 빠뜨리기 쉽고, 빠뜨린 곳은 캐시가 안 걸려 DB 를 그대로 읽습니다.
      // 정책은 lib/cachepolicy.js 에 있습니다.
      const cached = withCache(res, new URL(request.url).pathname);
      // MySQL 이면 본문을 다 보낸 뒤 연결을 닫습니다(lib/backend.js).
      return backend.done ? closeAfterBody(cached, backend.done, ctx) : cached;
    } catch (err) {
      if (backend.done) ctx.waitUntil(backend.done());
      return serverError(err);
    }
  },
};
```

- [ ] **Step 7: `wrangler.toml`**

`compatibility_date`(지금 `"2026-08-17"`)는 그대로 둡니다. 2026-08-04 이후라 `nodejs_compat` 이 이미 기본으로 켜져 있습니다(Hyperdrive 문서). 다른 런타임 동작이 바뀌지 않게 날짜를 올리지 않습니다. 파일 끝에 넣습니다(ID 는 Task 1 Step 5 의 값).

```toml
# MySQL(Cloud SQL)을 Hyperdrive 로 읽습니다(3단계).
# vars.DB_BACKEND 가 'mysql' 일 때만 씁니다. 'd1' 이면 지금처럼 D1 을 읽습니다.
[[hyperdrive]]
binding = "HYPERDRIVE"
id = "<Task 1 Step 5 에서 받은 Hyperdrive ID>"

[vars]
DB_BACKEND = "d1"
```

지금 `wrangler.toml` 에는 `[vars]` 가 없습니다. Task 1 이 아직이면 이 블록을 넣지 말고 Task 1 뒤에 넣습니다(컨트롤러가 ID 를 줍니다).

- [ ] **Step 8: 통과 확인**

Run: `npm test`
Expected: 기존 324개 + 새 9개 모두 통과. `npx --yes wrangler@4 deploy --dry-run --outdir C:/tmp/wr_dry` 로 번들이 만들어지는지 봅니다(배포는 하지 않습니다). `node:` 모듈을 못 찾는다는 오류가 나면 `compatibility_flags = ["nodejs_compat"]` 를 `compatibility_date` 아래에 더하고 다시 봅니다.

- [ ] **Step 9: 커밋**

```bash
git add src/lib/backendflag.js src/lib/mysqldb.js src/lib/backend.js src/index.js wrangler.toml package.json package-lock.json test/mysqldb.test.js test/backend.test.js
git commit -m "feat(api): MySQL(Hyperdrive) 어댑터와 DB_BACKEND 스위치(기본 d1)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: 샤드·행 수·표 정보가 백엔드를 알게

MySQL 은 `play_by_play` 가 한 표입니다. 샤드 바인딩 6개가 모두 같은 어댑터를 가리키므로, 샤드를 돌며 같은 질의를 6번 하면 결과가 6배가 됩니다(teamrange 는 샤드 안에서 날짜로만 거릅니다). 표 목록·열 정보는 D1 의 `sqlite_master`·`PRAGMA` 대신 MySQL `information_schema` 를 읽어야 합니다.

**Files:**
- Modify: `src/lib/shard.js`(`shardOf`, `groupBySeason`), `src/lib/counts.js`(`shardedCountOf`, `countOf` 의 `"${table}"`), `src/lib/pbpvirtual.js`(`isSharded`)
- Create: `src/lib/schema.js`
- Modify: `src/routes/dbexplorer.js`(`listTableNames`, `isSharded` 호출, `PRAGMA` 3곳, `"${...}"` 식별자), `src/routes/stats.js`(`tableExists`), `src/routes/schedule.js`(`playersHasCol`)
- Test: `test/schema.test.js`, `test/shard.test.js`(추가), `test/pbpvirtual.test.js`(추가)

**Interfaces:**
- Consumes: `isMysql(env)` 는 `src/lib/backendflag.js` 에서 import 합니다(`backend.js` 에서 import 하면 순환).
- Produces: `tableNames(env) → string[]`, `tableColumns(env, table, db = env.DB) → [{name, type, pk, notnull, …}]`(D1 은 PRAGMA 행 그대로, MySQL 은 SQLite 식 타입 이름), `tableExists(env, name) → boolean`, `sqliteTypeOf(mysqlDataType) → 'INTEGER'|'REAL'|'TEXT'|'BLOB'`; `isSharded(table, env)`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`test/schema.test.js`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { tableNames, tableColumns, tableExists, sqliteTypeOf } from '../src/lib/schema.js';

function fakeDb(answers) {
  const seen = [];
  return {
    seen,
    prepare(sql) {
      return {
        params: [],
        bind(...p) { this.params = p; return this; },
        async all() { seen.push([sql, this.params]); for (const [k, v] of answers) if (sql.includes(k)) return { results: v }; return { results: [] }; },
        async first() { const { results } = await this.all(); return results[0] || null; },
      };
    },
  };
}

test('MySQL 표 목록은 information_schema 에서, meta_ 표는 뺍니다', async () => {
  const db = fakeDb([['information_schema.tables', [{ name: 'games' }, { name: 'play_by_play' }]]]);
  const names = await tableNames({ DB: db, DB_BACKEND: 'mysql' });
  assert.deepEqual(names, ['games', 'play_by_play']);
  assert.ok(db.seen[0][0].includes("NOT LIKE 'meta"));
});

test('MySQL 열 정보는 D1 PRAGMA 와 같은 모양입니다', async () => {
  const db = fakeDb([['information_schema.columns', [
    { name: 'player_id', dtype: 'int', ckey: 'PRI', nullable: 'NO' },
    { name: 'speed', dtype: 'double', ckey: '', nullable: 'YES' },
    { name: 'as_of', dtype: 'date', ckey: '', nullable: 'NO' },
  ]]]);
  const cols = await tableColumns({ DB: db, DB_BACKEND: 'mysql' }, 'players');
  assert.deepEqual(cols, [
    { name: 'player_id', type: 'INTEGER', pk: 1, notnull: 1 },
    { name: 'speed', type: 'REAL', pk: 0, notnull: 0 },
    { name: 'as_of', type: 'TEXT', pk: 0, notnull: 1 },
  ]);
  assert.deepEqual(db.seen[0][1], ['players']);
});

test('D1 열 정보는 PRAGMA 행을 그대로 돌려줍니다', async () => {
  const row = { cid: 0, name: 'a', type: 'TEXT', notnull: 0, dflt_value: null, pk: 1 };
  const db = fakeDb([['PRAGMA table_info', [row]]]);
  const cols = await tableColumns({ DB: db }, 'games');
  assert.deepEqual(cols, [row]);
  assert.match(db.seen[0][0], /PRAGMA table_info\(`games`\)/);
});

test('샤드 DB 를 따로 줄 수 있습니다', async () => {
  const shardDb = fakeDb([['PRAGMA table_info', [{ name: 'pbp_id' }]]]);
  const cols = await tableColumns({ DB: fakeDb([]) }, 'play_by_play', shardDb);
  assert.deepEqual(cols, [{ name: 'pbp_id' }]);
});

test('표가 있는지 봅니다', async () => {
  const yes = fakeDb([['information_schema.tables', [{ x: 1 }]]]);
  assert.equal(await tableExists({ DB: yes, DB_BACKEND: 'mysql' }, 'wrc_plus_comparison'), true);
  const no = fakeDb([]);
  assert.equal(await tableExists({ DB: no, DB_BACKEND: 'mysql' }, 'nope'), false);
});

test('MySQL 타입 이름을 SQLite 식으로 바꿉니다', () => {
  assert.equal(sqliteTypeOf('int'), 'INTEGER');
  assert.equal(sqliteTypeOf('bigint'), 'INTEGER');
  assert.equal(sqliteTypeOf('double'), 'REAL');
  assert.equal(sqliteTypeOf('varchar'), 'TEXT');
  assert.equal(sqliteTypeOf('datetime'), 'TEXT');
  assert.equal(sqliteTypeOf('mediumblob'), 'BLOB');
});
```

`test/shard.test.js` 끝에 붙입니다.

```js
test('mysql 이면 시즌을 한 묶음으로 같은 DB 에 묻습니다', async () => {
  const { groupBySeason, fanOut, shardOf } = await import('../src/lib/shard.js');
  const db = { name: 'mysql' };
  const env = { DB: db, DB_BACKEND: 'mysql' };
  for (const s of SHARDS) env[s.binding] = db;
  const groups = groupBySeason(env, [2009, 2025, 2014, 1999]);
  assert.deepEqual(groups.map((g) => g.seasons), [[2009, 2014, 2025]]);
  assert.equal(groups[0].db, db);
  let calls = 0;
  const out = await fanOut(env, [2009, 2025], async (d, seasons) => { calls += 1; return [seasons.length]; });
  assert.equal(calls, 1);
  assert.deepEqual(out, [2]);
  assert.equal(shardOf(env, 2025), db);
  assert.equal(shardOf(env, 1999), null);
});
```

(`SHARDS` 는 이 파일이 이미 import 합니다. 아니면 `import { SHARDS } from '../src/lib/shard.js';` 를 맨 위에 더합니다.)

`test/pbpvirtual.test.js` 끝에 붙입니다.

```js
test('mysql 이면 play_by_play 도 나뉜 표가 아닙니다', async () => {
  const { isSharded } = await import('../src/lib/pbpvirtual.js');
  assert.equal(isSharded('play_by_play', {}), true);
  assert.equal(isSharded('play_by_play', { DB_BACKEND: 'mysql' }), false);
});
```

`test/` 에 counts 테스트가 없으면 `test/counts.test.js` 를 만듭니다.

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { shardedCountOf } from '../src/lib/counts.js';
import { SHARDS } from '../src/lib/shard.js';

test('mysql 이면 play_by_play 행 수를 한 번만 셉니다', async () => {
  const db = { prepare: () => ({ bind() { return this; }, async first() { return { n: 3983367 }; } }) };
  const env = { DB: db, DB_BACKEND: 'mysql' };
  for (const s of SHARDS) env[s.binding] = db;
  assert.equal(await shardedCountOf(env, SHARDS, 'play_by_play'), 3983367);
});
```

- [ ] **Step 2: 실패 확인**

Run: `npm test`
Expected: 새 테스트들이 FAIL(모듈 없음·6배·true).

- [ ] **Step 3: `src/lib/schema.js`**

```js
// 표 목록과 열 정보를 백엔드에 맞게 읽습니다.
//
// D1 은 sqlite_master·PRAGMA, MySQL 은 information_schema 입니다. 응답은
// 화면이 이미 쓰는 D1 모양({name, type, pk, notnull}, SQLite 식 타입
// 이름)으로 맞춥니다. CSV 의 실수 열 판단(csv.js isRealType)도 이 type 을
// 봅니다.
import { isMysql } from './backendflag.js';

export function sqliteTypeOf(dataType) {
  const t = String(dataType || '').toLowerCase();
  if (t.includes('int')) return 'INTEGER';
  if (t.includes('double') || t.includes('float') || t.includes('decimal') || t === 'real') return 'REAL';
  if (t.includes('blob') || t.includes('binary')) return 'BLOB';
  return 'TEXT';
}

export async function tableNames(env) {
  if (isMysql(env)) {
    const { results } = await env.DB.prepare(
      'SELECT table_name AS name FROM information_schema.tables '
      + "WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE' "
      + "AND table_name NOT LIKE 'meta\\\\_%' ORDER BY table_name",
    ).all();
    return results.map((r) => r.name);
  }
  const { results } = await env.DB.prepare(
    "SELECT name FROM sqlite_master WHERE type='table' "
    + "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '\\_cf\\_%' ESCAPE '\\' "
    + "AND name NOT LIKE 'meta\\_%' ESCAPE '\\' "
    + 'ORDER BY name',
  ).all();
  return results.map((r) => r.name);
}

export async function tableColumns(env, table, db = env.DB) {
  if (isMysql(env)) {
    // MySQL 8 은 information_schema 의 열 이름을 대문자로 돌려줍니다
    // (COLUMN_NAME 등). 별칭을 모두 붙여 이름을 고정합니다.
    const { results } = await db.prepare(
      'SELECT column_name AS name, data_type AS dtype, column_key AS ckey, '
      + 'is_nullable AS nullable FROM information_schema.columns '
      + 'WHERE table_schema = DATABASE() AND table_name = ? ORDER BY ordinal_position',
    ).bind(table).all();
    return results.map((r) => ({
      name: r.name,
      type: sqliteTypeOf(r.dtype),
      pk: r.ckey === 'PRI' ? 1 : 0,
      notnull: r.nullable === 'NO' ? 1 : 0,
    }));
  }
  // D1 은 PRAGMA 행을 그대로 돌려줍니다(지금 화면·CSV 가 쓰는 모양).
  const { results } = await db.prepare(`PRAGMA table_info(\`${table}\`)`).all();
  return results;
}

export async function tableExists(env, name) {
  try {
    const row = isMysql(env)
      ? await env.DB.prepare(
        'SELECT 1 AS x FROM information_schema.tables '
        + 'WHERE table_schema = DATABASE() AND table_name = ?',
      ).bind(name).first()
      : await env.DB.prepare(
        "SELECT 1 AS x FROM sqlite_master WHERE type IN ('table','view') AND name = ?",
      ).bind(name).first();
    return Boolean(row);
  } catch {
    return false;
  }
}
```

`tableNames` 의 D1 SQL 은 지금 `src/routes/dbexplorer.js` 의 `listTableNames` 글자 그대로입니다(옮기기만 함).

- [ ] **Step 4: 샤드·행 수·나뉜 표를 백엔드에 맞게**

`src/lib/shard.js` 에 `import { isMysql } from './backendflag.js';` 를 더합니다.

`shardOf` 의 첫머리, `groupBySeason` 의 첫머리에 넣습니다.

```js
// shardOf 안, Number 검사 다음
  if (isMysql(env)) return allSeasons().includes(n) ? env.DB : null;
```

```js
// groupBySeason 안, wanted 를 만든 다음
  if (isMysql(env)) {
    // MySQL 은 play_by_play 가 한 표입니다. 샤드마다 나눠 물으면 같은 행을
    // 여러 번 받습니다(같은 어댑터를 가리키므로).
    const known = wanted.filter((y) => allSeasons().includes(y));
    return known.length ? [{ binding: 'DB', db: env.DB, seasons: known }] : [];
  }
```

`src/lib/counts.js`: `import { isMysql } from './backendflag.js';` 를 더하고 `shardedCountOf` 첫 줄에 `if (isMysql(env)) return countOf(env.DB, table);` 를 넣습니다. `countOf` 의 `FROM "${table}"` 를 `` FROM `${table}` `` 로 바꿉니다(SQLite 도 백틱을 받습니다).

`src/lib/pbpvirtual.js`: `import { isMysql } from './backendflag.js';` 를 더하고 `isSharded(table)` 를 `isSharded(table, env)` 로 바꿔 `if (isMysql(env)) return false;` 를 첫 줄에 둡니다. `sliceRows` 의 `FROM "${table}"` 를 백틱으로 바꿉니다. `shardTableInfo` 의 `PRAGMA` 는 `import { tableColumns } from './schema.js';` 후 `return { results: await tableColumns(env, table, parts[0].db) };` 로 바꿉니다(반환 모양 `{ results }` 그대로).

- [ ] **Step 5: 라우트가 새 도우미를 쓰게**

- `src/routes/dbexplorer.js`
  - `listTableNames(db)` 를 지우고 `visibleTableNames(env)` 안에서 `await tableNames(env)` 를 씁니다. 다른 파일이 `listTableNames` 를 import 하면(grep) 그곳도 `tableNames(env)` 로 바꿉니다.
  - `isSharded(name)`·`isSharded(tableName)` 3곳을 `isSharded(name, env)`·`isSharded(tableName, env)` 로.
  - `PRAGMA table_info("${…}")` 를 읽는 3곳(약 78, 124, 224행, `db.prepare(…).all()` 전체)을 `{ results: await tableColumns(env, <표 이름>) }` 로 바꿉니다(뒤의 `info.results` 코드는 그대로).
  - `SELECT * FROM "${tableName}"` 2곳(약 146, 301행)을 백틱으로. 329행의 `filename="${tableName}.csv"` 는 SQL 이 아니므로 그대로 둡니다.
- `src/routes/stats.js`: 지역 함수 `tableExists(db, name)` 를 지우고 `import { tableExists } from '../lib/schema.js';` 후 호출부를 `tableExists(env, 'wrc_plus_comparison')` 로.
- `src/routes/schedule.js` `playersHasCol`: `PRAGMA table_info(players)` 대신 `const cols = await tableColumns(env, 'players'); playersColsCache = new Set(cols.map((c) => c.name));`.

- [ ] **Step 6: 통과 확인**

Run: `npm test`
Expected: 전부 통과(기존 + 새 것). `grep -rn "sqlite_master\|PRAGMA" src/` 의 결과가 `src/lib/schema.js` 안에만 있습니다.

- [ ] **Step 7: 커밋**

```bash
git add src/lib/schema.js src/lib/shard.js src/lib/counts.js src/lib/pbpvirtual.js src/routes/dbexplorer.js src/routes/stats.js src/routes/schedule.js test/
git commit -m "feat(api): 샤드·행 수·표 정보가 백엔드(D1/MySQL)를 알게 함

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: D1·MySQL 양쪽에서 같은 뜻인 SQL 로

같은 코드가 D1 과 MySQL 에서 같은 결과를 내도록 고칩니다. **각 고침은 SQLite 에서도 결과가 바뀌지 않아야 합니다**(Task 7 의 운영 ↔ 스테이징-D1 대조가 증명). 근거: SQLite 는 CAST 의 타입 이름을 친화성으로 읽습니다(`CHAR`→TEXT, `DOUBLE`→REAL, `SIGNED`→NUMERIC), 백틱 식별자와 `1.0e0` 실수 글자를 받습니다.

**Files:**
- Modify: `src/routes/players.js`, `src/routes/stats.js`, `src/routes/futuresplayer.js`, `src/routes/leaders.js`, `src/routes/wrc.js`, `src/routes/roster.js`, `src/routes/teamrecord.js`, `src/lib/kst.js`
- Test: `test/sqlportable.test.js`(새), `test/kbbpct.test.js`(글자 기대값 수정), `test/kst.test.js`(추가)

**Interfaces:**
- Produces: `kstDateDaysAgo(days, nowMs = Date.now()) → 'YYYY-MM-DD'`(`src/lib/kst.js`)

- [ ] **Step 1: 실패하는 테스트 쓰기(소스 검사 + kst)**

`test/sqlportable.test.js`:

```js
// D1 과 MySQL 양쪽에서 같은 뜻인 SQL 만 쓰는지 소스를 검사합니다(3단계).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';

const files = ['src/routes', 'src/lib']
  .flatMap((d) => readdirSync(d).filter((f) => f.endsWith('.js')).map((f) => `${d}/${f}`));
const src = Object.fromEntries(files.map((f) => [f, readFileSync(f, 'utf8')]));

function offenders(re) {
  return files.filter((f) => re.test(src[f]));
}

test('CAST 는 CHAR·SIGNED·DOUBLE 만 씁니다', () => {
  // CAST(ROUND(…) AS INT) 처럼 괄호가 겹쳐도 잡히게 "AS 타입)" 만 봅니다.
  assert.deepEqual(offenders(/\bAS (TEXT|INT|INTEGER|REAL)\)/), []);
});

test('스칼라 MIN(?, …) 을 쓰지 않습니다', () => {
  assert.deepEqual(offenders(/MIN\(\s*\?\s*,/), []);
});

test("date('now' …) 를 쓰지 않습니다", () => {
  assert.deepEqual(offenders(/date\('now'/i), []);
});

test('표 이름을 큰따옴표로 감싸지 않습니다', () => {
  // csv.js 의 셀 따옴표, 내려받기 파일 이름은 SQL 이 아니라 그대로 둡니다.
  assert.deepEqual(offenders(/(FROM|JOIN|table_info\()\s*"\$\{/), []);
});

test('정수 나눗셈 game_date / 10000 은 SIGNED 로 감쌉니다', () => {
  assert.deepEqual(offenders(/CAST\(game_date \/ 10000 AS (TEXT|CHAR)\)/), []);
});

test('sqlite_master·PRAGMA 는 schema.js 에만 있습니다', () => {
  const bad = offenders(/sqlite_master|PRAGMA/).filter((f) => !f.endsWith('lib/schema.js'));
  assert.deepEqual(bad, []);
});
```

`test/kst.test.js` 끝에 붙입니다.

```js
test('며칠 전 한국 날짜를 YYYY-MM-DD 로 줍니다', async () => {
  const { kstDateDaysAgo } = await import('../src/lib/kst.js');
  // 2026-10-03 23:30 KST = 2026-10-03 14:30 UTC
  const now = Date.UTC(2026, 9, 3, 14, 30);
  assert.equal(kstDateDaysAgo(0, now), '2026-10-03');
  assert.equal(kstDateDaysAgo(7, now), '2026-09-26');
  // 2026-10-04 00:30 KST = 2026-10-03 15:30 UTC — 한국은 이미 4일입니다.
  assert.equal(kstDateDaysAgo(0, Date.UTC(2026, 9, 3, 15, 30)), '2026-10-04');
});
```

- [ ] **Step 2: 실패 확인**

Run: `npm test`
Expected: `sqlportable` 의 CAST·MIN·date·큰따옴표·game_date 검사와 kst 가 FAIL(Task 3 을 마쳤으면 PRAGMA 검사는 통과).

- [ ] **Step 3: 고치기(곳마다)**

`src/lib/kst.js` 에 더합니다(기존 `kstDateOf(epochMs)` 를 씁니다).

```js
/** 오늘(한국)에서 days 일 전의 날짜 'YYYY-MM-DD' 입니다. */
export function kstDateDaysAgo(days, nowMs = Date.now()) {
  return kstDateOf(nowMs - days * 86400000);
}
```

`kstDateOf` 가 'YYYY-MM-DD' 를 돌려주지 않으면(파일을 보고) 같은 결과가 나오게 맞춥니다.

| 곳 | 지금 | 바꾼 뒤 |
|---|---|---|
| `players.js` `LATEST_TEAM_SQL`(약 15~18행) | `SELECT player_team FROM ( … UNION ALL … ) ORDER BY season DESC LIMIT 1` | 닫는 괄호 뒤에 `AS lt`: `… ) AS lt ORDER BY season DESC LIMIT 1` |
| `players.js` `LATEST_SEASON_SQL`(약 22~27행) | `SELECT MAX(season) FROM ( … )` | `… ) AS ls` |
| `players.js` `currentSeason`(약 46~49행) | `SELECT MAX(s) AS s FROM (SELECT … UNION ALL SELECT …)` | `… ) AS cs` |
| `stats.js`(약 21~25행) | `SELECT DISTINCT season FROM ( … UNION … )` | `… ) AS ss` |
| `futuresplayer.js`(약 405~410행) | 같은 꼴의 최신 팀 하위 질의 | `… ) AS lt` |
| `leaders.js` 207·212·214, `stats.js` 100, `wrc.js` 88 | `CAST(x AS TEXT)` | `CAST(x AS CHAR)` |
| `wrc.js` 261 | `CAST(game_date / 10000 AS TEXT) AS season` | `CAST(CAST(game_date / 10000 AS SIGNED) AS CHAR) AS season`(MySQL 의 `/` 는 2025.0415 를 줍니다. SIGNED 로 반올림하면 소수부가 0.1231 이하라 늘 그해입니다) |
| `wrc.js` 104 | `MIN(?, CAST(ROUND(3.1 * ROUND(2.0*g/10.0)) AS INT))` | `CASE WHEN ? < CAST(ROUND(3.1e0 * ROUND(2.0e0*g/10.0e0)) AS SIGNED) THEN ? ELSE CAST(ROUND(3.1e0 * ROUND(2.0e0*g/10.0e0)) AS SIGNED) END` 이고 `.bind(...)` 에서 그 값을 두 번 넘깁니다(실수 글자에 `e0` 을 붙여 MySQL 에서도 SQLite 처럼 DOUBLE 로 계산) |
| `roster.js` 111 | `CAST(back_number AS INTEGER)` | `CAST(back_number AS SIGNED)` |
| `stats.js` 148, `teamrecord.js` 44·46 | `CAST(… AS REAL)` | `CAST(… AS DOUBLE)` |
| `teamrecord.js` 49~50 | `1.0/3.0`, `2.0/3.0` | `1.0e0/3.0e0`, `2.0e0/3.0e0`(MySQL 에서 DECIMAL 이 아닌 DOUBLE 로) |
| `stats.js` 15·17, `leaders.js` 256·258 | `* 100.0 /` | `* 100.0e0 /`(MySQL 의 `100.0` 은 DECIMAL 이라 나눗셈이 소수 4자리에서 잘립니다) |
| `roster.js` 49 | `WHERE move_date >= date('now', '+9 hours', ?)` 와 `.bind(\`-${days} days\`, limit)` | `WHERE move_date >= ?` 와 `.bind(kstDateDaysAgo(days), limit)`(`import { kstDateDaysAgo } from '../lib/kst.js';`) |

아래 두 가지는 소스 검사로 잡기 어려워 눈으로 봅니다. 결과를 보고서에 적습니다.

- **GROUP BY 9곳**(`stats.js`, `teamrange.js`, `teamrecord.js`, `wrc.js`): MySQL 8 은 기본으로 `ONLY_FULL_GROUP_BY` 라, SELECT 에 집계도 GROUP BY 도 아닌 열이 있으면 오류입니다(SQLite 는 받아 줍니다). 그런 열이 있으면, 그룹 안에서 값이 하나뿐인 열은 GROUP BY 에 더하고, 아니면 질의를 고쳐 같은 뜻을 냅니다.
- **`LIMIT ?`·`OFFSET ?` 10곳**: 넘기는 값이 숫자인지 봅니다. 글자(`'50'`)를 넘기면 MySQL 이 `LIMIT '50'` 을 문법 오류로 거절합니다. `queryInt` 를 거치지 않은 값이면 `Number(...)` 로 감쌉니다.

`test/kbbpct.test.js` 의 글자 기대값(`ps.strikeout * 100.0 / ps.total_batters_faced` 와 BB 쪽)을 `100.0e0` 으로 고칩니다. 다른 소스 검사 테스트(playerteam, schedulelink, seasonteam, teamseason, sqlbind)가 위 변경으로 깨지면 **기대 글자만** 새 SQL 에 맞게 고칩니다(검사 의도는 그대로).

- [ ] **Step 4: 통과 확인**

Run: `npm test`
Expected: 전부 통과.

- [ ] **Step 5: 커밋**

```bash
git add src/ test/
git commit -m "fix(api): D1·MySQL 양쪽에서 같은 뜻인 SQL 로(별칭·CAST·나눗셈·날짜)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: 오류 응답을 캐시하지 않기(로드맵 0-4)

DB 질의가 실패해도 200 + `error` 필드로 내보내는 라우트가 4곳 있습니다(옛 파이썬 API 와 맞춘 것). 200 이면 엣지가 한 시간(+하루 stale) 동안 그 실패를 보여 줍니다. MySQL 로 바꾸면 접속 순간 실패(Hyperdrive·Cloud SQL 재시작)가 생길 수 있어, 이 4곳은 **본문은 그대로 두고 상태만 503**, `cache-control: no-store` 로 바꿉니다. `withCache` 는 200 이 아니면 손대지 않습니다(`src/lib/cachepolicy.js` 90행).

| 곳 | 지금 |
|---|---|
| `src/routes/dashboard.js` 약 87행 `dashboardStats` 의 catch | `json({ error, traceback })` |
| `src/routes/players.js` 약 284행(구종 구사율) catch | `json({ error, traceback })` |
| `src/routes/players.js` 약 409행(사용률) catch | `json({ error, traceback })` |
| `src/routes/leaders.js` 약 324행 catch | `json({ season, batter, pitcher, error })` |

예외를 삼키고 0·빈 배열로 넘어가는 곳(`dashboard.js` 의 `one()`, `players.js` 156행, `teamrecord.js` 271·293행, `wrc.js` 50행, `stats.js` 169행)은 "표가 없는 환경" 대비라 이번에는 바꾸지 않습니다. 보고서에 "남은 위험: 순간 실패 때 0 이 한 시간 캐시될 수 있음" 으로 적습니다.

**Files:**
- Modify: `src/lib/respond.js`, `src/routes/dashboard.js`, `src/routes/players.js`, `src/routes/leaders.js`
- Test: `test/dberror.test.js`(새)

**Interfaces:**
- Produces: `dbError(err, body = null) → Response`(503, `cache-control: no-store`, 본문은 `body` 또는 `{ detail }`)

- [ ] **Step 1: 실패하는 테스트**

`test/dberror.test.js`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { dbError } from '../src/lib/respond.js';
import { withCache } from '../src/lib/cachepolicy.js';

test('DB 오류는 503 이고 캐시하지 않습니다', async () => {
  const res = withCache(dbError(new Error('D1_ERROR: export')), '/dashboard/stats');
  assert.equal(res.status, 503);
  assert.equal(res.headers.get('cache-control'), 'no-store');
  assert.equal(res.headers.get('access-control-allow-origin'), '*');
  assert.match((await res.json()).detail, /export/);
});

test('본문을 그대로 줄 수 있습니다', async () => {
  const res = dbError(new Error('x'), { error: 'x', traceback: '' });
  assert.equal(res.status, 503);
  assert.deepEqual(await res.json(), { error: 'x', traceback: '' });
});

test('DB 오류를 200 으로 내던 4곳이 dbError 를 씁니다', () => {
  const count = (f) => (readFileSync(f, 'utf8').match(/return dbError\(err, \{/g) || []).length;
  assert.equal(count('src/routes/dashboard.js'), 1);
  assert.equal(count('src/routes/players.js'), 2);
  assert.equal(count('src/routes/leaders.js'), 1);
});
```

- [ ] **Step 2: 실패 확인**

Run: `node --test test/dberror.test.js`
Expected: `dbError` 가 없어 FAIL.

- [ ] **Step 3: 구현**

`src/lib/respond.js` 끝에 더합니다.

```js
/**
 * DB 를 못 읽은 경우입니다. 503 으로 돌려주고 캐시하지 않습니다.
 *
 * 200 으로 내보내면 엣지가 한 시간(+하루 stale) 동안 이 실패를 보여 줍니다.
 * 본문은 라우트가 원래 내던 모양을 그대로 넘길 수 있습니다(화면이 error
 * 필드를 읽는 곳이 있습니다).
 */
export function dbError(err, body = null) {
  const res = json(body || { detail: String(err && err.message ? err.message : err) }, 503);
  res.headers.set('cache-control', 'no-store');
  return res;
}
```

위 표의 4곳에서 `return json({` 를 `return dbError(err, {` 로 바꾸고(본문 객체와 닫는 괄호는 그대로), 각 파일 import 에 `dbError` 를 더합니다(`import { json, dbError } from '../lib/respond.js';`). `leaders.js` 의 주석 "원본은 예외 시 200 과 함께 error 필드를 돌려줍니다. 500 이 아닙니다." 는 "원본은 예외 시 200 과 함께 error 필드를 돌려줬습니다. 실패가 캐시에 굳지 않게 503 으로 바꿨습니다(본문은 같음)." 로 고칩니다. `dashboard.js`·`players.js` 의 catch 주석도 같은 뜻을 한 줄 더합니다.

- [ ] **Step 4: 통과·커밋**

Run: `npm test` — 전부 통과(골든 비교 테스트가 200 을 기대하면 그 기대만 503 으로 고칩니다).

```bash
git add src/lib/respond.js src/routes/dashboard.js src/routes/players.js src/routes/leaders.js test/dberror.test.js
git commit -m "fix(api): DB 오류는 503·no-store 로(한 번의 실패가 캐시에 굳지 않게)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

화면이 503 을 받았을 때 "불러오지 못했습니다" 를 보이는지는 화면 세션에 따로 확인을 요청합니다(컨트롤러가 메시지로 전달).

---

### Task 6: 응답 대조 도구

**Files:**
- Create: `scripts/api_compare.mjs`, `scripts/api_compare_urls.txt`
- Test: `test/api_compare.test.js`

**Interfaces:**
- Produces: CLI `node scripts/api_compare.mjs --a <base> --b <base> [--urls scripts/api_compare_urls.txt] [--out docs/mysql-migration/api-compare-<이름>.md]`(다르면 종료 코드 1); 함수 `diffJson(a, b, path = '$') → string[]`(차이 경로 목록, 실수는 상대 1e-9 허용, 객체 키 순서 무시)

- [ ] **Step 1: 실패하는 테스트**

`test/api_compare.test.js`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { diffJson } from '../scripts/api_compare.mjs';

test('같으면 빈 목록, 키 순서는 무시합니다', () => {
  assert.deepEqual(diffJson({ a: 1, b: [1, 2] }, { b: [1, 2], a: 1 }), []);
});

test('실수는 아주 작은 차이를 허용합니다', () => {
  assert.deepEqual(diffJson({ x: 0.30000000000000004 }, { x: 0.3 }), []);
  assert.equal(diffJson({ x: 0.31 }, { x: 0.3 }).length, 1);
});

test('타입이 다르면 차이입니다(글자 ID vs 숫자)', () => {
  assert.deepEqual(diffJson({ id: '72133' }, { id: 72133 }), ['$.id: "72133" ≠ 72133']);
});

test('배열 길이와 빠진 키를 알려 줍니다', () => {
  const d = diffJson({ a: [1, 2], b: 1 }, { a: [1], c: 2 });
  assert.ok(d.some((x) => x.startsWith('$.a: 길이')));
  assert.ok(d.some((x) => x.startsWith('$.b: B 에 없음')));
  assert.ok(d.some((x) => x.startsWith('$.c: A 에 없음')));
});
```

- [ ] **Step 2: `scripts/api_compare.mjs`**

```js
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

if (import.meta.url === pathToFileURL(process.argv[1]).href) main();
```

- [ ] **Step 3: `scripts/api_compare_urls.txt`**

`src/index.js` 의 GET 라우트마다 하나 이상, 시즌은 2008·2012·2015·2019·2025·2026 을 고루, 선수는 타자·투수·옛 선수를 섞습니다. 외부 사이트를 읽는 라우트(`/standings`, `/schedule`, `/schedule/futures`, `/futures/*`)는 DB 와 무관하고 시각마다 바뀌므로 넣지 않습니다. 선수 ID 는 `players` 에서 고릅니다(아래 명령, 공개 데이터).

```bash
BSTATS_MYSQL_SETTINGS=~/.bstats/mysql_proxy.json PYTHONUTF8=1 py -c "
from migration.mysql import conn
c=conn.connect(); cur=c.cursor()
cur.execute(\"SELECT player_id FROM kbo_official_batter_stats WHERE season IN (2012,2019,2025) ORDER BY plate_appearances DESC LIMIT 6\"); print([r[0] for r in cur.fetchall()])
cur.execute(\"SELECT player_id FROM kbo_official_pitcher_stats WHERE season IN (2012,2019,2025) ORDER BY innings_pitched DESC LIMIT 6\"); print([r[0] for r in cur.fetchall()])
c.close()"
```

(열 이름이 다르면 `migration/mysql/schema.sql` 을 보고 맞춥니다.) 목록은 80~120줄로 둡니다. 형식은 한 줄에 경로 하나(`/players/72133/arsenal?season=2019` 꼴), `#` 줄은 주석입니다.

- [ ] **Step 4: 통과·커밋**

Run: `npm test` — 통과.

```bash
git add scripts/api_compare.mjs scripts/api_compare_urls.txt test/api_compare.test.js
git commit -m "feat(api): D1·MySQL 응답 대조 도구와 URL 목록

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: 스테이징 두 개로 대조하고 차이 고치기(운영, evan 허락 뒤 배포)

운영 Worker(`kbo-api`)는 건드리지 않습니다. 같은 코드를 이름만 달리해 두 개 올립니다.

- [ ] **Step 1: 스테이징 배포(evan 허락)**

```bash
cd C:/tmp/b_project_3
npx --yes wrangler@4 deploy --name kbo-api-stg-d1
npx --yes wrangler@4 deploy --name kbo-api-stg-my --var DB_BACKEND:mysql
```

스테이징은 `workers.dev` 주소만 씁니다(사이트와 무관). 캐시도 따로입니다. MySQL 의 `meta_table_counts` 에 `play_by_play` 행이 있는지 봅니다(없으면 데이터 탐색기가 400만 행 `COUNT(*)` 를 합니다. 2단계 `Sink.refresh_count` 가 채우는지 확인하고, 없으면 evan 승인 뒤 한 번 넣습니다).

- [ ] **Step 2: 대조 ① 운영(옛 코드, D1) ↔ 스테이징-D1(새 코드, D1)**

D1 사용량을 먼저 봅니다. 그다음:

```bash
node scripts/api_compare.mjs --a https://kbo-api.bstats-baseball.workers.dev \
  --b https://kbo-api-stg-d1.bstats-baseball.workers.dev --out docs/mysql-migration/api-compare-d1.md
```

Expected: **다른 URL 0개**. 차이가 있으면 Task 2~5 의 변경이 D1 결과를 바꾼 것입니다. 고친 뒤(코드 수정은 서브에이전트, 테스트·커밋) 스테이징-D1 을 다시 올리고 다시 대조합니다.

- [ ] **Step 3: 대조 ② 스테이징-D1 ↔ 스테이징-MySQL**

```bash
node scripts/api_compare.mjs --a https://kbo-api-stg-d1.bstats-baseball.workers.dev \
  --b https://kbo-api-stg-my.bstats-baseball.workers.dev --out docs/mysql-migration/api-compare-mysql.md
```

차이를 하나씩 분류합니다.
- (가) 위 "달라져도 되는 것" 표로 설명됨 → 보고서에 근거를 적고 받아들입니다.
- (나) ID 타입(글자 ↔ 숫자): D1 이 숫자였던 곳(`kbo_roster*.player_id`, wrc 표 `batter_ID`)이 글자가 됐으면 그 라우트에서 `Number(...)` 로 되돌리거나 SQL 에서 `CAST(… AS SIGNED)` 로 맞춥니다.
- (다) 정렬 순서(ai_ci 정렬 규칙 ↔ SQLite 바이트 순): 같은 값 묶음 안의 순서 차이면 ORDER BY 에 열쇠를 더해 둘 다 같게 만듭니다.
- (라) 그 밖: 원인을 찾아 SQL·어댑터를 고칩니다. 짐작되는 원인: `ROUND(실수, n)` 의 반올림 규칙(MySQL 은 C 라이브러리를 따라 .5 에서 짝수 쪽일 수 있음, 이 경우 반올림을 JS 로 옮김), 글자 비교 규칙(대소문자·공백), `ONLY_FULL_GROUP_BY` 오류(상태 500), MySQL 8 예약어 열(`team_season_rank.rank`, `self_park_factor.window` — `r.rank` 처럼 표 이름을 앞에 붙이면 괜찮고, 붙이지 않았으면 백틱).

고칠 때마다 Task 7 Step 2(① D1 쪽 0 유지)와 Step 3 를 다시 돌립니다. 끝 기준: ①은 0, ②는 (가)로만 남음.

- [ ] **Step 4: 기록**

`docs/mysql-migration/api-compare-d1.md`, `api-compare-mysql.md` 와 차이 분류표를 커밋합니다.

---

### Task 8: 운영 전환(evan 허락 뒤)

- [ ] **Step 1: 전환 전 확인**

- 2단계 매일 대조(daily 요약의 D1·MySQL 대조)가 그날도 초록입니다.
- Task 7 끝 기준을 만족합니다.
- 화면 세션이 503 표시를 반영했는지(Task 5 끝 메모) 확인합니다. 아직이면 evan 이 그대로 갈지 정합니다.

- [ ] **Step 2: 전환 배포(evan 허락)**

`wrangler.toml` 의 `DB_BACKEND = "mysql"` 로 바꾸는 커밋을 main 에 넣고(evan 허락) 운영에 배포합니다.

```bash
npx --yes wrangler@4 deploy
curl -s -X POST "https://kbo-api.bstats-baseball.workers.dev/admin/purge-cache" -H "Authorization: Bearer $ADMIN_TOKEN"
```

`ADMIN_TOKEN` 은 evan 이 넣거나, daily 의 캐시 비우기를 손으로 돌립니다(roster 워크플로 Run).

- [ ] **Step 3: 지켜보기(배포 뒤 한 시간, 다음 날 아침)**

- 사이트 주요 화면을 evan 이 열어 봅니다(홈, 선수, 팀, 기록, 데이터 탐색기, wRC+).
- `npx --yes wrangler@4 tail kbo-api --format pretty` 로 오류를 봅니다(503·예외).
- 대조 ② 를 운영 ↔ 스테이징-D1 로 한 번 더 돌립니다.

- [ ] **Step 4: 되돌리기(문제가 있으면 즉시)**

`DB_BACKEND = "d1"` 로 되돌린 커밋을 배포하고 캐시를 비웁니다. D1 은 2단계 이중 적재로 계속 최신이라 그대로 읽힙니다.

- [ ] **Step 5: 기록·다음 단계**

로드맵에 `### 3단계 결과`(전환 날짜, 대조 결과, 받아들인 차이)를 적습니다. 다음은 5단계(D1 쓰기 중지·샤드 코드·바인딩 제거·D1 2주 보관 뒤 삭제)와 화면 세션의 새 API(B 명세)입니다. 스테이징 Worker 두 개는 5단계 끝에 지웁니다(`npx wrangler delete --name kbo-api-stg-d1` 등).
