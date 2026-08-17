// API 주소를 여기 한 곳에서 정합니다.
//
// 예전에는 EC2 의 nginx 가 `/api` 를 같은 서버의 FastAPI 로 넘겨 주어
// 상대 경로면 충분했습니다. 그 서버가 없어졌으므로 이제는 Cloudflare
// Worker 를 절대 주소로 직접 부릅니다.
//
// 한 곳에 모은 이유가 있습니다. 이 값이 js/api.js, pages/article.html,
// pages/factor-stats.html 세 군데에 따로 적혀 있었고, 게다가 쓰이지 않는
// 루트 api.js 에 네 번째 값이 있었습니다. 다음에 주소가 바뀔 때 하나를
// 빠뜨리면 그 페이지만 조용히 죽습니다.
//
// **이 파일은 api.js 보다 먼저 로드되어야 합니다.** 순서가 뒤바뀌면
// window.KBO_API_BASE 가 undefined 인 채로 읽혀 요청이 `undefined/teams`
// 로 나갑니다.
(function () {
  var host = window.location.hostname;
  var isLocal = host === 'localhost' || host === '127.0.0.1';

  // 로컬에서 `py -m uvicorn api.main:app --port 8000` 을 띄워 두고 화면을
  // 열면 그쪽을 봅니다. 그 외에는 배포된 Worker 를 봅니다.
  window.KBO_API_BASE = isLocal
    ? 'http://localhost:8000'
    : 'https://kbo-api.bstats-baseball.workers.dev';
})();
