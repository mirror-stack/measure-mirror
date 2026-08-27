"""A verdict has to say what it covered — by name, and about layers that never ran.

Two defects, both found in use, both the same shape: the output could not be mapped
back to what was actually checked.

1. A layer that was asked for but could not run (the `am` CLI absent) printed a WARN
   and was correctly left out of the count — and then the run still said `ALL OK` and
   exited 0. Three layers could vanish while the verdict and the exit code both said
   everything was fine.

2. Declared ledgers were labelled by role (`am`), not by file. A ledger named
   `am.jsonl` sat in the same directory, so three L1 lines read `am` while two of them
   were a different file. An auditor grepping the output for `seara.jsonl` found zero
   lines and reported it unverified; it had been verified all along, under another name.
   Their count of unique labels happened to equal the file count on disk, which made the
   wrong set look complete — a count is not a set.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

STACK = Path(__file__).resolve().parent.parent / "stack"


def _run(cfg, *args, env=None):
    return subprocess.run([sys.executable, str(STACK / "verify_all.py"),
                           "--config", str(cfg), *args],
                          capture_output=True, text=True, env=env)


def _env_without_am():
    """A PATH with no `am` on it — the environment of anyone who did not install it."""
    env = dict(os.environ)
    keep = [d for d in env.get("PATH", "").split(os.pathsep)
            if d and not (Path(d) / "am").exists()]
    env["PATH"] = os.pathsep.join(keep)
    return env


def _setup(tmp_path, real_am_chain=False):
    """One declared am ledger, plus a decoy ledger whose stem equals the role name.

    `am.jsonl` is the whole point: it is a real ledger that a directory sweep picks up,
    and its label collided with the role label of whatever the config declared.
    """
    led = tmp_path / "led"
    led.mkdir()
    linkage_only = '{"prev_seal":"genesis","seal":"a"}\n'
    family = led / "family.jsonl"
    if real_am_chain:
        # Let the tool build its own chain, so `am verify` has real seals to check.
        subprocess.run(["am", "--ledger", str(family), "record",
                        "--agent", "t", "--action", "x"], capture_output=True, check=True)
    else:
        family.write_text(linkage_only, encoding="utf-8")
    (led / "claims.jsonl").write_text(linkage_only, encoding="utf-8")
    (led / "am.jsonl").write_text(linkage_only, encoding="utf-8")   # decoy
    anchors = tmp_path / "anchors"
    anchors.mkdir()
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({
        "mm_ledgers": {},
        "am_ledger": str(family),
        "anchor_dir": str(anchors),
        "ledger_dir": str(led),
    }), encoding="utf-8")
    return cfg


# ─── 1. a layer that did not run must not read as a pass ─────────────────

def test_skipped_layer_is_not_all_ok(tmp_path):
    r = _run(_setup(tmp_path), env=_env_without_am())
    assert "ALL OK" not in r.stdout, "layers that never ran must not be certified"
    assert "PARTIAL" in r.stdout
    assert "did not run:" in r.stdout, "say WHICH layer, not just that something is missing"


def test_skipped_layer_reaches_the_exit_code(tmp_path):
    """`verify_all && publish` must not proceed on a run that skipped a layer."""
    r = _run(_setup(tmp_path), env=_env_without_am())
    assert r.returncode != 0, "exit 0 is what automation reads; PARTIAL has to reach it"


def test_allow_partial_is_an_explicit_opt_in(tmp_path):
    """Knowingly running without `am` stays possible — but you have to say so."""
    r = _run(_setup(tmp_path), "--allow-partial", env=_env_without_am())
    assert r.returncode == 0
    assert "PARTIAL" in r.stdout, "the escape hatch changes the exit code, not the truth"


def test_full_environment_still_passes(tmp_path):
    """Regression on the fix itself: with everything available this is still a clean pass."""
    if shutil.which("am") is None:
        import pytest
        pytest.skip("`am` CLI not installed — the green path cannot be exercised here")
    r = _run(_setup(tmp_path, real_am_chain=True))
    assert "PARTIAL" not in r.stdout and "ALL OK" in r.stdout
    assert r.returncode == 0


# ─── 2. the output has to name the file it checked ───────────────────────

def test_declared_ledger_is_labelled_by_file(tmp_path):
    """Grepping the output for the ledger's filename must find it."""
    r = _run(_setup(tmp_path), "--allow-partial", env=_env_without_am())
    assert "family.jsonl" in r.stdout, (
        "a declared ledger that appears only under its role name cannot be audited: "
        "searching for the file returns nothing and reads as 'never checked'")


def test_role_label_does_not_collide_with_a_same_named_ledger(tmp_path):
    """`am` the role and `am.jsonl` the file must not print the same label.

    Repeated labels are fine — one ledger gets several checks. What must not happen is
    two DIFFERENT ledgers answering to one label, because then a failure names a file
    that is not the one that failed.
    """
    r = _run(_setup(tmp_path), "--allow-partial", env=_env_without_am())
    labels = {line.split("]", 1)[1].split(":", 1)[0].strip()
              for line in r.stdout.splitlines() if "[L1 chain]" in line}
    assert labels, "no L1 lines at all — the test is measuring nothing"
    # three distinct ledgers were checked: family (declared), claims and am.jsonl (swept)
    assert len(labels) == 3, f"3 ledgers were checked but they answer to {len(labels)} label(s): {labels}"
    assert "am" in labels, "the swept am.jsonl should still be labelled by its own stem"
    assert "am[family.jsonl]" in labels, "the declared ledger must carry its filename"


def test_scope_line_names_the_declared_ledgers(tmp_path):
    """A count is not a set — 'N declared' must say WHICH N.

    Updated 2026-08-26 to require the full PATH rather than the bare filename. The original
    defect here was labelling by role (`am`) so an auditor grepping for `seara.jsonl` found
    nothing; a path still contains the filename, so that grep keeps working. What the bare
    name could not do is tell two files apart: `<ledger_dir>/x.jsonl` and `/elsewhere/x.jsonl`
    both printed as `x.jsonl`, and `N declared` counted them as one. Same failure one level
    up — a name is not an identity.
    """
    cfg = _setup(tmp_path)
    conf = json.loads(cfg.read_text(encoding="utf-8"))
    declared = [p for p in (list((conf.get("mm_ledgers") or {}).values())
                            + [conf.get("am_ledger"), conf.get("pm_ledger")]) if p]
    assert len(declared) == 1, f"fixture changed — expected one declared ledger, got {declared}"
    path = os.path.realpath(declared[0])
    r = _run(cfg, "--allow-partial", env=_env_without_am())
    scope = [l for l in r.stdout.splitlines() if l.startswith("--- scope:")]
    assert scope, "no scope line"
    assert "1 declared" in scope[0], f"'N declared' count missing: {scope[0]}"
    assert "family.jsonl" in scope[0], (
        f"an auditor greps for the filename — it must survive: {scope[0]}")
    assert path in scope[0], (
        f"'N declared' has to identify the FILE, not just its name: {scope[0]}")
