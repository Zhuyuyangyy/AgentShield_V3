# Anonymous artifact snapshot

This is the sanitized artifact for the submitted paper. It is a frozen snapshot
built specifically for double-blind review, not a mirror of a development
repository.

What is deliberately absent, by construction: repository history, commit
identifiers, release tags, repository and owner names, remote URLs, CI run
links, and any local filesystem path. The identifiers that bind this artifact to
the reported numbers are **content digests**, which identify bytes rather than
people:

```text
canonical result artifact   SHA-256
3e33c72d230cb7e0788dc4412574054c19dfd496546573698d73bff7b6a90565

dataset manifest           SHA-256
948b94325ae1c8cfbe41bd205fee46b0f500215559ef5cd97a25c27fcf580049
```

The first digest is the evaluated result file shipped below; the second is the
manifest over the external dump described in [DATASET.md](DATASET.md).

## Layout

```text
.
├── README.md                     this file
├── DATASET.md                    data contract for the external dump
├── requirements.txt              runtime dependencies
├── requirements-test.txt         test and dataset dependencies
├── pytest.ini                    test discovery; puts backend/ on sys.path
├── backend/app/                  the engine under test, shipped whole so that
│                                 app.shield.v3_engine resolves without a
│                                 partial tree
├── benchmark/
│   ├── v04_trust_replay.py       the experiment (RQ3 Pareto ladder)
│   ├── agentdojo_trace_replay.py trace loader and single-trajectory replayer
│   └── results/
│       └── v0_4_trust_pareto.json  the canonical result artifact
├── scripts/
│   ├── verify_v04_reproduction.py canonical-artifact verifier
│   ├── fingerprint_agentdojo_dump.py  dataset fingerprint
│   └── draw_manuscript_figures.py     figure generator (needs matplotlib)
└── tests/
    └── test_verify_v04_reproduction.py
```

## Install

```bash
pip install -r requirements-test.txt
```

Python 3.11 or 3.12. The replay is pure Python over local files: it makes no
network calls, no model API calls, and reads no wall-clock time or RNG state.

## Reproduce the reported experiment

Both steps run from this directory. The output goes to `reproduced/`, which is
created on demand and is not part of the shipped snapshot.

```bash
python benchmark/v04_trust_replay.py --mode audit --max-trajectories 400 \
  --out reproduced/v0_4_trust_pareto.json
```

```bash
python scripts/verify_v04_reproduction.py \
  benchmark/results/v0_4_trust_pareto.json \
  reproduced/v0_4_trust_pareto.json
```

The first step needs the dump staged at the path recorded in
[DATASET.md](DATASET.md); check it with `python scripts/fingerprint_agentdojo_dump.py`
before running the replay.

One environment condition: `AGENTSHIELD_ENABLE_CORPUS_MARKERS` must be unset, or
set to `0`/`false`/`no`/`off`. It switches on corpus-specific markers that change
scoring, and the canonical run had it unset. The verifier refuses to report a
pass while it is enabled.

Verifier exit codes: `0` exact agreement, `1` mismatch with a per-field
difference list, `2` comparison not attempted. There is no tolerance mode: the
reported rates are quotients of small integers rounded to five decimals, so any
difference means a different run rather than rounding noise. On success it prints
the sampling and audit counts, which must read `97 benign + 400 attack
trajectories`, `rows: 13913`, `trajectories: 10536`.

Byte-identity of the reproduced file is stronger than the verifier's PASS and
can be checked directly:

```bash
sha256sum reproduced/v0_4_trust_pareto.json
```

## Run the tests

```bash
python -m pytest
```

`tests/test_verify_v04_reproduction.py` exercises the verifier against in-memory
fixtures and runs no replay; the backend suite under `backend/tests/` covers the
engine.

## Regenerate the figures

```bash
python scripts/draw_manuscript_figures.py
```

Writes a 300 dpi PNG and a vector PDF per figure into `figures/` (created on
demand). This needs `matplotlib`, which is not in either requirements file
because the manuscript build is a separate toolchain from the experiment.
Both figures are generated from `v0_4_trust_pareto.json`, so their values can be
checked against the artifact without trusting an image.

## What is not here

| Absent | Why |
|---|---|
| the ~50.9 MB Arrow dump | 8 MB per-file limit on the host; binaries are not anonymized; upstream terms |
| other staged datasets | not part of this experiment; the manifest is specific to the dump above |
| repository history, tags, commit ids | not identifiers of the research; content digests are |
| build residue, caches, dev-only harness state | not part of the artifact |

The numbers this artifact produces, and their interpretation limits, are stated
in the paper. The verifier and the fingerprint are comparison tools: they contain
no expected research numbers, they diff and report, and nothing they return feeds
back into the engine, the detector or the replay.
