"""⑫h — a declared pre-seal check that records nothing about itself.

The titular half of #47: `pre_seal_checks` is a claim about work, carried inside
the artifact whose purpose is to make claims checkable, and nothing checked it.
Bare names stay valid (they are legitimate for checks with no artifact, and a
FAIL would invalidate every seal already written) — they just WARN now, and a
structured entry gives a later audit something to aggregate.
"""
from __future__ import annotations

import pytest

import measure_mirror.mm as mm


def _lint(**kw):
    pre = {"claim_id": "c", "metric": "acc", "min_n": 200, "baseline": 0.5,
           "pass_threshold": 0.6, "kill_condition": "acc below 0.55",
           "kill_threshold": {"metric": "acc", "threshold": 0.55, "direction": "below"}}
    pre.update(kw)
    return mm._preseal_lint(pre)


def _levels(findings, needle):
    return [f.level for f in findings if needle in f.msg]


# ── lint ─────────────────────────────────────────────────────────────────────

def test_bare_string_check_warns():
    fs = _lint(pre_seal_checks=["neutral-control"])
    assert _levels(fs, "nothing recorded about them") == ["WARN"]


def test_structured_check_does_not_warn():
    fs = _lint(pre_seal_checks=[
        {"name": "neutral-control", "result": "not_fired", "n": 30}])
    assert _levels(fs, "nothing recorded about them") == []
    # still reported as declared
    assert any(f.level == "OK" and "neutral-control" in f.msg for f in fs)


def test_mixed_list_warns_only_about_the_bare_ones():
    fs = _lint(pre_seal_checks=[
        {"name": "neutral-control", "result": "not_fired", "n": 30},
        "reachability-smoke",
    ])
    warn = [f for f in fs if "nothing recorded about them" in f.msg]
    assert len(warn) == 1
    assert "reachability-smoke" in warn[0].msg
    assert "neutral-control" not in warn[0].msg     # the recorded one is not accused


def test_unrecognised_name_still_flagged_when_structured():
    fs = _lint(pre_seal_checks=[{"name": "not-a-known-check", "result": "ok"}])
    assert any("unrecognised" in f.msg and "not-a-known-check" in f.msg for f in fs)


def test_no_checks_still_draws_the_info_nudge():
    fs = _lint()
    assert any(f.level == "INFO" and "declares no pre-seal machine-checks" in f.msg
               for f in fs)


# ── seal time ────────────────────────────────────────────────────────────────

def test_structured_entry_round_trips_through_the_seal(tmp_path):
    led = str(tmp_path / "l.jsonl")
    entry = {"name": "neutral-control", "result": "not_fired", "n": 30,
             "artifact_sha256": "8ddf93" + "0" * 58}
    e = mm.preregister(led, "c", metric="acc", min_n=200, baseline=0.5,
                       pass_threshold=0.6,
                       kill_threshold={"metric": "acc", "threshold": 0.55,
                                       "direction": "below"},
                       pre_seal_checks=[entry, "positive-control"])
    assert e["pre_seal_checks"] == [entry, "positive-control"]   # stored verbatim
    got = mm.declared_pre_seal_checks(led, "c")
    assert [g["name"] for g in got] == ["neutral-control", "positive-control"]
    assert got[0]["result"] == "not_fired" and got[0]["n"] == 30
    assert got[0]["_bare"] is False and got[1]["_bare"] is True


def test_object_entry_without_a_name_is_rejected_at_seal_time(tmp_path):
    # pre-registration is first-write-wins, so a nameless entry could not be
    # corrected under the same claim_id — fail while it can still be fixed.
    led = str(tmp_path / "l.jsonl")
    with pytest.raises(ValueError, match="no 'name'"):
        mm.preregister(led, "c", metric="acc", min_n=200, baseline=0.5,
                       pass_threshold=0.6,
                       pre_seal_checks=[{"result": "not_fired"}])


def test_non_string_non_object_entry_is_rejected(tmp_path):
    led = str(tmp_path / "l.jsonl")
    with pytest.raises(ValueError, match="check name or an object"):
        mm.preregister(led, "c", metric="acc", min_n=200, baseline=0.5,
                       pass_threshold=0.6, pre_seal_checks=[42])


def test_accessor_is_empty_for_unknown_claim(tmp_path):
    assert mm.declared_pre_seal_checks(str(tmp_path / "none.jsonl"), "x") == []


def test_accessor_aggregates_neutral_control_outcomes(tmp_path):
    # the α_eff use case: collect the outcome of every declared neutral control.
    led = str(tmp_path / "l.jsonl")
    for cid, checks in (
        ("a", [{"name": "neutral-control", "result": "not_fired", "n": 30}]),
        ("b", [{"name": "neutral-control", "result": "fired", "n": 30}]),
        ("c", ["neutral-control"]),                       # declared, no outcome
    ):
        mm.preregister(led, cid, metric="acc", min_n=200, baseline=0.5,
                       pass_threshold=0.6, pre_seal_checks=checks)
    outcomes = [e.get("result") for cid in ("a", "b", "c")
                for e in mm.declared_pre_seal_checks(led, cid)
                if e["name"] == "neutral-control"]
    assert outcomes == ["not_fired", "fired", None]       # the third is the gap


# ── the signature is an interface, not a comment ─────────────────────────────
# Everything above proves the BODY takes objects. The type hint said list[str]
# anyway, and every wrapper that derives a schema from it — the mirror-stack-mcp
# server does — rejected the object form at the wire, so the ⑫h advice above was
# unfollowable for MCP callers for as long as it existed. The hint is load-bearing
# for downstream, not documentation. Measured 08-28 ([자생] inbox 0826-145737).

def test_preregister_hint_admits_the_object_form_the_body_accepts():
    import typing
    hint = typing.get_type_hints(mm.preregister)["pre_seal_checks"]
    # list[str | dict] | None  →  the element union must contain dict
    (listish,) = [a for a in typing.get_args(hint) if a is not type(None)]
    (elem,) = typing.get_args(listish)
    assert dict in typing.get_args(elem), hint
