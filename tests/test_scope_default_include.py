"""Scope is default-include, and an exclusion must be a decision someone can overturn.

`stack.json` named four ledgers while seventy-eight sat beside them unverified. The cause was
not a judgement call — the config had a single string slot for the action ledger, so there was
no room for the rest. An exclusion with nobody's name on it has nobody to reverse it, which is
why that scope did not move for twelve days. So: everything in the ledger dir is in scope
unless a *recorded* decision says otherwise, and every such decision carries the condition
under which it must be revisited.
"""
import json
import subprocess
import sys
from pathlib import Path

STACK = Path(__file__).resolve().parent.parent / "stack"


def _run(cfg):
    return subprocess.run([sys.executable, str(STACK / "verify_all.py"), "--config", str(cfg)],
                          capture_output=True, text=True)


def _setup(tmp_path, excluded=None, nochain_has_seal=False):
    led = tmp_path / "led"
    led.mkdir()
    (led / "good.jsonl").write_text('{"prev_seal":"genesis","seal":"a"}\n', encoding="utf-8")
    body = '{"ts":"x","note":"not a chain"}\n'
    if nochain_has_seal:
        body += '{"prev_seal":"genesis","seal":"z"}\n'
    (led / "nochain.jsonl").write_text(body, encoding="utf-8")
    anchors = tmp_path / "anchors"
    anchors.mkdir()
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"mm_ledgers": {}, "anchor_dir": str(anchors),
                               "ledger_dir": str(led), "excluded": excluded or {}}),
                   encoding="utf-8")
    return cfg


FULL = {"reason": "not a hash chain", "decided_by": "[mirror]", "decided_at": "2026-08-19",
        "recheck_if": "any line gains a seal",
        "recheck_probe": {"kind": "any_line_has_key", "key": "seal"}}


def test_undeclared_ledgers_are_swept_in(tmp_path):
    """The default is IN. A ledger nobody mentioned still gets checked."""
    r = _run(_setup(tmp_path, excluded={"nochain.jsonl": FULL}))
    assert "auto-included" in r.stdout
    assert "[L1 chain] good" in r.stdout, "a ledger no config named must still be verified"


def test_scope_denominator_is_printed(tmp_path):
    """A verdict without its denominator is how 78 of 82 stayed invisible."""
    r = _run(_setup(tmp_path, excluded={"nochain.jsonl": FULL}))
    assert "scope:" in r.stdout and "2 ledger(s)" in r.stdout
    assert "1 auto-included" in r.stdout and "1 excluded" in r.stdout


def test_complete_exclusion_is_honoured(tmp_path):
    r = _run(_setup(tmp_path, excluded={"nochain.jsonl": FULL}))
    assert "ALL OK" in r.stdout and r.returncode == 0


def test_unsigned_exclusion_is_refused(tmp_path):
    """An exclusion with no author is the failure this change exists to prevent."""
    partial = {k: v for k, v in FULL.items() if k != "decided_by"}
    r = _run(_setup(tmp_path, excluded={"nochain.jsonl": partial}))
    assert "the exclusion is incomplete" in r.stdout
    assert "missing ['decided_by']" in r.stdout
    assert r.returncode != 0, "an unsigned exclusion must not be silently honoured"


def test_stale_exclusion_fires(tmp_path):
    """When the reason stops being true, the exclusion must not outlive it."""
    r = _run(_setup(tmp_path, excluded={"nochain.jsonl": FULL}, nochain_has_seal=True))
    assert "exclusion is stale" in r.stdout
    assert r.returncode != 0


def test_am_ledger_accepts_a_list(tmp_path):
    """The single-string slot is what left the other ledgers with nowhere to go.

    Exercised through the CLI rather than by importing the module: putting `stack/` on
    `sys.path` inside a test leaks that path into every test that runs after it.
    """
    led = tmp_path / "led"
    led.mkdir()
    for n in ("am1", "am2"):
        (led / f"{n}.jsonl").write_text('{"prev_seal":"genesis","seal":"a"}\n', encoding="utf-8")
    anchors = tmp_path / "anchors"
    anchors.mkdir()
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({
        "mm_ledgers": {}, "anchor_dir": str(anchors),
        "am_ledger": [str(led / "am1.jsonl"), str(led / "am2.jsonl")],
    }), encoding="utf-8")
    r = _run(cfg)
    # Both slots were read: each gets its own tagged linkage line, tagged by FILENAME.
    # The stem is not enough — an auditor searching the output for the ledger they care
    # about types `am1.jsonl`, and `am[am1]` does not contain that string.
    assert "am[am1.jsonl]" in r.stdout and "am[am2.jsonl]" in r.stdout, r.stdout


def test_missing_am_cli_degrades_instead_of_crashing(tmp_path):
    """The module contract promises degradation when `am` is absent. It used to crash.

    `subprocess.run(["am", ...])` raised FileNotFoundError and took the orchestrator down
    with a traceback, so the documented fallback only held on machines that happened to
    have the CLI installed. A skipped layer is printed but never counted as an OK.
    """
    import os
    led = tmp_path / "led"
    led.mkdir()
    (led / "am1.jsonl").write_text('{"prev_seal":"genesis","seal":"a"}\n', encoding="utf-8")
    anchors = tmp_path / "anchors"
    anchors.mkdir()
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"mm_ledgers": {}, "anchor_dir": str(anchors),
                               "am_ledger": str(led / "am1.jsonl")}), encoding="utf-8")
    env = dict(os.environ, PATH=str(tmp_path / "no-such-bin"))   # `am` unreachable
    r = subprocess.run([sys.executable, str(STACK / "verify_all.py"), "--config", str(cfg)],
                       capture_output=True, text=True, env=env)
    assert "Traceback" not in r.stderr, r.stderr
    assert "not installed" in r.stdout
    assert "verdict:" in r.stdout, "it must still reach a verdict, not die on the way"


# ── a ledger's identity is its path, never its filename ──────────────────────
# Reported 2026-08-26 by a sibling project that tested it in a copy first: declaring a
# ledger that lives OUTSIDE the swept directory did not add it to the audit — it *replaced*
# the same-named file inside, because `covered` held basenames and the sweep skipped by name.
# One config change silently swapped 11 audited entries for 62 unaudited ones and the reader
# saw a number that went up. The scope line was complicit: it counted names, so two distinct
# files reported as one `declared`.

def _seal_file(path, n, tag):
    """n chain-linked entries, so linkage passes and the count is identifiable."""
    import hashlib
    prev = "genesis"
    with open(path, "w", encoding="utf-8") as f:
        for i in range(n):
            e = {"claim_id": f"{tag}{i}", "prev_seal": prev}
            e["seal"] = hashlib.sha256(json.dumps(e, sort_keys=True).encode()).hexdigest()
            prev = e["seal"]
            f.write(json.dumps(e) + "\n")


def _collision_cfg(tmp_path, declare_outside):
    """A ledger dir with `dup.jsonl` inside, and another `dup.jsonl` one level up."""
    d = tmp_path / "ledgers"
    d.mkdir(exist_ok=True)          # called twice per test: same tree, two configs
    _seal_file(d / "dup.jsonl", 3, "inside")
    _seal_file(d / "other.jsonl", 2, "other")
    _seal_file(tmp_path / "dup.jsonl", 7, "outside")
    cfg = {"mm_ledgers": {}, "am_ledger": None, "pm_ledger": None,
           "anchor_dir": str(d), "ledger_dir": str(d)}
    if declare_outside:
        cfg["mm_ledgers"]["stray"] = str(tmp_path / "dup.jsonl")
    p = tmp_path / "stack.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return p


def test_declaring_an_outside_ledger_adds_it_without_dropping_the_inside_one(tmp_path):
    """The regression itself: both files must be checked, not one swapped for the other."""
    base = _run(_collision_cfg(tmp_path, declare_outside=False)).stdout
    out = _run(_collision_cfg(tmp_path, declare_outside=True)).stdout
    assert "3 entries" in base and "7 entries" not in base, base
    assert "3 entries" in out, "the inside ledger vanished when a same-named one was declared"
    assert "7 entries" in out, "the declared outside ledger was never checked"


def test_auto_included_count_does_not_shrink_when_a_same_named_file_is_declared(tmp_path):
    """The number a reader actually looks at. It went 85 → 84 in the reported incident."""
    import re
    def swept(cfg):
        m = re.search(r"(\d+) auto-included", _run(cfg).stdout)
        assert m, "scope line lost its auto-included count"
        return int(m.group(1))
    assert swept(_collision_cfg(tmp_path, False)) == swept(_collision_cfg(tmp_path, True))


def test_a_shared_filename_is_reported(tmp_path):
    """Legal, but a verdict about one file says nothing about the other — so say it."""
    out = _run(_collision_cfg(tmp_path, declare_outside=True)).stdout
    assert "same filename, different files" in out, out


def test_the_collision_notice_does_not_count_as_a_failed_check(tmp_path):
    """⊖ It is a hazard to point at, not a check that failed. `report()` folds anything
    non-OK into the verdict, so routing this through it would turn a healthy stack red."""
    import re
    out = _run(_collision_cfg(tmp_path, declare_outside=True)).stdout
    m = re.search(r"verdict: (\w+[\w ]*) \((\d+)/(\d+)\)", out)
    assert m, out
    assert m.group(2) == m.group(3), f"the notice was counted as a failure: {m.group(0)}"


def test_no_collision_notice_when_names_are_unique(tmp_path):
    """⊖ Negative control: the notice must not fire on an ordinary tree."""
    d = tmp_path / "ledgers"; d.mkdir()
    _seal_file(d / "a.jsonl", 2, "a")
    _seal_file(d / "b.jsonl", 2, "b")
    cfg = tmp_path / "stack.json"
    cfg.write_text(json.dumps({"mm_ledgers": {"a": str(d / "a.jsonl")}, "am_ledger": None,
                               "pm_ledger": None, "anchor_dir": str(d),
                               "ledger_dir": str(d)}), encoding="utf-8")
    assert "same filename" not in _run(cfg).stdout


def test_scope_line_names_files_not_filenames(tmp_path):
    """`N declared` must be countable back to distinct files, or it repeats the same error
    one level up: two paths sharing a name would print as one entry."""
    out = _run(_collision_cfg(tmp_path, declare_outside=True)).stdout
    assert str(tmp_path / "dup.jsonl") in out, "scope line does not identify the declared file"
