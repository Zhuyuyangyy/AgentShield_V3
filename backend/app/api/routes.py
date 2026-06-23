"""
AgentShield V3 - FastAPI Routes
处理工具调用请求 + 行为链治理 + 分支推演
"""

from __future__ import annotations
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.shield.storage import get_storage, StorageBackend
from app.security.auth import verify_api_key
from app.security.tenant import (
    extract_tenant_from_request,
    get_current_tenant,
    set_current_tenant,
    tenant_scoped_key,
    TenantContext,
)
from app.shield.session_ttl import SessionTTLManager
from app.shield.audit_log import AppendOnlyAuditLog


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


# ─── Production Components ──────────────────────────────────────

_storage: StorageBackend = get_storage()
_ttl_manager = SessionTTLManager(
    cleanup_callback=lambda sid: _storage.delete_session(sid),
)
_audit_log = AppendOnlyAuditLog()


def get_or_create_engine(session_id: str, tenant_id: str = "default") -> Any:
    """获取或创建 V3 引擎实例（使用生产存储后端）"""
    scoped_key = tenant_scoped_key(session_id, tenant_id)

    # Check TTL
    ttl_meta = _ttl_manager.get_session(session_id)
    if ttl_meta is None:
        # Session expired or new
        state = _storage.load_session(scoped_key)
        if state and "engine" in state:
            # Re-register with TTL
            _ttl_manager.register_session(
                session_id, tenant_id=tenant_id, engine_id=state.get("engine_id", "")
            )
            _ttl_manager.touch_session(session_id)
            return state["engine"]

    # Create new engine
    from app.shield.v3_engine import V3ShieldEngine
    engine = V3ShieldEngine(
        session_id=session_id,
        world_name=f"V3Shield_{session_id[:8]}",
        risk_threshold=0.70,
        max_branches=5,
        enable_counterfactual=True,
    )

    # Save to storage
    engine_state = {
        "engine": engine,
        "engine_id": engine.world_name,
        "session_id": session_id,
        "tenant_id": tenant_id,
    }
    _storage.save_session(scoped_key, engine_state)

    # Register with TTL
    _ttl_manager.register_session(
        session_id, tenant_id=tenant_id, engine_id=engine.world_name
    )

    # Audit log
    _audit_log.append(
        event="session_created",
        session_id=session_id,
        data={"engine_id": engine.world_name},
        tenant_id=tenant_id,
    )

    return engine


def _get_engine_from_store(session_id: str, tenant_id: str = "default") -> Any:
    """从存储中获取引擎实例，不存在则抛出 404"""
    scoped_key = tenant_scoped_key(session_id, tenant_id)

    # Check TTL first
    ttl_meta = _ttl_manager.get_session(session_id)
    if ttl_meta is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    _ttl_manager.touch_session(session_id)

    state = _storage.load_session(scoped_key)
    if state is None or "engine" not in state:
        raise HTTPException(status_code=404, detail="Session not found")

    return state["engine"]


# ─── Router ────────────────────────────────────────────────────

router = APIRouter(prefix="/api/v3", tags=["AgentShield V3"])


@router.post("/process_call")
async def process_call(
    req: ProcessCallRequest,
    actor: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    处理单个工具调用请求 → 行为图谱 + 分支推演 + 治理决策
    """
    session_id = req.session_id or str(uuid.uuid4())
    tenant_id = get_current_tenant()
    engine = get_or_create_engine(session_id, tenant_id)

    result = engine.process_tool_call(
        agent_id=req.agent_id,
        tool_name=req.tool_name,
        params=req.params,
        risk_score=req.risk_score,
        fuse_action=req.fuse_action,
        parent_node_id=req.parent_node_id,
        labels=req.labels,
    )

    # Save updated state
    scoped_key = tenant_scoped_key(session_id, tenant_id)
    _storage.save_session(scoped_key, {
        "engine": engine,
        "engine_id": engine.world_name,
        "session_id": session_id,
        "tenant_id": tenant_id,
    })

    # Audit log
    _audit_log.append(
        event="process_call",
        session_id=session_id,
        data={
            "agent_id": req.agent_id,
            "tool_name": req.tool_name,
            "risk_score": req.risk_score,
            "fuse_action": req.fuse_action,
        },
        actor=actor,
        decision=result.get("decision", ""),
        risk_score=req.risk_score,
    )

    # Periodic TTL cleanup
    _ttl_manager.maybe_cleanup()

    return result


@router.get("/status/{session_id}")
async def get_status(
    session_id: str,
    actor: str = Depends(verify_api_key),
) -> GovernanceStatusResponse:
    """获取治理状态"""
    tenant_id = get_current_tenant()
    engine = _get_engine_from_store(session_id, tenant_id)
    status = engine.get_governance_status()
    return GovernanceStatusResponse(**status)


@router.post("/fork_branch")
async def fork_branch(
    req: ForkBranchRequest,
    actor: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """主动创建分支（手动干预点）"""
    session_id = req.session_id or str(uuid.uuid4())
    tenant_id = get_current_tenant()
    engine = get_or_create_engine(session_id, tenant_id)

    branch_id = engine.fork_branch(
        branch_label=req.branch_label,
        intervention=req.intervention,
    )

    # Save updated state
    scoped_key = tenant_scoped_key(session_id, tenant_id)
    _storage.save_session(scoped_key, {
        "engine": engine,
        "engine_id": engine.world_name,
        "session_id": session_id,
        "tenant_id": tenant_id,
    })

    # Audit log
    _audit_log.append(
        event="fork_branch",
        session_id=session_id,
        data={"branch_id": branch_id, "branch_label": req.branch_label},
        actor=actor,
    )

    return {
        "branch_id": branch_id,
        "session_id": session_id,
        "message": f"分支已创建: {req.branch_label}",
    }


@router.get("/export_chain/{session_id}")
async def export_chain(
    session_id: str,
    actor: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """导出完整行为链（用于前端可视化）"""
    tenant_id = get_current_tenant()
    engine = _get_engine_from_store(session_id, tenant_id)
    return engine.export_chain()


@router.get("/behavior_graph/{session_id}")
async def get_behavior_graph(
    session_id: str,
    actor: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """获取行为图谱"""
    tenant_id = get_current_tenant()
    engine = _get_engine_from_store(session_id, tenant_id)
    return engine.behavior_graph.to_graph_dict()


@router.post("/simulate_steps")
async def simulate_steps(
    session_id: str,
    steps: int = 5,
    actor: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    运行多步仿真（扩展点：接LLM生成行为）
    """
    tenant_id = get_current_tenant()
    engine = _get_engine_from_store(session_id, tenant_id)
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


@router.get("/audit/records")
async def get_audit_records(
    limit: int = 50,
    session_id: Optional[str] = None,
    actor: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """获取审计日志记录"""
    records = _audit_log.query(session_id=session_id)
    return {
        "records": _audit_log.export_records(limit=limit),
        "total": _audit_log.record_count,
        "chain_valid": _audit_log.verify_chain(),
    }


@router.get("/sessions")
async def list_sessions(
    limit: int = 20,
    actor: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """列出所有会话"""
    sessions = _storage.list_sessions(limit=limit)
    ttl_stats = _ttl_manager.get_stats()
    return {
        "sessions": sessions,
        "ttl_stats": ttl_stats,
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    actor: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """删除会话"""
    tenant_id = get_current_tenant()
    scoped_key = tenant_scoped_key(session_id, tenant_id)
    deleted = _storage.delete_session(scoped_key)
    _ttl_manager.remove_session(session_id)

    _audit_log.append(
        event="session_deleted",
        session_id=session_id,
        data={"deleted": deleted},
        actor=actor,
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"session_id": session_id, "deleted": True}
