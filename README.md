# AgentShield V3

**行为链审计与多智能体风险治理系统**

V3 是 AgentShield 的第三代产品，聚焦于**多智能体行为链路**的实时审计、风险溯源与反事实推演。

## 核心定位

> V1 管 AI 说什么 → V2 管 Agent 工具做什么 → **V3 管多 Agent 行为链为什么这样做**

## 技术架构

```
AgentShield V3
├── ASF-BGT Framework（基础框架）
│   ├── World（共享状态）
│   ├── BranchTree（分支演化树）
│   ├── Simulator（状态推演）
│   └── CounterfactualEngine（反事实引擎）
├── AgentBehaviorGraph（行为图，从V2继承）
│   ├── 节点：Tool Call / Decision Point
│   └── 边：因果关系 + 风险传播
├── V3AuditLogger（审计日志）
└── V3ShieldEngine（核心引擎）
    ├── 行为捕获与节点化
    ├── 风险传播计算
    ├── 分支What-If反事实推演
    └── 三级治理门控（ALLOW / REVIEW / BLOCK）
```

## 目录结构

```
AgentShield_V3/
├── backend/
│   ├── app/
│   │   ├── shield/
│   │   │   ├── v3_engine.py         # 核心引擎
│   │   │   ├── v3_audit_logger.py   # 审计日志
│   │   │   └── agent_behavior_graph.py  # 行为图
│   │   ├── api/
│   │   │   └── routes.py            # FastAPI路由
│   │   └── main.py                  # 服务入口（端口8011）
│   └── tests/
│       └── test_v3_engine.py        # 10/10测试全绿
├── benchmark/
│   ├── evaluate.py                  # 基准测试脚本
│   └── test_cases/
│       └── test_cases.json          # 30条测试用例
├── docs/                            # 项目文档
└── README.md
```

## 核心能力

### 1. 行为链捕获
- 工具调用 → 行为图节点（携带风险评分）
- 因果链追踪（parent_node_id）
- 多Agent并发场景下的独立会话管理

### 2. 风险传播
- 基于贝叶斯的风险传播算法
- `risk_propagation()` 从污点源向下游节点推算
- 关键节点识别（影响度高 + 风险高）

### 3. What-If 反事实推演
- 高风险场景自动触发反事实分析
- 对比：阻止 vs 放行 vs 变形后的风险变化
- `whatif_result.risk_delta` 量化干预效果

### 4. 三级治理门控

| 风险区间 | 动作 | 说明 |
|---------|------|------|
| < 0.70 | ALLOW | 自动放行 |
| 0.70-0.89 | REVIEW | 人工复核 |
| ≥ 0.90 | BLOCK | 自动拦截 |

## 基准测试

```bash
cd benchmark
python evaluate.py
```

**当前结果：30条测试用例，Score准确率 100%，Action准确率 80%**

| 类别 | Score准确 | Action准确 |
|------|---------|----------|
| sensitive_data_access | 8/8 | 6/8 |
| external_network_transfer | 5/5 | 4/5 |
| bulk_operations | 5/5 | 5/5 |
| privilege_escalation | 4/4 | 4/4 |
| behavior_chain_risk | 5/5 | 4/5 |
| governance_bypass | 3/3 | 1/3 |

## API

### POST /api/v3/process_call
处理工具调用并返回治理决策。

**请求体：**
```json
{
  "agent_id": "data_agent",
  "tool_name": "execute_sql",
  "params": {"query": "SELECT phone FROM customers"},
  "risk_score": 0.92,
  "fuse_action": "BLOCK"
}
```

**响应：**
```json
{
  "call_id": "call_abc123",
  "node_id": "node_xyz789",
  "gate_result": {"action": "BLOCK", "reason": "risk_score >= 0.90", "score": 0.92},
  "future_branches": ["Branch(...)", "Branch(...)"],
  "whatif_result": {"risk_delta": -0.46, "projected_outcome": {...}}
}
```

### GET /api/v3/status/{session_id}
查询会话的当前治理状态和行为链摘要。

## 端口

- **V3 Backend**: 8011
- **V2 Backend**: 8010
- **MarketingCouncil**: 8009
- **TCM-Mind-RAG**: 8000

## Git Tag

`agentshield-v3-bench-30` (本地 tag)