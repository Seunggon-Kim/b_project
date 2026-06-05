# 💻 PowerShell에서 AWS EC2 상태 확인하기

**작성일:** 2026-01-15  
**목적:** PowerShell을 사용하여 AWS EC2 크롤링 및 메일 전송 상태 확인

---

## 🚀 빠른 시작 (복사해서 붙여넣기)

### 1단계: PowerShell 열기

**방법 A: 프로젝트 폴더에서 바로 열기 (추천)**

1. 파일 탐색기에서 `C:\Users\김승곤\Desktop\b_project` 폴더 열기
2. 주소창 클릭 → `powershell` 입력 → Enter

**방법 B: 시작 메뉴에서**

1. `Windows 키` 누르기
2. `PowerShell` 입력
3. `Windows PowerShell` 클릭

---

### 2단계: 프로젝트 폴더로 이동 (방법 B를 사용한 경우)

```powershell
cd C:\Users\김승곤\Desktop\b_project
```

---

### 3단계: EC2 IP 주소 확인

**옵션 A: 자동으로 브라우저 열기**

```powershell
.\get_ec2_ip.ps1
```

이 스크립트가 자동으로 AWS EC2 콘솔을 브라우저로 열어줍니다.

**옵션 B: 수동으로 확인**

1. 브라우저에서 <https://console.aws.amazon.com/ec2/home#Instances>: 접속
2. AWS 로그인 (루트 사용자)
3. `kbo-stats-server` 인스턴스 클릭
4. **퍼블릭 IPv4 주소** 복사 (예: `43.200.4.183`)

---

### 4단계: 상태 확인 스크립트 실행

IP 주소를 확인했다면:

```powershell
.\check_aws_status.ps1 [IP주소]
```

**예시:**

```powershell
.\check_aws_status.ps1 43.200.4.183
```

---

## 📋 전체 과정 (복사해서 사용)

PowerShell에서 아래 명령어를 **순서대로** 실행하세요:

```powershell
# 1. 프로젝트 폴더로 이동
cd C:\Users\김승곤\Desktop\b_project

# 2. EC2 IP 확인 도우미 실행 (브라우저 열림)
.\get_ec2_ip.ps1

# 3. IP 주소를 확인한 후, 아래 명령어 실행 (IP 주소 변경 필요)
.\check_aws_status.ps1 43.200.4.183
```

---

## 🔍 스크립트가 확인하는 항목

`check_aws_status.ps1` 스크립트는 자동으로 다음을 확인합니다:

1. **📋 Crontab 설정**
   - 크롤링 스케줄이 설정되어 있는지 확인

2. **📊 최근 로그 파일 목록**
   - 로그 파일이 생성되고 있는지 확인

3. **📝 Cron 로그**
   - Cron 작업 실행 기록 확인

4. **🤖 오늘 크롤러 로그**
   - 오늘 크롤링이 실행되었는지 확인

5. **💾 데이터베이스 파일 정보**
   - DB 파일이 업데이트되었는지 확인

6. **📧 이메일 설정 확인**
   - 이메일 설정이 올바른지 확인

7. **🔧 Cron 서비스 상태**
   - Cron 서비스가 실행 중인지 확인

8. **💿 디스크 공간**
   - 서버 디스크 공간 확인

---

## 📊 예상 출력 결과

### ✅ 정상인 경우

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 AWS EC2 크롤링 상태 확인
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ SSH 키 파일 확인 완료

🔌 EC2 서버 접속 중: 43.200.4.183

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 1. Crontab 설정 확인
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
0 2 * * * mkdir -p /home/ubuntu/b_project/logs && cd /home/ubuntu/b_project && ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 2. 최근 로그 파일 목록
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-rw-r--r-- 1 ubuntu ubuntu 12K Jan 15 02:15 cron.log
-rw-r--r-- 1 ubuntu ubuntu 45K Jan 15 02:14 selenium_batter_20260115.log

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 3. Cron 로그 (최근 30줄)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2026-01-15 02:00:01 - 크롤링 시작
2026-01-15 02:14:23 - 크롤링 완료
2026-01-15 02:14:45 - DB 저장 완료
2026-01-15 02:15:12 - 이메일 발송 완료

...
```

### ⚠️ 문제가 있는 경우

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 4. 오늘 크롤러 로그 (최근 50줄)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ 오늘 크롤러 로그 없음
```

→ 이 경우 [TROUBLESHOOTING_CHECKLIST.md](./TROUBLESHOOTING_CHECKLIST.md) 참고

---

## 🚨 SSH 접속 오류 해결

### 오류: "Permission denied (publickey)"

**원인:** SSH 키 파일 권한 문제

**해결:**

```powershell
# 키 파일 권한 재설정
icacls $HOME\.ssh\kbo-key.pem /inheritance:r
icacls $HOME\.ssh\kbo-key.pem /grant:r "$env:USERNAME`:R"
```

---

### 오류: "SSH 키 파일이 없습니다"

**원인:** `kbo-key.pem` 파일이 `.ssh` 폴더에 없음

**해결:**

```powershell
# .ssh 폴더 생성
New-Item -ItemType Directory -Force -Path $HOME\.ssh

# 다운로드 폴더에서 키 파일 찾기
Get-ChildItem $HOME\Downloads\kbo-key.pem

# 키 파일 이동
Move-Item $HOME\Downloads\kbo-key.pem $HOME\.ssh\

# 권한 설정
icacls $HOME\.ssh\kbo-key.pem /inheritance:r
icacls $HOME\.ssh\kbo-key.pem /grant:r "$env:USERNAME`:R"
```

---

## 🔧 수동으로 SSH 접속하기

상태 확인 스크립트 없이 직접 SSH 접속:

```powershell
# SSH 접속
ssh -i $HOME\.ssh\kbo-key.pem ubuntu@[IP주소]
```

**예시:**

```powershell
ssh -i $HOME\.ssh\kbo-key.pem ubuntu@43.200.4.183
```

접속 후 수동으로 확인:

```bash
# Crontab 확인
crontab -l

# 최근 로그 확인
tail -n 50 ~/b_project/logs/cron.log

# 오늘 크롤러 로그 확인
TODAY=$(date +%Y%m%d)
tail -n 50 ~/b_project/logs/selenium_batter_${TODAY}.log

# 이메일 설정 확인
cat ~/b_project/config/email_config.json

# 데이터베이스 확인
python ~/b_project/check_kbo_stats.py
```

---

## 🚀 긴급 조치: 수동 크롤링 및 메일 발송

SSH 접속 후:

```bash
# 프로젝트 폴더로 이동
cd ~/b_project
source venv/bin/activate

# 크롤링 실행 (10-15분 소요)
python data_collection/selenium_batter_scraper.py

# DB 저장
python data_collection/kbo_to_db.py

# 데이터 확인
python check_kbo_stats.py

# 이메일 발송
python data_collection/email_notifier.py --success --batter 450 --pitcher 300 --team 10
```

PowerShell로 돌아오기:

```bash
exit
```

---

## 📝 유용한 PowerShell 명령어

### 프로젝트 폴더의 스크립트 목록 보기

```powershell
Get-ChildItem *.ps1
```

### 스크립트 도움말 보기

```powershell
Get-Help .\check_aws_status.ps1
```

### SSH 키 파일 확인

```powershell
Test-Path $HOME\.ssh\kbo-key.pem
```

결과:

- `True` → 키 파일 존재 ✅
- `False` → 키 파일 없음 ❌

---

## 🎯 체크리스트

PowerShell에서 확인할 사항:

- [ ] PowerShell을 프로젝트 폴더에서 열었는가?
- [ ] EC2 IP 주소를 확인했는가?
- [ ] SSH 키 파일(`kbo-key.pem`)이 `.ssh` 폴더에 있는가?
- [ ] `check_aws_status.ps1` 스크립트를 실행했는가?
- [ ] 스크립트 출력 결과를 확인했는가?

---

## 📚 관련 문서

| 문서 | 설명 |
|------|------|
| **[QUICK_CHECK.md](./QUICK_CHECK.md)** | 빠른 확인 방법 |
| **[AWS_STATUS_CHECK_GUIDE.md](./AWS_STATUS_CHECK_GUIDE.md)** | 종합 상태 확인 가이드 |
| **[TROUBLESHOOTING_CHECKLIST.md](./TROUBLESHOOTING_CHECKLIST.md)** | 문제 해결 체크리스트 |
| **[check_aws_logs.md](./check_aws_logs.md)** | 로그 확인 가이드 |

---

## 💡 팁

### 1. PowerShell 히스토리 사용

이전에 실행한 명령어를 다시 사용하려면:

- `↑` (위 화살표) 키를 눌러 이전 명령어 불러오기
- `Ctrl + R` → 검색어 입력하여 명령어 찾기

### 2. 탭 자동완성

파일명이나 폴더명을 입력할 때:

- 일부만 입력하고 `Tab` 키를 누르면 자동완성

예시:

```powershell
.\check_  # Tab 키 누르기
→ .\check_aws_status.ps1
```

### 3. 복사 & 붙여넣기

- **복사:** 텍스트 드래그 후 `Ctrl + C`
- **붙여넣기:** PowerShell에서 `우클릭` 또는 `Ctrl + V`

---

**마지막 업데이트:** 2026-01-15  
**작성자:** Antigravity AI
