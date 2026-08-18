"""🪞 Measurement Mirror — 평가 주장 자동 감사 (훈련0·결정론적).

AI의 "X 달성" 주장이 진짜 신호인지 측정 착시(거짓양성/거짓음성)인지 자동 적발.
규율 원문: Chrysalis/agent_chat/MEASUREMENT_MIRROR.md (7체크).

의존성 범위 — **의존성0인 것은 이 코어와 A층 감사기들뿐이다.** 선택 모듈은
의존성을 가진다: ``judge`` (openai/anthropic), ``subspace`` (㉘ **B층 실행기**,
numpy). 이 단서를 떼고 "의존성0"만 말하는 것이 도감 항목
``catalog/self-catch/zero-dep-scope-overgeneralize.md``가 기록한 과대일반화다.
선택 모듈은 여기서 import하지 않는다 — 그래야 코어 import가 stdlib로 남는다.
"""
from .mm import (
    # ledger + utilities
    preregister, verify_chain, retract, anchor, calibrate, witness,
    certificate, badge,
    # audits — three tiers: verify (full/group) · umbrellas · individual probes
    verify, audit, continuous_audit, full_audit, GROUPS, group_of,
    # probes
    baseline_fairness, gaming_check, leakage_check, multiseed_check,
    scope_check, too_good_check, power_check, multiple_comparisons_check,
    grim_check, falsifiability_check, prereg_lint, cascade_check, negative_audit,
    subspace_claim_check,
    anchor_basis_check, threshold_provenance_check, content_delta_check,
    anchor_line_source_check, anchor_cell_check,
    judge_consistency_check, judge_bias_check, inter_rater_agreement,
    judge_score_sanity, judge_swap_check, judge_transitivity_check,
    ranking_stability_check,
    # helpers
    wilson_ci, lookup_baseline, lookup_reproduction, record_reproduction,
    catch_history, report, Finding, recover_resolution,
    declared_pre_seal_checks,
)

__all__ = [
    "preregister", "verify_chain", "retract", "anchor", "calibrate", "witness",
    "certificate", "badge",
    "verify", "audit", "continuous_audit", "full_audit", "GROUPS", "group_of",
    "baseline_fairness", "gaming_check", "leakage_check", "multiseed_check",
    "scope_check", "too_good_check", "power_check", "multiple_comparisons_check",
    "grim_check", "falsifiability_check", "prereg_lint", "cascade_check", "negative_audit",
    "subspace_claim_check",
    "anchor_basis_check", "threshold_provenance_check", "content_delta_check",
    "anchor_line_source_check", "anchor_cell_check",
    "judge_consistency_check", "judge_bias_check", "inter_rater_agreement",
    "judge_score_sanity", "judge_swap_check", "judge_transitivity_check",
    "ranking_stability_check",
    "wilson_ci", "lookup_baseline", "lookup_reproduction", "record_reproduction",
    "catch_history", "report", "Finding", "recover_resolution",
    "declared_pre_seal_checks",
]
__version__ = "0.38.1"
