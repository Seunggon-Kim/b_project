# 대시보드(dashboard_js) 정적 파일을 EC2로 배포
# nginx가 ~/b_project/dashboard_js/ 를 직접 서빙하므로 scp만 하면 즉시 반영 (재시작 불필요)
# 주의: api/main.py 는 서버에 별도 버전(회사 라우트 포함)이 있어 여기서 건드리지 않습니다.

$ErrorActionPreference = "Stop"
$cfg = Join-Path $PSScriptRoot 'ec2_config.local.ps1'
if (-not (Test-Path $cfg)) {
    Write-Host "[ERROR] ec2_config.local.ps1 가 없습니다. IP/키를 설정하세요." -ForegroundColor Red
    exit 1
}
. $cfg

if (-not (Test-Path $KEY_PATH)) {
    Write-Host "[ERROR] SSH 키를 찾을 수 없습니다: $KEY_PATH" -ForegroundColor Red
    exit 1
}

$src = Join-Path $PSScriptRoot 'dashboard_js'
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "대시보드 배포 -> ${EC2_USER}@${EC2_IP}:~/b_project/dashboard_js/" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

scp -i $KEY_PATH -r $src "${EC2_USER}@${EC2_IP}:~/b_project/"

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[OK] 배포 완료 — https://bstats.duckdns.org/kbo/ 에서 확인 (강력 새로고침 Ctrl+F5)" -ForegroundColor Green
} else {
    Write-Host "`n[FAIL] 배포 실패 (exit $LASTEXITCODE)" -ForegroundColor Red
}
