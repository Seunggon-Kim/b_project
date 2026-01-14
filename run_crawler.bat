@echo off
REM KBO 크롤러 실행 배치 파일
REM Anaconda 환경에서 자동 실행

echo ========================================
echo KBO 2025 크롤러 실행
echo ========================================
echo.

REM Anaconda 환경 활성화
call C:\ProgramData\Anaconda3\Scripts\activate.bat base 2>nul
if errorlevel 1 (
    call %USERPROFILE%\anaconda3\Scripts\activate.bat base 2>nul
)
if errorlevel 1 (
    call %USERPROFILE%\Anaconda3\Scripts\activate.bat base 2>nul
)

REM 크롤러 디렉토리로 이동
cd /d "%~dp0crawler"

REM 2025년 전체 경기 크롤링 (이미 있는 파일은 스킵)
echo 2025년 전체 경기 크롤링 중...
echo 이미 있는 파일은 자동으로 스킵됩니다.
echo.
python pbp.py -f 20250101 -t 20251231 -j

echo.
echo ========================================
echo 완료! 결과 확인 중...
echo ========================================
echo.
echo 수집된 파일 수:
dir save\2025\*.csv /b | find /c ".csv"
echo.
echo 통합 파일:
dir save\2025.csv 2>nul
if errorlevel 1 (
    echo 통합 파일이 생성되지 않았습니다. 로그를 확인하세요.
    type log.txt
)

pause
