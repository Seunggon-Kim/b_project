# ⚡ PowerShell 빠른 시작 가이드

## 🎯 지금 바로 시작하기

### 📝 복사해서 PowerShell에 붙여넣으세요

```powershell
# 1. 프로젝트 폴더로 이동
cd C:\Users\USERNAME\Desktop\b_project

# 2. EC2 IP 주소 확인 (브라우저가 자동으로 열림)
.\get_ec2_ip.ps1
```

브라우저에서 IP 주소를 복사한 후:

```powershell
# 3. 상태 확인 (아래 IP 주소를 실제 IP로 변경)
.\check_aws_status.ps1 EC2_PUBLIC_IP
```

---

## 🖥️ PowerShell 여는 방법

### 방법 1: 프로젝트 폴더에서 바로 열기 (가장 쉬움!) ⭐

1. 파일 탐색기 열기 (`Windows 키 + E`)
2. 주소창에 입력: `C:\Users\USERNAME\Desktop\b_project`
3. 주소창 클릭 → `powershell` 입력 → `Enter`

### 방법 2: 시작 메뉴에서

1. `Windows 키` 누르기
2. `PowerShell` 입력
3. `Windows PowerShell` 클릭
4. 아래 명령어 입력:

   ```powershell
   cd C:\Users\USERNAME\Desktop\b_project
   ```

---

## 📋 전체 과정 (스크린샷 가이드)

### 1단계: PowerShell 열기

```
파일 탐색기 주소창:
┌─────────────────────────────────────────────┐
│ C:\Users\USERNAME\Desktop\b_project            │
└─────────────────────────────────────────────┘
         ↓ 클릭 후 "powershell" 입력
┌─────────────────────────────────────────────┐
│ powershell                                  │
└─────────────────────────────────────────────┘
         ↓ Enter 키
```

### 2단계: EC2 IP 확인

PowerShell에 입력:

```powershell
.\get_ec2_ip.ps1
```

출력:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌐 AWS EC2 IP 주소 확인
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 안내:
  1. 브라우저가 자동으로 AWS EC2 콘솔을 엽니다
  2. AWS 계정으로 로그인하세요
  3. 'kbo-stats-server' 인스턴스를 찾으세요
  4. '퍼블릭 IPv4 주소'를 복사하세요

브라우저를 여시겠습니까? (Y/N): _
```

`Y` 입력 → Enter

### 3단계: AWS 콘솔에서 IP 복사

브라우저가 열리면:

1. AWS 로그인 (루트 사용자)
2. `kbo-stats-server` 인스턴스 클릭
3. **퍼블릭 IPv4 주소** 복사 (예: `EC2_PUBLIC_IP`)

### 4단계: 상태 확인

PowerShell에 입력 (IP 주소 변경):

```powershell
.\check_aws_status.ps1 EC2_PUBLIC_IP
```

---

## ✅ 정상 출력 예시

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 AWS EC2 크롤링 상태 확인
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ SSH 키 파일 확인 완료

🔌 EC2 서버 접속 중: EC2_PUBLIC_IP

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 1. Crontab 설정 확인
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
0 2 * * * mkdir -p /home/ubuntu/b_project/logs && ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 2. 최근 로그 파일 목록
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-rw-r--r-- 1 ubuntu ubuntu 12K Jan 15 02:15 cron.log
-rw-r--r-- 1 ubuntu ubuntu 45K Jan 15 02:14 selenium_batter_20260115.log

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 확인 완료
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🚨 문제 발생 시

### 문제 1: "SSH 키 파일이 없습니다"

PowerShell에 입력:

```powershell
# .ssh 폴더 생성
New-Item -ItemType Directory -Force -Path $HOME\.ssh

# 다운로드 폴더에서 키 파일 찾기
Move-Item $HOME\Downloads\kbo-key.pem $HOME\.ssh\

# 권한 설정
icacls $HOME\.ssh\kbo-key.pem /inheritance:r
icacls $HOME\.ssh\kbo-key.pem /grant:r "$env:USERNAME`:R"
```

### 문제 2: "오늘 크롤러 로그 없음"

→ [TROUBLESHOOTING_CHECKLIST.md](./TROUBLESHOOTING_CHECKLIST.md) 참고

### 문제 3: SSH 접속 실패

PowerShell에 입력:

```powershell
# 키 파일 권한 재설정
icacls $HOME\.ssh\kbo-key.pem /inheritance:r
icacls $HOME\.ssh\kbo-key.pem /grant:r "$env:USERNAME`:R"
```

---

## 🎯 다음 단계

상태 확인 후:

### ✅ 모든 것이 정상이면

- 매일 새벽 2시에 자동 크롤링 실행
- 크롤링 완료 후 자동 이메일 발송
- 받은편지함 확인: `your-email@gmail.com`

### ⚠️ 문제가 있으면

1. [TROUBLESHOOTING_CHECKLIST.md](./TROUBLESHOOTING_CHECKLIST.md) 확인
2. 수동으로 크롤링 실행 (아래 참고)

---

## 🚀 수동 크롤링 실행

PowerShell에서:

```powershell
# SSH 접속
ssh -i $HOME\.ssh\kbo-key.pem ubuntu@EC2_PUBLIC_IP
```

SSH 접속 후:

```bash
cd ~/b_project
source venv/bin/activate
python data_collection/selenium_batter_scraper.py
python data_collection/kbo_to_db.py
python data_collection/email_notifier.py --success --batter 450
```

---

## 💡 유용한 팁

### 복사 & 붙여넣기

- **복사:** `Ctrl + C`
- **붙여넣기:** PowerShell에서 `우클릭` 또는 `Ctrl + V`

### 이전 명령어 다시 사용

- `↑` (위 화살표) 키를 눌러 이전 명령어 불러오기

### 탭 자동완성

- 파일명 일부 입력 후 `Tab` 키

---

## 📚 상세 가이드

더 자세한 내용은:

- [POWERSHELL_GUIDE.md](./POWERSHELL_GUIDE.md) - PowerShell 상세 가이드
- [AWS_STATUS_CHECK_GUIDE.md](./AWS_STATUS_CHECK_GUIDE.md) - 종합 상태 확인
- [TROUBLESHOOTING_CHECKLIST.md](./TROUBLESHOOTING_CHECKLIST.md) - 문제 해결

---

**작성일:** 2026-01-15  
**목적:** PowerShell 초보자를 위한 빠른 시작 가이드
