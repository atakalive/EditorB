@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  py -3 "tools\register_filetype.py" --unregister
) else (
  python "tools\register_filetype.py" --unregister
)
pause
