// KST 날짜 계산.
//
// 원본은 `datetime.utcnow() + timedelta(hours=9)` 로 구합니다. 서머타임이
// 없는 고정 오프셋이라 이렇게 해도 맞습니다. 같은 방식으로 옮깁니다.
// Intl.DateTimeFormat 을 쓰면 더 정확해 보이지만, 원본과 결과가 달라질
// 여지를 만들 이유가 없습니다.

const KST_OFFSET_MS = 9 * 60 * 60 * 1000;

export function kstDateOf(epochMs) {
  const d = new Date(epochMs + KST_OFFSET_MS);
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function kstToday() {
  return kstDateOf(Date.now());
}
