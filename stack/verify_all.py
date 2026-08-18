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

    # L1 for the action/provenance ledgers (their own chains)
    if cfg.get("am_ledger"):
        generic_linkage(cfg["am_ledger"], "am", report)
        am_self_verify(cfg["am_ledger"], report)
    if cfg.get("pm_ledger"):
        generic_linkage(cfg["pm_ledger"], "pm", report)

    # L2 cross-witness — the check only the stack can do (needs `am`)
    if cfg.get("am_ledger"):
        for name, path in cfg["mm_ledgers"].items():
            cross_witness(cfg["am_ledger"], name, path, report)
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
    verdict = "ALL OK" if n_ok == total else "FAILURES PRESENT"
    print(f"=== verdict: {verdict} ({n_ok}/{total}) ===")
    raise SystemExit(0 if n_ok == total else 1)


if __name__ == "__main__":
    main()
