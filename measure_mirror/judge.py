"""
🪞 Measurement Mirror — LLM-as-a-Judge runner (optional module).

Install with judge extras:
    pip install "measure-mirror[judge]"

This module provides:
  openai_judge()    — returns a judge callable backed by the OpenAI API
  anthropic_judge() — returns a judge callable backed by the Anthropic API
  judge_run()       — runs the judge, chain-links results to the ledger,
                      and automatically fires probes ⑭⑮⑰ (and ⑱ with
                      swap_positions=True)

Probes ⑭⑮⑯⑰⑱ (judge_consistency_check, judge_bias_check,
inter_rater_agreement, judge_score_sanity, judge_swap_check) live in mm.py
so they stay zero-dependency and can be called standalone with any score list.
⑯ inter_rater_agreement is standalone-only: it is meant for two genuinely
different judges, and re-running the same judge is already covered by ⑭.

Unparseable judge responses score -1 and are excluded from probes; a
`judge-parse` WARN fires when the failure rate exceeds 10%.

Typical workflow
----------------
    from measure_mirror.judge import anthropic_judge, judge_run

    judge_fn = anthropic_judge(model="claude-opus-4-8")
    result   = judge_run(
        "/path/to/ledger.jsonl",
        "my_eval_v1",
        judge_fn=judge_fn,
        items=[{"prompt": p, "a": cand_a, "b": cand_b} for p, cand_a, cand_b in pairs],
        runs=2,       # each item judged twice → ⑭ consistency check
        pairwise=True # A vs B → ⑮ bias check
    )
    for f in result["findings"]:
        print(f"  {f.level}  [{f.probe}]  {f.msg}")

Each item dict shape (pairwise mode):
    {"prompt": str, "a": str, "b": str}

Each item dict shape (rating mode, pairwise=False):
    {"prompt": str, "response": str}
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from typing import Any

from . import mm


# ─────────────────────────────────────────────────────────────
# Default prompt templates
# ─────────────────────────────────────────────────────────────
_DEFAULT_PAIRWISE_TEMPLATE = """\
You are a fair and impartial judge evaluating two AI-generated responses to the same prompt.

[Prompt]
{prompt}

[Response A]
{a}

[Response B]
{b}

Which response is better? Reply with exactly one word: A or B."""

_DEFAULT_RATING_TEMPLATE = """\
Rate the quality of the following AI-generated response on a scale from 1 to 10.
1 = very poor,  5 = acceptable,  10 = excellent.

[Prompt]
{prompt}

[Response]
{response}

Reply with exactly one integer from 1 to 10, nothing else."""


# ─────────────────────────────────────────────────────────────
# Response parsers
# ─────────────────────────────────────────────────────────────
def _parse_pairwise(text: str) -> int:
    """'A' or 'B' → 0 (A wins) or 1 (B wins).  Returns -1 if unparseable."""
    t = text.strip().upper()
    if t.startswith("A"):
        return 0
    if t.startswith("B"):
        return 1
    has_a = "A" in t
    has_b = "B" in t
    if has_a and not has_b:
        return 0
    if has_b and not has_a:
        return 1
    return -1


def _parse_rating(text: str) -> int:
    """First integer found in text → int.  Returns -1 if unparseable."""
    m = re.search(r"\b(\d+)\b", text.strip())
    return int(m.group(1)) if m else -1


# ─────────────────────────────────────────────────────────────
# Ledger helpers (chain-linked judge_run entry)
# ─────────────────────────────────────────────────────────────
def _seal_judge_run(ledger_path: str, entry: dict) -> dict:
    prev_seal = mm._get_last_seal(ledger_path)
    entry["prev_seal"] = prev_seal
    entry["seal"] = hashlib.sha256(
        json.dumps(entry, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    with open(ledger_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


# ─────────────────────────────────────────────────────────────
# Adapter factories
# ─────────────────────────────────────────────────────────────
def openai_judge(
    model: str = "gpt-4o",
    *,
    system_prompt: str | None = None,
    prompt_fn=None,
    pairwise: bool = True,
):
    """Return a judge callable backed by the OpenAI API.

    Args:
        model:         OpenAI model ID (default "gpt-4o").
        system_prompt: Optional system message override.
        prompt_fn:     Optional callable(item) → str that formats the user prompt.
                       If None, the built-in pairwise or rating template is used.
        pairwise:      True = A vs B comparison (returns 0/1),
                       False = absolute rating 1-10 (returns int).

    Returns a judge callable: (item: dict) → int

    Requires: pip install "measure-mirror[judge]" (openai>=1.0)
    """
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError(
            "openai package required. Install: pip install 'measure-mirror[judge]'"
        ) from e

    client = OpenAI()
    _system = system_prompt or (
        "You are a fair and impartial judge evaluating AI responses."
    )
    _prompt_fn = prompt_fn or (
        (lambda item: _DEFAULT_PAIRWISE_TEMPLATE.format(**item)) if pairwise
        else (lambda item: _DEFAULT_RATING_TEMPLATE.format(**item))
    )
    _parse = _parse_pairwise if pairwise else _parse_rating

    def _judge(item: dict) -> int:
        user_prompt = _prompt_fn(item)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _system},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=16,
            temperature=0.0,
        )
        return _parse(resp.choices[0].message.content or "")

    return _judge


def anthropic_judge(
    model: str = "claude-opus-4-8",
    *,
    system_prompt: str | None = None,
    prompt_fn=None,
    pairwise: bool = True,
):
    """Return a judge callable backed by the Anthropic API.

    Args:
        model:         Anthropic model ID (default "claude-opus-4-8").
        system_prompt: Optional system message override.
        prompt_fn:     Optional callable(item) → str that formats the user prompt.
        pairwise:      True = A vs B (returns 0/1), False = rating 1-10 (returns int).

    Returns a judge callable: (item: dict) → int

    Requires: pip install "measure-mirror[judge]" (anthropic>=0.20)
    """
    try:
        from anthropic import Anthropic
    except ImportError as e:
        raise ImportError(
            "anthropic package required. Install: pip install 'measure-mirror[judge]'"
        ) from e

    client = Anthropic()
    _system = system_prompt or (
        "You are a fair and impartial judge evaluating AI responses."
    )
    _prompt_fn = prompt_fn or (
        (lambda item: _DEFAULT_PAIRWISE_TEMPLATE.format(**item)) if pairwise
        else (lambda item: _DEFAULT_RATING_TEMPLATE.format(**item))
    )
    _parse = _parse_pairwise if pairwise else _parse_rating

    def _judge(item: dict) -> int:
        user_prompt = _prompt_fn(item)
        resp = client.messages.create(
            model=model,
            system=_system,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=16,
        )
        content = resp.content[0].text if resp.content else ""
        return _parse(content)

    return _judge


# ─────────────────────────────────────────────────────────────
# Judge runner
# ─────────────────────────────────────────────────────────────
def judge_run(
    ledger_path: str,
    claim_id: str,
    *,
    judge_fn,
    items: list[dict],
    runs: int = 2,
    pairwise: bool = True,
    swap_positions: bool = False,
) -> dict[str, Any]:
    """Run a judge function on items, fire ⑭⑮⑯⑰(⑱) probes, seal into ledger.

    Args:
        ledger_path: Path to the JSONL ledger.
        claim_id:    Claim identifier (links this run to a preregister entry).
        judge_fn:    Callable (item: dict) → int. Use openai_judge() /
                     anthropic_judge() or supply your own.
        items:       List of item dicts.  For pairwise: {"prompt", "a", "b"}.
                     For rating: {"prompt", "response"}.
        runs:        How many times to call judge_fn per item (default 2).
                     Two runs enables the ⑭ consistency check.
        pairwise:    True = A-vs-B scores (0/1);  False = rating scores (int).
                     Controls ⑮ bias check and ledger entry fields.
        swap_positions: If True (pairwise only), each item is additionally
                     judged with a/b swapped and ⑱ judge_swap_check fires.
                     Catches position bias that aggregate win-rate (⑮) misses.

    Parse failures: judge responses that cannot be parsed score -1.  Items with
    a -1 in any run are excluded from all probes; a `judge-parse` WARN fires
    when the failure rate exceeds 10% (FAIL when nothing parsed).

    Returns dict with keys:
        findings       : list[Finding] — probe results
        scores         : list[int] — raw run-1 scores (one per item, may contain -1)
        score_pairs    : list of (run1, run2) tuples if runs >= 2, else None
        swap_scores    : list[int] — swapped-order scores if swap_positions, else None
        parse_failures : number of items excluded due to unparseable responses
        n_items        : number of items evaluated
        runs           : number of repetitions performed
        pairwise       : bool — whether pairwise mode was used
        ledger_entry   : the chain-linked entry appended to the ledger
    """
    if not items:
        return {
            "findings":       [mm.Finding("⑭ judge-consistency", "WARN",
                                          "judge_run called with empty items list.")],
            "scores":         [],
            "score_pairs":    None,
            "swap_scores":    None,
            "parse_failures": 0,
            "n_items":        0,
            "runs":           runs,
            "pairwise":       pairwise,
            "ledger_entry":   None,
        }

    all_run_scores: list[list[int]] = []
    for _ in range(runs):
        run_scores: list[int] = [judge_fn(item) for item in items]
        all_run_scores.append(run_scores)

    # Optional extra pass with positions swapped (⑱)
    swap_scores: list[int] | None = None
    if pairwise and swap_positions:
        swapped_items = [{**item, "a": item["b"], "b": item["a"]}
                         for item in items]
        swap_scores = [judge_fn(item) for item in swapped_items]

    # Exclude items where any run failed to parse (-1) — feeding parse noise
    # into the probes would distort ⑮ bias and ⑰ sanity results.
    n_total = len(items)
    valid_idx = [i for i in range(n_total)
                 if all(run[i] != -1 for run in all_run_scores)]
    parse_failures = n_total - len(valid_idx)
    parse_fail_rate = parse_failures / n_total

    findings: list[mm.Finding] = []
    if parse_failures == n_total:
        findings.append(mm.Finding(
            "judge-parse", "FAIL",
            f"All {n_total} judge responses unparseable — no usable scores. "
            "Check the prompt template / response format."))
    elif parse_fail_rate > 0.10:
        findings.append(mm.Finding(
            "judge-parse", "WARN",
            f"{parse_failures}/{n_total} judge responses unparseable "
            f"({parse_fail_rate:.0%}) — excluded from probes."))

    runs_valid = [[run[i] for i in valid_idx] for run in all_run_scores]

    if valid_idx:
        # ⑭ consistency — requires ≥ 2 runs
        if runs >= 2:
            findings.append(mm.judge_consistency_check(
                list(zip(runs_valid[0], runs_valid[1]))))

        # ⑮ position bias — only meaningful in pairwise mode
        if pairwise:
            findings.append(mm.judge_bias_check(runs_valid[0]))

        # ⑯ inter-rater is NOT auto-fired: run-1 vs run-2 of the same judge is
        # the same signal ⑭ already measures.  Call mm.inter_rater_agreement()
        # directly when you have two genuinely different judges.

        # ⑰ score sanity — always
        findings.append(mm.judge_score_sanity(runs_valid[0]))

        # ⑱ position-swap — judge_swap_check filters -1 pairs internally
        if swap_scores is not None:
            findings.append(mm.judge_swap_check(all_run_scores[0], swap_scores))

    score_pairs = (list(zip(all_run_scores[0], all_run_scores[1]))
                   if runs >= 2 else None)

    # Summarise for ledger
    level_counts: dict[str, int] = {"OK": 0, "WARN": 0, "FAIL": 0}
    for f in findings:
        level_counts[f.level] = level_counts.get(f.level, 0) + 1

    entry: dict = {
        "_type":          "judge_run",
        "ts":             mm._utc_now(),
        "claim_id":       claim_id,
        "n_items":        n_total,
        "runs":           runs,
        "pairwise":       pairwise,
        "parse_failures": parse_failures,
        "findings_ok":    level_counts["OK"],
        "findings_warn":  level_counts["WARN"],
        "findings_fail":  level_counts["FAIL"],
    }
    if runs >= 2 and valid_idx:
        flips = sum(1 for a, b in zip(runs_valid[0], runs_valid[1]) if a != b)
        entry["flip_count"] = flips
        entry["flip_rate"] = round(flips / len(valid_idx), 4)
    if pairwise and valid_idx:
        n_a = sum(1 for s in runs_valid[0] if s == 0)
        entry["a_win_rate"] = round(n_a / len(valid_idx), 4)
    if swap_scores is not None:
        swap_valid = [(f, s) for f, s in zip(all_run_scores[0], swap_scores)
                      if f in (0, 1) and s in (0, 1)]
        if swap_valid:
            locked = sum(1 for f, s in swap_valid if f == s)
            entry["swap_lock_rate"] = round(locked / len(swap_valid), 4)

    ledger_entry = _seal_judge_run(ledger_path, entry)

    return {
        "findings":       findings,
        "scores":         all_run_scores[0],
        "score_pairs":    score_pairs,
        "swap_scores":    swap_scores,
        "parse_failures": parse_failures,
        "n_items":        n_total,
        "runs":           runs,
        "pairwise":       pairwise,
        "ledger_entry":   ledger_entry,
    }
