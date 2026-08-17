// CSV 쓰기 유틸입니다.
//
// 파이썬 `csv.writer` 의 QUOTE_MINIMAL 규칙을 그대로 따릅니다. 정답지가
// SHA-256 으로 대조하므로 규칙이 하나만 달라도 불일치입니다.
//
// dbexplorer.js 안에 두었다가 여기로 옮겼습니다. 그 파일이 컬럼 사전 JSON 을
// import 하는데, Node 의 ESM 로더가 JSON import 에 `with { type: 'json' }`
// 을 요구해 테스트가 그 파일을 못 읽었습니다. CSV 규칙은 탐색기에 종속적이지
// 않으니 분리하는 편이 설계로도 맞습니다.

/** 선언 타입이 실수 계열인지 봅니다. SQLite 는 표기가 여러 가지입니다. */
export function isRealType(declType) {
  return /REAL|FLOA|DOUB/i.test(String(declType || ''));
}

/**
 * 칸 하나를 CSV 로 씁니다.
 *
 * 구분자·따옴표·개행이 들어 있을 때만 따옴표로 감싸고, 안의 따옴표는 두 번
 * 반복해 이스케이프합니다. null 과 undefined 는 빈 문자열입니다.
 * 0 은 빈 칸이 아닙니다.
 *
 * `isReal` 은 그 컬럼의 선언 타입이 REAL 계열일 때 참입니다. 이것이 필요한
 * 이유가 있습니다. SQLite REAL 에 든 150.0 을 파이썬은 float 으로 읽어
 * `150.0` 으로 쓰지만, JS 의 Number 는 정수와 실수를 구분하지 않아 `150`
 * 으로 씁니다. JSON 응답에서는 값이 같아 넘어갔지만 CSV 는 바이트로
 * 대조하므로 그대로 두면 해시가 어긋납니다. 컬럼 타입을 알면 재현됩니다.
 */
export function csvCell(v, isReal = false) {
  if (v === null || v === undefined) return '';
  if (isReal && typeof v === 'number' && Number.isInteger(v)
      && Number.isFinite(v)) {
    return `${v}.0`;
  }
  const s = String(v);
  if (/[",\r\n]/.test(s)) return `"${s.split('"').join('""')}"`;
  return s;
}

/**
 * 행 하나를 CSV 한 줄로. 줄바꿈은 파이썬 csv 기본값인 CRLF 입니다.
 * `realFlags` 는 컬럼과 같은 순서의 불리언 배열입니다.
 */
export function csvRow(cells, realFlags) {
  const flags = realFlags || [];
  return `${cells.map((c, i) => csvCell(c, flags[i])).join(',')}\r\n`;
}

/**
 * CSV 를 내보내기 전에 몇 행을 보낼지, 한도를 넘는지 계산합니다.
 *
 * 스트림을 연 뒤에는 HTTP 상태를 되돌릴 수 없으므로 열기 전에 판단해야
 * 합니다. 라우트에서 분리한 것은 D1 없이 테스트하기 위해서입니다.
 *
 * `limit` 이 0 이면 "끝까지"라는 뜻입니다(원본과 같은 약속입니다).
 */
export function csvExportPlan(total, limit, offset, maxRows) {
  const startAt = Math.max(0, offset || 0);
  const remaining = Math.max(0, total - startAt);
  const willSend = limit > 0 ? Math.min(limit, remaining) : remaining;
  return {
    startAt,
    willSend,
    tooLarge: willSend > maxRows,
    parts: Math.max(1, Math.ceil(total / maxRows)),
  };
}
