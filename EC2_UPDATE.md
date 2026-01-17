# EC2 업데이트 - PowerShell 가이드

## 🚀 EC2 업데이트 방법

### 방법 1: 자동 스크립트 (권장)

```powershell
.\update_ec2.ps1
```

### 방법 2: 직접 명령어

```powershell
ssh -i C:\Users\USERNAME\.ssh\kbo-key.pem ubuntu@EC2_PUBLIC_IP "cd ~/b_project && git pull && sudo systemctl restart kbo-dashboard"
```

### 방법 3: 접속 후 수동 실행

```powershell
# 1. EC2 접속
ssh -i C:\Users\USERNAME\.ssh\kbo-key.pem ubuntu@EC2_PUBLIC_IP

# 2. 접속 후 실행
cd ~/b_project
git pull
sudo systemctl restart kbo-dashboard
exit
```

---

## ⚠️ 연결 안 될 때

EC2 인스턴스가 중지되었을 수 있습니다.

**AWS 콘솔에서 인스턴스 시작:**
<https://ap-northeast-2.console.aws.amazon.com/ec2/home?region=ap-northeast-2#Instances>:

---

## ✅ 확인

브라우저에서 접속:

- <http://EC2_PUBLIC_IP:8502/Player_Stats>

투수 통계 탭이 보이면 성공! 🎉
