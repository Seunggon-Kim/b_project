# 🚨 AWS EC2 크롤링 & 메일 전송 빠른 확인

## 📋 상황

- AWS EC2에 프로젝트 등록 완료
- 크롤링이 실행되고 있는지 확인 필요
- 예약된 메일이 오지 않은 이유 파악 필요

---

## ⚡ 빠른 확인 (3단계)

### 1️⃣ EC2 IP 주소 확인

[AWS EC2 콘솔](https://console.aws.amazon.com/ec2/home#Instances:) 접속 → `kbo-stats-server` 클릭 → **퍼블릭 IPv4 주소** 복사

### 2️⃣ 상태 확인 스크립트 실행

```powershell
cd C:\Users\USERNAME\Desktop\b_project
.\check_aws_status.ps1 [EC2_IP주소]
```

**예시:**

```powershell
.\check_aws_status.ps1 EC2_PUBLIC_IP
```

### 3️⃣ 결과 확인

스크립트가 자동으로 다음을 확인합니다:

- ✅ Crontab 설정
- ✅ 크롤링 로그
- ✅ 이메일 설정
- ✅ Cron 서비스 상태

---

## 📚 상세 가이드

| 상황 | 문서 |
|------|------|
| **종합 상태 확인** | [AWS_STATUS_CHECK_GUIDE.md](./AWS_STATUS_CHECK_GUIDE.md) ⭐ |
| **문제 해결** | [TROUBLESHOOTING_CHECKLIST.md](./TROUBLESHOOTING_CHECKLIST.md) |
| **로그 확인** | [check_aws_logs.md](./check_aws_logs.md) |
| **EC2 인스턴스 확인** | [aws_instance_check.md](./aws_instance_check.md) |
| **초기 설정** | [AWS_AUTOMATION_GUIDE.md](./AWS_AUTOMATION_GUIDE.md) |

---

## 🚨 긴급 조치

메일이 오지 않았다면 수동으로 실행:

```bash
# SSH 접속
ssh -i ~/.ssh/kbo-key.pem ubuntu@[EC2_IP]

# 수동 실행
cd ~/b_project && source venv/bin/activate
python data_collection/selenium_batter_scraper.py
python data_collection/kbo_to_db.py
python data_collection/email_notifier.py --success --batter 450
```

---

## 🎯 주요 체크포인트

- [ ] EC2 인스턴스가 **실행 중**인가?
- [ ] Crontab이 설정되어 있는가?
- [ ] 오늘 날짜의 로그 파일이 생성되었는가?
- [ ] 이메일 설정이 올바른가?
- [ ] 스팸함도 확인했는가?

---

**작성일:** 2026-01-15  
**시작 문서:** [AWS_STATUS_CHECK_GUIDE.md](./AWS_STATUS_CHECK_GUIDE.md)
