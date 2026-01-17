@echo off
REM KBO 투수 통계 자동 수집 배치 파일
REM Windows 작업 스케줄러에서 실행 가능

cd /d C:\Users\USERNAME\Desktop\b_project

echo ========================================
echo KBO 투수 통계 자동 수집 시작
echo 시작 시간: %date% %time%
echo ========================================

REM 1. Selenium 크롤링
echo.
echo [1/3] Selenium 크롤링 중...
py data_collection\selenium_pitcher_scraper.py
set CRAWL_RESULT=%ERRORLEVEL%

if %CRAWL_RESULT% NEQ 0 (
    echo ❌ 크롤링 실패
    py data_collection\email_notifier.py --fail --error "투수 Selenium 크롤링 실패"
    exit /b 1
)

REM 2. DB 저장
echo.
echo [2/3] DB 저장 중...
py data_collection\pitcher_to_db.py
set DB_RESULT=%ERRORLEVEL%

if %DB_RESULT% NEQ 0 (
    echo ❌ DB 저장 실패
    py data_collection\email_notifier.py --fail --error "투수 DB 저장 실패"
    exit /b 1
)

REM 3. 이메일 알림 (성공)
echo.
echo [3/3] 이메일 발송 중...
py data_collection\email_notifier.py --success

echo.
echo ========================================
echo ✅ 모든 작업 완료
echo 종료 시간: %date% %time%
echo ========================================

exit /b 0
