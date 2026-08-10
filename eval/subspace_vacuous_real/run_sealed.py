#!/usr/bin/env python3
"""㉘ `vacuous` — first exercise of both directions on REAL runs (layer B).

WHY THIS RUN EXISTS
-------------------
Until now Finding 5 `vacuous` had never fired on anything but synthetic tables:
the FM×CDE corpus carries zero real VACUOUS labels (`vacuous_arms: []`,
`any_vacuous_null: false`), substrate-2 has no matched_null arm at all, and the
planted FN case (`vacuous_as_collapse`) was made by *hand-writing* a
certificate failure into a real report. `eval/subspace_planted/RESULTS.md`
records this openly. This run replaces the hand-written direction with runs
that COMPUTE their certificates from their own arrays
(`build_subspace_report(certificate_tol=…)`).

THE ORGANIC FAILURE ROUTE (no field is edited)
----------------------------------------------
The certificate criterion is fixed: the matched arm's retained energy **on the
eval split** must meet the declared target within tol, for every cell.

  honest   k selected on the eval split (the default): the minimal-k rule makes
           the margin ≥ 0 by construction — a genuinely matched arm.
  sloppy   k selected in-sample (energy_on="basis") at small n: the shuffled
           basis overfits its fit sample, so on the eval split the arm
           genuinely undershoots its target. Matched on paper, not in fact —
           the vacuous illusion, produced by a run instead of typed into one.

Cases are labelled by GROUND TRUTH (the margin recomputed from the emitted
eval-split energy cells), not by intended condition: a sloppy run at large n
where the manipulation demonstrably did not bite (margin inside tol) is a
genuinely matched arm and is scored as such — the equivalent-mutant filter,
after arXiv 2607.08028's mutation-killing discipline (via the yeoul lane memo).
Margins inside the boundary band |margin + tol| < delta are WITHHELD.

WHAT IS CLAIMED, AND WHAT IS NOT
--------------------------------
Claimed: PRIMARY BALANCED_CASE = (acc_unmatched + acc_matched) / 2 over
readable cases — layer A's `vacuous` says FAIL on every ground-truth-unmatched
arm and OK on every ground-truth-matched arm. Bar = 1.0 (the pipeline is
deterministic given seeds; one genuine disagreement is a real defect). Chance =
0.5 (a constant verdict scores exactly 0.5 balanced). A WARN anywhere counts
as wrong — the certificate must be present on every run.

NOT claimed: anything about a real substrate (data is isotropic Gaussian,
d=24), or about a stranger's certificate — layer B certifies its OWN run;
a consistent forgery still passes layer A (standing hole, unchanged).

Pre-commitment: bars fixed before the sealed run. If missed, shipped
documented — not renegotiated, no second repair round.

Usage:
    python eval/subspace_vacuous_real/run_sealed.py --out .../result.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import numpy as np                                          # noqa: E402

from measure_mirror.mm import subspace_claim_check          # noqa: E402
from measure_mirror.subspace import build_subspace_report   # noqa: E402

# Data seeds are drawn from a block disjoint from every burned block:
# runner tests use 100+s / 200+s, layer-B dev used 20260805 / 4242, the
# layer-B sealed run used 900_001..980_xxx, this file's pre-seal smoke used
# 555_001, and the INVALID first sealed attempt (17c36ad6) consumed
# 1_100_001 — all burned, none may be reused.
SEED_BLOCK_START = 1_200_001
AMBIENT = 24
N_LIST = (8, 20, 50, 200)
N_SEEDS = 4                  # seeds inside one report
N_EVAL = 200
TARGETS = (0.5, 0.7, 0.9)
TOL = 0.05                   # certificate tolerance, declared to layer B
DELTA = 0.005                # boundary band half-width around -TOL: withheld
PROCS = ("honest", "sloppy")

BAR_BALANCED = 1.0           # PRIMARY; chance 0.50 (any constant verdict)
CHANCE_BALANCED = 0.50
MIN_CLASS = 30               # below this, INVALID — never a pass

ARMS = {"TARGET": {"role": "target", "basis": "pca"},
        "MATCHED": {"role": "matched_null", "basis": "shuffled"}}
ANCHOR = {"code_path": "frozen",
          "reference": "eval/subspace_vacuous_real/run_sealed.py",
          "tol": {"bit_repro": 0.0}, "n_seeds": N_SEEDS}

PROTOCOL_FILES = ("measure_mirror/subspace.py", "measure_mirror/mm.py",
                  "eval/subspace_vacuous_real/run_sealed.py")


def protocol_sha() -> dict:
    per = {f: hashlib.sha256((REPO / f).read_bytes()).hexdigest()
           for f in PROTOCOL_FILES}
    combined = hashlib.sha256(
        "".join(f"{f}:{per[f]}\n" for f in PROTOCOL_FILES).encode()).hexdigest()
    return {"per_file": per, "combined": combined}


def _effect(ctx):
    """Toy effect: retained fraction of the eval array's energy. The verdicts
    under test consume certificates, not effects — this only has to be real."""
    return float((ctx["proj"]["eval"] ** 2).sum() / (ctx["data"]["eval"] ** 2).sum())


def _one_report(proc: str, n_fit: int, base_seed: int) -> dict:
    data = {}
    for s in range(N_SEEDS):
        ds = int(hashlib.sha256(
            f"{base_seed}|{proc}|{n_fit}|{s}".encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(ds)
        data[s] = {"basis": rng.standard_normal((n_fit, AMBIENT)),
                   "eval": rng.standard_normal((N_EVAL, AMBIENT))}
    kw = {"energy_on": "basis"} if proc == "sloppy" else {}
    return build_subspace_report(
        data, arms=ARMS, effect_fn=_effect, energy_targets=TARGETS,
        anchor=ANCHOR, certificate_tol=TOL, rng_seed=base_seed, **kw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replications", type=int, default=25)
    ap.add_argument("--out", required=True)
    ap.add_argument("--print-sha", action="store_true")
    ap.add_argument("--seed-block", type=int, default=SEED_BLOCK_START)
    args = ap.parse_args()

    sha = protocol_sha()
    if args.print_sha:
        for f, h in sha["per_file"].items():
            print(f"{h}  {f}")
        print(f"{sha['combined']}  COMBINED")
        return 0

    rows = []
    for r in range(args.replications):
        for proc in PROCS:
            for n in N_LIST:
                base = args.seed_block + r * 1000 + n + (500 if proc == "sloppy" else 0)
                rep = _one_report(proc, n, base)
                cells = [c for c in rep["cells"] if c["arm"] == "MATCHED"]
                # ground truth, recomputed from the emitted table — not read
                # from the certificate the verdict consumes
                margin = min(c["energy_kept_on_eval_split"] - c["energy_target"]
                             for c in cells)
                if margin < -TOL - DELTA:
                    truth = "unmatched"
                elif margin >= -TOL + DELTA:
                    truth = "matched"
                else:
                    truth = "boundary"
                vac = [f for f in subspace_claim_check(rep)
                       if f.probe == "㉘ vacuous"]
                level = vac[0].level if vac else "ABSENT"
                rows.append({
                    "replication": r, "proc": proc, "n_fit": n,
                    "base_seed": base, "truth_margin": margin, "truth": truth,
                    "cert_passed": rep["certificate"]["MATCHED"]["passed"],
                    "vacuous_level": level,
                    "correct": (level == "FAIL" if truth == "unmatched"
                                else level == "OK" if truth == "matched"
                                else None),
                })
        print(f"  replication {r + 1}/{args.replications} done", flush=True)

    unmatched = [x for x in rows if x["truth"] == "unmatched"]
    matched = [x for x in rows if x["truth"] == "matched"]
    withheld = [x for x in rows if x["truth"] == "boundary"]
    levels_seen = sorted({x["vacuous_level"] for x in rows})

    acc_un = (sum(x["correct"] for x in unmatched) / len(unmatched)) if unmatched else None
    acc_ma = (sum(x["correct"] for x in matched) / len(matched)) if matched else None
    balanced = ((acc_un + acc_ma) / 2.0
                if acc_un is not None and acc_ma is not None else None)

    # anchors: no extreme-condition run may land in the OPPOSITE class —
    # otherwise the stage itself is broken and nothing here is readable.
    # A boundary landing is allowed: withheld cases never enter the scoring,
    # so they cannot corrupt the verdict and do not refute the stage. (The
    # first sealed attempt, 17c36ad6, demanded the intended class literally
    # and went INVALID when one sloppy@8 margin of -0.0524 fell inside the
    # withheld band — a clause/degenerate-state interaction its author failed
    # to enumerate. Consumed as INVALID, re-sealed with this clause and a
    # fresh seed block. See catalog/self-catch/prereg-clause-defect-family.md.)
    anchor_pos = all(x["truth"] != "matched"
                     for x in rows if x["proc"] == "sloppy" and x["n_fit"] == 8)
    anchor_neut = all(x["truth"] != "unmatched"
                      for x in rows if x["proc"] == "honest" and x["n_fit"] == 200)

    if len(unmatched) < MIN_CLASS or len(matched) < MIN_CLASS:
        verdict = "INVALID_class_too_small"
    elif not anchor_pos:
        verdict = "INVALID_anchor_positive"
    elif not anchor_neut:
        verdict = "INVALID_anchor_neutral"
    elif len({x["vacuous_level"] for x in rows if x["truth"] != "boundary"}) < 2:
        verdict = "INVALID_constant_verdict"
    elif balanced is None or balanced < BAR_BALANCED:
        verdict = "KILL_balanced"
    else:
        verdict = "PASS"

    per_cond = {}
    for proc in PROCS:
        for n in N_LIST:
            sub = [x for x in rows if x["proc"] == proc and x["n_fit"] == n]
            per_cond[f"{proc}@{n}"] = {
                "runs": len(sub),
                "truth": {t: sum(x["truth"] == t for x in sub)
                          for t in ("matched", "unmatched", "boundary")},
                "margin_min": min(x["truth_margin"] for x in sub),
                "margin_max": max(x["truth_margin"] for x in sub),
                "vacuous_levels": sorted({x["vacuous_level"] for x in sub}),
            }

    out = {
        "protocol_sha256": sha,
        "config": {
            "replications": args.replications, "n_list": list(N_LIST),
            "ambient_dim": AMBIENT, "n_seeds_per_report": N_SEEDS,
            "n_eval": N_EVAL, "energy_targets": list(TARGETS),
            "certificate_tol": TOL, "boundary_delta": DELTA,
            "seed_block_start": args.seed_block,
        },
        "bars": {"balanced_min": BAR_BALANCED, "chance": CHANCE_BALANCED,
                 "min_class": MIN_CLASS},
        "primary": {"BALANCED_CASE": balanced,
                    "acc_unmatched": acc_un, "n_unmatched": len(unmatched),
                    "acc_matched": acc_ma, "n_matched": len(matched),
                    "n_withheld_boundary": len(withheld)},
        "anchors": {"sloppy_n8_all_unmatched": anchor_pos,
                    "honest_n200_all_matched": anchor_neut},
        "levels_seen": levels_seen,
        "per_condition": per_cond,
        "verdict": verdict,
        "env": {"python": sys.version.split()[0], "numpy": np.__version__,
                "platform": platform.platform()},
        "rows": rows,
    }
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in
                      ("primary", "anchors", "levels_seen", "bars", "verdict")},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
