# 🔍 AWS EC2 크롤링 및 메일 전송 상태 확인 가이드

**작성일:** 2026-01-15  
**목적:** AWS EC2 인스턴스의 크롤링 실행 여부 및 메일 미수신 원인 파악

---

## 📋 현재 상황 요약

- ✅ AWS EC2에 프로젝트 등록 완료
- ❓ 크롤링이 정상적으로 실행되고 있는지 확인 필요
- ❓ 예약된 메일이 오지 않은 이유 파악 필요

---

## 🚀 빠른 시작 (3단계)

### 1️⃣ EC2 IP 주소 확인

**방법 A: AWS 콘솔에서 확인**

1. [AWS EC2 콘솔](https://console.aws.amazon.com/ec2/home#Instances:) 접속
2. 로그인 (루트 사용자)
3. `kbo-stats-server` 인스턴스 클릭
4. **퍼블릭 IPv4 주소** 복사 (예: `43.200.4.183`)

**방법 B: 이전에 저장한 IP 사용**

- 이전 대화에서 사용했던 IP 주소가 있다면 그대로 사용 가능
- 단, EC2 인스턴스를 재시작한 경우 IP가 변경될 수 있음

---

### 2️⃣ 상태 확인 스크립트 실행

**PowerShell에서 실행:**

```powershell
# 프로젝트 폴더로 이동
cd C:\Users\김승곤\Desktop\b_project

# 상태 확인 스크립트 실행 (IP 주소 입력)
.\check_aws_status.ps1 [EC2_IP주소]
```

**예시:**

```powershell
.\check_aws_status.ps1 43.200.4.183
```

**이 스크립트가 자동으로 확인하는 항목:**

- ✅ Crontab 설정
- ✅ 최근 로그 파일 목록
- ✅ Cron 실행 로그
- ✅ 오늘 크롤러 로그
- ✅ 데이터베이스 파일 정보
- ✅ 이메일 설정 확인
- ✅ Cron 서비스 상태
- ✅ 디스크 공간

---

### 3️⃣ 결과 분석

스크립트 실행 후 출력된 정보를 바탕으로 문제를 파악합니다.

---

## 🔍 상세 진단 가이드

### 시나리오 A: "오늘 크롤러 로그 없음" 메시지가 나타나는 경우

**원인:**

- Cron 작업이 실행되지 않았음
- 또는 아직 실행 시간(새벽 2시)이 되지 않았음

**확인 사항:**

1. **현재 서버 시간 확인**

   ```bash
   ssh -i ~/.ssh/kbo-key.pem ubuntu@[EC2_IP]
   date
   ```

   - 서버 시간이 한국 시간(KST)인지 확인
   - 아직 새벽 2시가 되지 않았다면 정상

2. **Crontab 설정 확인**

   ```bash
   crontab -l
   ```

   - `0 2 * * *`로 시작하는 줄이 있는지 확인
   - 없다면 Crontab 재설정 필요

3. **Cron 서비스 상태 확인**

   ```bash
   sudo systemctl status cron
   ```

   - `active (running)` 상태인지 확인
   - 아니면 재시작: `sudo systemctl restart cron`

**해결 방법:**

→ **[TROUBLESHOOTING_CHECKLIST.md](./TROUBLESHOOTING_CHECKLIST.md)** 의 "문제 A" 참고

---

### 시나리오 B: 크롤링은 성공했지만 메일이 오지 않는 경우

**원인:**

- 이메일 설정 오류
- Gmail 앱 비밀번호 문제
- 이메일 발송 명령어가 Crontab에 없음

**확인 사항:**

1. **Crontab에 이메일 알림 명령어가 있는지 확인**

   ```bash
   crontab -l | grep email_notifier
   ```

   - `email_notifier.py --success` 부분이 있어야 함
   - 없다면 Crontab 재설정 필요

2. **이메일 설정 파일 확인**

   ```bash
   cat ~/b_project/config/email_config.json
   ```

   - `sender_email`, `sender_password`, `receiver_email` 확인
   - 비밀번호가 16자리 앱 비밀번호인지 확인

3. **수동 이메일 테스트**

   ```bash
   cd ~/b_project
   source venv/bin/activate
   python data_collection/email_notifier.py --success --batter 450
   ```

   - "✅ 이메일 발송 완료" 메시지 확인
   - 받은편지함 및 스팸함 확인

**해결 방법:**

→ **[TROUBLESHOOTING_CHECKLIST.md](./TROUBLESHOOTING_CHECKLIST.md)** 의 "문제 C" 참고

---

### 시나리오 C: 크롤링 자체가 실패하는 경우

**원인:**

- Chrome/ChromeDriver 버전 불일치
- 메모리 부족
- 네트워크 문제
- KBO 웹사이트 구조 변경

**확인 사항:**

1. **크롤러 로그 확인**

   ```bash
   TODAY=$(date +%Y%m%d)
   tail -n 100 ~/b_project/logs/selenium_batter_${TODAY}.log
   ```

   - 에러 메시지 확인

2. **Chrome 버전 확인**

   ```bash
   google-chrome --version
   ```

3. **수동 크롤링 테스트**

   ```bash
   cd ~/b_project
   source venv/bin/activate
   python data_collection/selenium_batter_scraper.py
   ```

**해결 방법:**

→ **[TROUBLESHOOTING_CHECKLIST.md](./TROUBLESHOOTING_CHECKLIST.md)** 의 "문제 B" 참고

---

## 🚨 긴급 조치: 수동 실행

모든 작업을 수동으로 실행하여 즉시 크롤링 및 메일 발송:

```bash
# 1. SSH 접속
ssh -i ~/.ssh/kbo-key.pem ubuntu@[EC2_IP]

# 2. 프로젝트 폴더로 이동 및 가상환경 활성화
cd ~/b_project
source venv/bin/activate

# 3. 크롤링 실행 (10-15분 소요)
python data_collection/selenium_batter_scraper.py

# 4. DB 저장
python data_collection/kbo_to_db.py

# 5. 데이터 확인
python check_kbo_stats.py

# 6. 이메일 발송
python data_collection/email_notifier.py --success --batter 450 --pitcher 300 --team 10
```

---

## 📊 예상되는 메일 내용

정상적으로 발송되는 이메일:

**제목:**

```
✅ KBO 공식 통계 수집 완료 - 2026-01-15
```

**내용:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 KBO 공식 통계 수집 완료
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 수집 일시: 2026-01-15 02:15:23

📈 수집 결과:
  ⚾ 타자: 450명
  🎯 투수: 300명
  🏆 팀 순위: 10개 팀

💾 저장 위치:
  - DB: database/kbo_stats.db
  - CSV: crawler/save/official_stats/

✅ 모든 데이터가 정상적으로 저장되었습니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KBO Stats Auto Collector
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**수신 이메일:** `wk120481@gmail.com`

---

## 🎯 체크리스트

### 시스템 상태

- [ ] EC2 인스턴스가 **실행 중** 상태인가?
- [ ] SSH 접속이 정상적으로 되는가?
- [ ] 서버 시간이 한국 시간(KST)인가?

### Crontab 설정

- [ ] `crontab -l` 명령어로 스케줄이 확인되는가?
- [ ] 크롤링 명령어가 포함되어 있는가?
- [ ] 이메일 알림 명령어가 포함되어 있는가?
- [ ] 실행 시간이 `0 2 * * *` (매일 새벽 2시)인가?

### 로그 확인

- [ ] 오늘 날짜의 크롤러 로그 파일이 생성되었는가?
- [ ] 로그에 "크롤링 완료" 메시지가 있는가?
- [ ] 에러 메시지가 없는가?

### 이메일 설정

- [ ] `config/email_config.json` 파일이 존재하는가?
- [ ] Gmail 앱 비밀번호가 올바르게 설정되어 있는가?
- [ ] 수동 이메일 테스트가 성공하는가?
- [ ] 받은편지함 및 스팸함을 확인했는가?

### 데이터 확인

- [ ] 데이터베이스 파일이 오늘 날짜로 업데이트되었는가?
- [ ] `check_kbo_stats.py` 실행 시 데이터가 표시되는가?

---

## 📚 관련 문서

| 문서 | 설명 |
|------|------|
| **[AWS_AUTOMATION_GUIDE.md](./AWS_AUTOMATION_GUIDE.md)** | AWS EC2 초기 설정 및 배포 가이드 |
| **[check_aws_logs.md](./check_aws_logs.md)** | 로그 확인 및 문제 해결 가이드 |
| **[aws_instance_check.md](./aws_instance_check.md)** | EC2 인스턴스 상태 확인 가이드 |
| **[TROUBLESHOOTING_CHECKLIST.md](./TROUBLESHOOTING_CHECKLIST.md)** | 상세 문제 해결 체크리스트 (신규) |

---

## 🔧 자주 발생하는 문제

### 1. SSH 접속 실패

**증상:**

```
Permission denied (publickey)
```

**해결:**

```powershell
# 키 파일 권한 재설정
icacls $HOME\.ssh\kbo-key.pem /inheritance:r
icacls $HOME\.ssh\kbo-key.pem /grant:r "$env:USERNAME`:R"
```

---

### 2. EC2 인스턴스가 중지됨

**원인:**

- 수동으로 중지했거나
- AWS 프리 티어 한도 초과

**해결:**

1. AWS 콘솔 접속
2. 인스턴스 선택
3. "인스턴스 상태" → "인스턴스 시작"
4. ⚠️ **주의:** IP 주소가 변경될 수 있음!

---

### 3. 디스크 공간 부족

**확인:**

```bash
df -h
```

**해결:**

```bash
# 오래된 로그 삭제 (30일 이상)
find ~/b_project/logs -name "*.log" -mtime +30 -delete

# 오래된 DB 백업 삭제
find ~/b_project/database -name "*.backup_*" -mtime +30 -delete
```

---

### 4. Gmail 앱 비밀번호 오류

**증상:**

```
❌ 이메일 발송 실패: Authentication failed
```

**해결:**

1. [Google 계정 보안 설정](https://myaccount.google.com/security) 접속
2. "2단계 인증" 활성화 확인
3. "앱 비밀번호" 클릭
4. 새 앱 비밀번호 생성 (16자리)
5. `config/email_config.json` 업데이트

```bash
nano ~/b_project/config/email_config.json
# sender_password를 새 비밀번호로 변경 (공백 제거)
# Ctrl+O → Enter → Ctrl+X
```

---

## 🎉 정상 작동 확인

모든 것이 정상적으로 작동하면:

1. **매일 새벽 2시**에 자동으로 크롤링 실행
2. **크롤링 완료 후** 자동으로 DB 저장
3. **DB 저장 후** 자동으로 이메일 발송
4. **이메일 수신:** `wk120481@gmail.com`

---

## 📞 추가 지원

문제가 계속되면:

1. **로그 파일 전체 확인**

   ```bash
   cat ~/b_project/logs/cron.log
   ```

2. **시스템 로그 확인**

   ```bash
   sudo journalctl -u cron -n 100
   ```

3. **상세 문제 해결 가이드 참고**
   - [TROUBLESHOOTING_CHECKLIST.md](./TROUBLESHOOTING_CHECKLIST.md)

---

**마지막 업데이트:** 2026-01-15  
**작성자:** Antigravity AI  
**문의:** 추가 문제 발생 시 대화를 통해 해결 가능
