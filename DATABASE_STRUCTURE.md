# 데이터베이스 구성 문서

## 📊 데이터베이스 개요

**파일 위치**: `database/kbo_stats.db`  
**데이터베이스 타입**: SQLite3  
**스키마 파일**: `database/schema.sql`

---

## 📋 테이블 구조

### 1. `teams` - 팀 정보

**용도**: KBO 10개 구단 정보

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| team_id | TEXT (PK) | 팀 ID (예: 'LG', 'KT') |
| team_name | TEXT | 팀 이름 (예: 'LG 트윈스') |
| team_name_en | TEXT | 영문 팀 이름 |
| city | TEXT | 연고지 |
| founded_year | INTEGER | 창단 연도 |
| stadium | TEXT | 홈구장 |

**데이터 현황**: 10개 팀 (LG, KT, SSG, NC, 두산, KIA, 롯데, 삼성, 한화, 키움)

---

### 2. `players` - 선수 정보

**용도**: 선수 기본 정보

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| player_id | TEXT (PK) | 선수 ID |
| player_name | TEXT | 선수 이름 |
| team_id | TEXT (FK) | 소속 팀 ID |
| position | TEXT | 포지션 |
| birth_date | DATE | 생년월일 |
| height_cm | INTEGER | 키 (cm) |
| weight_kg | INTEGER | 몸무게 (kg) |
| bats | TEXT | 타석 (우/좌/양) |
| throws | TEXT | 투구 (우/좌) |

---

### 3. `games` - 경기 정보

**용도**: 경기별 기본 정보

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| game_id | TEXT (PK) | 경기 ID (예: 20250322HHKT02025) |
| game_date | DATE | 경기 날짜 |
| season | INTEGER | 시즌 연도 |
| game_type | TEXT | 경기 유형 (정규시즌/포스트시즌) |
| home_team_id | TEXT (FK) | 홈팀 ID |
| away_team_id | TEXT (FK) | 원정팀 ID |
| home_score | INTEGER | 홈팀 득점 |
| away_score | INTEGER | 원정팀 득점 |
| stadium | TEXT | 경기장 |
| attendance | INTEGER | 관중 수 |
| game_time_minutes | INTEGER | 경기 시간 (분) |
| weather | TEXT | 날씨 |
| temperature | REAL | 기온 |

**2025 시즌 현황**: **719개 경기**

---

### 4. `play_by_play` - 플레이-바이-플레이 데이터

**용도**: 타석별 상세 기록 (투구, 타격, 주루 등 모든 플레이)

**주요 컬럼** (총 73개):

#### 기본 정보

- `pbp_id` (INTEGER, PK, AUTO_INCREMENT) - 고유 ID
- `gameID` (TEXT) - 경기 ID
- `game_date` (DATE) - 경기 날짜
- `stadium` (TEXT) - 경기장

#### 투구 정보

- `pitch_type` (TEXT) - 구종
- `pitcher` (TEXT) - 투수 이름
- `pitcher_ID` (TEXT) - 투수 ID
- `speed` (REAL) - 구속
- `pitch_result` (TEXT) - 투구 결과
- `pitch_number` (INTEGER) - 투구 번호

#### 타격 정보

- `batter` (TEXT) - 타자 이름
- `batter_ID` (TEXT) - 타자 ID
- `pa_result` (TEXT) - 타석 결과
- `pa_result_detail` (TEXT) - 타석 결과 상세
- `pa_number` (INTEGER) - 타석 번호
- `stands` (TEXT) - 타석 (좌/우)

#### 상황 정보

- `inning` (INTEGER) - 이닝
- `inning_topbot` (TEXT) - 초/말
- `balls` (INTEGER) - 볼 카운트
- `strikes` (INTEGER) - 스트라이크 카운트
- `outs` (INTEGER) - 아웃 카운트
- `outs_on_play` (INTEGER) - 해당 플레이의 아웃 수

#### 주루 정보

- `on_1b`, `on_2b`, `on_3b` (TEXT) - 각 루 주자 이름
- `on_1b_id`, `on_2b_id`, `on_3b_id` (TEXT) - 각 루 주자 ID

#### 수비 위치

- `pos_1` ~ `pos_9` (TEXT) - 각 포지션 선수 이름
- `pos_1_id` ~ `pos_9_id` (TEXT) - 각 포지션 선수 ID

#### 득점 정보

- `runs_scored` (INTEGER) - 해당 플레이 득점
- `score_home` (INTEGER) - 홈팀 누적 점수
- `score_away` (INTEGER) - 원정팀 누적 점수

#### 트래킹 데이터 (PITCHf/x)

- `px`, `pz` (REAL) - 투구 위치 좌표
- `pfx_x`, `pfx_z` (REAL) - 투구 변화량
- `vx0`, `vy0`, `vz0` (REAL) - 초기 속도 벡터
- `ax`, `ay`, `az` (REAL) - 가속도 벡터
- `sz_top`, `sz_bot` (REAL) - 스트라이크존 상단/하단

#### 기타

- `description` (TEXT) - 플레이 설명
- `referee` (TEXT) - 심판
- `pitchID` (TEXT) - 투구 고유 ID

**2025 시즌 현황**: **약 667,000개 플레이**

---

### 5. `game_team_stats` - 경기별 팀 통계

**용도**: 경기별 팀 집계 통계

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| stat_id | INTEGER (PK) | 고유 ID |
| game_id | TEXT (FK) | 경기 ID |
| team_id | TEXT (FK) | 팀 ID |
| runs | INTEGER | 득점 |
| hits | INTEGER | 안타 |
| errors | INTEGER | 실책 |
| left_on_base | INTEGER | 잔루 |
| doubles | INTEGER | 2루타 |
| triples | INTEGER | 3루타 |
| home_runs | INTEGER | 홈런 |
| walks | INTEGER | 볼넷 |
| strikeouts | INTEGER | 삼진 |
| stolen_bases | INTEGER | 도루 |

**제약 조건**: UNIQUE(game_id, team_id)

---

### 6. `batter_stats_temp` - PBP 계산 타자 통계

**용도**: play_by_play 데이터로부터 계산된 타자 통계

**주요 컬럼**:

- 타율, 출루율, 장타율, OPS
- 안타, 홈런, 타점, 득점
- 볼넷, 삼진 등

---

### 7. `pitcher_stats_temp` - PBP 계산 투수 통계

**용도**: play_by_play 데이터로부터 계산된 투수 통계

**주요 컬럼**:

- 평균자책점, 승, 패, 세이브
- 이닝, 피안타, 탈삼진
- WHIP 등

---

### 8. `kbo_official_batter_stats` - KBO 공식 타자 통계

**용도**: KBO 공식 홈페이지에서 수집한 타자 통계

**복합 기본키**: (player_id, season)

**주요 컬럼**:

- player_id, player_name, team_name, season
- games, at_bats, runs, hits, doubles, triples, home_runs
- rbis, stolen_bases, caught_stealing
- walks, strikeouts, batting_avg, on_base_pct, slugging_pct, ops
- **strikeout_per_pa (K%)**, **base_on_balls_per_pa (BB%)** [신규]
- created_at

**특징**:

- UPSERT 방식으로 데이터 갱신
- 동일 선수의 여러 시즌 데이터 저장 가능

---

### 9. `kbo_official_pitcher_stats` - KBO 공식 투수 통계

**용도**: KBO 공식 홈페이지에서 수집한 투수 통계

**복합 기본키**: (player_id, season)

**주요 컬럼**:

- player_id, player_name, team_name, season
- games, wins, losses, saves, holds
- innings_pitched, hits_allowed, runs_allowed, earned_runs
- walks, strikeouts, home_runs_allowed
- era, whip, k_per_9, bb_per_9
- **strikeout_per_pa (K%)**, **base_on_balls_per_pa (BB%)**, **BABIP** [신규]
- created_at

**특징**:

- UPSERT 방식으로 데이터 갱신
- 동일 선수의 여러 시즌 데이터 저장 가능

---

## 🔍 인덱스

성능 최적화를 위한 인덱스:

- `idx_games_date` - games(game_date)
- `idx_games_season` - games(season)
- `idx_games_home_team` - games(home_team_id)
- `idx_games_away_team` - games(away_team_id)
- `idx_pbp_game` - play_by_play(gameID)
- `idx_pbp_batter` - play_by_play(batter_ID)
- `idx_pbp_pitcher` - play_by_play(pitcher_ID)
- `idx_players_team` - players(team_id)
- `idx_game_stats_team` - game_team_stats(team_id)

---

## 📊 2025 시즌 데이터 현황

### 수집 완료 데이터

✅ **정규시즌 전체 경기 데이터 수집 완료**

#### CSV 파일

- **개별 파일**: `crawler/save/2025/` (720개 파일)
- **병합 파일**: `crawler/save/kbo_2025_regular_season.csv` (100.2 MB)

#### 데이터베이스

- **경기 수**: 719개 (games 테이블)
- **플레이 수**: 229,667개 (play_by_play 테이블)
- **타자 통계**: 398명 (2025 시즌 공식 통계)
- **투수 통계**: 281명 (2025 시즌 공식 통계)

---

## 🛠️ DB 관리 스크립트

### 초기화 및 스키마

```bash
# DB 초기화 (스키마 생성)
python database/init_db.py
```

### 데이터 삽입

```bash
# 2025 시즌 CSV 파일 일괄 삽입
python csv_to_db_2025.py

# 개별 CSV 파일 병합
python data_collection/merge_csv.py
```

### 데이터 확인

```bash
# 2025 시즌 DB 상태 확인
python check_db_2025.py

# 전체 DB 검증
python verify_db.py

# KBO 공식 통계 확인
python check_kbo_stats.py

# 투수 통계 확인
python check_pitcher_db.py
```

---

## 📈 데이터 흐름

```
KBO 웹사이트
    ↓
[크롤링] crawler/pbp.py
    ↓
개별 CSV 파일 (crawler/save/2025/*.csv)
    ↓
[병합] data_collection/merge_csv.py
    ↓
통합 CSV 파일 (kbo_2025_regular_season.csv)
    ↓
[DB 삽입] csv_to_db_2025.py
    ↓
SQLite DB (database/kbo_stats.db)
    ↓
[대시보드] dashboard/
```

---

## 🔄 데이터 업데이트 프로세스

### 일일 업데이트 (자동화)

1. **Play-by-Play 데이터**
   - 크롤러 실행 → CSV 생성 → DB 삽입
   - 스케줄: 매일 새벽 1:30 (AWS EC2 cron)

2. **KBO 공식 통계**
   - Selenium 크롤링 → CSV 저장 → DB UPSERT
   - 타자 + 투수 통계 동시 수집
   - 이메일 알림 발송

### 수동 업데이트

```bash
# 전체 파이프라인 실행
python data_collection/full_pipeline.py

# 개별 실행
python data_collection/selenium_batter_scraper.py
python data_collection/kbo_to_db.py
python data_collection/selenium_pitcher_scraper.py
python data_collection/pitcher_to_db.py
```

---

## 📝 주의사항

1. **백업**: 중요한 작업 전 DB 백업 권장

   ```bash
   copy database\kbo_stats.db database\kbo_stats.db.backup
   ```

2. **인코딩**: CSV 파일은 CP949 인코딩 사용
   - 병합 파일은 UTF-8-SIG로 저장

3. **복합 기본키**:
   - `kbo_official_batter_stats`: (player_id, season)
   - `kbo_official_pitcher_stats`: (player_id, season)
   - 동일 선수의 여러 시즌 데이터 관리 가능

4. **UPSERT 방식**:
   - 기존 데이터는 업데이트
   - 신규 데이터는 삽입
   - 데이터 중복 방지

---

**문서 버전**: v1.1  
**작성일**: 2026-01-18 (K%, BB%, BABIP 지표 구조 추가)  
**작성자**: 김승곤
