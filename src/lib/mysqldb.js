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
// 응답 모양을 지키려고 글자로 되돌립니다.
//
// 이름만 보고 바꾸면 D1 에서도 INTEGER 였던 같은 이름 열(kbo_roster(_moves)
// .player_id, wrc_plus_comparison·weighted_pf_by_batter_season 의 batter_ID)
// 까지 글자가 됩니다. 그래서 mysql2 의 열 정보(orgTable·orgName)로 원래
// 표가 아래 TEXT_ID_TABLES 인 열만 바꿉니다. 원래 표가 없는 계산한 열만
// 이 이름 목록으로 판단합니다.
export const TEXT_ID_COLUMNS = new Set([
  'player_id', 'batter_ID', 'pitcher_ID', 'on_1b_id', 'on_2b_id', 'on_3b_id',
  'pos_1_id', 'pos_2_id', 'pos_3_id', 'pos_4_id', 'pos_5_id',
  'pos_6_id', 'pos_7_id', 'pos_8_id', 'pos_9_id',
]);

// 위 ID 열이 D1 에서 TEXT 였던 표입니다.
export const TEXT_ID_TABLES = new Set([
  'players', 'kbo_official_batter_stats', 'kbo_official_pitcher_stats',
  'futures_season_stats', 'play_by_play',
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
    let rows;
    let fields;
    try {
      [rows, fields] = await conn.query(this.sql, this.params);
    } catch (err) {
      // 연결이 끊긴 오류(mysql2 가 fatal 로 표시)만 남깁니다. 표가 없는
      // 것(ER_NO_SUCH_TABLE) 같은 보통 오류는 라우트가 물러설 길로 씁니다.
      if (err && err.fatal === true) this.db.fail(err);
      throw err;
    }
    // 글자로 바꿀 키는 질의마다 한 번 정합니다(행마다 열 정보를 보지 않음).
    const keys = this.db.textKeysOf(fields);
    return { results: rows.map((r) => this.db.shape(r, keys)) };
  }

  async first() {
    const { results } = await this.all();
    return results.length ? results[0] : null;
  }
}

export class MysqlDb {
  constructor(open, { textColumns = TEXT_ID_COLUMNS, textTables = TEXT_ID_TABLES } = {}) {
    this.open = open;
    this.textColumns = textColumns;
    this.textTables = textTables;
    this.conn = null;
    // 연결 수준의 첫 실패입니다(없으면 null). 라우트 몇 곳은 질의 오류를
    // 삼키고 0·빈칸으로 물러섭니다. 표가 없을 때를 위한 것인데, MySQL 이
    // 아예 안 닿을 때도 그렇게 되면 200 + 0 이 한 시간 캐시됩니다.
    // index.js 가 이 값을 보고 응답을 503 으로 바꿉니다(backend.js
    // finalizeResponse).
    this.failed = null;
  }

  /** 연결 수준의 실패를 남깁니다. 처음 것만 둡니다. */
  fail(err) {
    if (!this.failed) this.failed = err || new Error('MySQL 연결 실패');
  }

  connection() {
    if (!this.conn) {
      // open 이 바로 던져도(설정 누락 등) 거절된 약속으로 바꿔 같은 길로
      // 처리합니다.
      this.conn = Promise.resolve()
        .then(() => this.open())
        .then((conn) => {
          // 질의가 없는 사이에 연결이 끊기면 mysql2 가 'error' 이벤트를
          // 냅니다. 듣는 쪽이 없으면 EventEmitter 가 그 오류를 던져 Worker 가
          // 죽습니다. 던지지 않고 연결 실패로 남깁니다.
          if (conn && typeof conn.on === 'function') {
            conn.on('error', (err) => this.fail(err));
          }
          return conn;
        }, (err) => {
          this.fail(err);
          throw err;
        });
    }
    return this.conn;
  }

  prepare(sql) {
    return new Statement(this, sql);
  }

  /**
   * 결과 열 정보(mysql2 의 fields)로 글자로 바꿀 행 키를 정합니다.
   *
   * 원래 표(orgTable)가 TEXT_ID_TABLES 이고 원래 열(orgName)이
   * TEXT_ID_COLUMNS 인 열의 키(name, 별칭)입니다. orgTable 이 빈 계산한
   * 열(COALESCE·집계, 물리화한 파생 표)은 열 이름 규칙으로 물러섭니다.
   * 이름이 겹치면 mysql2 가 행에 마지막 열 값을 남기므로 마지막 열을
   * 따릅니다. 열 정보가 아예 없으면 null(행 키 이름 규칙)입니다.
   *
   * Hyperdrive 를 거쳐도 mysql2 가 orgTable·orgName 을 채우는지는
   * 스테이징에서 확인해야 합니다(Task 7). 비어 오면 모두 이름 규칙이 되어
   * 예전 동작과 같아집니다.
   */
  textKeysOf(fields) {
    if (!Array.isArray(fields) || !fields.length) return null;
    const keys = new Set();
    for (const f of fields) {
      if (!f || typeof f.name !== 'string') continue;
      const orgTable = f.orgTable || '';
      const text = orgTable
        ? this.textTables.has(orgTable) && this.textColumns.has(f.orgName)
        : this.textColumns.has(f.name);
      if (text) keys.add(f.name);
      else keys.delete(f.name);
    }
    return keys;
  }

  shape(row, keys = null) {
    const text = keys || this.textColumns;
    let out = row;
    for (const k of Object.keys(row)) {
      const v = row[k];
      if (typeof v === 'number') {
        if (text.has(k)) {
          if (out === row) out = { ...row };
          out[k] = String(v);
        }
      } else if (v instanceof Uint8Array) {
        // BLOB 입니다. mysql2 는 Buffer 로 주고 D1 은 숫자 배열로 줍니다.
        // Buffer 를 그대로 두면 JSON 이 {type,data} 가 되고 CSV 칸이 깨진
        // 글자가 됩니다(/db/table/team_logos). D1 처럼 숫자 배열로 바꿉니다.
        if (out === row) out = { ...row };
        out[k] = Array.from(v);
      }
    }
    return out;
  }

  /**
   * 연결을 닫습니다. 던지지 않습니다.
   *
   * 응답을 보낸 뒤 waitUntil 에서 불립니다. 연결을 못 열었거나 이미
   * 끊겼으면 닫을 것이 없으니 조용히 넘어갑니다.
   */
  async close() {
    if (!this.conn) return;
    try {
      const c = await this.conn;
      await c.end();
    } catch {
      // 열기 실패는 이미 failed 에 남았습니다. 끊긴 연결의 end() 실패는
      // 할 일이 없습니다.
    }
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
