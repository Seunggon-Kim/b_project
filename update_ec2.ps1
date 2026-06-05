# EC2 상태 확인 및 업데이트 스크립트

$EC2_IP = "43.200.4.183"
$KEY_PATH = "C:\Users\김승곤\.ssh\kbo-key.pem"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "EC2 서버 상태 확인" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. EC2 서버 핑 테스트
Write-Host "`n1️⃣ 서버 연결 테스트 중..." -ForegroundColor Yellow
$ping = Test-Connection -ComputerName $EC2_IP -Count 2 -Quiet

if ($ping) {
    Write-Host "✅ 서버 응답 확인" -ForegroundColor Green
}
else {
    Write-Host "❌ 서버 응답 없음" -ForegroundColor Red
    Write-Host "`n⚠️ EC2 인스턴스가 중지되었을 수 있습니다." -ForegroundColor Yellow
    Write-Host "AWS 콘솔에서 인스턴스를 시작하세요:" -ForegroundColor Yellow
    Write-Host "https://ap-northeast-2.console.aws.amazon.com/ec2/home?region=ap-northeast-2#Instances:" -ForegroundColor Cyan
    exit 1
}

# 2. SSH 포트 확인
Write-Host "`n2️⃣ SSH 포트(22) 확인 중..." -ForegroundColor Yellow
$tcpClient = New-Object System.Net.Sockets.TcpClient
try {
    $tcpClient.Connect($EC2_IP, 22)
    $tcpClient.Close()
    Write-Host "✅ SSH 포트 열림" -ForegroundColor Green
}
catch {
    Write-Host "❌ SSH 포트 닫힘" -ForegroundColor Red
    Write-Host "`n⚠️ 보안 그룹에서 SSH(22번 포트)를 허용해야 합니다." -ForegroundColor Yellow
    exit 1
}

# 3. Git pull 및 재시작
Write-Host "`n3️⃣ EC2 업데이트 중..." -ForegroundColor Yellow
Write-Host ""

$commands = @"
cd ~/b_project
echo '📥 Git pull...'
git pull
echo ''
echo '🔄 대시보드 재시작...'
sudo systemctl restart kbo-dashboard
echo '✅ 완료!'
echo ''
echo '📊 서비스 상태:'
sudo systemctl status kbo-dashboard --no-pager | head -10
"@

ssh -i $KEY_PATH -o ConnectTimeout=10 ubuntu@$EC2_IP $commands

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "✅ 업데이트 완료!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "`n🌐 대시보드: http://43.200.4.183:8502" -ForegroundColor Green
    Write-Host "🎯 투수 통계 확인: http://43.200.4.183:8502/Player_Stats" -ForegroundColor Green
}
else {
    Write-Host "`n❌ 업데이트 실패" -ForegroundColor Red
    Write-Host "수동으로 접속하려면: .\connect_ec2.ps1" -ForegroundColor Yellow
}
