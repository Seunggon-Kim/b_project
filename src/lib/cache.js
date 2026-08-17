// 초 단위 TTL 메모리 캐시.
//
// 원본의 _STANDINGS_CACHE / _SCHEDULE_CACHE 를 대신합니다.
//
// Workers 의 전역 변수는 isolate 가 살아 있는 동안만 유지됩니다. 언제 버려질지
// 보장이 없어 적중률은 원본보다 낮습니다. 그래도 두는 이유는, 같은 isolate 가
// 연속 요청을 받을 때 외부 사이트를 반복해서 때리지 않기 위함입니다.
// 정확성에는 영향이 없습니다. 캐시가 비면 그냥 다시 가져옵니다.

export function ttlCache(ttlSeconds) {
  const store = new Map();
  return {
    get(key) {
      const hit = store.get(key);
      if (!hit) return undefined;
      if (Date.now() - hit.at > ttlSeconds * 1000) {
        store.delete(key);
        return undefined;
      }
      return hit.value;
    },
    set(key, value) {
      store.set(key, { at: Date.now(), value });
      return value;
    },
  };
}
