#!/usr/bin/env python3
"""Planted control set for ㉘ subspace_claim_check.

Three adapters turn real sealed experiment output into the probe's report
schema, and a planted set edits those reports in known ways so the probe can be
scored in BOTH directions: a planted negative it passes is a false negative, a
planted positive it fails is a false positive.

Every case carries two honesty labels, because they are not all equally real:

  layer = real       the edit is a label move, a deletion, or a copy. No number
                     is invented. The strongest evidence.
          half       the real run lacks a field the case needs, so one field is
                     broadcast or synthesised while the rest stays real.
          synthetic  the numbers are made up, because the corpus contains no
                     instance of the thing being tested.
          B          not decidable by layer A at all — belongs to the executor.

  provenance         where the numbers came from, in words.

⚠️ The basis B and the perturbation samples dX were never written to disk
(*.pt/*.npy/*.npz: 0 files), and re-running costs 103_ 2647s · 104_ 508s ·
105_ 928s. So "real" here means the recorded table is real — not that we can
regenerate it.

Usage:
    python eval/subspace_planted/gen_cases.py            # regenerate cases.jsonl
    python eval/subspace_planted/gen_cases.py --check    # validate cases.jsonl
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases.jsonl"
HOLDOUT = HERE / "cases_holdout.jsonl"
# Source results live outside the package (they are experiment output, not
# library data). Override with FM_CDE_DIR when they sit elsewhere.
SRC = Path(os.environ.get("FM_CDE_DIR", "/data/seara/fm_cde_followup"))

AMBIENT_DIM = 24          # dX dimension; 103_ localized the gain to ~6/24
HOMES = ("v04", "v01", "v05")


# ─────────────────────────────────────────────────────────────
# Adapters — real sealed output → report schema
# ─────────────────────────────────────────────────────────────
def _anchor(res: dict, home: dict, *, code_path: str, mixed_detail: str = "") -> dict:
    cfg = res["config"]
    a = {
        "code_path": code_path,
        "tol": {"bit_repro": res["bars"]["repro_tol"]},
        "n_seeds": cfg["NCORE"],
        # kept separate on purpose: folding the guard seeds into n_seeds would
        # read as if the anchor had been verified across all 10 main seeds
        "guard_seeds": cfg["NREPRO_guard_seeds"],
        "max_abs_delta": home["bit_repro_dev"],
        "holds": home["bit_repro_ok"],
        "seal": home["seal"],
    }
    if mixed_detail:
        a["mixed_detail"] = mixed_detail
    return a


def adapt_105(res: dict, home_name: str = "v04") -> dict:
    """105_ local basis — the complete case. 4 arms × 10 seeds × 4 targets,
    with per-bin k/energy vectors kept as vectors (averaging them would erase
    the per-bin overshoot 105_ itself warns about in honest_limits)."""
    home, cfg = res["per_home"][home_name], res["config"]
    role_of = {"LOCAL": "target", "GLOBAL": "null",
               "RANDOM": "null", "LOCAL_SHUF": "dof_control"}
    cells = []
    for arm, per_seed in home["cells"].items():
        for seed, per_target in per_seed.items():
            for tgt, c in per_target.items():
                cells.append({
                    "arm": arm, "role": role_of[arm], "seed": int(seed),
                    "grid_point": float(tgt),
                    "k": c["k_per_bin"],                 # length-TBINS vector
                    "energy_kept": c["energy_per_bin"],  # same length
                    "energy_target": float(tgt),
                    "effect": c["ratio"],
                })
    return {
        "source": f"105_local_basis / {home_name}",
        # honest_limits[0]: the no-projection point calls the FROZEN g91
        # rollout, projected points use a local copy → genuinely mixed
        "anchor": _anchor(res, home, code_path="mixed",
                          mixed_detail="no-projection point calls the frozen "
                                       "g91.rollout; projected points use a "
                                       "local copy of the same rollout"),
        "grid": {"kind": "energy", "targets": cfg["energy_targets_primary"]},
        "ambient_dim": AMBIENT_DIM,
        "bar": res["bars"]["ratio_reference"],
        "n_basis_fit": len(cfg["train_seeds"]) * cfg["EP_CORE"],
        "basis_fit_ids": cfg["train_seeds"],
        "effect_eval_ids": cfg["heldout_seeds"],
        "cells": cells,
        "arms": {arm: {"role": role_of[arm],
                       "effect_by_seed": home["auc_energy_per_seed"][arm]}
                 for arm in home["cells"]},
    }


def adapt_103(res: dict, home_name: str = "v04") -> dict:
    """103_ localization — an HONEST PARTIAL report, not a clean one.

    The primary grid records `k_used` per seed but only a single mean
    `energy_achieved`, so cells here are arm×grid-point, NOT arm×seed×grid-point.
    Attaching the mean energy to each seed's k would manufacture cell-level
    numbers that the run never produced. There is also no dof_control arm.
    """
    home, cfg = res["per_home"][home_name], res["config"]
    role_of = {"AMPLIFY": "target", "RANDOM": "null", "PCA": "data_only"}
    cells = []
    for arm, per_target in home["energy_grid_primary"].items():
        for tgt, c in per_target.items():
            cells.append({
                "arm": arm, "role": role_of[arm],
                "seed": None,                    # ← no per-seed energy exists
                "grid_point": float(tgt),
                "k": c["k_used_mean"],
                "energy_kept": c["energy_achieved"],
                "energy_target": float(tgt),
                "effect": c["ratio"],
            })
    return {
        "source": f"103_localization / {home_name}",
        "anchor": _anchor(res, home, code_path="frozen"),
        "grid": {"kind": "energy", "targets": cfg["energy_targets_primary"]},
        "ambient_dim": AMBIENT_DIM,
        "bar": res["bars"]["ratio_for_kstar"],
        "n_basis_fit": len(cfg["train_seeds"]) * cfg["EP_CORE"],
        "basis_fit_ids": cfg["train_seeds"],
        "effect_eval_ids": cfg["heldout_seeds"],
        "cells": cells,
        "arms": {arm: {"role": role_of[arm],
                       "effect_by_seed": home["auc_energy_per_seed"][arm]}
                 for arm in home["energy_grid_primary"]},
    }


def adapt_104(res: dict, home_name: str = "v04") -> dict:
    """104_ matched subspace — NO GRID AT ALL.

    Energy matching is therefore NOT APPLICABLE, not failed. This case exists
    to prove the probe distinguishes the two; conflating them would FAIL a
    clean report and misfire the false-positive kill.

    Certificate note: `valid` is the arm's own verdict. Sub-checks can be
    inapplicable (`amp_bar: null`, `amp_ok: null`) — a null is NOT a pass, and
    is carried through as null rather than coerced to True.
    """
    home = res["per_home"][home_name]
    cert, arms = {}, {}
    for arm, man in home["manipulation"].items():
        cert[arm] = {"passed": bool(man["valid"]),
                     "fit_ok": man.get("fit_ok"), "sv_ok": man.get("sv_ok"),
                     "amp_ok": man.get("amp_ok")}     # may be None = not claimed
    for arm, a in home["arms"].items():
        role = "target" if arm == "REF" else "matched_null"
        arms[arm] = {"role": role, "effect_by_seed": a["per_seed_T"]}
    return {
        "source": f"104_matched_subspace / {home_name}",
        "anchor": _anchor(res, home, code_path="frozen"),
        "grid": None,                                   # ← the whole point
        "ambient_dim": AMBIENT_DIM,
        "cells": [],
        "arms": arms,
        "certificate": cert,
        "basis_fit_ids": res["config"]["train_seeds"],
        "effect_eval_ids": res["config"]["heldout_seeds"],
    }


# ─────────────────────────────────────────────────────────────
# Planted set
# ─────────────────────────────────────────────────────────────
def _case(cid, kind, layer, provenance, report, expect, note="", sfx=""):
    return {"id": cid + sfx, "kind": kind, "layer": layer, "provenance": provenance,
            "expect": expect, "note": note, "report": report}


def build_cases(r103, r104, r105, home: str = "v04") -> list[dict]:
    """Build the full case set from one home.

    `home` is a parameter so the same edit recipes can be replayed on a home
    that development never saw. v04 was used to build and repair the probe;
    v01 and v05 are held out. Replaying the identical recipes there is the only
    way a later judgment carries evidence the development set can no longer
    give.
    """
    c105, c103, c104 = (adapt_105(r105, home), adapt_103(r103, home),
                        adapt_104(r104, home))
    sfx = "" if home == "v04" else f"@{home}"
    out = []

    # ── planted POSITIVES — failing these is a false positive ──────────
    out.append(_case(
        "clean_105", "positive", "real",
        "105_local_basis v04 verbatim: 4 arms × 10 seeds × 4 energy targets, "
        "no cell dropped, LOCAL_SHUF left in place as the dof control",
        c105,
        {"no-anchor": ["OK"], "dof-uncontrolled": ["OK"],
         "energy-not-matched": ["OK"], "estimation-eval-overlap": ["OK"]},
        "the main clean case", sfx))

    out.append(_case(
        "partial_103", "positive", "real",
        "103_localization v04 verbatim. The run has no dof_control arm and no "
        "per-seed energy on the primary grid — that is the run, not an edit",
        c103,
        {"no-anchor": ["OK"], "dof-uncontrolled": ["WARN"],
         "estimation-eval-overlap": ["OK"]},
        "an honest PARTIAL report: WARN is the correct answer, FAIL is a false positive", sfx))

    out.append(_case(
        "clean_104", "positive", "real",
        "104_matched_subspace v04 verbatim. Corpus-wide VACUOUS labels: 0 "
        "(vacuous_arms=[] and result_102 any_vacuous_null=false), so this is "
        "'0 vacuous + applicable certificates pass', NOT 'a vacuous example'",
        c104,
        {"no-anchor": ["OK"], "energy-not-matched": ["N/A"], "vacuous": ["OK"]},
        "no grid ⇒ energy matching N/A. FAILing this misfires the FP kill", sfx))

    self_null = copy.deepcopy(c105)
    self_null["arms"] = {
        "RANDOM_as_target": {"role": "target",
                             "effect_by_seed": c105["arms"]["RANDOM"]["effect_by_seed"]},
        "RANDOM": c105["arms"]["RANDOM"],
    }
    out.append(_case(
        "self_null", "positive", "real",
        "105_ RANDOM arm copied into both target and null. Real measured "
        "numbers on both sides — a guaranteed null built without inventing one",
        self_null,
        {"null-ladder": ["FAIL", "WARN"]},
        "an arm cannot beat itself; claiming it does would be the false positive", sfx))

    # ── planted NEGATIVES — passing these is a false negative ──────────
    stripped = copy.deepcopy(c105)
    stripped.pop("anchor")
    out.append(_case(
        "anchor_stripped", "negative", "real",
        "105_ v04 with the anchor block deleted. Deletion only — no number touched",
        stripped,
        {"no-anchor": ["FAIL"], "null-ladder": ["WARN", "FAIL"]},
        "★ and the ladder must NOT drop to OK underneath a failed anchor", sfx))

    dof_gone = copy.deepcopy(c105)
    dof_gone["cells"] = [c for c in dof_gone["cells"] if c["arm"] != "LOCAL_SHUF"]
    dof_gone["arms"].pop("LOCAL_SHUF")
    out.append(_case(
        "dof_missing", "negative", "real",
        "105_ v04 with the LOCAL_SHUF arm removed. Deletion only",
        dof_gone,
        {"dof-uncontrolled": ["FAIL"]},
        "complete in every other respect ⇒ omission, not scope ⇒ FAIL not WARN", sfx))

    relabeled = copy.deepcopy(c105)
    for c in relabeled["cells"]:
        if c["arm"] == "LOCAL":
            c["role"] = "dof_control"
        elif c["arm"] == "LOCAL_SHUF":
            c["role"] = "target"
    relabeled["arms"]["LOCAL"]["role"] = "dof_control"
    relabeled["arms"]["LOCAL_SHUF"]["role"] = "target"
    out.append(_case(
        "relabeled_dof", "negative", "real",
        "105_ v04 with the roles of LOCAL and LOCAL_SHUF swapped. Label move "
        "only; energies still match, a dof arm still exists, the anchor is intact",
        relabeled,
        {"__must_not__": {"null-ladder": ["OK"]}},
        "★ UNDECIDABLE FROM THE TABLE ALONE. The kill is not 'catch it' — it is "
        "'do not confirm it'. Emitting OK here is the real false negative", sfx))

    leak = copy.deepcopy(c105)
    leak["effect_eval_ids"] = leak["basis_fit_ids"]
    out.append(_case(
        "estimation_eval_leak", "negative", "half",
        "105_ v04 seed sets are real (train 0..7 / heldout 8..19, disjoint), but "
        "the holdout field is overwritten to force the overlap — the run itself "
        "never leaked",
        leak,
        {"estimation-eval-overlap": ["FAIL"]},
        "half: the ids are real, the collision is manufactured", sfx))

    confound = copy.deepcopy(c103)
    sec = r103["per_home"][home]["k_grid_secondary"]
    confound["cells"] = [
        {"arm": arm, "role": {"AMPLIFY": "target", "RANDOM": "null",
                              "PCA": "data_only"}[arm],
         "seed": None, "grid_point": float(k), "k": float(k),
         # the k grid records one `energy` per (arm, k) — submitting it under a
         # grid declared as "energy" is exactly the confound 103_ fixed pre-seal
         "energy_kept": c["energy"], "energy_target": None, "effect": c["ratio"]}
        for arm, per_k in sec.items() for k, c in per_k.items()]
    confound["grid"] = {"kind": "energy", "note": "MISDECLARED — this is the k grid"}
    out.append(_case(
        "energy_confound", "negative", "half",
        "103_ secondary k-grid resubmitted with grid.kind='energy'. Numbers are "
        "real; the declaration is the lie",
        confound,
        {"energy-not-matched": ["FAIL"]},
        "half: 103_ found and fixed this pre-seal, so it is a regression test, "
        "not a fresh falsification", sfx))

    vac = copy.deepcopy(c104)
    worst = min(vac["certificate"], key=lambda a: 0 if vac["certificate"][a]["passed"] else 1)
    vac["certificate"][worst] = {"passed": False, "fit_ok": False,
                                 "sv_ok": None, "amp_ok": None}
    out.append(_case(
        "vacuous_as_collapse", "negative", "synthetic",
        "🚨 FABRICATED. The corpus contains ZERO real VACUOUS arms "
        "(vacuous_arms=[] · surviving_arms=[] · all manipulation valid=true · "
        "result_102 any_vacuous_null=false), so a certificate failure had to be "
        "written in by hand",
        vac,
        {"vacuous": ["FAIL"]},
        "🚨 BOTH directions of Finding `vacuous` are synthetic — see RESULTS.md", sfx))

    n = 10
    flat = {f"ARM{i}": {"role": "target" if i == 0 else "null",
                        "effect_by_seed": [0.5 + 0.001 * ((j * 7 + i * 3) % 11 - 5)
                                           for j in range(n)]}
            for i in range(3)}
    signal_free = {"source": "synthetic", "anchor": c105["anchor"],
                   "grid": None, "cells": [], "arms": flat,
                   "basis_fit_ids": [0], "effect_eval_ids": [1]}
    out.append(_case(
        "signal_free", "negative", "synthetic",
        "Fabricated by construction: all arms drawn from one distribution",
        signal_free,
        {"null-ladder": ["FAIL", "WARN"]},
        "synthetic by design — a real run with no signal was never recorded", sfx))

    out.append(_case(
        "overfit_smallsample", "negative", "B",
        "NOT DECIDABLE BY LAYER A. Overfitting is a property of the estimation "
        "run, and layer A never sees the estimation run — only the table it "
        "produced. Layer A's honest stand-in is the declaration lint "
        "n_basis_fit < 3×ambient_dim → underdetermined-basis WARN",
        {"anchor": c105["anchor"], "grid": None, "cells": [], "arms": {},
         "ambient_dim": AMBIENT_DIM, "n_basis_fit": 20},
        {"underdetermined-basis": ["WARN"]},
        "moved to layer B (executor). Scoring it as a layer-A catch would be an "
        "over-claim", sfx))

    return out


# ─────────────────────────────────────────────────────────────
def _load():
    need = {"r103": "result_103_localization.json",
            "r104": "result_104_matched_subspace.json",
            "r105": "result_105_local_basis.json"}
    missing = [f for f in need.values() if not (SRC / f).exists()]
    if missing:
        raise SystemExit(
            f"source results not found in {SRC}: {missing}\n"
            f"set FM_CDE_DIR to the directory holding them")
    return {k: json.loads((SRC / f).read_text()) for k, f in need.items()}


REQUIRED = ("id", "kind", "layer", "provenance", "expect", "report")
LAYERS = {"real", "half", "synthetic", "B"}


def check(path=None) -> int:
    path = path or CASES
    if not path.exists():
        print(f"✗ {path} missing — run without --check first")
        return 1
    cases = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    errs = []
    for c in cases:
        for f in REQUIRED:
            if f not in c:
                errs.append(f"{c.get('id','?')}: missing field {f!r}")
        if c.get("layer") not in LAYERS:
            errs.append(f"{c.get('id','?')}: layer={c.get('layer')!r} not in {sorted(LAYERS)}")
        if c.get("kind") not in ("positive", "negative"):
            errs.append(f"{c.get('id','?')}: kind={c.get('kind')!r}")
        if not str(c.get("provenance", "")).strip():
            errs.append(f"{c.get('id','?')}: empty provenance")
    counts: dict[str, int] = {}
    for c in cases:
        counts[c.get("layer", "?")] = counts.get(c.get("layer", "?"), 0) + 1
    print(f"  {len(cases)} case(s): " +
          " · ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print("  kinds: positive=%d negative=%d" % (
        sum(c["kind"] == "positive" for c in cases),
        sum(c["kind"] == "negative" for c in cases)))
    for e in errs:
        print(f"  ✗ {e}")
    print("  ✅ OK" if not errs else f"  ✗ {len(errs)} problem(s)")
    return 1 if errs else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="validate cases.jsonl instead of regenerating it")
    ap.add_argument("--holdout", action="store_true",
                    help="build cases_holdout.jsonl from the HELD-OUT homes "
                         "(v01, v05) — homes development never touched")
    args = ap.parse_args()
    if args.check:
        return check()
    src = _load()
    if args.holdout:
        cases = []
        for home in ("v01", "v05"):
            cases += build_cases(src["r103"], src["r104"], src["r105"], home)
        HOLDOUT.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n"
                                   for c in cases))
        print(f"  wrote {len(cases)} holdout case(s) → {HOLDOUT}")
        return check(HOLDOUT)
    cases = build_cases(src["r103"], src["r104"], src["r105"])
    CASES.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases))
    print(f"  wrote {len(cases)} case(s) → {CASES}")
    return check()


if __name__ == "__main__":
    sys.exit(main())
