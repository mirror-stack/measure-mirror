#!/usr/bin/env python3
"""㉘ mutant↔clause correspondence map — decompose aggregate detection.

WHY THIS EXISTS
---------------
Seal `5c78e503` (substrate-2 generalization KILL, 0.80) exposed a structural
blindness in how ㉘ judgments were reported: the aggregate CASE_ACCURACY could
not be decomposed into "planted defect ↔ the clause that caught it" rows, so a
pass could not be told apart from substrate luck — `relabeled_dof` had passed
22/22 on FM×CDE only because the shuffled arm happened not to beat the null
there. The mutation-testing literature (arXiv 2607.08028 via the yeoul lane
memo) treats exactly this correspondence as the basic unit of verifier
coverage, and treats "the planted fault did not actually change behavior"
(the equivalent mutant) as a known trap that must be screened for.

THE UNIT OF THIS MAP
--------------------
For every planted layer-A negative whose honest parent is recoverable, run the
UNMODIFIED auditor on both the mutant and its parent and diff the finding
profiles.  A clause CATCHES a mutant only when both hold:

  satisfied       the mutant's emitted level meets the case's expectation
                  (same semantics as eval/subspace_planted/score.py),
  level_changed   the clause's level-set on the mutant differs from the
                  parent's — the catch is visible to a consumer, who reads
                  levels only, and
  detail_changed  the clause's (level, message) pairs differ — the auditor
                  internally distinguished the mutant even if the level
                  saturated.

Each expected clause is then typed:

  ATTRIBUTED        satisfied ∧ level_changed — the planted defect, not the
                    substrate, made the clause fire.  The unit `5c78e503`
                    could not produce.
  DOMINATED         satisfied ∧ ¬level_changed ∧ detail_changed — the parent
                    is already condemned at the same level, so the lie cannot
                    improve the verdict.  The catch carries no VALIDATION
                    weight for the clause (the row-level form of score.py's
                    CONSTANT rule, and of `5c78e503`'s constant
                    `estimation-eval-overlap` on substrate-2), but the defect
                    demonstrably changed the finding's reason — it is NOT an
                    equivalent mutant.  Two known sub-kinds, distinguished in
                    prose not mechanically: condemned-by-design (an honestly
                    declared k grid FAILs `energy-not-matched` anyway, so the
                    lying declaration is dominated) and condemned-by-accident
                    (substrate-2 carries one real duplicated row, so the
                    parent already FAILs the overlap check).
  CONSTANT_SUSPECT  satisfied ∧ nothing changed at all — the "catch" is
                    indistinguishable from the substrate; validation weight
                    zero and planting suspect.
  UNSAT             the expectation itself is missed (score.py territory).

A mutant whose whole profile — levels AND messages — equals its parent's is
an EQUIVALENT-mutant suspect: the planting failed to change auditor-visible
behavior, so failing to catch it is a planting failure, not an auditor
failure.  This typing is the equivalent-mutant screen, proceduralized.

PARENT RECOVERY
---------------
Every derived mutant in the corpora is a deepcopy-plus-one-edit of a clean
report (`eval/subspace_planted/gen_cases.py`, `eval/subspace_substrate2/
gen_cases_substrate2.py`), so the parent is the clean case in the same corpus
and home.  The two grid-confound cases are a real k-grid table resubmitted
under a lying `grid.kind='energy'` declaration; their parent is the SAME table
with the single lying field undone (`grid = {"kind": "k"}`) — the minimal
honest counterpart, so the diff isolates the lie and nothing else.
Whole-cloth fabrications (`signal_free`) have no honest counterpart; they are
reported in a separate section and never enter the primary metric.

SCOPE
-----
PRIMARY (sealed): the 12 derived mutants of the FM×CDE HELD-OUT homes
(v01, v05 × 6 recipes).  TYPE_MATCH = rows whose row type equals the type
DECLARED PER RECIPE from the spent development home (v04) before the sealed
run, / 12.  Development set = v04 + the substrate-2 corpus, both already
spent by earlier sealed judgments — used to build this tool and freeze the
expected types, carrying no evidential weight.  The vacuous real-run rows
(`eval/subspace_vacuous_real/sealed_result.json`) are re-read as ORGANIC
mutants: their ground-truth relabelling is the equivalent-mutant filter run
form, reported as-is.  NOT claimed: anything about other substrates — this map
decomposes detection within the corpora it covers, nothing more.

Usage:
    python eval/subspace_mutant_map/build_map.py --scope dev,s2 --out dev_map.json
    python eval/subspace_mutant_map/build_map.py --scope all   --out sealed_map.json
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from measure_mirror.mm import subspace_claim_check          # noqa: E402

PLANTED = REPO / "eval" / "subspace_planted"
S2 = REPO / "eval" / "subspace_substrate2"
VACUOUS = REPO / "eval" / "subspace_vacuous_real" / "sealed_result.json"

PROTOCOL_FILES = ("measure_mirror/mm.py",
                  "eval/subspace_mutant_map/build_map.py")
DATA_FILES = ("eval/subspace_planted/cases.jsonl",
              "eval/subspace_planted/cases_holdout.jsonl",
              "eval/subspace_substrate2/cases_substrate2.jsonl",
              "eval/subspace_vacuous_real/sealed_result.json")

BAR_PRIMARY = 1.0
N_PRIMARY = 12

# Parent recovery, sourced line-by-line from the generators (see docstring).
# "clean:<id>" = the clean case's report in the same corpus/home.
# "undo:grid_kind_k" = the mutant's own table with the lying declaration undone.
FMCDE_PARENT = {
    "anchor_stripped": "clean:clean_105",
    "dof_missing": "clean:clean_105",
    "relabeled_dof": "clean:clean_105",
    "estimation_eval_leak": "clean:clean_105",
    "energy_confound": "undo:grid_kind_k",
    "vacuous_as_collapse": "clean:clean_104",
}
S2_PARENT = {
    "s2_anchor_stripped": "clean:s2_clean",
    "s2_dof_missing": "clean:s2_clean",
    "s2_relabeled_dof": "clean:s2_clean",
    "s2_estimation_eval_leak": "clean:s2_clean",
    "s2_saturated": "clean:s2_clean",
    "s2_energy_confound": "undo:grid_kind_k",
}
FABRICATED = {"signal_free"}          # no honest counterpart exists

# PRIMARY expectation, FROZEN from the spent development home (v04) before the
# sealed run: replaying the identical recipes on the held-out homes must land
# every row on the same attribution type.  energy_confound is declared
# DOMINATED, not ATTRIBUTED, because an honestly declared k grid already FAILs
# `energy-not-matched` by design — the lie cannot improve the verdict, so the
# level cannot move; the catch is real but validates nothing about the lie.
EXPECTED_TYPE = {
    "anchor_stripped": "ATTRIBUTED",
    "dof_missing": "ATTRIBUTED",
    "relabeled_dof": "ATTRIBUTED",
    "estimation_eval_leak": "ATTRIBUTED",
    "energy_confound": "DOMINATED",
    "vacuous_as_collapse": "ATTRIBUTED",
}


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def profile(report: dict) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """(levels, details) keyed by clause suffix, each a sorted multiset.
    `levels` is what a consumer gates on; `details` = "level|message" pairs,
    the auditor's full deterministic output, used only to tell DOMINATED from
    CONSTANT_SUSPECT."""
    levels: dict[str, list[str]] = {}
    details: dict[str, list[str]] = {}
    for f in subspace_claim_check(report):
        suffix = f.probe.split(" ", 1)[1] if " " in f.probe else f.probe
        levels.setdefault(suffix, []).append(f.level)
        details.setdefault(suffix, []).append(f"{f.level}|{f.msg}")
    return ({k: sorted(v) for k, v in sorted(levels.items())},
            {k: sorted(v) for k, v in sorted(details.items())})


def satisfied(expect: dict, prof: dict) -> tuple[bool, list[dict]]:
    """score.py semantics, returned per-clause instead of pass/fail only."""
    per_clause = []
    for key, allowed in expect.items():
        if key == "__must_not__":
            for suffix, forbidden in allowed.items():
                actual = prof.get(suffix, [])
                per_clause.append({
                    "clause": suffix, "mode": "must_not",
                    "required": {"forbidden": forbidden}, "emitted": actual,
                    "ok": not any(lv in forbidden for lv in actual)})
            continue
        actual = prof.get(key)
        per_clause.append({
            "clause": key, "mode": "expect",
            "required": {"one_of": allowed}, "emitted": actual or [],
            "ok": actual is not None and any(lv in allowed for lv in actual)})
    return all(c["ok"] for c in per_clause), per_clause


def report_diff(parent: dict, mutant: dict) -> dict:
    """Which top-level fields the planting touched.  `cells` is summarized by
    row counts rather than dumped — the point is the mutation surface."""
    keys = sorted(set(parent) | set(mutant))
    changed, removed, added = [], [], []
    for k in keys:
        if k not in mutant:
            removed.append(k)
        elif k not in parent:
            added.append(k)
        elif json.dumps(parent[k], sort_keys=True) != json.dumps(mutant[k], sort_keys=True):
            changed.append(k)
    out: dict = {"changed": changed, "removed": removed, "added": added}
    if "cells" in changed:
        pc = {json.dumps(c, sort_keys=True) for c in parent.get("cells") or []}
        mc = {json.dumps(c, sort_keys=True) for c in mutant.get("cells") or []}
        out["cells_summary"] = {"parent_only": len(pc - mc),
                                "mutant_only": len(mc - pc),
                                "shared": len(pc & mc)}
    return out


def recover_parent(case: dict, by_id: dict[str, dict], parent_map: dict) -> tuple[dict | None, str]:
    base = case["id"].split("@", 1)[0]
    rule = parent_map.get(base)
    if rule is None:
        return None, "none"
    if rule.startswith("clean:"):
        sfx = "@" + case["id"].split("@", 1)[1] if "@" in case["id"] else ""
        return by_id[rule.split(":", 1)[1] + sfx]["report"], rule
    if rule == "undo:grid_kind_k":
        parent = copy.deepcopy(case["report"])
        parent["grid"] = {"kind": "k"}
        return parent, rule
    raise ValueError(f"unknown parent rule {rule!r}")


def clause_type(c: dict) -> str:
    if not c["ok"]:
        return "UNSAT"
    if c["level_changed"]:
        return "ATTRIBUTED"
    if c["detail_changed"]:
        return "DOMINATED"
    return "CONSTANT_SUSPECT"


ROW_TYPES = ("ATTRIBUTED", "DOMINATED", "CONSTANT_SUSPECT",
             "EQUIVALENT_SUSPECT", "UNSAT")


def row_type(clauses: list[dict], any_change: bool) -> str:
    """Worst clause wins, in the order UNSAT > EQUIVALENT_SUSPECT >
    CONSTANT_SUSPECT > DOMINATED > ATTRIBUTED — a row is only as attributable
    as its weakest expected clause."""
    types = {c["type"] for c in clauses}
    if "UNSAT" in types:
        return "UNSAT"
    if not any_change:
        return "EQUIVALENT_SUSPECT"
    for t in ("CONSTANT_SUSPECT", "DOMINATED"):
        if t in types:
            return t
    return "ATTRIBUTED"


def map_row(case: dict, parent: dict, parent_rule: str) -> dict:
    p_lv, p_dt = profile(parent)
    m_lv, m_dt = profile(case["report"])
    ok, per_clause = satisfied(case["expect"], m_lv)
    all_suffixes = sorted(set(p_lv) | set(m_lv))
    level_changed = [s for s in all_suffixes if p_lv.get(s, []) != m_lv.get(s, [])]
    detail_changed = [s for s in all_suffixes if p_dt.get(s, []) != m_dt.get(s, [])]
    for c in per_clause:
        c["parent_emitted"] = p_lv.get(c["clause"], [])
        c["level_changed"] = c["clause"] in level_changed
        c["detail_changed"] = c["clause"] in detail_changed
        c["type"] = clause_type(c)
    expected_names = {c["clause"] for c in per_clause}
    any_change = bool(detail_changed)          # levels changing implies details
    rt = row_type(per_clause, any_change) if per_clause else (
        "EQUIVALENT_SUSPECT" if not any_change else "ATTRIBUTED")
    return {
        "id": case["id"], "layer": case["layer"], "kind": case["kind"],
        "parent_rule": parent_rule,
        "mutation": case["provenance"].split(". ")[0].split(" — ")[0],
        "mutation_surface": report_diff(parent, case["report"]),
        "clauses": per_clause,
        "side_effect_clauses": {s: {"parent": p_lv.get(s, []),
                                    "mutant": m_lv.get(s, [])}
                                for s in level_changed
                                if s not in expected_names},
        "killed": any_change,
        "equivalent_suspect": not any_change,
        "row_type": rt,
        "parent_profile": p_lv, "mutant_profile": m_lv,
    }


def load_cases(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def derived_rows(cases: list[dict], parent_map: dict) -> list[dict]:
    by_id = {c["id"]: c for c in cases}
    rows = []
    for c in cases:
        if c["kind"] != "negative" or c["layer"] == "B":
            continue
        parent, rule = recover_parent(c, by_id, parent_map)
        if parent is None:
            continue
        rows.append(map_row(c, parent, rule))
    return rows


def fabricated_rows(cases: list[dict]) -> list[dict]:
    """No parent exists, so 'changed vs parent' is undefined.  The honest
    substitute is corpus-level: the expected clause must be satisfied AND must
    not be constant at that level across the corpus's layer-A cases."""
    layer_a = [c for c in cases if c["layer"] != "B"]
    corpus_levels: dict[str, set] = {}
    for c in layer_a:
        for suffix, levels in profile(c["report"])[0].items():
            corpus_levels.setdefault(suffix, set()).update(levels)
    rows = []
    for c in cases:
        if c["id"].split("@", 1)[0] not in FABRICATED:
            continue
        ok, per_clause = satisfied(c["expect"], profile(c["report"])[0])
        for pc in per_clause:
            pc["corpus_levels_seen"] = sorted(corpus_levels.get(pc["clause"], set()))
            pc["non_constant"] = len(pc["corpus_levels_seen"]) > 1
        rows.append({"id": c["id"], "layer": c["layer"],
                     "satisfied": ok, "clauses": per_clause})
    return rows


def mutated_positive_rows(cases: list[dict], parent_map_clean: str) -> list[dict]:
    """Positives that are themselves mutations of the clean report (self_null,
    s2_nogrid, s2_bar_resolves): reported so the map shows the auditor moving
    in BOTH directions, never scored — their scoring lives in score.py."""
    by_id = {c["id"]: c for c in cases}
    rows = []
    for c in cases:
        base = c["id"].split("@", 1)[0]
        if c["kind"] != "positive" or base in ("clean_105", "partial_103",
                                               "clean_104", "s2_clean"):
            continue
        sfx = "@" + c["id"].split("@", 1)[1] if "@" in c["id"] else ""
        parent_id = parent_map_clean + sfx
        if parent_id not in by_id:
            continue
        rows.append(map_row(c, by_id[parent_id]["report"], f"clean:{parent_map_clean}"))
    return rows


# ─────────────────────────────────────────────────────────────
# Controls — the procedure must pass these before any row is readable.
# ─────────────────────────────────────────────────────────────
def run_controls(dev_cases: list[dict], s2_cases: list[dict]) -> dict:
    by_id = {c["id"]: c for c in dev_cases}
    ctrl: dict = {}

    # killed-direction positive control: a deletion the auditor is KNOWN to
    # catch must come out ATTRIBUTED.
    row = map_row(by_id["anchor_stripped"], by_id["clean_105"]["report"],
                  "clean:clean_105")
    ctrl["killed_control"] = {"case": "anchor_stripped(dev)",
                              "row_type": row["row_type"],
                              "ok": row["row_type"] == "ATTRIBUTED"}

    # equivalent-direction positive control: mutate a field the auditor never
    # reads.  If the procedure calls this killed, the differ is broken.
    equiv = copy.deepcopy(by_id["clean_105"]["report"])
    equiv["source"] = "EQUIVALENT-CONTROL: auditor-ignored field edited"
    fake_case = {"id": "equiv_control", "layer": "control", "kind": "negative",
                 "provenance": "clean_105 with only the auditor-ignored "
                               "`source` field edited",
                 "expect": {}, "report": equiv}
    row = map_row(fake_case, by_id["clean_105"]["report"], "clean:clean_105")
    ctrl["equivalent_control"] = {"case": "clean_105+source-edit",
                                  "equivalent_suspect": row["equivalent_suspect"],
                                  "ok": row["equivalent_suspect"]}

    # neutral control: a report run through the FULL row machinery against
    # itself must show zero changed clauses and zero mutation surface — the
    # differ must not manufacture attribution out of nothing.  deepcopy on one
    # side so dict identity cannot short-circuit the comparison.
    self_case = {"id": "neutral_control", "layer": "control", "kind": "negative",
                 "provenance": "clean_105 vs an unmodified deep copy of itself",
                 "expect": {}, "report": copy.deepcopy(by_id["clean_105"]["report"])}
    row = map_row(self_case, by_id["clean_105"]["report"], "clean:clean_105")
    surface = row["mutation_surface"]
    ctrl["neutral_control"] = {
        "case": "clean_105 vs itself",
        "equivalent_suspect": row["equivalent_suspect"],
        "surface_empty": not (surface["changed"] or surface["removed"]
                              or surface["added"]),
        "ok": row["equivalent_suspect"] and not (surface["changed"]
                                                 or surface["removed"]
                                                 or surface["added"])}

    # negative control: sealed 5c78e503 recorded estimation-eval-overlap as
    # CONSTANT on substrate-2 (one eval row is byte-identical to a fit row, so
    # the parent already FAILs at the consumer-visible level).  The map must
    # reproduce that catch as carrying no validation weight — the row must NOT
    # come out ATTRIBUTED; if it does, the differ is lying.
    s2_by_id = {c["id"]: c for c in s2_cases}
    leak_parent, rule = recover_parent(s2_by_id["s2_estimation_eval_leak"],
                                       s2_by_id, S2_PARENT)
    row = map_row(s2_by_id["s2_estimation_eval_leak"], leak_parent, rule)
    ctrl["s2_dominated_control"] = {
        "case": "s2_estimation_eval_leak",
        "clause": "estimation-eval-overlap",
        "row_type": row["row_type"],
        "ok": row["row_type"] != "ATTRIBUTED"}

    ctrl["all_ok"] = all(v["ok"] for v in ctrl.values() if isinstance(v, dict))
    return ctrl


def vacuous_organic_summary(path: Path) -> dict:
    """Re-read the sealed vacuous run as organic mutants: sloppy rows whose
    ground-truth margin shows the manipulation did not bite are EQUIVALENT
    mutants caught by the run-time relabelling — the same filter, run form."""
    d = json.loads(path.read_text())
    rows = d["rows"]
    out: dict = {"seal": "2a22a95a", "per_condition": {}}
    for proc in ("honest", "sloppy"):
        for n in d["config"]["n_list"]:
            sub = [r for r in rows if r["proc"] == proc and r["n_fit"] == n]
            out["per_condition"][f"{proc}@{n}"] = {
                "runs": len(sub),
                "killed": sum(r["truth"] == "unmatched" for r in sub),
                "equivalent": sum(r["truth"] == "matched" for r in sub),
                "withheld_boundary": sum(r["truth"] == "boundary" for r in sub),
                "caught_by": "vacuous" if proc == "sloppy" else None,
            }
    sloppy = [r for r in rows if r["proc"] == "sloppy"]
    out["sloppy_total"] = {
        "runs": len(sloppy),
        "killed": sum(r["truth"] == "unmatched" for r in sloppy),
        "equivalent": sum(r["truth"] == "matched" for r in sloppy),
        "withheld_boundary": sum(r["truth"] == "boundary" for r in sloppy)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", default="dev,s2",
                    help="comma set from {dev,s2,holdout,vacuous} or 'all'. "
                         "The sealed run uses 'all'; development must not "
                         "pass 'holdout'.")
    ap.add_argument("--out", required=True)
    ap.add_argument("--print-sha", action="store_true")
    args = ap.parse_args()
    scope = ({"dev", "s2", "holdout", "vacuous"} if args.scope == "all"
             else set(args.scope.split(",")))

    sha = {"protocol": {f: sha256_of(REPO / f) for f in PROTOCOL_FILES},
           "data": {f: sha256_of(REPO / f) for f in DATA_FILES}}
    sha["combined"] = hashlib.sha256(json.dumps(sha, sort_keys=True).encode()).hexdigest()
    if args.print_sha:
        print(json.dumps(sha, indent=2))
        return 0

    dev_cases = load_cases(PLANTED / "cases.jsonl")
    s2_cases = load_cases(S2 / "cases_substrate2.jsonl")

    out: dict = {"sha256": sha, "scope": sorted(scope),
                 "bars": {"primary_type_match_min": BAR_PRIMARY,
                          "n_primary_rows": N_PRIMARY, "chance": 0.0},
                 "env": {"python": sys.version.split()[0],
                         "platform": platform.platform()}}

    out["controls"] = run_controls(dev_cases, s2_cases)

    if "dev" in scope:
        out["dev"] = {"rows": derived_rows(dev_cases, FMCDE_PARENT),
                      "fabricated": fabricated_rows(dev_cases),
                      "mutated_positives": mutated_positive_rows(dev_cases, "clean_105")}
    if "s2" in scope:
        out["s2"] = {"rows": derived_rows(s2_cases, S2_PARENT),
                     "fabricated": fabricated_rows(s2_cases),
                     "mutated_positives": mutated_positive_rows(s2_cases, "s2_clean")}
    if "holdout" in scope:
        hold_cases = load_cases(PLANTED / "cases_holdout.jsonl")
        rows = derived_rows(hold_cases, FMCDE_PARENT)
        for r in rows:
            base = r["id"].split("@", 1)[0]
            r["expected_type"] = EXPECTED_TYPE[base]
            r["type_match"] = r["row_type"] == r["expected_type"]
        n_match = sum(r["type_match"] for r in rows)
        out["holdout"] = {
            "rows": rows,
            "fabricated": fabricated_rows(hold_cases),
            "mutated_positives": mutated_positive_rows(hold_cases, "clean_105")}
        out["primary"] = {
            "TYPE_MATCH": (n_match / len(rows)) if rows else None,
            "n_match": n_match, "n_rows": len(rows),
            "expected_types": EXPECTED_TYPE,
            "mismatches": [{"id": r["id"], "expected": r["expected_type"],
                            "got": r["row_type"]}
                           for r in rows if not r["type_match"]]}
        if not out["controls"]["all_ok"]:
            verdict = "INVALID_control"
        elif len(rows) != N_PRIMARY:
            verdict = "INVALID_row_census"
        elif n_match < len(rows) * BAR_PRIMARY:
            verdict = "KILL_type_mismatch"
        else:
            verdict = "PASS"
        out["verdict"] = verdict
    if "vacuous" in scope:
        out["vacuous_organic"] = vacuous_organic_summary(VACUOUS)

    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    brief = {k: out[k] for k in ("scope", "bars") if k in out}
    brief["controls_all_ok"] = out["controls"]["all_ok"]
    for k in ("primary", "verdict"):
        if k in out:
            brief[k] = out[k]
    print(json.dumps(brief, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
