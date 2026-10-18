// src/lib/tos.js
// KBO 이용약관(2026-10-14 시행 제14조) 때문에 공개 화면에서 뺀 표 이름입니다.
// 데이터 탐색(routes/dbexplorer.js)과 저장소 현황(lib/opsstorage.js)이 같은 목록을 씁니다.
// JSON 을 import 하지 않아 node:test 가 직접 읽을 수 있습니다.

export const KBO_TOS_HIDDEN_TABLES = new Set([
  'futures_games', 'futures_season_stats', 'futures_teams', 'kbo_roster', 'kbo_roster_moves',
]);
