"""P1 — falsifiability_check auto-resolution: a kill-condition should be evaluated
from a *sealed* resolution (retraction / am_record) without hand-feeding reported_acc.
Unresolved claims keep the current WARN; an explicit reported_acc still wins.
"""
import json

import measure_mirror.mm as mm


def _prereg(led):
    mm.preregister(str(led), "c1", metric="acc", min_n=10, baseline=0.5, pass_threshold=0.6,
                   kill_threshold={"metric": "acc", "threshold": 0.55, "direction": "below"})


def _append(path, obj):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj) + "\n")


def test_unresolved_keeps_warn(tmp_path):
    led = tmp_path / "l.jsonl"
    _prereg(led)
    f = mm.falsifiability_check(str(led), "c1")
    assert f.level == "WARN"                                   # nothing sealed → current behaviour


def test_recover_numeric_result_from_am_record(tmp_path):
    led, am = tmp_path / "l.jsonl", tmp_path / "am.jsonl"
    _prereg(led)
    _append(am, {"_type": "action", "target": "c1", "payload": {"reported_acc": 0.40}})
    f = mm.falsifiability_check(str(led), "c1", am_ledger=str(am))
    assert f.level == "FAIL" and "auto-recovered" in f.msg     # 0.40 < 0.55 → kill fired


def test_recover_kill_verdict(tmp_path):
    led, am = tmp_path / "l.jsonl", tmp_path / "am.jsonl"
    _prereg(led)
    _append(am, {"_type": "action", "target": "c1", "action": "VERDICT c1 = KILL",
                 "payload": {"verdict": "KILL"}})
    assert mm.falsifiability_check(str(led), "c1", am_ledger=str(am)).level == "FAIL"


def test_recover_pass_verdict(tmp_path):
    led, am = tmp_path / "l.jsonl", tmp_path / "am.jsonl"
    _prereg(led)
    _append(am, {"_type": "action", "target": "c1", "payload": {"verdict": "PASS"}})
    assert mm.falsifiability_check(str(led), "c1", am_ledger=str(am)).level == "OK"


def test_sealed_retraction_is_resolved_negative(tmp_path):
    led = tmp_path / "l.jsonl"
    _prereg(led)
    _append(led, {"_type": "retraction", "claim_id": "c1", "reason": "kill fired"})
    f = mm.falsifiability_check(str(led), "c1")
    assert f.level == "FAIL" and "RETRACTED" in f.msg


def test_explicit_reported_acc_overrides_recovery(tmp_path):
    led, am = tmp_path / "l.jsonl", tmp_path / "am.jsonl"
    _prereg(led)
    _append(am, {"_type": "action", "target": "c1", "payload": {"reported_acc": 0.40}})  # would FAIL
    f = mm.falsifiability_check(str(led), "c1", reported_acc=0.90, am_ledger=str(am))
    assert f.level == "OK"                                     # explicit 0.90 wins, kill not tripped


def test_co_located_action_in_claims_ledger(tmp_path):
    # actions sometimes live in the same file as the prereg — recovery must see them too.
    led = tmp_path / "l.jsonl"
    _prereg(led)
    _append(led, {"_type": "action", "target": "c1", "payload": {"verdict": "KILL"}})
    assert mm.falsifiability_check(str(led), "c1").level == "FAIL"


def test_unknown_verdict_falls_through_to_warn(tmp_path):
    led, am = tmp_path / "l.jsonl", tmp_path / "am.jsonl"
    _prereg(led)
    _append(am, {"_type": "action", "target": "c1", "payload": {"verdict": "PENDING_REVIEW"}})
    assert mm.falsifiability_check(str(led), "c1", am_ledger=str(am)).level == "WARN"


# ── P2 — where a resolution is allowed to live ───────────────────────────────
# Real ledgers record the same fact in more than one shape: under a non-ASCII
# payload key, or in the action sentence only. A resolution the auditor cannot
# see reads as "never resolved", which silently inflates the unresolved count.

def test_recover_from_korean_payload_keys(tmp_path):
    for key, label, level in (("판정", "KILL", "FAIL"), ("결과", "PASS", "OK")):
        led, am = tmp_path / f"l_{key}.jsonl", tmp_path / f"am_{key}.jsonl"
        _prereg(led)
        _append(am, {"_type": "action", "target": "c1", "payload": {key: label}})
        assert mm.falsifiability_check(str(led), "c1", am_ledger=str(am)).level == level


def test_recover_from_action_text_without_payload_verdict(tmp_path):
    for text, level in (
        ("verdict real_granularity_sweep: KILL(delta +0.091 < 0.15)", "FAIL"),
        ("M7c 판정: 🔴KILL_DISPERSION_FRAGILE", "FAIL"),
        ("c1 결과=PASS(scope=verbatim regime): 5 kill 전부 미발동", "OK"),
    ):
        led, am = tmp_path / "l.jsonl", tmp_path / "am.jsonl"
        led.unlink(missing_ok=True), am.unlink(missing_ok=True)
        _prereg(led)
        _append(am, {"_type": "action", "target": "c1", "action": text, "payload": {}})
        assert mm.falsifiability_check(str(led), "c1", am_ledger=str(am)).level == level


def test_headline_verdict_wins_when_a_sentence_names_two(tmp_path):
    # "KILL … · monotone PASS" is one killed claim with a passing sub-metric,
    # not a pass. First match wins, so the headline is what gets recovered.
    led, am = tmp_path / "l.jsonl", tmp_path / "am.jsonl"
    _prereg(led)
    _append(am, {"_type": "action", "target": "c1", "payload": {},
                 "action": "verdict c1: KILL(delta +0.091 < 0.15) · monotone PASS · ctrl 0.745"})
    assert mm.falsifiability_check(str(led), "c1", am_ledger=str(am)).level == "FAIL"


def test_recovery_scans_a_sequence_of_ledgers(tmp_path):
    # A project's claims routinely span many ledger files; requiring the caller to
    # concatenate them is what forced the private-function workaround.
    led = tmp_path / "claims.jsonl"
    other, hit = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    _prereg(led)
    _append(other, {"_type": "action", "target": "unrelated", "payload": {"verdict": "PASS"}})
    _append(hit, {"_type": "action", "target": "c1", "payload": {"verdict": "KILL"}})
    f = mm.falsifiability_check(str(led), "c1", am_ledger=[str(other), str(hit)])
    assert f.level == "FAIL"


def test_public_name_is_exported_and_private_alias_still_works(tmp_path):
    import measure_mirror as m
    assert "recover_resolution" in m.__all__ and hasattr(m, "recover_resolution")
    led = tmp_path / "l.jsonl"
    _prereg(led)
    _append(led, {"_type": "action", "target": "c1", "payload": {"verdict": "KILL"}})
    assert m.recover_resolution(str(led), "c1") == ("verdict", "KILL")
    assert mm._recover_resolution(str(led), "c1") == ("verdict", "KILL")   # pre-0.34 callers
