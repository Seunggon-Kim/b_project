-- 1군 등록 현황과 등말소 이력입니다.
--
-- ## 왜 두 표인가
--
-- KBO 는 **오늘 것만** 보여 줍니다. 어제 누가 등록됐는지 묻는 화면이
-- 없습니다. 그래서 매일 받아 우리가 쌓아야 하고, 소급이 안 됩니다.
--
-- 명단을 날마다 통째로 쌓으면 445행 x 365일 = 16만 행입니다. 대부분
-- 어제와 같은 값이라 낭비입니다. 그래서 나눕니다.
--
--     kbo_roster        지금 1군에 누가 있는지. 덮어씁니다.
--     kbo_roster_moves  언제 들어오고 나갔는지. 쌓습니다.
--
-- ## 등번호가 여기 있는 이유
--
-- 같은 팀에 같은 이름 투수가 둘일 때(박준영 한화, 이승현 삼성)
-- 등번호로만 갈립니다. `players.back_number` 는 낡아서(이적·번호 변경
-- 반영 안 됨) 이 표가 최신값을 갖습니다.
--
-- ## player_id 가 비는 경우
--
-- 등록 현황 페이지는 이름과 등번호만 줍니다. 선수 ID 가 없습니다.
-- 우리 쪽 기록과 이름+팀+등번호로 짝지어 채우는데, 신인이나 육성선수는
-- 아직 기록이 없어 못 찾습니다. 그때는 NULL 로 둡니다. 이름은 남으니
-- 화면에 보여 줄 수 있고, 나중에 기록이 생기면 채워집니다.

CREATE TABLE IF NOT EXISTS kbo_roster (
  team         TEXT NOT NULL,
  name         TEXT NOT NULL,
  back_number  TEXT NOT NULL,     -- '00' 과 '0' 이 다릅니다. 정수 금지.
  role         TEXT NOT NULL,     -- 감독/코치/투수/포수/내야수/외야수
  player_id    INTEGER,           -- 못 찾으면 NULL
  as_of        TEXT NOT NULL,     -- YYYY-MM-DD (KST)
  league       TEXT NOT NULL DEFAULT '1군',   -- 1군 | 퓨처스
  PRIMARY KEY (team, name, back_number)
);

-- 이미 만들어진 표에 컬럼을 더합니다. 두 번 돌려도 괜찮게 두려면
-- 적재 스크립트가 오류를 삼켜야 합니다(roster_to_d1.py).
-- ALTER TABLE kbo_roster ADD COLUMN league TEXT NOT NULL DEFAULT '1군';

CREATE INDEX IF NOT EXISTS idx_roster_player ON kbo_roster(player_id);
CREATE INDEX IF NOT EXISTS idx_roster_team   ON kbo_roster(team);

CREATE TABLE IF NOT EXISTS kbo_roster_moves (
  move_date    TEXT NOT NULL,     -- YYYY-MM-DD (KST)
  kind         TEXT NOT NULL CHECK(kind IN ('등록','말소')),
  team         TEXT NOT NULL,
  name         TEXT NOT NULL,
  position     TEXT,              -- 투수/포수/내야수/외야수
  player_id    INTEGER,
  PRIMARY KEY (move_date, kind, team, name)
);

CREATE INDEX IF NOT EXISTS idx_moves_player ON kbo_roster_moves(player_id);
CREATE INDEX IF NOT EXISTS idx_moves_date   ON kbo_roster_moves(move_date);
