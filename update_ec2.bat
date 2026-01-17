@echo off
REM EC2 서버 업데이트 (Git pull + 대시보드 재시작)

echo ========================================
echo EC2 서버 업데이트 시작
echo ========================================

REM SSH 키 경로 (실제 경로로 수정 필요)
set KEY_PATH=C:\Users\USERNAME\.ssh\kbo-key.pem
set EC2_IP=EC2_PUBLIC_IP

echo.
echo 📡 EC2 서버에 접속 중...
echo.

REM SSH로 명령 실행
ssh -i %KEY_PATH% ubuntu@%EC2_IP% "cd ~/b_project && echo '📥 Git pull 시작...' && git pull && echo '✅ Git pull 완료' && echo '' && echo '🔄 대시보드 재시작 중...' && sudo systemctl restart kbo-dashboard && echo '✅ 대시보드 재시작 완료' && echo '' && echo '📊 서비스 상태:' && sudo systemctl status kbo-dashboard --no-pager -l | head -20"

echo.
echo ========================================
echo ✅ 업데이트 완료!
echo ========================================
echo.
echo 🌐 대시보드 접속: http://EC2_PUBLIC_IP:8502
echo.

pause
