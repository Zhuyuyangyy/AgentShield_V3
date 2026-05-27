#!/bin/bash
# AgentShield 启动脚本
# AI安全代理防护框架 V1 - FastAPI后端

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=============================================="
echo "  AgentShield - AI安全代理防护框架 V1"
echo "=============================================="
echo

# 虚拟环境
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

pip install -q fastapi uvicorn pydantic python-dotenv 2>/dev/null

echo "[启动] 服务运行于 http://localhost:8000"
echo "[启动] API文档: http://localhost:8000/docs"
cd "$SCRIPT_DIR/backend/app"
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload