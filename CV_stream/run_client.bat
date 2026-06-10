@echo off
:: CV Stream — Windows client launcher
:: Run this on the Windows machine that has the webcam.
:: The ML inference runs on the Linux server; only opencv + requests are needed here.

setlocal

:: -------------------------------------------------------
:: Server address: set CV_SERVER in your environment, OR
:: pass it as the first argument, OR enter it when prompted.
:: -------------------------------------------------------
if not "%~1"=="" (
    set CV_SERVER=%~1
    goto :have_server
)

if not "%CV_SERVER%"=="" goto :have_server

set /p CV_SERVER="Linux server address (e.g. http://192.168.1.100:5000): "

:have_server
echo.
echo Connecting to: %CV_SERVER%
echo.

:: Find Python
where py     >nul 2>&1 && set PY=py     && goto :found
where python >nul 2>&1 && set PY=python && goto :found
where python3>nul 2>&1 && set PY=python3&& goto :found

echo.
echo  ERROR: Python not found on PATH.
echo  Install Python 3.8+ from https://python.org
echo  (check "Add Python to PATH" during setup)
echo.
pause
exit /b 1

:found
echo Using: %PY%
%PY% --version
echo.

%PY% "%~dp0tracker_client.py" %CV_SERVER%

if errorlevel 1 (
    echo.
    echo  tracker_client.py exited with an error — see messages above.
    pause
)
