"""
AgentShield V3 - FastAPI Routes
处理工具调用请求 + 行为链治理 + 分支推演
"""

from __future__ import annotations
import logging
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ─── Request/Response Models ────────────────────────────────────

@dataclass
class ToolCallRequest:
    """V3 工具调用请求（兼容 V2 ToolCallRequest 格式）"""
    tool_name: str
    params: Dict[str, Any]
    agent_id: str = "unknown"
    session_id: str = ""
    is_database_tool: bool = False
    is_network_tool: bool = False
    risk_score: float = 0.0
    fuse_action: str = "allow"


class ProcessCallRequest(BaseModel):
    agent_id: str
    tool_name: str
    params: Dict[str, Any]
    risk_score: float
    fuse_action: str
    session_id: str = ""
    parent_node_id: Optional[str] = None
    labels: Optional[List[str]] = None


class ForkBranchRequest(BaseModel):
    branch_label: str
    intervention: Dict[str, Any]
    session_id: str = ""


class GovernanceStatusResponse(BaseModel):
    session_id: str
    engine_id: str
    risk_threshold: float
    branch_count: int
    behavior_graph: Dict[str, Any]
    gate_count: int
    # Present in the engine payload but not part of the public contract;
    # tolerated so extra keys never break deserialisation.
    world_state_keys: List[str] = Field(default_factory=list)
    # Shared-registry view (active sessions, TTL, capacity cap).
    registry: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


# ─── 全局引擎实例存储 ────────────────────────────────────────────────
# 引擎注册表集中在 app.engine_registry，与 backend/app.py（端口 8090 入口）
# 共用，保证同一 session 无论走哪个入口都对应同一个引擎。


def get_or_create_engine(session_id: str) -> Any:
    """获取或创建 V3 引擎实例"""
    from app.engine_registry import get_or_create_engine as _get

    return _get(session_id)


# ─── Router ────────────────────────────────────────────────────

router = APIRouter(prefix="/api/v3", tags=["AgentShield V3"])


@router.post("/process_call")
async def process_call(req: ProcessCallRequest) -> Dict[str, Any]:
    """
    处理单个工具调用请求 → 行为图谱 + 分支推演 + 治理决策
    """
    session_id = req.session_id or str(uuid.uuid4())
    engine = get_or_create_engine(session_id)

    result = engine.process_tool_call(
        agent_id=req.agent_id,
        tool_name=req.tool_name,
        params=req.params,
        risk_score=req.risk_score,
        fuse_action=req.fuse_action,
        parent_node_id=req.parent_node_id,
        labels=req.labels,
    )
    # 与 8090 入口保持一致：把 session 落盘，重启后可恢复。
    _persist_session(session_id, engine)
    return result


def _persist_session(session_id: str, engine: Any) -> None:
    """把引擎状态异步写入 SQLite（失败不影响请求结果）。

    复用 app.shield.persistence 的非阻塞实现，与 8090 入口共用同一套
    去重/补写逻辑；在非异步上下文（如同步测试）下它会自动同步写入。
    """
    try:
        from app.shield.persistence import save_engine_state

        save_engine_state(session_id, engine)
    except Exception:  # pragma: no cover - 持久化是最佳努力
        logger.warning("Session persist failed for %s", session_id, exc_info=True)


def get_existing_engine_or_404(session_id: str) -> Any:
    """按 session_id 取已有引擎；不存在则 404（不触发创建或加载）。"""
    from app.engine_registry import get_existing_engine

    engine = get_existing_engine(session_id)
    if engine is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return engine


@router.get("/status/{session_id}")
async def get_status(session_id: str) -> GovernanceStatusResponse:
    """获取治理状态"""
    engine = get_existing_engine_or_404(session_id)
    status = engine.get_governance_status()
    return GovernanceStatusResponse(**status)


@router.post("/fork_branch")
async def fork_branch(req: ForkBranchRequest) -> Dict[str, Any]:
    """主动创建分支（手动干预点）"""
    session_id = req.session_id or str(uuid.uuid4())
    engine = get_or_create_engine(session_id)

    branch_id = engine.fork_branch(
        branch_label=req.branch_label,
        intervention=req.intervention,
    )
    return {
        "branch_id": branch_id,
        "session_id": session_id,
        "message": f"分支已创建: {req.branch_label}",
    }


@router.get("/export_chain/{session_id}")
async def export_chain(session_id: str) -> Dict[str, Any]:
    """导出完整行为链（用于前端可视化）"""
    engine = get_existing_engine_or_404(session_id)
    return engine.export_chain()


@router.get("/behavior_graph/{session_id}")
async def get_behavior_graph(session_id: str) -> Dict[str, Any]:
    """获取行为图谱"""
    engine = get_existing_engine_or_404(session_id)
    return engine.behavior_graph.to_graph_dict()


@router.post("/simulate_steps")
async def simulate_steps(
    session_id: str,
    steps: int = 5,
) -> Dict[str, Any]:
    """
    运行多步仿真（扩展点：接LLM生成行为）
    """
    engine = get_existing_engine_or_404(session_id)
    # 简单模拟：生成 N 个假想步骤
    for i in range(steps):
        engine.process_tool_call(
            agent_id=f"agent_{i}",
            tool_name="simulated_call",
            params={"step": i},
            risk_score=0.1 * i,
            fuse_action="allow",
        )
    return {
        "session_id": session_id,
        "steps_run": steps,
        "behavior_graph": engine.behavior_graph.summary(),
    }
