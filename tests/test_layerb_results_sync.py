"""㉘ layer B RESULTS.md ↔ sealed result JSON sync guard.

A number written into the docs by hand is the exact defect class this tool
exists to catch — and it happened here once, when the README's `wilson_ci`
example said 0.7527 while the code returns 0.7533. So the layer-B results page
is *rendered* from the sealed run's JSON, and this test re-renders it and fails
on any drift.

It also pins the verdict to the ledger seals, so a later edit cannot quietly
promote a KILL into a PASS in the prose.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVAL = REPO / "eval" / "subspace_layerb"
sys.path.insert(0, str(EVAL))

import make_results                                        # noqa: E402

CLAIM_SEAL = "bd98a0450c65f35c31722477bfa3acaf0a3fc77db1b3b7112a4f4554187bbe19"
RESULT_SEAL = "c6a3e145e5e91ec8cc5f733b02549ec27434f4e902fa137a6e72242988569c95"
PROTOCOL_COMBINED = ("73cddbfa59c07124118739efa478fe8f4"
                     "adea5f272cbe43f326340eee71fc9d6")


def _result() -> dict:
    return json.loads((EVAL / "sealed_result.json").read_text())


def test_results_md_is_a_faithful_render_of_the_sealed_json():
    assert (EVAL / "RESULTS.md").read_text() == make_results.render(_result()), (
        "RESULTS.md drifted from sealed_result.json — re-run "
        "eval/subspace_layerb/make_results.py rather than editing the numbers.")


def test_verdict_and_bars_are_the_pre_committed_ones():
    d = _result()
    assert d["verdict"] == "PASS"
    assert d["bars"] == {"balanced_min": 0.90, "chance_balanced": 0.50,
                         "null_fpr_max": 0.10, "power_min": 0.90,
                         "nominal_alpha": 0.05}
    assert d["protocol_sha256"]["combined"] == PROTOCOL_COMBINED
    assert make_results.SEAL == CLAIM_SEAL
    assert make_results.AM_SEAL == RESULT_SEAL


def test_the_verdict_follows_from_the_numbers_and_not_from_the_label():
    """Recompute the verdict from the raw rows. A stored 'PASS' string is a
    claim; the rows are the evidence."""
    d = _result()
    rows, bars = d["rows"], d["bars"]
    assert len(rows) == d["primary"]["n"] == 240

    power = sum(r["pos_win"] for r in rows) / len(rows)
    readable = [r for r in rows if r["pos_win"]]
    fpr = sum(r["null_win"] for r in readable) / len(readable)
    balanced = (power + (1.0 - fpr)) / 2.0

    assert abs(power - d["components"]["POWER"]) < 1e-12
    assert abs(fpr - d["components"]["NULL_FPR"]) < 1e-12
    assert abs(balanced - d["primary"]["BALANCED"]) < 1e-12

    assert power >= bars["power_min"]
    assert fpr <= bars["null_fpr_max"]
    assert balanced >= bars["balanced_min"]


def test_withheld_runs_are_excluded_not_counted_as_passes():
    """The load-bearing accounting rule: a null run whose own positive control
    failed is unreadable, and must not be silently scored as 'no false win'."""
    d = _result()
    rows = d["rows"]
    withheld = [r for r in rows if not r["pos_win"]]
    assert len(withheld) == d["components"]["n_withheld"]
    assert len(withheld) + d["components"]["n_readable"] == len(rows)
    assert sorted(tuple(x) for x in d["components"]["withheld"]) == sorted(
        (r["n_basis"], r["rng_seed_pos"]) for r in withheld)


def test_judged_seeds_are_disjoint_from_the_burned_development_seeds():
    """Development and pre-seal smoke blocks were declared burned in the seal;
    a judged run reusing them would be scoring on data it had already seen."""
    d = _result()
    burned_blocks = (111_000, 222_000)
    burned_seeds = {20260805, 4242}
    used = {r["rng_seed_null"] for r in d["rows"]} | {
        r["rng_seed_pos"] for r in d["rows"]}
    assert not (used & burned_seeds)
    for block in burned_blocks:
        assert not any(block <= s < block + 80_000 for s in used)
    assert d["config"]["seed_block_start"] == 900_001


def test_results_page_states_the_scope_it_did_not_close():
    md = (EVAL / "RESULTS.md").read_text()
    assert "a consistent forgery still passes" in md
    assert "Says nothing about any real substrate" in md
    assert "not** evidence the pipeline beats its own test" in md
