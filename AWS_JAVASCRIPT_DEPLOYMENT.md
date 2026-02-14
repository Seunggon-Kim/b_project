# AWS EC2 JavaScript 대시보드 배포 가이드

기존 Streamlit 대시보드를 JavaScript 대시보드로 완전히 교체하는 가이드입니다.

---

## 📋 배포 개요

### 변경 사항

- ❌ **제거**: Streamlit 대시보드 (Python)
- ✅ **추가**: JavaScript 대시보드 + FastAPI 백엔드
- ✅ **유지**: 데이터 수집 자동화 (Cron)

### 장점

- ⚡ 더 빠른 로딩 속도
- 🎨 프리미엄 디자인
- 📱 완벽한 모바일 지원
- 🔧 더 쉬운 커스터마이징

---

## 🚀 배포 단계

### Step 1: GitHub에 코드 푸시

로컬 PC (PowerShell)에서:

```powershell
cd C:\Users\USERNAME\Desktop\b_project

# 변경사항 확인
git status

# 모든 변경사항 추가
git add .

# 커밋
git commit -m "Replace Streamlit with JavaScript dashboard"

# GitHub에 푸시
git push origin main
```

### Step 2: AWS EC2 접속

```powershell
# EC2 인스턴스가 실행 중인지 확인 (AWS 콘솔)
# https://ap-northeast-2.console.aws.amazon.com/ec2/home?region=ap-northeast-2#Instances:

# SSH 접속
ssh -i C:\Users\USERNAME\.ssh\kbo-key.pem ubuntu@[퍼블릭_IP]
```

### Step 3: 기존 Streamlit 서비스 중지

```bash
# Streamlit 서비스 중지
sudo systemctl stop kbo-dashboard
sudo systemctl disable kbo-dashboard

# 또는 nohup으로 실행 중이었다면
pkill -f streamlit
```

### Step 4: 코드 업데이트

```bash
cd ~/b_project

# 최신 코드 가져오기
git pull origin main

# 가상환경 활성화
source venv/bin/activate

# 새로운 패키지 설치
pip install fastapi uvicorn
```

### Step 5: FastAPI 서비스 설정

#### 5-1. systemd 서비스 파일 생성

```bash
sudo nano /etc/systemd/system/kbo-api.service
```

다음 내용 입력:

```ini
[Unit]
Description=KBO Analytics API Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/b_project
Environment="PATH=/home/ubuntu/b_project/venv/bin"
ExecStart=/home/ubuntu/b_project/venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

저장: `Ctrl + O` → `Enter` → `Ctrl + X`

#### 5-2. 서비스 시작

```bash
# 서비스 활성화
sudo systemctl enable kbo-api

# 서비스 시작
sudo systemctl start kbo-api

# 상태 확인
sudo systemctl status kbo-api
```

### Step 6: Nginx 설정 (웹 서버)

#### 6-1. Nginx 설치

```bash
sudo apt-get update
sudo apt-get install -y nginx
```

#### 6-2. Nginx 설정 파일 생성

```bash
sudo nano /etc/nginx/sites-available/kbo-dashboard
```

다음 내용 입력:

```nginx
server {
    listen 80;
    server_name _;

    # 정적 파일 (JavaScript 대시보드)
    location / {
        root /home/ubuntu/b_project/dashboard_js;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # API 프록시
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

저장: `Ctrl + O` → `Enter` → `Ctrl + X`

#### 6-3. Nginx 활성화

```bash
# 심볼릭 링크 생성
sudo ln -s /etc/nginx/sites-available/kbo-dashboard /etc/nginx/sites-enabled/

# 기본 사이트 비활성화
sudo rm /etc/nginx/sites-enabled/default

# 설정 테스트
sudo nginx -t

# Nginx 재시작
sudo systemctl restart nginx
```

### Step 7: 보안 그룹 설정

AWS 콘솔에서:

1. EC2 → 인스턴스 → 보안 그룹 클릭
2. 인바운드 규칙 편집
3. 다음 규칙 추가:

```
- HTTP (80) - 소스: 0.0.0.0/0
- HTTPS (443) - 소스: 0.0.0.0/0 (선택사항)
- 사용자 지정 TCP (8000) - 소스: 0.0.0.0/0 (API 직접 접근용, 선택사항)
```

1. 기존 8502 포트 규칙 삭제 (Streamlit 불필요)

### Step 8: JavaScript API URL 수정

EC2에서:

```bash
nano ~/b_project/dashboard_js/js/api.js
```

첫 줄을 다음과 같이 수정:

```javascript
const API_BASE_URL = '/api';  // Nginx 프록시 사용
// 또는
const API_BASE_URL = 'http://[퍼블릭_IP]:8000';  // 직접 접근
```

저장 후 종료

### Step 9: 테스트

```bash
# API 서버 확인
curl http://localhost:8000

# Nginx 확인
curl http://localhost

# 서비스 상태 확인
sudo systemctl status kbo-api
sudo systemctl status nginx
```

### Step 10: 브라우저에서 접속

```
http://[퍼블릭_IP]
```

또는

```
http://[퍼블릭_IP]:8000/docs  (API 문서)
```

---

## 🔄 자동 재시작 설정

서버 재부팅 시 자동으로 서비스가 시작되도록 설정:

```bash
# 부팅 시 자동 시작 확인
sudo systemctl is-enabled kbo-api
sudo systemctl is-enabled nginx

# 활성화되지 않았다면
sudo systemctl enable kbo-api
sudo systemctl enable nginx
```

---

## 📊 서비스 관리 명령어

### API 서버 (FastAPI)

```bash
# 시작
sudo systemctl start kbo-api

# 중지
sudo systemctl stop kbo-api

# 재시작
sudo systemctl restart kbo-api

# 상태 확인
sudo systemctl status kbo-api

# 로그 확인
sudo journalctl -u kbo-api -f
```

### 웹 서버 (Nginx)

```bash
# 시작
sudo systemctl start nginx

# 중지
sudo systemctl stop nginx

# 재시작
sudo systemctl restart nginx

# 상태 확인
sudo systemctl status nginx

# 설정 테스트
sudo nginx -t

# 로그 확인
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

---

## 🔧 트러블슈팅

### 문제 1: API 서버가 시작되지 않음

```bash
# 로그 확인
sudo journalctl -u kbo-api -n 50

# 포트 사용 확인
sudo netstat -tulpn | grep 8000

# 수동 실행 테스트
cd ~/b_project
source venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### 문제 2: Nginx 502 Bad Gateway

```bash
# API 서버 실행 확인
sudo systemctl status kbo-api

# API 서버 재시작
sudo systemctl restart kbo-api

# Nginx 재시작
sudo systemctl restart nginx
```

### 문제 3: 정적 파일이 로드되지 않음

```bash
# 파일 권한 확인
ls -la ~/b_project/dashboard_js/

# 권한 수정
chmod -R 755 ~/b_project/dashboard_js/
```

### 문제 4: CORS 오류

API에서 이미 CORS가 설정되어 있지만, 문제가 있다면:

```bash
nano ~/b_project/api/main.py
```

CORS 설정 확인:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 📝 코드 업데이트 프로세스

로컬에서 코드 수정 후:

```powershell
# 로컬 (Windows)
git add .
git commit -m "Update dashboard"
git push origin main
```

EC2에서:

```bash
# EC2 (Ubuntu)
cd ~/b_project
git pull origin main

# API 서버 재시작
sudo systemctl restart kbo-api

# Nginx는 정적 파일이므로 재시작 불필요 (캐시 문제 시에만)
# sudo systemctl restart nginx
```

---

## 🎯 완료 체크리스트

- [ ] GitHub에 코드 푸시
- [ ] EC2 SSH 접속
- [ ] 기존 Streamlit 서비스 중지
- [ ] 최신 코드 pull
- [ ] FastAPI 패키지 설치
- [ ] FastAPI systemd 서비스 생성 및 시작
- [ ] Nginx 설치 및 설정
- [ ] 보안 그룹 규칙 업데이트 (포트 80)
- [ ] JavaScript API URL 수정
- [ ] 브라우저에서 접속 확인
- [ ] API 문서 접속 확인 (/docs)
- [ ] 모든 페이지 동작 확인

---

## 🌐 접속 URL

배포 완료 후:

- **대시보드**: `http://[퍼블릭_IP]`
- **API 문서**: `http://[퍼블릭_IP]:8000/docs`
- **API 엔드포인트**: `http://[퍼블릭_IP]:8000/`

---

## 💡 추가 개선 사항 (선택)

### 1. HTTPS 설정 (Let's Encrypt)

```bash
# Certbot 설치
sudo apt-get install -y certbot python3-certbot-nginx

# 도메인이 있다면 SSL 인증서 발급
sudo certbot --nginx -d yourdomain.com
```

### 2. 도메인 연결

AWS Route 53 또는 다른 DNS 서비스에서 도메인을 EC2 IP에 연결

### 3. 성능 최적화

Nginx에서 gzip 압축 활성화:

```bash
sudo nano /etc/nginx/nginx.conf
```

```nginx
gzip on;
gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
```

---

**축하합니다! 🎉 JavaScript 대시보드가 AWS EC2에 배포되었습니다!**

이제 더 빠르고 모던한 대시보드를 24/7 사용할 수 있습니다!
