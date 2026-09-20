from pathlib import Path
p = Path('backend/app/api/routes.py')
src = p.read_text(encoding='utf-8')

def resolve(old_block, new_block):
    global src
    assert src.count(old_block) == 1, f"{src.count(old_block)}: {old_block[:60]!r}"
    src = src.replace(old_block, new_block)

# 冲突 1: imports — 合并两侧
resolve('''<<<<<<< HEAD
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)
=======
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
>>>>>>> origin/main''',
'''from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)''')

# 冲突 2: 引擎注册 — 保留远端 storage/TTL，同时接入共享 registry
resolve('''<<<<<<< HEAD
# \u2500\u2500\u2500 \u5168\u5c40\u5f15\u64ce\u5b9e\u4f8b\u5b58\u50a8 \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# \u5f15\u64ce\u6ce8\u518c\u8868\u96c6\u4e2d\u5728 app.engine_registry\uff0c\u4e0e backend/app.py\uff08\u7aef\u53e3 8090 \u5165\u53e3\uff09
# \u5171\u7528\uff0c\u4fdd\u8bc1\u540c\u4e00 session \u65e0\u8bba\u8d70\u54ea\u4e2a\u5165\u53e3\u90fd\u5bf9\u5e94\u540c\u4e00\u4e2a\u5f15\u64ce\u3002


def get_or_create_engine(session_id: str) -> Any:
    """\u83b7\u53d6\u6216\u521b\u5efa V3 \u5f15\u64ce\u5b9e\u4f8b"""
    from app.engine_registry import get_or_create_engine as _get

    return _get(session_id)
=======
# \u2500\u2500\u2500 Production Components \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

_storage: StorageBackend = get_storage()
_ttl_manager = SessionTTLManager(
    cleanup_callback=lambda sid: _storage.delete_session(sid),
)''',
'''# \u2500\u2500\u2500 Production Components \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

_storage: StorageBackend = get_storage()
_ttl_manager = SessionTTLManager(
    cleanup_callback=lambda sid: _storage.delete_session(sid),
)


def get_or_create_engine(session_id: str, tenant_id: str = "default") -> Any:
    """\u83b7\u53d6\u6216\u521b\u5efa V3 \u5f15\u64ce\u5b9e\u4f8b\u3002

    \u5f15\u64ce\u672c\u8eab\u7531 app.engine_registry \u7ef4\u62a4\uff08\u4e0e backend/app.py \u7684 8090 \u5165\u53e3\u5171\u4eab\uff0c
    \u5e76\u5e26 TTL + LRU \u5bb9\u91cf\u4e0a\u9650\uff09\uff1b\u8fd9\u91cc\u5728\u5176\u4e0a\u9762\u8fdb\u884c\u591a\u79df\u6237 TTL \u8bb0\u5f55\u3002
    """
    from app.engine_registry import get_or_create_engine as _registry_get

    ttl_meta = _ttl_manager.get_session(session_id)
    if ttl_meta is None:
        _ttl_manager.register_session(session_id, tenant_id=tenant_id)
    else:
        _ttl_manager.touch_session(session_id)

    _ttl_manager.maybe_cleanup()
    return _registry_get(session_id)''')

p.write_text(src, encoding='utf-8')
print("resolved 2 of 6")
