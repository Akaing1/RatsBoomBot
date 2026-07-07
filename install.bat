@echo off
setlocal

echo ========================================
echo RatsBoomBot Installer
echo ========================================
echo.

where py >nul 2>nul
if %errorlevel% neq 0 (
    echo Python launcher "py" was not found.
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo Checking Python version...
py --version
echo.

echo Creating virtual environment...
py -m venv .venv

if %errorlevel% neq 0 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
)

echo.
echo Upgrading pip...
call .venv\Scripts\python.exe -m pip install --upgrade pip

echo.
echo Installing requirements...
call .venv\Scripts\pip.exe install -r requirements.txt

if %errorlevel% neq 0 (
    echo Failed to install requirements.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Install complete!
echo ========================================
echo.
echo To run the bot, use:
echo run.bat
echo.

if not exist .env (
    echo No .env file found.
    echo Creating .env from .env.example if available...
    if exist .env.example (
        copy .env.example .env
        echo Created .env. Please edit it with your Twitch credentials.
    ) else (
        echo No .env.example found. Please create a .env file manually.
    )
)

pause