"""Tests for ⑫ pre-seal lint — seal QUALITY, not just presence.

These pin the failure classes a real experiment arc lost silent compute to
(semantic-fuel cell arc, 2026-07-20~21):
  • a kill-condition that leaked into the `metric` field from a malformed call
    (the human eye sees a criterion, the parser sees none) — self-catch #2;
  • a bar sitting at/below chance;
  • quantified kills written as free text with no structured threshold;
  • no cheap pre-seal machine-checks declared.
"""
import json

import pytest

from measure_mirror import mm


def _levels(findings):
    return {(f.probe, f.level) for f in findings}


def _msgs(findings):
    return "\n".join(f.msg for f in findings)


# ── ⑫a field-leak (self-catch #2) ────────────────────────────────────────────
def test_kill_condition_leaked_into_metric_is_FAIL():
    pre = {"claim_id": "gate0",
           "metric": "gene1 equilibrium; KILL if delta < 0.03 across all arms",
           "min_n": 24, "baseline": 0.5, "pass_threshold": 0.6}
    fs = mm._preseal_lint(pre)
    assert ("㉗ prereg-lint", "FAIL") in _levels(fs)
    assert "leaked into `metric`" in _msgs(fs)


def test_real_metric_name_is_not_flagged_as_leak():
    # A legitimate metric name with an operator-ish token must NOT false-positive.
    for name in ("acc", "separation_d", "bpb_ko", "delta_vs_baseline", "gene1_eq"):
        pre = {"claim_id": "c", "metric": name, "min_n": 200, "baseline": 0.5,
               "pass_threshold": 0.6,
               "kill_threshold": {"threshold": 0.1, "direction": "below"}}
        msgs = _msgs(mm._preseal_lint(pre))
        assert "leaked into `metric`" not in msgs, name


# ── ⑫b quantified text-only kill ─────────────────────────────────────────────
def test_quantified_text_only_kill_warns():
    pre = {"claim_id": "c", "metric": "acc", "min_n": 200, "baseline": 0.5,
           "pass_threshold": 0.6,
           "kill_condition": "fails if accuracy drops below 0.55"}
    msgs = _msgs(mm._preseal_lint(pre))
    assert "no structured kill_threshold" in msgs


def test_structured_threshold_suppresses_the_quantified_warning():
    pre = {"claim_id": "c", "metric": "acc", "min_n": 200, "baseline": 0.5,
           "pass_threshold": 0.6,
           "kill_condition": "fails below 0.55",
           "kill_threshold": {"threshold": 0.55, "direction": "below"}}
    assert "no structured kill_threshold" not in _msgs(mm._preseal_lint(pre))


def test_incidental_numbers_do_not_trigger_quantified_warning():
    # Regression for the A3 false-positive class: a kill_condition full of incidental
    # digits (sha, date, filename, section, sample size) is NOT a quantified threshold.
    for kc in (
        "protocol=0002_수렴설계_smoke; 봉인 설계대로",
        "H: 엘리트 너울(neoul_grounded.pt)의 Vault 붕괴",
        "coupling을 selection 게이트에 배선 (for v2)",
        "평가셋 n=600, 3시드에서 R-특이 서명이 사라지면 기각",
        "프로토콜 sha256=a1b2c3d4 위반 시 기각",
    ):
        pre = {"claim_id": "c", "metric": "acc", "min_n": 200,
               "pass_threshold": 0.6, "kill_condition": kc}
        assert "no structured kill_threshold" not in _msgs(mm._preseal_lint(pre)), kc


def test_operator_and_korean_comparison_trigger_quantified_warning():
    for kc in ("acc < 0.5 이면 기각", "정확도 0.55 미만이면 사망", "drops below 0.4"):
        pre = {"claim_id": "c", "metric": "acc", "min_n": 200,
               "pass_threshold": 0.6, "kill_condition": kc}
        assert "no structured kill_threshold" in _msgs(mm._preseal_lint(pre)), kc


# ── ⑫c bar at/below chance ───────────────────────────────────────────────────
def test_pass_bar_at_or_below_declared_chance_is_FAIL():
    # An absolute bounded-accuracy claim whose pass bar sits at/below declared chance.
    pre = {"claim_id": "c", "metric": "acc", "min_n": 200, "chance": 0.5,
           "pass_threshold": 0.45, "metric_range": [0, 1],
           "kill_threshold": {"threshold": 0.4, "direction": "below"}}
    assert "at or below the declared chance" in _msgs(mm._preseal_lint(pre))


def test_baseline_alone_is_NOT_treated_as_chance_floor():
    # Regression for the A3 false-positive class: `baseline` is a comparison-arm
    # score, not the random floor. pass=0.85 < baseline=0.92 must NOT FAIL.
    pre = {"claim_id": "c", "metric": "synth_acc", "min_n": 200, "baseline": 0.92,
           "pass_threshold": 0.85,
           "kill_condition": "fuzzy-key diagnostic; pilot 0.92 vs real 0.265"}
    assert "at or below" not in _msgs(mm._preseal_lint(pre))


def test_placeholder_pass_zero_on_kill_gated_claim_does_not_FAIL():
    # pass_threshold=0 with the real bar in kill_threshold (a delta gate) — placeholder,
    # not a crippled bar. A3 audit: dozens of oee_* claims were false-FAILed by this.
    pre = {"claim_id": "c", "metric": "sel_minus_granted", "min_n": 200,
           "baseline": 0.0, "pass_threshold": 0.0, "chance": 0.0,
           "kill_threshold": {"threshold": 0, "direction": "below_or_equal"}}
    assert "at or below" not in _msgs(mm._preseal_lint(pre))


def test_unbounded_metric_with_declared_chance_skips_bar_check():
    # A margin/delta metric (unbounded) whose pass=0.02 sits below an ABSOLUTE task
    # chance=0.28 — mixing scales. Must NOT FAIL (A3: babbler margin claims).
    pre = {"claim_id": "c", "metric": "margin_M_both_minus_B_lab", "min_n": 200,
           "pass_threshold": 0.02, "chance": 0.2816, "metric_range": "unbounded",
           "kill_threshold": {"threshold": 0.02, "direction": "below"}}
    assert "at or below" not in _msgs(mm._preseal_lint(pre))


def test_bounded_metric_without_declared_chance_skips_bar_check():
    # No declared chance → we don't know the floor → don't guess from baseline.
    pre = {"claim_id": "c", "metric": "acc", "min_n": 200, "baseline": 0.5,
           "pass_threshold": 0.45,
           "kill_threshold": {"threshold": 0.4, "direction": "below"}}
    assert "at or below" not in _msgs(mm._preseal_lint(pre))


# ── ⑫d underpowered ──────────────────────────────────────────────────────────
def test_low_min_n_warns():
    pre = {"claim_id": "c", "metric": "acc", "min_n": 10, "baseline": 0.5,
           "pass_threshold": 0.6,
           "kill_threshold": {"threshold": 0.5, "direction": "below"}}
    assert "below the small-sample floor" in _msgs(mm._preseal_lint(pre))


# ── ⑫e pre-seal machine-checks declaration ───────────────────────────────────
def test_missing_pre_seal_checks_draws_info_nudge():
    pre = {"claim_id": "c", "metric": "acc", "min_n": 200, "baseline": 0.5,
           "pass_threshold": 0.6,
           "kill_threshold": {"threshold": 0.5, "direction": "below"}}
    fs = mm._preseal_lint(pre)
    assert ("㉗ prereg-lint", "INFO") in _levels(fs)
    assert "no pre-seal machine-checks" in _msgs(fs)


def test_declared_pre_seal_checks_report_OK():
    pre = {"claim_id": "c", "metric": "acc", "min_n": 200, "baseline": 0.5,
           "pass_threshold": 0.6,
           "kill_threshold": {"threshold": 0.5, "direction": "below"},
           "pre_seal_checks": ["reachability-smoke", "neutral-control"]}
    fs = mm._preseal_lint(pre)
    assert ("㉗ prereg-lint", "OK") in _levels(fs)
    assert "no pre-seal machine-checks" not in _msgs(fs)


def test_healthy_seal_has_no_warn_or_fail():
    pre = {"claim_id": "good", "metric": "separation_d", "min_n": 240,
           "baseline": 0.5, "pass_threshold": 0.6,
           "kill_threshold": {"metric": "d", "threshold": 0.1, "direction": "below"},
           # ⑫h: a healthy seal records what its checks returned. Bare names are
           # still accepted, they just no longer read as clean.
           "pre_seal_checks": [{"name": "reachability-smoke", "result": "unreachable"},
                               {"name": "mass-balance-audit", "result": "balanced"}]}
    assert not [f for f in mm._preseal_lint(pre) if f.level in ("WARN", "FAIL")]


# ── ledger wrapper + preregister round-trip ──────────────────────────────────
def test_preregister_persists_pre_seal_checks_and_lint_reads_them(tmp_path):
    led = str(tmp_path / "l.jsonl")
    e = mm.preregister(led, "c", metric="acc", min_n=200, baseline=0.5,
                       pass_threshold=0.6,
                       kill_threshold={"metric": "acc", "threshold": 0.55,
                                       "direction": "below"},
                       pre_seal_checks=[{"name": "reachability-smoke",
                                         "result": "unreachable"}])
    assert e["pre_seal_checks"] == [{"name": "reachability-smoke",
                                     "result": "unreachable"}]
    fs = mm.prereg_lint(led, "c")
    assert not [f for f in fs if f.level in ("WARN", "FAIL")]


def test_prereg_lint_all_claims(tmp_path):
    led = str(tmp_path / "l.jsonl")
    mm.preregister(led, "good", metric="acc", min_n=200, baseline=0.5,
                   pass_threshold=0.6,
                   kill_threshold={"threshold": 0.55, "direction": "below"},
                   pre_seal_checks=["reachability-smoke"])
    mm.preregister(led, "weak", metric="acc", min_n=10, baseline=0.5,
                   pass_threshold=0.6,
                   kill_threshold={"threshold": 0.55, "direction": "below"})
    fs = mm.prereg_lint(led)  # claim_id=None → all
    weak_warns = [f for f in fs if "'weak'" in f.msg and f.level == "WARN"]
    assert weak_warns  # the low-n claim surfaces


def test_prereg_lint_missing_claim(tmp_path):
    led = str(tmp_path / "l.jsonl")
    mm.preregister(led, "c", metric="acc", min_n=200, baseline=0.5,
                   pass_threshold=0.6,
                   kill_threshold={"threshold": 0.55, "direction": "below"})
    fs = mm.prereg_lint(led, "nope")
    assert fs[0].level == "WARN" and "No pre-registration" in fs[0].msg


# ── ⑫g threshold with no metric name ─────────────────────────────────────────
# `preregister` validates that `threshold` is numeric and `direction` is below/above,
# but accepts a kill_threshold carrying no `metric`. Auto-evaluation then has no key to
# look for in the sealed result: the bar is sealed, what it is a bar OF is not.
def test_threshold_without_metric_warns():
    pre = {"claim_id": "c", "metric": "a prose description of the quantity",
           "min_n": 200, "baseline": 0.5, "pass_threshold": 0.6,
           "kill_condition": "x",
           "kill_threshold": {"threshold": 0.5, "direction": "below"}}
    msgs = _msgs(mm._preseal_lint(pre))
    assert "names no metric" in msgs
    assert ("㉗ prereg-lint", "WARN") in _levels(mm._preseal_lint(pre))


def test_named_metric_suppresses_the_warning():
    pre = {"claim_id": "c", "metric": "acc", "min_n": 200, "baseline": 0.5,
           "pass_threshold": 0.6, "kill_condition": "x",
           "kill_threshold": {"metric": "acc", "threshold": 0.5, "direction": "below"}}
    assert "names no metric" not in _msgs(mm._preseal_lint(pre))


def test_blank_or_whitespace_metric_counts_as_missing():
    for bad in ("", "   ", None):
        pre = {"claim_id": "c", "metric": "acc", "min_n": 200, "baseline": 0.5,
               "pass_threshold": 0.6, "kill_condition": "x",
               "kill_threshold": {"metric": bad, "threshold": 0.5}}
        assert "names no metric" in _msgs(mm._preseal_lint(pre)), repr(bad)


def test_text_only_kill_does_not_trigger_the_metric_warning():
    # No structured threshold at all is ⑫b's business, not ⑫g's.
    pre = {"claim_id": "c", "metric": "acc", "min_n": 200, "baseline": 0.5,
           "pass_threshold": 0.6, "kill_condition": "fails if it stops converging"}
    assert "names no metric" not in _msgs(mm._preseal_lint(pre))
