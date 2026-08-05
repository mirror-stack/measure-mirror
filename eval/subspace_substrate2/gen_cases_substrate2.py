#!/usr/bin/env python3
"""㉘ substrate-2 — the same planted recipes on a genuinely different substrate.

WHY THIS EXISTS
---------------
Every one of the 22 cases that judged ㉘ (seal `99a1a510`) came from **one
experiment family**: FM×CDE, 24-dimensional adapter deltas from a morphogenesis
arc. The seal says so in its own scope clause. A probe validated on one family
is a probe whose rules may be tuned to that family's shape — and the precedent
for treating that as a live risk rather than a wording problem is `seldyn`,
where seven seals on one toy substrate were promoted to a "law" and then failed
to reproduce on substrate-2 (both R1 and R2 KILLed).

Substrate-2 here is **real data from a different arc**, not synthetic:

  source     the A0-mini experiment-factory pilot (2026-07-20, sealed
             `factory-pilot-a0mini-emb-vs-prior-20260720`)
  vectors    2205 DINO crop embeddings, 384-d, saved as embs.npy by that run
  labels     1992 object pairs with a 4-way spatial relation (위/아래/왼쪽/
             오른쪽), recomputed from COCO val2017 bounding boxes
  claim      "the spatial-relation signal lives in a few directions of the
             embedding" — an active-subspace claim in a different domain

How it differs from FM×CDE, which is the whole point:

  ambient dimension    768 (pair = concat of two 384-d crops)   vs 24
  spectrum shape       flat — ~163 of 384 components for 90%    vs concentrated
  domain               vision embeddings / spatial relations    vs adapter deltas
  effect               held-out 4-class accuracy                vs a gain ratio
  seeds                resampled splits of ONE dataset          vs independent runs

⚠️ That last row is a real weakening and is declared, not hidden: the eight
"seeds" are disjoint random splits of the same 1992 pairs, so they are not
independent replications. The paired sign-flip test still has n=8 paired
observations, but they share a population.

PROVENANCE, CHECKED NOT ASSUMED
-------------------------------
`instances_val2017.json` sha256 head = `e8c7f7908f1d7278`, which is the value
the original pilot sealed in `plan.json`. Regenerating the pairs reproduces the
original run exactly: 2205 objects (= embs.npy rows) and 1992 pairs with the
relation distribution the pilot reported. The embeddings are the file that run
wrote; they are not recomputed here (that needs the images and a GPU-less DINO
pass), so "real" means the recorded vectors are real.

Usage:
    python eval/subspace_substrate2/gen_cases_substrate2.py            # build
    python eval/subspace_substrate2/gen_cases_substrate2.py --smoke    # synthetic
    python eval/subspace_substrate2/gen_cases_substrate2.py --print-sha
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from measure_mirror.subspace import build_subspace_report      # noqa: E402

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases_substrate2.jsonl"

# The substrate lives outside the package — it is experiment output, not
# library data. Same convention as eval/subspace_planted (FM_CDE_DIR).
SRC = Path(os.environ.get("FACTORY_DIR", "/data/seara/experiment_factory_poc"))
PAIRS = Path(os.environ.get("SUBSTRATE2_PAIRS",
                            "/data/seara/subspace_substrate2/pairs.npy"))

RELS = ["위", "아래", "왼쪽", "오른쪽"]
N_SEEDS = 8
ENERGY_TARGETS = (0.5, 0.7, 0.9)
SPLIT_SEED = 20260806          # split rng; declared in the report
# The pilot's own numbers, used as reproduction assertions rather than comments.
EXPECT_N_OBJ, EXPECT_N_PAIR = 2205, 1992
EXPECT_REL_COUNTS = {"위": 318, "아래": 318, "왼쪽": 665, "오른쪽": 691}
COCO_ANN_SHA_HEAD = "e8c7f7908f1d7278"      # sealed in the pilot's plan.json


# ─────────────────────────────────────────────────────────────
# substrate
# ─────────────────────────────────────────────────────────────
def load_substrate() -> tuple:
    embs = np.load(SRC / "embs.npy").astype(np.float64)
    pairs = np.load(PAIRS)
    if embs.shape[0] != EXPECT_N_OBJ:
        raise SystemExit(f"embs.npy has {embs.shape[0]} rows, pilot recorded "
                         f"{EXPECT_N_OBJ} — wrong file")
    if pairs.shape[0] != EXPECT_N_PAIR:
        raise SystemExit(f"pairs has {pairs.shape[0]} rows, pilot recorded "
                         f"{EXPECT_N_PAIR} — regenerate")
    counts = {RELS[i]: int((pairs[:, 2] == i).sum()) for i in range(4)}
    if counts != EXPECT_REL_COUNTS:
        raise SystemExit(f"relation distribution {counts} != pilot "
                         f"{EXPECT_REL_COUNTS} — regeneration did not reproduce")
    # A zero or constant feature matrix would let every arm "find" a subspace in
    # nothing. One candidate substrate (the robot episode tensors) was rejected
    # for exactly this: all 410 vision embeddings were the zero vector.
    if not np.isfinite(embs).all():
        raise SystemExit("embs.npy contains non-finite values")
    if (np.abs(embs).sum(axis=1) == 0).any():
        raise SystemExit("embs.npy contains all-zero rows")
    X = np.hstack([embs[pairs[:, 0]], embs[pairs[:, 1]]])     # (n_pair, 768)
    y = pairs[:, 2].astype(int)
    return X, y


def synthetic_substrate(rng_seed: int = 0) -> tuple:
    """Same shape, made up — for the reachability smoke only, so that the smoke
    never touches (and never spends) the real substrate."""
    rng = np.random.default_rng(rng_seed)
    n, d = EXPECT_N_PAIR, 768
    w = rng.standard_normal((d, 4))
    X = rng.standard_normal((n, d))
    y = (X @ w).argmax(axis=1)
    return X, y


# ─────────────────────────────────────────────────────────────
# effect — held-out 4-class accuracy of a ridge probe on the retained coefficients
# ─────────────────────────────────────────────────────────────
def _ridge_accuracy(ctx: dict) -> float:
    """Closed-form (deterministic, no iterative solver): ridge-regress one-hot
    labels on the retained coefficients, fit on the probe split, argmax on the
    eval split. The probe is fitted on a split that is NOT the basis split, so
    probe-estimation variance cannot masquerade as a subspace effect."""
    Xp, Xe = ctx["proj"]["probe"], ctx["proj"]["eval"]
    yp, ye = ctx["aux"]["probe"], ctx["aux"]["eval"]
    Ap = np.hstack([Xp, np.ones((Xp.shape[0], 1))])
    Y = np.eye(4)[yp]
    lam = 1e-3 * float(np.trace(Ap.T @ Ap)) / Ap.shape[1]
    W = np.linalg.solve(Ap.T @ Ap + lam * np.eye(Ap.shape[1]), Ap.T @ Y)
    pred = (np.hstack([Xe, np.ones((Xe.shape[0], 1))]) @ W).argmax(axis=1)
    return float((pred == ye).mean())


_EFFECT_SOURCE = __import__("inspect").getsource(_ridge_accuracy)

ARMS = {
    "EMB":     {"role": "target",      "basis": "pca"},
    "RANDOM":  {"role": "null",        "basis": "random"},
    "SHUFFLE": {"role": "dof_control", "basis": "shuffled"},
}


def _splits(n: int):
    """ONE global eval holdout; the basis/probe split is resampled inside the
    remaining pool, per seed.

    The obvious layout — permute all n rows independently per seed — was tried
    first and the pre-seal smoke killed it: `basis_fit_ids` and
    `effect_eval_ids` are unions over seeds, so a row that is basis for seed 0
    and eval for seed 3 puts a genuine collision in the union.
    `estimation-eval-overlap` FAILed the clean report and it was RIGHT. Fixing
    the harness is the answer; loosening the finding would have been the
    instrument-tuning this arc exists to refuse.
    """
    rng = np.random.default_rng(SPLIT_SEED)
    idx = rng.permutation(n)
    n_eval = n // 3
    eval_idx, pool = idx[:n_eval], idx[n_eval:]
    half = len(pool) // 2
    for s in range(N_SEEDS):
        p = np.random.default_rng(SPLIT_SEED + 1000 + s).permutation(len(pool))
        yield pool[p[:half]], pool[p[half:]], eval_idx


def build_clean_report(X, y, *, source_label: str) -> dict:
    """Eight resampled estimation splits against ONE fixed eval holdout."""
    data, aux = {}, {}
    for s, (b, p, e) in enumerate(_splits(X.shape[0])):
        data[s] = {"basis": X[b], "probe": X[p], "eval": X[e]}
        aux[s] = {"probe": y[p], "eval": y[e]}

    anchor = {
        # Honest label: this is a re-analysis of a recorded substrate, not a
        # re-execution of the pilot. 'frozen' would claim more than we did.
        "code_path": "reimplemented",
        "reference": "factory-pilot-a0mini-emb-vs-prior-20260720 — embs.npy is "
                     "that run's output; pairs recomputed from COCO val2017 "
                     f"(instances_val2017.json sha256 head {COCO_ANN_SHA_HEAD}, "
                     "the value the pilot sealed) and reproduced its object, "
                     "pair and relation counts exactly",
        "tol": {"pair_reproduction": 0.0},
        "n_seeds": N_SEEDS,
        "guard_seeds": 0,
    }
    rep = build_subspace_report(
        data, arms=ARMS, effect_fn=_ridge_accuracy,
        effect_fn_source=_EFFECT_SOURCE, energy_targets=ENERGY_TARGETS,
        anchor=anchor, aux_by_seed=aux, rng_seed=SPLIT_SEED,
        source=source_label,
        extra={
            "substrate": "COCO val2017 crops → DINO 384-d embeddings, pairs "
                         "concatenated to 768-d; 4-way spatial relation",
            "effect_definition": "held-out 4-class accuracy of a ridge probe on "
                                 "the retained coefficients",
            "chance_effect": float(max(np.bincount(y, minlength=4)) / len(y)),
            "seed_independence": "SEEDS ARE RESAMPLED SPLITS OF ONE DATASET, not "
                                 "independent replications — the paired test has "
                                 "n=8 paired observations that share a population",
        })
    return rep


def build_k_grid_report(X, y, *, source_label: str) -> dict:
    """A genuine k grid: every arm is held at the SAME k at each grid point.

    Not an edit of the energy report — a second real run of the executor with k
    fixed across arms, which is what makes relabelling it 'energy' a real lie
    rather than a fabricated one.
    """
    from measure_mirror.subspace import fit_basis, cumulative_energy

    cells, per_arm = [], {a: {} for a in ARMS}
    k_points = [8, 32, 128]
    for s, (b, p, e) in enumerate(_splits(X.shape[0])):
        arrays = {"basis": X[b], "probe": X[p], "eval": X[e]}
        for arm, spec in ARMS.items():
            sub = int(hashlib.sha256(f"kgrid|{arm}|{s}".encode()).hexdigest()[:8], 16)
            basis = fit_basis(arrays["basis"], kind=spec["basis"], rng_seed=sub)
            cum = cumulative_energy(basis, arrays["eval"])
            for k in k_points:
                comps = basis.top(k)
                proj = {nm: arr @ comps.T for nm, arr in arrays.items()}
                eff = _ridge_accuracy({"proj": proj,
                                       "aux": {"probe": y[p], "eval": y[e]}})
                cells.append({"arm": arm, "role": spec["role"], "seed": s,
                              "grid_point": float(k), "k": int(k),
                              "energy_kept": float(cum[k - 1]),
                              "energy_target": None, "effect": eff,
                              "n": int(len(e))})
                per_arm[arm].setdefault(s, []).append(eff)
    return {
        "source": source_label,
        "layer": "B",
        "anchor": None,        # the caller copies the clean report's anchor in
        "grid": {"kind": "energy", "note": "MISDECLARED — this is the k grid"},
        "ambient_dim": X.shape[1],
        "cells": cells,
        "arms": {a: {"role": ARMS[a]["role"],
                     "effect_by_seed": [float(np.mean(per_arm[a][s]))
                                        for s in sorted(per_arm[a])]}
                 for a in ARMS},
        "k_points": k_points,
    }


# ─────────────────────────────────────────────────────────────
# the planted set — recipes that are substrate-general
# ─────────────────────────────────────────────────────────────
def _case(cid, kind, layer, provenance, report, expect, note=""):
    return {"id": cid, "kind": kind, "layer": layer, "provenance": provenance,
            "expect": expect, "note": note, "report": report}


def build_cases(clean: dict, kgrid: dict) -> list[dict]:
    out = []

    # ── planted POSITIVES — failing one is a false positive ─────────────
    out.append(_case(
        "s2_clean", "positive", "real",
        "Layer B run verbatim on substrate-2: 3 arms × 8 splits × 3 energy "
        "targets, nothing removed or relabelled",
        clean,
        {"no-anchor": ["OK"], "dof-uncontrolled": ["OK"],
         "energy-not-matched": ["OK"], "estimation-eval-overlap": ["OK"]},
        "★ the load-bearing case. null-ladder is deliberately NOT asserted: "
        "whether this embedding subspace beats a random one is a property of "
        "the substrate, not of the auditor"))

    self_null = copy.deepcopy(clean)
    self_null["arms"] = {
        "RANDOM_as_target": {"role": "target",
                             "effect_by_seed": clean["arms"]["RANDOM"]["effect_by_seed"]},
        "RANDOM": clean["arms"]["RANDOM"],
    }
    out.append(_case(
        "s2_self_null", "positive", "real",
        "The RANDOM arm's real measured per-split effects copied into both the "
        "target and the null slot — a guaranteed null built without inventing "
        "a number",
        self_null,
        {"null-ladder": ["FAIL", "WARN"]},
        "an arm cannot beat itself; confirming that it does is the false positive"))

    # ── planted NEGATIVES — passing one is a false negative ─────────────
    stripped = copy.deepcopy(clean)
    stripped.pop("anchor")
    out.append(_case(
        "s2_anchor_stripped", "negative", "real",
        "Substrate-2 clean report with the anchor block deleted. Deletion only",
        stripped,
        {"no-anchor": ["FAIL"], "null-ladder": ["WARN", "FAIL"]},
        "★ the ladder must not report OK underneath a failed anchor"))

    dof_gone = copy.deepcopy(clean)
    dof_gone["cells"] = [c for c in dof_gone["cells"] if c["arm"] != "SHUFFLE"]
    dof_gone["arms"].pop("SHUFFLE")
    out.append(_case(
        "s2_dof_missing", "negative", "real",
        "Substrate-2 clean report with the SHUFFLE (dof_control) arm removed",
        dof_gone,
        {"dof-uncontrolled": ["FAIL"]},
        "complete in every other respect ⇒ omission, not scope ⇒ FAIL not WARN"))

    relabeled = copy.deepcopy(clean)
    for c in relabeled["cells"]:
        if c["arm"] == "EMB":
            c["role"] = "dof_control"
        elif c["arm"] == "SHUFFLE":
            c["role"] = "target"
    relabeled["arms"]["EMB"]["role"] = "dof_control"
    relabeled["arms"]["SHUFFLE"]["role"] = "target"
    out.append(_case(
        "s2_relabeled_dof", "negative", "real",
        "Roles of EMB and SHUFFLE swapped. Label move only — energies still "
        "match, a dof arm still exists, the anchor is intact",
        relabeled,
        {"__must_not__": {"null-ladder": ["OK"]}},
        "★ undecidable from the table alone. The requirement is not 'catch it' "
        "but 'do not confirm it'"))

    leak = copy.deepcopy(clean)
    leak["effect_eval_ids"] = leak["basis_fit_ids"]
    out.append(_case(
        "s2_estimation_eval_leak", "negative", "half",
        "The split ids are real and genuinely disjoint; the holdout field is "
        "overwritten to force the collision. The run itself never leaked",
        leak,
        {"estimation-eval-overlap": ["FAIL"]},
        "half: the ids are real, the collision is manufactured"))

    out.append(_case(
        "s2_energy_confound", "negative", "real",
        "A SECOND REAL EXECUTOR RUN gridded on k (every arm held at k ∈ "
        "{8,32,128}), resubmitted with grid.kind='energy'. Every number was "
        "measured; the declaration is the lie",
        kgrid,
        {"energy-not-matched": ["FAIL"]},
        "★ real on both sides — unlike the FM×CDE version, the k grid here was "
        "actually run rather than lifted from a secondary grid"))

    nogrid = copy.deepcopy(clean)
    nogrid.pop("grid")
    nogrid["cells"] = []
    out.append(_case(
        "s2_nogrid", "positive", "real",
        "Substrate-2 clean report with the grid and the cells deleted, arms and "
        "their per-split effects kept — the honest shape of a report that never "
        "ran a grid. Deletion only",
        nogrid,
        {"energy-not-matched": ["N/A"], "dof-uncontrolled": ["OK"]},
        "★ no grid ⇒ energy matching is NOT APPLICABLE, not failed. Reading the "
        "two as the same is what misfires the false-positive kill"))

    top = max(c["grid_point"] for c in clean["cells"])
    null_top = [c["effect"] for c in clean["cells"]
                if c["role"] == "null" and c["grid_point"] == top]
    saturated = copy.deepcopy(clean)
    saturated["bar"] = float(min(null_top))
    out.append(_case(
        "s2_saturated", "negative", "real",
        f"Substrate-2 clean report with a survival bar declared at "
        f"{min(null_top):.6g} — the null arm's own worst measured effect at the "
        f"top grid point {top}. Every number is measured; declaring a bar the "
        f"null already clears is the defect",
        saturated,
        {"saturation": ["FAIL"]},
        "a ladder whose null already clears the bar cannot separate signal from "
        "null at that grid point"))

    resolves = copy.deepcopy(clean)
    resolves["bar"] = float(max(null_top)) + 1e-9
    out.append(_case(
        "s2_bar_resolves", "positive", "real",
        f"The same report with the survival bar declared a hair above the null "
        f"arm's BEST measured effect at the top grid point "
        f"({max(null_top):.6g}) — the null does not clear it, so the ladder "
        f"still resolves",
        resolves,
        {"saturation": ["OK"]},
        "★ paired with s2_saturated on purpose. Both bars are derived from the "
        "same real measurement, one at the null's floor and one above its "
        "ceiling, so the finding is exercised in BOTH directions rather than "
        "passing constantly in one"))

    underdet = copy.deepcopy(clean)
    underdet["n_basis_fit"] = 20
    out.append(_case(
        "s2_underdetermined", "negative", "B",
        "n_basis_fit overwritten to 20 against ambient_dim 768. Layer A can "
        "only lint this; the executor judgment is layer B's overfit_smallsample",
        underdet,
        {"underdetermined-basis": ["WARN"]},
        "layer B, exactly as the FM×CDE set labelled the identical case: the "
        "lint has only a WARN state, so gating a kill on it would make its "
        "verdict constant by construction. Reported, not scored"))

    return out


# ─────────────────────────────────────────────────────────────
def protocol_sha() -> dict:
    files = {
        "measure_mirror/subspace.py": REPO / "measure_mirror/subspace.py",
        "measure_mirror/mm.py": REPO / "measure_mirror/mm.py",
        "eval/subspace_substrate2/gen_cases_substrate2.py": Path(__file__),
        "eval/subspace_planted/score.py": REPO / "eval/subspace_planted/score.py",
    }
    per = {k: hashlib.sha256(v.read_bytes()).hexdigest() for k, v in files.items()}
    combined = hashlib.sha256(
        "".join(f"{k}:{per[k]}\n" for k in sorted(per)).encode()).hexdigest()
    return {"per_file": per, "combined": combined}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true",
                    help="build from a synthetic substrate of the same shape — "
                         "the reachability check, so the real substrate is not "
                         "touched before the seal")
    ap.add_argument("--print-sha", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.print_sha:
        sha = protocol_sha()
        for k in sorted(sha["per_file"]):
            print(f"{sha['per_file'][k]}  {k}")
        print(f"{sha['combined']}  COMBINED")
        return 0

    if args.smoke:
        X, y = synthetic_substrate()
        label = "SMOKE synthetic 768-d (NOT substrate-2)"
        out = Path(args.out or (HERE / "cases_smoke.jsonl"))
    else:
        X, y = load_substrate()
        label = "substrate-2: A0-mini factory pilot embeddings (COCO/DINO)"
        out = Path(args.out or CASES)

    print(f"  substrate: X={X.shape} y={y.shape} classes={np.bincount(y)}")
    clean = build_clean_report(X, y, source_label=label)
    kgrid = build_k_grid_report(X, y, source_label=label + " [k grid]")
    kgrid["anchor"] = copy.deepcopy(clean["anchor"])
    kgrid["basis_fit_ids"] = clean["basis_fit_ids"]
    kgrid["effect_eval_ids"] = clean["effect_eval_ids"]

    cases = build_cases(clean, kgrid)
    out.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases))
    n_pos = sum(c["kind"] == "positive" for c in cases)
    print(f"  wrote {out} — {len(cases)} cases "
          f"({n_pos} positive · {len(cases) - n_pos} negative)")
    print(f"  protocol COMBINED sha256 = {protocol_sha()['combined']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
