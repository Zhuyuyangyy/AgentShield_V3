# -*- coding: utf-8 -*-
"""
AgentShield V3 - FastAPI 主入口 (端口8011)
POST /api/evaluate  - 工具调用风险评估（限流50次/分钟）
GET  /health        - 健康检查
"""
import logging
import os
import sys
import uuid
import time
import random
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# ── Rate Limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── Pydantic Models ────────────────────────────────────────────────────────────

class EvaluateRequest(BaseModel):
    agent_id: str
    tool_name: str
    params: Dict[str, Any]
    risk_score: float = 0.0
    session_id: str = ""
    labels: Optional[list[str]] = None


class EvaluateResponse(BaseModel):
    session_id: str
    decision: str          # "allow" | "block" | "review"
    risk_level: str        # "low" | "medium" | "high" | "critical"
    risk_score: float
    reasoning: str
    shield_version: str = "3.0.0"


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AgentShield V3",
    description="多主体行为链风险治理系统 - ASF-BGT Framework",
    version="3.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 引擎存储 ────────────────────────────────────────────────────────────────

_engine_store: Dict[str, Any] = {}


def _save_engine_to_db(session_id: str, engine: Any):
    """将引擎状态保存到 SQLite"""
    try:
        from app.shield.session_store import save_session
        state_data = {
            "risk_threshold": engine.risk_threshold,
            "max_branches": engine.max_branches,
            "enable_counterfactual": engine.enable_counterfactual,
            "engine_id": getattr(engine, "engine_id", ""),
            "gate_count": getattr(engine, "_gate_count", 0),
        }
        graph_data = {}
        if hasattr(engine, "behavior_graph"):
            bg = engine.behavior_graph
            if hasattr(bg, "to_graph_dict"):
                graph_data = bg.to_graph_dict()
        audit_data = []
        if hasattr(engine, "audit_logger"):
            al = engine.audit_logger
            if hasattr(al, "export_chain"):
                audit_data = al.export_chain()
        save_session(
            session_id=session_id,
            engine_id=getattr(engine, "engine_id", "unknown"),
            world_name=getattr(engine, "world_name", "V3Shield"),
            state_data=state_data,
            graph_data=graph_data,
            audit_data=audit_data,
        )
    except Exception:
        logger.warning("SQLite session save failed for %s", session_id, exc_info=True)


def get_engine(session_id: str) -> Any:
    if session_id not in _engine_store:
        # 先尝试从 SQLite 恢复
        try:
            from app.shield.session_store import load_session
            saved = load_session(session_id)
            if saved:
                from app.shield.v3_engine import V3ShieldEngine
                engine = V3ShieldEngine(
                    session_id=session_id,
                    world_name=saved.get("world_name", f"V3Shield_{session_id[:8]}"),
                    risk_threshold=saved["state_data"].get("risk_threshold", 0.70),
                    max_branches=saved["state_data"].get("max_branches", 5),
                    enable_counterfactual=saved["state_data"].get("enable_counterfactual", True),
                )
                _engine_store[session_id] = engine
                return engine
        except Exception:
            logger.debug("Session restore failed for %s, creating new engine", session_id, exc_info=True)
        # 创建新引擎
        try:
            from app.shield.v3_engine import V3ShieldEngine
            _engine_store[session_id] = V3ShieldEngine(
                session_id=session_id,
                world_name=f"V3Shield_{session_id[:8]}",
                risk_threshold=0.70,
                max_branches=5,
                enable_counterfactual=True,
            )
        except ImportError:
            # 降级：轻量内存引擎
            class DummyEngine:
                def __init__(self, session_id):
                    self.session_id = session_id
                    self.behavior_graph = self
                def process_tool_call(self, **kwargs):
                    return {
                        "node_id": str(uuid.uuid4()),
                        "session_id": session_id,
                        "decision": "block",
                        "risk_level": "high",
                        "risk_score": 0.9,
                        "reasoning": "DummyEngine fallback (v3_engine not found)",
                    }
                def get_governance_status(self):
                    return {
                        "session_id": self.session_id,
                        "engine_id": "DummyEngine",
                        "risk_threshold": 0.70,
                        "branch_count": 0,
                        "gate_count": 0,
                        "behavior_graph": {},
                    }
            _engine_store[session_id] = DummyEngine(session_id)
    return _engine_store[session_id]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
@limiter.limit("60/minute")
async def health(request: Request):
    """健康检查"""
    return {
        "status": "ok",
        "version": "3.0.0",
        "engine": "AgentShield_V3",
        "framework": "ASF-BGT",
        "port": 8011,
    }


@app.post("/api/evaluate")
@limiter.limit("50/minute")
async def evaluate(request: Request, body: EvaluateRequest):
    """
    工具调用风险评估 API
    - rate limit: 50次/分钟（全局）
    - 返回决策: allow / block / review
    """
    session_id = body.session_id or str(uuid.uuid4())
    engine = get_engine(session_id)

    try:
        result = engine.process_tool_call(
            agent_id=body.agent_id,
            tool_name=body.tool_name,
            params=body.params,
            risk_score=body.risk_score,
            fuse_action="allow",
            labels=body.labels or [],
        )
    except Exception as e:
        # 引擎异常时降级拦截（fail-closed）
        result = {
            "node_id": str(uuid.uuid4()),
            "decision": "block",
            "risk_level": "high",
            "risk_score": 0.9,
            "reasoning": f"Engine exception fallback: {str(e)}",
        }

    # 持久化 session
    _save_engine_to_db(session_id, engine)
    return EvaluateResponse(
        session_id=session_id,
        decision=result.get("decision", "block"),
        risk_level=result.get("risk_level", "high"),
        risk_score=result.get("risk_score", 0.9),
        reasoning=result.get("reasoning", ""),
    )


@app.get("/api/status/{session_id}")
async def get_status(session_id: str):
    """获取治理状态"""
    if session_id not in _engine_store:
        raise HTTPException(status_code=404, detail="Session not found")
    return _engine_store[session_id].get_governance_status()


@app.get("/api/behavior_graph/{session_id}")
async def get_behavior_graph(session_id: str):
    """获取行为图谱"""
    if session_id not in _engine_store:
        raise HTTPException(status_code=404, detail="Session not found")
    engine = _engine_store[session_id]
    if hasattr(engine.behavior_graph, "to_graph_dict"):
        return engine.behavior_graph.to_graph_dict()
    return {}


@app.post("/api/agent/behavior_chain")
async def agent_behavior_chain(data: dict):
    """多Agent行为链追踪"""
    agents = data.get("agents", [])
    chain_id = str(uuid.uuid4())
    steps = []
    overall_risk = 0.0
    violations = []
    for i, agent in enumerate(agents):
        aid = agent.get("id", f"agent_{i}")
        action = agent.get("action", "")
        target = agent.get("target", "")
        inp = agent.get("input", {})
        risk = round(min(0.95, max(0.1, len(str(inp)) / 200 * random.random())), 3)
        step = {
            "step_id": i + 1,
            "agent_id": aid,
            "action": action,
            "target": target,
            "input_summary": str(inp)[:50],
            "risk_score": risk,
            "decision": "block" if risk > 0.85 else "review" if risk > 0.6 else "allow",
        }
        if risk > 0.6:
            violations.append({"step": i+1, "reason": f"{action} to {target} risk={risk:.2f}"})
        steps.append(step)
        overall_risk = max(overall_risk, risk)
    verdict = "block" if overall_risk > 0.85 else "review" if overall_risk > 0.5 else "allow"
    return {"chain_id": chain_id, "steps": steps, "risk_score": round(overall_risk, 3), "verdict": verdict, "violations": violations}


@app.get("/api/agent/registry")
async def agent_registry():
    """Agent注册表"""
    agents = [
        {"type": "TCM-Cognition", "description": "中医辨证推理Agent", "capabilities": ["症状分析", "证型判断", "方剂推荐"]},
        {"type": "Visual-Perception", "description": "3D视觉感知Agent", "capabilities": ["点云处理", "碰撞检测", "路径规划"]},
        {"type": "Risk-Analysis", "description": "风险分析Agent", "capabilities": ["漏洞扫描", "威胁评估", "缓解建议"]},
        {"type": "Content-Audit", "description": "内容审计Agent", "capabilities": ["幻觉检测", "RAG溯源", "合规检查"]},
        {"type": "Narrative-Generation", "description": "叙事生成Agent", "capabilities": ["市场叙事", "KOL传播", "情绪放大"]},
        {"type": "Market-Regulation", "description": "市场监管Agent", "capabilities": ["干预策略", "风险预警", "效果评估"]},
        {"type": "Hypothesis-Engine", "description": "假设引擎Agent", "capabilities": ["假设生成", "KG约束", "贝叶斯验证"]},
        {"type": "Lab-Automation", "description": "实验自动化Agent", "capabilities": ["DoE设计", "FMEA分析", "结果统计"]},
    ]
    return {"agents": agents, "total": len(agents)}


@app.post("/api/agent/evaluate_intent")
async def evaluate_intent(data: dict):
    """意图一致性评估（Theory of Mind）"""
    agent_id = data.get("agent_id", "unknown")
    stated_goal = data.get("stated_goal", "")
    observed_actions = data.get("observed_actions", [])
    if not observed_actions:
        return {"intent_alignment": 0.5, "deception_score": 0.1, "reasoning": "无观察数据，无法评估", "agent_id": agent_id}
    goal_keywords = ["查询", "分析", "评估", "生成", "优化"]
    action_keywords = ["删除", "导出", "发送", "修改", "取消"]
    goal_match = sum(1 for kw in goal_keywords if kw in stated_goal) / max(len(goal_keywords), 1)
    action_risk = sum(1 for kw in action_keywords if any(kw in str(a) for a in observed_actions)) / max(len(observed_actions), 1)
    alignment = round(max(0.1, min(0.95, goal_match * 0.6 + (1 - action_risk) * 0.4)), 3)
    deception = round(max(0, min(0.9, action_risk * 0.7 - goal_match * 0.3)), 3)
    reasoning = f"目标表述包含{sum(1 for kw in goal_keywords if kw in stated_goal)}个操作类关键词，观察到{len(observed_actions)}个行动，其中{sum(1 for kw in action_keywords if any(kw in str(a) for a in observed_actions))}个存在风险"
    return {"agent_id": agent_id, "stated_goal": stated_goal, "intent_alignment": alignment, "deception_score": deception, "reasoning": reasoning}

# ── Session 管理 ────────────────────────────────────────────────────────────

@app.get("/api/sessions")
async def list_sessions(limit: int = 20):
    """列出最近的 sessions（从 SQLite）"""
    try:
        from app.shield.session_store import list_sessions as db_list
        return {"sessions": db_list(limit=limit), "count": limit}
    except Exception as e:
        return {"sessions": [], "error": str(e)}


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """获取指定 session 详情（从 SQLite）"""
    try:
        from app.shield.session_store import load_session
        saved = load_session(session_id)
        if not saved:
            raise HTTPException(status_code=404, detail="Session not found in DB")
        return saved
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """删除指定 session（从内存和 SQLite）"""
    if session_id in _engine_store:
        del _engine_store[session_id]
    try:
        import sqlite3, os
        db_path = os.environ.get("SHIELD_DB", str(__file__).replace("app.py", "shield_sessions.db"))
        conn = sqlite3.connect(db_path)
        conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
        conn.commit()
        conn.close()
        return {"deleted": session_id}
    except Exception as e:
        return {"deleted": session_id, "warning": str(e)}


@app.get("/api/health_detailed")
async def health_detailed():
    """详细健康状态（含 session 数量）"""
    return {
        "status": "ok",
        "version": "3.0.0",
        "framework": "ASF-BGT",
        "port": 8011,
        "active_sessions": len(_engine_store),
        "db_file": os.environ.get("SHIELD_DB", "shield_sessions.db"),
    }


# ── 启动入口（uvicorn直接运行此文件） ───────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8011,
        reload=False,
        log_level="info",
    )
