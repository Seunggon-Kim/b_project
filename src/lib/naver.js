// 네이버 스포츠 API(api-gw.sports.naver.com)를 JSON 으로 읽습니다.
//
// 원본 api/main.py 의 _kbo_fetch_json(url, timeout=8) 입니다. 경기 일정
// (routes/schedule.js)과 1군 순위(routes/standings.js)가 같이 씁니다.
//
// requests 의 timeout=8 은 연결·읽기 단위이고 AbortSignal.timeout 은 전체
// 경과 시간이라 엄밀히는 다르지만, 8초를 넘겨 정상 응답이 오는 경우가
// 없어 실질적인 차이는 없습니다.
//
// headers 는 기본 user-agent 위에 덧붙입니다. 통계(statistics) 주소는
// 브라우저 user-agent 와 Referer 가 있어야 답합니다.
export async function kboFetchJson(url, headers = {}) {
  const res = await fetch(url, {
    headers: { 'user-agent': 'Mozilla/5.0', ...headers },
    signal: AbortSignal.timeout(8000),
  });
  // 원본 raise_for_status() 자리입니다. 예외 메시지 문구만 다릅니다.
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
