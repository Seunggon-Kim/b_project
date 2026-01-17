@echo off
REM KBO 공식 통계 전체 자동 수집 배치 파일 (타자 + 투수)
REM Windows 작업 스케줄러에서 실행 가능

cd /d C:\Users\USERNAME\Desktop\b_project

echo ========================================
echo KBO 공식 통계 전체 자동 수집 시작
echo 시작 시간: %date% %time%
echo ========================================

REM ============================================
REM 1. 타자 통계 수집
REM ============================================
echo.
echo ========================================
echo [1/2] 타자 통계 수집 시작
echo ========================================

REM 1-1. 타자 크롤링
echo.
echo [1-1] 타자 Selenium 크롤링 중...
py data_collection\selenium_batter_scraper.py
set BATTER_CRAWL_RESULT=%ERRORLEVEL%

if %BATTER_CRAWL_RESULT% NEQ 0 (
    echo ❌ 타자 크롤링 실패
    py data_collection\email_notifier.py --fail --error "타자 Selenium 크롤링 실패"
    exit /b 1
)

REM 1-2. 타자 DB 저장
echo.
echo [1-2] 타자 DB 저장 중...
py data_collection\kbo_to_db.py
set BATTER_DB_RESULT=%ERRORLEVEL%

if %BATTER_DB_RESULT% NEQ 0 (
    echo ❌ 타자 DB 저장 실패
    py data_collection\email_notifier.py --fail --error "타자 DB 저장 실패"
    exit /b 1
)

echo ✅ 타자 통계 수집 완료

REM ============================================
REM 2. 투수 통계 수집
REM ============================================
echo.
echo ========================================
echo [2/2] 투수 통계 수집 시작
echo ========================================

REM 2-1. 투수 크롤링
echo.
echo [2-1] 투수 Selenium 크롤링 중...
py data_collection\selenium_pitcher_scraper.py
set PITCHER_CRAWL_RESULT=%ERRORLEVEL%

if %PITCHER_CRAWL_RESULT% NEQ 0 (
    echo ❌ 투수 크롤링 실패
    py data_collection\email_notifier.py --fail --error "투수 Selenium 크롤링 실패"
    exit /b 1
)

REM 2-2. 투수 DB 저장
echo.
echo [2-2] 투수 DB 저장 중...
py data_collection\pitcher_to_db.py
set PITCHER_DB_RESULT=%ERRORLEVEL%

if %PITCHER_DB_RESULT% NEQ 0 (
    echo ❌ 투수 DB 저장 실패
    py data_collection\email_notifier.py --fail --error "투수 DB 저장 실패"
    exit /b 1
)

echo ✅ 투수 통계 수집 완료

REM ============================================
REM 3. 이메일 알림 (성공)
REM ============================================
echo.
echo ========================================
echo [3/3] 이메일 발송 중...
echo ========================================
py data_collection\email_notifier.py --success

echo.
echo ========================================
echo ✅ 모든 작업 완료
echo 종료 시간: %date% %time%
echo ========================================

exit /b 0
