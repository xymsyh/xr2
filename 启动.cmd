@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "启动.py" %*
) else (
    py -3.11 "启动.py" %*
)
if errorlevel 1 pause
endlocal
