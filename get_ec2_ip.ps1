# AWS EC2 IP 주소 확인 도우미
# 이 스크립트는 AWS 콘솔을 브라우저로 열어줍니다

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "🌐 AWS EC2 IP 주소 확인" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

Write-Host "📋 안내:" -ForegroundColor Yellow
Write-Host "  1. 브라우저가 자동으로 AWS EC2 콘솔을 엽니다" -ForegroundColor Gray
Write-Host "  2. AWS 계정으로 로그인하세요" -ForegroundColor Gray
Write-Host "  3. 'kbo-stats-server' 인스턴스를 찾으세요" -ForegroundColor Gray
Write-Host "  4. '퍼블릭 IPv4 주소'를 복사하세요" -ForegroundColor Gray
Write-Host ""

Write-Host "브라우저를 여시겠습니까? (Y/N): " -ForegroundColor Green -NoNewline
$response = Read-Host

if ($response -eq 'Y' -or $response -eq 'y') {
    Write-Host ""
    Write-Host "🌐 AWS EC2 콘솔을 여는 중..." -ForegroundColor Yellow
    Start-Process "https://console.aws.amazon.com/ec2/home#Instances:"
    
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
    Write-Host "✅ 브라우저에서 IP 주소를 확인하세요" -ForegroundColor Green
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
    Write-Host ""
    Write-Host "📝 IP 주소를 확인한 후:" -ForegroundColor Cyan
    Write-Host "   .\check_aws_status.ps1 [IP주소]" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "   예시: .\check_aws_status.ps1 43.200.4.183" -ForegroundColor Gray
    Write-Host ""
}
else {
    Write-Host ""
    Write-Host "취소되었습니다." -ForegroundColor Gray
    Write-Host ""
    Write-Host "수동으로 확인하려면:" -ForegroundColor Yellow
    Write-Host "  https://console.aws.amazon.com/ec2/home#Instances:" -ForegroundColor Gray
    Write-Host ""
}
