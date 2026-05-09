"""
V3AuditLogger - 轻量级审计日志（V3专用）
提供与 ASF-BGT AuditLogger 不同的简化接口
"""

from __future__ import annotations

import time
import uuid
import json
import hashlib
from typing import Any, Dict, List, Optional


class V3AuditLogger:
    """
    V3 引擎专用审计日志
    简化接口：log(event, session_id, data)
    """

    def __init__(self, file_path: Optional[str] = None):
        self.records: List[Dict[str, Any]] = []
        self.file_path = file_path
        self._last_hash = "0" * 64

    def log(self, event: str, session_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """追加一条审计记录"""
        ts = time.time()
        record = {
            "record_id": f"rec_{uuid.uuid4().hex[:12]}",
            "event": event,
            "session_id": session_id,
            "data": data,
            "timestamp": ts,
            "previous_hash": self._last_hash,
        }
        record["record_hash"] = self._compute_hash(record)
        self.records.append(record)
        self._last_hash = record["record_hash"]
        return record

    def _compute_hash(self, record: Dict[str, Any]) -> str:
        """计算记录哈希（防篡改）"""
        h = {
            "record_id": record["record_id"],
            "event": record["event"],
            "session_id": record["session_id"],
            "data": json.dumps(record["data"], sort_keys=True, ensure_ascii=False),
            "timestamp": record["timestamp"],
            "previous_hash": record["previous_hash"],
        }
        return hashlib.sha256(json.dumps(h, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def get_records(self) -> List[Dict[str, Any]]:
        return self.records

    def export_chain(self) -> List[Dict[str, Any]]:
        """导出完整审计链"""
        return self.records

    def summary(self) -> Dict[str, Any]:
        return {
            "total_records": len(self.records),
            "events": list(set(r["event"] for r in self.records)),
        }

    def verify_chain(self) -> bool:
        """验证链完整性（哈希连续性）"""
        for i, record in enumerate(self.records):
            if i == 0:
                if record["previous_hash"] != "0" * 64:
                    return False
            else:
                if record["previous_hash"] != self.records[i - 1]["record_hash"]:
                    return False
        return True