@echo off
cd /d "%~dp0backend"
echo Installing dependencies...
pip install -r requirements.txt -q
echo.
echo Starting AgentShield V3 on port 8011...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8011 --reload
