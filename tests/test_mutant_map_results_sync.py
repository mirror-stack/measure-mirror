"""㉘ mutant-map RESULTS.md ↔ sealed JSON sync guard.

Same rule as the other results-sync tests, same reason: a number typed into
the docs by hand is the defect class this tool exists to catch. The results
page is rendered from the sealed JSON; this test re-renders it and fails on
drift, and re-derives the row types from the recorded clause columns so a
stored label cannot quietly diverge from the evidence.
"""
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVAL = REPO / "eval" / "subspace_mutant_map"

_spec = importlib.util.spec_from_file_location(
    "make_mutant_map_results", EVAL / "make_results.py")
make_results = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(make_results)

_bspec = importlib.util.spec_from_file_location(
    "mutant_map_build_for_sync", EVAL / "build_map.py")
build_map = importlib.util.module_from_spec(_bspec)
_bspec.loader.exec_module(build_map)

CLAIM_SEAL = "e79696560233c5b72a9efafbc2112feb5b8d358d80a23f0722c78397e27dc787"
RESULT_SEAL = "ddf46281b6f74b7b8bbbd40fafa8d75f30f911a2063e8d78952f65f7adf0104f"


def _result() -> dict:
    return json.loads((EVAL / "sealed_map.json").read_text())


def test_results_md_is_a_faithful_render_of_the_sealed_json():
    assert (EVAL / "RESULTS.md").read_text() == make_results.render(_result()), (
        "RESULTS.md drifted from sealed_map.json — re-run "
        "eval/subspace_mutant_map/make_results.py rather than editing the "
        "numbers.")


def test_verdict_bars_and_seals_are_the_pre_committed_ones():
    d = _result()
    assert d["verdict"] == "PASS"
    assert d["bars"] == {"primary_type_match_min": 1.0,
                         "n_primary_rows": 12, "chance": 0.0}
    assert make_results.SEAL == CLAIM_SEAL
    assert make_results.AM_SEAL == RESULT_SEAL


def test_row_types_follow_from_the_clause_columns_not_from_the_label():
    d = _result()
    for corpus in ("dev", "s2", "holdout"):
        for r in d[corpus]["rows"]:
            for c in r["clauses"]:
                assert c["type"] == build_map.clause_type(c), (r["id"], c)
            any_change = r["killed"]
            assert build_map.row_type(r["clauses"], any_change) == r["row_type"], r["id"]
            assert r["equivalent_suspect"] == (not any_change)


def test_vacuous_organic_counts_retell_the_sealed_rows():
    """The organic section is a re-read of seal 2a22a95a's rows — its counts
    must reproduce from that sealed artifact, not float free of it."""
    d = _result()
    sealed = json.loads(
        (REPO / "eval" / "subspace_vacuous_real" / "sealed_result.json").read_text())
    sloppy = [x for x in sealed["rows"] if x["proc"] == "sloppy"]
    got = d["vacuous_organic"]["sloppy_total"]
    assert got["runs"] == len(sloppy)
    assert got["killed"] == sum(x["truth"] == "unmatched" for x in sloppy)
    assert got["equivalent"] == sum(x["truth"] == "matched" for x in sloppy)
    assert got["withheld_boundary"] == sum(x["truth"] == "boundary" for x in sloppy)


def test_results_page_keeps_the_dominated_finding_and_the_scope():
    md = (EVAL / "RESULTS.md").read_text()
    assert "DOMINATED" in md and "cannot improve the verdict" in md
    assert "5c78e503" in md                      # the KILL this answers stays
    assert "equivalent" in md.lower()            # the screen is named
    assert "NOT claimed" in md                   # scope clause present
