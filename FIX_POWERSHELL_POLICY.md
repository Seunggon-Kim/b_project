# 🔓 PowerShell 스크립트 실행 권한 설정 가이드

## ⚠️ 오류 메시지

```
이 시스템에서 스크립트를 실행할 수 없으므로 파일을 로드할 수 없습니다.
PSSecurityException
UnauthorizedAccess
```

---

## ✅ 해결 방법 (1분 소요)

### 1단계: 실행 정책 변경

PowerShell에서 아래 명령어를 **복사해서 실행**하세요:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 2단계: 확인 메시지

다음과 같은 메시지가 나타납니다:

```
실행 정책 변경
실행 정책은 신뢰하지 않는 스크립트로부터 사용자를 보호합니다. 
실행 정책을 변경하면 about_Execution_Policies 도움말 항목(https://go.microsoft.com/fwlink/?LinkID=135170)에 
설명된 보안 위험에 노출될 수 있습니다. 
실행 정책을 변경하시겠습니까?
[Y] 예(Y)  [A] 모두 예(A)  [N] 아니요(N)  [L] 모두 아니요(L)  [S] 일시 중단(S)  [?] 도움말 (기본값은 "N"):
```

**`Y` 또는 `A`를 입력**하고 Enter를 누르세요.

### 3단계: 완료 확인

아무 메시지 없이 프롬프트로 돌아오면 성공입니다!

```powershell
PS C:\Users\USERNAME\Desktop\b_project>
```

---

## 🚀 이제 스크립트 실행

권한 설정 후, 다시 실행하세요:

```powershell
.\get_ec2_ip.ps1
```

---

## 📋 전체 과정 (복사해서 사용)

```powershell
# 1. 실행 정책 변경
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Y 또는 A 입력 후 Enter

# 2. EC2 IP 확인 스크립트 실행
.\get_ec2_ip.ps1

# 3. 상태 확인 (IP 주소 변경 필요)
.\check_aws_status.ps1 EC2_PUBLIC_IP
```

---

## 🔍 실행 정책이란?

**RemoteSigned** 정책:

- ✅ 로컬에서 작성한 스크립트는 실행 가능
- ✅ 인터넷에서 다운로드한 스크립트는 서명 필요
- ✅ 현재 사용자에게만 적용 (시스템 전체에 영향 없음)
- ✅ 안전하고 권장되는 설정

---

## 🛡️ 보안 참고사항

이 설정은:

- ✅ **안전합니다** - Microsoft 권장 설정
- ✅ **현재 사용자만** 영향받음
- ✅ **시스템 전체** 설정은 변경하지 않음
- ✅ **언제든지 되돌릴 수 있음**

---

## 🔄 설정 되돌리기 (필요시)

나중에 원래대로 되돌리려면:

```powershell
Set-ExecutionPolicy -ExecutionPolicy Restricted -Scope CurrentUser
```

---

## ❌ 다른 오류가 발생하는 경우

### 오류: "관리자 권한이 필요합니다"

**해결:**

1. PowerShell을 **관리자 권한**으로 실행
2. 시작 메뉴 → PowerShell 우클릭 → "관리자 권한으로 실행"
3. 위 명령어 다시 실행

### 오류: "레지스트리 키에 액세스할 수 없습니다"

**해결:**

```powershell
# 현재 세션에만 적용 (임시)
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
```

---

## 📚 관련 문서

- [Microsoft 공식 문서](https://go.microsoft.com/fwlink/?LinkID=135170)
- [START_HERE.md](./START_HERE.md) - 다음 단계
- [POWERSHELL_GUIDE.md](./POWERSHELL_GUIDE.md) - PowerShell 가이드

---

**작성일:** 2026-01-15  
**목적:** PowerShell 스크립트 실행 권한 오류 해결
