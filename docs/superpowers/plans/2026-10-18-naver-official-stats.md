# KBO 사이트 출처 표를 네이버 스포츠 API 로 바꾸기 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** KBO 이용약관 제14조 차항(2026-09-15 공고, 2026-10-14 시행, 자동 수집 금지)에 따라 멈춘 KBO 사이트 수집(main 4707d4c)을 네이버 스포츠 API(`api-gw.sports.naver.com`)와 이미 가진 play_by_play 로 대신합니다. evan 결정(2026-10-18): 사이트는 공개 유지, KBO 사이트는 어떤 방식으로도 부르지 않음, **지난 시즌 공식 기록도 네이버 값으로 바꿈**.

**대상 표:** `kbo_official_batter_stats`, `kbo_official_pitcher_stats`, `team_season_rank`, `team_seasons`, `players`.
**대체하지 않는 표(네이버에 없음):** `futures_games`, `futures_season_stats`, `kbo_roster`, `kbo_roster_moves` → 화면 정리 목록(맨 끝)만.

## Global Constraints

- koreabaseball.com·KBO 이미지 서버(`6ptotvmi5753.edge.naverncp.com/KBO_IMAGE`)는 코드·손 실행·확인용 호출 어디서도 부르지 않습니다.
- 네이버 호출은 `User-Agent`(브라우저)·`Referer: https://m.sports.naver.com/` 를 붙이고 **초당 1회 이하**로 합니다(조사 때 1.1초 간격으로 900여 건, 오류 없음).
- MySQL 쓰기·표 교체·push·배포는 evan 허락 뒤에만 합니다(쓰기 단계마다 따로 허락). 같은 main 을 여러 세션이 씁니다: push 직전 `git fetch` 로 목록을 다시 보고 허락받은 sha 만 올립니다.
- 애매한(데이터로 분명히 못 나누는) 칸은 만들지 않습니다(evan 규칙). 검증에서 기존 값과 맞지 않는 계산 칸은 넣지 않고 NULL 로 두며 화면에서 숨깁니다.
- 커밋 메시지 `<type>(<scope>): 한국어 설명` + `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## 조사 결과 (2026-10-18, 원자료는 세션 scratchpad `naver_plan/`)

### 1. 네이버 선수 시즌 기록 API

`GET /statistics/categories/kbo/seasons/{y}/players?playerType=HITTER|PITCHER&pageSize=400&teamCode={팀}`

- **제공 시즌: 2008~2026.** 2007 이전은 `400`(팀 API 도 같음, 2005~2007 은 빈 목록).
- **pageSize 최대 400**(500 을 주면 400 만 옴, 1000 은 `400` 오류). **page 파라미터는 무시됩니다**(1·2·3 쪽이 같은 사람). `sortField` 는 동작하지만 늘 내림차순. 그래서 **팀별(`teamCode`)로 나눠 받아야** 빠짐이 없습니다(한 팀 최대 ~45명). `teamId`·`team` 은 무시, `teamCode` 만 됩니다.
- `gameType` 은 무시됩니다(POST_SEASON·FUTURES 를 줘도 정규시즌). 포스트시즌·퓨처스 기록은 이 API 로 못 받습니다.
- 규정 미달 포함(`isQualified` true/false, 미달은 `ranking` null). 0타석 선수는 시즌에 따라 빠짐(아래 대조).
- **트레이드 선수:** 2025 는 두 팀 목록에 다 나옵니다. 새 팀 행 = 시즌 합계, 옛 팀 행 = 옛 팀 몫(손아섭 HH 111경기·NC 76경기). 2024 이전은 한 팀에만 나옵니다. 규칙: **선수마다 경기 수가 가장 큰 행**을 씁니다(DB 와 같아짐).
- 칸(타자): `hitterGameCount, hitterAb, hitterRun, hitterHit, hitterH2, hitterH3, hitterHr, hitterRbi, hitterSb, hitterCs(늘 null), hitterBb(고의4구 포함), hitterHp, hitterKk, hitterGd(늘 null), hitterHra, hitterObp, hitterSlg, hitterOps, hitterIsop, hitterBabip, hitterWoba, hitterWrcPlus, hitterWpa, hitterWar`.
- 칸(투수): `pitcherGameCount, pitcherWin, pitcherLose, pitcherSave, pitcherHold, pitcherInning('149 1/3' 글자), pitcherHit, pitcherHr, pitcherBb, pitcherHp, pitcherKk, pitcherR, pitcherEr, pitcherEra, pitcherWhip, pitcherQs, pitcherInningKk(K/9), pitcherInningBb(BB/9), pitcherKkBbRate(K/BB), pitcherPaKkRate, pitcherPaBbRate, pitcherWra, pitcherWpa, pitcherWar, pitcherStart(늘 null), pitcherPitchCount(늘 null)`.
- 공통: `playerId`(KBO 와 같은 번호), `playerName`, `teamId`(KT·SS·OB·HT·LT·SK·NC·WO·HH·LG), `teamName`(**지금 이름**: 2008 히어로즈가 '넥센'), `backNumber`, `height`, `weight`, `playerImageUrl`, `profile`(JSON 글자).

### 2. 현재 DB 와 대조 (2008~2026, 공개 `/db/table/:name/csv` 로 받은 값)

| | DB 행 | 네이버와 겹침 | DB 에만 | 네이버에만 |
|---|---|---|---|---|
| 타자 | 6,424 | 6,317 | 107 | 0 |
| 투수 | 4,623 | 4,596 | 27 | 0 |

겹친 행의 칸 일치(정수 칸은 그대로 비교):

- 타자: G 6,306/6,317 · AB·R·H·2B·HR·RBI·BB·HBP·SO 6,315/6,317 · 3B 6,316/6,317. 틀린 2명은 2025 트레이드 2명(위 규칙이면 맞음). G 차이 9건(2011 5·2018 3·2021 1)은 원인 미확인 → Task 2 에서 확인.
- 타자 AVG·OBP·SLG: AB 0 선수의 빈칸↔0.000 차이를 빼면 4,996건 중 5건 다름. 그중 3건은 반올림(KBO 는 0.3125→0.313, 파이썬 `round` 는 0.312) → `Decimal ROUND_HALF_UP`, 2건은 트레이드.
- 투수: G·W·L·SV·HLD·H·HR·BB·HBP·SO·R·ER·QS **4,596/4,596**. IP 4,503/4,596 은 모두 표기 차이(DB `'1/3'` ↔ 네이버 `'0 1/3'`). ERA 4,540·WHIP 4,553 은 소수 자리·반올림 차이(값 검증은 Task 2).
- 팀 이름: 타자 6,240/6,317, 투수 4,547/4,596 → 2008~2009 히어로즈('우리' ↔ '넥센') 등 **그 시즌 이름 차이**. `team_seasons(franchise_id, season)` 로 그 시즌 이름을 붙이면 됩니다.
- **DB 에만 있는 타자 107행:** 101행이 0타석(대주자·대수비), 6행이 1~8타석. 2009(38)·2011(47)에 몰림.
- **DB 에만 있는 투수 27행(9명):** 이민호(NC 2013~2019, 한 시즌 최대 130 2/3이닝), 이종혁·박성웅·오동욱·최세창·남호·이찬혁·문원·조제영·배창현. 네이버 선수 상세(`/seasons/{y}/players/{id}`)도 `400`. 네이버가 이 선수들을 통째로 빼 둔 것으로 보입니다. PBP 로 개수 칸은 셀 수 있지만 자책점(ER)·ERA 는 PBP 로 못 만듭니다.

### 3. 네이버에 없는 칸과 채울 방법

PBP(play_by_play, 네이버 문자중계)는 2008~2026 정규시즌을 사실상 다 덮습니다(시즌별 경기 ID 수: 2008 515·2013 590·2015~2026 718~726, games 정규시즌 504~721과 맞음). `pa_result`·`pa_result_detail`·`description`(주자·교체 문장)·`pitch_number`·`on_1b/2b/3b`·`score_*` 가 있습니다.

네이버 경기 기록 API `GET /schedule/games/{gameId}/record`(경기 ID 는 DB `games.game_id` 와 같음: 옛 경기는 13자 `20100701LTSS0`, 최근 경기는 17자 `20160701HTWO02016`)는 2008 부터 응답합니다. `pitchersBoxscore`(투수별 `inn, pa(상대 타자), bf(투구 수), ab, hit, hr, bb, bbhp, kk, r, er, wls(승·패·세·홀)`, 나온 순서), `battersBoxscore`(`ab, hit, run, rbi, hr, bb, kk, sb(2025~), pos, batOrder`), `pitchingResult`(W·L·S·H), `etcRecords`(결승타·홈런·2루타·3루타·도루·실책·병살타·폭투·보크… 글 문장)를 줍니다. 블론세이브·세이브 기회는 없습니다.

타자 칸 (`kbo_official_batter_stats`):

| 칸 | 방법 | 비고 |
|---|---|---|
| player_team | 네이버 teamId → team_seasons 그 시즌 이름 | |
| games, at_bat, run, single(=H), double, triple, home_run, run_batted_in, base_on_balls, hit_by_pitch, strikeout | 네이버 시즌 API | 대조 99.97%+ |
| batting_average, slugging_percentage, on_base_percentage, isop | 네이버 값, ROUND_HALF_UP 3자리 | AB 0 이면 NULL(DB 와 같게) |
| on_base_plus_slugging | OBP+SLG | |
| plate_appearance | PBP 타석 수 | 검증 필요(타격방해·주루사 타석 처리) |
| sacrifice_bunts, sacrifice_fly | PBP `희생번트*`, `희생플라이*` | |
| intentional_base_on_balls | PBP `고의4구`·`자동 고의4구` | 2018~ 자동, 이전은 4구 고의4구 |
| ground_into_double_play | PBP `병살타`(+삼중살) | 네이버 hitterGd 가 늘 null |
| total_bases, extra_base_hits | H·2B·3B·HR 로 계산 | |
| multi_hits | PBP 경기별 안타 2개 이상 | |
| runners_in_scoring_position | PBP 2·3루 주자 있을 때 타율 | |
| pinch_hit_batting_average | PBP `대타 X (으)로 교체` 다음 타석 | 이름→ID 는 바로 다음 타석 batter_ID 로 잇기, 검증 필수 |
| ground_outs, air_outs, go_ao | PBP `pa_result_detail`(땅볼·플라이·라인드라이브·인필드 플라이…) | KBO 분류와 같은지 검증 |
| gw_rbi(결승타) | 박스스코어 `etcRecords` '결승타' 이름 → 그 경기 타자 목록 ID | 박스 받기 필요(Task 4) |
| strikeout_per_pa, base_on_balls_per_pa, bb_k, p_pa | 위 값으로 계산(p_pa 는 PBP 투구 수) | 앞 둘은 지금도 95% 빈칸 |
| extended_runs, gross_production_average | 공식(XR·GPA) | KBO 공식과 같은지 검증, 안 맞으면 NULL |

투수 칸 (`kbo_official_pitcher_stats`):

| 칸 | 방법 | 비고 |
|---|---|---|
| games, wins, losses, save, hold, innings_pitched, hits, home_run, base_on_balls, hit_by_pitch, strikeout, run, earned_run, quality_start | 네이버 시즌 API | 대조 100%, IP 는 `'0 1/3'`→`'1/3'` |
| earned_run_average, walks_plus_hits_per_inning_pitched, k_9, bb_9, k_bb | 네이버 값(반올림 맞춤) | |
| winning_percentage | W/(W+L) | |
| games_started, games_finished | PBP 팀·경기별 첫·마지막 투수 | 네이버 pitcherStart 늘 null |
| complete_game, shutout | PBP 그 경기 그 팀 투수 1명(+실점 0) | |
| total_batters_faced, number_of_pitchers(투구 수) | PBP(또는 박스 `pa`·`bf`) | |
| double, triple, sacrifice_bunts, sacrifice_fly, intentional_base_on_balls, ground_into_double_play, ground_outs, air_outs, go_ao | PBP pa_result(투수 기준) | |
| batting_average, on_base_percentage, slugging_percentage, on_base_plus_slugging, batting_average_on_balls_in_play | PBP 로 계산 | |
| wild_pitch, balk | PBP `description` 의 `폭투`·`보크`(한 투구 행에 주자 여러 명이어도 1번) | 2025 폭투 645행·보크 35행, 검증 필수 |
| wins_game_started, wins_game_relieved | 박스 `wls`+선발 여부 | Task 4 |
| p_g, p_ip, strikeout_per_pa, base_on_balls_per_pa | 계산 | 뒤 둘은 지금도 94% 빈칸 |
| **blown_save, save_opportunity, total_saves** | **못 만듦**(네이버에 없음, PBP 로 만들면 세이브 상황 판정이 애매) | 결정 3 |

### 4. 화면·API 가 쓰는 칸

- API: `/stats/batters`·`/stats/pitchers` 는 `BATTER_STAT_COLUMNS`·`PITCHER_STAT_COLUMNS`(모든 칸), `/players/:id` 는 `SELECT *` 로 두 표의 모든 칸을 내보냅니다. 팀 기록(`teamrecord.js`)은 AB·H·HR·R·RBI·ER·IP·SO·BB 합계, `/leaders` 는 규정·순위 칸.
- 화면: `js/stats/metrics.js`(선수·팀 통계 표)가 거의 모든 칸을 열로 씁니다. `pages/player-analytics.html` 은 ERA·WHIP·K/9·BB/9·K/BB·BABIP·TBF·투구 수·CG·SHO·QS·BS·WP·BK·GS 등.
- 어디서도 안 쓰는 칸: 타자 `on_base_plus_slugging`(API 가 `ops` 별칭으로만), `go_ao`·`strikeout_per_pa`·`base_on_balls_per_pa`·`bb_k`·`isop`, 투수 `winning_percentage`·`wins_game_started`·`wins_game_relieved`·`total_saves`·`go_ao`·`p_g`·`p_ip`·`strikeout_per_pa`·`base_on_balls_per_pa`·`on_base_plus_slugging`. `players` 의 `draft_year`·`draft_order`·`signing_bonus`·`image_url` 은 src SQL 이 이름으로 안 부르지만 `/players/:id` 가 `p.*` 로 내보내고 화면이 `image_url` 을 씁니다.
- 결론: 안 쓰는 칸은 계산이 쉬울 때만 채우고 아니면 NULL 로 둬도 화면이 깨지지 않습니다. BS·세이브 기회는 `metrics.js`·`player-analytics.html` 이 쓰므로 NULL 이면 화면에서 열을 숨겨야 합니다.

### 5. 팀 순위 `/statistics/categories/kbo/seasons/{y}/teams`

2008~2026, 178 팀-시즌 모두 DB `team_season_rank` 와 rank·games·W·L·D·pct·팀 이름(team_seasons 경유) **178/178 일치**. gb 173/178(2010 다섯 팀 0.5~1.5 차이, 2010 무승부 처리 차이로 보임 → Task 1 에서 확인). 칸 대응: `ranking→rank, gameCount→games, winGameCount→wins, loseGameCount→losses, drawnGameCount→draws, wra→pct, gameBehind→gb, teamId→franchise_id`, `league` 는 '정규'(1999·2000 양대리그는 2008 이전이라 무관). 새 시즌의 `team_seasons` 행은 teamId + 그 시즌 이름으로 만듭니다(네이버 `teamName` 은 지금 이름이라 바뀐 해에는 손 확인).

### 6. players

- 선수 상세 `GET /statistics/categories/kbo/seasons/{y}/players/{id}` (`/players/kbo/{id}` 는 403, `/players/kbo/{id}/info` 는 팀·등번호·포지션만): `backNo, position(영문), dateOfBirth, height, weight, playerPlayType('우투좌타'), salary, career(마지막 학교), draftInfo('23 키움 11R 106순위'), teamId, isRetire`.
- 표본 40명(players 1,760명 중 무작위): 응답 40/40, 생년월일 40/40, 키·몸무게 39/40. `playerPlayType` 은 15/40 이 null(은퇴 선수), `draftInfo` 23/40 null. `career` 는 KBO 의 학교 전체 경로가 아니라 마지막 학교. 계약금(`signing_bonus`)은 없습니다.
- players 1,760명은 모두 2008 이후 기록이 있는 선수입니다(2008 이전만 뛴 1,457명은 players 에 없음).
- 사진: `https://sports-phinf.pstatic.net/player/kbo/default/{id}.png`. **없는 ID 도 200 + 기본 그림(24,159바이트)**을 줘서 크기·해시로 기본 그림을 걸러야 합니다. KBO 사진(jpg, middle)과 비율·배경이 다를 수 있어 선수 분석 머리 칸 캡처 확인이 필요합니다.

### 7. 새 선수 추가

PBP 적재 뒤 `batter_ID`·`pitcher_ID`·`pos_*_id`·`on_*_id` 가운데 players 에 없는 ID → 선수 상세 API 로 한 행씩 넣습니다. 소속(`team_id`, 한글 이름)은 매일 올 시즌 선수 목록(팀별)의 teamId 를 team_seasons 이름으로 바꿔 갱신합니다(`sync_players_from_roster` 대체). 1군 등록 명단 자체는 네이버에 없어 대체하지 않습니다.

## 파일 지도

| 파일 | 맡는 일 | Task |
|---|---|---|
| `data_collection/naver_http.py` (새) | 헤더·초당 1회·재시도·JSON | 0 |
| `data_collection/naver_team_ranks.py` (새) | team_season_rank·team_seasons(2008~) | 1 |
| `data_collection/naver_season_stats.py` (새) | 시즌 API 를 팀별로 받아 두 공식 표의 네이버 칸 | 2 |
| `data_collection/pbp_season_stats.py` (새) | PBP 로 빈 칸 계산 | 3 |
| `data_collection/naver_boxscore.py` (새, 결정 4) | 박스스코어 원자료 표 `naver_boxscore_*` | 4 |
| `data_collection/naver_players.py` (새) | players 갱신·새 선수·사진 | 5 |
| `.github/workflows/daily.yml`, `database/lineage_writes.json`, `scripts/build_lineage.py` 결과 | 단계 연결·계보 | 6 |
| `src/routes/*` 출처 문구, `dashboard_js/*` | 화면 정리 | 8 |
| `tests/test_naver_*.py` (새) | 저장해 둔 응답(fixture)으로 파싱·계산 시험 | 각 Task |

## Tasks

### Task 0: 네이버 호출 도우미

- [ ] `naver_http.py`: `get_json(path, params)` — UA·Referer, 직전 호출에서 1.1초 미만이면 기다림, 5xx·연결 오류만 3회 재시도, 4xx 는 바로 올림. 호스트가 `api-gw.sports.naver.com` 이 아니면 거부(KBO 주소 차단 겸).
- [ ] 시험: 호스트 거부, 간격 지킴(시계 주입), 4xx 즉시 실패.
- [ ] `src/lib/naver.js`(Worker)와 헤더를 같게 둡니다.

### Task 1: 팀 순위

- [ ] `naver_team_ranks.py --from 2008 --to 2026 | --current | --dry-run`. 2010 gb 차이를 먼저 확인(네이버 gb 와 (W-L) 차 공식 비교) 후 어느 값을 쓸지 기록.
- [ ] 쓰기: 2008~ 행만 지우고 넣음(`mysql_sink.mirror`). 2007 이전은 결정 1 대로.
- [ ] 시험: fixture 2010·2025 로 칸 대응·이름 매핑.
- [ ] 되돌리기: 쓰기 전 `SELECT` 결과를 `~/.bstats/backups/team_season_rank_YYYYMMDD.sql` 로.

### Task 2: 공식 기록의 네이버 칸

- [ ] 시즌·팀·종류별로 받아(시즌당 약 20회) 선수별 최대 경기 행을 고름. ROUND_HALF_UP, IP 표기 맞춤, AB 0 → 비율 NULL.
- [ ] 2011·2018·2021 G 차이 9건 원인 확인(네이버 vs DB, 트레이드·이름 변경 여부).
- [ ] 대조 보고 `docs/naver-migration/official-compare.md`: 시즌별 행 수·칸별 일치율(위 숫자 재현).
- [ ] 시험: fixture 2025(트레이드 2명)·2009(0타석 누락)·반올림 0.3125.

### Task 3: PBP 로 빈 칸 계산

- [ ] 칸마다 함수 하나(위 표). 시즌 단위로 MySQL 에서 읽어(시즌당 23만 행 이하) 파이썬에서 셈. 정규시즌만(`kbo_season`/경기 ID 규칙 재사용).
- [ ] **검증 문턱:** 2008~2026 의 지금 DB 값(KBO 에서 받은 값)과 칸별 정확 일치율을 냄. 99% 이상이면 채택, 미만이면 원인 확인 뒤 고치거나 NULL(결정 3 과 같이 보고). 결과표를 `docs/naver-migration/pbp-columns-verify.md` 에.
- [ ] PBP 빠진 경기(20250628HHSK 원천 깨짐, 20210627LTOB 목록 없음 등)는 그 선수 값이 모자람 → 검증표에 경기 목록과 영향 행 수를 적음.

### Task 4: 박스스코어 (결정 4 가 '받음'일 때)

- [ ] 2008~2026 정규시즌 약 12,500경기 × 1회 = 약 3.8시간(초당 1회 이하). 원자료를 MySQL 새 표(`naver_boxscore_raw(game_id, json, fetched_at)`)에 두고 다시 받지 않음. daily 는 그날 경기만.
- [ ] 쓰는 곳: 결승타(gw_rbi), 선발승·구원승, TBF·투구 수 교차 확인.

### Task 5: players

- [ ] 1,760명 + 새 선수 상세 받기(약 30분). 바꾸는 칸: back_number, position(한글로), birthday, height, weight, throw/bat(`playerPlayType`), salary, team_id(올 시즌 목록 기준), image_url(sports-phinf, 기본 그림이면 NULL). 네이버가 null 인 칸은 결정 5 대로.
- [ ] 화면 확인: 선수 분석 머리 사진 캡처(현역·은퇴·사진 없음 3명).
- [ ] `heal_player_photos.py`·`player_info_scraper.py`·`add_new_players.py`·`sync_players_from_roster.py` 는 지우지 말고 워크플로에서 안 부르는 상태 유지(4707d4c), 새 스크립트가 대신함.

### Task 6: daily 연결·계보

- [ ] daily: PBP → games → `naver_team_ranks --current` → `naver_season_stats --current` → `pbp_season_stats --current` → (`naver_boxscore --date`) → `naver_players --new --sync-team` → 구종 가치. 각 단계 `record_job_run`(KNOWN_JOBS 추가), 요약·실패 판정.
- [ ] 계보: 원천 `naver_stats`(시즌·팀·선수 API)·`naver_record`(박스) 추가, `scripts/build_lineage.py` 로 다시 만들기, `tests/test_lineage.py` 등 통과.

### Task 7: 교체와 확인 (evan 허락)

- [ ] 교체 전 두 공식 표·players·team_season_rank 전체를 `~/.bstats/backups/*_kbo_20261018.sql` 로 백업(PITR 7일도 있음).
- [ ] 2008~2026 행 교체(한 트랜잭션), 결정 2·3 반영.
- [ ] `/admin/purge-cache` 후 `migration/api_compare.mjs` 로 교체 전후 `/stats/batters`·`/stats/pitchers`·`/leaders`·`/players/:id`·`/teams/:id`·`/wrc/*` 대조, 차이 보고.
- [ ] 되돌리기: 백업 SQL 다시 넣기 + 캐시 비우기.

### Task 8: 화면·문구 정리 (화면 세션)

- [ ] 출처 문구: `dashboard_js/index.html:92·964` "KBO 공식 (koreabaseball.com)", `js/player-stats/page.js:189-190`, `js/team-stats/page.js:111·117` "KBO 실시간" → 네이버 스포츠.
- [ ] 1군 순위 표 최근 10경기 칸(네이버는 최근 5경기만) → 열 바꾸기 또는 숨기기.
- [ ] NULL 이 된 칸(결정 3) 열 숨기기: `js/stats/metrics.js`, `pages/player-analytics.html`.
- [ ] 퓨처스·등록 명단(대체 안 함, 지금 410): `index.html` 일정 퓨처스 토글(`ep: 'schedule/futures'`)·퓨처스 순위·개인 순위(`loadFutures`)·선수 검색의 퓨처스 폴백(597행)·`/roster`·`/roster/moves` 칸, `pages/player-analytics.html` 2군 전용 선수 화면(`getFuturesPlayer`, 928행)·퓨처스 검색 폴백(439행). 각각 숨기거나 "제공 중단" 안내로.
- [ ] 계보 탭: 멈춘 작업·바뀐 원천 표시 확인(4707d4c 에서 `stopped` 추가됨).

## evan 결정 (2026-10-18)

1. **2007 이전:** 백업 파일로 빼 두고 DB·화면에서 지웁니다(출처를 네이버 하나로).
2. **네이버에 없는 행:** 타자는 네이버 기준(DB 에만 있는 107행 지움). 투수 9명 27행은 원인 확인 뒤 다시 정함.
3. **못 만드는 칸:** blown_save·save_opportunity·total_saves 와 검증 문턱(99%)을 못 넘는 계산 칸은 NULL, 화면에서 숨김.
4. **박스스코어:** 받습니다(네이버만, 1초 이상 간격). 원자료는 우선 로컬 파일(`~/.bstats/naver_boxscore/`)로 두고 DB 표는 쓰기 허락 때 정함.
5. **players 에서 네이버가 비운 칸:** 미정(evan 답 대기). 그 칸은 건드리지 않는 형태로 준비.
6. **교체 방식:** 같은 표에 덮어씁니다(덮기 전 백업 덤프, PITR 7일).

## evan 이 정할 것 (조사 때 질문, 위 결정으로 답함)

1. **2007 이전 기록(1982~2007):** 네이버에 없습니다. 공식 기록 타자 5,572행·투수 3,348행, 팀 순위 1982~2007(26시즌)은 10/14 전에 KBO 에서 받은 값입니다. (가) 그대로 둠 (나) 지움 (다) 화면에서만 숨김.
2. **네이버에 없는 선수 행:** 0타석 타자 101행(+1~8타석 6행), 네이버가 빼 둔 투수 9명 27행(이민호 등). (가) 지금 DB 값 유지 (나) 지움 (다) 개수 칸만 PBP 로, ER·ERA 는 NULL.
3. **못 만드는 칸:** blown_save·save_opportunity·total_saves(+검증 문턱을 못 넘는 계산 칸). (가) NULL + 화면 열 숨김(권장, 애매한 기능은 안 만든다는 규칙) (나) 지난 시즌은 지금 값 유지, 올 시즌부터 NULL.
4. **박스스코어 받기(약 3.8시간, 1회):** 결승타·선발승/구원승·교차 확인에 필요. 받지 않으면 gw_rbi·wins_game_started·wins_game_relieved 는 NULL.
5. **players 에서 네이버가 비운 칸(은퇴 선수 투타·드래프트, 학교 전체 경로, 계약금):** (가) 지금 값 유지 (나) NULL.
6. **교체 방식:** (가) 같은 표에 덮어쓰기(백업 후) (나) 새 표(`*_naver`)를 만들고 API 를 옮긴 뒤 옛 표 삭제.
