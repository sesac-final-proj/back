@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "PYTHONIOENCODING=utf-8"
set "PYTHON=..\.venv\Scripts\python.exe"
set "LOG=crawler.batch.log"
set "BATCH_ONCE=0"

if /I "%~1"=="--once" set "BATCH_ONCE=1"

if not exist "%PYTHON%" (
    echo Python virtual environment not found: %PYTHON%
    exit /b 1
)

:run
>>"%LOG%" echo [%date% %time%] Batch cycle started
"%PYTHON%" -B safecity_crawler.py --once >>"%LOG%" 2>&1
set "CRAWLER_EXIT=%ERRORLEVEL%"
>>"%LOG%" echo [%date% %time%] Batch cycle finished with exit code %CRAWLER_EXIT%

if "%BATCH_ONCE%"=="1" exit /b %CRAWLER_EXIT%

"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "Start-Sleep -Seconds 600"
goto run
