# SCI Baseline Comparison

Dataset: `D:\ZYY Project\AgentShield_V3\benchmark\test_cases\test_cases_sci_600.json`
Cases: 600

| Method | Action Acc. | Macro F1 | BLOCK Recall | False Allow | False Block | Review Rate | MAE | ms/case |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Tool-name rules | 20.83% | 12.50% | 0.00% | 97.24% | 0.00% | 2.67% | 0.4592 | 0.0026 |
| Content keywords | 32.67% | 31.77% | 13.36% | 7.37% | 0.00% | 39.33% | 0.2080 | 0.0042 |
| Local context | 62.67% | 60.98% | 76.96% | 0.00% | 16.00% | 43.33% | 0.1569 | 0.0060 |
| AgentShield chain-aware | 75.33% | 72.61% | 84.79% | 0.00% | 6.40% | 47.67% | 0.1532 | 0.0109 |

## Notes

- Tool-name rules use only the invoked tool name.
- Content keywords use only serialized tool input.
- Local context adds category priors but ignores chain metadata.
- AgentShield chain-aware adds stage, chain, and governance-bypass context.
