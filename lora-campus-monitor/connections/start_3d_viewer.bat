@echo off
rem Double-click to open the 3D wiring viewer (Windows). Needs Python 3.7+.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 start_3d_viewer.py %*
) else (
    python start_3d_viewer.py %*
)
if errorlevel 1 (
    echo.
    echo Python 3 was not found or the viewer failed to start.
    echo Install Python from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
    echo Or open the ready-made pictures in the 3d\images folder.
)
pause
