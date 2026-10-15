@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Execute INSTALAR_WINDOWS.cmd primeiro.
    pause
    exit /b 1
)
cd tcc-web
echo Painel: http://127.0.0.1:8000/
"..\.venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
pause
