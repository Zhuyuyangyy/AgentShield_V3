@echo off
cd /d "%~dp0backend"
echo ==============================================
echo   AgentShield V3 - AI安全代理防护框架
echo ==============================================
echo.
echo [启动] 服务运行于 http://localhost:8090
echo [启动] API文档: http://localhost:8090/docs
echo.
python app.py
