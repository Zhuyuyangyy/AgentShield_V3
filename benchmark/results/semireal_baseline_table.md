# Semi-Real Trace Baseline Comparison

Dataset: `D:\ZYY Project\AgentShield_V3\benchmark\test_cases\test_cases_semireal_150.json`
Traces: 150
Steps: 405

| Method | Action Acc. | Macro F1 | BLOCK Recall | False Allow | False Block | Review Rate | MAE | ms/trace |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Tool-name rules | 33.33% | 17.09% | 0.00% | 91.67% | 0.00% | 3.33% | 0.4307 | 0.0028 |
| Content keywords | 33.33% | 19.61% | 0.00% | 50.00% | 0.00% | 20.00% | 0.2553 | 0.0041 |
| Local context | 66.67% | 63.37% | 16.67% | 0.00% | 0.00% | 60.00% | 0.0753 | 0.0042 |
| AgentShield chain-aware | 76.67% | 75.11% | 75.00% | 0.00% | 0.00% | 23.33% | 0.0873 | 0.0063 |

## Notes

- Each trace is reduced to its expected intervention or critical step for baseline comparison.
- Chain-aware evaluation keeps trace identity, step index, and attack stage metadata.
