@echo off
echo =========================================================
echo Regenerating E-Commerce Executive Profitability Dashboard
echo =========================================================

REM Check if local virtual environment exists
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" generate_dashboard.py %*
) else (
    python generate_dashboard.py %*
)

if %ERRORLEVEL% equ 0 (
    echo.
    echo =========================================================
    echo Dashboard successfully generated: dashboard.html
    echo Opening dashboard in your default web browser...
    echo =========================================================
    start dashboard.html
) else (
    echo.
    echo [ERROR] Dashboard generation failed with code %ERRORLEVEL%.
)

