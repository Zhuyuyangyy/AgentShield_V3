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

   Investigated further and this is **not closeable without label leakage**:
   for a given AgentDojo sample, the malicious and benign variants share the
   same final tool call — identical `tool_name` and identical `tool_input`.
   The only separating field is `injection_goal`, which is empty for benign
   samples and non-empty for attacks (85.8% of attack goals contain an email
   address; 0% of benign prompts do). Feeding that in would trivially score
   ~100% and would be pure leakage. AgentDojo's attack requires injected text
   to appear in a *previous* tool output and be read by the next LLM turn,
   which is outside a single-event governance point.

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

## Chain-level evaluation (`benchmark/evaluate_chain.py`)

Added to measure what the flat harness cannot: risk propagating across calls.
It replays a fixture's steps as separate tool calls joined by
`parent_node_id`, so `AgentBehaviorGraph` gets real edges. Seeded with
`risk_score=0.0`; labels are used only afterwards.

The mechanism works — replaying a chain produces the intended graph shape
(`nodes == steps`, `edges == nodes - 1`), and propagation fires: on V3-060 the
last node inherits 0.72 from upstream and is flagged as an amplifier.

Accuracy on the six `multi_step_action` cases is **0/6**, and this is left as
is rather than tuned away. Every one of those cases is labelled BLOCK with an
expected score of 0.94–0.99, but the payloads are short snake_case stage names
(`check_balance`, `withdraw_1000`, `phish_employee`). The engine tops out at
0.85 → HUMAN_REVIEW, which is a defensible verdict for `SELECT phone FROM
customers`; pushing every case to BLOCK would mean inflating weights until the
fixture passes, which is the same failure mode as before.

Generic offensive-security vocabulary was added to the content scorer
(`phish`, `exfil`, `reverse_shell`, `lateral_movement`, `prompt_injection`, …)
because those are recognised attack stages any reviewer would flag. Payloads
that merely name a *target* — `withdraw_1000`, `check_balance` — were
deliberately **not** added: scoring those is fixture-fitting, not detection.

## External harness audit (post-cleanup)

`external_experiment.py` still had two leakage paths after the first cleanup
round. Both are now closed and covered by tests.

**1. Label-derived `category`.** The AgentDojo adapter set
`category = attack_name if label == 1 else "benign"`. `risk_local_context`,
`risk_agent_shield` and `risk_agent_shield_graph` all read `category` through
`CATEGORY_PRIORS`. The leak was latent only because that table's keys
(`sensitive_data_access`, …) never matched AgentDojo's values (`direct`,
`ignore_previous`), so every lookup fell through to the 0.42 default. A single
added key would have activated it.

**2. LLM-Guard read `injection_goal`.** `predict_llm_guard` concatenated it
into the scanned text. That field is the benchmark's statement of what the
attack is trying to achieve — so this baseline was being shown the answer
while AgentShield was not. The comparison was meaningless in AgentShield's
disfavour.

Fixes: `benchmark/baselines.py` gained `observable_view()`, which strips every
evaluation-only field *including derived ones like `category`*; all scorers now
read through it. The adapter emits a label-free `category`, and
`predict_llm_guard` consumes the same observable surface as AgentShield.

### Consequential finding: "AgentShield V3 (full)" was not the production engine

That method routed through `risk_agent_shield_graph` — the hand-written
benchmark scorer — not the engine. Both it and the ablation variant now call
`V3ShieldEngine` directly with `risk_score=0.0`.

### Honest external numbers after the audit

Measured with `benchmark/external_experiment.py`, label-free, on AgentDojo
(1,500 samples; 1,416 attack / 84 benign):

| Metric | Value |
|--------|-------|
| `detection_recall` (REVIEW ∪ BLOCK) | **0.000** |
| `block_recall` (BLOCK only) | **0.000** |
| `benign_block_fpr` | 0.000 |
| `three_class_accuracy` | 0.056 |

The zeros are the result, not a harness fault: for a given AgentDojo sample the
malicious and benign variants carry identical `tool_name` and `tool_input`. The
attack lives in a *previous* tool output, which this governance point never
sees. A single-event gate has nothing to separate them on.

This supersedes the "82% recall / 26.2% FPR" figures previously listed here:
those came from an ad-hoc script calling `V3ShieldEngine` directly with a
different metric definition (REVIEW-or-BLOCK counted as detected), never from
the committed harness. They are removed rather than reconciled, per the
Evaluation Contract.

AgentDojo `confusion`: `{ALLOW: {ALLOW: 84}, BLOCK: {ALLOW: 1416}}`.

### Contract

`docs/research/EVALUATION_CONTRACT.md` now defines the three field classes
(runtime observable / derived runtime / evaluation-only), forbids derived
fields from class 3, fixes the metric names above, and requires the
regression tests that `test_evaluation_leakage.py` implements: label
invariance under scrambling, distribution sanity, determinism, and equal
observable surface across compared methods.
