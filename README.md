# AgentShield V3

AgentShield V3 is a behavior-chain risk governance prototype for multi-agent tool-use systems. It records agent tool calls as graph nodes, propagates risk through behavior chains, applies governance decisions, and produces audit evidence plus counterfactual what-if analysis.

The project is currently positioned as both an engineering prototype and a research artifact for SCI-oriented experiments on multi-agent safety governance.

## Why V3

Traditional guardrails usually judge a single prompt, response, or tool call in isolation. AgentShield V3 focuses on the behavior chain:

```text
V1: What did the AI say?
V2: What tool did the agent call?
V3: Why does this multi-agent behavior chain become risky?
```

V3 is designed for scenarios where risk emerges across multiple steps, for example:

- querying sensitive fields and exporting them later,
- staging data before external transfer,
- privilege escalation through delegated tools,
- audit-log bypass or callback smuggling,
- bulk database operations with delayed impact.

## Core Capabilities

- **Behavior graph modeling**: converts every tool call into an `AgentBehaviorGraph` node.
- **Risk propagation**: tracks local risk, inherited risk, downstream amplification, and critical nodes.
- **Three-level governance**: returns `ALLOW`, `HUMAN_REVIEW`, or `BLOCK`.
- **Future branch projection**: generates possible next-step branches for high-risk calls.
- **Counterfactual intervention**: estimates risk reduction if a risky action is blocked earlier.
- **Audit chain export**: keeps structured evidence for review, debugging, and research analysis.
- **SCI benchmark workflow**: includes synthetic/semi-realistic dataset generation and baseline comparison scripts.

## Repository Layout

```text
AgentShield_V3/
+-- backend/
|   +-- app/
|   |   +-- api/
|   |   |   +-- routes.py
|   |   +-- shield/
|   |   |   +-- agent_behavior_graph.py
|   |   |   +-- v3_audit_logger.py
|   |   |   +-- v3_engine.py
|   |   +-- main.py
|   +-- tests/
|       +-- test_v3_engine.py
+-- benchmark/
|   +-- baselines.py
|   +-- evaluate.py
|   +-- generate_sci_dataset.py
|   +-- results/
|   |   +-- sci_baseline_report.json
|   |   +-- sci_baseline_table.md
|   +-- test_cases/
|       +-- test_cases_v3_standard.json
|       +-- test_cases_sci_600.json
+-- docs/
|   +-- paper_plan.md
+-- pytest.ini
+-- requirements.txt
+-- README.md
```

## Quick Start

### 1. Install Dependencies

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run Tests

```bash
python -m pytest -q
```

Current verified result:

```text
10 passed
```

### 3. Start the API Server

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8011
```

Then open:

- API root: `http://localhost:8011/`
- Swagger docs: `http://localhost:8011/docs`
- Health check: `http://localhost:8011/health`

On Windows, you can also run:

```bash
start.bat
```

## API Example

### Process a Tool Call

```http
POST /api/v3/process_call
```

Request:

```json
{
  "session_id": "demo-session",
  "agent_id": "data_agent",
  "tool_name": "execute_sql",
  "params": {
    "query": "SELECT phone, id_card FROM customers"
  },
  "risk_score": 0.92,
  "fuse_action": "BLOCK"
}
```

Response fields include:

```json
{
  "call_id": "call_xxxxxxxx",
  "node_id": "node_xxxxxxxx",
  "decision": "block",
  "risk_level": "critical",
  "gate_result": {
    "action": "BLOCK",
    "score": 0.92
  },
  "future_branches": [],
  "whatif_result": {}
}
```

### Other Endpoints

- `GET /api/v3/status/{session_id}`
- `POST /api/v3/fork_branch`
- `GET /api/v3/export_chain/{session_id}`
- `GET /api/v3/behavior_graph/{session_id}`
- `POST /api/v3/simulate_steps`

## Benchmark

Run the standard regression benchmark:

```bash
python benchmark\evaluate.py
```

Run the V3 standard benchmark:

```bash
python benchmark\evaluate_v3.py
```

The current restored engine has been verified with:

```text
Score accuracy: 100/100
Action accuracy: 100/100
```

## SCI Experiment Workflow

The repository now includes a reproducible SCI-oriented experiment path.

### 1. Generate the SCI-600 Dataset

```bash
python benchmark\generate_sci_dataset.py
```

Default output:

```text
benchmark/test_cases/test_cases_sci_600.json
```

The generated dataset keeps the existing benchmark schema and adds optional chain metadata:

- `chain_id`
- `step_index`
- `attack_stage`
- `semi_realistic_trace`

### 2. Run Baseline Comparison

```bash
python benchmark\baselines.py
```

Default outputs:

- `benchmark/results/sci_baseline_report.json`
- `benchmark/results/sci_baseline_table.md`

Current snapshot on the deterministic SCI-600 dataset:

| Method | Action Acc. | Macro F1 | BLOCK Recall | False Allow | False Block |
|---|---:|---:|---:|---:|---:|
| Tool-name rules | 20.83% | 12.50% | 0.00% | 97.24% | 0.00% |
| Content keywords | 32.67% | 31.77% | 13.36% | 7.37% | 0.00% |
| Local context | 62.67% | 60.98% | 76.96% | 0.00% | 16.00% |
| AgentShield chain-aware | 75.33% | 72.61% | 84.79% | 0.00% | 6.40% |

These results are an internal research milestone. For SCI submission, the next step is to add ablation studies and semi-real traces from controlled LangChain, AutoGen, or internal agent workflows.

### 3. Generate the V3.1 Semi-Real Trace Dataset

```bash
python benchmark\generate_semireal_traces.py
```

Default output:

```text
benchmark/test_cases/test_cases_semireal_150.json
```

The V3.1 dataset contains 150 controlled semi-real traces and 405 tool-call steps. It preserves trace-level labels, parent-child step links, critical intervention steps, and anonymized tool inputs.

### 4. Run Semi-Real Trace Evaluation

```bash
python benchmark\evaluate_semireal.py
```

Default outputs:

- `benchmark/results/semireal_baseline_report.json`
- `benchmark/results/semireal_baseline_table.md`

Current snapshot:

| Method | Action Acc. | Macro F1 | BLOCK Recall | False Allow | False Block |
|---|---|---:|---:|---:|---:|---:|
| Tool-name rules | 33.33% | 17.09% | 0.00% | 91.67% | 0.00% |
| Content keywords | 33.33% | 19.61% | 0.00% | 50.00% | 0.00% |
| Local context | 66.67% | 63.37% | 16.67% | 0.00% | 0.00% |
| AgentShield chain-aware | 76.67% | 75.11% | 75.00% | 0.00% | 0.00% |

### 5. Run Ablation Study

```bash
python scripts/run_ablation.py --dataset sci
python scripts/run_ablation.py --dataset semireal
```

Outputs (published to `benchmark/results/`):

- `ablation_sci_report.json` / `ablation_sci_table.csv` / `ablation_sci_deltas.csv`
- `ablation_semireal_report.json` / `ablation_semireal_table.csv` / `ablation_semireal_deltas.csv`

The ablation disables each chain-aware component in turn:

| Ablation | Component disabled |
|---|---|
| 1 −stage boost | Attack-stage risk elevation (recon/collect/stage/exfiltrate) |
| 2 −category×chain boost | Behavior-chain and governance-bypass category boost |
| 3 −external+sensitive boost | External transfer + sensitive-field combination boost |
| 4 −audit/evasion boosts | Audit-disabling and log-tampering detection |
| 5 −special-case rules | Review-marker caps and exception rules |
| 6 Local context (all chain) | Equivalent to the Local context baseline |

Current SCI-600 results:

| Method | Action Acc. | Macro F1 | BLOCK Recall |
|---|---:|---:|---:|
| 0 Full AgentShield | 75.33% | 72.61% | 84.79% |
| 1 −stage boost | 75.83% | 73.35% | 84.79% |
| 2 −category×chain boost | 75.83% | 73.35% | 84.79% |
| 3 −external+sensitive boost | 75.33% | 72.61% | 84.79% |
| 4 −audit/evasion boosts | 75.17% | 72.60% | 79.26% |
| 5 −special-case rules | 51.33% | 47.78% | 84.79% |
| 6 Local context | 62.67% | 60.98% | 76.96% |

### Semi-Real Trace Methodology

The V3.1 semi-real traces (`benchmark/test_cases/test_cases_semireal_150.json`) are constructed from controlled scenario templates that model real multi-agent attack patterns:

- **Data exfiltration chain**: sensitive query → staging → compress → external transfer
- **Privilege escalation**: config read → admin role modification
- **Audit log bypass**: callback request → disable audit logging
- **Bulk destructive operations**: single bulk DELETE
- **Multi-agent delegation risk**: task delegation → sensitive query → external delivery

Each trace preserves:
- Step-level tool calls with realistic `agent_id`, `tool_name`, and anonymized `tool_input`
- Parent-child step links
- Per-step `local_risk_score` and `local_risk_type`
- Trace-level `chain_label` (ALLOW / HUMAN_REVIEW / BLOCK) as ground truth
- Critical intervention step and attack stage annotation (collect/stage/exfiltrate)

This design produces traces that are more structurally realistic than fully synthetic cases while retaining deterministic, reproducible ground truth for benchmarking.

## Research Direction

The current paper route is documented in:

```text
docs/paper_plan.md
```

Recommended SCI framing:

- problem: single-call guardrails miss behavior-chain risk,
- method: behavior graph plus chain-aware governance,
- evidence: standard benchmark, SCI-600 dataset, baseline comparison, ablation, latency, case studies,
- next data need: anonymized or semi-real multi-agent tool-call traces.

## Development Notes

- Keep patent drafts, application documents, private datasets, backups, and local experiment dumps out of git.
- Prefer committing source, tests, benchmark scripts, sanitized datasets, and reproducible reports only.
- Do not commit `__pycache__`, `.pytest_cache`, raw credentials, or private logs.

Suggested verification before committing:

```bash
python -m pytest -q
python benchmark\generate_sci_dataset.py
python benchmark\baselines.py
python benchmark\generate_semireal_traces.py
python benchmark\evaluate_semireal.py
```

## Status

The V3 core engine, tests, benchmark runner, SCI dataset generator, baseline report workflow, and V3.1 semi-real trace benchmark are currently operational. The project is ready for the next research phase: ablation experiments, latency analysis, and case-study visualization.
