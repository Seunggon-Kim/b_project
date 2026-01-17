# EC2 빠른 업데이트 가이드 (PuTTY 없이!)

## 🚀 가장 쉬운 방법: PowerShell 사용

### 1단계: PowerShell 스크립트 실행

```powershell
.\connect_ec2.ps1
```

또는 직접 명령어:

```powershell
ssh -i C:\Users\USERNAME\.ssh\kbo-key.pem ubuntu@EC2_PUBLIC_IP
```

### 2단계: EC2에 접속되면 다음 명령어 실행

```bash
cd ~/b_project
git pull
sudo systemctl restart kbo-dashboard
```

### 3단계: 확인

```bash
sudo systemctl status kbo-dashboard
```

정상이면 `active (running)` 표시됨

### 4단계: 종료

```bash
exit
```

---

## 🎯 한 번에 실행 (자동화)

접속 없이 바로 업데이트:

```powershell
ssh -i C:\Users\USERNAME\.ssh\kbo-key.pem ubuntu@EC2_PUBLIC_IP "cd ~/b_project && git pull && sudo systemctl restart kbo-dashboard && sudo systemctl status kbo-dashboard --no-pager"
```

---

## ❌ SSH 연결 오류 시

### 오류 1: "Permission denied"

키 파일 권한 문제. 다음 명령어 실행:

```powershell
icacls C:\Users\USERNAME\.ssh\kbo-key.pem /inheritance:r
icacls C:\Users\USERNAME\.ssh\kbo-key.pem /grant:r "$($env:USERNAME):(R)"
```

### 오류 2: "Connection timed out"

1. AWS 보안 그룹에서 SSH(22번 포트) 허용 확인
2. EC2 인스턴스가 실행 중인지 확인
3. 인터넷 연결 확인

### 오류 3: "Host key verification failed"

```powershell
ssh-keygen -R EC2_PUBLIC_IP
```

---

## 🔧 PuTTY 설치 (선택사항)

PuTTY를 사용하고 싶다면:

### 다운로드

<https://www.putty.org/>

또는 PowerShell로 설치:

```powershell
winget install PuTTY.PuTTY
```

### PuTTY 사용법

1. **PuTTY 실행**
2. **Host Name**: `ubuntu@EC2_PUBLIC_IP`
3. **Port**: `22`
4. **Connection > SSH > Auth > Credentials**:
   - Private key file: `C:\Users\USERNAME\.ssh\kbo-key.pem` 선택
5. **Open** 클릭

---

## 📋 전체 업데이트 절차

```powershell
# 1. 로컬에서 Git push (이미 완료)
git push

# 2. EC2 접속
ssh -i C:\Users\USERNAME\.ssh\kbo-key.pem ubuntu@EC2_PUBLIC_IP

# 3. EC2에서 실행
cd ~/b_project
git pull
sudo systemctl restart kbo-dashboard

# 4. 확인
sudo systemctl status kbo-dashboard

# 5. 종료
exit
```

---

## 🌐 브라우저에서 확인

<http://EC2_PUBLIC_IP:8502>

투수 통계 탭이 보이면 성공! 🎉

---

## 💡 팁

### 빠른 접속 별칭 만들기

PowerShell 프로필에 추가:

```powershell
notepad $PROFILE
```

다음 내용 추가:

```powershell
function ec2 {
    ssh -i C:\Users\USERNAME\.ssh\kbo-key.pem ubuntu@EC2_PUBLIC_IP
}

function ec2-update {
    ssh -i C:\Users\USERNAME\.ssh\kbo-key.pem ubuntu@EC2_PUBLIC_IP "cd ~/b_project && git pull && sudo systemctl restart kbo-dashboard"
}
```

저장 후 사용:

```powershell
ec2          # EC2 접속
ec2-update   # 자동 업데이트
```
