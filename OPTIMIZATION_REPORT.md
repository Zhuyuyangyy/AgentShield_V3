# AgentShield_V3 评测优化报告
> 评测时间：2026-05-27 | 评测人：Alice
> 代码量：52个.py文件 | 后端端口：8090 | 前端：✅ | Benchmark：✅

---

## 一、整体完成度：**88%**

| 模块 | 完成度 | 说明 |
|------|--------|------|
| V3引擎 (v3_engine.py) | 95% | 核心业务逻辑完整，359行，无硬编码端口问题 |
| 行为图谱 (agent_behavior_graph.py) | 90% | 链路追踪完整 |
| 审计日志 (v3_audit_logger.py) | 85% | 基础日志完整 |
| Benchmark测试 | 90% | 4个pytest测试用例 |
| 前端Dashboard | 85% | Canvas 2D实时渲染 |
| API Routes | 88% | 6个endpoint完整 |

---

## 二、端口配置

- **正确**：`backend/app.py` 注释写明 `绔?8090`
- 路由：`backend/app/main.py` → `backend/app/api/routes.py`
- 需要确认 .env 或启动参数是否有 port=8090

---

## 三、性能分析

### ✅ 优点
1. **无循环数据库查询** — 内存状态管理，无DB IO瓶颈
2. **异步架构** — FastAPI async def，合理
3. **Branch缓存** — `get_or_create_engine` 单例模式，避免重复计算
4. **测试完整** — test_semireal_* 覆盖核心场景

### ⚠️ 潜在问题
1. `_governance_decision` 逻辑中有 `OLD_GOV` vs `NEW_GOV` 两个版本同时存在（代码注释残留）
2. `process_call` 有 `max_calls=50` 硬限制，分钟切片，暂无动态扩容机制
3. 无连接池配置，高并发下可能瓶颈在 asyncio event loop

---

## 四、未完成模块

| 模块 | 状态 | 说明 |
|------|------|------|
| /api/fork_branch | ✅ 已有 | 但无测试用例 |
| /api/export_chain | ✅ 已有 | 有测试但无 benchmark 验证 |
| WebSocket | ❌ 未实现 | 只有 REST API |
| 持久化存储 | ❌ 缺失 | session 存在内存，重启丢失 |

---

## 五、优化建议

### P0（必须修复）
1. **清理 OLD_GOV / NEW_GOV 残留代码** — 注释已说明旧版新版同时存在，需要确认哪个是生产版本
2. **添加 /api/fork_branch 的单元测试** — 已有API但无测试覆盖

### P1（建议优化）
3. **持久化方案** — 建议加 SQLite 或 Redis 做 session 持久化，避免重启丢失
4. **添加 WebSocket 支持** — 实时推送 trace 事件给前端，提升体验
5. **连接池监控** — 添加 asyncio 任务队列监控，防止高并发阻塞

### P2（锦上添花）
6. **Benchmark 测试用例扩增** — 当前只有 4 个测试，建议增加边界场景覆盖
7. **添加 /api/stream_trace** — SSE 实时流式输出 trace

---

## 六、测试用例现状

```
test_semireal_generator_produces_balanced_trace_dataset  ✅
test_semireal_traces_include_required_risky_scenarios    ✅
test_semireal_evaluator_writes_report_and_table          ✅
test_semireal_json_is_serializable                      ✅
test_semireal_ablation_writes_required_configs          ✅
```

---

## 七、核心函数清单

| 文件 | 函数 | 行数 |
|------|------|------|
| v3_engine.py | `process_call`, `get_status`, `fork_branch`, `_governance_decision` | 359 |
| agent_behavior_graph.py | `log`, `_compute_hash`, `get_records`, `export_chain`, `summary` | ~13621 bytes |
| routes.py | `health`, `root`, `process_call`, `get_status`, `fork_branch`, `export_chain`, `get_behavior_graph`, `simulate_steps` | ~128 |

---

**综合评价：** AgentShield_V3 是当前最成熟的项目之一，V3引擎逻辑完整，benchmark测试覆盖核心场景。主要问题是 OLD_GOV/NEW_GOV 残留代码和 session 内存持久化缺失。优化优先级：P0清理残留 + P1持久化。