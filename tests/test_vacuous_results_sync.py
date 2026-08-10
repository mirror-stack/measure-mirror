"""㉘ vacuous-real-runs RESULTS.md ↔ sealed result JSON sync guard.

Same rule as `test_layerb_results_sync.py`, same reason: a number typed into
the docs by hand is the defect class this tool exists to catch. The results
page is rendered from the sealed JSON; this test re-renders it and fails on
drift, and re-derives the verdict from the raw rows so a stored label cannot
quietly diverge from the evidence.
"""
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVAL = REPO / "eval" / "subspace_vacuous_real"

# Load by path under a unique module name — a bare `import make_results` would
# collide in sys.modules with the layer-B results test's module of the same
# name, and whichever test ran first would silently win.
_spec = importlib.util.spec_from_file_location(
    "make_vacuous_results", EVAL / "make_results.py")
make_vacuous_results = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(make_vacuous_results)

CLAIM_SEAL = "2a22a95acf542fc56f511e5f19a376883e13793cdd76da57943ac2cc157f9cf2"
RESULT_SEAL = "79cd081647e0c876ab89fabbd1cede56a43c40ead3f789c652db53303db19f9c"
PROTOCOL_COMBINED = ("9e5f3e969f1dfc99193dc39ca12b6bb97"
                     "96c678fbf35545046d17211f3ea95e4")
TOL, DELTA = 0.05, 0.005


def _result() -> dict:
    return json.loads((EVAL / "sealed_result.json").read_text())


def test_results_md_is_a_faithful_render_of_the_sealed_json():
    assert (EVAL / "RESULTS.md").read_text() == make_vacuous_results.render(
        _result()), (
        "RESULTS.md drifted from sealed_result.json — re-run "
        "eval/subspace_vacuous_real/make_results.py rather than editing "
        "the numbers.")


def test_verdict_bars_and_seals_are_the_pre_committed_ones():
    d = _result()
    assert d["verdict"] == "PASS"
    assert d["bars"] == {"balanced_min": 1.0, "chance": 0.50, "min_class": 30}
    assert d["config"]["certificate_tol"] == TOL
    assert d["config"]["boundary_delta"] == DELTA
    assert d["protocol_sha256"]["combined"] == PROTOCOL_COMBINED
    assert make_vacuous_results.SEAL == CLAIM_SEAL
    assert make_vacuous_results.AM_SEAL == RESULT_SEAL


def test_the_verdict_follows_from_the_rows_and_not_from_the_label():
    """Ground-truth classes, accuracies and anchors, all re-derived from the
    raw rows the run recorded."""
    d = _result()
    rows = d["rows"]

    for x in rows:
        m = x["truth_margin"]
        truth = ("unmatched" if m < -TOL - DELTA
                 else "matched" if m >= -TOL + DELTA else "boundary")
        assert truth == x["truth"]

    unmatched = [x for x in rows if x["truth"] == "unmatched"]
    matched = [x for x in rows if x["truth"] == "matched"]
    boundary = [x for x in rows if x["truth"] == "boundary"]
    p = d["primary"]
    assert (len(unmatched), len(matched), len(boundary)) == (
        p["n_unmatched"], p["n_matched"], p["n_withheld_boundary"])
    assert len(unmatched) >= d["bars"]["min_class"]
    assert len(matched) >= d["bars"]["min_class"]

    acc_un = sum(x["vacuous_level"] == "FAIL" for x in unmatched) / len(unmatched)
    acc_ma = sum(x["vacuous_level"] == "OK" for x in matched) / len(matched)
    assert acc_un == p["acc_unmatched"]
    assert acc_ma == p["acc_matched"]
    assert (acc_un + acc_ma) / 2.0 == p["BALANCED_CASE"] >= d["bars"]["balanced_min"]

    # anchors as sealed in v2: no extreme run in the OPPOSITE class
    assert not any(x["truth"] == "matched"
                   for x in rows if x["proc"] == "sloppy" and x["n_fit"] == 8)
    assert not any(x["truth"] == "unmatched"
                   for x in rows if x["proc"] == "honest" and x["n_fit"] == 200)
    # non-constant instrument
    assert {"FAIL", "OK"} <= {x["vacuous_level"] for x in rows}


def test_judged_seeds_are_disjoint_from_the_burned_blocks():
    """dev smoke (555001) and the INVALID v1 attempt (1100001) are burned."""
    d = _result()
    assert d["config"]["seed_block_start"] == 1_200_001
    used = {x["base_seed"] for x in d["rows"]}
    for block in (555_001, 1_100_001):
        assert not any(block <= s < block + 80_000 for s in used)


def test_results_page_keeps_the_invalid_attempt_and_the_scope():
    md = (EVAL / "RESULTS.md").read_text()
    assert "INVALID" in md and "17c36ad6" in md          # v1 kept, not hidden
    assert "consistent forgery" in md                    # standing hole stated
    assert "Synthetic isotropic Gaussians only" in md
    assert "vacuous_as_collapse" in md                   # planted case stays
