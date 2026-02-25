@echo off
chcp 65001 >nul
echo ============================================
echo   AI Visa Explanation Letter Generator
echo ============================================
echo.

:: ---- Check Python ----
python --version 2>nul
if %ERRORLEVEL% neq 0 (
    echo ❌ Khong tim thay Python! Cai dat Python 3.10+ tu:
    echo    https://www.python.org/downloads/
    echo    Nho tich "Add Python to PATH" khi cai dat.
    pause
    exit /b 1
)

python -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)" 2>nul
if %ERRORLEVEL% neq 0 (
    echo ❌ Python qua cu! Can Python 3.9 tro len.
    python --version
    pause
    exit /b 1
)

:: ---- Auto-detect or create venv ----
set VENV_DIR=
if exist venv\Scripts\activate.bat set VENV_DIR=venv
if exist myenv\Scripts\activate.bat set VENV_DIR=myenv
if exist .venv\Scripts\activate.bat set VENV_DIR=.venv

if "%VENV_DIR%"=="" (
    echo [*] Lan dau chay - tao moi truong ao...
    python -m venv venv
    set VENV_DIR=venv
    echo ✅ Da tao moi truong ao!
) else (
    echo ✅ Moi truong ao: %VENV_DIR%
)

:: ---- Activate ----
call %VENV_DIR%\Scripts\activate.bat

:: ---- Install/update dependencies ----
echo [*] Cap nhat thu vien...
pip install -r requirements.txt --quiet 2>nul
echo ✅ Thu vien OK!

:: ---- Ensure directories ----
if not exist input mkdir input
if not exist output mkdir output
if not exist output\cache mkdir output\cache

:: ---- Check .env ----
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
    ) else (
        echo OPENAI_API_KEY=YOUR_KEY_HERE>.env
        echo OPENAI_MODEL=gpt-4o-mini>>.env
    )
    echo.
    echo ⚠️  FILE .env CHUA CO API KEY!
    echo    Mo file .env va dien OPENAI_API_KEY truoc khi dung.
    echo    Sau do chay lai start.bat
    echo.
    start notepad .env
    pause
    exit /b 0
)

:: ---- Start server ----
echo.
echo ============================================
echo   🚀 Dang khoi dong server...
echo   Mo trinh duyet: http://127.0.0.1:8000
echo   Bam Ctrl+C de dung server
echo ============================================
echo.
start http://127.0.0.1:8000
python server.py
