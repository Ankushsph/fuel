@echo off
REM Start Flask app using conda environment
echo Starting Flask app with conda environment 'fuelflux'...
cd /d "%~dp0"

REM Use direct path to Python in conda environment
set PYTHON_PATH=%USERPROFILE%\anaconda3\envs\fuelflux\python.exe

if exist "%PYTHON_PATH%" (
    echo Using conda environment: fuelflux
    echo Starting Flask app...
    echo.
    "%PYTHON_PATH%" app.py
) else (
    echo ERROR: Python not found at %PYTHON_PATH%
    echo Please check your Anaconda installation.
    pause
    exit /b 1
)

pause

