# AWS EC2 자동화 배포 가이드

KBO 타자 통계 대시보드를 AWS EC2에서 24/7 자동 수집 및 호스팅하는 완전한 가이드입니다.

---

## 📋 목차

1. [사전 준비](#사전-준비)
2. [AWS 계정 생성](#aws-계정-생성)
3. [EC2 인스턴스 생성](#ec2-인스턴스-생성)
4. [SSH 접속 설정](#ssh-접속-설정)
5. [서버 환경 구축](#서버-환경-구축)
6. [GitHub 저장소 설정](#github-저장소-설정)
7. [프로젝트 배포](#프로젝트-배포)
8. [자동화 설정 (Crontab)](#자동화-설정-crontab)
9. [대시보드 배포 (선택)](#대시보드-배포-선택)
10. [트러블슈팅](#트러블슈팅)

---

## 🎯 사전 준비

### 필요한 것들

- ✅ 이메일 주소 (AWS 가입용)
- ✅ 신용카드 또는 체크카드 (1달러 결제 후 환불)
- ✅ 휴대폰 번호 (SMS 인증용)
- ✅ 로컬 PC에 완성된 프로젝트 코드

### 예상 비용

- **프리 티어 (12개월 무료)**: t2.micro 또는 t3.micro
- **월 750시간 무료** (24시간 운영 가능)
- **스토리지**: 30GB 무료
- **데이터 전송**: 15GB/월 무료

---

## 🔐 AWS 계정 생성

### Step 1: AWS 가입 페이지 접속

1. <https://aws.amazon.com/ko/> 접속
2. **"무료 계정 만들기"** 클릭

### Step 2: 계정 정보 입력

- **이메일**: 본인 이메일
- **계정 이름**: 원하는 이름 (예: KBO-Stats-Project)
- **비밀번호**: 8자 이상, 대소문자/숫자/특수문자 포함

### Step 3: 연락처 정보

- **계정 유형**: 개인
- **이름, 전화번호, 주소**: 실제 정보 입력
- 주소 영문 변환: <https://www.juso.go.kr/openIndexPage.do>

### Step 4: 결제 정보

- 카드 번호, 유효기간, CVC 입력
- **1달러 결제 후 자동 환불**됩니다

### Step 5: 본인 확인

- **SMS 인증** 선택
- 전화번호: +82 10-XXXX-XXXX
- 받은 4자리 코드 입력

### Step 6: 지원 플랜

- **기본 지원 - 무료** 선택

### Step 7: 로그인

- **루트 사용자** 선택
- 이메일 + 비밀번호 입력

---

## 🖥️ EC2 인스턴스 생성

### Step 1: EC2 서비스 이동

1. AWS 콘솔 상단 검색창에 **"EC2"** 입력
2. EC2 클릭

### Step 2: 인스턴스 시작

1. 좌측 메뉴 **"인스턴스"** 클릭
2. **"인스턴스 시작"** 버튼 클릭

### Step 3: 인스턴스 설정

#### **이름 및 태그**

```
이름: kbo-stats-server
```

#### **애플리케이션 및 OS 이미지**

```
- Ubuntu Server 24.04 LTS (HVM), SSD Volume Type
- 아키텍처: 64비트(x86)
```

#### **인스턴스 유형**

```
- t3.micro (프리 티어 사용 가능) ✅
```

#### **키 페어 (로그인)**

```
1. "새 키 페어 생성" 클릭
2. 키 페어 이름: kbo-key
3. 키 페어 유형: RSA
4. 프라이빗 키 파일 형식: .pem
5. "키 페어 생성" 클릭
⚠️ kbo-key.pem 파일 자동 다운로드 (잘 보관!)
```

#### **네트워크 설정**

```
보안 그룹 이름: kbo-stats-sg

인바운드 규칙:
1. SSH (22) - 소스: 내 IP
2. 사용자 지정 TCP (8502) - 소스: 0.0.0.0/0 (Streamlit용)
```

#### **스토리지 구성**

```
- 크기: 20 GiB
- 볼륨 유형: gp3
```

### Step 4: 인스턴스 시작

- **"인스턴스 시작"** 버튼 클릭
- 상태가 **"실행 중"**으로 바뀔 때까지 대기 (1-2분)

### Step 5: 퍼블릭 IP 확인

- 인스턴스 클릭
- **퍼블릭 IPv4 주소** 복사 (예: EC2_PUBLIC_IP)

---

## 🔑 SSH 접속 설정

### Windows (PowerShell)

#### Step 1: .ssh 폴더 생성

```powershell
New-Item -ItemType Directory -Force -Path $HOME\.ssh
```

#### Step 2: 키 파일 이동

```powershell
Move-Item $HOME\Downloads\kbo-key.pem $HOME\.ssh\
```

#### Step 3: 키 파일 권한 설정

```powershell
icacls $HOME\.ssh\kbo-key.pem /inheritance:r
icacls $HOME\.ssh\kbo-key.pem /grant:r "$env:USERNAME`:R"
```

#### Step 4: SSH 접속

```powershell
ssh -i $HOME\.ssh\kbo-key.pem ubuntu@[퍼블릭_IP]
```

처음 접속 시 `yes` 입력

---

## 🛠️ 서버 환경 구축

### Step 1: 시스템 업데이트

```bash
sudo apt-get update && sudo apt-get upgrade -y
```

### Step 2: Python 및 필수 도구 설치

```bash
sudo apt-get install -y python3-pip python3-venv git wget curl
```

### Step 3: Google Chrome 설치

```bash
# Chrome 다운로드
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

# Chrome 설치
sudo apt install -y ./google-chrome-stable_current_amd64.deb

# 설치 파일 삭제
rm google-chrome-stable_current_amd64.deb

# Chrome 버전 확인
google-chrome --version
```

### Step 4: 설치 확인

```bash
python3 --version  # Python 3.12.x
pip3 --version     # pip 24.x
git --version      # git 2.x
google-chrome --version  # Google Chrome 143.x
```

---

## 🐙 GitHub 저장소 설정

### Step 1: GitHub 계정 생성 (없다면)

- <https://github.com> 접속
- 계정 생성

### Step 2: 새 저장소 생성

1. GitHub 로그인
2. **"New repository"** 클릭
3. 설정:
   - Repository name: `b_project`
   - Description: `KBO Baseball Statistics Dashboard`
   - Visibility: Public
   - Add .gitignore: **Python** ✅
   - Add README: Off
   - Add license: No license
4. **"Create repository"** 클릭

### Step 3: 로컬 코드 업로드 (Windows PowerShell)

#### 프로젝트 폴더로 이동

```powershell
cd C:\Users\[사용자명]\Desktop\b_project
```

#### Git 초기화

```powershell
git init
git remote add origin https://github.com/[사용자명]/b_project.git
git branch -M main
```

#### .gitignore 설정 (중요!)

```powershell
# .gitignore 파일 열기
notepad .gitignore
```

다음 내용 추가:

```
# Database files
database/*.db
database/*.db.backup
*.db
*.db.backup

# Large CSV files
crawler/save/*.csv
crawler/save/**/*.csv

# Logs
logs/*.log
```

#### 큰 파일 임시 이동

```powershell
# 임시 폴더 생성
New-Item -ItemType Directory -Force -Path C:\temp\b_project_backup

# 큰 파일 이동
Move-Item database\kbo_stats.db C:\temp\b_project_backup\ -ErrorAction SilentlyContinue
Move-Item database\kbo_stats.db.backup C:\temp\b_project_backup\ -ErrorAction SilentlyContinue
Move-Item crawler\save\2025.csv C:\temp\b_project_backup\ -ErrorAction SilentlyContinue
```

#### Git 커밋 & 푸시

```powershell
# .git 폴더 삭제 (깨끗한 시작)
Remove-Item -Recurse -Force .git

# Git 다시 초기화
git init
git branch -M main
git remote add origin https://github.com/[사용자명]/b_project.git

# 파일 추가 및 커밋
git add .
git commit -m "Initial commit: KBO Stats Dashboard"

# 푸시
git push -u origin main --force
```

GitHub 로그인 창이 나타나면 로그인

---

## 🚀 프로젝트 배포

### Step 1: 서버에 코드 복사

```bash
# 홈 디렉토리로 이동
cd ~

# GitHub에서 코드 가져오기
git clone https://github.com/[사용자명]/b_project.git

# 프로젝트 폴더로 이동
cd b_project
```

### Step 2: Python 가상환경 설정

```bash
# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate

# pip 업그레이드
pip install --upgrade pip

# 패키지 설치
pip install -r requirements.txt

# Selenium 추가 설치
pip install selenium webdriver-manager
```

### Step 3: 데이터베이스 초기화

```bash
python database/init_db.py
```

### Step 4: 크롤러 테스트

```bash
# 크롤러 실행 (10-15분 소요)
python data_collection/selenium_batter_scraper.py

# DB 저장
python data_collection/kbo_to_db.py
```

### Step 5: 데이터 확인

```bash
python check_kbo_stats.py
```

---

## ⏰ 자동화 설정 (Crontab)

### Step 1: Crontab 편집

```bash
crontab -e
```

처음 실행 시 편집기 선택: **1** (nano)

### Step 2: 스케줄 추가

맨 아래에 다음 내용 추가:

```bash
# KBO 타자 통계 자동 수집 (매일 새벽 2시)
0 2 * * * cd /home/ubuntu/b_project && /home/ubuntu/b_project/venv/bin/python data_collection/selenium_batter_scraper.py && /home/ubuntu/b_project/venv/bin/python data_collection/kbo_to_db.py >> /home/ubuntu/b_project/logs/cron.log 2>&1
```

### Step 3: 저장 및 종료

- `Ctrl + O` (저장)
- `Enter` (확인)
- `Ctrl + X` (종료)

### Step 4: Crontab 확인

```bash
crontab -l
```

### Step 5: 로그 폴더 생성

```bash
mkdir -p /home/ubuntu/b_project/logs
```

---

## 🌐 대시보드 배포 (선택사항)

### 방법 1: nohup으로 백그라운드 실행

```bash
# 대시보드 실행
nohup streamlit run dashboard/Home.py --server.port 8502 --server.address 0.0.0.0 > /home/ubuntu/b_project/logs/streamlit.log 2>&1 &

# 프로세스 확인
ps aux | grep streamlit

# 대시보드 접속
# http://[퍼블릭_IP]:8502
```

### 방법 2: systemd 서비스 (권장)

#### Step 1: 서비스 파일 생성

```bash
sudo nano /etc/systemd/system/kbo-dashboard.service
```

#### Step 2: 서비스 설정

```ini
[Unit]
Description=KBO Stats Dashboard
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/b_project
Environment="PATH=/home/ubuntu/b_project/venv/bin"
ExecStart=/home/ubuntu/b_project/venv/bin/streamlit run dashboard/Home.py --server.port 8502 --server.address 0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target
```

#### Step 3: 서비스 시작

```bash
# 서비스 활성화
sudo systemctl enable kbo-dashboard

# 서비스 시작
sudo systemctl start kbo-dashboard

# 상태 확인
sudo systemctl status kbo-dashboard
```

#### Step 4: 대시보드 접속

```
http://[퍼블릭_IP]:8502
```

---

## 🔧 트러블슈팅

### 문제 1: SSH 접속 실패

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

### 문제 2: Chrome 설치 실패

**증상:**

```
E: Unable to locate package google-chrome-stable
```

**해결:**

```bash
# 시스템 업데이트
sudo apt-get update

# Chrome 재다운로드
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb
```

---

### 문제 3: Git 푸시 실패 (파일 크기 초과)

**증상:**

```
remote: error: File xxx is 127.17 MB; this exceeds GitHub's file size limit of 100.00 MB
```

**해결:**

```powershell
# 큰 파일 제외
Remove-Item -Recurse -Force .git
git init
git branch -M main
git remote add origin https://github.com/[사용자명]/b_project.git
git add .
git commit -m "Initial commit"
git push -u origin main --force
```

---

### 문제 4: Cron 작업이 실행되지 않음

**확인:**

```bash
# Crontab 목록 확인
crontab -l

# 로그 확인
tail -f /home/ubuntu/b_project/logs/cron.log

# Cron 서비스 상태
sudo systemctl status cron
```

**해결:**

```bash
# Cron 서비스 재시작
sudo systemctl restart cron
```

---

### 문제 5: 대시보드 접속 불가

**확인:**

```bash
# 프로세스 확인
ps aux | grep streamlit

# 포트 확인
sudo netstat -tulpn | grep 8502
```

**해결:**

```bash
# 기존 프로세스 종료
pkill -f streamlit

# 대시보드 재시작
nohup streamlit run dashboard/Home.py --server.port 8502 --server.address 0.0.0.0 > /home/ubuntu/b_project/logs/streamlit.log 2>&1 &
```

---

## 📊 유지보수

### 코드 업데이트

```bash
# 서버에서
cd ~/b_project
git pull origin main

# 가상환경 활성화
source venv/bin/activate

# 패키지 업데이트
pip install -r requirements.txt --upgrade
```

### 로그 확인

```bash
# Cron 로그
tail -f ~/b_project/logs/cron.log

# Streamlit 로그
tail -f ~/b_project/logs/streamlit.log

# 크롤러 로그
ls -lh ~/b_project/logs/selenium_batter_*.log
```

### 디스크 공간 확인

```bash
df -h
```

### 데이터베이스 백업

```bash
# 백업 생성
cp ~/b_project/database/kbo_stats.db ~/b_project/database/kbo_stats.db.backup_$(date +%Y%m%d)

# 오래된 백업 삭제 (30일 이상)
find ~/b_project/database -name "*.backup_*" -mtime +30 -delete
```

---

## 🎯 완료 체크리스트

- [ ] AWS 계정 생성
- [ ] EC2 인스턴스 생성 및 실행
- [ ] SSH 접속 성공
- [ ] 서버 환경 구축 (Python, Chrome 등)
- [ ] GitHub 저장소 생성 및 코드 업로드
- [ ] 서버에 코드 배포
- [ ] 크롤러 테스트 성공
- [ ] 데이터베이스 저장 확인
- [ ] Crontab 자동화 설정
- [ ] 대시보드 배포 (선택)
- [ ] 외부에서 대시보드 접속 확인

---

## 📞 추가 지원

문제가 발생하면:

1. 로그 파일 확인
2. GitHub Issues에 문의
3. AWS 프리 티어 한도 확인

---

**축하합니다! 🎉 24/7 자동 크롤링 시스템이 완성되었습니다!**
