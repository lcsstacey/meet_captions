@echo off
REM ============================================================
REM  Lumen — one-time setup for Windows
REM
REM  Creates a local virtualenv in .venv and installs every
REM  dependency from requirements.txt. Re-run safely; it's idempotent.
REM ============================================================
setlocal

cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel% neq 0 (
  echo [ERROR] Python launcher 'py' not found. Install Python 3.11+
  echo         from https://www.python.org/downloads/windows/ and re-run.
  pause
  exit /b 1
)

if not exist ".venv" (
  echo [1/3] Creating virtual environment in .venv ...
  py -3 -m venv .venv || goto :fail
) else (
  echo [1/3] Virtual environment already exists.
)

echo [2/3] Upgrading pip ...
".venv\Scripts\python.exe" -m pip install --upgrade pip wheel >nul || goto :fail

echo [3/3] Installing dependencies ...
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail

if not exist ".env" (
  echo.
  echo [INFO] No .env found. Creating a template — add your GEMINI_API_KEY.
  > .env echo GEMINI_API_KEY=
)

echo.
echo  Setup complete. Launch with:  run.bat
echo.
exit /b 0

:fail
echo.
echo [ERROR] Setup failed. See the output above.
pause
exit /b 1
