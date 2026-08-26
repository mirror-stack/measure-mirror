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


def _am(args):
    """Run the `am` CLI, or report that it is absent instead of dying.

    The module contract says an uninstalled `am` degrades the stack to measure-mirror's
    own self-verification. It did not: `subprocess.run(["am", ...])` raised
    FileNotFoundError and took the whole orchestrator down with a traceback — a promise
    of graceful degradation that only held where the tool happened to be installed.
    """
    try:
        return subprocess.run(args, capture_output=True, text=True)
    except FileNotFoundError:
        return None


def cross_witness(am_ledger, peer_name, peer_path, report, skipped=None):
    r = _am(["am", "--ledger", am_ledger, "verify-peer", "--name", peer_name, peer_path])
    if r is None:
        # Skipped, not passed: printed (so it is visible) but never counted as an OK —
        # and recorded, so the verdict line can say the run was only partial.
        print(f"{WARN} [L2 witness] {peer_name}: skipped — the `am` CLI is not installed; "
              f"this run says nothing about the cross-witness layer")
        if skipped is not None:
            skipped.append(f"L2 witness/{peer_name} (the `am` CLI is not installed)")
        return
    out = (r.stdout or r.stderr).strip().replace("\n", " | ")
    ok = r.returncode == 0 and ("OK" in out or "✅" in out or "consistent" in out.lower())
    report(OK if ok else FAIL, "L2 witness", peer_name, out)


def am_self_verify(am_ledger, report, tag="am", skipped=None):
    r = _am(["am", "--ledger", am_ledger, "verify"])
    if r is None:
        print(f"{WARN} [L1 chain] {tag}: `am verify` skipped — the `am` CLI is not installed "
              f"(the format-agnostic linkage check above still ran)")
        if skipped is not None:
            skipped.append(f"L1 chain/{tag} seal-verify (the `am` CLI is not installed)")
        return
    ok = r.returncode == 0 and "OK" in r.stdout
    report(OK if ok else FAIL, "L1 chain", tag,
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


def ledger_id(p):
    """A ledger's identity is its RESOLVED PATH, never its filename.

    This used to be the basename, and that made two different files with the same name
    indistinguishable to the audit. Reported 2026-08-26: one project's ledger existed as
    `/data/seara/mm_reason_ledger.jsonl` (62 sealed entries, never audited) *and* as
    `<ledger_dir>/mm_reason_ledger.jsonl` (11 entries, audited). Declaring the first in the
    config did not add it — the sweep then skipped the second because the *name* matched, so
    the run swapped one file for the other and the witness layer went red. Worse, the scope
    line counted names, so `N declared` reported two distinct files as one and a reader
    could not tell that half the evidence was outside.
    """
    return str(Path(p).resolve())


def name_collisions(declared, swept_paths):
    """Two distinct files sharing a filename is a scope hazard, so say it out loud.

    Not a failure: it is legal to have `<dir>/x.jsonl` and `/elsewhere/x.jsonl`. What is not
    legal is for a verdict to be read as covering both when it covers one. Reporting it is
    what keeps `N declared` from quietly meaning `N names`.
    """
    by_name = {}
    for src, paths in (("declared", declared), ("swept", swept_paths)):
        for p in paths:
            rp = ledger_id(p)
            by_name.setdefault(Path(rp).name, set()).add(rp)
    hits = {n: sorted(v) for n, v in by_name.items() if len(v) > 1}
    # Printed, never counted: `report()` folds anything that is not OK into the verdict, and
    # a shared filename is a hazard to point at, not a failed check. Same convention as the
    # exclusion notices below.
    for n, paths in sorted(hits.items()):
        print(f"{WARN} [scope] {n}: same filename, different files — a verdict about one says "
              f"nothing about the other: " + " | ".join(paths))
    return hits


def sweep_ledger_dir(cfg, already, report):
    """Default-include: every ledger in the directory is in scope unless excluded ON PURPOSE.

    Returns (n_found, included_names, excluded_names). Prints the denominator, because a
    verdict without one cannot be told apart from a verdict over nothing.

    `already` holds resolved PATHS (see `ledger_id`), not names.
    """
    root = cfg.get("ledger_dir")
    if not root:
        return 0, [], []
    excluded = cfg.get("excluded", {}) or {}
    found = sorted(Path(root).glob("*.jsonl"))
    included, skipped = [], []
    for lp in found:
        if ledger_id(lp) in already:      # the same FILE, not merely the same name
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
    ap.add_argument("--allow-partial", action="store_true",
                    help="exit 0 even when a layer could not run (the verdict still says "
                         "PARTIAL). For runs that knowingly lack the `am` CLI.")
    args = ap.parse_args()
    cfg = DEFAULT_CONFIG if not args.config else json.loads(Path(args.config).read_text())
    results, could_not_run = [], []

    def report(level, layer, name, msg):
        results.append(level == OK)
        print(f"{level} [{layer}] {name}: {msg}")

    print("=== Mirror Stack verify-all (orchestrator) ===")

    # L1 + L3 for each mm claims ledger — measure-mirror's own self-verification
    for name, path in cfg["mm_ledgers"].items():
        verify_self(path, cfg["anchor_dir"], report)

    # L1 for the action/provenance ledgers (their own chains). Both slots accept a list.
    # The label carries the FILE, always. `am` alone named whichever ledger the config
    # happened to declare — and a ledger literally called `am.jsonl` sat in the same
    # directory, so three L1 lines read `am` while two of them were a different file
    # (3,700 entries) from the third (1 entry). A failure line would have accused the
    # wrong ledger, and an auditor grepping for the filename found nothing at all.
    am_ledgers, pm_ledgers = _as_list(cfg.get("am_ledger")), _as_list(cfg.get("pm_ledger"))
    for led in am_ledgers:
        tag = f"am[{Path(led).name}]"
        generic_linkage(led, tag, report)
        am_self_verify(led, report, tag=tag, skipped=could_not_run)
    for led in pm_ledgers:
        tag = f"pm[{Path(led).name}]"
        generic_linkage(led, tag, report)

    # Default-include sweep: anything in the ledger dir that no one excluded on purpose.
    declared_paths = list(cfg["mm_ledgers"].values()) + am_ledgers + pm_ledgers
    covered = {ledger_id(p) for p in declared_paths}
    n_found, swept, skipped = sweep_ledger_dir(cfg, covered, report)
    root = cfg.get("ledger_dir")
    swept_paths = [str(Path(root) / n) for n in swept] if root else []
    collisions = name_collisions(declared_paths, swept_paths)

    # L2 cross-witness — the check only the stack can do (needs `am`)
    if am_ledgers:
        for name, path in cfg["mm_ledgers"].items():
            cross_witness(am_ledgers[0], name, path, report, skipped=could_not_run)
    elif cfg["mm_ledgers"]:
        print(f"{WARN} [L2 witness] (skipped) — no witness ledger configured; stack degrades to "
              "measure-mirror self-verify (case-study witness ledger is private, see honesty box)")
        could_not_run.append("L2 witness (no witness ledger configured)")

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
        # Name the declared ones too: a count is not a set. An auditor counted unique L1
        # labels, got a number that happened to equal the file count, and read the scope as
        # full — while two declared ledgers were absent from it under different labels.
        print(f"--- scope: {n_found} ledger(s) in {cfg['ledger_dir']} · "
              f"{len(covered)} declared ({', '.join(sorted(covered))}) · "
              f"{len(swept)} auto-included · {len(skipped)} excluded ---")

    if n_ok != total:
        verdict, code = "FAILURES PRESENT", 1
    elif could_not_run:
        # Everything that RAN passed — but a layer that was asked for never ran, so this
        # run cannot support "the stack verifies". A green exit here is the failure this
        # whole tool is about: what was not looked at reads as a pass.
        verdict, code = "PARTIAL", (0 if args.allow_partial else 3)
    else:
        verdict, code = "ALL OK", 0

    print(f"=== verdict: {verdict} ({n_ok}/{total}) ===")
    for layer in could_not_run:
        print(f"    did not run: {layer}")
    if could_not_run:
        print(f"    {len(could_not_run)} layer(s) did not run — this verdict does not cover them"
              + ("  [--allow-partial: exiting 0 anyway]" if args.allow_partial else ""))
    raise SystemExit(code)


if __name__ == "__main__":
    main()
