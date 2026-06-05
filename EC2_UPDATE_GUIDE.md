# EC2 서버 업데이트 가이드

## 🚀 빠른 업데이트 방법

### 1단계: PuTTY로 EC2 접속

1. **PuTTY 실행**
2. **Host Name**: `ubuntu@43.200.4.183`
3. **Port**: `22`
4. **Connection > SSH > Auth**: `kbo-key.ppk` 선택
5. **Open** 클릭

### 2단계: 명령어 실행

EC2에 접속한 후 다음 명령어를 **순서대로** 실행:

```bash
# 1. 프로젝트 디렉토리로 이동
cd ~/b_project

# 2. Git pull
git pull

# 3. 대시보드 재시작
sudo systemctl restart kbo-dashboard

# 4. 상태 확인
sudo systemctl status kbo-dashboard
```

### 3단계: 확인

브라우저에서 접속:

- <http://43.200.4.183:8502>

투수 통계가 보이면 성공! 🎉

---

## 🔧 문제 해결

### Git pull 실패 시

```bash
cd ~/b_project
git status
git stash  # 로컬 변경사항 임시 저장
git pull
```

### 대시보드 재시작 실패 시

```bash
# 로그 확인
sudo journalctl -u kbo-dashboard -n 50

# 수동 재시작
sudo systemctl stop kbo-dashboard
sudo systemlit start kbo-dashboard
```

### 투수 크롤링 실행 (EC2에서)

```bash
cd ~/b_project
source venv/bin/activate  # 가상환경 활성화 (있는 경우)
python data_collection/selenium_pitcher_scraper.py
python data_collection/pitcher_to_db.py
```

---

## 📋 전체 업데이트 체크리스트

- [ ] 로컬에서 `git push` 완료
- [ ] EC2에 SSH 접속
- [ ] `cd ~/b_project`
- [ ] `git pull`
- [ ] `sudo systemctl restart kbo-dashboard`
- [ ] 브라우저에서 확인 (<http://43.200.4.183:8502>)
- [ ] 투수 통계 탭 확인

---

## 🌐 도메인 연결 (ilovefieldhockey)

도메인을 연결하려면:

1. **도메인 구매** (예: ilovefieldhockey.com)
   - GoDaddy, Namecheap, Cafe24 등

2. **DNS 설정**
   - A 레코드: `@` → `43.200.4.183`
   - A 레코드: `www` → `43.200.4.183`

3. **Nginx 설정** (선택사항, HTTPS용)

   ```bash
   sudo apt install nginx certbot python3-certbot-nginx
   sudo certbot --nginx -d ilovefieldhockey.com
   ```

4. **Nginx 리버스 프록시 설정**

   ```nginx
   server {
       listen 80;
       server_name ilovefieldhockey.com www.ilovefieldhockey.com;
       
       location / {
           proxy_pass http://localhost:8502;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
       }
   }
   ```

설정 후 접속:

- <http://ilovefieldhockey.com> (포트 번호 없이!)

---

## 💡 자동화 (선택사항)

EC2에서 cron으로 자동 pull 설정:

```bash
crontab -e

# 매일 새벽 2시에 자동 pull
0 2 * * * cd ~/b_project && git pull && sudo systemctl restart kbo-dashboard
```
