@echo off
cd /d "%~dp0"
py -3 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.11 or newer is required. Install Python from python.org and try again.
  pause
  exit /b 1
)
py -3 launch.py
if errorlevel 1 pause
