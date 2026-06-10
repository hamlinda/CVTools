@echo off
:: CV Stream Tracker — Windows launcher
:: Double-click this file or run from any terminal.
:: Requires Python 3.8+ installed and on PATH (python.org installer, MS Store, or conda).

setlocal

:: Find python (try 'py' launcher first, then 'python', then 'python3')
where py     >nul 2>&1 && set PY=py     && goto :found
where python >nul 2>&1 && set PY=python && goto :found
where python3>nul 2>&1 && set PY=python3&& goto :found

echo.
echo  ERROR: Python not found on PATH.
echo  Install Python 3.8+ from https://python.org (check "Add to PATH" during setup).
echo.
pause
exit /b 1

:found
echo Using: %PY%
%PY% --version

:: Run the self-bootstrapping tracker
%PY% "%~dp0tracker.py"

if errorlevel 1 (
    echo.
    echo  tracker.py exited with an error — see messages above.
    pause
)
