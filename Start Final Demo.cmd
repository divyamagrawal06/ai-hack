@echo off
cd /d "%~dp0"
python -X utf8 tools\start_demo.py --port 8081 --db var\demo-final.sqlite3
if errorlevel 1 pause
