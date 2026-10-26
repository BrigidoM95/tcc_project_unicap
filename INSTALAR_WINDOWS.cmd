@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel% equ 0 (
    py -3 scripts\instalar_local.py
) else (
    python scripts\instalar_local.py
)
if errorlevel 1 (
    echo A instalacao encontrou um erro. Confira a mensagem acima.
    pause
    exit /b 1
)
pause
