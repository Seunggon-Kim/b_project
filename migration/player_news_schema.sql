-- 선수별 뉴스 캐시.
--
-- 구글 뉴스 RSS 는 Cloudflare 엣지에서 막힙니다(설계 문서 §7 위험 2 판정).
-- GitHub Actions 러너에서는 정상 응답하므로, Actions 가 하루 한 번 모아
-- 이 표에 넣고 Worker 는 여기만 읽습니다.
--
-- 갱신은 통째로 갈아 끼웁니다(DELETE 후 INSERT). 선수마다 지우고 넣으면
-- SQL 문이 두 배가 되고, 어차피 매일 전량을 다시 모읍니다.

DROP TABLE IF EXISTS player_news;

CREATE TABLE player_news (
  player_id  TEXT    NOT NULL,   -- players.player_id
  rank       INTEGER NOT NULL,   -- 화면 표시 순서 1..5
  title      TEXT    NOT NULL,   -- 언론사 꼬리를 뗀 제목
  link       TEXT    NOT NULL,
  press      TEXT    NOT NULL,
  pub_date   TEXT,               -- RSS pubDate 원문
  fetched_at TEXT    NOT NULL,   -- 수집 시각 (KST)
  PRIMARY KEY (player_id, rank)
);

-- 선수 한 명의 기사를 순서대로 읽는 것이 유일한 조회 패턴입니다.
-- PRIMARY KEY 가 (player_id, rank) 라 그 조회는 이미 덮입니다.
