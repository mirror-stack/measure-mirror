#!/usr/bin/env python3
"""㉘ layer B — sealed false-positive-rate run for `overfit_smallsample`.

WHY A SEALED RUN AT ALL
-----------------------
`overfit_smallsample` was *built* by looking at its own output: the first
version ran its positive control only at the largest n, and the development
runs are what exposed that. Those seeds are therefore spent — the same
"development signal consumed the test set" situation the layer-A arc hit
(sealed 98e993b2 → 3e6bd450 → 99a1a510, judged on the v01/v05 holdout). This
script replays the frozen protocol on rng seeds development never touched.

WHAT IS CLAIMED, AND WHAT IS NOT
--------------------------------
NOT claimed: "the pipeline never invents an effect". That bar is wrong. The
null ladder is a calibrated test at α, so an *honest* instrument produces a
spurious win at roughly the nominal rate; demanding zero would fail a correct
instrument and would be met perfectly by an inert one.

Claimed instead:

  PRIMARY  BALANCED = (POWER + (1 - NULL_FPR)) / 2 — balanced accuracy over the
           two conditions. Bar ≥ 0.90, chance 0.50. It is deliberately NOT
           NULL_FPR on its own: an *inert* instrument that never reports a win
           scores a perfect NULL_FPR = 0, and an instrument that always reports
           one scores perfect power. Both sit at exactly 0.50 here, so the
           vacuous pass is unreachable by construction rather than by a
           side-condition someone can forget to check.

  Components, each a HARD kill on its own so the two cannot be traded off:
    NULL_FPR — fraction of READABLE (n, seed) null runs (signal 0, disjoint
               samples) where the target arm clears the null ladder.
               Bar ≤ 0.10 = 2× the nominal α = 0.05. KILL above.
    POWER    — fraction of (n, seed) positive-control runs where the target arm
               clears the ladder. Bar ≥ 0.90. A null run whose own (n, seed)
               control failed is WITHHELD, never counted as a pass.

Pre-commitment: the bars above are fixed before the run. If any is missed, that
is reported as a defect of the layer-B pipeline and shipped documented — the
bar is not renegotiated afterwards, and there is no second repair round.

Usage:
    python eval/subspace_layerb/run_sealed.py --out /data/.../result.json
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

from measure_mirror.subspace import _one_condition          # noqa: E402

# Seeds development never used. The module default (20260805) and the test
# seed (4242) are both burned; these are drawn from a disjoint block.
SEED_BLOCK_START = 900_001
N_LIST = (20, 50, 200)
AMBIENT = 24
N_SEEDS = 8                 # seeds INSIDE one condition (the paired ladder's n)
N_PROBE = N_EVAL = 2000
TARGETS = (0.5, 0.7, 0.9)
ALPHA = 0.05
POSITIVE_SIGNAL = 1.5

BAR_BALANCED = 0.90         # PRIMARY; chance = 0.50 (inert and always-on both)
BAR_NULL_FPR = 0.10         # KILL above
BAR_POWER = 0.90            # below → INVALID (withheld), not a pass
CHANCE_BALANCED = 0.50
NOMINAL_ALPHA = 0.05

PROTOCOL_FILES = ("measure_mirror/subspace.py", "measure_mirror/mm.py",
                  "eval/subspace_layerb/run_sealed.py")


def protocol_sha() -> dict:
    per = {f: hashlib.sha256((REPO / f).read_bytes()).hexdigest()
           for f in PROTOCOL_FILES}
    combined = hashlib.sha256(
        "".join(f"{f}:{per[f]}\n" for f in PROTOCOL_FILES).encode()).hexdigest()
    return {"per_file": per, "combined": combined}


def main() -> int:
    ap = argparse.ArgumentParser()
    # 80 × 3 n-values = 240 runs. Sized by ⑧ power_check BEFORE sealing: at
    # n=90 the design could not separate the bar (0.10) from nominal α (0.05)
    # at 80% power — it wanted n ≥ 216.
    ap.add_argument("--replications", type=int, default=80,
                    help="independent outer rng seeds")
    ap.add_argument("--out", required=True)
    ap.add_argument("--print-sha", action="store_true")
    # Smoke runs must not spend the sealed block's seeds. Pre-seal checks pass
    # a different block so the sealed draws stay genuinely unseen.
    ap.add_argument("--seed-block", type=int, default=SEED_BLOCK_START)
    args = ap.parse_args()

    sha = protocol_sha()
    if args.print_sha:
        for f, h in sha["per_file"].items():
            print(f"{h}  {f}")
        print(f"{sha['combined']}  COMBINED")
        return 0

    common = dict(d=AMBIENT, n_seeds=N_SEEDS, n_probe=N_PROBE, n_eval=N_EVAL,
                  energy_targets=TARGETS, alpha=ALPHA)
    rows = []
    for r in range(args.replications):
        base = args.seed_block + r * 1000
        for n in N_LIST:
            null = _one_condition(n_basis=n, signal=0.0, overlap=False,
                                  rng_seed=base + n, **common)
            pos = _one_condition(n_basis=n, signal=POSITIVE_SIGNAL,
                                 overlap=False, rng_seed=base + n + 500, **common)
            rows.append({
                "replication": r, "rng_seed_null": base + n,
                "rng_seed_pos": base + n + 500, "n_basis": n,
                "null_win": bool(null["target_beats_null"]),
                "pos_win": bool(pos["target_beats_null"]),
                "null_ladder": null["ladder_level"],
                "pos_ladder": pos["ladder_level"],
                "null_effects": null["arm_effects"],
                "pos_effects": pos["arm_effects"],
            })
        print(f"  replication {r + 1}/{args.replications} done", flush=True)

    power = sum(x["pos_win"] for x in rows) / len(rows)
    readable = [x for x in rows if x["pos_win"]]
    withheld = [x for x in rows if not x["pos_win"]]
    fpr = (sum(x["null_win"] for x in readable) / len(readable)) if readable else None

    balanced = (power + (1.0 - fpr)) / 2.0 if fpr is not None else None
    if fpr is None:
        verdict = "INVALID_no_readable_run"
    elif power < BAR_POWER:
        verdict = "KILL_power"
    elif fpr > BAR_NULL_FPR:
        verdict = "KILL_fpr"
    elif balanced < BAR_BALANCED:
        verdict = "KILL_balanced"
    else:
        verdict = "PASS"

    per_n = {}
    for n in N_LIST:
        sub = [x for x in rows if x["n_basis"] == n]
        rd = [x for x in sub if x["pos_win"]]
        per_n[str(n)] = {
            "runs": len(sub),
            "power": sum(x["pos_win"] for x in sub) / len(sub),
            "readable": len(rd),
            "null_wins": sum(x["null_win"] for x in rd),
            "null_fpr": (sum(x["null_win"] for x in rd) / len(rd)) if rd else None,
        }

    out = {
        "protocol_sha256": sha,
        "config": {
            "replications": args.replications, "n_list": list(N_LIST),
            "ambient_dim": AMBIENT, "n_seeds_per_condition": N_SEEDS,
            "n_probe": N_PROBE, "n_eval": N_EVAL, "energy_targets": list(TARGETS),
            "alpha": ALPHA, "positive_signal": POSITIVE_SIGNAL,
            "seed_block_start": args.seed_block,
        },
        "bars": {"balanced_min": BAR_BALANCED, "chance_balanced": CHANCE_BALANCED,
                 "null_fpr_max": BAR_NULL_FPR, "power_min": BAR_POWER,
                 "nominal_alpha": NOMINAL_ALPHA},
        "primary": {"BALANCED": balanced, "n": len(rows)},
        "components": {"NULL_FPR": fpr, "n_readable": len(readable),
                       "null_wins": sum(x["null_win"] for x in readable),
                       "POWER": power, "n_total": len(rows),
                       "n_withheld": len(withheld),
                       "withheld": [(x["n_basis"], x["rng_seed_pos"])
                                    for x in withheld]},
        "per_n": per_n,
        "verdict": verdict,
        "env": {"python": sys.version.split()[0], "numpy": np.__version__,
                "platform": platform.platform()},
        "rows": rows,
    }
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in
                      ("primary", "components", "per_n", "bars", "verdict")},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
