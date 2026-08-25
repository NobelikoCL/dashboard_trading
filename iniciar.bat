@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Primero ejecute configurar.bat
  pause
  exit /b 1
)
if not exist "config.json" (
  echo Primero ejecute configurar.bat
  pause
  exit /b 1
)
echo Capturadora activa. Use Ctrl+C para detenerla.
.venv\Scripts\python.exe collector.py
pause
