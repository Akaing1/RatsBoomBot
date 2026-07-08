@echo off
setlocal

if not exist .venv (
    echo Virtual environment not found.
    echo Run install.bat first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

python tray_launcher.py

pause