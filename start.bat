@echo off
cd /d "%~dp0backend"
echo Starting AgentShield V3 Backend on port 8011...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8011
