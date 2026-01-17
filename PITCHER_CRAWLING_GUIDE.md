# KBO 투수 통계 크롤링 가이드

## 📋 개요

KBO 공식 홈페이지에서 투수 통계를 크롤링하여 DB에 저장하는 프로세스입니다.

## 🎯 크롤링 대상

- **URL**: <https://www.koreabaseball.com/Record/Player/PitcherBasic/Basic1.aspx>
- **팀**: LG, HH, SK, SS, NC, KT, LT, HT, OB, WO (10개 팀)
- **페이지**: Basic1, Basic2, Detail1, Detail2 (4개 페이지)

## 📊 수집 데이터

총 52개 컬럼의 투수 통계 데이터:

- **기본 정보**: player_id, player_name, player_team
- **기본 기록**: ERA, G, W, L, SV, HLD, WPCT, IP, H, HR, BB, HBP, SO, R, ER, WHIP
- **세부 기록**: CG, SHO, QS, BSV, TBF, NP, AVG, 2B, 3B, SAC, SF, IBB, WP, BK
- **선발/구원**: GS, Wgs, Wgr, GF, SVO, TS
- **고급 지표**: GDP, GO, AO, GO/AO, BABIP, P/G, P/IP, K/9, BB/9, K/BB, OBP, SLG, OPS

## 🚀 실행 방법

### 1. 크롤링 실행

```bash
py data_collection\selenium_pitcher_scraper.py
```

**결과**:

- CSV 파일 생성: `crawler/save/official_stats/pitcher_stats_2026.csv`
- 로그 파일: `logs/selenium_pitcher_YYYYMMDD_HHMMSS.log`

### 2. DB 저장

```bash
py data_collection\pitcher_to_db.py
```

**결과**:

- DB 테이블: `kbo_official_pitcher_stats`
- 복합 PRIMARY KEY: (player_id, season)
- UPSERT 방식: 기존 데이터는 업데이트, 신규 데이터는 삽입

### 3. 이메일 알림 (선택)

```bash
py data_collection\email_notifier.py --success
```

**결과**:

- 타자 + 투수 통계 개수 자동 계산
- 수집 완료 이메일 발송

### 🚀 한 번에 실행 (권장)

**투수만**:

```bash
.\selenium_pitcher_collector.bat
```

**타자 + 투수 전체**:

```bash
.\selenium_all_stats_collector.bat
```

## 📁 파일 구조

```text
b_project/
├── data_collection/
│   ├── selenium_pitcher_scraper.py    # 투수 크롤러
│   └── pitcher_to_db.py                # DB 저장 스크립트
├── crawler/save/official_stats/
│   └── pitcher_stats_2026.csv          # 크롤링 결과
├── database/
│   └── kbo_stats.db                    # SQLite DB
└── logs/
    └── selenium_pitcher_*.log          # 크롤링 로그
```

## 🔍 데이터 확인

### CSV 확인

```bash
py -c "import pandas as pd; df = pd.read_csv('crawler/save/official_stats/pitcher_stats_2026.csv'); print(f'총 {len(df)}명, {len(df.columns)}개 컬럼'); print(df.head())"
```

### DB 확인

```bash
py -c "import sqlite3; conn = sqlite3.connect('database/kbo_stats.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM kbo_official_pitcher_stats'); print(f'투수 데이터: {cursor.fetchone()[0]}명'); conn.close()"
```

## ⚙️ 스키마 매핑

| KBO 웹사이트 | DB 컬럼명 |
| ----------- | -------- |
| 선수명 | player_name |
| 팀명 | player_team |
| ERA | earned_run_average |
| G | games |
| W | wins |
| L | losses |
| SV | save |
| HLD | hold |
| WPCT | winning_percentage |
| IP | innings_pitched |
| H | hits |
| HR | home_run |
| BB | base_on_balls |
| HBP | hit_by_pitch |
| SO | strikeout |
| R | run |
| ER | earned_run |
| WHIP | walks_plus_hits_per_inning_pitched |
| CG | complete_game |
| SHO | shutout |
| QS | quality_start |
| BSV | blown_save |
| TBF | total_batters_faced |
| NP | number_of_pitchers |
| AVG | batting_average |
| 2B | double |
| 3B | triple |
| SAC | sacrifice_bunts |
| SF | sacrifice_fly |
| IBB | intentional_base_on_balls |
| WP | wild_pitch |
| BK | balk |
| GS | games_started |
| Wgs | wins_game_started |
| Wgr | wins_game_relieved |
| GF | games_finished |
| SVO | save_opportunity |
| TS | total_saves |
| GDP | ground_into_double_play |
| GO | ground_outs |
| AO | air_outs |
| GO/AO | go_ao |
| BABIP | batting_average_on_balls_in_play |
| P/G | p_g |
| P/IP | p_ip |
| K/9 | k_9 |
| BB/9 | bb_9 |
| K/BB | k_bb |
| OBP | on_base_percentage |
| SLG | slugging_percentage |
| OPS | on_base_plus_slugging |

## 📝 주요 특징

1. **팀별 디버그 로그**: 각 팀 크롤링 후 샘플 데이터 3행 출력
2. **페이지네이션 지원**: 2페이지 이상인 경우 자동 처리
3. **player_id 추출**: 선수 링크에서 5자리 player_id 자동 추출
4. **UPSERT 방식**: 기존 데이터 업데이트, 신규 데이터 삽입
5. **타임스탬프 관리**: created_at, updated_at 자동 관리

## ✅ 크롤링 결과 (2026년 기준)

- **총 투수**: 281명
- **총 컬럼**: 52개
- **팀별 분포**:
  - LG: 29명
  - HH: 23명
  - SK: 22명
  - SS: 29명
  - NC: 30명
  - KT: 28명
  - LT: 29명
  - HT: 34명 (2페이지)
  - OB: 28명
  - WO: 29명

## 🔧 문제 해결

### Selenium 설치

```bash
py -m pip install selenium webdriver-manager
```

### 전체 패키지 설치

```bash
py -m pip install -r requirements.txt
```

### DB 초기화 (필요시)

```bash
py -c "import sqlite3; conn = sqlite3.connect('database/kbo_stats.db'); conn.execute('DROP TABLE IF EXISTS kbo_official_pitcher_stats'); conn.close()"
```

## 📌 참고사항

- 크롤링 시간: 약 6-7분 (10개 팀 × 4개 페이지)
- Headless 모드로 실행되어 브라우저 창이 보이지 않음
- 각 페이지 로딩 후 2초 대기 (안정성 확보)
