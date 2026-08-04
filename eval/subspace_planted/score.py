#!/usr/bin/env python3
"""G2 — two-directional scoring of ㉘ subspace_claim_check against the planted set.

A planted NEGATIVE that the probe lets through is a FALSE NEGATIVE.
A planted POSITIVE that the probe fails is a FALSE POSITIVE.
Kill condition: FP ≥ 1 or FN ≥ 1 among the layer-A cases.

Layer-B cases are reported separately and are NOT part of the kill condition —
`overfit_smallsample` is a property of the estimation run, which layer A never
sees. Counting it as a layer-A catch would be an over-claim.

Deterministic: no RNG, no clock, no network. Same cases.jsonl + same mm.py ⇒
same verdict.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from measure_mirror import subspace_claim_check          # noqa: E402

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases.jsonl"


def levels_by_suffix(findings) -> dict:
    out = {}
    for f in findings:
        # probe labels look like "㉘ null-ladder"; key on the part after the symbol
        suffix = f.probe.split(" ", 1)[1] if " " in f.probe else f.probe
        out.setdefault(suffix, []).append(f.level)
    return out


def score_case(case: dict) -> dict:
    findings = subspace_claim_check(case["report"])
    got = levels_by_suffix(findings)
    mismatches = []

    for key, allowed in case["expect"].items():
        if key == "__must_not__":
            for suffix, forbidden in allowed.items():
                actual = got.get(suffix, [])
                bad = [lv for lv in actual if lv in forbidden]
                if bad:
                    mismatches.append(
                        f"{suffix}: emitted {bad} which is forbidden ({forbidden})")
            continue
        actual = got.get(key)
        if actual is None:
            mismatches.append(f"{key}: no finding emitted (expected one of {allowed})")
        elif not any(lv in allowed for lv in actual):
            mismatches.append(f"{key}: got {actual}, expected one of {allowed}")

    return {"id": case["id"], "kind": case["kind"], "layer": case["layer"],
            "ok": not mismatches, "mismatches": mismatches,
            "levels": {k: v for k, v in sorted(got.items())}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=str(CASES),
                    help="path to a cases jsonl (default: the development set)")
    args = ap.parse_args()
    path = Path(args.cases)
    print(f"  scoring: {path.name}")
    cases = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    results = [score_case(c) for c in cases]

    layer_a = [r for r in results if r["layer"] != "B"]
    layer_b = [r for r in results if r["layer"] == "B"]

    fp = [r for r in layer_a if r["kind"] == "positive" and not r["ok"]]
    fn = [r for r in layer_a if r["kind"] == "negative" and not r["ok"]]

    print("═══ layer A (kill condition applies) ═══")
    for r in layer_a:
        mark = "✅" if r["ok"] else ("🔴 FP" if r["kind"] == "positive" else "🔴 FN")
        print(f"  {mark:6} [{r['layer']:9}] {r['id']}")
        for m in r["mismatches"]:
            print(f"           ✗ {m}")

    print("\n═══ layer B (reported, NOT in the kill condition) ═══")
    for r in layer_b:
        print(f"  {'✅' if r['ok'] else '⚠️ '}     [{r['layer']:9}] {r['id']}")
        for m in r["mismatches"]:
            print(f"           ✗ {m}")

    # ── discriminative-power gate ────────────────────────────────────────
    # Learned from the KILL of seal 98e993b2: `energy-not-matched` emitted FAIL
    # on ALL EIGHT grid-carrying cases. A constant catches every planted
    # negative for free, so its "pass" carried no information. A finding that
    # gates a planted negative must emit at least two distinct levels across
    # the layer-A set, or its passes are vacuous.
    gating = set()
    for c in cases:
        if c["layer"] == "B" or c["kind"] != "negative":
            continue
        for key, val in c["expect"].items():
            gating.update(val.keys()) if key == "__must_not__" else gating.add(key)
    constant = {}
    for suffix in sorted(gating):
        seen = {lv for r in layer_a for lv in r["levels"].get(suffix, [])}
        if len(seen) == 1:
            constant[suffix] = sorted(seen)

    n_pos = sum(r["kind"] == "positive" for r in layer_a)
    n_neg = sum(r["kind"] == "negative" for r in layer_a)
    print(f"\n═══ discriminative power (findings that gate a planted negative) ═══")
    for suffix in sorted(gating):
        seen = sorted({lv for r in layer_a for lv in r["levels"].get(suffix, [])})
        mark = "🔴 CONSTANT" if len(seen) == 1 else "✅"
        print(f"  {mark:12} {suffix:26} levels seen: {seen}")

    print(f"\n  layer A: {n_pos} positive · {n_neg} negative")
    print(f"  FP = {len(fp)}   FN = {len(fn)}   constant-findings = {len(constant)}")
    verdict = "PASS" if not fp and not fn and not constant else "KILL"
    print(f"  VERDICT: {verdict}")

    (path.parent / f"score_output_{path.stem}.json").write_text(
        json.dumps({"verdict": verdict, "fp": len(fp), "fn": len(fn),
                    "constant_findings": constant,
                    "n_positive": n_pos, "n_negative": n_neg,
                    "results": results}, ensure_ascii=False, indent=2))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
