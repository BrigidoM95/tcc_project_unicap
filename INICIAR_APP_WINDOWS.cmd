@echo off
setlocal
cd /d "%~dp0"
call flutter pub get
if errorlevel 1 goto falha
call flutter run -d chrome --web-port=8080 --dart-define=API_URL=http://127.0.0.1:8000/
if errorlevel 1 goto falha
exit /b 0
:falha
echo Confira a instalacao do Flutter e mantenha o backend aberto.
pause
exit /b 1
