#!/usr/bin/env python3
"""🪞🔎🪪 Mirror Stack verify-all — the STACK ORCHESTRATOR.

This is the layer *above* any single mirror: it coordinates the three mirrors and adds the
one check that no single mirror can do alone — cross-witness between ledgers.

  L1 self-chain    + L3 external anchor : delegated to verify_self (measure-mirror's own job)
  L2 cross-witness : witness ledger's pinned heads vs claims ledger's actual history (via `am`)

Dependency note (intentional, unlike measure-mirror's zero-dep core): L2 requires the
action-mirror CLI (`am`) to be installed. Without it, L2 is skipped and reported as such —
the stack degrades to the self-verification that measure-mirror provides on its own.

Philosophy: this does not prevent dishonesty — it makes only honesty provable.
Sealed preregistrations and time-pinned witnesses cannot be fabricated retroactively.

Default config verifies the bundled evidence/. The witness (L2) ledger from the case study is
a private family ledger and is not bundled. usage: verify_all.py [--config stack.json]
"""
import argparse
import json
import subprocess
from pathlib import Path

from verify_self import OK, FAIL, WARN, generic_linkage, verify_self

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = {
    "mm_ledgers": {"compute_governor_mm": str(HERE / "evidence/compute_governor.jsonl")},
    "am_ledger": None,
    "pm_ledger": None,
    "anchor_dir": str(HERE / "evidence"),
}


def cross_witness(am_ledger, peer_name, peer_path, report):
    r = subprocess.run(["am", "--ledger", am_ledger, "verify-peer",
                        "--name", peer_name, peer_path],
                       capture_output=True, text=True)
    out = (r.stdout or r.stderr).strip().replace("\n", " | ")
    ok = r.returncode == 0 and ("OK" in out or "✅" in out or "consistent" in out.lower())
    report(OK if ok else FAIL, "L2 witness", peer_name, out)


def am_self_verify(am_ledger, report):
    r = subprocess.run(["am", "--ledger", am_ledger, "verify"], capture_output=True, text=True)
    ok = r.returncode == 0 and "OK" in r.stdout
    report(OK if ok else FAIL, "L1 chain", "am",
           "am verify: " + (r.stdout.strip().splitlines()[-1] if r.stdout else r.stderr.strip()))


REQUIRED_EXCLUSION_FIELDS = ("reason", "decided_by", "decided_at", "recheck_if")


def _as_list(v):
    """A config slot that was a single string could only ever hold ONE ledger.
    That is how ledgers ended up outside the scope: not by a decision, but by
    there being no room for them. Both forms are accepted now."""
    if not v:
        return []
    return list(v) if isinstance(v, (list, tuple)) else [v]


def _recheck_fired(path, probe):
    """Is an exclusion's own revisit-condition now true?

    An exclusion with a reason is an exclusion someone CHOSE. An exclusion with a
    machine-checkable revisit-condition is one that cannot quietly outlive its reason
    — which is the failure this whole change is about.
    """
    if not probe:
        return None
    kind = probe.get("kind")
    if kind == "any_line_has_key":
        key = probe["key"]
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                if key in json.loads(line):
                    return f"a line now has `{key}` — the reason for excluding it no longer holds"
            except Exception:
                continue
        return None
    return f"unknown recheck probe kind {kind!r} — cannot be checked, treat as unverified"


def sweep_ledger_dir(cfg, already, report):
    """Default-include: every ledger in the directory is in scope unless excluded ON PURPOSE.

    Returns (n_found, included_names, excluded_names). Prints the denominator, because a
    verdict without one cannot be told apart from a verdict over nothing.
    """
    root = cfg.get("ledger_dir")
    if not root:
        return 0, [], []
    excluded = cfg.get("excluded", {}) or {}
    found = sorted(Path(root).glob("*.jsonl"))
    included, skipped = [], []
    for lp in found:
        if lp.name in already:
            continue
        rec = excluded.get(lp.name)
        if rec is None:
            generic_linkage(str(lp), lp.stem, report)
            included.append(lp.name)
            continue
        missing = [f for f in REQUIRED_EXCLUSION_FIELDS if not rec.get(f)]
        if missing:
            # An exclusion nobody signed is the thing that started this: it has no author,
            # so it has nobody to overturn it. Refuse to honour it silently.
            report(FAIL, "scope", lp.name,
                   f"excluded but the exclusion is incomplete — missing {missing}")
            continue
        fired = _recheck_fired(lp, rec.get("recheck_probe"))
        if fired:
            report(FAIL, "scope", lp.name, f"exclusion is stale: {fired} (recheck_if: {rec['recheck_if']})")
            continue
        skipped.append(lp.name)
        print(f"{WARN} [scope] {lp.name}: excluded by {rec['decided_by']} on {rec['decided_at']} "
              f"— {rec['reason']} · revisit when: {rec['recheck_if']}")
    return len(found), included, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    args = ap.parse_args()
    cfg = DEFAULT_CONFIG if not args.config else json.loads(Path(args.config).read_text())
    results = []

    def report(level, layer, name, msg):
        results.append(level == OK)
        print(f"{level} [{layer}] {name}: {msg}")

    print("=== Mirror Stack verify-all (orchestrator) ===")

    # L1 + L3 for each mm claims ledger — measure-mirror's own self-verification
    for name, path in cfg["mm_ledgers"].items():
        verify_self(path, cfg["anchor_dir"], report)

    # L1 for the action/provenance ledgers (their own chains). Both slots accept a list.
    am_ledgers, pm_ledgers = _as_list(cfg.get("am_ledger")), _as_list(cfg.get("pm_ledger"))
    for i, led in enumerate(am_ledgers):
        tag = "am" if len(am_ledgers) == 1 else f"am[{Path(led).stem}]"
        generic_linkage(led, tag, report)
        am_self_verify(led, report)
    for led in pm_ledgers:
        tag = "pm" if len(pm_ledgers) == 1 else f"pm[{Path(led).stem}]"
        generic_linkage(led, tag, report)

    # Default-include sweep: anything in the ledger dir that no one excluded on purpose.
    covered = {Path(p).name for p in list(cfg["mm_ledgers"].values()) + am_ledgers + pm_ledgers}
    n_found, swept, skipped = sweep_ledger_dir(cfg, covered, report)

    # L2 cross-witness — the check only the stack can do (needs `am`)
    if am_ledgers:
        for name, path in cfg["mm_ledgers"].items():
            cross_witness(am_ledgers[0], name, path, report)
    else:
        print(f"{WARN} [L2 witness] (skipped) — no witness ledger configured; stack degrades to "
              "measure-mirror self-verify (case-study witness ledger is private, see honesty box)")

    n_ok, total = sum(results), len(results)
    if not total:
        # A config that declares nothing must NOT read as a pass. `n_ok == len(results)`
        # is 0 == 0 on an empty run, so the old line printed ALL OK (0/0) and exited 0 —
        # a *vacuous pass*: true only because there was nothing to falsify it. Callers
        # chaining on `&&`, and humans reading the verdict line, could not see it.
        print(f"=== verdict: NOTHING VERIFIED (0/0) — no ledger was checked ===")
        print(f"    the config declares no ledger this orchestrator can read; "
              f"a green verdict here would certify nothing.")
        raise SystemExit(2)
    if cfg.get("ledger_dir"):
        # State the denominator next to the verdict. "ALL OK" over a scope nobody printed
        # is how 78 of 82 ledgers stayed unverified for twelve days without anyone noticing.
        print(f"--- scope: {n_found} ledger(s) in {cfg['ledger_dir']} · "
              f"{len(covered)} declared · {len(swept)} auto-included · {len(skipped)} excluded ---")
    verdict = "ALL OK" if n_ok == total else "FAILURES PRESENT"
    print(f"=== verdict: {verdict} ({n_ok}/{total}) ===")
    raise SystemExit(0 if n_ok == total else 1)


if __name__ == "__main__":
    main()
