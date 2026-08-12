@echo off
REM Double-click this file inside the extracted package folder (or copy it next to the exe).
cd /d "%~dp0"
if exist "terminal-insight-v2.exe" (
  set "TARGET=%cd%"
) else if exist "..\terminal-insight-v2.exe" (
  cd ..
  set "TARGET=%cd%"
) else (
  set "TARGET=%cd%"
)
echo Unblocking: %TARGET%
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '%TARGET%' -Recurse -Force | Unblock-File -ErrorAction SilentlyContinue"
echo.
echo Done. Now start terminal-insight-v2.exe
pause
