"""Run V3.2 ablation experiments on Semi-Real-150 traces.

The ablation keeps the V3.1 evaluation path intact: every configuration is
evaluated through the same case-level risk functions used by
benchmark/evaluate_semireal.py. Ablations remove input features before calling
the predictor instead of reading trace labels or scenario templates.
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmark.baselines import evaluate, risk_agent_shield, risk_local_context
from benchmark.evaluate_semireal import load_traces, trace_to_case


ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET = ROOT / "test_cases" / "test_cases_semireal_150.json"
DEFAULT_JSON = ROOT / "results" / "semireal_ablation_report.json"
DEFAULT_MD = ROOT / "results" / "semireal_ablation_table.md"

CaseTransform = Callable[[Dict[str, Any]], Dict[str, Any]]
CasePredictor = Callable[[Dict[str, Any]], float]


def identity(case: Dict[str, Any]) -> Dict[str, Any]:
    return deepcopy(case)


def without_chain_propagation_features(case: Dict[str, Any]) -> Dict[str, Any]:
    ablated = deepcopy(case)
    ablated["attack_stage"] = "single_call"
    ablated["chain_id"] = ""
    ablated["step_index"] = 0
    return ablated


def without_parent_step_features(case: Dict[str, Any]) -> Dict[str, Any]:
    ablated = deepcopy(case)
    ablated["chain_id"] = ""
    ablated["step_index"] = 0
    return ablated


def without_future_whatif_features(case: Dict[str, Any]) -> Dict[str, Any]:
    # V3.1's semi-real baseline does not pass future branch or what-if features
    # into risk_agent_shield. This ablation is therefore an identity control.
    return deepcopy(case)


def predict_agent_shield(transform: CaseTransform) -> CasePredictor:
    def _predict(case: Dict[str, Any]) -> float:
        return risk_agent_shield(transform(case))

    return _predict


ABLATIONS: List[Tuple[str, CasePredictor, str]] = [
    (
        "Full AgentShield",
        predict_agent_shield(identity),
        "Same risk_agent_shield(case) path used by evaluate_semireal.py.",
    ),
    (
        "w/o chain propagation",
        predict_agent_shield(without_chain_propagation_features),
        "Removes attack_stage, chain_id, and step_index features before inference.",
    ),
    (
        "w/o parent_step relation",
        predict_agent_shield(without_parent_step_features),
        "Removes chain_id and step_index features; current V3.1 predictor has no explicit parent_step input.",
    ),
    (
        "local-only AgentShield",
        risk_local_context,
        "Uses the existing local-context baseline without chain-aware features.",
    ),
    (
        "w/o future branch / what-if",
        predict_agent_shield(without_future_whatif_features),
        "Identity control because V3.1 semi-real scoring does not consume future branch or what-if features.",
    ),
]


def cases_from_traces(traces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [trace_to_case(trace) for trace in traces]


def write_markdown(report: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Semi-Real Trace Ablation Study",
        "",
        f"Dataset: `{report['dataset']}`",
        f"Traces: {report['total_traces']}",
        f"Steps: {report['total_steps']}",
        "",
        "| Configuration | Action Acc. | Macro F1 | BLOCK Recall | False Allow | False Block |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in report["ablations"]:
        lines.append(
            "| {name} | {acc:.2%} | {f1:.2%} | {block:.2%} | {fa:.2%} | {fb:.2%} |".format(
                name=item["name"],
                acc=item["action_accuracy"],
                f1=item["macro_f1"],
                block=item["block_recall"],
                fa=item["false_allow_rate"],
                fb=item["false_block_rate"],
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `Full AgentShield` is intentionally identical to the V3.1 `evaluate_semireal.py` AgentShield chain-aware path.",
            "- `w/o chain propagation` removes chain-stage and chain-position features before prediction.",
            "- `w/o parent_step relation` removes the available chain identity and step-position proxy. V3.1 does not expose raw `parent_step` to the predictor.",
            "- `local-only AgentShield` is the existing local-context baseline.",
            "- `w/o future branch / what-if` is an identity control because those features are not consumed by the V3.1 semi-real predictor.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    dataset: Path = DEFAULT_DATASET,
    json_out: Path = DEFAULT_JSON,
    md_out: Path = DEFAULT_MD,
) -> Dict[str, Any]:
    traces = load_traces(dataset)
    cases = cases_from_traces(traces)
    results = []
    for name, predictor, description in ABLATIONS:
        item = evaluate(name, predictor, cases)
        item["description"] = description
        results.append(item)

    report = {
        "dataset": str(dataset),
        "total_traces": len(traces),
        "total_steps": sum(len(trace.get("steps", [])) for trace in traces),
        "note": "Full AgentShield reuses the V3.1 evaluate_semireal.py risk_agent_shield(case) path.",
        "ablations": results,
    }
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, md_out)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run V3.2 semi-real ablation study.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    report = run(dataset=args.dataset, json_out=args.json_out, md_out=args.md_out)
    print(f"Evaluated {report['total_traces']} traces / {report['total_steps']} steps")
    print(f"JSON report: {args.json_out}")
    print(f"Markdown table: {args.md_out}")
    for item in report["ablations"]:
        print(
            f"{item['name']:<28} acc={item['action_accuracy']:.3f} "
            f"macro_f1={item['macro_f1']:.3f} block_recall={item['block_recall']:.3f}"
        )


if __name__ == "__main__":
    main()
