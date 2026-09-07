@echo off
rem Double-click friendly wrapper. Extra arguments are passed through, e.g.  build_exe.bat -Online -Launch
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_exe.ps1" %*
if errorlevel 1 (
    echo.
    echo BUILD FAILED
    pause
    exit /b 1
)
echo.
echo BUILD OK
pause
