@echo off
REM run.bat — Start MedSure Vision backend on Windows
REM Usage: run.bat

cd /d "%~dp0"

REM Seed the database on first run
python scripts\seed_db.py

REM Start the server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
