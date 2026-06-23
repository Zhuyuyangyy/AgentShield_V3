没有完全“完成”。准确说：

1. **路线规划层面：可以一次性给完整总路线，下面这条就是最终总控路线。**
2. **代码落地层面：我不能确认 GitHub main 已经完成全部实现和 push。** 公开仓库当前显示顶层目录包括 `.github/workflows`、`backend`、`benchmark`、`docs`、`frontend`、`papers`、`scripts`、`tests` 等，但没有在顶层直接看到 `sdk/` 目录；而你上传的执行日志里写到 Phase 8 / Phase 9 曾在 `/workspace` 下创建过 `paper_experiments.py`、SDK、Proxy Gateway、Console API 和路由注册。也就是说：**日志里显示本地工作区有推进，但公开仓库是否同步完成，需要重新跑测试和检查 git status / push 状态确认。**  当前公开 README 把 AgentShield V3 定义为多智能体工具调用系统的 behavior-chain risk governance 原型，并包含行为图建模、链式风险传播、ALLOW / HUMAN_REVIEW / BLOCK 三层门控、未来分支预测、反事实干预和审计链导出。([GitHub][1])

下面给你一版 **真正完整、可执行、从当前状态一路到最完美形态的总路线**。

---

# AgentShield_V3 最终路线总纲

AgentShield_V3 的最终形态不应该是一个普通 guardrail demo，而应该成为：

> **多智能体 / MCP / 工具调用系统的运行时安全治理层。**
> 它实时观察 Agent 行为链，构建行为图，传播组合风险，预测下游伤害，选择最优干预点，输出审计证据，并可接入企业安全体系。

最终不是：

```text
Prompt Guardrail
单步 Tool Call 分类器
关键词风险检测器
Demo Dashboard
```

而是：

```text
Agent Runtime Security Platform
= SDK
+ Gateway
+ MCP Proxy
+ Behavior Graph Risk Engine
+ Counterfactual Intervention Engine
+ Policy Engine
+ Audit Chain
+ SOC Console
+ Paper-grade Benchmark
+ Enterprise Deployment Stack
```

仓库自己的 `RESEARCH_VERDICT.md` 已经把核心问题说得很准：当前科学问题真实、概念框架正确，但实现存在标签泄漏、循环评估、弱基线、图推理未接入评分管线、反事实分析过于简化等致命问题。([GitHub][2]) 所以下一步不是盲目堆功能，而是围绕 **可信度闭环** 重构。

---

# 一、当前状态判定

## 1. 已有基础

公开仓库现在已经具备这些基础：

```text
backend/
benchmark/
docs/
frontend/
papers/
scripts/
tests/
Dockerfile
README.md
RESEARCH_VERDICT.md
REPRODUCE.md
```

README 显示系统已有行为图、风险传播、三层门控、未来分支预测、反事实干预、审计链导出、SCI-600 synthetic dataset、semi-real trace dataset、baseline comparison、ablation tooling 等。([GitHub][1])

上传日志中还显示，曾经推进过：

```text
Phase 8: paper_experiments.py
Phase 9: Python SDK
Phase 9: Proxy Gateway
Phase 9: Enterprise Console API
Phase 9: console_router 路由注册
```

并且日志写到 `paper_experiments.py` 包含 main comparison、ablation、leakage test、robustness test、latency benchmark、review cost analysis、case studies 七类实验。

## 2. 当前最关键问题

现在不能继续做“外观包装”，必须先修这些：

```text
P0-1：测试失败和测试语义错误
P0-2：risk_score 新旧逻辑不一致
P0-3：API world_name 属性错误
P0-4：端口 8011 / 8090 文档和测试不一致
P0-5：图推理仍可能没有真正主导 final risk
P0-6：反事实分析必须从 risk * 0.5 变成真实 replay
P0-7：标签泄漏与循环评估必须彻底移除
P0-8：强基线必须接入
P0-9：SDK / console / proxy 是否已经 push 到 GitHub 需要确认
```

上传日志明确分析过一个核心问题：新引擎已经从 raw `risk_score` 改成 `RiskSignalExtractor + GraphRiskState` 计算，并且如果传入 `risk_score > 0`，会用 `final_risk = 0.6 * computed_risk + 0.4 * risk_score` 混合，因此旧测试里“risk_score=0.95 必然 BLOCK”的预期已经不成立。

---

# 二、最终版本路线

总路线分 12 个阶段：

```text
V0.3.x  Stability：修测试、修文档、修端口、修 repo hygiene
V0.4.x  Research Fairness：去标签泄漏、强基线、公平评测
V0.5.x  Graph Risk：图推理真正接入 final risk
V0.6.x  Counterfactual：真实链级反事实 replay
V0.7.x  Secure Core：auth、policy、storage、audit
V0.8.x  MCP Shield Proxy：MCP 工具链安全代理
V0.9.x  SOC Dashboard：安全运营可视化台
V1.0    Paper-grade Release：论文级可复现版本
V1.5    SDK + Gateway：接入真实 Agent 框架
V2.0    Enterprise Runtime：多租户、RBAC、SIEM、OTel
V3.0    Adaptive Governance：反馈学习、策略推荐、红队
V4.0+   Perfect Form：完整 Agent Runtime Security Platform
```

---

# 三、V0.3.x：Stability，先把项目救稳

## 目标

让仓库进入“clone 后能跑、测试能过、文档一致、结果可复现”的状态。

## 任务 1：确认真实仓库状态

先执行：

```bash
git status
git branch -vv
git log --oneline -5
git remote -v
find . -maxdepth 2 -type d | sort
```

确认：

```text
1. Phase 8 / Phase 9 代码是否真的在当前仓库
2. 是否有未提交文件
3. 是否已经 push 到 origin/main
4. sdk/ 是否存在
5. backend/app/proxy/ 是否存在
6. backend/app/console/ 是否存在
7. benchmark/paper_experiments.py 是否存在
```

如果日志里显示完成，但仓库没有这些文件，就执行：

```bash
git add benchmark/paper_experiments.py sdk backend/app/proxy backend/app/console backend/app/main.py
git commit -m "feat: add paper experiments sdk proxy and enterprise console"
git push origin main
```

## 任务 2：统一端口

README 里 API 启动命令使用 `8011`。([GitHub][1]) 旧测试或文档如果还期待 `8090`，全部改成 `8011`。

统一：

```text
backend/app/main.py
backend/app.py
Dockerfile
docker-compose.yml
start.sh
start.bat
README.md
docs/USER_GUIDE.md
backend/tests/test_api_routes.py
```

标准：

```text
开发端口：8011
Docker 映射：8011:8011
文档示例：http://localhost:8011
测试断言：port == 8011
```

## 任务 3：修 `world_name` 错误

上传日志显示 API route 测试里出现过：

```text
AttributeError: 'V3ShieldEngine' object has no attribute 'world_name'
```

根因是 routes 访问了：

```python
engine.world_name
```

但实际应为：

```python
engine.world.name
```

修复：

```bash
grep -R "engine.world_name" -n backend
```

替换为：

```python
engine.world.name
```

如果 constructor 仍然传入 `world_name`，确认 `V3ShieldEngine.__init__` 是否接受该参数；不接受就改成：

```python
world=World(name=request.world_name)
```

或在 engine 内保留兼容属性：

```python
@property
def world_name(self) -> str:
    return self.world.name
```

更建议保留兼容属性，避免旧 API 断裂。

## 任务 4：修测试语义

旧测试问题是：把 raw `risk_score` 当成最终 risk。现在必须分成三类测试。

### A. 纯阈值测试

直接测：

```python
_action_for_score(0.1) == "ALLOW"
_action_for_score(0.7) == "HUMAN_REVIEW"
_action_for_score(0.95) == "BLOCK"
```

### B. 集成测试

不要再断言：

```python
risk_score == input_risk_score
```

而是断言：

```python
0 <= result["risk_score"] <= 1
result["gate_result"]["score"] == result["risk_score"]
decision 与 final_risk 区间一致
```

### C. 高风险测试

如果要稳定触发 BLOCK，不要靠普通 `send_email + risk_score=0.95`，因为新引擎会混合 computed risk，上传日志已经算出普通 `send_email` 最终可能只有约 0.44。

应该用 mock：

```python
def _make_risk_state(score: float):
    return GraphRiskState(
        local_risk=score,
        inherited_risk=score,
        downstream_exposure=score,
        path_risk=score,
        intervention_value=score,
        confidence=1.0,
        signals=[],
    )
```

然后 patch：

```python
with patch.object(
    engine._risk_extractor,
    "compute_graph_risk_state",
    return_value=_make_risk_state(0.95)
):
    result = engine.process_tool_call(...)
    assert result["decision"] == "block"
```

## 任务 5：更新 what-if 测试结构

新 `CounterfactualEngine` 输出不是旧结构。上传日志里写到新结构包含：

```text
scenario_id
removed_event_id
original_risk
modified_risk
risk_delta
prevented_downstream_risk
business_cost
net_value
downstream_events_affected
recommended
reason
```

所以旧测试：

```python
whatif["projected_outcome"]["projected_risk"]
```

要改成：

```python
assert whatif["modified_risk"] < whatif["original_risk"]
assert whatif["risk_delta"] < 0
assert "net_value" in whatif
```

## 任务 6：repo hygiene

`.gitignore` 必须加入：

```gitignore
*.db
*.sqlite
*.sqlite3
backend/*.db
.pytest_cache/
__pycache__/
.coverage
htmlcov/
benchmark/results/tmp/
```

删除运行态文件：

```bash
git rm --cached backend/shield_sessions.db || true
find . -name "__pycache__" -type d -prune -exec rm -rf {} +
find . -name ".pytest_cache" -type d -prune -exec rm -rf {} +
```

## V0.3 验收命令

```bash
python -m pytest -q
python benchmark/baselines.py
python benchmark/evaluate_semireal.py
python scripts/run_ablation.py --dataset sci
python scripts/run_ablation.py --dataset semireal
python benchmark/paper_experiments.py --smoke
docker build -t agentshield-v3 .
```

通过后：

```bash
git tag v0.3.1-stability
git push origin v0.3.1-stability
```

---

# 四、V0.4.x：Research Fairness，修论文可信度

## 目标

把项目从“自己考自己”变成“审稿人可以相信”。

`RESEARCH_VERDICT.md` 已经明确指出，当前必须修复标签泄漏、循环评估、弱基线等问题，否则论文不可发表。([GitHub][2])

## 任务 1：彻底切断 ground truth 字段

建立两个 schema。

### 可观测输入

```python
@dataclass
class ObservedToolEvent:
    event_id: str
    session_id: str
    parent_event_id: str | None
    timestamp: float
    agent_id: str
    agent_role: str | None
    tool_name: str
    tool_input: dict
    tool_output_summary: str | None
    resource_type: str | None
    destination: str | None
    previous_tools: list[str]
    chain_length: int
```

### 隐藏标签

```python
@dataclass
class HiddenGroundTruth:
    event_id: str
    chain_id: str
    step_index: int
    attack_stage: str
    label: Literal["ALLOW", "HUMAN_REVIEW", "BLOCK"]
    rationale: str
```

scorer / detector / engine 只能读 `ObservedToolEvent`。

禁止读取：

```text
attack_stage
chain_id
step_index
label
expected_action
ground_truth
is_attack
```

测试：

```python
def test_detector_cannot_read_hidden_ground_truth():
    forbidden = {
        "attack_stage",
        "chain_id",
        "step_index",
        "label",
        "expected_action",
        "ground_truth",
    }
    assert not detector_accesses_any(forbidden)
```

## 任务 2：重建数据集分层

```text
benchmark/datasets/
  dev_synthetic/
  heldout_adversarial/
  semireal/
  real_anonymized/
```

| 数据集                 | 用途   | 要求                       |
| ------------------- | ---- | ------------------------ |
| Dev Synthetic       | 开发调试 | 可规则生成                    |
| Heldout Adversarial | 主实验  | 生成逻辑与检测逻辑隔离              |
| Semi-real           | 工程验证 | 保留已有 semi-real traces    |
| Real Anonymized     | 论文增强 | 至少 50 条真实 Agent workflow |

## 任务 3：强基线接入

必须新增：

```text
LLM-as-Judge with full chain context
NeMo Guardrails real config
Llama Guard / LLM Guard equivalent
Local context classifier
Tool-name-only rules
Content-only rules
AgentShield no-graph
AgentShield graph-only
AgentShield full
```

论文中不能只打 keyword baseline。`RESEARCH_VERDICT.md` 也明确要求增加 LLM-as-Judge 和 NeMo Guardrails 等真实强基线。([GitHub][2])

## 任务 4：指标升级

必须输出：

```text
accuracy
macro_f1
weighted_f1
BLOCK recall
false_allow_rate
false_block_rate
review_rate
governance_efficiency
latency_p50
latency_p95
latency_p99
AUROC
AUPRC
ECE calibration error
```

## V0.4 验收

```bash
python benchmark/experiments/leakage_test.py
python benchmark/experiments/main_comparison.py
python benchmark/experiments/robustness.py
python benchmark/experiments/latency.py
```

验收标准：

```text
无标签泄漏
有 heldout adversarial set
有强基线
所有实验有 seed
所有结果有 bootstrap CI
输出 paper-ready CSV / JSON / Markdown
```

Tag：

```bash
v0.4.0-research-fairness
```

---

# 五、V0.5.x：Graph Risk，图推理真正主导 final risk

## 目标

让 AgentShield 的核心贡献从“特征工程”变成“图推理”。

当前裁决文档明确说：行为图和传播算法已经实现，但未真正接入评分管线，当前链感知更多来自查找表和特征工程。([GitHub][2]) 这就是下一步最大的研究机会。

## 新风险管线

```text
ObservedToolEvent
  ↓
RiskSignalExtractor
  ↓
BehaviorGraph.update()
  ↓
GraphRiskPropagation
  ↓
PathRiskAnalyzer
  ↓
CounterfactualInterventionValue
  ↓
PolicyDecisionEngine
  ↓
AuditEvidence
```

## RiskSignal 标准

```python
class RiskSignalType(str, Enum):
    SENSITIVE_SOURCE = "sensitive_source"
    EXTERNAL_SINK = "external_sink"
    PRIVILEGE_CHANGE = "privilege_change"
    AUDIT_TAMPER = "audit_tamper"
    BULK_OPERATION = "bulk_operation"
    CREDENTIAL_ACCESS = "credential_access"
    CROSS_AGENT_DELEGATION = "cross_agent_delegation"
    POLICY_EVASION = "policy_evasion"
    MCP_TOOL_POISONING = "mcp_tool_poisoning"
    TOKEN_PASSTHROUGH = "token_passthrough"
    SSRF_VECTOR = "ssrf_vector"
```

## GraphRiskState

```python
@dataclass
class GraphRiskState:
    local_risk: float
    inherited_risk: float
    path_risk: float
    downstream_exposure: float
    intervention_value: float
    confidence: float
    signals: list[RiskSignal]
```

## 推荐融合公式

当前公式如果导致单步风险过低，可以调整为：

```python
final_risk = clamp(
    0.25 * local_risk
    + 0.25 * inherited_risk
    + 0.20 * path_risk
    + 0.20 * downstream_exposure
    + 0.10 * intervention_value
)
```

如果仍保留 raw input risk：

```python
final_risk = clamp(
    0.75 * graph_risk
    + 0.25 * external_prior_risk
)
```

但注意：**raw risk_score 只能是 prior，不能主导决策。**

## 验收

```text
图传播结果进入 final_risk
decision 由 final_risk 统一控制
risk evidence 可追踪到 graph path
graph-only ablation 显著优于 no-graph
特征工程版与图推理版分离
```

Tag：

```bash
v0.5.0-graph-risk
```

---

# 六、V0.6.x：Counterfactual，真实反事实干预

## 目标

把 what-if 从“演示解释”变成真正的干预优化。

裁决文档明确指出，当前如果反事实分析只是 `risk * 0.5`，必须改成移除某步骤后重新计算整条链风险传播。([GitHub][2])

## CounterfactualEngine

```python
class CounterfactualEngine:
    def remove_event(self, graph, event_id): ...
    def replay_graph(self, modified_graph): ...
    def recompute_risk(self, modified_graph): ...
    def estimate_prevented_harm(self, original, modified): ...
    def estimate_business_cost(self, removed_event): ...
    def rank_intervention_points(self, graph): ...
```

## 输出结构

```python
@dataclass
class InterventionOutcome:
    scenario_id: str
    removed_event_id: str
    original_risk: float
    modified_risk: float
    risk_delta: float
    prevented_downstream_risk: float
    business_cost: float
    net_value: float
    downstream_events_affected: list[str]
    recommended: bool
    reason: str
```

## 干预价值

```python
net_value = (
    prevented_downstream_risk
    - false_positive_cost
    - business_delay_cost
    - user_friction_cost
)
```

## 对比策略

```text
first-risk blocking
last-risk blocking
highest-risk blocking
optimal counterfactual blocking
```

指标：

```text
governance_efficiency = risk_prevented / steps_blocked
```

## 验收

```text
任意节点可移除 replay
重新传播整条链风险
能输出 original graph vs modified graph diff
能排序推荐最优干预点
optimal intervention 优于 first/last baseline
```

Tag：

```bash
v0.6.0-counterfactual
```

---

# 七、V0.7.x：Secure Core，企业安全内核

## 目标

从研究后端变成安全产品后端。

## 必做模块

```text
backend/app/security/
  auth.py
  api_key.py
  jwt.py
  rbac.py
  tenant.py
  rate_limit.py

backend/app/storage/
  postgres.py
  redis_store.py
  graph_store.py
  audit_store.py
  migrations/

backend/app/policy/
  engine.py
  schema.py
  compiler.py
  evaluator.py
```

## API 安全

```text
API key auth
JWT auth
tenant_id isolation
project_id isolation
RBAC
rate limit
request signing
audit auth events
```

## Policy DSL

```yaml
policy_id: finance-data-exfiltration-v1
scope:
  tenant: acme
  project: finance-agent
rules:
  - when:
      source: ["database", "crm", "drive"]
      sink: ["email", "http", "slack", "external_api"]
      contains: ["pii", "credential", "financial_record"]
    then:
      action: BLOCK
      reason: Sensitive source to external sink
```

## 审计链

```json
{
  "event_id": "evt_123",
  "decision_id": "dec_456",
  "tenant_id": "acme",
  "project_id": "finance-agent",
  "policy_id": "finance-data-exfiltration-v1",
  "risk_score": 0.91,
  "decision": "BLOCK",
  "evidence": [],
  "graph_path": [],
  "counterfactual": {},
  "timestamp": "...",
  "signature": "..."
}
```

## 验收

```text
所有 /api/* 需要 auth
tenant 隔离测试通过
policy CRUD 可用
audit append-only
session 可持久化恢复
CORS 默认不再 *
```

Tag：

```bash
v0.7.0-secure-core
```

---

# 八、V0.8.x：MCP Shield Proxy

## 目标

切入 MCP 生态，成为 MCP 工具调用链的安全代理。

MCP 官方安全实践明确列出 token passthrough、confused deputy、SSRF、session hijacking、local MCP server compromise、scope minimization 等风险，因此 AgentShield 的行为链图推理非常适合做 MCP 代理层。([GitHub][3])

## 架构

```text
MCP Client
   ↓
AgentShield MCP Proxy
   ↓
MCP Server
```

## 事件模型

```python
@dataclass
class MCPToolInvocation:
    client_id: str
    server_id: str
    session_id: str
    tool_name: str
    tool_descriptor_hash: str
    input_schema_hash: str
    arguments: dict
    auth_scopes: list[str]
    user_id: str
    tenant_id: str
```

## 检测项

```text
tool descriptor change
tool poisoning
rug-pull tool update
overbroad scope
token passthrough
SSRF destination
local command execution
sensitive source → external sink
cross-server exfiltration
session hijacking
```

## 代理能力

```text
拦截 tools/list
hash tool descriptor
检测 descriptor 变更
拦截 tools/call
检查 auth scope
检查 destination
调用 graph risk engine
ALLOW / REVIEW / BLOCK
记录 consent 与 audit
```

## 验收

```text
支持 stdio / HTTP transport
可拦截 tools/list 与 tools/call
可检测 MCP tool poisoning
可检测 SSRF
可检测 token passthrough
可输出 MCP audit chain
```

Tag：

```bash
v0.8.0-mcp-shield
```

---

# 九、V0.9.x：SOC Dashboard

## 目标

把前端从 demo dashboard 升级为安全运营台。

上传日志显示曾经做过 SOC 风格 UI，包含暗色主题、五级风险色、API 状态指示器、实时时钟、相对路径 API、mock fallback、响应式布局和 vanilla JS 单文件。 这可以作为过渡版，但最终应该升级成模块化前端。

## 页面结构

```text
frontend/src/
  pages/
    Overview.tsx
    SessionTimeline.tsx
    BehaviorGraph.tsx
    RiskDiff.tsx
    CounterfactualStudio.tsx
    PolicyWorkbench.tsx
    MCPMonitor.tsx
    RedTeamArena.tsx
    AuditExport.tsx
    ProductionMonitor.tsx
  components/
    RiskNode.tsx
    GraphCanvas.tsx
    TimelineEvent.tsx
    DecisionCard.tsx
    EvidencePanel.tsx
    PolicyEditor.tsx
```

## 核心页面

| 页面                    | 功能                             |
| --------------------- | ------------------------------ |
| Overview              | 总体风险态势                         |
| Session Timeline      | 单个 session 行为时间线               |
| Behavior Graph        | 节点、边、风险传播、关键路径                 |
| Counterfactual Studio | 点选节点后模拟阻断                      |
| Policy Workbench      | 策略编辑、dry-run、发布                |
| MCP Monitor           | MCP server/tool 风险监控           |
| Red Team Arena        | 攻击链测试                          |
| Audit Export          | 导出 JSON / PDF / SARIF          |
| Production Monitor    | 延迟、吞吐、review queue、false allow |

## 验收

```text
实时展示 session graph
点击节点查看 evidence
运行 counterfactual replay
编辑 policy 并 dry-run
导出 audit report
API 不可用时 mock fallback
```

Tag：

```bash
v0.9.0-soc-dashboard
```

---

# 十、V1.0：Paper-grade Release

## 目标

第一个可以投稿、参赛、展示、复现的研究版本。

## 推荐论文题目

```text
ChainRisk: Formal Modeling and Runtime Detection of Compositional Risk in Multi-Agent Tool-Use Systems
```

裁决文档也推荐把论文主线放在 multi-agent tool-use compositional risk 的形式化建模与运行时检测，并要求接入真正图推理、公平强基线、对抗评估、PR 曲线和真实 trace。([GitHub][2])

## 论文贡献

```text
1. 多智能体工具调用组合风险的形式化定义
2. 行为图风险传播算法
3. 运行时治理门控
4. 反事实干预点选择
5. 对抗 benchmark
6. paper-grade 可复现实验
```

## 实验矩阵

```text
main comparison
ablation study
leakage test
robustness test
latency benchmark
review cost analysis
intervention timing
case studies
```

这些与上传日志里 Phase 8 的 `paper_experiments.py` 七类实验基本一致，可以继续强化为正式 paper pipeline。

## 输出目录

```text
benchmark/results/paper/
  main_comparison.csv
  main_comparison.json
  ablation.csv
  leakage_test.json
  robustness.json
  latency.json
  review_cost.json
  intervention_timing.json
  case_studies.md
  paper_report.md
  figures/
```

## 验收

```bash
python benchmark/paper_experiments.py --all --seed 42
python benchmark/paper_experiments.py --all --seed 43
python benchmark/paper_experiments.py --all --seed 44
```

必须满足：

```text
一键复现所有实验
所有结果有 seed
所有指标有 confidence interval
所有 dataset 有 schema
无标签泄漏
PR 曲线完整
真实 trace >= 50
```

Tag：

```bash
v1.0.0-research-release
```

---

# 十一、V1.5：SDK + Gateway

## 目标

让真实 Agent 项目能接入 AgentShield。

## Python SDK

```python
from agentshield import Shield, SecurityException

shield = Shield(
    project="finance-agent",
    api_key="...",
    base_url="https://shield.company.com",
)

decision = shield.evaluate_tool_call(
    agent_id="analyst_agent",
    tool_name="send_email",
    arguments={
        "to": "external@example.com",
        "body": "customer export attached"
    },
    parent_event_id="evt_123"
)

if decision.blocked:
    raise SecurityException(decision.reason)
```

## Adapter

```text
sdk/agentshield/adapters/
  langchain.py
  autogen.py
  crewai.py
  openai_agents.py
  mcp.py
```

## Gateway 模式

```text
Agent App
  ↓
AgentShield Gateway
  ↓
Tools / MCP Servers / APIs
```

## 验收

```text
LangChain demo 可运行
AutoGen demo 可运行
CrewAI demo 可运行
MCP demo 可运行
SDK 有 pytest
Gateway 有 e2e test
```

Tag：

```bash
v1.5.0-sdk-gateway
```

---

# 十二、V2.0：Enterprise Runtime

## 目标

变成企业能部署的安全产品。

## 多租户模型

```text
tenant
  └── project
        └── environment
              └── session
                    └── event
```

字段贯穿：

```text
tenant_id
project_id
environment
user_id
agent_id
session_id
event_id
```

## 企业能力

```text
SSO: OIDC / SAML
RBAC: Admin / Security Analyst / Developer / Auditor
SIEM: Splunk / Elastic / Datadog / Chronicle
OTel: traces / metrics / logs
HA: 多副本
DR: 备份恢复
Audit: append-only + signature
Compliance: OWASP / NIST / MCP mapping
```

## 部署

```text
deploy/
  docker-compose.yml
  helm/
  k8s/
  terraform/
```

## 验收

```text
多租户隔离通过
RBAC 通过
SSO 可接入
OTel 可导出
SIEM webhook 可用
K8s Helm chart 可部署
审计报告可导出
```

Tag：

```bash
v2.0.0-enterprise-runtime
```

---

# 十三、V3.0：Adaptive Governance

## 目标

从静态策略升级为自适应治理系统。

## 能力

```text
per tenant threshold calibration
per tool threshold calibration
per agent role threshold calibration
human feedback loop
policy recommendation
active red-team scenario generation
replay-based regression testing
```

## Human feedback loop

```text
security analyst review
  ↓
label correction
  ↓
policy refinement
  ↓
threshold calibration
  ↓
benchmark replay
  ↓
safe policy release
```

## 策略推荐例子

```text
过去 7 天中：
某类 HUMAN_REVIEW 事件 82% 被人工判定为 BLOCK
系统建议：
将该 pattern 升级为 BLOCK policy
```

## 验收

```text
支持人工反馈
支持策略推荐
支持 per-tenant calibration
支持 replay regression
支持 red-team generator
```

Tag：

```bash
v3.0.0-adaptive-governance
```

---

# 十四、V4.0+：最终完美形态

最终架构：

```text
┌────────────────────────────────────────────────────┐
│ LangChain / AutoGen / CrewAI / OpenAI Agents / MCP  │
└──────────────────────┬─────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────┐
│ AgentShield SDK / Gateway / MCP Proxy               │
└──────────────────────┬─────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────┐
│ Event Normalizer + Policy Gateway                   │
└──────────────────────┬─────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────┐
│ Behavior Graph Risk Engine                          │
│ - local risk                                         │
│ - inherited risk                                     │
│ - path risk                                          │
│ - downstream exposure                                │
│ - intervention value                                 │
└──────────────────────┬─────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────┐
│ Counterfactual Intervention Engine                  │
└──────────────────────┬─────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────┐
│ Governance Decision                                 │
│ ALLOW / REVIEW / BLOCK / SANDBOX / REDACT            │
└──────────────────────┬─────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────┐
│ Audit Evidence + OTel + SIEM + SOC Console           │
└────────────────────────────────────────────────────┘
```

最终能力表：

| 能力         | 完美标准                                          |
| ---------- | --------------------------------------------- |
| Runtime 防护 | 所有 Agent tool call 可拦截                        |
| 行为图        | 跨 agent、跨 tool、跨 MCP server                   |
| 风险传播       | 支持因果路径、信息流路径、权限路径                             |
| 干预         | 找最优阻断点，而不是粗暴 block                            |
| 审计         | 可复盘、可签名、可导出                                   |
| MCP        | tool poisoning、token、SSRF、descriptor rug-pull |
| 企业         | 多租户、RBAC、SSO、SIEM、OTel                        |
| 论文         | 公平基线、heldout、真实 trace、消融                      |
| UI         | SOC 级 graph + timeline + policy workbench     |
| SDK        | Python / JS / Gateway / LangChain / MCP       |

---

# 十五、最终执行顺序

严格按这个顺序做：

```text
1. 确认 Phase 8 / Phase 9 是否已 push
2. 修 world_name、端口、测试语义
3. pytest 全绿
4. 去标签泄漏
5. 建 heldout adversarial set
6. 接强基线
7. 图推理进入 final_risk
8. 真实 counterfactual replay
9. policy engine + auth + tenant
10. MCP proxy
11. SOC dashboard
12. SDK / adapters / gateway
13. OTel / SIEM / RBAC / Helm
14. paper release
15. enterprise release
```

---

# 十六、当前下一步最小闭环

现在马上应该做的不是继续写新功能，而是执行这个闭环：

```bash
# 1. 确认文件是否存在
ls benchmark/paper_experiments.py
ls sdk/agentshield/client.py
ls backend/app/proxy/gateway.py
ls backend/app/console/routes.py

# 2. 确认 git 状态
git status
git log --oneline -5

# 3. 修测试
python -m pytest -q

# 4. 修 benchmark
python benchmark/paper_experiments.py --smoke

# 5. 修 Docker
docker build -t agentshield-v3 .

# 6. 提交
git add .
git commit -m "stabilize AgentShield V3 research and enterprise pipeline"
git push origin main

# 7. 打 tag
git tag v0.3.1-stability
git push origin v0.3.1-stability
```

---

# 最终判断

**AgentShield_V3 的方向是对的，但它现在最需要的不是更多概念，而是可信度闭环。**

它的最终路线应该是：

```text
从 demo 安全原型
→ 到 paper-grade graph-risk detector
→ 到 MCP tool-chain security proxy
→ 到 enterprise Agent runtime firewall
→ 到完整 Agent Runtime Security Platform
```

当前最优先四件事：

```text
第一：测试全绿
第二：去标签泄漏
第三：图推理真正接入 final risk
第四：真实反事实 replay
```

只要这四件事完成，AgentShield_V3 就会从“概念不错的项目”进入“真正可信的安全系统”阶段。

[1]: https://github.com/Zhuyuyangyy/AgentShield_V3 "GitHub - Zhuyuyangyy/AgentShield_V3 · GitHub"
[2]: https://github.com/Zhuyuyangyy/AgentShield_V3/blob/main/RESEARCH_VERDICT.md "AgentShield_V3/RESEARCH_VERDICT.md at main · Zhuyuyangyy/AgentShield_V3 · GitHub"
[3]: https://github.com/CHATS-lab/ToolShield?utm_source=chatgpt.com "CHATS-lab/ToolShield: [ICML 2026] Official ..."
