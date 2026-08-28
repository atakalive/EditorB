@echo off
cd /d "%~dp0"
where python >nul 2>nul && (python "tools\register_filetype.py" --unregister) || (py -3 "tools\register_filetype.py" --unregister)
pause
