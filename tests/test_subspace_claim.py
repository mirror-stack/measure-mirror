"""㉘ subspace_claim_check — the declaration auditor.

Test names carry the -k filters the development plan verifies against:
signflip (A3) · findings (A4) · not_applicable (A5) · consistency (A6) ·
granularity (A7).
"""
import pytest

from measure_mirror import subspace_claim_check
from measure_mirror.mm import _paired_signflip_p, _subspace_consistency


AMBIENT = 24
GRID = [0.5, 0.7, 0.9]          # retained-energy grid points
SEEDS = list(range(10))


def _lvl(findings, probe_suffix):
    """Level of the single finding whose probe label ends with `probe_suffix`."""
    hits = [f for f in findings if f.probe.endswith(probe_suffix)]
    assert len(hits) <= 1, f"{probe_suffix}: expected ≤1 finding, got {len(hits)}"
    return hits[0].level if hits else None


# k must be a strictly increasing function of the grid point within an arm:
# retained energy is a function of (basis, k), so the same k cannot yield two
# different energies for the same arm+seed. C1 enforces exactly that, and it
# caught an earlier version of this fixture that violated it.
_K_CONCENTRATED = {0.5: 1, 0.7: 2, 0.9: 3}


def _cells(arm, role, *, k_of, effect, seeds=SEEDS, grid=GRID):
    """One cell per (seed, grid point). `energy_kept` always meets the target."""
    out = []
    for s in seeds:
        for g in grid:
            k = k_of(g)
            # a null arm spreads energy evenly, so energy ≈ k/d — that is the
            # relation C4 exploits to recover the ambient dimension
            energy = k / AMBIENT if role in ("null", "matched_null") else g
            out.append({"arm": arm, "role": role, "seed": s, "grid_point": g,
                        "k": k, "energy_kept": energy, "energy_target": g,
                        "effect": effect})
    return out


def clean_report(**over):
    """A complete, internally consistent, honest report."""
    rep = {
        "anchor": {"code_path": "frozen", "tol": {"loss": 1e-9},
                   "n_seeds": 10, "guard_seeds": 5, "max_abs_delta": 0.0},
        "grid": {"kind": "energy"},
        "ambient_dim": AMBIENT,
        "bar": 0.90,
        "n_basis_fit": 8 * AMBIENT,
        "basis_fit_ids": list(range(0, 8)),
        "effect_eval_ids": list(range(8, 20)),
        "cells": (
            _cells("TGT", "target", k_of=_K_CONCENTRATED.get, effect=0.80)
            + _cells("RND", "null", k_of=lambda g: round(g * AMBIENT), effect=0.40)
            + _cells("SHUF", "dof_control", k_of=_K_CONCENTRATED.get, effect=0.42)
        ),
        "arms": {
            "TGT":  {"role": "target",      "effect_by_seed": [0.80 + 0.01 * i for i in range(10)]},
            "RND":  {"role": "null",        "effect_by_seed": [0.40 + 0.01 * i for i in range(10)]},
            "SHUF": {"role": "dof_control", "effect_by_seed": [0.42 + 0.01 * i for i in range(10)]},
        },
    }
    rep.update(over)
    return rep


# ─────────────────────────── A3 · signflip ───────────────────────────
def test_signflip_exact_small_n_is_closed_form():
    # 5 identical positive diffs: only the all-+ and all-− assignments reach
    # |mean| ≥ observed → 2/32.
    assert _paired_signflip_p([1.0] * 5) == pytest.approx(2 / 32)


def test_signflip_is_deterministic_in_both_regimes():
    small = [0.3, -0.1, 0.4, 0.2, 0.5]
    big = [0.1 * ((-1) ** i) + 0.25 for i in range(20)]      # n = 20 → Monte Carlo
    assert _paired_signflip_p(small) == _paired_signflip_p(small)
    assert _paired_signflip_p(big) == _paired_signflip_p(big)


def test_signflip_edge_cases():
    assert _paired_signflip_p([]) is None
    assert _paired_signflip_p([0.0, 0.0, 0.0]) == 1.0
    p = _paired_signflip_p([0.1, -0.2, 0.05])
    assert 0.0 < p <= 1.0


def test_signflip_no_signal_is_not_significant():
    # symmetric diffs centred on zero must not clear α=0.05
    assert _paired_signflip_p([0.1, -0.1, 0.2, -0.2, 0.05, -0.05]) > 0.05


def test_signflip_switches_to_monte_carlo_above_14():
    # exact enumeration of 2^n is only affordable up to the declared bound;
    # both sides must still return a usable probability
    assert 0.0 < _paired_signflip_p([0.5] * 14) <= 1.0
    assert 0.0 < _paired_signflip_p([0.5] * 15) <= 1.0


# ─────────────────────────── A4 · findings ───────────────────────────
def test_findings_clean_report_passes_every_finding():
    f = subspace_claim_check(clean_report())
    assert _lvl(f, "no-anchor") == "OK"
    assert _lvl(f, "energy-not-matched") == "OK"
    assert _lvl(f, "dof-uncontrolled") == "OK"
    assert _lvl(f, "null-ladder") == "OK"
    assert _lvl(f, "estimation-eval-overlap") == "OK"
    assert _lvl(f, "saturation") == "OK"
    assert not [x for x in f if x.level == "FAIL"]


def test_findings_anchor_absent_is_failure():
    f = subspace_claim_check(clean_report(anchor=None))
    assert _lvl(f, "no-anchor") == "FAIL"


def test_findings_anchor_declaration_lint_catches_each_hole():
    for bad, needle in (
        ({"code_path": "unknown", "tol": 1e-9, "n_seeds": 10, "guard_seeds": 5}, "unknown"),
        ({"code_path": "mixed", "tol": 1e-9, "n_seeds": 10, "guard_seeds": 5}, "mixed_detail"),
        ({"code_path": "reimplemented", "tol": 1e-9, "n_seeds": 10, "guard_seeds": 5}, "reference"),
        ({"code_path": "frozen", "n_seeds": 10, "guard_seeds": 5}, "tol"),
        ({"code_path": "frozen", "tol": 1e-9, "n_seeds": 10}, "guard_seeds"),
    ):
        f = subspace_claim_check(clean_report(anchor=bad))
        hit = [x for x in f if x.probe.endswith("no-anchor")][0]
        assert hit.level == "FAIL", bad
        assert needle in hit.msg, (bad, hit.msg)


def test_findings_priority_anchor_failure_holds_null_ladder_below_ok():
    """★ The priority rule: p is fine, but the axis it sits on is not.

    Without a reproducible anchor the ratio normalizer is undefined, so a
    ladder that clears every rung still cannot be reported OK.
    """
    rep = clean_report(anchor=None)
    f = subspace_claim_check(rep)
    ladder = [x for x in f if x.probe.endswith("null-ladder")][0]
    assert ladder.level == "WARN"
    assert ladder.data["held_by"] == "no-anchor"
    # and the same table WITH an anchor does reach OK — so the hold is the
    # anchor's doing, not a weak ladder
    assert _lvl(subspace_claim_check(clean_report()), "null-ladder") == "OK"


def test_findings_null_ladder_fails_when_target_does_not_clear():
    rep = clean_report()
    rep["arms"]["RND"]["effect_by_seed"] = rep["arms"]["TGT"]["effect_by_seed"][:]
    f = subspace_claim_check(rep)
    assert _lvl(f, "null-ladder") == "FAIL"


def test_findings_dof_control_removed_is_failure_in_a_complete_report():
    rep = clean_report()
    rep["cells"] = [c for c in rep["cells"] if c["arm"] != "SHUF"]
    del rep["arms"]["SHUF"]
    assert _lvl(subspace_claim_check(rep), "dof-uncontrolled") == "FAIL"


def test_findings_estimation_eval_overlap():
    assert _lvl(subspace_claim_check(
        clean_report(effect_eval_ids=list(range(4, 16)))), "estimation-eval-overlap") == "FAIL"
    assert _lvl(subspace_claim_check(
        clean_report(basis_fit_ids=None)), "estimation-eval-overlap") == "WARN"


def test_findings_vacuous_certificate():
    rep = clean_report()
    rep["arms"]["MN"] = {"role": "matched_null",
                         "effect_by_seed": [0.41 + 0.01 * i for i in range(10)]}
    assert _lvl(subspace_claim_check(rep), "vacuous") == "WARN"        # undeclared
    rep["certificate"] = {"MN": {"passed": False, "amp_rel": 0.4}}
    assert _lvl(subspace_claim_check(rep), "vacuous") == "FAIL"        # declared + failed
    rep["certificate"] = {"MN": {"passed": True, "amp_rel": 1.4e-06}}
    assert _lvl(subspace_claim_check(rep), "vacuous") == "OK"


def test_findings_saturation_when_null_already_clears_the_bar():
    rep = clean_report(bar=0.10)      # null effect ≈ 0.40 ≫ bar
    for c in rep["cells"]:
        if c["arm"] == "RND":
            c["effect"] = 0.40
    assert _lvl(subspace_claim_check(rep), "saturation") == "FAIL"


def test_findings_underdetermined_basis_is_a_declaration_lint():
    f = subspace_claim_check(clean_report(n_basis_fit=10))
    assert _lvl(f, "underdetermined-basis") == "WARN"
    assert _lvl(subspace_claim_check(clean_report()), "underdetermined-basis") is None


# ────────────────────── A5 · absent vs not_applicable ──────────────────────
def test_not_applicable_no_grid_is_not_a_failure():
    """104_-style: no grid at all. 'Not applicable' must not read as 'failed',
    or a clean report gets FAILed and the false-positive kill misfires."""
    rep = clean_report(grid=None)
    f = subspace_claim_check(rep)
    assert _lvl(f, "energy-not-matched") == "N/A"
    assert not [x for x in f if x.probe.endswith("energy-not-matched") and x.level == "FAIL"]


def test_not_applicable_single_arm_grid_point_has_nothing_to_match():
    rep = clean_report()
    rep["cells"] = [c for c in rep["cells"] if c["arm"] == "TGT"]
    assert _lvl(subspace_claim_check(rep), "energy-not-matched") == "N/A"


def test_not_applicable_partial_report_downgrades_dof_to_warn():
    """103_-style honest partial report: no grid, no per-seed vectors.
    Missing scope is not the same as omission → WARN, not FAIL."""
    rep = clean_report(grid=None, arms={})
    assert _lvl(subspace_claim_check(rep), "dof-uncontrolled") in ("WARN", "OK")
    rep["cells"] = [c for c in rep["cells"] if c["arm"] != "SHUF"]
    assert _lvl(subspace_claim_check(rep), "dof-uncontrolled") == "WARN"


def test_not_applicable_k_locked_grid_fails_even_when_labelled_energy():
    """The confound is a k grid wearing an energy label — every arm on the same
    k. NOT 'achieved energies differ': k is an integer, so they always do."""
    rep = clean_report()
    for c in rep["cells"]:
        c["k"] = 4                                  # same k for every arm
    assert _lvl(subspace_claim_check(rep), "energy-not-matched") == "FAIL"


def test_not_applicable_coincidental_k_collisions_are_not_a_k_grid():
    """★ The regression that killed seal 3e6bd450. Arms choosing small integer
    k do collide by chance — real 105_ has 8 of 160 compared cells k-locked.
    Only a fraction of exactly 1.0 is a k grid; anything less is coincidence."""
    rep = clean_report()
    # lock k for one grid point only, leave the rest varying
    for c in rep["cells"]:
        if c["grid_point"] == 0.5:
            c["k"] = 7
    f = subspace_claim_check(rep)
    hit = [x for x in f if x.probe.endswith("energy-not-matched")][0]
    assert hit.level == "OK"
    assert 0.0 < hit.data["k_locked_fraction"] < 1.0


def test_not_applicable_declared_k_grid_fails_outright():
    assert _lvl(subspace_claim_check(clean_report(grid={"kind": "k"})),
                "energy-not-matched") == "FAIL"


def test_not_applicable_unequal_achieved_energy_is_not_by_itself_a_failure():
    """★ The regression this exists for. Real 105_ data has a 34% per-bin spread
    between arms at target 0.1 (RANDOM 0.1203 vs GLOBAL 0.1824) because integer
    k cannot hit a continuous energy target. Gating on that spread FAILed a
    verbatim clean report — the false positive that killed seal 98e993b2."""
    rep = clean_report()
    for c in rep["cells"]:
        if c["arm"] == "TGT":
            c["energy_kept"] = c["energy_kept"] * 1.5
    f = subspace_claim_check(rep)
    assert _lvl(f, "energy-not-matched") == "OK"       # k still varies per arm
    hit = [x for x in f if x.probe.endswith("energy-not-matched")][0]
    assert hit.data["max_energy_spread"] > 0.05        # …and the spread is reported


# ─────────────────────────── A6 · consistency ───────────────────────────
def test_consistency_c1_same_k_must_give_identical_energy():
    rows = [{"arm": "A", "role": "target", "seed": 1, "bin": None, "k": 3,
             "energy_kept": 0.5, "energy_target": None, "effect": None},
            {"arm": "A", "role": "target", "seed": 1, "bin": None, "k": 3,
             "energy_kept": 0.6, "energy_target": None, "effect": None}]
    assert _lvl(_subspace_consistency(rows), "consistency-C1") == "FAIL"


def test_consistency_c2_energy_must_not_fall_as_k_rises():
    rows = [{"arm": "A", "role": "target", "seed": 1, "bin": None, "k": 2,
             "energy_kept": 0.7, "energy_target": None, "effect": None},
            {"arm": "A", "role": "target", "seed": 1, "bin": None, "k": 5,
             "energy_kept": 0.3, "energy_target": None, "effect": None}]
    assert _lvl(_subspace_consistency(rows), "consistency-C2") == "FAIL"


def test_consistency_c3_achieved_must_meet_declared_target():
    rows = [{"arm": "A", "role": "target", "seed": 1, "bin": None, "k": 2,
             "energy_kept": 0.4, "energy_target": 0.9, "effect": None}]
    assert _lvl(_subspace_consistency(rows), "consistency-C3") == "FAIL"


def test_consistency_c4_recovers_ambient_dimension_from_null_arms():
    """★ The load-bearing law: the null arm's own numbers testify to d, which
    caps what the target arm's (k, energy) pairs can claim."""
    f = subspace_claim_check(clean_report())
    c4 = [x for x in f if x.probe.endswith("consistency-C4")][0]
    assert c4.level == "OK"
    assert c4.data["recovered_dim"] == pytest.approx(AMBIENT, rel=0.02)


def test_consistency_c4_flags_a_declared_dimension_that_does_not_match():
    f = subspace_claim_check(clean_report(ambient_dim=6))
    assert _lvl(f, "consistency-C4") == "WARN"


def test_consistency_c5_concavity_stays_dead():
    """🔴 C5 (energy concave in k) was KILLED on real data — 770 of 1431 cells
    violate it, because it only holds when the sorting criterion is the
    measuring criterion. Shipping it would have been a false-positive misfire
    machine. This test exists so nobody adds it back by reflex."""
    import measure_mirror.mm as m
    src = open(m.__file__, encoding="utf-8").read()
    assert "consistency-C5" not in src
    # a convex (non-concave) but otherwise legal table must stay clean
    rows = [{"arm": "A", "role": "target", "seed": 1, "bin": None, "k": k,
             "energy_kept": e, "energy_target": None, "effect": None}
            for k, e in ((1, 0.10), (2, 0.15), (3, 0.45), (4, 0.95))]
    assert not [x for x in _subspace_consistency(rows) if x.level == "FAIL"]


def test_consistency_clean_table_has_no_violations():
    f = subspace_claim_check(clean_report())
    assert not [x for x in f if x.probe.startswith("㉘ consistency-") and x.level == "FAIL"]


# ─────────────────────────── A7 · granularity ───────────────────────────
def test_granularity_vector_k_and_energy_are_accepted():
    """105_ carries per-bin length-4 vectors. Averaging them would erase the
    per-bin overshoot this probe exists to catch, so vectors stay vectors."""
    rep = clean_report()
    rep["cells"] = rep["cells"] + [{
        "arm": "VEC", "role": "data_only", "seed": 0, "grid_point": 0.5,
        "k": [2, 3, 4, 5], "energy_kept": [0.50, 0.52, 0.54, 0.56],
    }]
    f = subspace_claim_check(rep)
    assert not [x for x in f if x.probe.endswith("schema")]


def test_granularity_vector_length_mismatch_is_a_schema_failure():
    rep = clean_report()
    rep["cells"] = [{"arm": "V", "role": "target", "seed": 0, "grid_point": 0.5,
                     "k": [2, 3, 4], "energy_kept": [0.5, 0.6]}]
    f = subspace_claim_check(rep)
    schema = [x for x in f if x.probe.endswith("schema")][0]
    assert schema.level == "FAIL"
    assert "vector lengths must match" in schema.msg


def test_granularity_missing_seed_vectors_warns_instead_of_permuting_a_mean():
    """Without seed-level values a paired test silently runs at n=1. That is
    the silent error the 103_ adapter would otherwise produce."""
    rep = clean_report()
    for meta in rep["arms"].values():
        meta.pop("effect_by_seed")
    f = subspace_claim_check(rep)
    assert _lvl(f, "insufficient-granularity") == "WARN"
    assert _lvl(f, "null-ladder") == "WARN"


def test_granularity_unknown_role_is_rejected():
    rep = clean_report()
    rep["cells"] = [{"arm": "X", "role": "definitely_not_a_role", "seed": 0,
                     "grid_point": 0.5, "k": 2, "energy_kept": 0.5}]
    assert _lvl(subspace_claim_check(rep), "schema") == "FAIL"


def test_granularity_paired_test_uses_seed_level_n_not_one():
    f = subspace_claim_check(clean_report())
    ladder = [x for x in f if x.probe.endswith("null-ladder")][0]
    for res in ladder.data["results"].values():
        assert res["n"] == len(SEEDS)
        assert res["exact"] is True


# ─────────────── ⑧ dof-outperforms-target · the coherence law ───────────────
# Added after substrate-2 (seal 5c78e503) turned `relabeled_dof` into a
# confirmed false negative: the probe had NO mechanism for a role swap, and the
# case had passed on FM×CDE only because the shuffled arm did not beat the null
# there. The law: a dof_control is the target's procedure with the claimed
# structure destroyed, and destroying structure cannot ADD effect.
def _swap_roles(rep, a, b):
    """Swap two arms' declared roles in both `arms` and `cells`."""
    import copy
    r = copy.deepcopy(rep)
    r["arms"][a]["role"], r["arms"][b]["role"] = (r["arms"][b]["role"],
                                                 r["arms"][a]["role"])
    for c in r["cells"]:
        if c["arm"] == a:
            c["role"] = r["arms"][a]["role"]
        elif c["arm"] == b:
            c["role"] = r["arms"][b]["role"]
    return r


def test_coherence_ok_when_the_control_stays_below_its_target():
    f = subspace_claim_check(clean_report())
    assert _lvl(f, "dof-outperforms-target") == "OK"
    assert _lvl(f, "null-ladder") == "OK"


def test_coherence_fails_when_the_control_beats_its_target():
    """The swap the probe used to confirm. TGT and SHUF exchange roles, so the
    declared target (0.42) now sits below the declared control (0.80)."""
    f = subspace_claim_check(_swap_roles(clean_report(), "TGT", "SHUF"))
    assert _lvl(f, "dof-outperforms-target") == "FAIL"


def test_coherence_violation_holds_the_ladder_below_ok():
    """Same priority shape as the anchor rule: the ladder's arithmetic is fine,
    but a consumer reading only `null-ladder` must not see a green light on a
    report whose control beats its treatment."""
    f = subspace_claim_check(_swap_roles(clean_report(), "TGT", "SHUF"))
    ladder = next(x for x in f if x.probe.endswith("null-ladder"))
    assert ladder.level == "WARN"
    assert ladder.data["held_by"] == "dof-outperforms-target"


def test_coherence_warns_when_the_control_only_leads_on_the_mean():
    """A control level with its treatment leaves nothing for the treatment to
    have caused — but it is not a verdict, so it must not be a FAIL."""
    rep = clean_report()
    # every seed alternates sign → mean excess > 0, sign-flip p well above α
    rep["arms"]["SHUF"]["effect_by_seed"] = [
        v + (0.05 if i % 2 else -0.04)
        for i, v in enumerate(rep["arms"]["TGT"]["effect_by_seed"])]
    assert _lvl(subspace_claim_check(rep), "dof-outperforms-target") == "WARN"


def test_coherence_is_not_emitted_without_a_dof_control_arm():
    """Nothing to compare is not a pass and not a failure — no finding at all.
    `dof-uncontrolled` is the finding that speaks to the absence."""
    rep = clean_report()
    rep["arms"].pop("SHUF")
    rep["cells"] = [c for c in rep["cells"] if c["arm"] != "SHUF"]
    f = subspace_claim_check(rep)
    assert _lvl(f, "dof-outperforms-target") is None
    assert _lvl(f, "dof-uncontrolled") == "FAIL"


def test_coherence_does_not_demand_the_target_be_variance_optimal():
    """The rejected alternative, pinned as a test so it cannot creep back.

    A target arm is a hypothesis about where the EFFECT lives, not where the
    variance lives — 103_ labels its PCA arm `data_only` for exactly that
    reason. A rule keyed on 'the target must need the fewest components' would
    FAIL this honest report, where the control reaches each energy target with
    the same k as the target and the null needs far more.
    """
    rep = clean_report()
    tgt_k = {c["grid_point"]: c["k"] for c in rep["cells"] if c["arm"] == "TGT"}
    shuf_k = {c["grid_point"]: c["k"] for c in rep["cells"] if c["arm"] == "SHUF"}
    assert tgt_k == shuf_k                      # no k-ordering signal at all
    assert _lvl(subspace_claim_check(rep), "dof-outperforms-target") == "OK"
