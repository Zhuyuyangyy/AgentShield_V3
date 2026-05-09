# AgentShield V3 - 多主体行为链风险治理系统

> 继承 ASF-BGT Framework + AgentShield V2  
> 端口：8011

## 核心定位

| 版本 | 管什么 | 粒度 | 核心能力 |
|------|--------|------|----------|
| V1 | AI "说什么" | 单次输出 | 幻觉检测 + RAG溯源 |
| V2 | Agent "做什么" | 单次工具调用 | 影子模拟 + 熔断 |
| **V3** | **多主体行为链** | **行为链 + 分支路径** | **未来推演 + What-if干预** |

## 技术架构

```
AgentShield V3
├── app/shield/v3_engine.py    ← V3核心引擎（继承ASF-BGT）
├── app/api/routes.py           ← FastAPI路由
├── ASF-BGT Framework          ← 核心骨架（World/Simulator/Gate/Audit）
└── agent-shield-v2             ← V2 AgentBehaviorGraph
```

## 核心流程

```
ToolCallRequest
    ↓
AgentBehaviorGraph（V2行为图谱）
    ↓ 风险传播计算
未来分支生成（N条候选行为链）
    ↓
GovernanceGate（BLOCK/REVIEW/ALLOW）
    ↓
Counterfactual What-if（高风险触发）
    ↓
最低风险路径执行 → AuditLogger（链式哈希不可篡改）
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v3/process_call` | POST | 处理工具调用 → 行为链治理 |
| `/api/v3/status/{session_id}` | GET | 治理状态 |
| `/api/v3/fork_branch` | POST | 主动创建分支（干预点） |
| `/api/v3/export_chain/{session_id}` | GET | 导出完整行为链 |
| `/api/v3/behavior_graph/{session_id}` | GET | 行为图谱 |
| `/api/v3/simulate_steps` | POST | 多步仿真 |

## 启动

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8011
```

## 测试

```bash
cd backend
pytest tests/test_v3_engine.py -v
```

## 继承说明

- **ASF-BGT Framework**：`D:\ZYY Project\ASF-BGT-Framework`（33/33测试全绿）
- **AgentShield V2**：`D:\ZYY Project\agent-shield-v2`（V2工具调用审计）
