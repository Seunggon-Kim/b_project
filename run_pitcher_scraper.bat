@echo off
REM KBO 투수 통계 수집 배치 파일

cd /d C:\Users\USERNAME\Desktop\b_project

echo ========================================
echo KBO 투수 통계 수집 시작
echo 시작 시간: %date% %time%
echo ========================================

echo.
echo Selenium 크롤링 중...
py data_collection\selenium_pitcher_scraper.py

echo.
echo ========================================
echo 작업 완료
echo 종료 시간: %date% %time%
echo ========================================

pause
