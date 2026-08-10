"""㉘ mutant↔clause map — the differ, the taxonomy, and the controls.

The map's promise is mechanical: a clause only counts as catching a mutant
when the parent-diff proves the planted defect moved it. These tests pin the
taxonomy on constructed inputs (no auditor involved) and then hold the four
procedure controls on the real corpora — the same controls the sealed run
gates on, so a regression here is caught before it can invalidate a run.
"""
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVAL = REPO / "eval" / "subspace_mutant_map"

# Load by path under a unique module name — a bare import would collide in
# sys.modules with other eval directories' same-named modules.
_spec = importlib.util.spec_from_file_location(
    "mutant_map_build", EVAL / "build_map.py")
build_map = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_map)


def _clause(ok, level_changed, detail_changed):
    return {"ok": ok, "level_changed": level_changed,
            "detail_changed": detail_changed}


def test_clause_taxonomy_is_the_documented_lattice():
    assert build_map.clause_type(_clause(True, True, True)) == "ATTRIBUTED"
    assert build_map.clause_type(_clause(True, False, True)) == "DOMINATED"
    assert build_map.clause_type(_clause(True, False, False)) == "CONSTANT_SUSPECT"
    assert build_map.clause_type(_clause(False, True, True)) == "UNSAT"


def test_row_type_worst_clause_wins():
    att = {**_clause(True, True, True), "type": "ATTRIBUTED"}
    dom = {**_clause(True, False, True), "type": "DOMINATED"}
    uns = {**_clause(False, False, False), "type": "UNSAT"}
    assert build_map.row_type([att, att], True) == "ATTRIBUTED"
    assert build_map.row_type([att, dom], True) == "DOMINATED"
    assert build_map.row_type([att, uns], True) == "UNSAT"
    # a satisfied expectation on a mutant that changed NOTHING is an
    # equivalent-mutant suspect, never a catch
    con = {**_clause(True, False, False), "type": "CONSTANT_SUSPECT"}
    assert build_map.row_type([con], False) == "EQUIVALENT_SUSPECT"


def test_report_diff_isolates_the_mutation_surface():
    parent = {"a": 1, "cells": [{"x": 1}, {"x": 2}], "gone": True}
    mutant = {"a": 2, "cells": [{"x": 1}], "new": True}
    d = build_map.report_diff(parent, mutant)
    assert d["changed"] == ["a", "cells"]
    assert d["removed"] == ["gone"] and d["added"] == ["new"]
    assert d["cells_summary"] == {"parent_only": 1, "mutant_only": 0, "shared": 1}


def test_controls_hold_on_the_real_corpora():
    dev = build_map.load_cases(build_map.PLANTED / "cases.jsonl")
    s2 = build_map.load_cases(build_map.S2 / "cases_substrate2.jsonl")
    ctrl = build_map.run_controls(dev, s2)
    assert ctrl["all_ok"], ctrl
    assert ctrl["killed_control"]["row_type"] == "ATTRIBUTED"
    assert ctrl["equivalent_control"]["equivalent_suspect"]
    assert ctrl["neutral_control"]["surface_empty"]
    assert ctrl["s2_dominated_control"]["row_type"] == "DOMINATED"


def test_dev_home_reproduces_the_frozen_expectation_table():
    """The sealed claim froze per-recipe types from v04; if the auditor or the
    corpora change so that v04 no longer lands on that table, the frozen
    expectation is stale and the next sealed run must re-freeze under a new
    claim — this test is the tripwire."""
    dev = build_map.load_cases(build_map.PLANTED / "cases.jsonl")
    rows = build_map.derived_rows(dev, build_map.FMCDE_PARENT)
    got = {r["id"]: r["row_type"] for r in rows}
    assert got == build_map.EXPECTED_TYPE


def test_sealed_map_is_internally_consistent():
    d = json.loads((EVAL / "sealed_map.json").read_text())
    assert d["verdict"] == "PASS"
    assert d["controls"]["all_ok"]
    p = d["primary"]
    assert p["n_rows"] == build_map.N_PRIMARY == 12
    assert p["mismatches"] == [] and p["n_match"] == p["n_rows"]
    # the verdict must follow from the rows, not from the stored label
    for r in d["holdout"]["rows"]:
        base = r["id"].split("@", 1)[0]
        assert r["expected_type"] == build_map.EXPECTED_TYPE[base]
        assert r["type_match"] == (r["row_type"] == r["expected_type"])
        assert r["type_match"]
