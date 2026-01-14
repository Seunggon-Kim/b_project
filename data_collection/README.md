# 데이터 수집 스크립트

## 📁 파일 목록 및 용도

### 🎯 **핵심 스크립트**

#### 1. `selenium_batter_scraper.py` ⭐ 최신

**용도**: KBO 공식 타자 통계 크롤링 (페이지네이션 지원)

**기능**:

- 10개 팀 전체 타자 기록 수집
- 기본 기록 + 세부 기록 병합
- 모든 페이지 자동 크롤링
- 새로운 컬럼 스키마 적용

**사용법**:

```bash
python selenium_batter_scraper.py
```

**저장 위치**: `crawler/save/official_stats/batter_stats_2026.csv`

---

#### 2. `kbo_to_db.py` ⭐ 최신

**용도**: 크롤링한 타자 통계를 DB에 저장

**기능**:

- 새로운 스키마로 테이블 생성
- CSV → SQLite 변환
- 중복 데이터 처리

**사용법**:

```bash
python kbo_to_db.py
```

**DB 테이블**: `kbo_official_batter_stats`

---

#### 3. `email_notifier.py`

**용도**: 크롤링 결과 이메일 알림

**기능**:

- 성공/실패 이메일 발송
- Gmail SMTP 사용
- 수집 통계 요약

**사용법**:

```bash
# 성공 알림
python email_notifier.py --success --batter 450

# 실패 알림
python email_notifier.py --fail --error "오류 메시지"
```

**수신**: `your-email@gmail.com`

---

### 📊 **PBP (Play-by-Play) 관련**

#### 4. `csv_to_db.py`

**용도**: PBP CSV 파일을 DB로 변환

**사용법**:

```bash
python csv_to_db.py ../crawler/save/2025.csv
```

---

#### 5. `csv_to_db_lite.py`

**용도**: 경량화된 CSV → DB 변환

---

#### 6. `calculate_stats.py`

**용도**: PBP 데이터에서 선수 통계 계산

**기능**:

- 타자 통계: 타율, OPS, 장타율 등
- 투수 통계: 방어율, WHIP 등

**사용법**:

```bash
python calculate_stats.py
```

**DB 테이블**: `batter_stats_temp`, `pitcher_stats_temp`

---

### 🔄 **자동화 스크립트**

#### 7. `daily_update.py`

**용도**: 매일 전날 경기 데이터 자동 수집

**기능**:

- 전날 날짜 자동 계산
- 크롤러 실행
- CSV → DB 변환
- 로그 기록

**사용법**:

```bash
python daily_update.py
```

---

#### 8. `full_pipeline.py`

**용도**: 크롤링 → DB 저장 → 통계 계산 전체 파이프라인

**사용법**:

```bash
python full_pipeline.py
```

---

### 🔍 **분석 및 검증**

#### 9. `analyze_games.py`

**용도**: 경기 데이터 분석

---

#### 10. `check_team_counts.py`

**용도**: 팀별 데이터 개수 확인

---

#### 11. `find_missing_games.py`

**용도**: 누락된 경기 찾기

---

### 🗂️ **기타 유틸리티**

#### 12. `merge_csv.py`

**용도**: 여러 CSV 파일 병합

---

#### 13. `official_stats_scraper.py`

**용도**: KBO 공식 통계 크롤링 (BeautifulSoup)

**⚠️ 제한사항**: JavaScript 렌더링 필요한 페이지는 실패
**→ `selenium_batter_scraper.py` 사용 권장**

---

#### 14. `official_stats_to_db.py`

**용도**: 공식 통계 CSV → DB 저장

---

## 🎯 **권장 워크플로우**

### 📈 KBO 공식 통계 수집 (매일 오후 3시)

```bash
# 1. 타자 통계 크롤링
python selenium_batter_scraper.py

# 2. DB 저장
python kbo_to_db.py

# 3. 이메일 알림
python email_notifier.py --success --batter 450

# 또는 배치 파일 사용
..\selenium_daily_collector.bat
```

### ⚾ PBP 데이터 수집 (시즌 전체)

```bash
# 1. 크롤링
cd ../crawler
python pbp.py -f 20250101 -t 20251231 -j

# 2. DB 저장
cd ../data_collection
python csv_to_db.py ../crawler/save/2025.csv

# 3. 통계 계산
python calculate_stats.py
```

---

## 📋 **설정 파일**

### `config/email_config.json`

이메일 발송 설정 (Gmail SMTP)

```json
{
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "your_email@gmail.com",
    "sender_password": "your_app_password"
}
```

---

## 📝 **로그 파일**

- `logs/selenium_batter_YYYYMMDD.log` - 크롤링 로그
- `logs/daily_update_YYYYMMDD.log` - 일일 업데이트 로그

---

## 🔧 **문제 해결**

### 크롤링 실패

1. Chrome Driver 설치 확인
2. `pip install selenium webdriver-manager`
3. 로그 파일 확인

### DB 저장 실패

1. 테이블 스키마 확인
2. `../drop_table.py` 실행 후 재시도
3. CSV 파일 컬럼명 확인

### 이메일 발송 실패

1. `config/email_config.json` 확인
2. Gmail 앱 비밀번호 재생성
3. 2단계 인증 활성화 확인

---

## 📚 **추가 문서**

- `../SELENIUM_SETUP_GUIDE.md` - Selenium 설정 가이드
- `OFFICIAL_STATS_NOTES.md` - 공식 통계 크롤링 노트

---

**마지막 업데이트**: 2026-01-12  
**버전**: v2.0 (현재 버전)
