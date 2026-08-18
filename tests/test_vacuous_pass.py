"""A verifier that checked nothing must not report a pass.

`verdict = "ALL OK" if n_ok == len(results)` is `0 == 0` when no check ran, so an empty
config printed `ALL OK (0/0)` and exited 0 — true only because nothing could falsify it
(a *vacuous pass*, the failure mode `vacuity detection` names in formal verification).
The verdict line and the exit code are what automation and readers act on, so both must
distinguish "everything passed" from "nothing was measured".
"""
import json
import subprocess
import sys
from pathlib import Path

STACK = Path(__file__).resolve().parent.parent / "stack"


def _run(script, *args):
    return subprocess.run([sys.executable, str(STACK / script), *args],
                          capture_output=True, text=True)


def test_empty_config_is_not_a_pass(tmp_path):
    cfg = tmp_path / "empty.json"
    cfg.write_text(json.dumps({"mm_ledgers": {}}), encoding="utf-8")
    r = _run("verify_all.py", "--config", str(cfg))
    assert "ALL OK" not in r.stdout, "an empty declaration must never read as a pass"
    assert "NOTHING VERIFIED" in r.stdout
    assert r.returncode != 0, "exit 0 would let `verify && publish` proceed on no evidence"


def test_real_config_still_passes(tmp_path):
    """The guard must not break the normal green path (regression on the fix itself)."""
    led = tmp_path / "l.jsonl"
    led.write_text('{"prev_seal":"genesis","seal":"a"}\n', encoding="utf-8")
    anchors = tmp_path / "anchors"
    anchors.mkdir()
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"mm_ledgers": {"x": str(led)}, "anchor_dir": str(anchors)}),
                   encoding="utf-8")
    r = _run("verify_all.py", "--config", str(cfg))
    assert "NOTHING VERIFIED" not in r.stdout
    assert "verdict:" in r.stdout


def test_seal_check_reports_its_denominator(tmp_path):
    """"seals valid" without a count cannot be told apart from "no seals to check"."""
    led = STACK / "evidence" / "compute_governor.jsonl"      # real seals, so the OK path runs
    anchors = tmp_path / "anchors"
    anchors.mkdir()
    r = _run("verify_self.py", str(led), str(anchors))
    assert "seals valid" in r.stdout
    assert "entries checked" in r.stdout, "a green line must carry the number it verified"
