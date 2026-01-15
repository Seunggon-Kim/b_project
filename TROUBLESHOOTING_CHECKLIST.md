# AWS EC2 크롤링 & 메일 전송 문제 해결 체크리스트

**작성일:** 2026-01-15  
**목적:** 크롤링 실행 여부 및 메일 미수신 원인 파악

---

## 🎯 빠른 진단 (5분)

### 1️⃣ EC2 인스턴스 상태 확인

```powershell
# PowerShell에서 실행
.\check_aws_status.ps1 [EC2_IP주소]
```

**확인 사항:**

- [ ] EC2 인스턴스가 **실행 중**인가?
- [ ] SSH 접속이 정상적으로 되는가?

---

### 2️⃣ Crontab 설정 확인

SSH 접속 후:

```bash
crontab -l
```

**예상 결과:**

```bash
# KBO 타자 통계 자동 수집 (매일 새벽 2시) + 이메일 알림
0 2 * * * mkdir -p /home/ubuntu/b_project/logs && cd /home/ubuntu/b_project && /home/ubuntu/b_project/venv/bin/python data_collection/selenium_batter_scraper.py && /home/ubuntu/b_project/venv/bin/python data_collection/kbo_to_db.py && /home/ubuntu/b_project/venv/bin/python data_collection/email_notifier.py --success >> /home/ubuntu/b_project/logs/cron.log 2>&1
```

**체크:**

- [ ] Crontab에 크롤링 스케줄이 설정되어 있는가?
- [ ] 이메일 알림 명령어가 포함되어 있는가?
- [ ] 시간이 `0 2 * * *` (매일 새벽 2시)로 설정되어 있는가?

---

### 3️⃣ 최근 실행 로그 확인

```bash
# 오늘 날짜 확인
date

# Cron 로그 확인 (최근 50줄)
tail -n 50 ~/b_project/logs/cron.log

# 오늘 크롤러 로그 확인
TODAY=$(date +%Y%m%d)
ls -lh ~/b_project/logs/selenium_batter_${TODAY}.log
tail -n 50 ~/b_project/logs/selenium_batter_${TODAY}.log
```

**체크:**

- [ ] 오늘 날짜의 로그 파일이 생성되었는가?
- [ ] 크롤링이 성공적으로 완료되었는가? ("크롤링 완료" 메시지 확인)
- [ ] 에러 메시지가 없는가?

---

### 4️⃣ 이메일 설정 확인

```bash
# 이메일 설정 파일 확인
cat ~/b_project/config/email_config.json
```

**체크:**

- [ ] `email_config.json` 파일이 존재하는가?
- [ ] `sender_email`이 올바른 Gmail 주소인가?
- [ ] `sender_password`가 16자리 앱 비밀번호인가?
- [ ] `receiver_email`이 올바른 주소인가?

---

### 5️⃣ 수동 이메일 테스트

```bash
# 가상환경 활성화
cd ~/b_project
source venv/bin/activate

# 테스트 이메일 발송
python data_collection/email_notifier.py --success --batter 450 --pitcher 300 --team 10
```

**예상 결과:**

```
✅ 이메일 발송 완료
```

**체크:**

- [ ] 이메일이 성공적으로 발송되었는가?
- [ ] 받은편지함에 이메일이 도착했는가?
- [ ] 스팸함도 확인했는가?

---

## 🔍 상세 진단 (문제가 있는 경우)

### 문제 A: Cron 작업이 실행되지 않음

**증상:**

- 오늘 날짜의 로그 파일이 없음
- `cron.log`에 오늘 날짜의 기록이 없음

**해결 방법:**

```bash
# Cron 서비스 상태 확인
sudo systemctl status cron

# Cron 서비스 재시작
sudo systemctl restart cron

# Crontab 재확인
crontab -l

# 로그 폴더 권한 확인
ls -ld ~/b_project/logs
mkdir -p ~/b_project/logs
chmod 755 ~/b_project/logs
```

**체크:**

- [ ] Cron 서비스가 실행 중인가?
- [ ] 로그 폴더가 존재하고 쓰기 권한이 있는가?

---

### 문제 B: 크롤링이 실패함

**증상:**

- 로그 파일에 에러 메시지가 있음
- "크롤링 완료" 메시지가 없음

**해결 방법:**

```bash
# Chrome 버전 확인
google-chrome --version

# Python 패키지 확인
cd ~/b_project
source venv/bin/activate
pip list | grep -E "(selenium|webdriver)"

# 수동 크롤링 테스트
python data_collection/selenium_batter_scraper.py
```

**일반적인 에러:**

1. **Chrome/ChromeDriver 버전 불일치**

   ```bash
   pip install --upgrade selenium webdriver-manager
   ```

2. **메모리 부족**

   ```bash
   free -h
   # 스왑 메모리 추가 필요할 수 있음
   ```

3. **네트워크 문제**

   ```bash
   ping -c 3 www.koreabaseball.com
   ```

---

### 문제 C: 이메일 발송 실패

**증상:**

- 크롤링은 성공했지만 이메일이 오지 않음
- 로그에 이메일 관련 에러가 있음

**해결 방법:**

#### C-1. 이메일 설정 파일 확인

```bash
cat ~/b_project/config/email_config.json
```

**올바른 형식:**

```json
{
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "your-email@gmail.com",
    "sender_password": "abcdefghijklmnop",
    "receiver_email": "receiver@gmail.com"
}
```

#### C-2. Gmail 앱 비밀번호 재생성

1. [Google 계정 보안 설정](https://myaccount.google.com/security) 접속
2. "2단계 인증" 활성화 확인
3. "앱 비밀번호" 클릭
4. 새 앱 비밀번호 생성
5. 16자리 비밀번호를 `email_config.json`에 업데이트 (공백 제거)

```bash
nano ~/b_project/config/email_config.json
# sender_password를 새 비밀번호로 변경
# Ctrl+O → Enter → Ctrl+X
```

#### C-3. 이메일 발송 테스트

```bash
python data_collection/email_notifier.py --success --batter 100
```

**체크:**

- [ ] "✅ 이메일 발송 완료" 메시지가 나타나는가?
- [ ] 받은편지함에 이메일이 도착하는가?
- [ ] 스팸함도 확인했는가?

---

### 문제 D: 데이터베이스 업데이트 실패

**증상:**

- 크롤링은 성공했지만 DB가 업데이트되지 않음

**해결 방법:**

```bash
# DB 파일 확인
ls -lh ~/b_project/database/kbo_stats.db

# DB 최종 수정 시간 확인
stat ~/b_project/database/kbo_stats.db | grep Modify

# DB 통계 확인
python check_kbo_stats.py

# 수동 DB 저장
python data_collection/kbo_to_db.py
```

---

## 🚨 긴급 조치: 수동 실행

모든 작업을 수동으로 실행하여 테스트:

```bash
# SSH 접속
ssh -i ~/.ssh/kbo-key.pem ubuntu@[EC2_IP]

# 프로젝트 폴더로 이동
cd ~/b_project
source venv/bin/activate

# 1. 크롤링 실행 (10-15분 소요)
python data_collection/selenium_batter_scraper.py

# 2. DB 저장
python data_collection/kbo_to_db.py

# 3. 데이터 확인
python check_kbo_stats.py

# 4. 이메일 발송
python data_collection/email_notifier.py --success --batter 450 --pitcher 300 --team 10
```

---

## 📊 시간대 확인

**중요:** Cron은 서버의 시간대를 사용합니다!

```bash
# 현재 서버 시간 확인
date

# 시간대 확인
timedatectl

# 한국 시간대로 설정 (필요시)
sudo timedatectl set-timezone Asia/Seoul
```

**체크:**

- [ ] 서버 시간이 한국 시간(KST)인가?
- [ ] Crontab의 `0 2 * * *`는 서버 시간 기준 새벽 2시인가?

---

## 🔄 Crontab 재설정 (필요시)

```bash
# Crontab 편집
crontab -e

# 기존 내용 삭제 후 다시 입력
# 아래 내용을 복사하여 붙여넣기
0 2 * * * mkdir -p /home/ubuntu/b_project/logs && cd /home/ubuntu/b_project && /home/ubuntu/b_project/venv/bin/python data_collection/selenium_batter_scraper.py && /home/ubuntu/b_project/venv/bin/python data_collection/kbo_to_db.py && /home/ubuntu/b_project/venv/bin/python data_collection/email_notifier.py --success >> /home/ubuntu/b_project/logs/cron.log 2>&1

# 저장: Ctrl+O → Enter → Ctrl+X
```

---

## 📧 이메일 알림 내용 확인

정상적으로 발송되는 이메일 예시:

**제목:** `KBO 공식 통계 수집 완료 - 2026-01-15`

**내용:**

```
📊 KBO 공식 통계 수집이 완료되었습니다!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 수집 정보
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🕐 수집 일시: 2026-01-15 02:15:23
📈 타자 통계: 450명
📈 투수 통계: 300명
📈 팀 통계: 10팀

💾 저장 위치:
  - 데이터베이스: ~/b_project/database/kbo_stats.db
  - CSV 파일: ~/b_project/crawler/save/2025.csv

✅ 상태: 정상 완료
```

---

## 🎯 최종 체크리스트

### 시스템 상태

- [ ] EC2 인스턴스 실행 중
- [ ] SSH 접속 가능
- [ ] Cron 서비스 실행 중
- [ ] 디스크 공간 충분 (`df -h`)

### 크롤링 설정

- [ ] Crontab 설정 완료
- [ ] 로그 폴더 존재 및 권한 확인
- [ ] Python 가상환경 정상
- [ ] Chrome/ChromeDriver 정상

### 이메일 설정

- [ ] `email_config.json` 파일 존재
- [ ] Gmail 앱 비밀번호 설정
- [ ] 수동 이메일 테스트 성공
- [ ] 스팸함 확인

### 실행 확인

- [ ] 오늘 날짜의 로그 파일 생성
- [ ] 크롤링 성공 메시지 확인
- [ ] DB 업데이트 확인
- [ ] 이메일 수신 확인

---

## 📞 추가 도움

### 로그 파일 위치

```bash
# Cron 실행 로그
~/b_project/logs/cron.log

# 크롤러 로그 (날짜별)
~/b_project/logs/selenium_batter_YYYYMMDD.log

# Streamlit 로그 (대시보드 실행 시)
~/b_project/logs/streamlit.log
```

### 시스템 로그 확인

```bash
# Cron 시스템 로그
sudo journalctl -u cron -n 100

# 시스템 전체 로그
sudo journalctl -xe
```

---

## 🎉 문제 해결 완료 후

1. **자동화 재확인**

   ```bash
   crontab -l
   ```

2. **다음 실행 대기**
   - 내일 새벽 2시에 자동 실행됨
   - 이메일 수신 확인

3. **실시간 모니터링 (선택)**

   ```bash
   # 로그 실시간 확인
   tail -f ~/b_project/logs/cron.log
   ```

---

**마지막 업데이트:** 2026-01-15  
**작성자:** Antigravity AI  
**목적:** AWS EC2 크롤링 및 메일 전송 문제 해결
