@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  py -3 "tools\register_filetype.py"
) else (
  python "tools\register_filetype.py"
)
pause
