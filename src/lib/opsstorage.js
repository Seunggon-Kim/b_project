// src/lib/opsstorage.js
// 공개 '데이터 관리' 화면의 저장소 현황(GET /ops/storage)입니다.
//
// 세 가지를 읽습니다. 표 크기(information_schema, MySQL 추정치라 하루 단위로
// 갱신), 행 수(meta_table_counts, 적재 때 맞춘 값), 빅쿼리 사본 현황(meta_bq_tables,
// 주간 복사가 record_bq_snapshot.py 로 남김). Worker 에는 GCP 자격이 없어
// 빅쿼리를 직접 읽지 않습니다. 오류 원문(meta_bq_tables.error)은 프로젝트 이름이나
// 경로가 섞일 수 있어 내보내지 않습니다.
// 설계: docs/superpowers/specs/2026-10-18-data-ops-tab-design.md §4-3

export const SIZE_SQL =
  'SELECT table_name AS name, data_length AS data_bytes, index_length AS index_bytes '
  + 'FROM information_schema.tables WHERE table_schema = DATABASE() '
  + "AND table_type = 'BASE TABLE' AND table_name NOT LIKE 'meta\\_%'";  // lib/schema.js 와 같은 글자

// updated_at 은 UTC 로 적혀 있습니다(mysql_sink.refresh_count).
export const COUNT_SQL =
  "SELECT name, n, DATE_FORMAT(DATE_ADD(updated_at, INTERVAL 9 HOUR), '%Y-%m-%d %H:%i') AS updated_kst "
  + 'FROM meta_table_counts';

// 시각은 KST 로 적혀 있습니다(record_bq_snapshot.py).
export const BQ_SQL =
  'SELECT name, bq_rows, bq_bytes, '
  + "DATE_FORMAT(last_ok_at, '%Y-%m-%d %H:%i') AS last_ok_at, "
  + "DATE_FORMAT(last_try_at, '%Y-%m-%d %H:%i') AS last_try_at, status "
  + 'FROM meta_bq_tables';

function num(v) {
  if (v === null || v === undefined || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function kstText(d) {
  const k = new Date(d.getTime() + 9 * 3600 * 1000);
  const p = (x) => String(x).padStart(2, '0');
  return `${k.getUTCFullYear()}-${p(k.getUTCMonth() + 1)}-${p(k.getUTCDate())} `
    + `${p(k.getUTCHours())}:${p(k.getUTCMinutes())}`;
}

export function storageBody({ sizes, counts, bq, tables, now }) {
  const cnt = new Map((counts || []).map(r => [r.name, r]));
  const my = (sizes || []).map((r) => {
    const c = cnt.get(r.name);
    return {
      name: r.name,
      category: ((tables || {})[r.name] || {}).category || '',
      rows: c ? num(c.n) : null,
      rows_updated_at: c ? (c.updated_kst || null) : null,
      data_bytes: num(r.data_bytes) || 0,
      index_bytes: num(r.index_bytes) || 0,
    };
  });
  my.sort((a, b) => (b.data_bytes + b.index_bytes) - (a.data_bytes + a.index_bytes)
    || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));

  let bigquery = null;
  if (bq) {
    const list = bq.map(r => ({
      name: r.name, rows: num(r.bq_rows), bytes: num(r.bq_bytes),
      last_ok_at: r.last_ok_at || null, last_try_at: r.last_try_at || null, status: r.status,
    }));
    const tries = list.map(t => t.last_try_at).filter(Boolean).sort();
    bigquery = {
      last_copy_at: tries.length ? tries[tries.length - 1] : null,
      ok: list.filter(t => t.status === 'ok').length,
      fail: list.filter(t => t.status !== 'ok').length,
      tables: list,
    };
  }
  return {
    generated_at: kstText(now),
    mysql: {
      tables: my,
      total_rows: my.reduce((s, t) => s + (t.rows || 0), 0),
      total_bytes: my.reduce((s, t) => s + t.data_bytes + t.index_bytes, 0),
    },
    bigquery,
  };
}
