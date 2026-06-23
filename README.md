# AgentShield V3

> Behavior-chain risk governance for multi-agent tool-use systems.

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)
![Tests](https://img.shields.io/badge/Tests-242%20passed-brightgreen)

## Overview

AgentShield V3 is a research prototype for **behavior-chain risk governance** in multi-agent tool-use systems. Traditional guardrails evaluate individual prompts, responses, or tool calls in isolation. V3 addresses the fundamental limitation that **risk in multi-agent systems often emerges across sequences of actions**, not within any single call.

The system models agent tool calls as nodes in a directed behavior graph, propagates risk scores through behavior chains, applies three-level governance decisions (ALLOW / HUMAN_REVIEW / BLOCK), and provides counterfactual what-if analysis to estimate risk reduction from earlier interventions. This approach enables detection of attack patterns such as staged data exfiltration, privilege escalation through delegated tools, audit-log bypass, and bulk destructive operations with delayed impact.

AgentShield V3 is positioned as both an engineering prototype and a research artifact for SCI-oriented experiments on multi-agent safety governance. The repository includes a reproducible benchmark workflow with synthetic and semi-realistic datasets, baseline comparisons, and ablation studies.

## Key Features

1. **Behavior Graph Modeling** -- Converts every tool call into an `AgentBehaviorGraph` node with agent identity, risk status, inherited risk, and downstream amplification tracking.

2. **Chain-Aware Risk Propagation** -- Tracks local risk, inherited risk from upstream nodes, downstream amplification, and critical node identification across the full behavior chain.

3. **Three-Level Governance Gate** -- Returns structured decisions (`ALLOW`, `HUMAN_REVIEW`, `BLOCK`) with risk scores, reasons, and confidence levels for each tool call.

4. **Future Branch Projection** -- Generates possible next-step risk branches for high-risk calls, enabling proactive governance before damage occurs.

5. **Counterfactual Intervention Analysis** -- Estimates risk reduction if a risky action had been blocked at an earlier point in the chain, supporting root-cause attribution.

6. **Audit Chain Export** -- Produces structured evidence chains for review, debugging, and research analysis with full provenance tracking.

7. **SCI Benchmark Workflow** -- Includes synthetic dataset generation (SCI-600), semi-realistic trace generation (150 traces, 405 steps), baseline comparison scripts, and ablation study tooling.

## Architecture

```
                          +-------------------+
                          |   API Gateway     |
                          |   (FastAPI)       |
                          +--------+----------+
                                   |
                          +--------v----------+
                          |   V3 Engine       |
                          |   (Governance)    |
                          +--------+----------+
                                   |
              +--------------------+--------------------+
              |                    |                     |
   +----------v----------+ +------v-------+ +-----------v-----------+
   | Behavior Graph      | | Audit Logger | | Session Store         |
   | (Node/Edge Model)   | | (Evidence)   | | (State Management)    |
   +----------+----------+ +--------------+ +-----------------------+
              |
   +----------v----------+
   | Risk Propagation    |
   | (Chain Analysis)    |
   +----------+----------+
              |
   +----------v----------+
   | Governance Gate     |
   | (ALLOW/REVIEW/BLOCK)|
   +----------+----------+
              |
   +----------v----------+
   | Branch Tree &       |
   | What-If Analysis    |
   +---------------------+
```

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Backend Framework | FastAPI + Uvicorn | REST API server with async support |
| Core Engine | Python 3.9+ | Behavior graph, risk propagation, governance logic |
| Data Validation | Pydantic v2 | Request/response schema validation |
| Testing | pytest | Unit tests and integration tests |
| Rate Limiting | slowapi | API rate limiting |
| HTTP Client | httpx | Async HTTP communication |
| Logging | loguru | Structured logging |
| Containerization | Docker | Deployment packaging |

## Quick Start

### Prerequisites

- Python 3.9 or higher
- pip package manager

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd AgentShield_V3

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

### Running Tests

```bash
python -m pytest -q
```

Expected output: `242 passed`

### Starting the API Server

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8011
```

The following endpoints will be available:

| Endpoint | Description |
|----------|-------------|
| `http://localhost:8011/` | API root |
| `http://localhost:8011/docs` | Swagger documentation |
| `http://localhost:8011/health` | Health check |

On Windows, you can also use `start.bat`.

### API Usage Example

Process a tool call through the governance pipeline:

```http
POST /api/v3/process_call
Content-Type: application/json

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

Response:

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

Additional endpoints:

- `GET /api/v3/status/{session_id}` -- Session status
- `POST /api/v3/fork_branch` -- Fork a behavior branch
- `GET /api/v3/export_chain/{session_id}` -- Export audit chain
- `GET /api/v3/behavior_graph/{session_id}` -- Behavior graph visualization
- `POST /api/v3/simulate_steps` -- Simulate future steps

## Project Structure

```
AgentShield_V3/
+-- backend/
|   +-- app/
|   |   +-- api/
|   |   |   +-- routes.py                   # API endpoint definitions
|   |   +-- shield/
|   |   |   +-- agent_behavior_graph.py      # Behavior graph data model
|   |   |   +-- session_store.py             # Session state management
|   |   |   +-- v3_audit_logger.py           # Audit evidence logger
|   |   |   +-- v3_engine.py                 # Core governance engine
|   |   +-- main.py                          # FastAPI application entry
|   +-- tests/
|       +-- test_v3_engine.py                # Engine unit tests
|       +-- test_semireal_benchmark.py       # Semi-real benchmark tests
+-- benchmark/
|   +-- ablation_semireal.py                 # Ablation study for semi-real traces
|   +-- baselines.py                         # Baseline comparison framework
|   +-- evaluate.py                          # Standard evaluation runner
|   +-- evaluate_semireal.py                 # Semi-real trace evaluation
|   +-- generate_sci_dataset.py              # SCI-600 dataset generator
|   +-- generate_semireal_traces.py          # Semi-real trace generator
|   +-- results/                             # Benchmark result artifacts
|   +-- test_cases/                          # Test case datasets
+-- docs/
|   +-- CHANGELOG.md                         # Version history
|   +-- PERFORMANCE_BENCHMARK.md             # Performance benchmarks
|   +-- USER_GUIDE.md                        # User documentation
|   +-- paper_plan.md                        # SCI paper roadmap
|   +-- v3_1_evidence_summary.md             # V3.1 results summary
|   +-- v3_2_ablation_report.md              # Ablation study report
+-- frontend/
|   +-- index.html                           # Dashboard UI
+-- Dockerfile                               # Container configuration
+-- pytest.ini                               # Test configuration
+-- requirements.txt                         # Python dependencies
```

## Benchmarks & Results

### SCI-600 Dataset (600 synthetic cases)

| Method | Action Acc. | Macro F1 | BLOCK Recall | False Allow | False Block |
|--------|------------|----------|-------------|-------------|-------------|
| Tool-name rules | 20.83% | 12.50% | 0.00% | 97.24% | 0.00% |
| Content keywords | 32.67% | 31.77% | 13.36% | 7.37% | 0.00% |
| Local context | 62.67% | 60.98% | 76.96% | 0.00% | 16.00% |
| **AgentShield chain-aware** | **75.33%** | **72.61%** | **84.79%** | **0.00%** | **6.40%** |

### Semi-Real Trace Dataset (150 traces, 405 steps)

| Method | Action Acc. | Macro F1 | BLOCK Recall | False Allow | False Block |
|--------|------------|----------|-------------|-------------|-------------|
| Tool-name rules | 33.33% | 17.09% | 0.00% | 91.67% | 0.00% |
| Content keywords | 33.33% | 19.61% | 0.00% | 50.00% | 0.00% |
| Local context | 66.67% | 63.37% | 16.67% | 0.00% | 0.00% |
| **AgentShield chain-aware** | **76.67%** | **75.11%** | **75.00%** | **0.00%** | **0.00%** |

### Ablation Study (SCI-600)

| Method | Action Acc. | Macro F1 | BLOCK Recall |
|--------|------------|----------|-------------|
| Full AgentShield | 75.33% | 72.61% | 84.79% |
| - stage boost | 75.83% | 73.35% | 84.79% |
| - category x chain boost | 75.83% | 73.35% | 84.79% |
| - external+sensitive boost | 75.33% | 72.61% | 84.79% |
| - audit/evasion boosts | 75.17% | 72.60% | 79.26% |
| - special-case rules | 51.33% | 47.78% | 84.79% |
| Local context (all chain) | 62.67% | 60.98% | 76.96% |

### Running Benchmarks

```bash
# Standard regression benchmark
python benchmark/evaluate.py

# V3 standard benchmark
python benchmark/evaluate_v3.py

# Generate and evaluate SCI-600 dataset
python benchmark/generate_sci_dataset.py
python benchmark/baselines.py

# Generate and evaluate semi-real traces
python benchmark/generate_semireal_traces.py
python benchmark/evaluate_semireal.py

# Run ablation studies
python scripts/run_ablation.py --dataset sci
python scripts/run_ablation.py --dataset semireal
```

## Semi-Real Trace Methodology

The V3.1 semi-real traces are constructed from controlled scenario templates modeling real multi-agent attack patterns:

- **Data exfiltration chain**: sensitive query -> staging -> compress -> external transfer
- **Privilege escalation**: config read -> admin role modification
- **Audit log bypass**: callback request -> disable audit logging
- **Bulk destructive operations**: single bulk DELETE
- **Multi-agent delegation risk**: task delegation -> sensitive query -> external delivery

Each trace preserves step-level tool calls with realistic agent/tool metadata, parent-child step links, per-step risk scores, trace-level ground truth labels, and attack stage annotations.

## Research & Publications

- **Paper Plan**: Documented in `docs/paper_plan.md`
- **Recommended SCI Framing**:
  - Problem: Single-call guardrails miss behavior-chain risk
  - Method: Behavior graph + chain-aware governance
  - Evidence: Standard benchmark, SCI-600 dataset, baseline comparison, ablation, latency, case studies
  - Next data need: Anonymized or semi-real multi-agent tool-call traces

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| V3.0 Core Engine | Completed | Behavior graph, risk propagation, governance gate |
| V3.1 Semi-Real Traces | Completed | 150 controlled traces with attack stage annotations |
| V3.2 Ablation Evidence | Completed | Component-level ablation study |
| V3.3 Latency Optimization | In Progress | Engine latency reduction and throughput improvement |
| V3.4 Real-World Traces | Planned | Anonymized traces from production agent workflows |
| V3.5 Case Study Visualization | Planned | Interactive visualization of behavior chains and risk propagation |

## Documentation

| Document | Description |
|----------|-------------|
| [User Guide](docs/USER_GUIDE.md) | Complete user manual with quick start, concepts, SDK, API reference |
| [Performance Benchmark](docs/PERFORMANCE_BENCHMARK.md) | Latency, throughput, memory, accuracy benchmarks |
| [CHANGELOG](CHANGELOG.md) | Version history from V3.0 through V3.2 |
| [V3.1 Evidence Summary](docs/v3_1_evidence_summary.md) | Semi-real benchmark results summary |
| [V3.2 Ablation Report](docs/v3_2_ablation_report.md) | Ablation study methodology and findings |
| [Paper Plan](docs/paper_plan.md) | SCI paper roadmap |
| [Label Policy](benchmark/label_policy.md) | Benchmark labeling criteria |

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome. Please ensure:

1. All tests pass (`python -m pytest -q`)
2. Benchmark scripts run successfully
3. No credentials, private datasets, or cache files are committed

## Contact

For questions, collaboration, or research inquiries, please open an issue on the repository.
