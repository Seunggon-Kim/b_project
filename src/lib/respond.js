// FastAPI 와 같은 형태의 JSON 응답을 만듭니다.
//
// 골든 비교가 본문을 바이트가 아니라 파싱된 값으로 대조하므로 키 순서는
// 상관없습니다. 다만 content-type 이 다르면 requests 가 .json() 을 실패해
// 비교 자체가 어긋나므로 charset 까지 맞춥니다.

export function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      // 원본 api/main.py 의 CORSMiddleware(allow_origins=["*"]) 와 같게 둡니다.
      'access-control-allow-origin': '*',
    },
  });
}

/**
 * 원본은 최상위 예외 핸들러가 500 과 함께 detail 을 돌려줍니다.
 * 다만 외부 연동 엔드포인트들은 자체 try/catch 로 200 + error 필드를
 * 내보냅니다. 그 차이를 그대로 유지해야 골든 비교가 통과합니다.
 */
export function serverError(err) {
  return json({ detail: String(err && err.message ? err.message : err) }, 500);
}
