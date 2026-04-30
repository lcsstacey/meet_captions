@echo off
REM ============================================================
REM  Lumen — launcher
REM
REM  Activates .venv and starts the app. Pass --visible to keep
REM  the console window open for logs.
REM ============================================================
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] No virtualenv found. Run setup.bat first.
  pause
  exit /b 1
)

REM Use pythonw for a clean, consoleless launch unless the user wants logs.
if /I "%~1"=="--visible" goto verbose

start "" ".venv\Scripts\pythonw.exe" -m app.main
exit /b 0

:verbose
".venv\Scripts\python.exe" -m app.main
exit /b %errorlevel%
