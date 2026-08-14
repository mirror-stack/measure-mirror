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


def test_recover_pass_verdict_without_number_warns(tmp_path):
    # #47 result side: a label-only PASS used to return OK. "Not falsified" rested
    # on the label alone — the sealed threshold was never checked against a
    # measurement, which is exactly how inflation happens. Now WARN.
    led, am = tmp_path / "l.jsonl", tmp_path / "am.jsonl"
    _prereg(led)
    _append(am, {"_type": "action", "target": "c1", "payload": {"verdict": "PASS"}})
    f = mm.falsifiability_check(str(led), "c1", am_ledger=str(am))
    assert f.level == "WARN" and "label alone" in f.msg


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
    # label-only PASS → WARN since the #47 result-side change (no gradable number).
    for key, label, level in (("판정", "KILL", "FAIL"), ("결과", "PASS", "WARN")):
        led, am = tmp_path / f"l_{key}.jsonl", tmp_path / f"am_{key}.jsonl"
        _prereg(led)
        _append(am, {"_type": "action", "target": "c1", "payload": {key: label}})
        assert mm.falsifiability_check(str(led), "c1", am_ledger=str(am)).level == level


def test_recover_from_action_text_without_payload_verdict(tmp_path):
    # the PASS row expects WARN since the #47 result-side change: a verdict
    # recovered from prose carries no gradable number by construction.
    for text, level in (
        ("verdict real_granularity_sweep: KILL(delta +0.091 < 0.15)", "FAIL"),
        ("M7c 판정: 🔴KILL_DISPERSION_FRAGILE", "FAIL"),
        ("c1 결과=PASS(scope=verbatim regime): 5 kill 전부 미발동", "WARN"),
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


# ── P3 — the result side of a resolution (#47) ──────────────────────────────
# A verdict is a conclusion; a metric-named number is a measurement. Only the
# second lets the Popper gate re-check the sealed threshold instead of trusting
# the label. Measured before this existed: of 133 resolved-negative claims in
# one real ledger, exactly 1 carried a number falsifiability_check could grade.

def _prereg_named(led):
    mm.preregister(str(led), "c1", metric="separation_d", min_n=10, baseline=0.5,
                   pass_threshold=0.6,
                   kill_threshold={"metric": "separation_d", "threshold": 0.55,
                                   "direction": "below"})


def test_attributed_metric_value_is_graded(tmp_path):
    led, am = tmp_path / "l.jsonl", tmp_path / "am.jsonl"
    _prereg_named(led)
    _append(am, {"_type": "action", "target": "c1",
                 "payload": {"verdict": "KILL", "metric": "separation_d", "value": 0.40}})
    f = mm.falsifiability_check(str(led), "c1", am_ledger=str(am))
    assert f.level == "FAIL" and "its own pre-registered criterion" in f.msg
    assert "recorded for metric 'separation_d'" in f.msg


def test_pass_label_backed_by_its_number_stays_ok(tmp_path):
    led, am = tmp_path / "l.jsonl", tmp_path / "am.jsonl"
    _prereg_named(led)
    _append(am, {"_type": "action", "target": "c1",
                 "payload": {"verdict": "PASS", "metric": "separation_d", "value": 0.72}})
    f = mm.falsifiability_check(str(led), "c1", am_ledger=str(am))
    assert f.level == "OK" and "not triggered" in f.msg


def test_pass_label_contradicted_by_its_own_number_fails(tmp_path):
    # numeric wins over label: a PASS whose own recorded number trips the sealed
    # bar is a falsified claim wearing a passing label.
    led, am = tmp_path / "l.jsonl", tmp_path / "am.jsonl"
    _prereg_named(led)
    _append(am, {"_type": "action", "target": "c1",
                 "payload": {"verdict": "PASS", "metric": "separation_d", "value": 0.40}})
    assert mm.falsifiability_check(str(led), "c1", am_ledger=str(am)).level == "FAIL"


def test_number_of_a_different_metric_is_not_graded(tmp_path):
    # 0.40 is explicitly a measurement of runtime_s. Grading it against the
    # separation_d threshold would be a misrecovery — worse than no recovery.
    # The claim resolves by its label instead: a PASS with no gradable number.
    led, am = tmp_path / "l.jsonl", tmp_path / "am.jsonl"
    _prereg_named(led)
    _append(am, {"_type": "action", "target": "c1",
                 "payload": {"verdict": "PASS", "metric": "runtime_s", "value": 0.40}})
    f = mm.falsifiability_check(str(led), "c1", am_ledger=str(am))
    assert f.level == "WARN" and "label alone" in f.msg


def test_payload_key_named_like_the_sealed_metric_is_recovered(tmp_path):
    # "separation_d" is not in _RESULT_KEYS — it is found because the seal names it.
    led, am = tmp_path / "l.jsonl", tmp_path / "am.jsonl"
    _prereg_named(led)
    _append(am, {"_type": "action", "target": "c1",
                 "payload": {"separation_d": 0.40}})
    f = mm.falsifiability_check(str(led), "c1", am_ledger=str(am))
    assert f.level == "FAIL" and "recorded for metric 'separation_d'" in f.msg


def test_similar_key_is_not_a_match(tmp_path):
    # exact-after-trim only — no substring, no separator folding; both have
    # produced measured false positives. separation_d_v2 ≠ separation_d.
    led, am = tmp_path / "l.jsonl", tmp_path / "am.jsonl"
    _prereg_named(led)
    _append(am, {"_type": "action", "target": "c1",
                 "payload": {"verdict": "PASS", "separation_d_v2": 0.40}})
    f = mm.falsifiability_check(str(led), "c1", am_ledger=str(am))
    assert f.level == "WARN" and "label alone" in f.msg


def test_bare_number_is_graded_but_says_assumed(tmp_path):
    # A bare result key still grades (compat), but the note is honest that the
    # number's quantity is assumed, not recorded.
    led, am = tmp_path / "l.jsonl", tmp_path / "am.jsonl"
    _prereg_named(led)
    _append(am, {"_type": "action", "target": "c1", "payload": {"reported_acc": 0.40}})
    f = mm.falsifiability_check(str(led), "c1", am_ledger=str(am))
    assert f.level == "FAIL" and "assumed to be 'separation_d'" in f.msg


def test_recover_resolution_metric_kwarg_public(tmp_path):
    import measure_mirror as m
    led = tmp_path / "l.jsonl"
    _prereg_named(led)
    _append(led, {"_type": "action", "target": "c1", "payload": {"separation_d": 0.40}})
    # without metric= there is nothing to find: not a generic result key, no verdict
    assert m.recover_resolution(str(led), "c1") == (None, None)
    assert m.recover_resolution(str(led), "c1", metric="separation_d") == ("acc", 0.40)


def test_public_name_is_exported_and_private_alias_still_works(tmp_path):
    import measure_mirror as m
    assert "recover_resolution" in m.__all__ and hasattr(m, "recover_resolution")
    led = tmp_path / "l.jsonl"
    _prereg(led)
    _append(led, {"_type": "action", "target": "c1", "payload": {"verdict": "KILL"}})
    assert m.recover_resolution(str(led), "c1") == ("verdict", "KILL")
    assert mm._recover_resolution(str(led), "c1") == ("verdict", "KILL")   # pre-0.34 callers
