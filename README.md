# 🪞 Measurement Mirror

<p align="center">
  <img src="docs/measure_mirror_og.png" alt="Measurement Mirror" width="500">
</p>

[![CI](https://github.com/mirror-stack/measure-mirror/actions/workflows/ci.yml/badge.svg)](https://github.com/mirror-stack/measure-mirror/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![core deps: zero](https://img.shields.io/badge/core%20deps-zero-brightgreen.svg)](pyproject.toml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)

**Catch AI evaluation illusions — false positives and false negatives — automatically.**  
Zero training · Deterministic · Stdlib-only core (Python 3.10+; the `judge` and `subspace` modules are optional and do have dependencies).

> Built while honestly killing our own project.  
> The makers ran it on themselves first. → [🦋 Origin Story](docs/CHRONICLE.md)

**[📖 Full Probe Guide →](docs/GUIDE.md)** — detailed explanations, worked examples, and workflows for all 28 probes
**[📜 MIRROR-SPEC v1.1 →](docs/SPEC.md)** — the normative ledger format & verification protocol (ratified 2026-07-02, amended 2026-07-17; this package is its reference implementation)
**[🦋 Catalog of Measurement Illusions →](catalog/README.md)** — 80 real sealed cases of measurement deceiving its own authors (gaming · self-catch · false-negative guards · contamination)

> **🪞🔎🪪 New — Mirror Stack** ([`stack/`](stack/)): measure-mirror is the *claims* layer of a
> three-mirror integrity stack for autonomous research agents (claims · actions · provenance,
> joined by five conventions + one `verify-all` command). Includes a real case study:
> **[an agent that retracted its own experiment before spending a single token](stack/CASE_STUDY_compute_governor.md)**
> — preregistration → power-check design fix → adversarial amendments → prior-art retraction,
> with the actual chain-sealed ledger bundled so you can verify it yourself.
> What it guarantees — and the one thing no tool can (independence) — is mapped in four pillars:
> **[PILLARS.md](stack/PILLARS.md)** (integrity · non-erasure · falsifiability · verifiability).
> measure-mirror itself is unchanged (feature-frozen core; the stack adds conventions, not probes).

| Tool | Audits | Question |
|---|---|---|
| 🪞 **measure-mirror** (you are here) | AI evaluation claims | **Is the claim honest?** |
| 🪪 [action-mirror](https://github.com/mirror-stack/action-mirror) | Agent behaviour | Who did what, **provably**? |
| 🔎 [provenance-mirror](https://github.com/mirror-stack/provenance-mirror) | Content authenticity | Is the **origin** proven? |
| 👁 [mirror-witness](https://github.com/mirror-stack/mirror-witness) | Cross-operator witness board | Who else **witnessed** it? |

💬 **[Discussions](https://github.com/orgs/mirror-stack/discussions)** — questions · ideas · independent reproductions welcome.
🔁 **[Reproduce this in 15 minutes →](https://github.com/mirror-stack/measure-mirror/issues/new?template=reproduce-report.yml)** — verify a sealed ledger, tamper with it, watch it break. Failures are as welcome as successes.

---

## The Problem

AI/ML papers routinely overclaim. The most common failure modes:

| Illusion | How it happens |
|---|---|
| Small-sample mirage | n=9, acc=55.6% reported as breakthrough |
| Post-hoc metric swap | Register accuracy, report the F1 that happened to look better |
| Crippled baseline | Compare against a deliberately weak competitor |
| Data leakage | Train/test overlap inflating every number |
| Scope overreach | "Works on task A" claimed as "general reasoning" |

Measurement Mirror catches these **structurally**, not by opinion.

> **Precisely what it does (and does not).** It runs deterministic checks on the inputs *you
> provide* — it is **input-driven**, not an autonomous flaw-hunter. Arithmetic/statistical probes
> (small-sample CI, GRIM, power, multiple-comparisons) are fully deterministic. But design-flaw
> probes (crippled baseline, gaming, scope) only fire on the baseline / reward terms / scopes you
> *declare* — the tool cannot discover a flaw you hide, and many real catches are still **your
> judgment**, guided by the [discipline](https://github.com/mirror-stack/measure-mirror/tree/main/stack/DISCIPLINE.md).
> It makes honesty *provable*; it does not *force* it.

---

## Install

```bash
pip install -e .                        # core — stdlib only, no dependencies
pip install -e ".[mcp]"                 # + MCP server for AI agents
pip install -e ".[judge]"               # + LLM-as-a-Judge runner (openai / anthropic)
pip install -e ".[subspace]"            # + subspace executor, layer B (numpy)
pip install -e ".[test]"                # + pytest plugin
pip install -e ".[mcp,judge,subspace,test]"   # everything
```

CLI entry point: `mm`  
MCP entry point: `mm-mcp`

---

## Quick Start

### CLI

```bash
# Step 1 — BEFORE running your experiment: seal the criteria
#   always include a kill-condition — a claim you can't fail is unfalsifiable
mm register my_model --metric acc --min-n 200 --baseline 0.5 --pass 0.60 \
           --kill-threshold 0.55 --kill-direction below

# Step 2 — AFTER evaluation: audit the result against the sealed criteria
mm audit my_model --acc 0.72 --n 500   # pass the result inline — nothing else to create

# …or audit from a result file you write yourself:
echo '{"claim_id":"my_model","metric":"acc","acc":0.72,"n":500}' > my_model.json
mm my_model                            # auto-loads my_model.json
mm audit --file my_model.json          # or any path via --file
```

`my_model.json` format: `{"claim_id": "my_model", "metric": "acc", "acc": 0.72, "n": 500}`

### Python API

```python
from measure_mirror import mm

LEDGER = "mm_ledger.jsonl"

# Your train / test item ids (disjoint here → no leakage)
train_items, test_items = list(range(800)), list(range(800, 1000))

# ① Before experiment — seal criteria (tamper-evident hash)
#    kill_threshold seals a falsification criterion — never omit it
mm.preregister(LEDGER, "my_model",
               metric="acc", min_n=200, baseline=0.5, pass_threshold=0.60,
               kill_threshold={"metric": "acc", "threshold": 0.55, "direction": "below"})

# ② After evaluation — full 7-probe audit at once
findings = mm.full_audit(
    LEDGER, "my_model",
    reported_metric="acc", reported_acc=0.72, n=500,
    baseline=0.5,
    competing_name="strong_baseline", competing_acc=0.68,   # ② fairness
    reward_terms=["cross_entropy"],                          # ③ gaming check
    train_items=train_items, test_items=test_items,         # ④ leakage
    seed_results=[0.70, 0.72, 0.74],                         # ⑤ multi-seed
    claimed_scope=["reasoning"], tested_scope=["task_a"],    # ⑥ scope
)
mm.report("my_model", findings)

# Individual probes
mm.report("fairness", [mm.baseline_fairness("vs GRU", 0.72, 0.68)])
mm.report("leakage",  [mm.leakage_check(train_items, test_items)])
mm.report("seeds",    [mm.multiseed_check([0.70, 0.72, 0.74], baseline=0.5)])
```

### Regression / Continuous Metrics

For MSE, Pearson r, RMSE, and other non-binary metrics:

```python
findings = mm.continuous_audit(
    LEDGER, "my_regressor",
    reported_metric="mse", reported_value=0.10,
    baseline_value=0.15, n=500,
    higher_better=False,   # lower MSE is better
    std=0.02,              # optional: enables effect-size check
)
mm.report("regression", findings)
```

### pytest Integration (CI Gate)

```python
# conftest.py
pytest_plugins = ["measure_mirror.pytest_plugin"]

# test_eval.py
from measure_mirror import mm
from measure_mirror.pytest_plugin import assert_clean

def test_my_model_is_real():
    findings = mm.audit("ledger.jsonl", "my_model",
                        reported_metric="acc", reported_acc=0.78, n=1000)
    assert_clean(findings)   # FAIL findings → test fails → CI goes red
```

---

## Three Verification Tiers

You don't need to memorize 28 probes — there are exactly three ways to use the mirror:

```bash
# FULL — one shot, everything applicable runs automatically
mm verify --file results.json

# GROUP — restrict to verification groups
mm verify --file results.json --groups stats judge
mm verify --list-groups

# INDIVIDUAL — any probe directly (Python)
mm.grim_check(reported_acc=0.33, n=10)
```

```python
from measure_mirror import mm

# FULL: probes activate based on which keys exist in data
findings = mm.verify("ledger.jsonl", {
    "claim_id": "my_model", "acc": 0.72, "n": 500,        # → ledger + stats
    "seed_results": [0.70, 0.72, 0.74],                    # → ⑤
    "scores": [3, 7, 5, 8, 4],                             # → judge ⑰
})

# GROUP: same data, judge group only
findings = mm.verify("ledger.jsonl", data, groups=["judge"])
```

`verify()` runs only the probes whose inputs are present — an empty key fires nothing,
extra keys fire extra probes. The `data` keys are identical to the JSON file format.

## Probes by Verification Group

### `ledger` — pre-registration & ledger integrity

| Probe | # | Catches |
|---|---|---|
| `preregister` / `audit` | ① | Post-hoc metric swap · sample underrun · ledger tampering |
| `verify_chain` | ① | Deleted/inserted entries · ledger tampering |
| `cascade_check` | ⑫ | Claim or transitive dependency retracted → FAIL/WARN stale |

### `stats` — statistical validity

| Probe | # | Catches |
|---|---|---|
| `audit` — Wilson CI | ④a | Results indistinguishable from chance (small sample) |
| `audit` — direction | ④a | Performance worse than baseline (anti-signal) |
| `multiseed_check` | ⑤ | Unstable signal / lucky seed |
| `too_good_check` | ⑦ | Suspiciously large Δ over baseline |
| `power_check` | ⑧ | n too small to detect minimum effect (false-negative guard) |
| `multiple_comparisons_check` | ⑨ | k>1 experiments in ledger — Bonferroni correction alarm |
| `grim_check` | ⑩ | Reported acc × n is arithmetically impossible (fabricated value) |

### `design` — experiment-design fairness

| Probe | # | Catches |
|---|---|---|
| `baseline_fairness` | ② | Crippled / tied / reversed baseline |
| `gaming_check` | ③ | Metric directly in reward/loss (self-fulfilling) |
| `leakage_check` | ④a | Train∩test data contamination |
| `scope_check` | ⑥ | Claimed scope wider than tested scope |
| `falsifiability_check` | ⑪ | No kill-condition → unfalsifiable; kill_threshold triggered → claim is dead |
| `anchor_basis_check` | ㉑ | Positive-control anchor rests on a static "structurally guaranteed" argument instead of measured dynamics |
| `threshold_provenance_check` | ㉒ | Pass/kill threshold re-derived from the observed distribution (self-calibrating) instead of externally fixed |
| `content_delta_check` | ㉓ | Judgment on agreement/match alone (rubber-stampable) without a content-delta check |
| `anchor_line_source_check` | ㉔ | Positive-control anchor **line** copied from a stronger/other cell instead of aligned to this cell's sealed separatrix |
| `anchor_cell_check` | ㉕ | Positive-control anchor **cell** sits on the threshold/boundary (straddles it seed-to-seed) instead of a deep regime |

> ㉑–㉕ are **grounding probes** — the mutual-grounding arc's sealed defense laws (anchors need measured dynamics · thresholds externally fixed · judgment needs a content check · anchor line aligned to this cell · anchor cell in a deep regime). ㉔㉕ are the other two anchor-reproduction-failure subtypes (catalog: 3 real cases), completing the anchor-discipline trio with ㉑. Analogy from a micro-substrate experiment; structure only. See `docs/GROUNDING_PROBES_DESIGN.md`.
>
> ㉑㉒㉔㉕ can also be **declared at seal time**: `preregister(..., anchor_basis="dynamics-measured", threshold_source="external-fixed", anchor_cell="deep-regime", anchor_line_source="separator-aligned", known_confounds=[...])` stores the declarations in the sealed entry and `audit()` runs the probes on them automatically (㉑㉒ = SPEC amendment A1; ㉔㉕ + `known_confounds` INFO = A2). ㉓ stays on the `verify(data)` path (`judgment_basis` describes the analysis, not the preregistration). Calibrated: FP/FN labeled set in `eval/self_fpfn/` (grounding core 0 FN / 0 FP; disclosed fail-closed vocab limitation → see `eval/self_fpfn/RESULTS.md`).

### Pre-compute seal lint ㉗ — standalone, runs *before* compute

| Probe | # | Catches |
|---|---|---|
| `prereg_lint` | ㉗ | Seal *quality*, not just presence: kill-condition leaked into the `metric` field (malformed call — the human eye sees a criterion, the parser sees none), a quantified kill written as free text with no structured `kill_threshold`, a pass bar at/below declared chance, `min_n` below the small-sample floor, or no pre-seal machine-checks declared |

> ㉗ is deliberately **not** part of the `verify()` umbrella or any group: it is a *pre-compute*
> check (run it right after sealing, before spending compute), while `verify()`/`audit()` run at
> report time. It fires automatically inside `mm_register` (the response carries the lint), and
> the mirror-stack compute gate BLOCKs on a ㉗ FAIL. Declare the cheap checks you ran before
> sealing with `preregister(..., pre_seal_checks=["reachability-smoke", "mass-balance-audit",
> "neutral-control", "manipulation-check", "positive-control"])` — declaring none draws an INFO
> nudge. Grounds: a real arc lost silent compute to exactly these defect classes
> (semantic-fuel cell arc, 2026-07; 3 self-catches sealed in the catalog).

### `negative` — Resolved-Negative closure gate

| Probe | # | Catches |
|---|---|---|
| `negative_audit` | ⑬ | Negative conclusion has too few independent angles, unregistered angles, or scope overshoot |

### `subspace` — "the gain lives in a few directions" claims

⚠️ **A declaration auditor, not a recomputer.** It reads the submitted table, never the basis or the model, so a falsified `energy_kept` passes. The C1–C4 consistency laws raise the cost of a false table — they do not close the hole.

🟡 **Validated on one experiment family; a second one killed the generalization, and the gap it exposed is now closed.** Replaying the same planted recipes on a different real substrate (768-d DINO embeddings from another arc; seal `5c78e503`, result `am 2ab6eab7`) scored **8/10 against a pre-committed bar of 1.0** — FP=1, FN=1. The load-bearing failure: **㉘ had no guard against a swapped-role claim** — the `relabeled_dof` case passed on the first substrate only because the shuffled arm did not beat the null *there*. That pass looked like a guard and was substrate luck.

🟢 **Closed in v0.31.0 by `dof-outperforms-target`** — a coherence law, not a heuristic: destroying the claimed structure cannot *add* effect, so a control that beats its target means the labels are swapped or the control is not one. Sealed on the FM×CDE holdout at **22/22** (`582f4130`, result `am 45d5f3d2`), and it closes the substrate-2 false negative too. It catches the swap only when the true target genuinely beats its control; when the two are indistinguishable the swap stays invisible — and so does the effect it would hide. Full write-up: [eval/subspace_substrate2/RESULTS.md](eval/subspace_substrate2/RESULTS.md).

| Probe | # | Catches |
|---|---|---|
| `subspace_claim_check` | ㉘ | Undeclared bit-reproduction anchor · retained energy not matched across arms · missing degrees-of-freedom control · target not clearing the null ladder (paired sign-flip, exact 2ⁿ for n ≤ 14) · a `matched_null` arm that fails its certificate (neither collapse nor survival) · a saturated grid · the basis estimated on the very samples the effect is scored on · **a degrees-of-freedom control that outperforms the target it controls for** (destroying the claimed structure cannot add effect, so the labels are swapped or the control is not one) |

#### ㉘ layer B — the executor (`measure_mirror.subspace`, needs numpy)

```bash
pip install "measure-mirror[subspace]"
```

Layer A audits a table. **Layer B produces one from the arrays**, then hands it
straight back to layer A — so your own run is judged by the same auditor a
stranger's claim is. It does not supersede layer A and does not widen what
layer A can see.

|  | layer A — `subspace_claim_check` | layer B — `measure_mirror.subspace` |
|---|---|---|
| sees | the submitted table only | the arrays |
| dependencies | stdlib | numpy |
| audits | anyone's claim | only your own run |
| cannot catch | a consistent forgery | anything it did not itself run |

```python
from measure_mirror.subspace import build_subspace_report, overfit_smallsample
from measure_mirror import subspace_claim_check

report   = build_subspace_report(data_by_seed, arms=arms, effect_fn=my_effect,
                                 energy_targets=(0.5, 0.7, 0.9), anchor=anchor)
findings = subspace_claim_check(report)         # layer A audits layer B
```

Two things layer B can do that a table cannot encode:

- **Content-addressed sample ids.** `basis_fit_ids` / `effect_eval_ids` are
  sha256 of each row's float64 bytes, not positional labels — so
  `estimation-eval-overlap` tests whether the same rows were actually reused,
  which renaming a split cannot defeat.
- **`overfit_smallsample`** — layer A can only *lint* `underdetermined-basis`
  from a declared `n_basis_fit`; whether a basis fitted from that few samples
  really aligned with noise is a property of the estimation run. Layer B runs
  it: synthetic isotropic Gaussians, signal 0, `n_basis ∈ {20, 50, 200}`, and
  the target arm must not clear the null ladder. **A positive control runs at
  every `n`** — without it, "the target did not win at n=20" is
  indistinguishable from "the instrument is blind at n=20", and any `n` whose
  positive control fails is reported *withheld*, never counted as a pass.

These are executors, not `verify()` probes, and are deliberately not counted in
the probe registry above.


### `judge` — LLM-judge reliability

| Probe | # | Catches |
|---|---|---|
| `judge_consistency_check` | ⑭ | LLM judge flip-rate too high — unreliable judge detector |
| `judge_bias_check` | ⑮ | Judge systematically favors position A or B — position bias detector |
| `inter_rater_agreement` | ⑯ | Cohen's κ between two *different* judges below threshold (standalone-only) |
| `judge_score_sanity` | ⑰ | Judge assigns identical/near-identical scores — degenerate distribution |
| `judge_swap_check` | ⑱ | Verdict stays with the slot after AB→BA swap — judge reads position, not content |

### `ranking` — leaderboard integrity

| Probe | # | Catches |
|---|---|---|
| `judge_transitivity_check` | ⑲ | A>B>C>A preference cycles — judge has no consistent quality scale |
| `ranking_stability_check` | ⑳ | "A beats B" flips under bootstrap resampling — ranking mirage |

| Utility | Purpose |
|---|---|
| `anchor` | Print tamper-evident ledger snapshot (hash + head seal) to stdout for external archival |
| `calibrate` | Self-test: 5 synthetic known-good/bad cases; confirms tool health |
| `witness` | Execute a command, capture output, seal tamper-evident run record |
| `retract` | Append a chain-linked retraction entry; cascades to dependents via cascade_check |
| `certificate` | Issue a sealed verification certificate: CERTIFIED / WITH-WARNINGS / UNVERIFIED / REJECTED |
| `badge` | Render a certificate as an embeddable markdown / SVG badge (verdict-colored) |

### Chain hash ledger (① extended)

Every `preregister()` call now embeds the previous entry's seal into the new one
before computing the SHA-256. This makes the ledger tamper-evident end-to-end:

```python
# verify the entire ledger chain at any time
findings = mm.verify_chain("mm_ledger.jsonl")
mm.report("ledger integrity", findings)
```

Catches: entry deletion, entry insertion, content modification.  
**Documented limitation**: complete file deletion + fresh re-registration is not caught —
commit the ledger file to git for that guarantee.

### Power check ⑧

```python
# warn when n is too small to detect a real effect
f = mm.power_check(n=50, baseline=0.5, min_detectable_effect=0.05)
# ⚠️  n=50 insufficient to detect Δ=+0.05 at 80% power (need n≥388)

# or activate via full_audit
findings = mm.full_audit(LEDGER, "my_model", ..., min_detectable_effect=0.05)
```

### Multiple comparisons ⑨

```python
# warn when k>1 experiments share a ledger (Bonferroni)
f = mm.multiple_comparisons_check("mm_ledger.jsonl")
# ⚠️  k=3 experiments → Bonferroni α=0.0167 (not 0.05)

# or activate via full_audit
findings = mm.full_audit(LEDGER, "my_model", ..., check_multiplicity=True)
```

### Falsifiability ⑪ — the Popper gate

```python
# Register BEFORE the experiment — seal what would kill the claim
mm.preregister("mm_ledger.jsonl", "my_model",
               metric="acc", min_n=200, baseline=0.5, pass_threshold=0.60,
               # human-readable (optional)
               kill_condition="accuracy on held-out test drops below 0.55",
               # structured: auto-evaluated at audit time
               kill_threshold={"metric": "acc", "threshold": 0.55, "direction": "below"})

# After the experiment — audit checks ⑪ automatically
findings = mm.audit("mm_ledger.jsonl", "my_model",
                    reported_metric="acc", reported_acc=0.50, n=500)
# 🔴 [⑪ falsifiability] Kill condition triggered: acc=0.5 < 0.55.
#    Claim 'my_model' is falsified by its own pre-registered criterion.

# Or check standalone
f = mm.falsifiability_check("mm_ledger.jsonl", "my_model", reported_acc=0.50)
```

```bash
# CLI
mm register my_model --metric acc --min-n 200 --baseline 0.5 --pass 0.60 \
  --kill "accuracy < 0.55 on held-out" \
  --kill-threshold 0.55 --kill-direction below
```

Claims registered without any `kill_condition` or `kill_threshold` receive a
`WARN: Unfalsifiable` at audit time — operationalizing Popper's criterion as a
code contract. OSF pre-registration accepts hypotheses; this is the first tool
that also seals the kill condition.

### Retraction cascade ⑫

```python
# Register a claim that depends on prior work
mm.preregister("mm_ledger.jsonl", "model_v2",
               metric="acc", min_n=200, baseline=0.5, pass_threshold=0.60,
               depends_on=["dataset_v1", "baseline_eval"])

# Later: dataset_v1 turns out to have contamination — retract it
mm.retract("mm_ledger.jsonl", "dataset_v1", "train/test overlap discovered")

# cascade_check flags model_v2 as STALE automatically
f = mm.cascade_check("mm_ledger.jsonl", "model_v2")
# ⚠️  [⑫ retraction-cascade] Claim 'model_v2' is STALE: depends (transitively) on
#     retracted claim(s): 'dataset_v1'

# audit() runs cascade_check automatically — only WARN/FAIL are appended
findings = mm.audit("mm_ledger.jsonl", "model_v2",
                    reported_metric="acc", reported_acc=0.72, n=500)
```

```bash
# CLI
mm register model_v2 --metric acc --min-n 200 --baseline 0.5 --pass 0.60 \
  --depends-on dataset_v1 baseline_eval

mm retract dataset_v1 --reason "train/test overlap discovered"
```

The retraction entry is **chain-linked** — deleting it from the ledger breaks the
chain and is detected by `verify_chain()`. Retraction propagates regardless of
publication order: a claim built on a retracted foundation is automatically stale.

### Negative-claim audit ⑬ — the premature-closure gate

A single negative result may reflect a frame flaw, not a universal wall.
`negative_audit` gates "Resolved-Negative" conclusions: you must present
≥ `min_angles` independent pre-registered experiments before closing.

```python
# Register each independent angle BEFORE running the experiment
for angle_id in ["oee_test_wave", "oee_test_bilinear", "oee_test_alife"]:
    mm.preregister("mm_ledger.jsonl", angle_id,
                   metric="oee_score", min_n=100, baseline=0.5, pass_threshold=0.0)

# After all angles converge negative — gate the closure
f = mm.negative_audit("mm_ledger.jsonl",
                      angles=["oee_test_wave", "oee_test_bilinear", "oee_test_alife"],
                      min_angles=3)
# ✅ [⑬ negative-audit] 3/3 independent pre-registered angle(s) verified —
#    negative conclusion is supported.

# Optional scope check: negative conclusion must not overgeneralize
f = mm.negative_audit("mm_ledger.jsonl",
                      angles=["oee_test_wave", "oee_test_bilinear", "oee_test_alife"],
                      conclusion_scope=["all_substrates"],   # claimed scope
                      tested_scope=["in_silico"])            # actually tested
# 🔴 [⑬ negative-audit] conclusion scope includes untested domain(s): ['all_substrates'].
```

```bash
# CLI
mm negative --angles oee_test_wave oee_test_bilinear oee_test_alife --min-angles 3

# Or activate inside full_audit
findings = mm.full_audit(LEDGER, "main_claim", ..., angles=["a1", "a2", "a3"])
```

| Condition | Level |
|---|---|
| `len(angles) < min_angles` | FAIL — premature closure |
| Any angle not pre-registered | FAIL — unverifiable evidence |
| `conclusion_scope ⊄ tested_scope` | FAIL — scope overshoot |
| A registered angle is retracted | WARN — weakened case |
| All checks pass | OK |

### LLM-as-a-Judge probes ⑭⑮⑯⑰

LLM judges introduce their own failure modes that numeric metrics don't catch.
The four judge probes audit the **judge itself**, not just the model being evaluated.

```bash
pip install "measure-mirror[judge]"   # adds openai and anthropic
```

```python
from measure_mirror.judge import anthropic_judge, openai_judge, judge_run

# Build a judge callable (pairwise A-vs-B mode)
judge_fn = anthropic_judge(model="claude-opus-4-8")
# or: judge_fn = openai_judge(model="gpt-4o")

# Each item: {"prompt": str, "a": str, "b": str}  (pairwise)
#            {"prompt": str, "response": str}       (rating, pairwise=False)
pairs = [
    {"prompt": "Summarize quantum entanglement",
     "a": "candidate_A output", "b": "candidate_B output"},
    ...
]

# judge_run calls judge_fn runs×len(items) times,
# fires ⑭⑮⑯⑰(⑱) automatically, and seals a chain-linked entry.
result = judge_run("mm_ledger.jsonl", "my_llm_eval",
                   judge_fn=judge_fn,
                   items=pairs,
                   runs=2,               # run each item twice → ⑭ consistency
                   pairwise=True,        # A-vs-B → ⑮ bias check
                   swap_positions=True)  # extra AB→BA pass → ⑱ swap test

for f in result["findings"]:
    print(f"  {f.level}  [{f.probe}]  {f.msg}")
```

**The checks triggered by `judge_run`:**

| Probe | Catches |
|---|---|
| `judge_consistency_check` ⑭ | Judge gives different verdict on re-run (stochastic / unreliable) |
| `judge_bias_check` ⑮ | Judge systematically favors position A or B regardless of content |
| `judge_score_sanity` ⑰ | Judge assigns identical / near-identical scores to everything |
| `judge_swap_check` ⑱ | Verdict stays with the slot after AB→BA swap (content-blind judge) |

⑯ `inter_rater_agreement` is **standalone-only**: it compares two genuinely
different judges; re-running the same judge is already covered by ⑭.

Unparseable judge responses score -1 and are **excluded from all probes**; a
`judge-parse` WARN fires when the failure rate exceeds 10% (FAIL when nothing parsed).

**Why ⑱ matters** — a deterministic judge that never reads the responses passes
⑭ (perfectly consistent), ⑮ (balanced win-rate), ⑯ (κ=1.0), and ⑰ (varied scores).
Only swapping A and B exposes it: a content-driven judge must invert its verdict,
a content-blind judge keeps choosing the same slot. Run the demo:

```bash
python examples/demo_judge.py   # no API key needed — mock judges
```

**Standalone usage (bring-your-own scores):**

```python
from measure_mirror import mm

# ⑭ consistency — did the judge flip its verdict?
score_pairs = [(1, 1), (0, 0), (1, 0), (0, 0), (1, 1)]  # (run1, run2) per item
f = mm.judge_consistency_check(score_pairs, flip_threshold=0.20)
# ✅  flip rate 20.0% ≤ 20.0% (1/5 flips). Consistent.

# ⑮ position bias — does A always win?
results = [0, 0, 0, 0, 0, 0, 0, 1, 0, 0]  # 0=A won, 1=B won
f = mm.judge_bias_check(results, bias_threshold=0.60)
# 🔴  Position A win rate 90.0% > 60.0%. Strong position bias detected.

# ⑯ inter-rater — Cohen's κ between two raters / runs
matrix = [(1, 1), (0, 0), (1, 1), (0, 1), (1, 0), (0, 0)]
f = mm.inter_rater_agreement(matrix, min_kappa=0.40)
# ⚠️  Cohen's κ=0.333 < 0.40 — fair agreement only.

# ⑰ score sanity — degenerate distribution?
scores = [8, 8, 8, 8, 8, 8, 8, 7, 8, 8]  # 90% are 8
f = mm.judge_score_sanity(scores)
# ⚠️  90% of scores are '8' — near-degenerate distribution.

# ⑱ position-swap — does the verdict follow content or slot?
forward = [0, 1, 0, 1, 0]   # winners in (A, B) order
swapped = [0, 1, 0, 1, 0]   # winners after AB→BA swap — identical = locked!
f = mm.judge_swap_check(forward, swapped)
# 🔴  Position-lock rate 100.0% > 65.0%. Judge is reading position, not content.

# ⑲ transitivity — does the judge have a consistent quality scale?
matches = [("gpt", "claude", 0), ("claude", "llama", 0), ("llama", "gpt", 0)]
f = mm.judge_transitivity_check(matches)
# 🔴  Preference cycle detected: gpt > claude > llama > gpt.
#     Any leaderboard from these verdicts is order-dependent.

# ⑳ ranking stability — does "A beats B" survive resampling?
f = mm.ranking_stability_check(scores_model_a, scores_model_b)
# 🔴  Ranking 'A > B' survives only 64.2% of 1000 bootstrap resamples (n=7).
#     The ranking is noise — indistinguishable from a tie.
```

```bash
# CLI: audit pre-collected judge scores from a JSON file
mm judge --file judge_scores.json
# keys: score_pairs / pairwise_results / ratings_matrix / scores /
#       forward_results + swapped_results / matches / scores_a + scores_b
```

### Certificate 📜 — one sealed verdict per claim

`certificate()` collapses the full integrity state of a claim into a single
verifiable artifact you can embed in a paper, README, or release notes:

```python
# Structural certificate (prereg seal + chain + retraction status)
cert = mm.certificate("mm_ledger.jsonl", "my_model")

# Full certificate — fold audit findings in
findings = mm.audit("mm_ledger.jsonl", "my_model",
                    reported_metric="acc", reported_acc=0.72, n=500)
cert = mm.certificate("mm_ledger.jsonl", "my_model", findings=findings)
# {"verdict": "CERTIFIED", "prereg_seal": "6c802655ab095e8b",
#  "anchor_hash": "sha256...", "findings": {"ok": 4, "warn": 0, "fail": 0},
#  "seal": "9d1e83a4b72f0c5e", ...}
```

```bash
# CLI
mm certify my_model --pretty                  # structural only
mm certify my_model --acc 0.72 --n 500        # + audit findings folded in
mm certify my_model | gh gist create -        # publish externally
```

| Verdict | Meaning |
|---|---|
| `CERTIFIED` | Pre-registered, chain intact, not retracted, no FAIL/WARN findings |
| `CERTIFIED-WITH-WARNINGS` | Valid but has stale dependencies or WARN findings |
| `UNVERIFIED` | No pre-registration exists — nothing to certify against |
| `REJECTED` | Chain broken, seal tampered, retracted, or FAIL findings |

The certificate embeds the ledger's `anchor_hash`, so it attests to **one specific
ledger state** — and the certificate itself is sealed, so any field edit is detectable.

**Badge 🏷 — embed the verdict in your README:**

```bash
mm certify my_model --badge markdown >> README.md   # shields.io badge
mm certify my_model --badge svg > badge.svg          # offline self-contained SVG
```

```python
cert = mm.certificate("mm_ledger.jsonl", "my_model")
print(mm.badge(cert))                 # markdown (default)
print(mm.badge(cert, fmt="svg"))      # SVG with cert seal in the tooltip
# ![🪞 my_model: CERTIFIED](https://img.shields.io/badge/🪞_my__model-CERTIFIED-brightgreen)
```

Badge color follows the verdict: CERTIFIED = green · WITH-WARNINGS = yellow ·
UNVERIFIED = grey · REJECTED = red. The SVG variant embeds the certificate seal
and anchor-hash prefix in its tooltip, making the badge traceable back to the
exact sealed certificate it renders.

### Anchor ⎈

```bash
# Print tamper-evident ledger snapshot to stdout — pipe wherever you trust
mm anchor                              # compact JSON (default)
mm anchor --pretty                     # human-readable

# External archival examples (zero new dependencies)
mm anchor >> ~/Dropbox/mm_anchors.jsonl          # local backup
mm anchor | gh gist create -                     # GitHub Gist
mm anchor | aws s3 cp - s3://bucket/anchor.json  # S3
```

```python
a = mm.anchor("mm_ledger.jsonl")
# {"_type": "anchor", "ts": "...", "entry_count": 3,
#  "head_seal": "a3b9f2c1", "anchor_hash": "sha256hex...", "chain_ok": true}
```

The `anchor_hash` (full SHA-256 of the ledger file) detects even **complete file replacement** — the one attack that chain hashes alone cannot catch. Save it externally before publishing results.

### Calibrate + Witness run

```bash
# Verify the mirror itself is working correctly
mm calibrate
# ✅ [⚙ calibrate] 5/5 synthetic cases correct — mirror is calibrated.

# Witness-execute a command: calibrate first, then run and seal the record
mm run my_model -- python evaluate.py --model my_model
# ✅ [⚙ calibrate] 5/5 synthetic cases correct — mirror is calibrated.
#
# 🎬 Witnessed: my_model
#    Command:     python evaluate.py --model my_model
#    Started:     2026-06-11T12:00:00Z
#    Ended:       2026-06-11T12:00:03Z
#    Exit code:   0  (ok)
#    Output hash: a3b9f2c1e8d74f6a
#    Prev seal:   6c802655ab095e8b
#    Seal:        9d1e83a4b72f0c5e
```

```python
# Python API
findings = mm.calibrate()
mm.report("Mirror calibration", findings)

entry = mm.witness("mm_ledger.jsonl", "my_model",
                   ["python", "evaluate.py", "--model", "my_model"])
# entry["output_hash"] changes if the script output ever changes
```

### GRIM ⑩

```python
# catch arithmetically impossible accuracy values
f = mm.grim_check(reported_acc=0.33, n=10)
# 🔴  acc=0.33 is arithmetically impossible for n=10.
#     No integer k satisfies round(k/10, 2) = 0.33.
#     (candidates: k=3 → 0.3, k=4 → 0.4). Fabricated value or mis-reported n.

# GRIM runs automatically inside audit() — FAIL is appended to findings
findings = mm.audit(LEDGER, "my_model", reported_metric="acc", reported_acc=0.33, n=10)
```

---

## MCP Server — AI Agent Integration

Any MCP-compatible AI (Claude Code, Cursor, Windsurf, …) can call Measurement Mirror directly mid-conversation.

### Setup

```bash
pip install "measure-mirror[mcp]"
```

**Claude Code** — add to `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "measure-mirror": {
      "command": "python",
      "args": ["-m", "measure_mirror.mcp_server"],
      "cwd": "/path/to/measure-mirror"
    }
  }
}
```

**Other MCP clients** — run `mm-mcp` as the stdio server command.

All 28 probes + 6 utilities + the `mm_verify` umbrella are exposed as MCP tools (38 total):  
`mm_verify` (full / group-filtered) ·  
`mm_register` · `mm_verify_chain` · `mm_audit` · `mm_continuous_audit` · `mm_full_audit` ·  
`mm_baseline_fairness` · `mm_gaming_check` · `mm_leakage_check` · `mm_multiseed_check` · `mm_scope_check` ·
`mm_anchor_basis_check` · `mm_threshold_provenance_check` · `mm_content_delta_check` ·  
`mm_anchor_line_source_check` · `mm_anchor_cell_check` ·  
`mm_too_good_check` · `mm_power_check` · `mm_multiple_comparisons_check` · `mm_grim_check` ·  
`mm_falsifiability_check` · `mm_prereg_lint` · `mm_cascade_check` · `mm_negative_audit` ·  
`mm_subspace_claim_check` ·  
`mm_judge_consistency_check` · `mm_judge_bias_check` · `mm_inter_rater_agreement` ·  
`mm_judge_score_sanity` · `mm_judge_swap_check` · `mm_judge_transitivity_check` ·  
`mm_ranking_stability_check` ·  
`mm_anchor` · `mm_calibrate` · `mm_witness` · `mm_retract` · `mm_certificate` · `mm_badge`

---

## Real Catches — Dog-Fooding

We ran Measurement Mirror on our own AI research before publishing. It caught:

```
🪞 Audit: ZERO "55.6% Best" claim
   🔴 FAIL
   🔴 [④a small-sample CI] n=9, acc=0.556 → 95%CI [0.267, 0.811] ⊃ baseline(0.5)
       Statistically indistinguishable from chance.
   🔴 [① pre-registration(min_n)] reported n=9 < registered min_n=200. Undersized.
   🔴 [① pre-registration(metric swap)] reported 'best_of_9' ≠ registered 'acc_full_balanced'
       Post-hoc metric swap detected. (seal=6c802655ab095e8b)

🪞 Audit: Field candidate 5 (control sim)
   🔴 FAIL
   🔴 [② fair baseline] Field 0.996 ≈ GRU-ODE 0.998 (Δ+0.002 < 0.01). Tied — no genuine advantage.
```

Run the demos yourself:

```bash
python examples/quickstart.py    # happy path: honest researcher
python examples/demo_zero.py     # ZERO 55.6% mirage (our own project killed)
python examples/demo_field.py    # Field candidate false positives
```

---

## Project Structure

```
measure-mirror/
├── measure_mirror/
│   ├── mm.py              # verify() + probes ①~㉘ + CLI + DB lookup (stdlib only)
│   ├── mcp_server.py      # MCP server — 37 tools (pip install .[mcp])
│   ├── judge.py           # LLM-as-a-Judge runner (pip install .[judge])
│   ├── subspace.py        # ㉘ layer B executor — numpy (pip install .[subspace])
│   └── pytest_plugin.py   # assert_clean() for CI gates
├── docs/
│   ├── GUIDE.md           # full per-probe reference (English)
│   └── GUIDE_KO.md        # full per-probe reference (Korean)
├── examples/
│   ├── quickstart.py      # happy path demo
│   ├── demo_zero.py       # ZERO false-positive (dog-food)
│   ├── demo_field.py      # Field false-positive (dog-food)
│   ├── demo_judge.py      # LLM-judge failure modes (no API key needed)
│   └── mcp_example.py     # MCP tool usage reference
├── db/                    # local memory, split by who produced the record
│   ├── README.md              the measured/ vs curated/ distinction
│   ├── measured/             ← measure-mirror's own output (quantitative)
│   │   ├── baselines.json         task-level fair baselines
│   │   └── reproductions.jsonl    reproductions (verdict auto-judged)
│   └── curated/              ← human-curated (qualitative)
│       ├── self_catches.jsonl          false positives on ourselves
│       ├── false_negative_guards.jsonl false negatives re-checked
│       ├── gaming_patterns.json        gaming signatures
│       ├── contamination.jsonl         data leakage found
│       └── research_closures.jsonl     qualitative negative conclusions
└── tests/
    ├── test_mm.py         # 145 tests for core probes, CI-enforced
    ├── test_judge.py      # 17 tests for judge.py module
    └── test_sync.py       # sync gate: probe ↔ MCP ↔ tests ↔ README ↔ exports ↔ version
```

---

## Helper Functions

Exported alongside the probes. They are part of the public API — `__all__`
promises them — so they are documented here rather than left to be discovered
by reading the source.

| Function | Signature | Returns |
|---|---|---|
| `wilson_ci` | `wilson_ci(k, n, z=1.96)` | Wilson score interval `(lo, hi)` for `k` successes in `n` trials. Used by `audit()` to decide whether a reported accuracy actually clears its baseline. Returns `(0.0, 1.0)` when `n <= 0` rather than dividing by zero. |
| `lookup_baseline` | `lookup_baseline(task, db_dir=None)` | The recorded baseline for a task from `db/`, or `None` when the task is unknown. Lets `audit()` fill in a baseline you did not pass. |
| `lookup_reproduction` | `lookup_reproduction(task, db_dir=None)` | Prior **failed** reproductions recorded for this task in `db/`. A result that others already failed to reproduce should not be read as fresh evidence. |

```python
from measure_mirror import wilson_ci, lookup_baseline, lookup_reproduction

lo, hi = wilson_ci(780, 1000)          # (0.7533, 0.8046)
base = lookup_baseline("my_task")      # None if never recorded
prior = lookup_reproduction("my_task") # [] when nothing failed before
```

## Local Memory (`db/`)

`db/` is your **local memory of past audits** — not a shared/crowd database.
We tried the "CVE / shared signature" framing and **for us it didn't earn its
keep** (this is a scoped observation, not a universal law): contributing would
mean publishing *your own research that was wrong* (`self_catches`) or *a peer's
failed reproduction* (`reproductions`), which runs into the trust ⊥ reputation
dilemma. A team with the right incentives might sustain a shared DB; we didn't,
and the value below needs no sharing anyway.

The value that *does* hold needs no sharing at all: **warn future-you about a
pattern past-you already got burned by.** It works regardless of how private the
data is — it never leaves your machine.

`db/` is split by **who produced the record**, so the two kinds are never
confused (see [`db/README.md`](db/README.md) for the full structure):

### `db/measured/` — what measure-mirror produces (quantitative)

Verdicts computed by the tool itself; re-running on the same numbers reproduces
the same verdict exactly. These are wired into the audit loop and grow only via
`record_reproduction()`.

| File | How it's used |
|---|---|
| `measured/baselines.json` | `audit(task="musr")` auto-fetches the fair baseline |
| `measured/reproductions.jsonl` | `audit(task=...)` warns on a prior reproduction failure; `record_reproduction(...)` appends new ones (verdict auto-judged from Wilson CI) |

```python
# memory grows: you reproduce a claim and record the result
mm.record_reproduction("musr", claim="ZERO 55.6%", acc_claimed=0.556,
                       n_claimed=9, acc=0.385, n=1050, note="collapsed at scale")
# → verdict auto-judged FAIL, appended to db/measured/reproductions.jsonl

# later: any audit on the same task surfaces it automatically
mm.audit("ledger.jsonl", "new_claim", reported_metric="acc",
         reported_acc=0.62, n=120, task="musr")
# ⚠️ [⚙ prior-reproduction] task 'musr' has a prior reproduction failure:
#    'ZERO 55.6%' claimed 0.556 (n=9) → reproduced 0.385 (n=1050). collapsed at scale
```

### `db/curated/` — what we wrote by hand (qualitative)

Our **catch log** and research closures — human-curated, *not* the tool's
automatic output. Searchable via `catch_history()`, but **not** auto-wired into
`audit()` (matching is fuzzy text, not a clean `task` key, so auto-warning would
mean false positives).

| File | `kind` | Catch history of |
|---|---|---|
| `curated/self_catches.jsonl` | `self_catch` | false *positives* you flagged on yourself |
| `curated/false_negative_guards.jsonl` | `false_negative` | false *negatives* you re-checked |
| `curated/gaming_patterns.json` | `gaming` | gaming / mirage signatures you've seen |
| `curated/contamination.jsonl` | `contamination` | data leakage you found |
| `curated/research_closures.jsonl` | `closure` | qualitative negative conclusions (no `acc`/`n` — **not** a tool verdict) |

```python
mm.catch_history(db_dir="db")                 # all curated records
mm.catch_history(kind="gaming", db_dir="db")  # the gaming-signature catalog
mm.catch_history(source="fm_cde_pixel_feasibility")  # records from one arc
```

**Why the split is honest**: calling `db/` as a whole "measure-mirror history"
would over-claim — only `measured/` is that. Every `measured/` record was
cross-checked: feeding its `(acc, n)` back through the tool's own Wilson-CI logic
reproduces the recorded verdict with **0 mismatches**.

---

## Design Principles

- **Stdlib-only core** — pure Python stdlib, no dependencies. Say it with its scope attached: the optional `judge` module adds openai/anthropic, and the optional `subspace` module (㉘ **layer B**) adds numpy. **Stdlib-only describes the core and every layer-A auditor, not the whole package** — collapsing that into a bare "zero deps" headline is the overgeneralisation catalogued in [zero-dep-scope-overgeneralize](catalog/self-catch/zero-dep-scope-overgeneralize.md), caught on this very README.
- **Bidirectional** — catches false *positives* **and** false *negatives*. Premature negative closures are also illusions.
- **Tamper-evident pre-registration** — SHA-256 seal on first write. Only the *first* sealed registration for a `claim_id` counts in `audit()`; a later re-registration is still appended to the chain (the record is never silently dropped) but cannot override the original. Ledger tampering is detected on every audit.
- **Independent probes** — each check is a standalone function. Add new ones without touching existing code.
- **Adversarial by default** — "too good to be true" is flagged before you believe it.

---

## Contributing

New probes and baseline contributions are welcome.

1. Fork → branch → PR
2. **`db/baselines.json`**: shareable task baselines (not your private failures)
3. **New probes**: add the function to `mm.py` + tests in `tests/test_mm.py`
4. CI must stay green: `pytest tests/`

---

## License

[Apache 2.0](LICENSE)

---

**[한국어 README →](README_KO.md)**
