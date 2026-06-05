# 📧 KBO 통계 이메일 알림 가이드

## 📋 개요

KBO 공식 통계 수집 완료 후 자동으로 이메일 알림을 발송하는 시스템입니다.

## ✨ 주요 기능

1. **자동 개수 계산**: 타자 및 투수 CSV 파일에서 자동으로 선수 수 계산
2. **성공/실패 알림**: 수집 성공 시 상세 결과, 실패 시 오류 내용 발송
3. **통합 알림**: 타자 + 투수 통계를 한 번에 알림

## 📊 이메일 내용 예시

### 성공 알림

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 KBO 공식 통계 수집 완료
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 수집 일시: 2026-01-18 03:00:15

📈 수집 결과:
  ⚾ 타자: 398명
  🎯 투수: 281명
  🏆 팀 순위: 10개 팀

💾 저장 위치:
  - DB: database/kbo_stats.db
  - CSV: crawler/save/official_stats/

✅ 모든 데이터가 정상적으로 저장되었습니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KBO Stats Auto Collector
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 실패 알림

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ KBO 공식 통계 수집 실패
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 시도 일시: 2026-01-18 03:00:15

❌ 오류 내용:
투수 Selenium 크롤링 실패

📋 로그 파일: logs/selenium_batter_20260118.log

🔧 조치 필요:
  - 로그 파일 확인
  - 수동으로 재실행 권장

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KBO Stats Auto Collector
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## 🚀 사용 방법

### 1. 이메일 설정

`config/email_config.json` 파일 생성:

```json
{
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "your_email@gmail.com",
    "sender_password": "your_app_password"
}
```

**Gmail 앱 비밀번호 생성**:

1. Google 계정 → 보안
2. 2단계 인증 활성화
3. 앱 비밀번호 생성
4. 생성된 16자리 비밀번호를 `sender_password`에 입력

### 2. 수동 실행

**성공 알림 (자동 계산)**:

```bash
py data_collection\email_notifier.py --success
```

**성공 알림 (수동 지정)**:

```bash
py data_collection\email_notifier.py --success --batter 398 --pitcher 281
```

**실패 알림**:

```bash
py data_collection\email_notifier.py --fail --error "크롤링 실패"
```

### 3. 배치 파일 사용 (권장)

**투수만**:

```bash
.\selenium_pitcher_collector.bat
```

- 투수 크롤링 → DB 저장 → 이메일 알림

**타자 + 투수 전체**:

```bash
.\selenium_all_stats_collector.bat
```

- 타자 크롤링 → DB 저장
- 투수 크롤링 → DB 저장
- 이메일 알림 (통합)

## 📝 배치 파일 구조

### selenium_pitcher_collector.bat

```batch
1. 투수 크롤링 (selenium_pitcher_scraper.py)
   ↓ 실패 시 → 실패 이메일 발송 후 종료
2. DB 저장 (pitcher_to_db.py)
   ↓ 실패 시 → 실패 이메일 발송 후 종료
3. 이메일 알림 (email_notifier.py --success)
   ✅ 성공 이메일 발송
```

### selenium_all_stats_collector.bat

```batch
1. 타자 크롤링 (selenium_batter_scraper.py)
   ↓ 실패 시 → 실패 이메일 발송 후 종료
2. 타자 DB 저장 (kbo_to_db.py)
   ↓ 실패 시 → 실패 이메일 발송 후 종료
3. 투수 크롤링 (selenium_pitcher_scraper.py)
   ↓ 실패 시 → 실패 이메일 발송 후 종료
4. 투수 DB 저장 (pitcher_to_db.py)
   ↓ 실패 시 → 실패 이메일 발송 후 종료
5. 이메일 알림 (email_notifier.py --success)
   ✅ 성공 이메일 발송 (타자 + 투수 통합)
```

## 🔍 자동 개수 계산 로직

```python
# 타자 CSV 파일 자동 탐색
batter_files = glob.glob('crawler/save/official_stats/batter_stats_*.csv')
latest_batter = max(batter_files, key=os.path.getmtime)
batter_count = len(pd.read_csv(latest_batter))

# 투수 CSV 파일 자동 탐색
pitcher_files = glob.glob('crawler/save/official_stats/pitcher_stats_*.csv')
latest_pitcher = max(pitcher_files, key=os.path.getmtime)
pitcher_count = len(pd.read_csv(latest_pitcher))
```

## 📧 수신자 설정

현재 수신자: `wk120481@gmail.com` (고정)

변경하려면 `data_collection/email_notifier.py` 파일의 33번째 줄 수정:

```python
RECIPIENT_EMAIL = "your_email@gmail.com"
```

## 🔧 문제 해결

### 이메일 발송 실패

**원인 1**: Gmail 앱 비밀번호 오류

- 해결: 앱 비밀번호 재생성 후 `email_config.json` 업데이트

**원인 2**: 2단계 인증 미활성화

- 해결: Google 계정에서 2단계 인증 활성화

**원인 3**: SMTP 서버 연결 실패

- 해결: 방화벽 설정 확인, 포트 587 허용

### 개수 계산 오류

**원인**: CSV 파일 없음

- 해결: 크롤링 먼저 실행 후 이메일 발송

## 📌 참고사항

- 이메일은 UTF-8 인코딩으로 발송됩니다
- Gmail 앱 비밀번호는 16자리입니다 (공백 없이 입력)
- 배치 파일은 각 단계 실패 시 즉시 실패 이메일을 발송합니다
- 성공 이메일은 모든 단계 완료 후 1회만 발송됩니다

## 🎯 Windows 작업 스케줄러 설정

매일 자동으로 실행하려면:

1. 작업 스케줄러 열기
2. 기본 작업 만들기
3. 트리거: 매일 오후 3시
4. 동작: `selenium_all_stats_collector.bat` 실행
5. 완료

**결과**: 매일 오후 3시에 타자 + 투수 통계 수집 후 이메일 발송

## ✅ 테스트

이메일 설정이 올바른지 테스트:

```bash
py data_collection\email_notifier.py --success
```

정상 작동 시 몇 초 내에 이메일 수신됩니다.
