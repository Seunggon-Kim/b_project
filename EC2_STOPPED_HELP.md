# ⚠️ EC2 인스턴스 중지됨

## 🔴 문제

EC2 서버(EC2_PUBLIC_IP)에 연결할 수 없습니다.
인스턴스가 **중지(Stopped)** 상태일 가능성이 높습니다.

## ✅ 해결 방법

### 1. AWS 콘솔에서 인스턴스 시작

1. **AWS 콘솔 접속**:
   <https://ap-northeast-2.console.aws.amazon.com/ec2/home?region=ap-northeast-2#Instances>:

2. **인스턴스 선택**
   - KBO 대시보드 인스턴스 체크

3. **인스턴스 시작**
   - 우클릭 → "인스턴스 시작" 또는
   - 상단 "인스턴스 상태" → "인스턴스 시작"

4. **IP 주소 확인**
   - 퍼블릭 IPv4 주소가 변경되었을 수 있음
   - 새 IP 주소를 확인하세요

### 2. 인스턴스 시작 후

IP 주소가 **변경되지 않았다면** (여전히 EC2_PUBLIC_IP):

```powershell
.\update_ec2.ps1
```

IP 주소가 **변경되었다면**:

1. `update_ec2.ps1` 파일 수정:

   ```powershell
   $EC2_IP = "새로운_IP_주소"
   ```

2. `connect_ec2.ps1` 파일도 수정

3. 다시 실행:

   ```powershell
   .\update_ec2.ps1
   ```

---

## 💡 IP 주소 고정 (Elastic IP)

매번 IP가 바뀌는 것을 방지하려면:

1. **AWS 콘솔** → **EC2** → **탄력적 IP**
2. **탄력적 IP 주소 할당**
3. **주소 연결** → 인스턴스 선택
4. 이제 IP 주소가 고정됩니다!

---

## 🔧 자동 시작 설정 (선택사항)

EC2가 자동으로 중지되지 않도록:

1. **CloudWatch 알람 설정**
2. **Auto Scaling 그룹 사용**
3. **Lambda 함수로 자동 시작**

---

## 📞 빠른 체크리스트

- [ ] AWS 콘솔 접속
- [ ] EC2 인스턴스 상태 확인
- [ ] 인스턴스 시작
- [ ] IP 주소 확인 (변경 여부)
- [ ] `update_ec2.ps1` 실행
- [ ] 브라우저에서 확인: <http://EC2_PUBLIC_IP:8502>

---

## 🌐 현재 상태

로컬 작업은 모두 완료되었습니다:

- ✅ 투수 크롤러 생성
- ✅ DB 저장 (281명)
- ✅ 대시보드 코드 수정
- ✅ Git push 완료

**EC2만 업데이트하면 투수 데이터가 보입니다!**
