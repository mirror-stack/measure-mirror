"""measure-mirror test suite — regression gate (dog-fooded)."""
import json
import hashlib
import sys
import pytest
from measure_mirror import mm
from measure_mirror.pytest_plugin import assert_clean


# ─── Core probes ──────────────────────────────────────────────

def test_small_sample_caught():
    f = mm.audit("/dev/null", "x", reported_metric="acc", reported_acc=0.556, n=9)
    assert any(x.level == "FAIL" for x in f)


def test_honest_passes():
    f = mm.audit("/dev/null", "x", reported_metric="acc", reported_acc=0.78, n=1000)
    assert all(x.level != "FAIL" for x in f)
    assert_clean(f)


def test_anti_signal():
    f = mm.audit("/dev/null", "x", reported_metric="acc", reported_acc=0.385, n=1050)
    assert any("anti-signal" in x.probe for x in f)


def test_baseline_inversion():
    assert mm.baseline_fairness("x", 0.86, 0.92).level == "FAIL"


def test_baseline_tie():
    assert mm.baseline_fairness("x", 0.996, 0.998, higher_better=False).level == "FAIL"


def test_baseline_n_aware():
    # Δ above the fixed margin but not distinguishable at small n -> FAIL
    assert mm.baseline_fairness("x", 0.62, 0.60, n=20).level == "FAIL"
    # same Δ, large enough n -> CI excludes baseline -> OK
    # (n=2000 is NOT enough: a 2-pt gap needs ~n≥5000 to clear 95% — the very
    #  reason a fixed n-blind margin is misleading)
    assert mm.baseline_fairness("x", 0.62, 0.60, n=5000).level == "OK"
    # n omitted -> backward-compatible (no n-check)
    assert mm.baseline_fairness("x", 0.62, 0.60).level == "OK"


def test_scope_overgeneralization():
    assert mm.scope_check(["reasoning"], ["musr_1task"]).level == "FAIL"


def test_scope_ok():
    assert mm.scope_check(["t"], ["t", "held_out"]).level == "OK"


def test_leakage():
    assert mm.leakage_check([1, 2, 3], [3, 4, 5]).level == "FAIL"


def test_leakage_normalized_nearduplicate():
    # differs only in case / punctuation -> caught by normalization
    assert mm.leakage_check(["Hello, World!"], ["hello world"]).level == "FAIL"
    # exact-only mode must NOT flag the normalized near-dup
    assert mm.leakage_check(["Hello, World!"], ["hello world"], fuzzy=False).level == "OK"


def test_leakage_token_jaccard_nearduplicate():
    # high token overlap (one word of seven changed: J=6/8=0.75) -> WARN
    assert mm.leakage_check(
        ["one two three four five six seven"],
        ["one two three four five six eight"]).level == "WARN"
    # genuinely disjoint -> OK
    assert mm.leakage_check(["alpha beta gamma"], ["delta epsilon zeta"]).level == "OK"


def test_wilson_extreme():
    assert mm.wilson_ci(0, 0) == (0.0, 1.0)


def test_db_baseline_lookup():
    assert mm.lookup_baseline("musr", db_dir="db") == 0.5
    assert mm.lookup_baseline("nonexistent", db_dir="db") is None


# ─── local memory: prior-reproduction lookup ─────────────────

def _repro_db(tmp_path):
    db = tmp_path / "db"
    (db / "measured").mkdir(parents=True)
    (db / "measured" / "reproductions.jsonl").write_text(
        '{"_doc":"header comment, not a record"}\n'
        '{"task":"musr","claim":"X 55%","acc_claimed":0.55,"n_claimed":9,'
        '"reproduction":{"n":1000,"acc":0.38},"verdict":"FAIL","note":"chance 미만"}\n'
        '{"task":"musr","claim":"Y passed","verdict":"PASS"}\n'
        '{"task":"gsm8k","claim":"Z","verdict":"FAIL"}\n',
        encoding="utf-8")
    return str(db)


def test_lookup_reproduction_finds_fail(tmp_path):
    recs = mm.lookup_reproduction("musr", _repro_db(tmp_path))
    assert len(recs) == 1                     # _doc skipped, PASS excluded
    assert recs[0]["claim"] == "X 55%"


def test_lookup_reproduction_no_task():
    assert mm.lookup_reproduction(None) == []


def test_lookup_reproduction_unknown_task(tmp_path):
    assert mm.lookup_reproduction("unseen", _repro_db(tmp_path)) == []


def test_lookup_reproduction_missing_file(tmp_path):
    assert mm.lookup_reproduction("musr", str(tmp_path)) == []


def test_audit_surfaces_prior_reproduction(tmp_path):
    """audit(task=...) warns when that task has a prior reproduction failure."""
    db = _repro_db(tmp_path)
    fs = mm.audit("/dev/null", "new_claim",
                  reported_metric="acc", reported_acc=0.62, n=120,
                  task="musr", db_dir=db)
    warns = [f for f in fs if f.probe == "⚙ prior-reproduction"]
    assert len(warns) == 1
    assert warns[0].level == "WARN"
    assert "X 55%" in warns[0].msg


def test_audit_no_reproduction_warning_for_clean_task(tmp_path):
    db = _repro_db(tmp_path)
    fs = mm.audit("/dev/null", "c",
                  reported_metric="acc", reported_acc=0.62, n=120,
                  task="unseen", db_dir=db)
    assert not any(f.probe == "⚙ prior-reproduction" for f in fs)


# ─── local memory: WRITE companion — memory grows ────────────

def test_record_reproduction_fail_verdict(tmp_path):
    """Reproduction that doesn't clear baseline → auto verdict FAIL."""
    db = str(tmp_path / "db")
    e = mm.record_reproduction("arc", claim="80% claim", acc_claimed=0.80,
                               n_claimed=20, acc=0.41, n=800, db_dir=db)
    assert e["verdict"] == "FAIL"
    assert e["task"] == "arc"
    assert e["reproduction"] == {"n": 800, "acc": 0.41}


def test_record_reproduction_pass_verdict(tmp_path):
    """Reproduction that clears baseline → auto verdict PASS."""
    db = str(tmp_path / "db")
    e = mm.record_reproduction("arc", claim="real", acc_claimed=0.80,
                               n_claimed=20, acc=0.78, n=800, db_dir=db)
    assert e["verdict"] == "PASS"


def test_record_then_lookup_roundtrip(tmp_path):
    """Memory grows: a recorded FAIL is then found by lookup + audit."""
    db = str(tmp_path / "db")
    mm.record_reproduction("musr", claim="55%", acc_claimed=0.55, n_claimed=9,
                           acc=0.38, n=1000, note="collapsed", db_dir=db)
    found = mm.lookup_reproduction("musr", db)
    assert len(found) == 1 and found[0]["claim"] == "55%"
    fs = mm.audit("/dev/null", "x", reported_metric="acc", reported_acc=0.6,
                  n=100, task="musr", db_dir=db)
    assert any(f.probe == "⚙ prior-reproduction" for f in fs)


def test_record_reproduction_pass_not_warned(tmp_path):
    """A PASS reproduction is recorded but does NOT trigger an audit warning."""
    db = str(tmp_path / "db")
    mm.record_reproduction("arc", claim="genuine", acc_claimed=0.78,
                           n_claimed=20, acc=0.77, n=800, db_dir=db)
    fs = mm.audit("/dev/null", "y", reported_metric="acc", reported_acc=0.7,
                  n=100, task="arc", db_dir=db)
    assert not any(f.probe == "⚙ prior-reproduction" for f in fs)


# ─── catch log: structured detection history ─────────────────

def _catch_db(tmp_path):
    db = tmp_path / "db"
    cur = db / "curated"
    cur.mkdir(parents=True)
    (cur / "self_catches.jsonl").write_text(
        '{"_doc":"header"}\n'
        '{"case":"FP1","catch":"too-good self-suspect","outcome":"fixed","source":"arc_x"}\n',
        encoding="utf-8")
    (cur / "false_negative_guards.jsonl").write_text(
        '{"case":"FN1","guard":"stand-in","resolution":"re-ran","source":"arc_x"}\n',
        encoding="utf-8")
    (cur / "contamination.jsonl").write_text(
        '{"type":"target_leak","where":"pretrain","detail":"future info","fix":"diff"}\n',
        encoding="utf-8")
    (cur / "gaming_patterns.json").write_text(
        '{"_doc":"sigs","patterns":[{"id":"best_of_n","name":"cherry","signature":"max of N"}]}',
        encoding="utf-8")
    return str(db)


def test_catch_history_all_kinds(tmp_path):
    db = _catch_db(tmp_path)
    rows = mm.catch_history(db_dir=db)
    kinds = {r["kind"] for r in rows}
    assert kinds == {"self_catch", "false_negative", "gaming", "contamination"}
    assert len(rows) == 4   # _doc header skipped


def test_catch_history_kind_filter(tmp_path):
    db = _catch_db(tmp_path)
    rows = mm.catch_history(kind="gaming", db_dir=db)
    assert len(rows) == 1 and rows[0]["id"] == "best_of_n"


def test_catch_history_source_filter(tmp_path):
    db = _catch_db(tmp_path)
    rows = mm.catch_history(source="arc_x", db_dir=db)
    # both self_catch and false_negative share source arc_x; gaming has no source
    assert {r["kind"] for r in rows} == {"self_catch", "false_negative"}


def test_catch_history_empty_db(tmp_path):
    assert mm.catch_history(db_dir=str(tmp_path)) == []


# ─── Bug-fix regression tests ─────────────────────────────────

def test_first_registration_wins(tmp_path):
    """Second registration for same claim_id must be ignored."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1", metric="acc", min_n=200, baseline=0.5, pass_threshold=0.6)
    mm.preregister(ledger, "exp1", metric="f1",  min_n=10,  baseline=0.3, pass_threshold=0.5)
    pre = mm._load_prereg(ledger, "exp1")
    assert pre["metric"] == "acc"
    assert pre["min_n"] == 200


def test_seal_tamper_detected(tmp_path):
    """Direct ledger file modification must trigger seal-tamper FAIL."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp2", metric="acc", min_n=200, baseline=0.5, pass_threshold=0.6)
    with open(ledger) as f:
        entry = json.loads(f.read())
    entry["baseline"] = 0.1  # tamper
    with open(ledger, "w") as f:
        f.write(json.dumps(entry))
    findings = mm.audit(ledger, "exp2", reported_metric="acc", reported_acc=0.72, n=500)
    assert any("seal-tamper" in x.probe for x in findings)
    assert any(x.level == "FAIL" for x in findings)


def test_pass_threshold_fail(tmp_path):
    """acc < pass_threshold → FAIL."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp3", metric="acc", min_n=10, baseline=0.5, pass_threshold=0.80)
    findings = mm.audit(ledger, "exp3", reported_metric="acc", reported_acc=0.75, n=500)
    assert any("pass-threshold" in x.probe for x in findings)
    assert any(x.level == "FAIL" for x in findings)


def test_pass_threshold_pass(tmp_path):
    """acc >= pass_threshold → no pass-threshold FAIL."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp4", metric="acc", min_n=10, baseline=0.5, pass_threshold=0.70)
    findings = mm.audit(ledger, "exp4", reported_metric="acc", reported_acc=0.75, n=500)
    assert not any("pass-threshold" in x.probe and x.level == "FAIL" for x in findings)


# ─── New probes (③⑤⑦) ─────────────────────────────────────────

def test_gaming_check_fail():
    assert mm.gaming_check("acc", ["acc_loss", "entropy"]).level == "FAIL"


def test_gaming_check_ok():
    assert mm.gaming_check("acc", ["cross_entropy", "kl_div"]).level == "OK"


def test_multiseed_unstable():
    assert mm.multiseed_check([0.48, 0.72, 0.65], baseline=0.5).level == "FAIL"


def test_multiseed_high_cv():
    assert mm.multiseed_check([0.60, 0.90, 0.75], baseline=0.5).level == "WARN"


def test_multiseed_stable():
    assert mm.multiseed_check([0.74, 0.75, 0.76], baseline=0.5).level == "OK"


def test_multiseed_single():
    assert mm.multiseed_check([0.75], baseline=0.5).level == "WARN"


def test_too_good_flagged():
    assert mm.too_good_check("test", 0.95, 0.5, suspicious_margin=0.30).level == "WARN"


def test_too_good_ok():
    assert mm.too_good_check("test", 0.60, 0.5, suspicious_margin=0.30).level == "OK"


# ─── Continuous metric audit ──────────────────────────────────

def test_continuous_audit_ok():
    findings = mm.continuous_audit("/dev/null", "reg1",
                                   reported_metric="mse", reported_value=0.10,
                                   baseline_value=0.15, n=500, higher_better=False)
    assert all(x.level != "FAIL" for x in findings)


def test_continuous_audit_direction_fail():
    findings = mm.continuous_audit("/dev/null", "reg2",
                                   reported_metric="mse", reported_value=0.20,
                                   baseline_value=0.15, n=500, higher_better=False)
    assert any(x.level == "FAIL" for x in findings)


def test_continuous_audit_effect_size_warn():
    findings = mm.continuous_audit("/dev/null", "reg3",
                                   reported_metric="pearson_r", reported_value=0.55,
                                   baseline_value=0.50, n=100, std=0.20, higher_better=True)
    assert any("effect-size" in x.probe and x.level == "WARN" for x in findings)


def test_continuous_audit_ledger(tmp_path):
    """Pre-registration + metric swap → FAIL."""
    ledger = str(tmp_path / "c.jsonl")
    mm.preregister(ledger, "reg4", metric="pearson_r", min_n=100, baseline=0.5, pass_threshold=0.6)
    findings = mm.continuous_audit(ledger, "reg4",
                                   reported_metric="spearman_r",
                                   reported_value=0.70, baseline_value=0.50, n=200)
    assert any("metric-swap" in x.probe for x in findings)
    assert any(x.level == "FAIL" for x in findings)


# ─── ① Chain hash tests ───────────────────────────────────────

def test_chain_intact_single(tmp_path):
    """Single registration → chain OK."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1", metric="acc", min_n=200, baseline=0.5, pass_threshold=0.6)
    findings = mm.verify_chain(ledger)
    assert all(f.level == "OK" for f in findings), findings


def test_chain_intact_two_entries(tmp_path):
    """Two registrations → chain links correctly."""
    ledger = str(tmp_path / "l.jsonl")
    e1 = mm.preregister(ledger, "exp1", metric="acc", min_n=200, baseline=0.5, pass_threshold=0.6)
    e2 = mm.preregister(ledger, "exp2", metric="f1",  min_n=100, baseline=0.5, pass_threshold=0.7)
    # second entry must link to first
    assert e2["prev_seal"] == e1["seal"]
    findings = mm.verify_chain(ledger)
    assert all(f.level == "OK" for f in findings), findings


def test_chain_tamper_content(tmp_path):
    """Modifying entry content → seal mismatch → FAIL."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1", metric="acc", min_n=200, baseline=0.5, pass_threshold=0.6)
    with open(ledger) as f:
        entry = json.loads(f.read())
    entry["metric"] = "f1"   # tamper without updating seal
    with open(ledger, "w") as f:
        f.write(json.dumps(entry) + "\n")
    findings = mm.verify_chain(ledger)
    assert any(f.level == "FAIL" and "chain-integrity" in f.probe for f in findings)


def test_chain_break_deleted_middle_entry(tmp_path):
    """Deleting a middle entry → chain break → FAIL."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1", metric="acc", min_n=200, baseline=0.5, pass_threshold=0.6)
    mm.preregister(ledger, "exp2", metric="f1",  min_n=100, baseline=0.5, pass_threshold=0.7)
    mm.preregister(ledger, "exp3", metric="r2",  min_n=50,  baseline=0.0, pass_threshold=0.5)
    # Remove middle entry (exp2)
    with open(ledger) as f:
        lines = f.readlines()
    with open(ledger, "w") as f:
        f.write(lines[0])   # exp1
        f.write(lines[2])   # exp3 — its prev_seal points to exp2, not exp1
    findings = mm.verify_chain(ledger)
    assert any(f.level == "FAIL" and "chain-integrity" in f.probe for f in findings)


def test_chain_break_first_entry_deleted(tmp_path):
    """Deleting the first entry → chain break at entry 1 (prev≠genesis)."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1", metric="acc", min_n=200, baseline=0.5, pass_threshold=0.6)
    mm.preregister(ledger, "exp2", metric="f1",  min_n=100, baseline=0.5, pass_threshold=0.7)
    # Keep only exp2 (exp1 deleted)
    with open(ledger) as f:
        lines = f.readlines()
    with open(ledger, "w") as f:
        f.write(lines[1])   # exp2 — prev_seal points to exp1, not genesis
    findings = mm.verify_chain(ledger)
    assert any(f.level == "FAIL" and "chain-integrity" in f.probe for f in findings)


def test_chain_entry_missing_prev_seal_is_caught(tmp_path):
    """Entry without prev_seal FAILS the chain check (SPEC §4 rule 3: a missing
    prev_seal is treated as the empty string, so the §5 linkage comparison fails
    naturally). Previously this was silently skipped — that let an attacker strip
    prev_seal to downgrade a chained ledger and hide deletions. The seal itself
    still recomputes fine; it is the *linkage* that must not be waived."""
    ledger = str(tmp_path / "l.jsonl")
    entry = {
        "ts": "2025-01-01T00:00:00",
        "claim_id": "no_prev",
        "metric": "acc",
        "min_n": 100,
        "baseline": 0.5,
        "pass_threshold": 0.6,
    }
    entry["seal"] = hashlib.sha256(
        json.dumps(entry, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    with open(ledger, "w") as f:
        f.write(json.dumps(entry) + "\n")
    findings = mm.verify_chain(ledger)
    assert any(f.level == "FAIL" for f in findings), findings
    assert mm._verify_seal(entry), "seal recomputation itself is unaffected"


def test_chain_empty_ledger_no_file(tmp_path):
    """Non-existent ledger → chain OK (empty)."""
    findings = mm.verify_chain(str(tmp_path / "nonexistent.jsonl"))
    assert all(f.level == "OK" for f in findings)


# ─── ⑧ Power probe tests ─────────────────────────────────────

def test_power_insufficient_small_n():
    """n=50, Δ=0.05 above baseline=0.5 → WARN (need ~300+)."""
    f = mm.power_check(50, 0.5, min_detectable_effect=0.05)
    assert f.level == "WARN"
    assert f.probe == "⑧ power"
    assert "n≥" in f.msg


def test_power_sufficient_large_n():
    """n=500, Δ=0.10 → OK."""
    f = mm.power_check(500, 0.5, min_detectable_effect=0.10)
    assert f.level == "OK"


def test_power_large_effect_small_n():
    """n=50 is enough for Δ=0.20 (large effect detectable with less data)."""
    f = mm.power_check(50, 0.5, min_detectable_effect=0.20)
    assert f.level == "OK"


def test_power_very_small_n_always_warn():
    """n=10 never sufficient for small effects."""
    f = mm.power_check(10, 0.5, min_detectable_effect=0.05)
    assert f.level == "WARN"


def test_power_required_n_in_message():
    """Message includes required n."""
    f = mm.power_check(10, 0.5, min_detectable_effect=0.05)
    assert "n≥" in f.msg


def _required_n(**kw):
    """Extract the required n the probe computed (WARN path prints 'need n≥N')."""
    import re
    f = mm.power_check(1, 0.5, min_detectable_effect=0.05, **kw)
    m = re.search(r"n≥(\d+)", f.msg)
    assert m, f.msg
    return int(m.group(1))


def test_power_higher_target_power_needs_more_n():
    """Regression: target_power must change the computed n, not just the text.

    Before the fix z_beta was hardcoded to 0.842 (80%), so 0.99 printed
    'at 99% power' while still returning the 80% n — text and number lied."""
    n80 = _required_n(target_power=0.80)
    n99 = _required_n(target_power=0.99)
    assert n99 > n80, f"0.99 power ({n99}) must exceed 0.80 power ({n80})"
    assert n80 == 781 and n99 == 1829, (n80, n99)


def test_power_stricter_alpha_needs_more_n():
    """Regression: alpha must change the computed n (z_alpha2 was hardcoded)."""
    n05 = _required_n(alpha=0.05)
    n0001 = _required_n(alpha=0.0001)
    assert n0001 > n05, f"α=0.0001 ({n0001}) must exceed α=0.05 ({n05})"
    assert n0001 == 2229, n0001


# ─── ⑨ Multiple comparisons tests ────────────────────────────

def test_multicomp_single_experiment(tmp_path):
    """One claim in ledger → OK."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1", metric="acc", min_n=200, baseline=0.5, pass_threshold=0.6)
    f = mm.multiple_comparisons_check(ledger)
    assert f.level == "OK"


def test_multicomp_three_experiments(tmp_path):
    """Three distinct claims → WARN with Bonferroni α=0.05/3."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1", metric="acc", min_n=200, baseline=0.5, pass_threshold=0.6)
    mm.preregister(ledger, "exp2", metric="f1",  min_n=100, baseline=0.5, pass_threshold=0.7)
    mm.preregister(ledger, "exp3", metric="r2",  min_n=50,  baseline=0.0, pass_threshold=0.5)
    f = mm.multiple_comparisons_check(ledger)
    assert f.level == "WARN"
    assert f.probe == "⑨ multiple-comparisons"
    assert "k=3" in f.msg
    assert "0.0167" in f.msg  # 0.05/3 ≈ 0.0167


def test_multicomp_no_ledger(tmp_path):
    """Non-existent ledger → OK."""
    f = mm.multiple_comparisons_check(str(tmp_path / "none.jsonl"))
    assert f.level == "OK"


def test_multicomp_rereg_same_claim_counts_once(tmp_path):
    """Re-registering same claim_id counts as 1 unique — still OK."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1", metric="acc", min_n=200, baseline=0.5, pass_threshold=0.6)
    mm.preregister(ledger, "exp1", metric="f1",  min_n=10,  baseline=0.5, pass_threshold=0.5)
    f = mm.multiple_comparisons_check(ledger)
    assert f.level == "OK"  # still k=1 unique claim


# ─── full_audit new probes integration ───────────────────────

def test_full_audit_basic(tmp_path):
    ledger = str(tmp_path / "f.jsonl")
    findings = mm.full_audit(ledger, "fa1",
                             reported_metric="acc", reported_acc=0.72, n=500, baseline=0.5)
    assert isinstance(findings, list) and len(findings) > 0


def test_full_audit_all_probes(tmp_path):
    """All optional probes activated at once."""
    ledger = str(tmp_path / "f2.jsonl")
    mm.preregister(ledger, "fa2", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.65)
    findings = mm.full_audit(
        ledger, "fa2",
        reported_metric="acc", reported_acc=0.72, n=200, baseline=0.5,
        competing_name="gru_baseline", competing_acc=0.68,
        reward_terms=["cross_entropy"],
        train_items=[1, 2, 3], test_items=[4, 5, 6],
        seed_results=[0.70, 0.72, 0.74],
        claimed_scope=["task_a"], tested_scope=["task_a"],
    )
    probes = {f.probe for f in findings}
    assert "② fair-baseline" in probes
    assert "③ gaming" in probes
    assert "④a data-leakage" in probes
    assert "⑤ multi-seed" in probes
    assert "⑥ scope" in probes
    assert "⑦ too-good" in probes


def test_full_audit_power_probe(tmp_path):
    """min_detectable_effect activates ⑧ power."""
    ledger = str(tmp_path / "f3.jsonl")
    mm.preregister(ledger, "fa3", metric="acc", min_n=10, baseline=0.5, pass_threshold=0.6)
    findings = mm.full_audit(ledger, "fa3",
                             reported_metric="acc", reported_acc=0.72, n=20, baseline=0.5,
                             min_detectable_effect=0.05)
    assert any(f.probe == "⑧ power" for f in findings)


def test_full_audit_multiplicity_probe(tmp_path):
    """check_multiplicity=True activates ⑨ with k=2."""
    ledger = str(tmp_path / "f4.jsonl")
    mm.preregister(ledger, "m1", metric="acc", min_n=10, baseline=0.5, pass_threshold=0.6)
    mm.preregister(ledger, "m2", metric="acc", min_n=10, baseline=0.5, pass_threshold=0.6)
    findings = mm.full_audit(ledger, "m1",
                             reported_metric="acc", reported_acc=0.72, n=500, baseline=0.5,
                             check_multiplicity=True)
    probes = {f.probe for f in findings}
    assert "⑨ multiple-comparisons" in probes


# ─── ⑩ GRIM tests ────────────────────────────────────────────

def test_grim_ok_exact():
    """acc=0.70, n=10 → k=7, round(7/10,2)=0.70 → OK."""
    f = mm.grim_check(0.70, 10)
    assert f.level == "OK"
    assert f.probe == "⑩ GRIM"


def test_grim_ok_large_n():
    """acc=0.72, n=500 → k=360, round(360/500,2)=0.72 → OK."""
    f = mm.grim_check(0.72, 500)
    assert f.level == "OK"


def test_grim_fail_impossible():
    """acc=0.33, n=10 → round(3/10,2)=0.30, round(4/10,2)=0.40 → FAIL."""
    f = mm.grim_check(0.33, 10)
    assert f.level == "FAIL"
    assert f.probe == "⑩ GRIM"
    assert "Fabricated" in f.msg or "arithmetically impossible" in f.msg


def test_grim_fail_three_decimals():
    """acc=0.556, n=9 → round(5/9,3)=0.556 → OK (real catch from dog-food)."""
    f = mm.grim_check(0.556, 9)
    # 5/9 ≈ 0.5556 rounds to 0.556 at 3 dp — should be OK
    assert f.level == "OK"


def test_grim_invalid_n():
    """n=0 → WARN."""
    f = mm.grim_check(0.70, 0)
    assert f.level == "WARN"


def test_grim_explicit_decimals():
    """n_decimals override respected: force 1 dp check."""
    # 0.3, n=10 → k=3, round(3/10,1)=0.3 → OK
    f = mm.grim_check(0.3, 10, n_decimals=1)
    assert f.level == "OK"


# ─── GRIM on MEANS (acc > 1), not just proportions ───────────
# Regression for the k<=n bug found dog-fooding Brown & Heathers (2017):
# a Likert mean has k = mean·n > n, which the old proportion-only cap
# wrongly failed.

def test_grim_mean_paper_example_impossible():
    """Brown & Heathers' canonical case: 28 integers cannot mean 5.19."""
    f = mm.grim_check(5.19, 28)
    assert f.level == "FAIL"


def test_grim_mean_valid_not_failed():
    """5.18 from n=28 IS possible (k=145) — must be OK, not FAIL (the bug)."""
    f = mm.grim_check(5.18, 28)
    assert f.level == "OK"
    f2 = mm.grim_check(5.21, 28)   # k=146
    assert f2.level == "OK"


def test_grim_mean_div20_second_decimal():
    """Dividing integers by 20 → second decimal is 0 or 5 only."""
    assert mm.grim_check(3.18, 20).level == "FAIL"   # impossible
    assert mm.grim_check(3.15, 20).level == "OK"      # k=63


def test_grim_items_multi_item_granularity():
    """items>1: granularity is n·items, not n (GRIM paper's standard form)."""
    # 5.90 from n=40 subjects × 3 items → N=120; consistent
    assert mm.grim_check(5.90, 40, items=3).level == "OK"
    assert mm.grim_check(0, 5, items=0).level == "WARN"   # guard items<1


def test_grim_external_validation_set():
    """Cross-check against scrutiny (R) — 18 cases with known GRIM verdicts.
    Source: cran.r-project.org/web/packages/scrutiny grim vignette.
    Measure-mirror must reproduce all 18 verdicts (means, multi-item, percents).
    """
    cases = [  # (value, n, items, consistent?)
        (5.27, 43, 1, False), (8.97, 28, 1, False), (2.61, 28, 1, True),
        (7.26, 28, 1, False), (3.64, 28, 1, True),  (9.26, 28, 1, False),
        (10.46, 28, 1, True), (7.39, 28, 1, True),
        (5.90, 40, 3, True),  (5.71, 40, 3, True),  (3.50, 40, 3, True),
        (3.82, 40, 3, True),  (4.61, 40, 3, True),  (5.24, 40, 3, True),
        (0.325, 438, 1, False), (0.356, 455, 1, True),
        (0.217, 501, 1, False), (0.393, 516, 1, True),
    ]
    for value, n, items, consistent in cases:
        expected = "OK" if consistent else "FAIL"
        got = mm.grim_check(value, n, items=items).level
        assert got == expected, f"grim({value}, n={n}, items={items}): {got} ≠ {expected}"


def test_grim_in_audit_fail_appended(tmp_path):
    """GRIM FAIL is appended to audit findings (probe name in result set)."""
    ledger = str(tmp_path / "l.jsonl")
    # acc=0.33, n=10 is GRIM-impossible (no k gives round(k/10,2)=0.33)
    findings = mm.audit(ledger, "grim_test",
                        reported_metric="acc", reported_acc=0.33, n=10)
    assert any(f.probe == "⑩ GRIM" and f.level == "FAIL" for f in findings)


def test_grim_ok_not_appended_to_audit(tmp_path):
    """GRIM OK is silently dropped from audit output to keep output clean."""
    ledger = str(tmp_path / "l.jsonl")
    # acc=0.70, n=10 → GRIM OK → should not appear in findings
    findings = mm.audit(ledger, "clean_test",
                        reported_metric="acc", reported_acc=0.70, n=10)
    assert not any(f.probe == "⑩ GRIM" for f in findings)


# ─── ⚙ calibrate tests ───────────────────────────────────────

def test_calibrate_ok():
    """calibrate() returns OK when the mirror is working correctly."""
    findings = mm.calibrate()
    assert len(findings) == 1
    assert findings[0].level == "OK"
    assert findings[0].probe == "⚙ calibrate"
    assert "5/5" in findings[0].msg


def test_calibrate_returns_finding_list():
    """calibrate() always returns list[Finding]."""
    findings = mm.calibrate()
    assert isinstance(findings, list)
    assert all(isinstance(f, mm.Finding) for f in findings)


# ─── 🎬 witness tests ─────────────────────────────────────────

def test_witness_basic(tmp_path):
    """witness() runs a command and creates a sealed record."""
    ledger = str(tmp_path / "l.jsonl")
    e = mm.witness(ledger, "test_run", [sys.executable, "-c", "print('hello')"])
    assert e["run_status"] == "ok"
    assert e["returncode"] == 0
    assert "seal" in e
    assert "output_hash" in e
    assert e["claim_id"] == "test_run"


def test_witness_type_in_ledger(tmp_path):
    """Witness record has _type='witness' in ledger file."""
    ledger = str(tmp_path / "l.jsonl")
    mm.witness(ledger, "x", [sys.executable, "-c", "pass"])
    with open(ledger) as f:
        entry = json.loads(f.readline())
    assert entry["_type"] == "witness"


def test_witness_output_hash_stable(tmp_path):
    """Identical command output → identical output_hash (content-addressable)."""
    l1 = str(tmp_path / "l1.jsonl")
    l2 = str(tmp_path / "l2.jsonl")
    e1 = mm.witness(l1, "x", [sys.executable, "-c", "print('stable')"])
    e2 = mm.witness(l2, "x", [sys.executable, "-c", "print('stable')"])
    assert e1["output_hash"] == e2["output_hash"]


def test_witness_chain_linked_to_prereg(tmp_path):
    """Witness entry's prev_seal links to the preregister entry's seal."""
    ledger = str(tmp_path / "l.jsonl")
    pre = mm.preregister(ledger, "exp1",
                         metric="acc", min_n=50, baseline=0.5, pass_threshold=0.6)
    w = mm.witness(ledger, "exp1", [sys.executable, "-c", "pass"])
    assert w["prev_seal"] == pre["seal"]


def test_witness_chain_verifies(tmp_path):
    """Full ledger with preregister + witness passes verify_chain."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1",
                   metric="acc", min_n=50, baseline=0.5, pass_threshold=0.6)
    mm.witness(ledger, "exp1", [sys.executable, "-c", "pass"])
    findings = mm.verify_chain(ledger)
    assert all(f.level == "OK" for f in findings), findings


def test_witness_nonzero_exit(tmp_path):
    """Non-zero exit code is recorded; run_status is still 'ok' (the run ran)."""
    ledger = str(tmp_path / "l.jsonl")
    e = mm.witness(ledger, "x",
                   [sys.executable, "-c", "import sys; sys.exit(42)"])
    assert e["returncode"] == 42
    assert e["run_status"] == "ok"


# ─── 📎 anchor tests ──────────────────────────────────────────

def test_anchor_missing_ledger(tmp_path):
    """Anchor on non-existent ledger returns empty sentinel values."""
    a = mm.anchor(str(tmp_path / "none.jsonl"))
    assert a["entry_count"] == 0
    assert a["head_seal"] == "empty"
    assert a["anchor_hash"] == "empty"
    assert a["chain_ok"] is True
    assert a["_type"] == "anchor"


def test_anchor_basic(tmp_path):
    """Anchor returns expected keys and correct entry_count."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1",
                   metric="acc", min_n=100, baseline=0.5, pass_threshold=0.6)
    mm.preregister(ledger, "exp2",
                   metric="f1",  min_n=50,  baseline=0.5, pass_threshold=0.7)
    a = mm.anchor(ledger)
    assert a["entry_count"] == 2
    assert a["chain_ok"] is True
    assert len(a["anchor_hash"]) == 64  # full SHA-256 hex
    assert a["head_seal"] != "empty"


def test_anchor_hash_changes_on_new_entry(tmp_path):
    """Adding an entry changes anchor_hash (detects any modification)."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1",
                   metric="acc", min_n=100, baseline=0.5, pass_threshold=0.6)
    a1 = mm.anchor(ledger)
    mm.preregister(ledger, "exp2",
                   metric="f1",  min_n=50,  baseline=0.5, pass_threshold=0.7)
    a2 = mm.anchor(ledger)
    assert a1["anchor_hash"] != a2["anchor_hash"]


def test_anchor_head_seal_matches_last_entry(tmp_path):
    """anchor head_seal equals the last registered entry's seal."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "e1", metric="acc", min_n=10, baseline=0.5, pass_threshold=0.6)
    pre = mm.preregister(ledger, "e2", metric="f1",  min_n=10, baseline=0.5, pass_threshold=0.7)
    a = mm.anchor(ledger)
    assert a["head_seal"] == pre["seal"]


def test_anchor_chain_ok_false_on_tamper(tmp_path):
    """Tampered ledger → chain_ok is False in anchor."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1",
                   metric="acc", min_n=100, baseline=0.5, pass_threshold=0.6)
    with open(ledger) as f:
        entry = json.loads(f.read())
    entry["baseline"] = 0.9  # tamper without updating seal
    with open(ledger, "w") as f:
        f.write(json.dumps(entry) + "\n")
    a = mm.anchor(ledger)
    assert a["chain_ok"] is False


# ─── ⑪ falsifiability_check tests ────────────────────────────

def test_falsifiability_no_prereg(tmp_path):
    """No pre-registration → WARN (kill-condition unknown)."""
    f = mm.falsifiability_check(str(tmp_path / "none.jsonl"), "x")
    assert f.level == "WARN"
    assert f.probe == "⑪ falsifiability"


def test_falsifiability_no_kill_condition_warns(tmp_path):
    """Pre-registration without any kill-condition → WARN unfalsifiable."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1",
                   metric="acc", min_n=100, baseline=0.5, pass_threshold=0.6)
    f = mm.falsifiability_check(ledger, "exp1")
    assert f.level == "WARN"
    assert "unfalsifiable" in f.msg.lower() or "no kill-condition" in f.msg.lower()


def test_falsifiability_text_only_ok(tmp_path):
    """kill_condition text-only (no threshold) → OK with text note."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1",
                   metric="acc", min_n=100, baseline=0.5, pass_threshold=0.6,
                   kill_condition="accuracy drops below 0.55 on held-out test")
    f = mm.falsifiability_check(ledger, "exp1")
    assert f.level == "OK"
    assert "text-only" in f.msg


def test_falsifiability_threshold_not_triggered(tmp_path):
    """kill_threshold registered; acc ≥ threshold → OK."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1",
                   metric="acc", min_n=100, baseline=0.5, pass_threshold=0.6,
                   kill_threshold={"metric": "acc", "threshold": 0.55, "direction": "below"})
    f = mm.falsifiability_check(ledger, "exp1", reported_acc=0.72)
    assert f.level == "OK"
    assert f.probe == "⑪ falsifiability"


def test_falsifiability_threshold_triggered_fail(tmp_path):
    """kill_threshold registered; acc < threshold → FAIL (claim falsified)."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1",
                   metric="acc", min_n=100, baseline=0.5, pass_threshold=0.6,
                   kill_condition="model is not better than chance",
                   kill_threshold={"metric": "acc", "threshold": 0.55, "direction": "below"})
    f = mm.falsifiability_check(ledger, "exp1", reported_acc=0.50)
    assert f.level == "FAIL"
    assert "falsified" in f.msg


def test_falsifiability_threshold_above_direction(tmp_path):
    """direction=above; reported > threshold → FAIL (e.g. MSE error metric)."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1",
                   metric="mse", min_n=50, baseline=0.5, pass_threshold=0.0,
                   kill_threshold={"metric": "mse", "threshold": 0.30, "direction": "above"})
    # reported MSE=0.35 > kill threshold 0.30 → FAIL
    f = mm.falsifiability_check(ledger, "exp1", reported_acc=0.35)
    assert f.level == "FAIL"


# ─── ⑫ prereg_lint tests (full coverage in tests/test_preseal_lint.py) ────────

def test_prereg_lint_flags_leaked_kill_condition(tmp_path):
    """A kill-condition sealed into the `metric` field (malformed call) is FAILed
    by the lint even though falsifiability_check would only say 'unfalsifiable'."""
    ledger = str(tmp_path / "l.jsonl")
    # Simulate the malformed seal: criterion text in `metric`, no kill fields.
    mm.preregister(ledger, "gate0",
                   metric="gene1 eq; KILL if delta < 0.03 across all arms",
                   min_n=200, baseline=0.5, pass_threshold=0.6)
    fs = mm.prereg_lint(ledger, "gate0")
    assert any(f.level == "FAIL" and "leaked into `metric`" in f.msg for f in fs)


def test_prereg_lint_clean_on_healthy_seal(tmp_path):
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "good", metric="acc", min_n=200, baseline=0.5,
                   pass_threshold=0.6,
                   kill_threshold={"metric": "acc", "threshold": 0.55, "direction": "below"},
                   pre_seal_checks=["reachability-smoke", "neutral-control"])
    fs = mm.prereg_lint(ledger, "good")
    assert not [f for f in fs if f.level in ("WARN", "FAIL")]


def test_falsifiability_threshold_no_result_warns(tmp_path):
    """kill_threshold registered but no reported_acc → WARN (unevaluated)."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1",
                   metric="acc", min_n=100, baseline=0.5, pass_threshold=0.6,
                   kill_threshold={"metric": "acc", "threshold": 0.55, "direction": "below"})
    f = mm.falsifiability_check(ledger, "exp1")  # no reported_acc
    assert f.level == "WARN"


def test_falsifiability_stored_in_ledger(tmp_path):
    """kill_condition and kill_threshold are sealed into the ledger entry."""
    ledger = str(tmp_path / "l.jsonl")
    e = mm.preregister(ledger, "exp1",
                       metric="acc", min_n=100, baseline=0.5, pass_threshold=0.6,
                       kill_condition="model is not useful",
                       kill_threshold={"metric": "acc", "threshold": 0.55, "direction": "below"})
    assert e["kill_condition"] == "model is not useful"
    assert e["kill_threshold"]["threshold"] == 0.55


def test_falsifiability_in_audit_unfalsifiable_warns(tmp_path):
    """audit() appends ⑪ WARN when no kill-condition is registered."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1",
                   metric="acc", min_n=50, baseline=0.5, pass_threshold=0.6)
    findings = mm.audit(ledger, "exp1",
                        reported_metric="acc", reported_acc=0.72, n=200)
    assert any(f.probe == "⑪ falsifiability" and f.level == "WARN" for f in findings)


def test_falsifiability_in_audit_triggered_fails(tmp_path):
    """audit() appends ⑪ FAIL when kill_threshold is triggered."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1",
                   metric="acc", min_n=50, baseline=0.5, pass_threshold=0.4,
                   kill_threshold={"metric": "acc", "threshold": 0.60, "direction": "below"})
    findings = mm.audit(ledger, "exp1",
                        reported_metric="acc", reported_acc=0.55, n=200)
    assert any(f.probe == "⑪ falsifiability" and f.level == "FAIL" for f in findings)


def test_falsifiability_kill_threshold_seal_valid(tmp_path):
    """Adding kill fields doesn't break the chain seal."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "e1",
                   metric="acc", min_n=50, baseline=0.5, pass_threshold=0.6,
                   kill_threshold={"metric": "acc", "threshold": 0.55, "direction": "below"})
    findings = mm.verify_chain(ledger)
    assert all(f.level == "OK" for f in findings), findings


# ─── ⑫ retraction cascade tests ──────────────────────────────

def test_cascade_ok_no_retractions(tmp_path):
    """No retractions in ledger → OK."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.6)
    f = mm.cascade_check(ledger, "exp1")
    assert f.level == "OK"
    assert f.probe == "⑫ retraction-cascade"


def test_cascade_ok_empty_ledger(tmp_path):
    """Empty ledger → OK (no retraction risk)."""
    f = mm.cascade_check(str(tmp_path / "none.jsonl"), "exp1")
    assert f.level == "OK"


def test_cascade_fail_direct_retraction(tmp_path):
    """Claim itself retracted → FAIL."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.6)
    mm.retract(ledger, "exp1", "data labelling error")
    f = mm.cascade_check(ledger, "exp1")
    assert f.level == "FAIL"
    assert "exp1" in f.msg


def test_cascade_warn_direct_dependency(tmp_path):
    """Claim depends on retracted claim → WARN stale."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "base", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.6)
    mm.preregister(ledger, "exp1", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.6,
                   depends_on=["base"])
    mm.retract(ledger, "base", "fundamental flaw found")
    f = mm.cascade_check(ledger, "exp1")
    assert f.level == "WARN"
    assert "STALE" in f.msg
    assert "base" in f.msg


def test_cascade_warn_transitive_dependency(tmp_path):
    """Transitive chain: exp2 → exp1 → base (base retracted) → exp2 is STALE."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "base", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.6)
    mm.preregister(ledger, "exp1", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.6,
                   depends_on=["base"])
    mm.preregister(ledger, "exp2", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.6,
                   depends_on=["exp1"])
    mm.retract(ledger, "base", "fundamental flaw")
    f = mm.cascade_check(ledger, "exp2")
    assert f.level == "WARN"
    assert "STALE" in f.msg


def test_retract_entry_chain_verifies(tmp_path):
    """Retraction entry is chain-linked and passes verify_chain."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.6)
    mm.retract(ledger, "exp1", "mistake")
    findings = mm.verify_chain(ledger)
    assert all(f.level == "OK" for f in findings), findings


def test_retract_returns_entry_with_seal(tmp_path):
    """retract() returns a dict with the expected keys."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "e1", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.6)
    e = mm.retract(ledger, "e1", "wrong baseline used")
    assert e["_type"] == "retraction"
    assert e["claim_id"] == "e1"
    assert e["reason"] == "wrong baseline used"
    assert len(e["seal"]) == 64   # full digest since seal upgrade


def test_cascade_in_audit_fail_appended(tmp_path):
    """audit() appends ⑫ FAIL when claim is retracted."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.4)
    mm.retract(ledger, "exp1", "results were fabricated")
    findings = mm.audit(ledger, "exp1",
                        reported_metric="acc", reported_acc=0.72, n=200)
    assert any(f.probe == "⑫ retraction-cascade" and f.level == "FAIL" for f in findings)


def test_cascade_in_audit_warn_appended(tmp_path):
    """audit() appends ⑫ WARN when audited claim's dependency was retracted."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "base", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.4)
    mm.preregister(ledger, "exp1", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.4,
                   depends_on=["base"])
    mm.retract(ledger, "base", "dataset contaminated")
    findings = mm.audit(ledger, "exp1",
                        reported_metric="acc", reported_acc=0.72, n=200)
    assert any(f.probe == "⑫ retraction-cascade" and f.level == "WARN" for f in findings)


def test_depends_on_sealed_in_entry(tmp_path):
    """depends_on is included in the ledger entry and sealed."""
    ledger = str(tmp_path / "l.jsonl")
    e = mm.preregister(ledger, "exp1", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.6,
                       depends_on=["baseline_v1", "data_v2"])
    assert e["depends_on"] == ["baseline_v1", "data_v2"]
    findings = mm.verify_chain(ledger)
    assert all(f.level == "OK" for f in findings), findings


# ─── ⑬ negative_audit tests ──────────────────────────────────

def _reg(ledger, cid):
    """Helper: register a claim with minimal args."""
    mm.preregister(ledger, cid, metric="acc", min_n=50, baseline=0.5, pass_threshold=0.6)


def test_negative_audit_ok(tmp_path):
    """3 pre-registered angles, none retracted → OK."""
    ledger = str(tmp_path / "l.jsonl")
    for cid in ["a1", "a2", "a3"]:
        _reg(ledger, cid)
    f = mm.negative_audit(ledger, angles=["a1", "a2", "a3"])
    assert f.level == "OK"
    assert f.probe == "⑬ negative-audit"


def test_negative_audit_fail_too_few(tmp_path):
    """Only 2 angles with min_angles=3 → FAIL premature closure."""
    ledger = str(tmp_path / "l.jsonl")
    for cid in ["a1", "a2"]:
        _reg(ledger, cid)
    f = mm.negative_audit(ledger, angles=["a1", "a2"], min_angles=3)
    assert f.level == "FAIL"
    assert "2" in f.msg


def test_negative_audit_fail_unregistered(tmp_path):
    """One angle not pre-registered → FAIL."""
    ledger = str(tmp_path / "l.jsonl")
    _reg(ledger, "a1")
    _reg(ledger, "a2")
    # "ghost" is not registered
    f = mm.negative_audit(ledger, angles=["a1", "a2", "ghost"], min_angles=3)
    assert f.level == "FAIL"
    assert "ghost" in f.msg


def test_negative_audit_warn_retracted(tmp_path):
    """3 angles registered but one retracted → WARN weakened."""
    ledger = str(tmp_path / "l.jsonl")
    for cid in ["a1", "a2", "a3"]:
        _reg(ledger, cid)
    mm.retract(ledger, "a3", "error in experiment design")
    f = mm.negative_audit(ledger, angles=["a1", "a2", "a3"])
    assert f.level == "WARN"
    assert "a3" in f.msg


def test_negative_audit_fail_empty_angles(tmp_path):
    """Empty angles list → FAIL (0 < min_angles=3)."""
    f = mm.negative_audit(str(tmp_path / "l.jsonl"), angles=[], min_angles=3)
    assert f.level == "FAIL"


def test_negative_audit_ok_custom_min(tmp_path):
    """1 angle, min_angles=1 → OK."""
    ledger = str(tmp_path / "l.jsonl")
    _reg(ledger, "solo")
    f = mm.negative_audit(ledger, angles=["solo"], min_angles=1)
    assert f.level == "OK"


def test_negative_audit_scope_fail(tmp_path):
    """conclusion_scope broader than tested_scope → FAIL."""
    ledger = str(tmp_path / "l.jsonl")
    for cid in ["a1", "a2", "a3"]:
        _reg(ledger, cid)
    f = mm.negative_audit(ledger, angles=["a1", "a2", "a3"],
                          conclusion_scope=["general_OEE", "all_substrates"],
                          tested_scope=["gray_scott"])
    assert f.level == "FAIL"
    assert "general_OEE" in f.msg or "all_substrates" in f.msg


def test_negative_audit_in_full_audit(tmp_path):
    """full_audit with angles param appends ⑬ finding."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "main", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.4)
    for cid in ["a1", "a2", "a3"]:
        _reg(ledger, cid)
    findings = mm.full_audit(ledger, "main",
                             reported_metric="acc", reported_acc=0.72, n=200,
                             angles=["a1", "a2", "a3"])
    assert any(f.probe == "⑬ negative-audit" for f in findings)


# ─── ⑭ judge_consistency_check tests ─────────────────────────

def test_judge_consistency_ok():
    """Flip rate at/below threshold → OK."""
    pairs = [(1, 1), (0, 0), (1, 1), (0, 0), (1, 0)]  # 1 flip / 5 = 20%
    f = mm.judge_consistency_check(pairs, flip_threshold=0.20)
    assert f.level == "OK"
    assert f.probe == "⑭ judge-consistency"


def test_judge_consistency_fail():
    """Flip rate above threshold → FAIL."""
    pairs = [(1, 0), (0, 1), (1, 0), (0, 0), (1, 1)]  # 3 flips / 5 = 60%
    f = mm.judge_consistency_check(pairs, flip_threshold=0.20)
    assert f.level == "FAIL"
    assert "60%" in f.msg or "0.6" in f.msg.lower() or "3/5" in f.msg


def test_judge_consistency_warn_empty():
    """Empty score_pairs → WARN (cannot assess)."""
    f = mm.judge_consistency_check([])
    assert f.level == "WARN"


# ─── ⑮ judge_bias_check tests ────────────────────────────────

def test_judge_bias_ok():
    """Balanced A/B wins → OK."""
    results = [0, 1, 0, 1, 0, 1, 0, 1, 0, 1]  # 50/50
    f = mm.judge_bias_check(results)
    assert f.level == "OK"
    assert f.probe == "⑮ judge-bias"


def test_judge_bias_fail_a_dominates():
    """A wins 90% → FAIL position bias."""
    results = [0] * 9 + [1]  # A wins 90%
    f = mm.judge_bias_check(results, bias_threshold=0.60)
    assert f.level == "FAIL"
    assert "A" in f.msg


def test_judge_bias_fail_b_dominates():
    """B wins 90% → FAIL position bias."""
    results = [1] * 9 + [0]  # B wins 90%
    f = mm.judge_bias_check(results, bias_threshold=0.60)
    assert f.level == "FAIL"
    assert "B" in f.msg


# ─── ⑯ inter_rater_agreement tests ───────────────────────────

def test_inter_rater_ok():
    """Perfect agreement → κ=1.0 → OK."""
    matrix = [(1, 1), (0, 0), (1, 1), (0, 0), (1, 1)]
    f = mm.inter_rater_agreement(matrix)
    assert f.level == "OK"
    assert f.probe == "⑯ inter-rater"
    assert "1.000" in f.msg


def test_inter_rater_warn():
    """Moderate agreement (κ ≈ 0.33) → WARN."""
    # Rater1: [0,0,0,1,1,1]  Rater2: [0,1,0,1,0,1]
    # Agreement: items 0,2,3,5 → p_o = 4/6 ≈ 0.667
    # p1_rate1=0.5, p1_rate2=0.5; p_e=0.5*0.5+0.5*0.5=0.5; κ=(0.667-0.5)/(0.5)=0.333
    matrix = [(0, 0), (0, 1), (0, 0), (1, 1), (1, 0), (1, 1)]
    f = mm.inter_rater_agreement(matrix, min_kappa=0.40)
    assert f.level == "WARN"
    assert "0.33" in f.msg


def test_inter_rater_fail_too_few():
    """Fewer than 3 items → FAIL."""
    f = mm.inter_rater_agreement([(1, 0), (0, 1)])
    assert f.level == "FAIL"
    assert "3" in f.msg


# ─── ⑰ judge_score_sanity tests ──────────────────────────────

def test_judge_score_sanity_ok():
    """Varied scores → OK."""
    scores = [3, 7, 5, 8, 4, 6, 9, 2, 7, 5, 3, 8, 6, 4, 7]
    f = mm.judge_score_sanity(scores)
    assert f.level == "OK"
    assert f.probe == "⑰ judge-score-sanity"


def test_judge_score_sanity_fail_all_identical():
    """All scores identical → FAIL."""
    scores = [8] * 20
    f = mm.judge_score_sanity(scores)
    assert f.level == "FAIL"
    assert "8" in f.msg


def test_judge_score_sanity_warn_near_degenerate():
    """One value covers >90% → WARN."""
    scores = [8] * 19 + [7]  # 95% are 8
    f = mm.judge_score_sanity(scores)
    assert f.level == "WARN"


def test_judge_score_sanity_warn_empty():
    """Empty scores list → WARN."""
    f = mm.judge_score_sanity([])
    assert f.level == "WARN"


# ─── ⑱ judge_swap_check tests ────────────────────────────────

def test_judge_swap_ok_content_driven():
    """Verdict inverts with the swap → content-driven → OK."""
    forward = [0, 1, 0, 1, 0, 1, 0, 1, 0, 1]
    swapped = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0]  # all inverted
    f = mm.judge_swap_check(forward, swapped)
    assert f.level == "OK"
    assert f.probe == "⑱ judge-swap"


def test_judge_swap_fail_position_locked():
    """Verdict stays with the slot → position-locked → FAIL."""
    forward = [0, 0, 0, 0, 0, 1, 1, 1, 1, 1]
    swapped = [0, 0, 0, 0, 0, 1, 1, 1, 1, 1]  # identical = locked
    f = mm.judge_swap_check(forward, swapped)
    assert f.level == "FAIL"
    assert "position" in f.msg.lower()


def test_judge_swap_warn_noise_band():
    """~50% lock rate → noise band → WARN."""
    forward = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    swapped = [0, 0, 0, 0, 0, 1, 1, 1, 1, 1]  # 5/10 locked
    f = mm.judge_swap_check(forward, swapped)
    assert f.level == "WARN"


def test_judge_swap_fail_length_mismatch():
    """Different lengths → FAIL usage error."""
    f = mm.judge_swap_check([0, 1, 0], [0, 1])
    assert f.level == "FAIL"
    assert "mismatch" in f.msg.lower()


def test_judge_swap_filters_parse_failures():
    """-1 entries excluded from lock-rate computation."""
    forward = [0, -1, 1, 0, -1]
    swapped = [1, 0, 0, 1, 1]  # valid pairs: (0,1),(1,0),(0,1) — all inverted
    f = mm.judge_swap_check(forward, swapped)
    assert f.level == "OK"


def test_judge_swap_warn_no_valid_pairs():
    """All pairs contain -1 → WARN."""
    f = mm.judge_swap_check([-1, -1], [0, 1])
    assert f.level == "WARN"


# ─── certificate tests ───────────────────────────────────────

def test_certificate_certified(tmp_path):
    """Clean claim with valid prereg → CERTIFIED."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.4)
    c = mm.certificate(ledger, "exp1")
    assert c["verdict"] == "CERTIFIED"
    assert c["prereg_seal_ok"] is True
    assert c["chain_ok"] is True
    assert len(c["seal"]) == 64   # full digest since seal upgrade


def test_certificate_unverified_no_prereg(tmp_path):
    """No prereg entry → UNVERIFIED."""
    ledger = str(tmp_path / "l.jsonl")
    c = mm.certificate(ledger, "ghost")
    assert c["verdict"] == "UNVERIFIED"
    assert c["prereg_seal"] is None


def test_certificate_rejected_retracted(tmp_path):
    """Retracted claim → REJECTED."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.4)
    mm.retract(ledger, "exp1", "fabricated data")
    c = mm.certificate(ledger, "exp1")
    assert c["verdict"] == "REJECTED"
    assert c["cascade"] == "FAIL"


def test_certificate_warns_stale_dependency(tmp_path):
    """Stale dependency → CERTIFIED-WITH-WARNINGS."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "base", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.4)
    mm.preregister(ledger, "exp1", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.4,
                   depends_on=["base"])
    mm.retract(ledger, "base", "flaw found")
    c = mm.certificate(ledger, "exp1")
    assert c["verdict"] == "CERTIFIED-WITH-WARNINGS"
    assert c["cascade"] == "WARN"


def test_certificate_rejected_on_fail_findings(tmp_path):
    """FAIL finding folded in → REJECTED."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1", metric="acc", min_n=200, baseline=0.5, pass_threshold=0.6)
    findings = mm.audit(ledger, "exp1",
                        reported_metric="acc", reported_acc=0.556, n=9)  # small-sample FAIL
    c = mm.certificate(ledger, "exp1", findings=findings)
    assert c["verdict"] == "REJECTED"
    assert c["findings"]["fail"] >= 1


def test_certificate_embeds_anchor_hash(tmp_path):
    """Certificate pins the ledger state via anchor_hash."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.4)
    c1 = mm.certificate(ledger, "exp1")
    a = mm.anchor(ledger)
    assert c1["anchor_hash"] == a["anchor_hash"]
    # ledger change → new certificate has a different anchor_hash
    mm.preregister(ledger, "exp2", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.4)
    c2 = mm.certificate(ledger, "exp1")
    assert c2["anchor_hash"] != c1["anchor_hash"]


# ─── ⑲ judge_transitivity_check tests ────────────────────────

def test_transitivity_ok_acyclic():
    """Clean transitive tournament A>B>C → OK."""
    matches = [("A", "B", 0), ("B", "C", 0), ("A", "C", 0)]
    f = mm.judge_transitivity_check(matches)
    assert f.level == "OK"
    assert f.probe == "⑲ judge-transitivity"


def test_transitivity_fail_cycle():
    """A>B, B>C, C>A → cycle → FAIL with example path."""
    matches = [("A", "B", 0), ("B", "C", 0), ("C", "A", 0)]
    f = mm.judge_transitivity_check(matches)
    assert f.level == "FAIL"
    assert ">" in f.msg  # example cycle shown


def test_transitivity_majority_aggregation():
    """Repeated matches aggregate by majority: A beats B 2-1 → edge A>B."""
    matches = [("A", "B", 0), ("A", "B", 0), ("A", "B", 1),
               ("B", "C", 0), ("A", "C", 0)]
    f = mm.judge_transitivity_check(matches)
    assert f.level == "OK"


def test_transitivity_warn_too_few_models():
    """Only 2 models → WARN (cycle impossible)."""
    matches = [("A", "B", 0), ("A", "B", 1)]
    f = mm.judge_transitivity_check(matches)
    assert f.level == "WARN"


def test_transitivity_warn_empty():
    """No matches → WARN."""
    f = mm.judge_transitivity_check([])
    assert f.level == "WARN"


def test_transitivity_ties_no_edge():
    """Exactly tied pair produces no edge — no false cycle."""
    # A-B tied (1-1); B>C, C>A would only cycle if A>B existed
    matches = [("A", "B", 0), ("A", "B", 1),
               ("B", "C", 0), ("C", "A", 0)]
    f = mm.judge_transitivity_check(matches)
    assert f.level == "OK"
    assert "tied" in f.msg


# ─── ⑳ ranking_stability_check tests ─────────────────────────

def test_ranking_stability_ok_clear_winner():
    """Large consistent gap → stable ranking → OK."""
    scores_a = [9, 8, 9, 9, 8, 9, 8, 9, 9, 8] * 3
    scores_b = [3, 2, 3, 2, 3, 2, 3, 2, 3, 2] * 3
    f = mm.ranking_stability_check(scores_a, scores_b)
    assert f.level == "OK"
    assert f.probe == "⑳ ranking-stability"
    assert "A > B" in f.msg


def test_ranking_stability_fail_noise():
    """Tiny gap on few noisy items → ranking flips under resampling → FAIL."""
    scores_a = [5, 9, 1, 8, 2, 7, 3]
    scores_b = [6, 1, 9, 2, 8, 3, 7]   # nearly identical sums, high variance
    f = mm.ranking_stability_check(scores_a, scores_b)
    assert f.level in ("FAIL", "WARN")  # unstable either way
    assert f.level == "FAIL" or "below" in f.msg


def test_ranking_stability_fail_tied_means():
    """Exactly tied sums → no ranking to certify → FAIL."""
    f = mm.ranking_stability_check([5, 5, 5, 5, 5], [5, 5, 5, 5, 5])
    assert f.level == "FAIL"
    assert "tied" in f.msg


def test_ranking_stability_fail_length_mismatch():
    f = mm.ranking_stability_check([1, 2, 3], [1, 2])
    assert f.level == "FAIL"
    assert "mismatch" in f.msg.lower()


def test_ranking_stability_warn_too_few():
    f = mm.ranking_stability_check([9, 9, 9], [1, 1, 1])
    assert f.level == "WARN"


def test_ranking_stability_deterministic():
    """Same inputs + seed → identical Finding (mirror discipline)."""
    a = [5, 9, 1, 8, 2, 7, 3, 6, 4, 8]
    b = [6, 1, 9, 2, 8, 3, 7, 4, 6, 2]
    f1 = mm.ranking_stability_check(a, b, seed=0)
    f2 = mm.ranking_stability_check(a, b, seed=0)
    assert f1.msg == f2.msg and f1.level == f2.level


# ─── badge tests ─────────────────────────────────────────────

def test_badge_markdown_certified(tmp_path):
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.4)
    cert = mm.certificate(ledger, "exp1")
    b = mm.badge(cert, fmt="markdown")
    assert "CERTIFIED" in b
    assert "img.shields.io" in b
    assert "brightgreen" in b


def test_badge_svg_contains_seal(tmp_path):
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "exp1", metric="acc", min_n=50, baseline=0.5, pass_threshold=0.4)
    mm.retract(ledger, "exp1", "flaw")
    cert = mm.certificate(ledger, "exp1")
    b = mm.badge(cert, fmt="svg")
    assert b.startswith("<svg")
    assert "REJECTED" in b
    assert cert["seal"] in b          # traceable back to the certificate
    assert "#e05d44" in b             # red for REJECTED


def test_badge_unknown_format_raises(tmp_path):
    ledger = str(tmp_path / "l.jsonl")
    cert = mm.certificate(ledger, "ghost")
    import pytest
    with pytest.raises(ValueError):
        mm.badge(cert, fmt="png")


def test_badge_shields_escaping(tmp_path):
    """Dashes/underscores in claim_id are escaped for the shields URL."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "my-model_v2", metric="acc", min_n=50, baseline=0.5,
                   pass_threshold=0.4)
    cert = mm.certificate(ledger, "my-model_v2")
    b = mm.badge(cert, fmt="markdown")
    assert "my--model__v2" in b
    # verdict CERTIFIED-WITH-WARNINGS would need escaping too
    mm.retract(ledger, "dep", "x")  # unrelated; keep cert CERTIFIED
    assert "img.shields.io/badge/" in b


# ─── verify() three-tier entry point tests ───────────────────

def test_verify_full_runs_all_applicable(tmp_path):
    """FULL tier: probes from multiple groups fire when their inputs exist."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "m1", metric="acc", min_n=50, baseline=0.5,
                   pass_threshold=0.4)
    data = {
        "claim_id": "m1", "metric": "acc", "acc": 0.72, "n": 500,
        "scores": [3, 7, 5, 8, 4, 6, 9, 2, 7, 5],          # judge ⑰
        "matches": [("A", "B", 0), ("B", "C", 0), ("A", "C", 0)],  # ranking ⑲
    }
    findings = mm.verify(ledger, data)
    groups_seen = {mm.group_of(f) for f in findings}
    assert "stats" in groups_seen
    assert "judge" in groups_seen
    assert "ranking" in groups_seen


def test_verify_group_filter(tmp_path):
    """GROUP tier: groups=['judge'] keeps only judge findings."""
    ledger = str(tmp_path / "l.jsonl")
    mm.preregister(ledger, "m1", metric="acc", min_n=50, baseline=0.5,
                   pass_threshold=0.4)
    data = {
        "claim_id": "m1", "acc": 0.72, "n": 500,
        "scores": [3, 7, 5, 8, 4, 6, 9, 2, 7, 5],
    }
    findings = mm.verify(ledger, data, groups=["judge"])
    assert findings, "judge probe should have fired"
    assert all(mm.group_of(f) == "judge" for f in findings)


def test_verify_stats_only_excludes_ledger(tmp_path):
    """groups=['stats'] drops ① ledger findings emitted by the core audit."""
    ledger = str(tmp_path / "l.jsonl")
    data = {"claim_id": "ghost", "acc": 0.72, "n": 500}
    findings = mm.verify(ledger, data, groups=["stats"])
    assert findings
    assert all(mm.group_of(f) == "stats" for f in findings)
    assert not any(f.probe.startswith("①") for f in findings)


def test_verify_unknown_group_raises(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="Unknown group"):
        mm.verify(str(tmp_path / "l.jsonl"), {"acc": 0.7, "n": 100},
                  groups=["statz"])


def test_verify_negative_without_acc(tmp_path):
    """⑬ fires from angles alone — no reported result needed."""
    ledger = str(tmp_path / "l.jsonl")
    for cid in ["a1", "a2", "a3"]:
        mm.preregister(ledger, cid, metric="acc", min_n=50, baseline=0.5,
                       pass_threshold=0.6)
    findings = mm.verify(ledger, {"angles": ["a1", "a2", "a3"]})
    assert any(f.probe.startswith("⑬") for f in findings)


def test_verify_empty_data_no_findings(tmp_path):
    """Empty data dict → nothing to verify → empty list."""
    findings = mm.verify(str(tmp_path / "l.jsonl"), {})
    assert findings == []


def test_verify_ranking_keys(tmp_path):
    """⑳ fires from scores_a + scores_b."""
    findings = mm.verify(str(tmp_path / "l.jsonl"), {
        "scores_a": [9, 8, 9, 9, 8, 9, 8, 9],
        "scores_b": [3, 2, 3, 2, 3, 2, 3, 2],
    })
    assert any(f.probe.startswith("⑳") for f in findings)


def test_groups_registry_covers_all_symbols():
    """Every probe symbol ①–⑳ maps to a group (no orphan probes)."""
    symbols = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩",
               "⑪", "⑫", "⑬", "⑭", "⑮", "⑯", "⑰", "⑱", "⑲", "⑳",
               "㉑", "㉒", "㉓"]
    for s in symbols:
        assert s in mm._SYMBOL_GROUP, f"symbol {s} has no group"
        assert mm._SYMBOL_GROUP[s] in mm.GROUPS


# ─── Grounding probes (㉑㉒㉓) — smoke; full behavior in test_grounding_probes ─
def test_anchor_basis_check_smoke():
    assert mm.anchor_basis_check("structural-argument").level == "WARN"
    assert mm.anchor_basis_check("dynamics-measured").level == "OK"


def test_threshold_provenance_check_smoke():
    assert mm.threshold_provenance_check("observed-distribution").level == "WARN"
    assert mm.threshold_provenance_check("external-fixed").level == "OK"


def test_content_delta_check_smoke():
    assert mm.content_delta_check(["match"]).level == "WARN"
    assert mm.content_delta_check(["match", "incompressibility"]).level == "OK"


def test_anchor_line_source_check_smoke():
    assert mm.anchor_line_source_check("copied-from-other-cell").level == "WARN"
    assert mm.anchor_line_source_check("separator-aligned").level == "OK"


def test_anchor_cell_check_smoke():
    assert mm.anchor_cell_check("threshold-cell").level == "WARN"
    assert mm.anchor_cell_check("deep-regime").level == "OK"


def test_subspace_claim_check_smoke():
    # ㉘ declaration auditor. An empty report has no anchor → FAIL, and the
    # priority rule keeps the ladder from ever reading OK underneath that.
    f = mm.subspace_claim_check({})
    assert [x for x in f if x.probe.endswith("no-anchor")][0].level == "FAIL"
    assert not [x for x in f if x.probe.endswith("null-ladder") and x.level == "OK"]
    # a report with no grid is NOT APPLICABLE for energy matching, not failing
    f = mm.subspace_claim_check({"anchor": {"code_path": "frozen", "tol": 1e-9,
                                            "n_seeds": 10, "guard_seeds": 5}})
    assert [x for x in f if x.probe.endswith("energy-not-matched")][0].level == "N/A"
