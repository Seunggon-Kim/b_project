# KBO Baseball Analytics Project

## 📁 프로젝트 폴더 구조

```
b_project/
├── 📂 crawler/              # 크롤러 스크립트 및 수집 데이터
├── 📂 data_collection/      # 데이터 수집 및 처리 스크립트
├── 📂 database/             # SQLite 데이터베이스 파일
├── 📂 dashboard/            # Streamlit 대시보드
├── 📂 config/               # 설정 파일 (이메일 등)
├── 📂 logs/                 # 로그 파일
├── 📂 .streamlit/           # Streamlit 설정
└── 📄 기타 유틸리티 파일들
```

---

## 📂 폴더별 상세 설명

### 1. `crawler/` 🕷️

**용도**: KBO 경기 데이터 크롤링

**주요 파일**:

- `pbp.py` - Play-by-Play 크롤러 메인
- `download.py` - 데이터 다운로드 로직
- `game_parse.py` - 경기 데이터 파싱
- `misc.py` - 유틸리티 함수
- `save/` - 크롤링된 CSV 파일 저장
  - `2025/` - 2025년 경기별 CSV
  - `official_stats/` - KBO 공식 통계 CSV

**사용 예시**:

```bash
cd crawler
python pbp.py -f 20250101 -t 20251231 -j
```

---

### 2. `data_collection/` 📊

**용도**: 데이터 수집, 변환, 처리

**주요 스크립트**:

- `selenium_batter_scraper.py` ⭐ - 타자 통계 크롤링
- `selenium_pitcher_scraper.py` ⭐ - 투수 통계 크롤링
- `kbo_to_db.py` ⭐ - 타자 DB 저장 (UPSERT 방식)
- `pitcher_to_db.py` ⭐ - 투수 DB 저장 (UPSERT 방식)
- `merge_csv.py` - CSV 파일 병합 (2025 → kbo_2025_regular_season.csv)
- `email_notifier.py` - 이메일 알림
- `csv_to_db.py` - PBP CSV → DB
- `calculate_stats.py` - 선수 통계 계산
- `daily_update.py` - 일일 자동 업데이트
- `full_pipeline.py` - 전체 파이프라인

**상세 문서**: `data_collection/README.md`

---

### 3. `database/` 💾

**용도**: SQLite 데이터베이스 저장

**파일**:

- `kbo_stats.db` - 메인 데이터베이스
- `kbo_stats.db.backup` - 백업 파일
- `init_db.py` - DB 초기화 스크립트
- `schema.sql` - DB 스키마 정의

**테이블**:

- `teams` - 팀 정보 (10개 팀)
- `players` - 선수 정보
- `games` - 경기 정보 (2025 시즌: **719개 경기**)
- `play_by_play` - 타석별 상세 기록 (2025 시즌: **약 667,000개 플레이**)
- `game_team_stats` - 팀 통계
- `batter_stats_temp` - PBP 계산 타자 통계
- `pitcher_stats_temp` - PBP 계산 투수 통계
- `kbo_official_batter_stats` - KBO 공식 타자 통계 (복합 PK: player_id, season)
- `kbo_official_pitcher_stats` - KBO 공식 투수 통계 (복합 PK: player_id, season)

**2025 시즌 데이터 현황**:

- ✅ 정규시즌 전체 경기 데이터 수집 완료
- ✅ 개별 CSV 파일: `crawler/save/2025/` (720개 파일)
- ✅ 병합 CSV 파일: `crawler/save/kbo_2025_regular_season.csv` (100.2 MB)
- ✅ DB 저장 완료: 719개 경기, 667,000개 플레이

---

### 4. `dashboard/` 📈

**용도**: Streamlit 웹 대시보드

**구조**:

```
dashboard/
├── Home.py              # 메인 페이지
└── pages/
    ├── 1_Team_Stats.py       # 팀 통계
    ├── 2_Player_Stats.py     # 선수 통계
    ├── 3_Game_Analysis.py    # 경기 분석
    └── 4_Database_Explorer.py # DB 탐색기
```

**실행**:

```bash
streamlit run dashboard/Home.py
```

**접속**: <http://localhost:8502>

---

### 5. `config/` ⚙️

**용도**: 설정 파일 저장

**파일**:

- `email_config.json` - 이메일 SMTP 설정
- `email_config.json.template` - 설정 템플릿

**⚠️ 주의**: `email_config.json`은 `.gitignore`에 포함 (개인정보 보호)

---

### 6. `logs/` 📝

**용도**: 실행 로그 저장

**로그 파일**:

- `selenium_batter_YYYYMMDD.log` - 크롤링 로그
- `daily_update_YYYYMMDD.log` - 일일 업데이트 로그

---

### 7. `.streamlit/` 🎨

**용도**: Streamlit 앱 설정

**파일**:

- `config.toml` - 테마, 포트 등 설정

---

## 📄 루트 디렉토리 주요 파일

### 📚 문서

- `README.md` - 프로젝트 개요
- `DATABASE_STRUCTURE.md` ⭐ - **데이터베이스 구조 상세 문서**
- `SELENIUM_SETUP_GUIDE.md` - Selenium 설정 가이드
- `PITCHER_CRAWLING_GUIDE.md` ⭐ - **투수 통계 크롤링 가이드**
- `SAMPLE_DATA.md` - 샘플 데이터 설명
- `AWS_AUTOMATION_GUIDE.md` ⭐ - **AWS 24/7 자동화 가이드**
- `WHY_NO_EMAIL.md` 🔧 - **메일 미수신 문제 해결 가이드**
- `check_kbo_stats.py` - KBO 공식 통계 DB 검증 (수집 데이터 확인용)
- `check_pitcher_db.py` - 투수 통계 DB 검증

### 🔧 유틸리티 스크립트

- `reset_and_recrawl.py` - DB 초기화 및 재크롤링
- `verify_db.py` - DB 검증
- `check_db_stats.py` - DB 통계 확인
- `check_db_2025.py` - 2025 시즌 DB 상태 확인
- `compare_csv_db.py` - CSV와 DB 비교
- `show_data.py` - 데이터 조회
- `drop_table.py` - 테이블 삭제
- `csv_to_db_2025.py` ⭐ - 2025 시즌 CSV 파일 일괄 DB 삽입
- `robust_merge.py` - CSV 파일 병합 (구버전)

### 🚀 배치 파일

- `run_crawler.bat` - PBP 크롤러 실행
- `selenium_daily_collector.bat` - 타자 일일 자동 수집
- `selenium_pitcher_collector.bat` ⭐ - 투수 자동 수집 (크롤링 + DB + 이메일)
- `selenium_all_stats_collector.bat` ⭐ - 타자 + 투수 전체 자동 수집

### 📦 설정

- `requirements.txt` - Python 패키지 목록
- `.gitignore` - Git 제외 파일

### 📓 노트북

- `2025_pbp_data.ipynb` - 데이터 분석 Jupyter Notebook

---

## 🎯 주요 워크플로우

### 1️⃣ **초기 설정**

```bash
# 패키지 설치
pip install -r requirements.txt

# DB 초기화
python database/init_db.py

# 이메일 설정
copy config/email_config.json.template config/email_config.json
# email_config.json 편집
```

### 2️⃣ **데이터 수집 (PBP)**

```bash
# 크롤링
cd crawler
python pbp.py -f 20250101 -t 20251231 -j

# DB 저장
cd ../data_collection
python csv_to_db.py ../crawler/save/2025.csv

# 통계 계산
python calculate_stats.py
```

### 3️⃣ **공식 통계 수집**

**타자 통계**:

```bash
# 크롤링
python data_collection/selenium_batter_scraper.py

# DB 저장 (UPSERT)
python data_collection/kbo_to_db.py

# 이메일 알림 (개수 자동 계산)
python data_collection/email_notifier.py --success
```

**투수 통계**:

```bash
# 크롤링
python data_collection/selenium_pitcher_scraper.py

# DB 저장 (UPSERT)
python data_collection/pitcher_to_db.py

# 확인
python check_pitcher_db.py
```

**상세 가이드**: `PITCHER_CRAWLING_GUIDE.md`

### 4️⃣ **대시보드 실행**

```bash
streamlit run dashboard/Home.py
```

---

## 🔄 자동화 옵션

### 1️⃣ Windows 작업 스케줄러 (로컬용)

- **제약:** 컴퓨터가 켜져 있어야 작동함.
- **PBP 일일 업데이트**: 매일 오전 6시
- **공식 통계 수집**: 매일 오후 3시
- **참고:** `SELENIUM_SETUP_GUIDE.md`

### 2️⃣ AWS EC2 (24/7 자동용) ⭐

- **장점:** 컴퓨터를 꺼도 클라우드 서버에서 24시간 수집 및 대시보드 호스팅 가능.
- **스케줄:** 매일 새벽 1시 30분 자동 실행 (Crontab)
- **가이드:** `AWS_AUTOMATION_GUIDE.md` 참고
- **문제 해결:** 메일이 안 오면 `WHY_NO_EMAIL.md` 참고

---

## 📊 데이터 흐름

```
KBO 웹사이트
    ↓
[크롤러] crawler/pbp.py
    ↓
CSV 파일 (crawler/save/)
    ↓
[변환] data_collection/csv_to_db.py
    ↓
SQLite DB (database/kbo_stats.db)
    ↓
[통계 계산] calculate_stats.py
    ↓
[대시보드] dashboard/
```

---

## 🛠️ 개발 환경

- **Python**: 3.x
- **주요 패키지**: pandas, selenium, streamlit, sqlite3
- **OS**: Windows (배치 파일 사용)
- **브라우저**: Chrome (Selenium)

---

## 📞 문제 해결

### 크롤링 실패

→ `logs/` 폴더의 로그 파일 확인

### DB 오류

→ `verify_db.py` 실행하여 검증

### 대시보드 오류

→ Streamlit 로그 확인 (`streamlit run` 출력)

---

**프로젝트 버전**: v2.3  
**마지막 업데이트**: 2026-01-25  
**주요 변경사항**:

- 투수 통계에 K%, BB%, BABIP, 볼삼비율 추가
- 피출루율, 피장타율, 피OPS 소수점 3자리 표시
- 선수 통계 페이지 UI 개선 (2행 레이아웃)
- 선택된 컬럼 태그 표시 기능 추가
- 팀 통계 페이지 간소화 (순위 테이블만 표시)
- 투수 데이터 캐시 TTL 설정 (5분)
- EC2 자동 크롤링 스케줄 최적화 (매일 오전 2시)

**관리자**: USERNAME
