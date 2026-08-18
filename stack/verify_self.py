#!/usr/bin/env python3
"""🪞 verify-self — verify ONE measure-mirror claims ledger + its external anchors.

This is the measure-mirror layer of verification: it needs nothing but this repo.
  L1 self-chain     : prev_seal→seal linkage (format-agnostic) + mm native seal verification
  L3 external anchor : stored snapshots vs current ledger — intact / extended / REPLACED?

Zero external-tool dependency by design — no `am`, no subprocess, no other mirror.
Cross-witness (L2) lives one layer up, in the stack orchestrator (verify_all.py), because
witnessing is *between* mirrors and is not measure-mirror's job.

usage: verify_self.py LEDGER.jsonl [ANCHOR_DIR]   (defaults to bundled evidence/)
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OK, FAIL, WARN = "✅", "❌", "⚠️"


def load_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def generic_linkage(path, name, report):
    """Format-agnostic prev_seal→seal linkage check (works on any mirror ledger).

    Thin adapter over the single source `measure_mirror.mm.linkage_check` — the
    same algorithm the outsider `mirror-stack-verify` CLI uses, so the two cannot
    drift (an empty or malformed ledger is reported, not crashed). Returns the
    parsed entries (or None when unreadable) so the caller can gate seal-verify.
    """
    sys.path.insert(0, str(HERE.parent))
    from measure_mirror.mm import linkage_check
    ok, msg, entries = linkage_check(path)
    report(OK if ok else FAIL, "L1 chain", name, msg)
    return entries


def mm_self_verify(path, name, report):
    """Recompute mm seals via the measure_mirror package (same repo, zero-dep core)."""
    try:
        sys.path.insert(0, str(HERE.parent))
        from measure_mirror.mm import verify_chain
        findings = verify_chain(str(path))
        bad = [f for f in findings if getattr(f, "level", "OK") not in ("OK", "INFO")]
        if bad:
            report(FAIL, "L1 chain", name, f"mm verify_chain: {[str(f) for f in bad]}")
        else:
            # Report the DENOMINATOR, not just the colour: "seals valid" over zero entries
            # is the same vacuous pass the verdict-line guard blocks one level up.
            n = len(load_jsonl(path))
            report(OK, "L1 chain", name, f"mm verify_chain: seals valid ({n} entries checked)")
    except Exception as e:
        report(WARN, "L1 chain", name, f"mm lib unavailable, linkage-only ({e})")


def anchor_check(anchor_file, report):
    a = json.loads(Path(anchor_file).read_text())
    lp = Path(a["ledger_path"])
    if not lp.exists():  # bundled evidence: fall back to a copy next to the anchor
        lp = Path(anchor_file).parent / lp.name
    name = f"{Path(anchor_file).name}→{lp.name}"
    if not lp.exists():
        report(FAIL, "L3 anchor", name, "ledger missing")
        return
    cur = hashlib.sha256(lp.read_bytes()).hexdigest()
    if cur == a["anchor_hash"]:
        report(OK, "L3 anchor", name, f"intact (unchanged since {a['ts']})")
        return
    entries = load_jsonl(lp)
    n = a["entry_count"]
    if len(entries) >= n and str(entries[n - 1].get("seal", "")) == a["head_seal"]:
        report(OK, "L3 anchor", name,
               f"extended ({n}→{len(entries)} entries, anchored head still in chain)")
    else:
        report(FAIL, "L3 anchor", name,
               "REPLACED? anchored head_seal not found at anchored position")


def verify_self(ledger, anchor_dir, report):
    """Run L1+L3 for a single mm ledger. Returns nothing; appends via report()."""
    if generic_linkage(ledger, Path(ledger).stem, report) is not None:
        mm_self_verify(ledger, Path(ledger).stem, report)
    for f in sorted(Path(anchor_dir).glob("anchor_*.json")):
        anchor_check(f, report)


def main():
    ledger = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "evidence/compute_governor.jsonl")
    anchor_dir = sys.argv[2] if len(sys.argv) > 2 else str(HERE / "evidence")
    results = []

    def report(level, layer, name, msg):
        results.append(level == OK)
        print(f"{level} [{layer}] {name}: {msg}")

    print("=== verify-self (measure-mirror: L1 chain + L3 anchors) ===")
    verify_self(ledger, anchor_dir, report)
    n_ok, total = sum(results), len(results)
    if not total:
        # Same guard as verify_all.py. Not reachable from this CLI today (generic_linkage
        # always reports), but the bare `n_ok == len(results)` is the shape that let a
        # vacuous pass through one layer up — pin it here so a refactor cannot reopen it.
        print(f"=== verdict: NOTHING VERIFIED (0/0) — no check ran ===")
        sys.exit(2)
    verdict = "ALL OK" if n_ok == total else "FAILURES PRESENT"
    print(f"=== verdict: {verdict} ({n_ok}/{total}) ===")
    sys.exit(0 if n_ok == total else 1)


if __name__ == "__main__":
    main()
