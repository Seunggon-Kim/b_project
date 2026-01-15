# AWS EC2 크롤링 상태 빠른 확인 스크립트
# 사용법: .\check_aws_status.ps1 [EC2_IP주소]

param(
    [Parameter(Mandatory=$false)]
    [string]$EC2_IP = ""
)

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "🔍 AWS EC2 크롤링 상태 확인" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# EC2 IP 주소 확인
if ($EC2_IP -eq "") {
    Write-Host "❌ EC2 IP 주소를 입력하세요." -ForegroundColor Red
    Write-Host ""
    Write-Host "사용법:" -ForegroundColor Yellow
    Write-Host "  .\check_aws_status.ps1 EC2_PUBLIC_IP" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "EC2 IP 주소 확인 방법:" -ForegroundColor Yellow
    Write-Host "  1. AWS 콘솔 접속 (https://aws.amazon.com/ko/)" -ForegroundColor Gray
    Write-Host "  2. EC2 → 인스턴스 → kbo-stats-server 클릭" -ForegroundColor Gray
    Write-Host "  3. '퍼블릭 IPv4 주소' 복사" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

# SSH 키 파일 확인
$SSH_KEY = "$HOME\.ssh\kbo-key.pem"
if (-not (Test-Path $SSH_KEY)) {
    Write-Host "❌ SSH 키 파일이 없습니다: $SSH_KEY" -ForegroundColor Red
    Write-Host ""
    Write-Host "해결 방법:" -ForegroundColor Yellow
    Write-Host "  1. AWS EC2 콘솔에서 키 페어 다운로드" -ForegroundColor Gray
    Write-Host "  2. 다운로드한 kbo-key.pem 파일을 $HOME\.ssh\ 폴더로 이동" -ForegroundColor Gray
    Write-Host "  3. 권한 설정:" -ForegroundColor Gray
    Write-Host "     icacls $SSH_KEY /inheritance:r" -ForegroundColor DarkGray
    Write-Host "     icacls $SSH_KEY /grant:r `"$env:USERNAME`:R`"" -ForegroundColor DarkGray
    Write-Host ""
    exit 1
}

Write-Host "✅ SSH 키 파일 확인 완료" -ForegroundColor Green
Write-Host ""

# SSH 명령어 생성
$TODAY = Get-Date -Format "yyyyMMdd"
$SSH_CMD = @"
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
echo '📋 1. Crontab 설정 확인'
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
crontab -l
echo ''
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
echo '📊 2. 최근 로그 파일 목록'
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
ls -lht ~/b_project/logs/*.log 2>/dev/null | head -5 || echo '❌ 로그 파일 없음'
echo ''
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
echo '📝 3. Cron 로그 (최근 30줄)'
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
tail -n 30 ~/b_project/logs/cron.log 2>/dev/null || echo '❌ cron.log 파일 없음'
echo ''
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
echo '🤖 4. 오늘 크롤러 로그 (최근 50줄)'
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
tail -n 50 ~/b_project/logs/selenium_batter_$TODAY.log 2>/dev/null || echo '❌ 오늘 크롤러 로그 없음'
echo ''
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
echo '💾 5. 데이터베이스 파일 정보'
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
ls -lh ~/b_project/database/kbo_stats.db 2>/dev/null || echo '❌ DB 파일 없음'
echo ''
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
echo '📧 6. 이메일 설정 확인'
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
cat ~/b_project/config/email_config.json 2>/dev/null || echo '❌ 이메일 설정 파일 없음'
echo ''
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
echo '🔧 7. Cron 서비스 상태'
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
sudo systemctl status cron --no-pager | head -10
echo ''
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
echo '💿 8. 디스크 공간'
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
df -h | grep -E '(Filesystem|/$)'
echo ''
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
echo '✅ 확인 완료'
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
"@

Write-Host "🔌 EC2 서버 접속 중: $EC2_IP" -ForegroundColor Yellow
Write-Host ""

# SSH 접속 및 명령 실행
ssh -i $SSH_KEY -o StrictHostKeyChecking=no ubuntu@$EC2_IP $SSH_CMD

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
    Write-Host "✅ 상태 확인 완료" -ForegroundColor Green
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
    Write-Host ""
    Write-Host "📋 다음 단계:" -ForegroundColor Cyan
    Write-Host "  1. 위 로그를 확인하여 문제 파악" -ForegroundColor Gray
    Write-Host "  2. 문제가 있다면 check_aws_logs.md 참고" -ForegroundColor Gray
    Write-Host "  3. 수동 크롤링 필요 시:" -ForegroundColor Gray
    Write-Host "     ssh -i $SSH_KEY ubuntu@$EC2_IP" -ForegroundColor DarkGray
    Write-Host "     cd ~/b_project && source venv/bin/activate" -ForegroundColor DarkGray
    Write-Host "     python data_collection/selenium_batter_scraper.py" -ForegroundColor DarkGray
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Red
    Write-Host "❌ 접속 실패" -ForegroundColor Red
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Red
    Write-Host ""
    Write-Host "확인 사항:" -ForegroundColor Yellow
    Write-Host "  1. EC2 인스턴스가 실행 중인지 확인 (AWS 콘솔)" -ForegroundColor Gray
    Write-Host "  2. EC2 IP 주소가 올바른지 확인" -ForegroundColor Gray
    Write-Host "  3. 보안 그룹에서 SSH(22) 포트가 열려 있는지 확인" -ForegroundColor Gray
    Write-Host "  4. SSH 키 파일이 올바른지 확인" -ForegroundColor Gray
    Write-Host ""
}
