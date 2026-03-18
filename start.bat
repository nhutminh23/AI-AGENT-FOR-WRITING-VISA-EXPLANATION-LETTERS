@echo off
chcp 65001 >nul
echo ============================================
echo   AI Visa Explanation Letter Generator
echo ============================================
echo.

:: ---- Auto-detect or create venv ----
set VENV_DIR=
if exist myenv\Scripts\activate.bat set VENV_DIR=myenv
if exist venv\Scripts\activate.bat if "%VENV_DIR%"=="" set VENV_DIR=venv
if exist .venv\Scripts\activate.bat if "%VENV_DIR%"=="" set VENV_DIR=.venv

if "%VENV_DIR%"=="" (
    echo [*] Lan dau chay - tao moi truong ao...
    :: Try py launcher first (finds newest Python), then python3, then python
    where py >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        py -3 -m venv myenv
    ) else (
        where python3 >nul 2>nul
        if %ERRORLEVEL% equ 0 (
            python3 -m venv myenv
        ) else (
            python -m venv myenv
        )
    )
    set VENV_DIR=myenv
    echo ✅ Da tao moi truong ao!
) else (
    echo ✅ Moi truong ao: %VENV_DIR%
)

:: ---- Check Python version in venv ----
%VENV_DIR%\Scripts\python.exe -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)" 2>nul
if %ERRORLEVEL% neq 0 (
    %VENV_DIR%\Scripts\python.exe --version
    echo ❌ Python trong %VENV_DIR% qua cu! Can Python 3.9 tro len.
    echo    Xoa thu muc %VENV_DIR% va cai Python 3.10+ roi chay lai.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('%VENV_DIR%\Scripts\python.exe --version 2^>^&1') do echo ✅ %%v

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
