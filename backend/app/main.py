"""
AgentShield V3 - FastAPI 主入口
端口：8011
继承 ASF-BGT Framework + V2 AgentBehaviorGraph
"""

import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as v3_router

app = FastAPI(
    title="AgentShield V3",
    description="多主体行为链风险治理系统 - 基于 ASF-BGT Framework",
    version="3.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 V3 路由
app.include_router(v3_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "3.0.0",
        "engine": "AgentShield_V3",
        "framework": "ASF-BGT",
    }


@app.get("/")
async def root():
    return {
        "message": "AgentShield V3 API",
        "docs": "/docs",
        "endpoints": {
            "process_call": "POST /api/v3/process_call",
            "status": "GET /api/v3/status/{session_id}",
            "fork_branch": "POST /api/v3/fork_branch",
            "export_chain": "GET /api/v3/export_chain/{session_id}",
            "behavior_graph": "GET /api/v3/behavior_graph/{session_id}",
            "simulate_steps": "POST /api/v3/simulate_steps",
        },
    }
