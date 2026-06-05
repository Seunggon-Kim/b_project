# EC2 SSH 접속 스크립트 (PuTTY 불필요!)
# PowerShell에서 바로 실행 가능

$EC2_IP = "43.200.4.183"
$KEY_PATH = "C:\Users\김승곤\.ssh\kbo-key.pem"
$USER = "ubuntu"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "EC2 서버 접속 준비" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 키 파일 권한 확인
if (Test-Path $KEY_PATH) {
    Write-Host "✅ SSH 키 파일 확인: $KEY_PATH" -ForegroundColor Green
}
else {
    Write-Host "❌ SSH 키 파일을 찾을 수 없습니다: $KEY_PATH" -ForegroundColor Red
    exit 1
}

Write-Host "`n📡 EC2 서버에 접속 중..." -ForegroundColor Yellow
Write-Host "서버: $USER@$EC2_IP" -ForegroundColor Yellow
Write-Host ""
Write-Host "접속 후 다음 명령어를 실행하세요:" -ForegroundColor Cyan
Write-Host "  cd ~/b_project" -ForegroundColor White
Write-Host "  git pull" -ForegroundColor White
Write-Host "  sudo systemctl restart kbo-dashboard" -ForegroundColor White
Write-Host ""
Write-Host "종료하려면: exit 입력" -ForegroundColor Yellow
Write-Host "========================================`n" -ForegroundColor Cyan

# SSH 접속
ssh -i $KEY_PATH $USER@$EC2_IP
