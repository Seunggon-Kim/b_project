# KBO 공식 통계 자동 수집 시스템 설정 가이드

## 📋 개요

매일 오후 3시에 KBO 공식 타자 통계를 자동으로 수집하고 이메일로 알림을 받는 시스템입니다.

---

## 🚀 설정 단계

### 1️⃣ Chrome Driver 설치

Selenium이 Chrome을 제어하려면 ChromeDriver가 필요합니다.

**방법 A: 자동 설치 (권장)**

```bash
pip install webdriver-manager
```

**방법 B: 수동 설치**

1. Chrome 버전 확인: `chrome://version/`
2. [ChromeDriver 다운로드](https://chromedriver.chromium.org/downloads)
3. `C:\Windows\System32\` 또는 프로젝트 폴더에 저장

---

### 2️⃣ 필요한 패키지 설치

```bash
pip install selenium pandas
```

---

### 3️⃣ 이메일 설정

#### Gmail 앱 비밀번호 생성

1. **Google 계정 설정** 이동
   - <https://myaccount.google.com/>

2. **보안** 탭 클릭

3. **2단계 인증** 활성화 (필수)

4. **앱 비밀번호** 생성
   - 앱 선택: 메일
   - 기기 선택: Windows 컴퓨터
   - **16자리 비밀번호 생성됨** (예: `abcd efgh ijkl mnop`)

5. **설정 파일 생성**

   ```bash
   # config/email_config.json.template을 복사
   copy config\email_config.json.template config\email_config.json
   ```

6. **email_config.json 편집**

   ```json
   {
       "smtp_server": "smtp.gmail.com",
       "smtp_port": 587,
       "sender_email": "your_email@gmail.com",
       "sender_password": "abcd efgh ijkl mnop"
   }
   ```

   - `sender_email`: 본인 Gmail 주소
   - `sender_password`: 위에서 생성한 16자리 앱 비밀번호

---

### 4️⃣ 테스트 실행

```bash
# 크롤링 테스트
python data_collection\selenium_batter_scraper.py

# DB 저장 테스트
python data_collection\kbo_to_db.py

# 이메일 테스트
python data_collection\email_notifier.py --success --batter 450
```

---

### 5️⃣ Windows 작업 스케줄러 설정

#### 작업 스케줄러 열기

```
Win + R → taskschd.msc
```

#### 새 작업 만들기

**일반 탭:**

- 이름: `KBO 타자 통계 수집`
- 설명: `매일 오후 3시 KBO 공식 타자 통계 자동 수집`
- ✅ 사용자가 로그온할 때만 실행
- ✅ 가장 높은 수준의 권한으로 실행

**트리거 탭:**

- 새로 만들기 클릭
- 작업 시작: 일정에 따라
- 설정: 매일
- 시작: 오후 3:00:00
- ✅ 사용

**동작 탭:**

- 새로 만들기 클릭
- 동작: 프로그램 시작
- 프로그램/스크립트: `C:\Users\김승곤\Desktop\b_project\selenium_daily_collector.bat`
- 시작 위치: `C:\Users\김승곤\Desktop\b_project`

**조건 탭:**

- ❌ 컴퓨터의 AC 전원이 켜져 있을 때만 작업 시작 (체크 해제)
- ✅ 작업을 실행하기 위해 절전 모드 종료

**설정 탭:**

- ✅ 요청 시 작업 실행 허용
- ✅ 실행 실패 시 다시 시작 간격: 10분
- 다시 시도 횟수: 3회

---

## 📊 작동 방식

```
[매일 오후 3시]
    ↓
selenium_daily_collector.bat 실행
    ↓
1. Selenium 크롤링 (10개 팀)
    ↓
2. CSV 저장
    ↓
3. DB 저장
    ↓
4. 이메일 발송 (wk120481@gmail.com)
    ↓
완료
```

---

## 📁 파일 구조

```
b_project/
├── data_collection/
│   ├── selenium_batter_scraper.py   # Selenium 크롤러
│   ├── kbo_to_db.py                 # DB 저장
│   └── email_notifier.py            # 이메일 알림
├── config/
│   ├── email_config.json.template   # 템플릿
│   └── email_config.json            # 실제 설정 (직접 생성)
├── crawler/save/official_stats/
│   └── batter_stats_2025.csv        # 크롤링 결과
├── database/
│   └── kbo_stats.db                 # DB
├── logs/
│   └── selenium_batter_YYYYMMDD.log # 로그
└── selenium_daily_collector.bat     # 자동화 배치
```

---

## 🔍 문제 해결

### 크롤링 실패 시

1. 로그 파일 확인: `logs/selenium_batter_YYYYMMDD.log`
2. Chrome Driver 버전 확인
3. KBO 웹사이트 접속 가능 여부 확인

### 이메일 발송 실패 시

1. `config/email_config.json` 확인
2. Gmail 앱 비밀번호 재생성
3. 2단계 인증 활성화 확인

### 작업 스케줄러 실행 안 됨

1. 작업 스케줄러 → 작업 기록 확인
2. 배치 파일 경로 확인
3. 수동 실행 테스트: `selenium_daily_collector.bat`

---

## ✅ 완료 체크리스트

- [ ] Chrome Driver 설치
- [ ] 필요한 패키지 설치 (`selenium`, `pandas`)
- [ ] Gmail 앱 비밀번호 생성
- [ ] `config/email_config.json` 파일 생성 및 설정
- [ ] 크롤링 테스트 성공
- [ ] DB 저장 테스트 성공
- [ ] 이메일 발송 테스트 성공
- [ ] Windows 작업 스케줄러 등록
- [ ] 작업 스케줄러 수동 실행 테스트

---

## 📧 이메일 예시

### 성공 시

```
제목: ✅ KBO 공식 통계 수집 완료 - 2026-01-11

📊 KBO 공식 통계 수집 완료
📅 수집 일시: 2026-01-11 15:00:23
⚾ 타자: 450명
💾 DB 저장 완료
```

### 실패 시

```
제목: ❌ KBO 통계 수집 실패 - 2026-01-11

⚠️ KBO 공식 통계 수집 실패
📅 시도 일시: 2026-01-11 15:00:23
❌ 오류: Selenium 크롤링 실패
📋 로그 파일 확인 필요
```

---

## 🎯 다음 단계

1. 투수 통계 크롤러 추가
2. 팀 순위 크롤러 추가
3. 대시보드 페이지 생성
4. PBP 데이터와 비교 기능 추가

---

**문의사항이 있으면 로그 파일을 확인하거나 수동으로 스크립트를 실행해보세요!** 🚀
