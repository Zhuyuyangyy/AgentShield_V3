# Benchmark Status — read this before quoting any number

> Status as of the label-leakage cleanup. **No headline metric in this
> repository is currently quotable in a paper.** The table below is the
> complete picture, including the numbers that look bad.

## Why this file exists

Three separate measurement defects were found in the evaluation harness. All
of them were in the *harness*, not the engine, which is why
`test_no_label_leakage.py` — scanning only `backend/app/shield/` and
`backend/app/security/` — passed the whole time while the measurements were
void.

| # | Defect | Effect |
|---|--------|--------|
| 1 | `benchmark/evaluate.py` passed `risk_score=expected_risk_score` into the engine, then compared the output to that value | Measured "how often does it avoid over-blocking once told the answer", not detection. Reported action accuracy was **89%**; the clean figure is **23%**. |
| 2 | `ground_truth_from_dict` read `data.get("label", "ALLOW")` while every generated corpus carries `expected_action` | All 600 SCI-600 items parsed as ALLOW. HUMAN_REVIEW/BLOCK support went to 0, macro-F1 was pinned near 0.2 for *every* baseline, and `false_allow` was structurally always 0. |
| 3 | `load_dataset` for AgentHarm fails on `datasets` 3.6.0 (`Feature type 'List' not found`) | Both splits loaded **zero rows**, so every AgentHarm number ever produced was computed on an empty set. |

Defect 3 is fixed by reading the cached Arrow file directly
(`_load_agentharm_arrow`), which also makes the external benchmark usable
offline.

## Current figures, by data source

| Source | Samples | Who labelled it | AgentShield result | Quotable? |
|---|---|---|---|---|
| `test_cases_v3_standard.json` | 100 | us (generated) | Action acc **23%**; 17% within ±0.15 | No |
| SCI-600 via `fair_evaluate.py` | 600 | us (generated) | **0.4350** acc / **0.4298** macro-F1 (production baseline) | No |
| AgentDojo (external) | 2000 | AgentDojo authors | **82.0%** attack recall, **26.2%** benign FPR, 0 BLOCK | Directionally |
| AgentHarm (external) | 208 | UK AISI authors | **28.8%** recall, 0 BLOCK | Directionally |

"Directionally" means: useful for comparing against baselines *in the same
run*, not as an absolute capability claim. All four runs use the corrected,
label-free harness.

## What the numbers actually say

**The engine's real detection ability is far better than the 23% headline.**
The 100-case set has 60 distinct tool names, most appearing exactly once. It
is a set of hand-built scenario snapshots, not a statistically meaningful
sample, and it cannot separate "engine fails to detect" from "fixture label is
inconsistent with the payload".

**Two structural findings, neither fixable by tuning weights:**

1. *The signal extractor cannot see prompt injection.* On AgentDojo it scores
   benign and attack payloads identically — content score mean 0.052 for
   benign vs 0.054 for attack, with ≥0.6 rates of 6.0% vs 5.1%. The attack
   signal lives in `user_task_prompt` / `injection_goal`, and
   `RiskSignalExtractor` only reads `tool_name` and `tool_input`. This is why
   BLOCK fires zero times on both external sets.

2. *The 100-case set and the engine's architecture disagree on 14 cases.* All
   `behavior_chain_risk` items use the tool name `multi_step_action` with the
   whole chain packed into one call's parameters (`{"steps": [...]}`). Chain
   risk emerges *between* calls in `AgentBehaviorGraph`; a single call carrying
   five steps has no graph to propagate through. Those cases measure the wrong
   thing and should be re-authored as separate events.

**Cost of the previous approach:** the earlier weight table (0.25–0.55, from
`e8070bd`) made BLOCK unreachable, so it was raised to 0.45–0.95 to make the
benchmark number go up. That was fitting the fixture. The current symptom is
the mirror image: 1571 of 1916 AgentDojo attacks land on HUMAN_REVIEW and
**none** reach BLOCK. Any future weight change must be justified against an
external set, with the before/after recorded here.

## What to do before writing a paper

1. Decide the product's actual question. AgentShield governs single tool
   calls; AgentDojo's threat model is prompt injection reaching a benign tool.
   Closing that gap means ingesting untrusted text as a first-class signal —
   a feature, not a tuning pass.
2. Re-author the 14 `multi_step_action` cases as multi-event chains so
   `AgentBehaviorGraph` propagation is exercised at all.
3. Regenerate `benchmark/results/paper/*` once the above are settled. Those
   files were produced by `paper_experiments.py` on the pre-fix harness and
   are **known invalid**; they have not been regenerated yet.
4. Keep the SCI-600 result labelled "our own synthetic set" wherever it
   appears. It is not evidence of generalisation.

## Regression protection

`backend/tests/test_evaluation_leakage.py` now pins both harness properties:

* predictions are bit-for-bit identical when labels are scrambled, changed,
  or deleted;
* the parsed ground-truth distribution spans all three classes and matches
  the source data exactly.

If a future change reintroduces leakage, those tests fail rather than the
paper quietly inheriting a fake number.
