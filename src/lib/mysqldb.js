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
    let rows;
    try {
      [rows] = await conn.query(this.sql, this.params);
    } catch (err) {
      // 연결이 끊긴 오류(mysql2 가 fatal 로 표시)만 남깁니다. 표가 없는
      // 것(ER_NO_SUCH_TABLE) 같은 보통 오류는 라우트가 물러설 길로 씁니다.
      if (err && err.fatal === true) this.db.fail(err);
      throw err;
    }
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
        .catch((err) => {
          this.fail(err);
          throw err;
        });
    }
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
