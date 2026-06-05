# 📧 메일이 안 온 이유 확인하기 (가장 간단한 방법)

**작성일:** 2026-01-15 12:50  
**목적:** 메일 미수신 원인을 빠르게 파악하기

---

## 🎯 가장 빠른 확인 방법 (5분)

### ✅ 1단계: EC2 인스턴스가 실행 중인지 확인

1. **브라우저에서 AWS 콘솔 열기**
   - <https://console.aws.amazon.com/ec2/home#Instances>:

2. **로그인** (루트 사용자)

3. **인스턴스 상태 확인**
   - `kbo-stats-server` 찾기
   - 상태가 **"실행 중"**인지 확인

   **결과:**
   - ✅ **실행 중** → 2단계로
   - ❌ **중지됨** → 인스턴스 시작 필요 (메일이 안 온 이유!)
   - ❌ **종료됨** → 인스턴스가 삭제됨 (재생성 필요)

---

### ✅ 2단계: 현재 시간 확인

**중요:** 크롤링은 **매일 새벽 2시**에 실행됩니다!

현재 시간: **2026-01-15 12:50 (오후 12시 50분)**

**질문:**

- 오늘 새벽 2시 이후에 메일을 받았어야 하나요?
- 아니면 어제나 그 전에 받았어야 하나요?

**확인:**

- ✅ 오늘 새벽 2시 이후 → 메일이 와야 함 (문제 있음)
- ⚠️ 아직 새벽 2시 전 → 메일이 안 온 게 정상

---

### ✅ 3단계: 스팸함 확인

**받는 이메일:** `wk120481@gmail.com`

1. Gmail 접속
2. **스팸함** 확인
3. "KBO" 또는 "통계" 검색

---

## 🔍 상세 확인 (SSH 필요)

EC2가 실행 중이고, 시간도 지났는데 메일이 안 왔다면:

### PowerShell에서 SSH 접속

```powershell
# EC2 IP 주소를 실제 IP로 변경
ssh -i $HOME\.ssh\kbo-key.pem ubuntu@43.200.4.183
```

**SSH 키 파일이 없다면:**

```powershell
# 다운로드 폴더에서 찾기
Move-Item $HOME\Downloads\kbo-key.pem $HOME\.ssh\
icacls $HOME\.ssh\kbo-key.pem /inheritance:r
icacls $HOME\.ssh\kbo-key.pem /grant:r "$env:USERNAME`:R"
```

---

### SSH 접속 후 확인

```bash
# 1. Crontab 설정 확인
crontab -l

# 2. 오늘 크롤링 로그 확인
TODAY=$(date +%Y%m%d)
ls -lh ~/b_project/logs/selenium_batter_${TODAY}.log

# 3. 로그 내용 확인 (마지막 50줄)
tail -n 50 ~/b_project/logs/selenium_batter_${TODAY}.log

# 4. Cron 로그 확인
tail -n 50 ~/b_project/logs/cron.log

# 5. 이메일 설정 확인
cat ~/b_project/config/email_config.json
```

---

## 📊 예상 원인별 해결 방법

### 원인 1: EC2 인스턴스가 중지됨

**증상:** AWS 콘솔에서 "중지됨" 상태

**해결:**

1. 인스턴스 선택
2. "인스턴스 상태" → "인스턴스 시작"
3. ⚠️ IP 주소가 변경될 수 있음

---

### 원인 2: Crontab이 설정되지 않음

**증상:** `crontab -l` 실행 시 아무것도 안 나옴

**해결:**

```bash
crontab -e

# 아래 내용 추가
0 2 * * * mkdir -p /home/ubuntu/b_project/logs && cd /home/ubuntu/b_project && /home/ubuntu/b_project/venv/bin/python data_collection/selenium_batter_scraper.py && /home/ubuntu/b_project/venv/bin/python data_collection/kbo_to_db.py && /home/ubuntu/b_project/venv/bin/python data_collection/email_notifier.py --success >> /home/ubuntu/b_project/logs/cron.log 2>&1

# Ctrl+O → Enter → Ctrl+X
```

---

### 원인 3: 크롤링은 성공했지만 이메일 발송 실패

**증상:** 크롤러 로그는 있지만 이메일 없음

**해결:**

```bash
# 이메일 설정 확인
cat ~/b_project/config/email_config.json

# 수동 이메일 테스트
cd ~/b_project
source venv/bin/activate
python data_collection/email_notifier.py --success --batter 450
```

**이메일 설정이 없다면:**

```bash
nano ~/b_project/config/email_config.json

# 아래 내용 입력 (본인 정보로 수정)
{
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "본인이메일@gmail.com",
    "sender_password": "앱비밀번호16자리",
    "receiver_email": "wk120481@gmail.com"
}

# Ctrl+O → Enter → Ctrl+X
```

---

### 원인 4: 크롤링 자체가 실패

**증상:** 오늘 날짜의 로그 파일이 없거나 에러 메시지

**해결:**

```bash
# 수동 크롤링 테스트
cd ~/b_project
source venv/bin/activate
python data_collection/selenium_batter_scraper.py
```

---

## 🚨 긴급 조치: 지금 당장 메일 받기

SSH 접속 후:

```bash
cd ~/b_project
source venv/bin/activate

# 크롤링 실행 (10-15분)
python data_collection/selenium_batter_scraper.py

# DB 저장
python data_collection/kbo_to_db.py

# 이메일 발송
python data_collection/email_notifier.py --success --batter 450 --pitcher 300 --team 10
```

---

## 📋 체크리스트

- [ ] EC2 인스턴스가 **실행 중**인가?
- [ ] 현재 시간이 **새벽 2시 이후**인가?
- [ ] **스팸함**을 확인했는가?
- [ ] SSH 접속이 가능한가?
- [ ] Crontab이 설정되어 있는가?
- [ ] 오늘 날짜의 로그 파일이 있는가?
- [ ] 이메일 설정 파일이 있는가?

---

## 💡 가장 가능성 높은 원인

1. **아직 새벽 2시가 안 됨** (정상)
2. **EC2 인스턴스가 중지됨**
3. **Crontab이 설정되지 않음**
4. **이메일 설정이 없음**
5. **스팸함에 있음**

---

**다음 단계:**

1. AWS 콘솔에서 EC2 상태 확인
2. 실행 중이면 SSH 접속
3. 위 명령어로 확인

**SSH 접속 방법:**

```powershell
ssh -i $HOME\.ssh\kbo-key.pem ubuntu@[EC2_IP주소]
```

---

**작성일:** 2026-01-15  
**목적:** 메일 미수신 원인을 빠르게 파악하고 해결하기
