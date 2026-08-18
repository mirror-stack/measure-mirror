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
    # Both slots were read: each gets its own tagged linkage line.
    assert "am[am1]" in r.stdout and "am[am2]" in r.stdout, r.stdout


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
