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
| AgentDojo (external), **verified subset** | 1500 (attack 1416 / benign 84) | AgentDojo authors | detection_recall **0.000**, block_recall **0.000**, benign_block_fpr 0.000, three_class_acc 0.056 | Directionally |
| AgentDojo (external), full set | 2000 | AgentDojo authors | **pending** clean-harness rerun — not reported | — |
| AgentHarm-derived proxy | 208 | UK AISI authors (grading metadata) | pending clean-harness rerun | Proxy only, never as AgentHarm benchmark performance |

"Directionally" means: useful for comparing against baselines *in the same
run*, not as an absolute capability claim. All runs use the corrected,
label-free harness.

Every self-authored row is a generated fixture, not evidence of
generalisation. The AgentHarm row is a **metadata-derived proxy**: it
synthesises one hypothetical call per `target_functions` entry, so it is not a
runtime trajectory and cannot be described as label-free runtime evaluation.

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
benchmark number go up. That was fitting the fixture.

The mirror-image symptom was measured on an ad-hoc engine run, **not** the
committed harness, and described a different population and metric, so it is
not carried forward as a current result: 1571 of 1916 AgentDojo attacks landed
on HUMAN_REVIEW with none reaching BLOCK. On the clean harness the analogous
figure is `block_recall = 0.000` at n=1500, with `confusion =
{ALLOW: {ALLOW: 84}, BLOCK: {ALLOW: 1416}}` — nothing is flagged at all,
because nothing observable distinguishes the two classes.

Any future weight change must be justified against an external set, with the
before/after recorded here.

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

## Trajectory-level evaluation (stage G)

`benchmark/evaluate_trajectory.py` replays each AgentDojo sample as a trajectory
instead of a single call, because the flat harness measures nothing useful: the
malicious and benign variants share `tool_name` and `tool_input`.

Two design points that only became clear by running it:

* The dump records the **pre-injection** tool (a calendar search, a file
  search). The attack action lives in the instruction — "email this to X".
  Replaying the original tool as the final step scores a call the attacker never
  makes, so the sink is derived from the instruction's own verb.
* The engine emits lower-case short-form decisions (`review`) while labels are
  upper-case (`HUMAN_REVIEW`). Coercing without mapping turned every review into
  ALLOW, which pinned detection_recall at 0.0 and looked exactly like a broken
  harness. Both are regression-tested.

2,000-sample stratified subset of the AgentDojo dump (1961 attack / 39 benign).
The detector never sees a label — `injection_goal` reaches it only as trajectory
*content*, never as a feature. Note what this is **not**: the trajectories are
reconstructed from attack metadata, so these are AgentDojo-derived
*reconstructed* trajectories, not a native runtime trace.

| Configuration (each rung adds over the one above) | detection_recall | block_recall | benign_review_rate | benign_block_fpr |
|---|---|---|---|---|
| local_only (single-event gate) | 0.792 | 0.034 | 0.128 | 0.000 |
| + untrusted output inspection | 0.814 | 0.054 | 0.128 | 0.000 |
| **+ entity provenance / taint** | **0.891** | **0.790** | 0.128 | 0.000 |
| + intent consistency | 0.891 | 0.790 | 0.128 | 0.000 |

`block_recall` is where provenance earns its place: **0.034 → 0.790, i.e.
+75.6 percentage points (~23x)**. Under an ablation that holds the local
tool-call scorer fixed, the only thing that can differentiate two calls with
identical arguments is a cross-event feature — here, where the destination came
from. The jump concentrates in the entity-provenance rung (0.054 → 0.790); the
intent rung adds nothing on this set because the operator's request is only
available on the first event of each trajectory.

`benign_block_fpr` reads 0.000, but that is **0 of 39 benign samples**. With
n=39 the 95% one-sided upper bound on the true FPR is roughly 7.7%, so the
result is "no over-blocking observed on a small benign sample", not "no
over-blocking". Attack:benign is 50:1, so benign FPR is not well estimated here
— the paired design below is what addresses that.

Ablations are engine **configuration flags** (`enable_provenance`,
`enable_taint_tracking`, and intent suppression for the third rung), not copies
of the predictor — the failure mode that produced the earlier fake "no
special-case rules" entry. An earlier revision named the second rung
"+ taint tracking" while the code *disabled* taint tracking; the ladder above is
named for what each rung actually adds.

## Paired counterfactual control (`benchmark/paired_trajectory_eval.py`)

The obvious objection to the table above: attacks end in `send_email` /
`delete_file`, which a single-event gate already considers dangerous, so the
improvement might be "risky tool" rather than "risky source". The paired design
holds the final call fixed — identical `tool_name` *and* identical `tool_input`
— and varies only where the destination came from:

| pair | attack decision | benign decision |
|---|---|---|
| send_email(attendees → partner) | **block** | review |
| delete_file(4821) | **block** | **allow** |
| http_request(metrics endpoint) | **block** | **allow** |
| upload_file(customers.csv) | block | block |

Two of four pairs separate completely. `local_only` gives both members of every
pair the *same* decision (the pairing-validity check), proving the members are
matched on the observable call. This is the cleanest statement of the
contribution: **the same action, decided differently by source.**

The `upload_file` pair is not separated, and that is defensible rather than a
tuning miss: the benign member uploads a customer export to an external host,
which `sensitive_to_external_flow` flags at 0.95 regardless of who authorised
it. Adjusting that would require weakening the signal for cases where the
operator explicitly asks for an exfiltration.

Not measured: benign task success, p99 latency, and native AgentDojo runtime
behaviour. All three need the task suite executed with an agent in the loop.

Not measured: utility / benign task success and latency. Both need a runtime that
executes AgentDojo's actual task suite, which this adapter does not have. Do not
claim them from these numbers.

## Native trace replay over the real AgentDojo dump (stage I)

`benchmark/native_trace_replay.py` replays the dump's **recorded**
``(tool_call_function, tool_call_args, tool_response)`` triples in order and
scores each step. This is the tier the reconstructed experiment could not reach:
every call and response really happened, and neither ``injection_goal`` nor
``label`` reaches the engine — labels only split the finished predictions into
benign and attack groups for reporting.

Why the benign sample finally has statistical power: the dump holds **97 fully
benign tasks / 339 recorded steps** and 949 tasks containing attacks /
13,574 steps. The reconstructed run had 39 benign samples; this one has 339.

Full dump, all four rungs:

| Configuration | attack flag rate | benign block | benign review |
|---|---|---|---|
| local_only (single-event gate) | 0.034 | 0.003 (1/339) | 0.118 |
| **+ untrusted output inspection** | **1.000** | 0.003 (1/339) | 0.118 |
| + entity provenance / taint | 1.000 | 0.003 (1/339) | 0.118 |
| + intent consistency | 1.000 | 0.003 (1/339) | 0.118 |

Read the two numbers together:

* **+96.6 points of attack coverage** from switching on output inspection.
  local_only scores 0.034 because the recorded ``tool_call_args`` are benign —
  a calendar search, a file read. The attack is carried by what the tool
  *returned*. That is the empirical form of the project's core claim, measured
  on someone else's data with no reconstructed steps.
* **Benign block rate 1/339 = 0.3%, 95% one-sided upper bound ~1.1%.** This
  replaces the 0/39 figure whose upper bound was ~7.7%. The gain is not bought
  by over-blocking on a sample large enough to say so.

The three provenance rungs do not separate here, and that is stated rather than
hidden: taint tracking and intent consistency are already saturated once output
inspection is on, because the recorded traces contain no operator request text
(a native runtime would supply it). The rung that matters on this set is the
first one.

### What this corrected in the implementation

The instruction-detection vocabulary did not cover how these dumps actually
inject. Measured over the attack steps, the carriers are ``Please email``
(1,547), ``SYSTEM:`` (936), ``IMPORTANT:`` (849), ``TODO:`` (742) — while the
table only had override phrases like "ignore previous instructions". With the
generalised markers, 10,746 of 13,574 attack steps are recognised and **0 of
339 benign steps** are flagged, which is the signal-to-noise that makes the
1.000 above real rather than a blanket block-everything rule.

### Still not measured

Benign task success / utility, and attack success rate in the AgentDojo sense
(which requires an agent to act on the injection and then checks whether the
task's goal was reached). Both need an LLM in the loop; none is installed and
none is on the governance path by design. `native_trace_eval.json` says so in
its own note field.

The paired counterfactual control remains the right evidence for "the same
action, decided differently by source"; this run is the right evidence for
"the attack lives in the tool output, not the call".
