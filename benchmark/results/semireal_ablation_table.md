# Semi-Real Trace Ablation Study

Dataset: `D:\ZYY Project\AgentShield_V3\benchmark\test_cases\test_cases_semireal_150.json`
Traces: 150
Steps: 405

| Configuration | Action Acc. | Macro F1 | BLOCK Recall | False Allow | False Block |
|---|---:|---:|---:|---:|---:|
| Full AgentShield | 76.67% | 75.11% | 75.00% | 0.00% | 0.00% |
| w/o chain propagation | 63.33% | 58.21% | 8.33% | 0.00% | 0.00% |
| w/o parent_step relation | 76.67% | 75.11% | 75.00% | 0.00% | 0.00% |
| local-only AgentShield | 66.67% | 63.37% | 16.67% | 0.00% | 0.00% |
| w/o future branch / what-if | 76.67% | 75.11% | 75.00% | 0.00% | 0.00% |

## Interpretation

- `Full AgentShield` is intentionally identical to the V3.1 `evaluate_semireal.py` AgentShield chain-aware path.
- `w/o chain propagation` removes chain-stage and chain-position features before prediction.
- `w/o parent_step relation` removes the available chain identity and step-position proxy. V3.1 does not expose raw `parent_step` to the predictor.
- `local-only AgentShield` is the existing local-context baseline.
- `w/o future branch / what-if` is an identity control because those features are not consumed by the V3.1 semi-real predictor.
