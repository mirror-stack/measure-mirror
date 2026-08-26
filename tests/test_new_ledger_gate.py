# -*- coding: utf-8 -*-
"""Creating a ledger has to be said out loud; appending to one does not.

`--ledger` defaults to a RELATIVE path, so a mistyped name or the wrong working
directory silently starts a second ledger that is indistinguishable, on disk, from one
someone meant to create. Measured 2026-08-26 in the authors' own ledger directory: 92
ledger files against 4 named by the audit configuration; two lanes had seals in a file
named `mm_ledger.jsonl` — this default's own filename — and 62 seals belonging to a
third lane's declared ledger sat outside the audited directory entirely. Every integrity
check was green throughout: the chains were intact, they were simply in the wrong file,
and nothing checked placement.

The gate is therefore narrow on purpose. Appending is untouched; only creation asks.
Tests below pin both halves, because a gate that also blocks appends would be a far worse
bug than the one it fixes, and it would show up in every existing user's workflow.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from measure_mirror import mm  # noqa: E402

REGISTER = ["register", "c1", "--metric", "acc", "--min-n", "10",
            "--baseline", "0.5", "--pass", "0.6", "--kill", "acc<0.5"]


def _run(monkeypatch, argv):
    """Drive the real CLI entry point; return its exit code (0 when it does not raise)."""
    monkeypatch.setattr(sys, "argv", ["mm"] + argv)
    try:
        mm._cli()
    except SystemExit as e:
        return e.code if e.code is not None else 0
    return 0


def _seal_one(path):
    mm.preregister(path, "seed", metric="acc", min_n=10, baseline=0.5,
                   pass_threshold=0.6, kill_condition="acc<0.5",
                   kill_threshold={"metric": "acc", "threshold": 0.5, "direction": "below"})


# ── creation is gated ────────────────────────────────────────────────────────
def test_missing_ledger_is_refused(monkeypatch, tmp_path, capsys):
    led = str(tmp_path / "new.jsonl")
    assert _run(monkeypatch, ["--ledger", led] + REGISTER) == 2
    assert not os.path.exists(led), "refused but created the file anyway"


def test_the_refusal_names_the_absolute_path_and_the_flag(monkeypatch, tmp_path, capsys):
    """"No such file" is useless when the failure mode is not knowing which directory
    you are in — so the message has to carry the resolved path and the exact fix."""
    led = str(tmp_path / "new.jsonl")
    _run(monkeypatch, ["--ledger", led] + REGISTER)
    err = capsys.readouterr().err
    assert os.path.abspath(led) in err
    assert "--new-ledger" in err


@pytest.mark.parametrize("cmd", sorted(mm.LEDGER_WRITERS))
def test_every_writing_subcommand_is_gated(monkeypatch, tmp_path, cmd):
    """Parametrised over the module's own set, so adding a writer without gating it fails
    here rather than shipping an un-gated path."""
    led = str(tmp_path / f"{cmd}.jsonl")
    argv = {"register": REGISTER,
            "retract": ["retract", "c1", "--reason", "r"],
            "run": ["run", "c1", "--", "true"]}[cmd]
    assert _run(monkeypatch, ["--ledger", led] + argv) == 2, f"{cmd} was not gated"
    assert not os.path.exists(led)


# ── appending is NOT gated (the half that must not regress) ──────────────────
def test_existing_ledger_needs_no_flag(monkeypatch, tmp_path):
    led = str(tmp_path / "have.jsonl")
    _seal_one(led)
    assert _run(monkeypatch, ["--ledger", led] + REGISTER) == 0
    rows = [json.loads(l) for l in open(led, encoding="utf-8") if l.strip()]
    assert len(rows) == 2
    assert rows[1]["prev_seal"] == rows[0]["seal"], "the gate broke the chain"


def test_flag_creates_the_ledger(monkeypatch, tmp_path):
    led = str(tmp_path / "new.jsonl")
    assert _run(monkeypatch, ["--ledger", led, "--new-ledger"] + REGISTER) == 0
    assert os.path.exists(led)


def test_flag_on_an_existing_ledger_is_a_no_op(monkeypatch, tmp_path):
    """Passing it habitually (a script, an alias) must not become a second behaviour."""
    led = str(tmp_path / "have.jsonl")
    _seal_one(led)
    assert _run(monkeypatch, ["--ledger", led, "--new-ledger"] + REGISTER) == 0
    assert len([l for l in open(led, encoding="utf-8") if l.strip()]) == 2


def test_an_empty_but_existing_ledger_is_not_creation(monkeypatch, tmp_path):
    """`touch ledger.jsonl` is a deliberate act; the file is there, so appending proceeds."""
    led = tmp_path / "empty.jsonl"
    led.write_text("", encoding="utf-8")
    assert _run(monkeypatch, ["--ledger", str(led)] + REGISTER) == 0


# ── reads are untouched ──────────────────────────────────────────────────────
@pytest.mark.parametrize("cmd", ["anchor", "calibrate"])
def test_reading_subcommands_are_not_gated(monkeypatch, tmp_path, cmd):
    led = str(tmp_path / "absent.jsonl")
    assert _run(monkeypatch, ["--ledger", led, cmd]) != 2


# ── flag position (argparse puts top-level options before the subcommand) ────
@pytest.mark.parametrize("place", ["before", "after"])
def test_flag_works_on_either_side_of_the_subcommand(monkeypatch, tmp_path, place):
    """This is the one flag a first-time user is forced to type; both readings of the
    command line have to work, or the fix produces a second confusing error."""
    led = str(tmp_path / f"{place}.jsonl")
    argv = (["--ledger", led, "--new-ledger"] + REGISTER if place == "before"
            else ["--ledger", led] + REGISTER[:2] + ["--new-ledger"] + REGISTER[2:])
    assert _run(monkeypatch, argv) == 0, f"--new-ledger {place} the subcommand failed"
    assert os.path.exists(led)


def test_the_subparser_default_does_not_erase_the_top_level_flag(monkeypatch, tmp_path):
    """⊕ Regression control for the argparse trap this fix had to dodge.

    Declaring the same option on both the main parser and a subparser makes the subparser
    write its own default over the value already parsed — so `mm --new-ledger register`
    would come out False and the flag would appear to work while doing nothing. The
    subparser therefore declares `default=argparse.SUPPRESS`. If someone replaces that
    with `default=False`, this test fails and the next two do not.
    """
    led = str(tmp_path / "trap.jsonl")
    monkeypatch.setattr(sys, "argv", ["mm", "--ledger", led, "--new-ledger"] + REGISTER)
    captured = {}
    real = mm.preregister

    def spy(path, *a, **k):
        captured["called"] = True
        return real(path, *a, **k)

    monkeypatch.setattr(mm, "preregister", spy)
    try:
        mm._cli()
    except SystemExit as e:
        pytest.fail(f"top-level --new-ledger was erased by the subparser default (exit {e.code})")
    assert captured.get("called"), "the write never happened"


# ── the set itself ───────────────────────────────────────────────────────────
def test_writers_are_a_subset_of_the_known_subcommands():
    """A typo in LEDGER_WRITERS would gate nothing and no other test would notice:
    `args.cmd in {"regsiter"}` is simply always false."""
    known = {"register", "audit", "calibrate", "run", "anchor", "retract",
             "negative", "judge", "certify", "verify"}
    assert mm.LEDGER_WRITERS <= known, mm.LEDGER_WRITERS - known


def test_the_gate_can_actually_fire_and_actually_pass(monkeypatch, tmp_path):
    """⊕/⊖ control in one: the same command must be refused and accepted under the only
    difference that should matter. A gate observed only failing, or only passing, is not
    known to be reading its condition."""
    led = str(tmp_path / "ctl.jsonl")
    refused = _run(monkeypatch, ["--ledger", led] + REGISTER)
    accepted = _run(monkeypatch, ["--ledger", led, "--new-ledger"] + REGISTER)
    assert (refused, accepted) == (2, 0)
