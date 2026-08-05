# ㉘ substrate-2 — 🔴 **KILL_auditor**

claim `subspace_claim_check_substrate2_generalization_20260806_v4` · seal `5c78e503` ·
result am `2ab6eab7` · `stack_verify_all` **ALL OK (10/10)**

| | value | bar |
|---|---|---|
| **CASE_ACCURACY** | **0.80** (8 / 10 layer-A cases) | 1.0 · chance 0.60 |
| FP | **1** | 0 |
| FN | **1** | 0 |
| constant findings | 1 (`estimation-eval-overlap`) | 0 |

The seal declared three possible outcomes before the run. This is outcome (2),
`KILL_auditor`, and the pre-commitment says there is no repair round: the
finding is reported, and ㉘ ships with its scope clause unchanged.

## What substrate-2 is

The A0-mini experiment-factory pilot (2026-07-20, sealed
`factory-pilot-a0mini-emb-vs-prior-20260720`) — **real data from another arc**,
not a synthetic stand-in:

* 2205 DINO crop embeddings (384-d) written by that run
* 1992 COCO val2017 object pairs with a 4-way spatial relation, recomputed from
  the annotations; `instances_val2017.json` sha256 head `e8c7f7908f1d7278` is
  bit-identical to the value the pilot sealed, and regeneration reproduced the
  object, pair and relation counts exactly
* ambient dimension **768**, spectrum **flat** (~163 of 384 components for 90%
  energy), effect = held-out 4-class accuracy

versus FM×CDE's 24-dimensional adapter deltas with a concentrated spectrum and
a gain-ratio effect. Different domain, different dimension, different geometry,
different effect — which is the point.

## The two failures

### FN — `s2_relabeled_dof`: the auditor confirmed a swapped-role claim

Measured arm means over 8 splits (chance = 0.3469):

| arm | role | mean effect |
|---|---|---|
| EMB | target | 0.4834 |
| SHUFFLE | dof_control | 0.4437 |
| RANDOM | null | 0.4240 |

The recipe swaps the roles of `EMB` and `SHUFFLE`, so the declared target
becomes the degrees-of-freedom control. On this substrate **SHUFFLE beats
RANDOM on all 8 splits**, so the paired sign-flip returns OK — the auditor
confirms a claim whose "treatment" is the control.

**This is the load-bearing result.** The auditor behaves *identically* to how it
behaved on FM×CDE; only the substrate differs. So the `relabeled_dof` case
passed in the original 22/22 because the shuffled arm happened not to beat the
null there — **not because the probe has any mechanism for it.** That pass was
substrate luck, and it looked like a guard. ㉘ has no guard against a
swapped-role claim, and one substrate could not show that.

A second fact worth recording on its own: **a column-shuffled basis is not a
null on real anisotropic embeddings.** Shuffling destroys cross-dimension
covariance but preserves per-dimension marginals, and on this substrate those
dimensions carry signal.

### FP — `s2_clean`: one byte-identical row spans estimation and evaluation

`|fit ids| = 1317`, `|eval ids| = 664`, **intersection = 1**. The splits are
index-disjoint by construction, but layer B's ids are content-addressed, and the
substrate carries 4 duplicate pair-feature rows (from 2 duplicate rows in
`embs.npy`). One of them lands on both sides.

Unsealed diagnosis, labelled as such and **not used to rescore**: the auditor is
reporting a *true* fact, and the case expectation of `OK` was the thing that was
wrong — index-disjointness does not imply content-disjointness. That vindicates
the content-addressed id design, and it still falsifies the claim exactly as the
claim was written. Renegotiating the expectation after seeing the result is the
move the pre-commitment exists to forbid.

Because the clean report already FAILs this finding, the planted leak case's
catch is vacuous here — hence the constant.

## What this does and does not falsify

* It does **not** falsify seal `99a1a510`, the FM×CDE holdout judgment. That
  claim was scoped to one experiment family and said so in its own text.
* It falsifies **generalization to a second substrate**, which was never
  asserted before this run. ㉘'s scope clause is now backed by evidence rather
  than by caution.

## Scope of this run

n = 1 additional substrate. The 8 seeds are resampled estimation splits against
one fixed eval holdout — **not** independent replications. The `vacuous` finding
is not exercised at all, because substrate-2 has no `matched_null` arm. Layer
A's standing hole is untouched: a consistent forgery still passes.

## Reproduce

```bash
python eval/subspace_substrate2/gen_cases_substrate2.py --smoke   # synthetic
python eval/subspace_substrate2/gen_cases_substrate2.py           # substrate-2
python eval/subspace_planted/score.py \
    --cases eval/subspace_substrate2/cases_substrate2.jsonl
```

Protocol frozen at `COMBINED = 2dbbf624949980d1fa5760094607211be7ca676f47e5e55edffde2ce7a31b29b`,
verified bit-identical immediately before the run. Substrate frozen at
`embs.npy = b8ff91be…`, `pairs.npy = 04a27b87…`.

## Ledger note

Three seals — `8ebe2b57`, `70c99337`, `2157327a` — carry the same protocol and
are **dead**. Each was written through a malformed call in which the
`pass_threshold` argument leaked into the metric string, so the bar fell back to
its default 0.6, equal to the declared chance, and ㉗ `prereg-lint` FAILed and
blocked the compute gate. Nothing was ever run under any of them. They are left
standing rather than deleted; that is what an append-only ledger is for, and the
lint catching the same operator error three running is the honest record.
