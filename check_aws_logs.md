# AWS EC2 크롤링 및 메일 발송 확인 가이드

오늘 아침에 메일이 오지 않았을 때 확인해야 할 사항들입니다.

---

## 🔍 1단계: AWS EC2 인스턴스 상태 확인

### AWS 콘솔에서 확인

1. **AWS 콘솔 접속**
   - <https://aws.amazon.com/ko/> 접속
   - 로그인 (루트 사용자)

2. **EC2 대시보드 이동**
   - 상단 검색창에 "EC2" 입력
   - EC2 클릭

3. **인스턴스 상태 확인**
   - 좌측 메뉴 "인스턴스" 클릭
   - `kbo-stats-server` 인스턴스 찾기
   - **상태 확인:**
     - ✅ **실행 중** → 정상
     - ⚠️ **중지됨** → 인스턴스가 꺼져 있음 (크롤링 불가)
     - ❌ **종료됨** → 인스턴스가 삭제됨

4. **퍼블릭 IP 확인**
   - 인스턴스 클릭
   - "퍼블릭 IPv4 주소" 복사 (예: 43.200.4.183)

---

## 🔑 2단계: SSH 접속 준비

### Windows PowerShell에서 실행

```powershell
# SSH 키 파일 위치 확인
Test-Path $HOME\.ssh\kbo-key.pem
```

**결과:**

- `True` → 키 파일 존재 ✅
- `False` → 키 파일 없음 ❌ (다운로드 폴더에서 찾아야 함)

### 키 파일이 없는 경우

```powershell
# 다운로드 폴더에서 찾기
Get-ChildItem $HOME\Downloads\kbo-key.pem

# 있으면 .ssh 폴더로 이동
Move-Item $HOME\Downloads\kbo-key.pem $HOME\.ssh\

# 권한 설정
icacls $HOME\.ssh\kbo-key.pem /inheritance:r
icacls $HOME\.ssh\kbo-key.pem /grant:r "$env:USERNAME`:R"
```

---

## 🖥️ 3단계: SSH 접속

```powershell
# [퍼블릭_IP]를 실제 IP로 변경
ssh -i $HOME\.ssh\kbo-key.pem ubuntu@[퍼블릭_IP]
```

**예시:**

```powershell
ssh -i $HOME\.ssh\kbo-key.pem ubuntu@43.200.4.183
```

처음 접속 시 `Are you sure you want to continue connecting?` → `yes` 입력

---

## 📋 4단계: 크롤링 로그 확인

SSH 접속 후 실행:

### 4-1. Crontab 설정 확인

```bash
# Crontab 목록 확인
crontab -l
```

**확인 사항:**

- 크롤링 스케줄이 설정되어 있는지 확인
- 예상 결과: `0 2 * * *` (매일 새벽 2시 실행)

### 4-2. Cron 로그 확인

```bash
# 최근 로그 확인 (마지막 50줄)
tail -n 50 ~/b_project/logs/cron.log
```

**확인 사항:**

- 오늘 날짜의 로그가 있는지 확인
- 에러 메시지가 있는지 확인

### 4-3. 크롤러 로그 확인

```bash
# 오늘 날짜의 크롤러 로그 확인
TODAY=$(date +%Y%m%d)
tail -n 100 ~/b_project/logs/selenium_batter_${TODAY}.log
```

**확인 사항:**

- "크롤링 완료" 메시지가 있는지 확인
- 에러 메시지가 있는지 확인

### 4-4. 최근 로그 파일 목록

```bash
# 최근 7일간의 로그 파일 확인
ls -lht ~/b_project/logs/*.log | head -10
```

**확인 사항:**

- 오늘 날짜의 로그 파일이 생성되었는지 확인
- 파일 크기가 0이 아닌지 확인

---

## 📧 5단계: 이메일 발송 확인

### 5-1. 이메일 설정 확인

```bash
# 이메일 설정 파일 확인
cat ~/b_project/config/email_config.json
```

**확인 사항:**

- `sender_email`: Gmail 주소가 올바른지 확인
- `sender_password`: 앱 비밀번호가 설정되어 있는지 확인

### 5-2. 수동 이메일 테스트

```bash
# 가상환경 활성화
cd ~/b_project
source venv/bin/activate

# 성공 이메일 테스트
python data_collection/email_notifier.py --success --batter 450 --pitcher 300 --team 10
```

**확인 사항:**

- "✅ 이메일 발송 완료" 메시지가 나타나는지 확인
- 실제로 이메일이 도착하는지 확인 (<wk120481@gmail.com>)

---

## 🔍 6단계: 데이터베이스 확인

### 6-1. 최근 데이터 확인

```bash
# DB 통계 확인
python check_kbo_stats.py
```

**확인 사항:**

- 타자, 투수 데이터가 있는지 확인
- 최근 업데이트 날짜 확인

### 6-2. DB 파일 확인

```bash
# DB 파일 정보
ls -lh ~/b_project/database/kbo_stats.db

# DB 파일 최종 수정 시간
stat ~/b_project/database/kbo_stats.db | grep Modify
```

**확인 사항:**

- 오늘 날짜로 수정되었는지 확인

---

## 🛠️ 7단계: 문제 해결

### 문제 1: Cron 작업이 실행되지 않음

```bash
# Cron 서비스 상태 확인
sudo systemctl status cron

# Cron 서비스 재시작
sudo systemctl restart cron

# Crontab 재설정
crontab -e
```

### 문제 2: 크롤링 실패

```bash
# Chrome 버전 확인
google-chrome --version

# ChromeDriver 확인
which chromedriver

# 수동 크롤링 테스트
cd ~/b_project
source venv/bin/activate
python data_collection/selenium_batter_scraper.py
```

### 문제 3: 이메일 발송 실패

```bash
# 이메일 설정 재확인
cat ~/b_project/config/email_config.json

# 수동 이메일 테스트
python data_collection/email_notifier.py --success --batter 100
```

### 문제 4: 디스크 공간 부족

```bash
# 디스크 공간 확인
df -h

# 큰 파일 찾기
du -sh ~/b_project/* | sort -h

# 오래된 로그 삭제 (30일 이상)
find ~/b_project/logs -name "*.log" -mtime +30 -delete
```

---

## 📊 8단계: 실시간 모니터링

### Cron 로그 실시간 확인

```bash
# 로그 실시간 모니터링 (Ctrl+C로 종료)
tail -f ~/b_project/logs/cron.log
```

### 크롤러 실행 중 로그 확인

```bash
# 오늘 날짜의 크롤러 로그 실시간 확인
TODAY=$(date +%Y%m%d)
tail -f ~/b_project/logs/selenium_batter_${TODAY}.log
```

---

## 🎯 체크리스트

오늘 메일이 오지 않은 이유를 찾기 위한 체크리스트:

- [ ] EC2 인스턴스가 실행 중인가?
- [ ] Crontab이 설정되어 있는가?
- [ ] Cron 서비스가 실행 중인가?
- [ ] 오늘 날짜의 크롤러 로그가 생성되었는가?
- [ ] 크롤링이 성공적으로 완료되었는가?
- [ ] 이메일 설정이 올바른가?
- [ ] 이메일 발송이 성공했는가?
- [ ] 데이터베이스가 업데이트되었는가?

---

## 🚨 긴급 조치

### 수동 크롤링 및 메일 발송

```bash
# SSH 접속 후
cd ~/b_project
source venv/bin/activate

# 1. 크롤링 실행
python data_collection/selenium_batter_scraper.py

# 2. DB 저장
python data_collection/kbo_to_db.py

# 3. 이메일 발송
python data_collection/email_notifier.py --success --batter 450 --pitcher 300 --team 10
```

---

## 📞 추가 도움

문제가 계속되면:

1. **로그 파일 전체 확인**

   ```bash
   cat ~/b_project/logs/cron.log
   ```

2. **시스템 로그 확인**

   ```bash
   sudo journalctl -u cron -n 50
   ```

3. **AWS CloudWatch 로그 확인** (AWS 콘솔에서)

---

**작성일:** 2026-01-15
**목적:** 오늘 아침 메일이 오지 않은 원인 파악 및 해결
