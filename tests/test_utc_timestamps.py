"""Every timestamp this library seals is UTC with an explicit 'Z'.

`preregister`, `retract` and the judge log wrote local wall-clock with no
timezone marker, while anchors in the same module — and the sibling action /
provenance ledgers — wrote UTC+Z. Entries from the two families sat on
different clocks and nothing in the string said which.

That breaks the audit a hash-chained ledger is uniquely able to answer: did the
seal exist before the result did? On a real ledger the naive comparison put
28 of 28 claims out of order ("sealed after the result was known"); normalising
the clocks flipped it to 28 of 28 correct. The wrong direction accuses the
author of peeking, so this is a regression worth pinning.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import measure_mirror.mm as mm

# 2026-08-15T00:11:02Z — trailing Z required, no offset form accepted.
UTC_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _entries(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def test_helper_shape_and_value():
    ts = mm._utc_now()
    assert UTC_Z.match(ts), ts
    parsed = datetime.fromisoformat(ts[:-1]).replace(tzinfo=timezone.utc)
    delta = abs((datetime.now(timezone.utc) - parsed).total_seconds())
    assert delta < 120, f"helper is not on UTC: off by {delta}s"


def test_preregister_seals_utc(tmp_path):
    led = str(tmp_path / "l.jsonl")
    e = mm.preregister(led, "c", metric="acc", min_n=200, baseline=0.5,
                       pass_threshold=0.6,
                       kill_threshold={"metric": "acc", "threshold": 0.55,
                                       "direction": "below"})
    assert UTC_Z.match(e["ts"]), e["ts"]


def test_retract_seals_utc(tmp_path):
    led = str(tmp_path / "l.jsonl")
    mm.preregister(led, "c", metric="acc", min_n=200, baseline=0.5,
                   pass_threshold=0.6)
    mm.retract(led, "c", reason="superseded")
    retraction = [e for e in _entries(led) if e.get("_type") == "retraction"]
    assert retraction and UTC_Z.match(retraction[0]["ts"])


def test_every_written_entry_carries_a_utc_timestamp(tmp_path):
    # Whatever an entry's _type, if it has a ts the library wrote, it is UTC.
    led = str(tmp_path / "l.jsonl")
    mm.preregister(led, "a", metric="acc", min_n=200, baseline=0.5,
                   pass_threshold=0.6)
    mm.preregister(led, "b", metric="acc", min_n=200, baseline=0.5,
                   pass_threshold=0.6)
    mm.retract(led, "a", reason="x")
    stamped = [e for e in _entries(led) if "ts" in e]
    assert len(stamped) == 3
    offenders = [(e.get("_type", "prereg"), e["ts"])
                 for e in stamped if not UTC_Z.match(e["ts"])]
    assert not offenders, f"non-UTC timestamps written: {offenders}"


def test_ordering_survives_across_entry_kinds(tmp_path):
    # The property the fix exists for: timestamps from different writers are
    # comparable as plain strings, so seal-before-result is checkable.
    led = str(tmp_path / "l.jsonl")
    mm.preregister(led, "c", metric="acc", min_n=200, baseline=0.5,
                   pass_threshold=0.6)
    mm.retract(led, "c", reason="x")
    ts = [e["ts"] for e in _entries(led) if "ts" in e]
    assert ts == sorted(ts), f"lexicographic order broken: {ts}"


def test_module_has_no_naive_strftime_left():
    # The three call sites this fixes were easy to reintroduce by copy-paste.
    # Parse rather than grep: the first version of this guard matched the old
    # format string quoted inside _utc_now's own docstring and failed on
    # documentation. A substring guard cannot tell code from prose.
    import ast
    import inspect

    from measure_mirror import judge

    offenders = []
    for mod in (mm, judge):
        tree = ast.parse(inspect.getsource(mod))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if not (isinstance(fn, ast.Attribute) and fn.attr == "strftime"):
                continue
            fmt = node.args[0] if node.args else None
            if isinstance(fmt, ast.Constant) and isinstance(fmt.value, str):
                # A bare format with no zone marker, and no gmtime() second arg,
                # is local wall-clock passed off as a timestamp.
                if "Z" not in fmt.value and "%z" not in fmt.value:
                    offenders.append((mod.__name__, fmt.value))
    assert not offenders, (
        f"timezone-less timestamps written: {offenders} — use _utc_now()")
