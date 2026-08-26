"""
🪞 Measurement Mirror — probe engine (no training, pure rule+stat).

Probes ①~㉗:
  ① Pre-registration ledger — append-only chain-hash, first-write wins,
      metric-swap detection, tamper detection, re-registration detection
  ② Fair baseline — crippled / tied / reversed baseline
  ③ Gaming boundary — metric directly in reward/loss
  ④a Small-sample Wilson CI + direction + data leakage (exact hash +
      normalized + token-Jaccard near-dup) + effect-size (continuous metrics)
  ⑤ Multi-seed reproduction — cross-seed variance alarm
  ⑥ Scope — claimed scope wider than tested scope
  ⑦ Too-good — suspiciously large improvement alarm
  ⑧ Power — false-negative guard (n vs. minimum detectable effect)
  ⑨ Multiple comparisons — Bonferroni alarm for k>1 experiments in ledger
  ⑩ GRIM — arithmetic consistency (acc × n must be a whole-number count)
  ⑪ Falsifiability — Popper gate (kill-condition registered? triggered?)
  ⑫ Retraction cascade — claim or transitive dependency retracted?
  ⑬ Negative-claim audit — angle-count gate + scope for Resolved-Negative closures
  ⑭ Judge consistency — LLM judge flip-rate (unreliable judge detector)
  ⑮ Judge position bias — systematic A-wins / B-wins preference
  ⑯ Inter-rater agreement — Cohen's κ for multi-judge setups
  ⑰ Judge score sanity — degenerate scoring distribution
  ⑱ Judge position-swap — AB/BA cross-validation (content vs position lock)
  ⑲ Judge transitivity — A>B>C>A cycle detection in pairwise tournaments
  ⑳ Ranking stability — bootstrap resampling guard against ranking mirages
  ㉑ Anchor basis — positive-control anchor rests on structure, not measured dynamics
  ㉒ Threshold provenance — pass/kill bar re-derived from the observed distribution
  ㉓ Content delta — judgment on agreement alone, rubber-stampable
  ㉔ Anchor line source — anchor line copied from another cell
  ㉕ Anchor cell — anchor cell sits on the threshold boundary
  ㉖ Known confounds — confounds declared before results (INFO declaration)
  ㉗ Prereg lint — seal QUALITY before compute: kill-condition leaked into the
      metric field, quantified kill with no structured threshold, pass bar
      at/below chance, min_n below floor, no pre-seal machine-checks declared

Three verification tiers (사용 3단계):
  verify(ledger, data)                — FULL: every probe whose inputs are present
  verify(ledger, data, groups=[...]) — GROUP: restrict to named groups
  <probe>(...)                        — INDIVIDUAL: call any probe directly

Groups (GROUPS registry):
  ledger   ①⑫  pre-registration, chain integrity, retraction cascade
  stats    ④⑤⑦⑧⑨⑩  statistical validity of the numbers
  design   ②③⑥⑪  experiment-design fairness
  negative ⑬  Resolved-Negative closure gate
  judge    ⑭⑮⑯⑰⑱  LLM-judge reliability
  ranking  ⑲⑳  leaderboard integrity

Utilities:
  calibrate()   — self-test: run 5 synthetic known-good/known-bad cases
  anchor()      — tamper-evident ledger snapshot for external archival
  witness()     — execute a command and seal a tamper-evident run record
  retract()     — append a chain-linked retraction entry to the ledger
  certificate() — issue a sealed verification certificate for a claim
  badge()       — render a certificate as a markdown / SVG badge

Design:
  - Zero dependencies (Python stdlib only). Deterministic. No trained model.
  - Each probe is an independent function. Add without touching existing ones.
  - Ledger = append-only JSONL + chain hash + first-write wins + SHA-256 seal.
"""
from __future__ import annotations
import json, math, time, hashlib, os, random, re, statistics
from dataclasses import dataclass


# ─────────────────────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────────────────────
@dataclass
class Finding:
    probe: str
    level: str   # OK / WARN / FAIL
    msg: str
    data: dict | None = None
    """Optional structured payload.

    Probes that compute numbers a caller may want to act on (recovered
    dimension, per-arm p-values, …) attach them here instead of stuffing them
    into ``msg``.

    Compatibility, stated honestly:
      · ``Finding(probe, level, msg)`` — unchanged (the field is defaulted).
      · attribute access, ``==`` between two Findings — unchanged.
      · ``dataclasses.astuple(f)`` / ``asdict(f)`` — **CHANGED**: now 4 elements
        / 4 keys. Code comparing against a 3-tuple literal breaks. This is a
        real break, not a theoretical one; it is accepted because no in-repo
        caller does it (`astuple`/`asdict` on Finding: 0 hits) and the
        alternative — encoding numbers in ``msg`` — is what this field exists
        to stop.
    """


def _utc_now() -> str:
    """Sealed timestamps are UTC with an explicit 'Z'.

    Not cosmetic. `preregister`, `retract` and the judge log used to write
    `time.strftime("%Y-%m-%dT%H:%M:%S")` — local wall-clock with **no timezone
    marker at all** — while anchors in this same file, and the sibling action /
    provenance ledgers, already wrote UTC+Z. Sealed entries from the two families
    therefore sat on different clocks and nothing in the string said so.

    That breaks the one audit a hash-chained ledger is uniquely able to answer:
    *did the seal exist before the result did?* Measured on a real ledger
    (2026-08-15): comparing 28 claims whose seal and resolution were both
    recorded, the naive comparison reported **28 of 28 out of order** — i.e.
    "every claim was sealed after its result was known". Normalising the two
    clocks flipped it to 28 of 28 correctly ordered. The failure direction is
    the dangerous one: it accuses the ledger's own author of peeking.

    Legacy naive timestamps stay as they are — they are sealed, and a rewrite
    would break the chain. They remain ambiguous by construction; only entries
    written from here on carry their timezone.
    """
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ─────────────────────────────────────────────────────────────
# ① Pre-registration ledger (append-only, chain-hashed)
# ─────────────────────────────────────────────────────────────
def _seal_of(raw: bytes):
    """`seal` of one raw ledger line, or None if it has none / does not parse.

    Bytes, not str: the tail reader below seeks into the file and cannot rely on
    text-mode decoding of a chunk boundary. A line that is not a JSON *object*
    (a bare number, a list) has no seal and must not raise — real ledgers in this
    house contain such lines, and `entry["seal"]` on an int is a TypeError.
    """
    line = raw.strip()
    if not line:
        return None
    try:
        entry = json.loads(line.decode("utf-8"))
    except Exception:
        return None
    return entry["seal"] if isinstance(entry, dict) and "seal" in entry else None


def _get_last_seal(ledger_path: str, _chunk: int = 8192) -> str:
    """The seal of the last sealed entry — read from the END of the file.

    This runs on EVERY append. Parsing the whole ledger to find its last line makes
    append O(n): measured 2026-08-26 on the family ledger (5,676 entries / 4.6 MB)
    one lookup spent **56.18 ms** here, against **0.085 ms** for this tail read on the
    same file — and the old cost grows with every entry ever written, so the ledger
    gets slower precisely because it is being used. (The number is re-measured, not
    inherited: a handoff carried 39.0 ms and then 47.98 ms for the same call; the
    ledger had simply grown between readings.)

    Ported from action-mirror's `_get_last_seal`, which has run this way since
    2026-08. The one deliberate difference is the empty-ledger answer: measure-mirror
    says lowercase `"genesis"` and action-mirror says `"GENESIS"`. That is not a typo
    to tidy up — the string is hashed into every first entry, so changing it would
    invalidate the head of every existing measure-mirror chain.

    Deliberately NOT cached in memory: this ledger is appended by other processes
    (cron jobs, sibling agents), and a cached head would hand out a prev_seal that is
    no longer last, forking the chain. The file stays the single source of truth;
    only the amount of it we read changes.

    Semantics are unchanged, including the awkward cases: unsealed or unparseable
    trailing lines are skipped, a ledger with no sealed entry at all still answers
    `genesis`, and CRLF / CR / LF endings all read the same — text mode used to
    normalise those for us.
    """
    if not os.path.exists(ledger_path):
        return "genesis"
    with open(ledger_path, "rb") as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        buf = b""
        while pos > 0:
            step = min(_chunk, pos)
            pos -= step
            f.seek(pos)
            buf = f.read(step) + buf
            # Split on every line ending, not just \n. Reading bytes means universal-newline
            # translation no longer happens for us: a ledger written with CR-only endings
            # would parse as ONE line and the lookup would answer genesis — which would
            # append a second genesis entry into the middle of a live chain.
            parts = buf.replace(b"\r\n", b"\n").replace(b"\r", b"\n").split(b"\n")
            # parts[0] may be the tail of a line that starts earlier in the file —
            # only safe to read once we have reached the beginning.
            head, complete = parts[0], parts[1:]
            for line in reversed(complete):
                seal = _seal_of(line)
                if seal is not None:
                    return seal
            if pos == 0:
                seal = _seal_of(head)
                if seal is not None:
                    return seal
                break
            buf = head
    return "genesis"


def preregister(ledger_path: str, claim_id: str, *, metric: str,
                min_n: int, baseline: float, pass_threshold: float,
                kill_condition: str | None = None,
                kill_threshold: dict | None = None,
                depends_on: list[str] | None = None,
                metric_range: list | str | None = None,
                chance: float | None = None,
                anchor_basis: str | None = None,
                threshold_source: str | None = None,
                anchor_cell: str | None = None,
                anchor_line_source: str | None = None,
                known_confounds: list[str] | None = None,
                pre_seal_checks: list[str] | None = None) -> dict:
    """Seal evaluation criteria BEFORE seeing results.

    Each entry is cryptographically linked to the previous one (chain hash).
    Re-registration for the same claim_id is silently ignored — only the
    first registration counts in audit().

    kill_condition: human-readable description of what would falsify the claim,
        e.g. "accuracy drops below 0.55 on held-out test".
    kill_threshold: structured auto-evaluable form:
        {"metric": "acc", "threshold": 0.55, "direction": "below"}
        direction "below": FAIL when reported_acc < threshold.
        direction "above": FAIL when reported_acc > threshold (error metrics).
        Both can be provided together. Claims with neither are flagged
        "unfalsifiable" by falsifiability_check() at audit time.
    depends_on: list of claim_ids this claim builds on. If any of those claims
        is later retracted, this claim is flagged STALE by cascade_check().
    anchor_basis / threshold_source: optional grounding declarations (SPEC
        amendment A1). Declare the positive-control anchor's basis
        ("dynamics-measured" | "structural-argument") and the pass/kill
        threshold's provenance ("external-fixed" | "observed-distribution")
        at seal time; audit() reads them back and runs the ㉑/㉒ grounding
        probes automatically.
    anchor_cell / anchor_line_source / known_confounds: optional grounding
        declarations (SPEC amendment A2). anchor_cell ("deep-regime" |
        "threshold-cell") and anchor_line_source ("separator-aligned" |
        "copied-from-other-cell") complete the anchor-discipline trio with
        anchor_basis; audit() reads them back and runs ㉔/㉕. known_confounds
        (list of strings) records confounds declared BEFORE results — a
        pre-declared confound legitimizes later attribution cycles; audit()
        surfaces them as an INFO finding (declaration, not a verdict).
    pre_seal_checks: list of cheap machine-checks run BEFORE sealing (e.g.
        "reachability-smoke", "mass-balance-audit", "neutral-control",
        "manipulation-check", "positive-control"). _preseal_lint()/prereg_lint()
        read them back; declaring none draws an INFO nudge. These are the
        checks that catch a KILL before compute is spent.
        An entry may be a bare name, or an object recording what the check
        returned — {"name": "neutral-control", "result": "not_fired", "n": 30},
        any extra keys preserved. A bare name declares work without recording
        it, so the lint WARNs (⑫h) and no later audit can aggregate its outcome;
        read them back with declared_pre_seal_checks().

    Chain link: deleting or inserting entries breaks the chain and is
    detected by verify_chain(). Complete ledger replacement is NOT caught
    here — use git commit anchoring for that guarantee.
    """
    prev_seal = _get_last_seal(ledger_path)
    entry: dict = {
        "ts": _utc_now(),
        "claim_id": claim_id,
        "metric": metric,
        "min_n": min_n,
        "baseline": baseline,
        "pass_threshold": pass_threshold,
        "prev_seal": prev_seal,
    }
    if kill_condition is not None:
        entry["kill_condition"] = kill_condition
    if kill_threshold is not None:
        # Validate the structured form at seal time — fail fast, while it can
        # still be fixed. A malformed threshold accepted here would otherwise
        # only surface as a KeyError inside audit()/falsifiability_check(), and
        # because pre-registration is first-write-wins it could not be corrected
        # by re-registering the same claim_id.
        if isinstance(kill_threshold, dict):
            if "threshold" not in kill_threshold:
                raise ValueError(
                    "kill_threshold must contain a numeric 'threshold' key "
                    "(structured form: {'metric', 'threshold', 'direction'}). "
                    "For a free-text criterion, use kill_condition= instead.")
            try:
                float(kill_threshold["threshold"])
            except (TypeError, ValueError):
                raise ValueError(
                    "kill_threshold['threshold'] must be numeric, got "
                    f"{kill_threshold['threshold']!r}.")
            direction = kill_threshold.get("direction", "below")
            if direction not in ("below", "above"):
                raise ValueError(
                    "kill_threshold['direction'] must be 'below' or 'above', "
                    f"got {direction!r}.")
        entry["kill_threshold"] = kill_threshold
    if depends_on:
        entry["depends_on"] = depends_on
    if metric_range is not None:
        entry["metric_range"] = metric_range
    if chance is not None:
        entry["chance"] = chance
    if anchor_basis is not None:
        entry["anchor_basis"] = anchor_basis
    if threshold_source is not None:
        entry["threshold_source"] = threshold_source
    if anchor_cell is not None:
        entry["anchor_cell"] = anchor_cell
    if anchor_line_source is not None:
        entry["anchor_line_source"] = anchor_line_source
    if known_confounds:
        entry["known_confounds"] = list(known_confounds)
    if pre_seal_checks:
        # Validate at seal time — fail fast while it can still be fixed. A dict
        # entry with no `name` names no check, and pre-registration is
        # first-write-wins, so it could not be corrected under the same claim_id.
        for c in pre_seal_checks:
            if isinstance(c, dict) and not str(c.get("name") or "").strip():
                raise ValueError(
                    "pre_seal_checks entry is an object with no 'name': "
                    f"{c!r}. Use {{'name': '<check>', 'result': '<what it returned>'}} "
                    "or a bare check name.")
            if not isinstance(c, (str, dict)) or (isinstance(c, str) and not c.strip()):
                raise ValueError(
                    f"pre_seal_checks entry must be a check name or an object: {c!r}")
        entry["pre_seal_checks"] = list(pre_seal_checks)
    entry["seal"] = hashlib.sha256(
        json.dumps(entry, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    with open(ledger_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def _load_prereg(ledger_path: str, claim_id: str) -> dict | None:
    """Return the FIRST preregister entry for claim_id (skips witness/anchor entries)."""
    if not os.path.exists(ledger_path):
        return None
    with open(ledger_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Only preregister entries — witness/anchor have explicit _type
            if e.get("claim_id") == claim_id and "_type" not in e:
                return e
    return None


def _falsifiability_eval(pre: dict, reported_acc: float | None) -> Finding:
    """Internal: evaluate kill-condition from an already-loaded pre-registration entry."""
    kill_cond  = pre.get("kill_condition")
    kill_thresh = pre.get("kill_threshold")

    if kill_cond is None and kill_thresh is None:
        return Finding("⑪ falsifiability", "WARN",
                       f"Unfalsifiable: '{pre['claim_id']}' has no kill-condition. "
                       "Add kill_condition= or kill_threshold= to preregister().")

    if kill_thresh is not None:
        if reported_acc is None:
            return Finding("⑪ falsifiability", "WARN",
                           "Kill threshold registered but result not yet provided "
                           "— cannot evaluate kill condition.")
        metric    = kill_thresh.get("metric", pre.get("metric", "?"))
        # Guard already-sealed ledgers that predate seal-time validation: a
        # malformed threshold degrades to WARN instead of crashing every
        # downstream audit()/falsifiability_check().
        try:
            thr = float(kill_thresh["threshold"])
        except (KeyError, TypeError, ValueError):
            return Finding("⑪ falsifiability", "WARN",
                           f"Malformed kill_threshold for '{pre['claim_id']}' "
                           "(no numeric 'threshold') — cannot auto-evaluate. "
                           "Re-register under a new claim_id with the structured "
                           "form, or use kill_condition= for a text criterion.")
        direction = kill_thresh.get("direction", "below")
        triggered = (
            (direction == "below" and reported_acc < thr) or
            (direction == "above" and reported_acc > thr)
        )
        text = f" [{kill_cond}]" if kill_cond else ""
        if triggered:
            op = "<" if direction == "below" else ">"
            return Finding("⑪ falsifiability", "FAIL",
                           f"Kill condition triggered{text}: "
                           f"{metric}={reported_acc} {op} {thr}. "
                           f"Claim '{pre['claim_id']}' is falsified by its own "
                           "pre-registered criterion.")
        op = "≥" if direction == "below" else "≤"
        return Finding("⑪ falsifiability", "OK",
                       f"Kill condition not triggered{text}: "
                       f"{metric}={reported_acc} {op} {thr}.")

    # kill_condition text-only (no structured threshold)
    return Finding("⑪ falsifiability", "OK",
                   f"Falsifiable (text-only): '{kill_cond}'. "
                   "Add kill_threshold= for automatic evaluation.")


# ─────────────────────────────────────────────────────────────
# ㉗ Pre-seal lint — QUALITY of the seal, not just its presence.
#
# falsifiability_check(⑪) and the compute gate ask "does a kill-condition
# exist?". This asks "is the seal well-formed enough that the automated
# checks can actually fire, and is the bar meaningful?" — the failure
# classes a real arc lost silent compute to:
#   ⑫a  kill-condition prose leaked into the `metric` field (a malformed
#       tool call) → the human eye sees a criterion, the parser sees none.
#   ⑫b  quantified kill written as free text with no structured threshold
#       → falsifiability_check can never auto-evaluate it.
#   ⑫c  the pass bar sits at or below chance → nothing to clear.
#   ⑫d  min_n below a small-sample floor.
#   ⑫e  no cheap pre-seal machine-checks declared (reachability / accounting
#       / neutral-control / manipulation) — the checks that catch a KILL
#       before compute is spent.
#   ⑫h  a declared pre-seal check that recorded nothing about itself → the
#       list names work but carries no outcome, so no later audit can
#       aggregate it (the ⑫b/⑫g shape, one field over).
#   ⑫g  a structured kill_threshold that names no metric → the bar is sealed
#       but nothing says what it is a bar OF, so auto-evaluation has no key
#       to look for. The mirror image of ⑫b.
# Pure over a single pre-registration dict; no I/O.
# ─────────────────────────────────────────────────────────────

# Tokens that signal a falsification criterion has been written as prose.
_KILL_WORDS = (
    "kill", "falsif", "reject", "fail if", "fail when", "reject_if", "reject if",
    "철회", "죽", "사망", "기각", "미만", "이상", "이하", "초과", "떨어지", "넘으면",
    "below", "above", "drops", "exceeds", "less than", "greater than",
)
_CMP_CHARS = ("<", ">", "≤", "≥", "=")

# A well-formed metric is a short identifier ("acc", "separation_d", "bpb_ko").
# A leaked kill-condition is a sentence: it has spaces AND kill-language.
_METRIC_LEAK_RE = re.compile(r"\s")


def _looks_like_kill_prose(text: str) -> bool:
    """True if `text` reads like a falsification criterion rather than a metric name."""
    if not text or not _METRIC_LEAK_RE.search(text):
        return False  # single token → a real metric name, not a leaked sentence
    low = text.lower()
    has_word = any(w in low for w in _KILL_WORDS)
    has_cmp = any(c in text for c in _CMP_CHARS)
    has_num = any(ch.isdigit() for ch in text)
    return has_word or (has_cmp and has_num)


# A number written in a *comparison* context — "below 0.55", "acc < 0.5", "0.3 미만".
# Requires a comparison word/operator adjacent to a digit, so incidental numbers
# (sha256 hashes, dates like 20260720, "n=600", filenames "v2", "§6", "protocol=0002")
# do NOT read as a quantified threshold. Validated against 64 real ledgers (A3 audit).
_QUANT_CMP_WORDS = (
    "below", "above", "drops", "exceeds", "less than", "greater than",
    "미만", "이상", "이하", "초과",
)
_QUANT_WORD_NUM = re.compile(
    "(?:" + "|".join(_QUANT_CMP_WORDS) + r")\D{0,8}\d", re.IGNORECASE)
_QUANT_NUM_WORD = re.compile(r"\d\s*(?:" + "|".join(_QUANT_CMP_WORDS) + ")")
_QUANT_OP_NUM = re.compile(r"[<>≤≥]\s*=?\s*\d")


def _has_quantified_comparison(text: str) -> bool:
    """True if `text` states a numeric threshold in a comparison context (not an
    incidental number). Basis for ⑫b — 'you wrote a number you could structure'."""
    if not text:
        return False
    return bool(_QUANT_WORD_NUM.search(text)
                or _QUANT_NUM_WORD.search(text)
                or _QUANT_OP_NUM.search(text))


# Recognised pre-seal machine-checks (declared via preregister(pre_seal_checks=...)).
KNOWN_PRESEAL_CHECKS = (
    "reachability-smoke",     # is the answer already determined in the code?
    "mass-balance-audit",     # does the accounting balance?
    "neutral-control",        # does a should-do-nothing arm do nothing?
    "manipulation-check",     # does the intended lever actually move its proxy?
    "positive-control",       # does a known-true anchor reproduce?
)


def _preseal_entries(checks) -> list[dict]:
    """Normalise a pre_seal_checks list to dicts, keeping the bare/structured
    distinction in `_bare`. A bare string names a check and records nothing about
    it; a dict may carry `result`, `n`, `artifact_sha256`, whatever the author had.
    Entries that are neither are dropped — a check nobody can name is not a check.
    """
    out = []
    for c in checks or ():
        if isinstance(c, str) and c.strip():
            out.append({"name": c.strip(), "_bare": True})
        elif isinstance(c, dict):
            name = str(c.get("name") or "").strip()
            if name:
                out.append({**c, "name": name, "_bare": False})
    return out


def declared_pre_seal_checks(ledger_path, claim_id: str) -> list[dict]:
    """The pre-seal checks a claim declared, normalised to dicts.

    Each entry has at least `name`, plus `_bare=True` when the seal recorded only
    the name and nothing a machine can read back. Whatever else the author sealed
    (`result`, `n`, `artifact_sha256`, …) is passed through untouched.

    This is the accessor an audit aggregates over — e.g. collecting the outcome of
    every declared `neutral-control` across a ledger. Entries sealed as bare strings
    have no outcome to collect, which is the gap ⑫h warns about at seal time.
    Returns [] when the claim has no pre-registration or declared no checks.
    """
    pre = _load_prereg(ledger_path, claim_id)
    return _preseal_entries(pre.get("pre_seal_checks")) if pre else []


def _preseal_lint(pre: dict) -> list["Finding"]:
    """㉗ Lint a pre-registration for seal-quality defects. Returns a list of Findings
    (may be empty). Complements falsifiability_check: that asks *whether* a kill-
    condition exists; this asks whether the seal is well-formed and its bar meaningful.
    """
    findings: list[Finding] = []
    P = "㉗ prereg-lint"
    cid = pre.get("claim_id", "?")
    metric = pre.get("metric") or ""
    kill_cond = pre.get("kill_condition")
    kill_thr = pre.get("kill_threshold")

    # ⑫a — kill-condition leaked into the metric field.
    if kill_cond is None and kill_thr is None and _looks_like_kill_prose(metric):
        findings.append(Finding(
            P, "FAIL",
            f"'{cid}': the metric field reads like a kill-condition "
            f"({metric[:60]!r}...) but kill_condition/kill_threshold are empty. "
            "The criterion likely leaked into `metric` from a malformed call — "
            "re-seal under a new claim_id with the text in kill_condition= "
            "(and a structured kill_threshold= if it is numeric)."))

    # ⑫f — genuinely unfalsifiable (neither field, and not a detectable leak).
    elif kill_cond is None and kill_thr is None:
        findings.append(Finding(
            P, "WARN",
            f"'{cid}' has no kill-condition (unfalsifiable). "
            "Add kill_condition= or kill_threshold=."))

    # ⑫b — quantified kill written as free text with no structured threshold.
    # Fire only on a number in a COMPARISON context: an incidental digit (a sha256,
    # a date, "n=600", a filename "v2", "§6") is not a threshold you could structure.
    if kill_thr is None and kill_cond and _has_quantified_comparison(kill_cond):
        findings.append(Finding(
            P, "WARN",
            f"'{cid}' kill_condition names a threshold ({kill_cond[:50]!r}) but has no "
            "structured kill_threshold= — falsifiability_check cannot auto-evaluate it. "
            "Add kill_threshold={'metric','threshold','direction'}."))

    # ⑫g — a threshold that does not say what it is a threshold OF.
    # `preregister` validates that `threshold` is numeric and `direction` is below/above,
    # but accepts a kill_threshold with no `metric` at all. Auto-evaluation then has no
    # key to look for in the sealed result, so falsifiability_check can never grade the
    # claim by itself — the mirror image of ⑫b, and just as blinding.
    if isinstance(kill_thr, dict) and not str(kill_thr.get("metric") or "").strip():
        findings.append(Finding(
            P, "WARN",
            f"'{cid}' kill_threshold sets a bar ({kill_thr.get('threshold')!r}) but names "
            "no metric — nothing says what quantity it is a threshold of, so "
            "falsifiability_check cannot auto-evaluate this claim later. "
            "Add kill_threshold={'metric': '<the quantity>', ...}."))

    # ⑫c — pass bar at or below chance.
    # Floor = an EXPLICITLY declared `chance` only. In practice `baseline` is a
    # comparison-arm score (e.g. 0.92, or the other arm in a two-arm compare), not the
    # random floor — using it here produced 44 false FAILs across 64 real ledgers (A3
    # audit). Also skip: pass_threshold that is 0/absent (a placeholder for a claim whose
    # real bar is the kill_threshold), and non-[0,1]/unbounded metrics (pass is then a
    # delta/margin, not an absolute score comparable to an absolute chance).
    pass_thr = pre.get("pass_threshold")
    chance = pre.get("chance")
    metric_range = pre.get("metric_range")
    bounded_accuracy = metric_range is None or metric_range == [0, 1]
    if (chance is not None and bounded_accuracy
            and pass_thr not in (None, 0, 0.0)):
        try:
            if 0 < float(pass_thr) <= float(chance):
                findings.append(Finding(
                    P, "FAIL",
                    f"'{cid}' pass_threshold={pass_thr} is at or below the declared "
                    f"chance level ({chance}) — a claim clearing this bar has cleared "
                    "nothing. (If this is a delta/improvement target, declare an "
                    "unbounded metric_range so the bar isn't read as an absolute score.)"))
        except (TypeError, ValueError):
            pass

    # ⑫d — underpowered small-sample floor.
    min_n = pre.get("min_n")
    if isinstance(min_n, (int, float)) and min_n < 20:
        findings.append(Finding(
            P, "WARN",
            f"'{cid}' min_n={min_n} is below the small-sample floor (20). "
            "A signal at this n is easily a lucky draw — raise min_n or run mm_power_check."))

    # ⑫e — no cheap pre-seal machine-checks declared.
    checks = pre.get("pre_seal_checks")
    if not checks:
        findings.append(Finding(
            P, "INFO",
            f"'{cid}' declares no pre-seal machine-checks. Before spending compute, "
            "run and declare the cheap ones (pre_seal_checks=[...]): "
            + ", ".join(KNOWN_PRESEAL_CHECKS) + "."))
    else:
        entries = _preseal_entries(checks)
        names = [e["name"] for e in entries]
        unknown = [n for n in names if n not in KNOWN_PRESEAL_CHECKS]
        note = f" (unrecognised: {unknown})" if unknown else ""
        findings.append(Finding(
            P, "OK",
            f"'{cid}' declared pre-seal checks: {', '.join(names)}{note}."))

        # ⑫h — a declared check that recorded nothing about itself.
        # The list is a claim about work, carried inside the artifact whose whole
        # purpose is to make claims checkable. WARN, not FAIL: bare strings are
        # legitimate for checks with no artifact, and a FAIL here would invalidate
        # every seal already written.
        bare = [e["name"] for e in entries if e["_bare"]]
        if bare:
            findings.append(Finding(
                P, "WARN",
                f"'{cid}' declares {len(bare)} pre-seal check(s) with nothing recorded "
                f"about them ({', '.join(bare)}) — a reader cannot tell these ran. "
                "Seal each as an object instead: {'name': '<check>', 'result': "
                "'<what it returned>'} (plus 'n', 'artifact_sha256', … as they apply), "
                "so a later audit can aggregate the outcome instead of the intention."))

    return findings


def prereg_lint(ledger_path: str, claim_id: str | None = None) -> list["Finding"]:
    """㉗ Lint pre-registration(s) in a ledger for seal-quality defects.

    claim_id=None lints every pre-registration in the ledger. Returns a flat list of
    Findings (empty means clean). This is the ledger-level entry point behind the
    mm_prereg_lint MCP tool; _preseal_lint() is the pure per-record core.
    """
    findings: list[Finding] = []
    if not os.path.exists(ledger_path):
        return [Finding("㉗ prereg-lint", "WARN",
                        f"No ledger at '{ledger_path}'.")]
    if claim_id is not None:
        pre = _load_prereg(ledger_path, claim_id)
        if pre is None:
            return [Finding("㉗ prereg-lint", "WARN",
                            f"No pre-registration for '{claim_id}'.")]
        return _preseal_lint(pre)
    seen: set = set()
    with open(ledger_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("_type") is not None:
                continue  # witness / anchor / retraction
            cid = e.get("claim_id")
            if cid is None or cid in seen:
                continue  # first-write-wins, matches _load_prereg
            seen.add(cid)
            findings.extend(_preseal_lint(e))
    return findings


_LEGACY_SEAL_LEN = 16   # pre-v0.19 truncated seals — see _seal_matches


def _seal_matches(stored: str, full_hex: str) -> bool:
    """Match a stored seal against the full SHA-256 hex digest.

    Entries are now sealed with the FULL 64-hex digest: the old 16-hex (64-bit)
    truncation lets a dishonest sealer birthday-search (~2^32 hashes) a pair of
    different entries sharing one seal, undermining tamper evidence. Legacy
    16-hex seals remain verifiable via prefix match — their (weaker) proof
    strength is unchanged; the upgrade protects entries sealed from now on.
    """
    if stored == full_hex:
        return True
    return len(stored) == _LEGACY_SEAL_LEN and stored == full_hex[:_LEGACY_SEAL_LEN]


def _verify_seal(entry: dict) -> bool:
    """Recompute SHA-256 seal. Accepts full (current) and legacy-truncated seals.

    Seal recomputation only — chain linkage (incl. the mandatory prev_seal per
    SPEC §4 rule 3) is enforced separately in verify_chain / linkage_check."""
    stored = entry.get("seal", "")
    check = {k: v for k, v in entry.items() if k != "seal"}
    full = hashlib.sha256(
        json.dumps(check, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return _seal_matches(stored, full)


def verify_chain(ledger_path: str) -> list[Finding]:
    """Verify full ledger integrity: individual seals + chain links.

    Catches: tampered entries, deleted entries, inserted entries.
    Does NOT catch: complete ledger file deletion + fresh re-registration
    (use git commit anchoring for that guarantee).
    """
    if not os.path.exists(ledger_path):
        return [Finding("① chain-integrity", "OK", "Empty ledger.")]

    entries = []
    bad_lines = []
    with open(ledger_path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                bad_lines.append(i)

    if bad_lines:
        return [Finding("① chain-integrity", "FAIL",
            f"Malformed JSON at line(s) {bad_lines}. Ledger corrupted.")]

    if not entries:
        return [Finding("① chain-integrity", "OK", "Empty ledger.")]

    findings = []
    prev_seal = "genesis"

    for i, entry in enumerate(entries):
        cid = entry.get("claim_id", "?")

        if not _verify_seal(entry):
            findings.append(Finding("① chain-integrity", "FAIL",
                f"Seal mismatch at entry {i + 1} (claim_id={cid}). Entry was tampered."))
            prev_seal = entry.get("seal", "")
            continue

        # Chain link — SPEC §4 rule 3: a missing prev_seal is treated as the
        # empty string, so the §5 comparison fails naturally. An entry without
        # prev_seal is NOT trusted silently — stripping prev_seal to hide a
        # deletion/reorder is a downgrade attack, not a legacy pass.
        # (SPEC §5.1: the genesis marker is case-insensitive — action-mirror
        # ledgers write "GENESIS" where measure-mirror writes "genesis".)
        entry_prev = str(entry.get("prev_seal", ""))
        link_ok = (entry_prev.lower() == "genesis" if i == 0
                   else entry_prev == prev_seal)
        if not link_ok:
            findings.append(Finding("① chain-integrity", "FAIL",
                f"Chain break before entry {i + 1} (claim_id={cid}). "
                f"Expected prev={prev_seal[:8]}…, got {entry_prev[:8] or '(missing)'}…. "
                f"An entry was deleted/inserted, or prev_seal was stripped."))

        prev_seal = entry.get("seal", "")

    if not findings:
        return [Finding("① chain-integrity", "OK",
            f"Chain intact — {len(entries)} entries verified.")]
    return findings


def linkage_check(path: str) -> tuple[bool, str, list | None]:
    """Format-agnostic prev_seal→seal linkage — the SINGLE SOURCE of this check
    for the stack verifiers.

    Unlike `verify_chain()`, this does NOT recompute measure-mirror's own seal,
    so it works on ANY mirror ledger (claims / actions / provenance): it only
    confirms that each entry's `prev_seal` points at the previous entry's `seal`,
    rooted at "genesis". A break means an entry was inserted, deleted, or
    reordered after sealing. Stdlib only.

    Returns ``(ok, message, entries)`` — ``entries`` is the parsed list when the
    ledger was readable (so callers needn't re-read it), else ``None``. Both
    `stack/verify_self.py:generic_linkage` and the outsider `mirror-stack-verify`
    CLI use this one definition so they cannot drift apart.
    """
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as e:
        return False, f"ledger unreadable: {e}", None
    except UnicodeDecodeError as e:
        # SPEC §3.1: bytes that don't decode as UTF-8 are malformed content,
        # not an unreadable file.
        return False, f"malformed JSON in ledger: not valid UTF-8 ({e})", None
    try:
        entries = [json.loads(l) for l in text.splitlines() if l.strip()]
    except json.JSONDecodeError as e:
        return False, f"malformed JSON in ledger: {e}", None
    # SPEC §3.1/§6.1 step 2: a line that parses as JSON but is not an object
    # (e.g. `42`, `[1,2]`) is malformed, same as unparseable JSON.
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            return False, f"malformed JSON in ledger: entry {i} is not an object", None
    if not entries:
        return False, "ledger is empty", []
    prev = None
    for i, e in enumerate(entries):
        declared = str(e.get("prev_seal", ""))
        if i == 0:
            if declared.lower() != "genesis":
                return False, f"first entry prev_seal={declared!r} is not 'genesis'", entries
        elif declared != prev:
            return False, f"linkage broken at entry {i}: prev_seal {declared} != {prev}", entries
        prev = str(e.get("seal", ""))
    return True, f"linkage intact — {len(entries)} entries, head={prev[:16]}", entries


# ─────────────────────────────────────────────────────────────
# ④a-1 Small-sample confidence interval (Wilson score, binomial)
# ─────────────────────────────────────────────────────────────
def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    p = max(0.0, min(1.0, k / n))
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


# ─────────────────────────────────────────────────────────────
# ④a-2 Exact small-sample distinguishability (two-sided binomial test)
# Wilson's normal approximation is over-optimistic right at the boundary; for
# small n the exact two-sided binomial test is the correct method (the one
# scipy.stats.binomtest implements, but pure-python — no scipy dependency).
# eval/self_fpfn/v2 measured ~1.3% boundary over-optimism in the Wilson path.
# ─────────────────────────────────────────────────────────────
_EXACT_MAX_N = 10_000  # exact is cheap O(n) here; Wilson ≈ exact above this


def binom_two_sided_p(k: int, n: int, p0: float) -> float:
    """Exact two-sided binomial test p-value: k successes in n under H0 p=p0.

    Matches scipy.stats.binomtest(k, n, p0, alternative='two-sided') — sums the
    pmf of every outcome no more likely than the observed one. Pure-python,
    log-space (no overflow). Returns 1.0 for degenerate inputs.
    """
    if n <= 0:
        return 1.0
    k = max(0, min(n, int(k)))
    if p0 <= 0.0:
        return 1.0 if k == 0 else 0.0
    if p0 >= 1.0:
        return 1.0 if k == n else 0.0
    logp, log1mp, lgn = math.log(p0), math.log1p(-p0), math.lgamma(n + 1)

    def _logpmf(i: int) -> float:
        return lgn - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * logp + (n - i) * log1mp

    thresh = _logpmf(k) + 1e-7          # rel-tolerance for float ties (scipy-style)
    total = 0.0
    for i in range(n + 1):
        lp = _logpmf(i)
        if lp <= thresh:
            total += math.exp(lp)
    return min(1.0, total)


# ─────────────────────────────────────────────────────────────
# ⑩ GRIM — arithmetic consistency check
# ─────────────────────────────────────────────────────────────
def _infer_decimals(x: float) -> int:
    """Infer reported decimal places from Python's float repr (strips trailing zeros)."""
    s = str(x)
    if "." in s:
        frac = s.split(".")[1].rstrip("0")
        return len(frac) if frac else 0
    return 0


def grim_check(reported_acc: float, n: int, *,
               n_decimals: int | None = None, items: int = 1) -> Finding:
    """⑩ GRIM test: verify that acc × n is arithmetically possible.

    Works for both a proportion (k/n) and a MEAN of integers (sum/N, e.g. a
    Likert 1–7 average). There must exist an integer k such that
    round(k/N, d) == reported_acc; if none does, the number was fabricated or
    n was mis-reported. (k may exceed N for a mean — see the k≥0 note below.)

    items: number of items averaged per subject (default 1). A mean of `items`
    integer responses from each of `n` subjects has granularity N = n·items
    (the GRIM paper's standard form). For a single-item scale or a plain
    proportion, items=1.

    Current audit() silently does round(acc × n) and hides this signal —
    this probe makes it explicit.

    n_decimals: decimal places in the reported value. Auto-detected from the
    float if not provided (works for typical reporting like 0.72, 0.715).

    SCOPE — small samples only. GRIM's power is granularity: with small N few
    values are reachable. Once N ≳ 10^d (e.g. a 2-decimal mean at n ≥ 100) every
    value is reachable and GRIM can flag nothing. It also catches only ARITHMETIC
    impossibility, not distributional fabrication (a large fake dataset usually
    passes GRIM; digit/distribution forensics catch those — out of scope).
    """
    if n <= 0:
        return Finding("⑩ GRIM", "WARN", f"n={n} ≤ 0 — cannot run GRIM check.")
    if items < 1:
        return Finding("⑩ GRIM", "WARN", f"items={items} < 1 — cannot run GRIM check.")

    N = n * items   # granularity denominator
    d = n_decimals if n_decimals is not None else _infer_decimals(reported_acc)
    d = max(d, 1)  # at minimum 1 decimal place

    k_lo = math.floor(reported_acc * N)
    k_hi = k_lo + 1
    target = round(reported_acc, d)
    gran = f"n={n}" if items == 1 else f"n={n}×items={items}=N={N}"

    # k >= 0 only: a proportion has k ≤ N, but a MEAN of integers (e.g. a
    # Likert 1–7 average like 5.18) has k = mean·N > N. Capping at N silently
    # assumed proportions and wrongly failed valid means — caught dog-fooding
    # the GRIM paper's own example (mean 5.18, n=28). See db/curated/self_catches.
    for k in (k_lo, k_hi):
        if k >= 0 and round(k / N, d) == target:
            return Finding("⑩ GRIM", "OK",
                f"acc={reported_acc} consistent with {gran} "
                f"(k={k}, {k}/{N}={k/N:.{d+2}f} → {round(k/N, d)}).")

    return Finding("⑩ GRIM", "FAIL",
        f"acc={reported_acc} is arithmetically impossible for {gran}. "
        f"No integer k satisfies round(k/{N}, {d}) = {target}. "
        f"(candidates: k={k_lo} → {round(k_lo/N, d)}, "
        f"k={k_hi} → {round(k_hi/N, d)}). "
        f"Fabricated value or mis-reported n.")


# ─────────────────────────────────────────────────────────────
# ④a-2 Data leakage (exact hash + normalized + token-Jaccard near-dup)
# ─────────────────────────────────────────────────────────────
def _normalize_text(x) -> str:
    """Lowercase, strip punctuation, collapse whitespace — for near-dup matching."""
    s = re.sub(r"[^\w\s]", " ", str(x).lower())
    return re.sub(r"\s+", " ", s).strip()


def _tokens(x) -> set:
    return set(_normalize_text(x).split())


def leakage_check(train_items, test_items, *, fuzzy: bool = True,
                  jaccard_threshold: float = 0.7) -> Finding:
    """Detect train∩test contamination.

    Tiered, most-confident first:
      1. exact hash intersection            -> FAIL (identical items)
      2. normalized match (case/space/punct) -> FAIL (trivial near-dup)
      3. token-Jaccard ≥ threshold           -> WARN (likely paraphrase; review)

    SCOPE — fuzzy matching is lexical. A semantic paraphrase whose token overlap
    falls below `jaccard_threshold` (e.g. heavy rewording) is NOT caught; that
    needs embedding-based matching, which is out of scope (a hand-tuned low
    threshold would just trade misses for false alarms). Set fuzzy=False for the
    exact-only behaviour.
    """
    def H(xs):
        return {hashlib.sha256(str(x).encode()).hexdigest() for x in xs}
    th, eh = H(train_items), H(test_items)
    inter = th & eh
    if inter:
        frac = len(inter) / max(1, len(eh))
        return Finding("④a data-leakage", "FAIL",
            f"train∩test = {len(inter)} items ({frac:.1%} of test) exact-match. Contaminated.")
    if not fuzzy:
        return Finding("④a data-leakage", "OK", "train∩test = 0 (exact). No leakage.")

    # 2. normalized-exact: differs only in case / whitespace / punctuation
    nt = {n for n in (_normalize_text(x) for x in train_items) if n}
    norm_hits = [x for x in test_items if _normalize_text(x) in nt]
    if norm_hits:
        return Finding("④a data-leakage", "FAIL",
            f"{len(norm_hits)} test item(s) match a train item after normalization "
            f"(case/whitespace/punctuation). Contaminated.")

    # 3. token-Jaccard near-duplicate (lower confidence -> WARN)
    train_tok = [t for t in (_tokens(x) for x in train_items) if t]
    near = 0
    example = 0.0
    for x in test_items:
        et = _tokens(x)
        if not et:
            continue
        best = max((len(et & tt) / len(et | tt) for tt in train_tok), default=0.0)
        if best >= jaccard_threshold:
            near += 1
            example = max(example, best)
    if near:
        return Finding("④a data-leakage", "WARN",
            f"{near} test item(s) are near-duplicates of a train item "
            f"(token Jaccard ≥ {jaccard_threshold:.2f}; max {example:.2f}). "
            f"Possible paraphrase contamination — review.")

    return Finding("④a data-leakage", "OK",
        "train∩test = 0 (exact, normalized, token-Jaccard). No leakage detected "
        "(semantic paraphrase below threshold needs embedding matching — out of scope).")


# ─────────────────────────────────────────────────────────────
# ② Fair baseline
# ─────────────────────────────────────────────────────────────
def baseline_fairness(name: str, claimed: float, baseline: float, *,
                      higher_better: bool = True, margin: float = 0.01,
                      n: int | None = None) -> Finding:
    """② Is the claimed metric a genuine advantage over the baseline?

    The fixed `margin` is n-blind: a Δ above it can still be sampling noise. When
    `n` is supplied (accuracy-style proportions, higher_better=True), additionally
    require the claimed value's 95% Wilson CI to actually exclude the baseline —
    otherwise the "advantage" is not statistically distinguishable. n is ignored
    for error-style metrics (higher_better=False), where the proportion model
    does not apply.
    """
    diff = (claimed - baseline) if higher_better else (baseline - claimed)
    if diff <= -margin:
        return Finding("② fair-baseline", "FAIL",
            f"{name}: claimed {claimed:.3f} is WORSE than baseline {baseline:.3f}. "
            f"Baseline wins — claim invalid.")
    if abs(diff) < margin:
        return Finding("② fair-baseline", "FAIL",
            f"{name}: claimed {claimed:.3f} ≈ baseline {baseline:.3f} "
            f"(Δ{diff:+.3f} < {margin}). Tied — no genuine advantage.")
    if n is not None and n > 0 and higher_better:
        k = round(claimed * n)
        if n <= _EXACT_MAX_N:
            # Exact two-sided binomial test — the correct small-sample method
            # (Wilson is over-optimistic at the boundary; see eval/self_fpfn/v2).
            p = binom_two_sided_p(k, n, baseline)
            if p > 0.05:
                return Finding("② fair-baseline", "FAIL",
                    f"{name}: claimed {claimed:.3f} beats baseline {baseline:.3f} "
                    f"(Δ{diff:+.3f} > margin {margin}) but at n={n} an exact binomial "
                    f"test gives p={p:.3f} > 0.05 — not statistically distinguishable.")
            return Finding("② fair-baseline", "OK",
                f"{name}: claimed {claimed:.3f} beats baseline {baseline:.3f} "
                f"(Δ{diff:+.3f}; n={n} exact binomial p={p:.3f} ≤ 0.05 — distinguishable).")
        lo, hi = wilson_ci(k, n)
        if lo <= baseline <= hi:
            return Finding("② fair-baseline", "FAIL",
                f"{name}: claimed {claimed:.3f} beats baseline {baseline:.3f} "
                f"(Δ{diff:+.3f} > margin {margin}) but at n={n} the 95% CI "
                f"[{lo:.3f}, {hi:.3f}] still includes the baseline — "
                f"not statistically distinguishable.")
        return Finding("② fair-baseline", "OK",
            f"{name}: claimed {claimed:.3f} beats baseline {baseline:.3f} "
            f"(Δ{diff:+.3f}; n={n} 95% CI [{lo:.3f}, {hi:.3f}] excludes baseline).")
    return Finding("② fair-baseline", "OK",
        f"{name}: claimed {claimed:.3f} beats baseline {baseline:.3f} (Δ{diff:+.3f}).")


# ─────────────────────────────────────────────────────────────
# Local memory DB lookups (baselines + prior reproductions)
#
# These read the LOCAL db/ directory — your own record of past audits.
# Not a shared/crowd database: the value is "warn future-me about patterns
# past-me already got burned by", which works regardless of how private the
# data is (it never leaves your machine).
# ─────────────────────────────────────────────────────────────
def lookup_baseline(task: str | None, db_dir: str | None = None) -> float | None:
    if not task:
        return None
    p = os.path.join(db_dir or "db", "measured", "baselines.json")
    if not os.path.exists(p):
        return None
    try:
        db = json.load(open(p, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None        # missing/corrupt db → degrade; unexpected errors surface
    e = db.get(task)
    return e.get("baseline") if isinstance(e, dict) else None


def lookup_reproduction(task: str | None, db_dir: str | None = None) -> list[dict]:
    """Return prior FAILED reproductions recorded for this task in db/.

    Reads db/reproductions.jsonl — your local memory of claims that did not
    survive a larger-sample reproduction. When you later audit a new claim on
    the same task, audit() surfaces these so you don't re-fall for a pattern
    you already disproved (e.g. "MuSR 55.6% at n=9" → 0.385 at n=1050).

    Returns the matching records (verdict == "FAIL"); empty list if none.
    """
    if not task:
        return []
    p = os.path.join(db_dir or "db", "measured", "reproductions.jsonl")
    if not os.path.exists(p):
        return []
    out: list[dict] = []
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "_doc" in e:                       # skip header/comment rows
                    continue
                if e.get("task") == task and e.get("verdict") == "FAIL":
                    out.append(e)
    except OSError:
        return []          # unreadable db → degrade; unexpected errors surface
    return out


def record_reproduction(task: str, *, claim: str,
                        acc_claimed: float, n_claimed: int,
                        acc: float, n: int,
                        baseline: float | None = None,
                        note: str = "", source: str = "",
                        db_dir: str | None = None) -> dict:
    """Append a reproduction result to db/reproductions.jsonl — local memory grows.

    This is the WRITE companion to lookup_reproduction(). The verdict is judged
    automatically from the reproduction's own Wilson CI vs the task baseline:
    if the lower bound does not clear the baseline, the reproduction FAILED
    (the original claim did not survive a larger sample) and future audits on
    this task will warn about it.

    Recording is explicit by design — audit() does NOT auto-record, because an
    audit FAIL ("this single claim is statistically weak") is not the same as a
    reproduction failure ("I re-ran it at larger n and it collapsed"). You call
    this when you actually reproduced something.

    Returns the appended record (matching the db/reproductions.jsonl schema).
    """
    if baseline is None:
        b = lookup_baseline(task, db_dir)
        baseline = b if b is not None else 0.5
    lo, _ = wilson_ci(round(acc * n), n)
    verdict = "FAIL" if lo <= baseline else "PASS"
    entry = {
        "claim":        claim,
        "task":         task,
        "n_claimed":    n_claimed,
        "acc_claimed":  acc_claimed,
        "reproduction": {"n": n, "acc": acc},
        "verdict":      verdict,
        "note":         note,
        "source":       source,
    }
    p = os.path.join(db_dir or "db", "measured", "reproductions.jsonl")
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


# Catch log: structured history of what you've already caught.
# Not auto-wired into audit() — matching a new claim is fuzzy text (no clean
# task key), so auto-warning would mean false positives. Searchable, not dead.
_CATCH_FILES = {
    "self_catch":     ("curated/self_catches.jsonl",          "jsonl"),
    "false_negative": ("curated/false_negative_guards.jsonl", "jsonl"),
    "gaming":         ("curated/gaming_patterns.json",         "patterns"),
    "contamination":  ("curated/contamination.jsonl",          "jsonl"),
    "closure":        ("curated/research_closures.jsonl",      "jsonl"),
}


def catch_history(*, kind: str | None = None, source: str | None = None,
                  db_dir: str | None = None) -> list[dict]:
    """Query the local catch log — past detections across the db/ catch files.

    Each returned record is tagged with its `kind`:
      self_catch     — a false positive you flagged on your own work
      false_negative — a false negative you re-checked before believing
      gaming         — a gaming / mirage signature you've seen
      contamination  — data leakage you found
      closure        — a qualitative research closure (negative conclusion with
                       no quantitative acc/n — NOT a measure-mirror verdict)

    Filters (optional): `kind` restricts to one catch type; `source` matches
    the originating arc/source string (jsonl files only). Returns [] if nothing
    matches or the files are absent. Read-only — this is memory, not an audit.
    """
    base = db_dir or "db"
    out: list[dict] = []
    for k, (fname, fmt) in _CATCH_FILES.items():
        if kind is not None and k != kind:
            continue
        p = os.path.join(base, fname)
        if not os.path.exists(p):
            continue
        try:
            if fmt == "jsonl":
                with open(p, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            e = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if "_doc" in e:
                            continue
                        if source is not None and e.get("source") != source:
                            continue
                        out.append({"kind": k, **e})
            else:  # patterns: a single JSON with a "patterns" list
                d = json.load(open(p, encoding="utf-8"))
                if source is not None:
                    continue   # pattern records carry no source field
                for pat in d.get("patterns", []):
                    out.append({"kind": k, **pat})
        except (OSError, json.JSONDecodeError):
            continue       # missing/corrupt db file → skip; unexpected errors surface
    return out


# ─────────────────────────────────────────────────────────────
# ③ Gaming boundary — metric directly in reward/loss
# ─────────────────────────────────────────────────────────────
def gaming_check(metric: str, reward_terms: list[str]) -> Finding:
    metric_lower = metric.lower()
    hits = [t for t in reward_terms if metric_lower in t.lower()]
    if hits:
        return Finding("③ gaming", "FAIL",
            f"Eval metric '{metric}' found in reward/loss terms {hits}. Self-fulfilling.")
    return Finding("③ gaming", "OK",
        f"Eval metric '{metric}' not in reward/loss. No gaming detected.")


# ─────────────────────────────────────────────────────────────
# ⑤ Multi-seed reproduction
# ─────────────────────────────────────────────────────────────
def multiseed_check(seed_results: list[float], *, baseline: float = 0.5,
                    cv_threshold: float = 0.10) -> Finding:
    if len(seed_results) < 2:
        return Finding("⑤ multi-seed", "WARN",
            f"Only {len(seed_results)} seed result(s) — cannot verify reproducibility.")
    mean = statistics.mean(seed_results)
    std = statistics.stdev(seed_results)
    cv = std / mean if mean != 0 else float("inf")
    lo, hi = min(seed_results), max(seed_results)
    if lo <= baseline <= hi:
        return Finding("⑤ multi-seed", "FAIL",
            f"Seed range [{lo:.3f}, {hi:.3f}] includes baseline({baseline}). Unstable.")
    if cv >= cv_threshold:
        return Finding("⑤ multi-seed", "WARN",
            f"CV={cv:.2%} ≥ {cv_threshold:.0%}. mean={mean:.3f}, std={std:.3f}.")
    return Finding("⑤ multi-seed", "OK",
        f"{len(seed_results)} seeds: mean={mean:.3f}, std={std:.3f}, CV={cv:.2%}. Stable.")


# ─────────────────────────────────────────────────────────────
# ⑥ Scope — over-generalization
# ─────────────────────────────────────────────────────────────
def scope_check(claimed_scope, tested_scope) -> Finding:
    tested = set(tested_scope)
    untested = [c for c in claimed_scope if c not in tested]
    if untested:
        return Finding("⑥ scope", "FAIL",
            f"Claimed {untested} not tested (evidence={list(tested_scope)}). "
            f"Over-generalization.")
    return Finding("⑥ scope", "OK",
        f"Claimed scope ⊆ tested scope {list(tested_scope)}.")


# ─────────────────────────────────────────────────────────────
# ㉑㉒㉓ Grounding probes — mutual-grounding arc sealed defense laws.
# Analogy from a micro-substrate learning-loop experiment; STRUCTURE only,
# not ported numbers (scope: micro-substrate·40 gens·single attack family·
# N≤8·median verdict). Design doc: docs/GROUNDING_PROBES_DESIGN.md
# ─────────────────────────────────────────────────────────────
_ANCHOR_DYNAMICS = {"dynamics-measured", "dynamics", "measured", "empirical"}
_ANCHOR_STATIC = {"structural-argument", "structural", "guaranteed",
                  "static", "by-construction"}


def anchor_basis_check(anchor_basis: str) -> Finding:
    """㉑ A positive-control anchor must rest on the substrate's MEASURED
    DYNAMICS, not a static 'it's structurally guaranteed' argument.

    Grounds: mutual-grounding arc M11b (seal ef5fdb20) — a 'structurally
    guaranteed' anchor was refuted by consumption dynamics (the vote wiring
    worked 100%, yet resource depletion self-limited the attack, so the anchor
    failed). Static structural argument ≠ anchor. Catalog:
    anchor-reproduction-failure (structural-guarantee subtype, 3rd real case).
    Scope: micro-substrate analogy — structure only, no ported numbers.
    """
    basis = str(anchor_basis).strip().lower()
    if basis in _ANCHOR_DYNAMICS:
        return Finding("㉑ anchor-basis", "OK",
                       "PC anchor rests on measured dynamics of the substrate.")
    if basis in _ANCHOR_STATIC:
        return Finding("㉑ anchor-basis", "WARN",
                       "PC anchor rests on a static structural argument "
                       "('guaranteed by construction'). A structural guarantee "
                       "can be refuted by the substrate's own dynamics "
                       "(consumption/depletion) — anchors must be validated by a "
                       "measured dynamics smoke test (illusion: "
                       "anchor-reproduction-failure, structural-guarantee subtype).")
    return Finding("㉑ anchor-basis", "WARN",
                   f"Unrecognized anchor_basis {anchor_basis!r} — declare "
                   "'dynamics-measured' or 'structural-argument'.")


_THRESH_EXTERNAL = {"external-fixed", "external", "fixed", "human-fixed",
                    "preregistered"}
_THRESH_OBSERVED = {"observed-distribution", "observed", "adaptive",
                    "self-calibrated", "data-driven"}


def threshold_provenance_check(threshold_source: str) -> Finding:
    """㉒ A pass/kill threshold must be EXTERNALLY FIXED, not re-derived from the
    observed submission distribution.

    Grounds: mutual-grounding arc M9b (c79e541a) / M10b (eb64d325) — a threshold
    moved by the observed distribution is self-calibrating; an attacker floods
    low-quality submissions to drag it down (strictly worse than a fixed
    threshold). Even 'uncontaminable source' variants failed (M10). Scope:
    micro-substrate analogy — structure only.
    """
    src = str(threshold_source).strip().lower()
    if src in _THRESH_EXTERNAL:
        return Finding("㉒ threshold-provenance", "OK",
                       "Threshold is externally fixed.")
    if src in _THRESH_OBSERVED:
        return Finding("㉒ threshold-provenance", "WARN",
                       "Threshold derived from the observed submission "
                       "distribution is self-calibrating — an attacker drags it "
                       "down by flooding low-quality submissions (worse than "
                       "fixed; even uncontaminable-source variants failed). "
                       "Fix the threshold externally.")
    return Finding("㉒ threshold-provenance", "WARN",
                   f"Unrecognized threshold_source {threshold_source!r} — declare "
                   "'external-fixed' or 'observed-distribution'.")


_MATCH_TERMS = {"match", "agreement", "similarity", "consistency", "accuracy",
                "overlap"}
_CONTENT_TERMS = {"content-delta", "incompressibility", "change-magnitude",
                  "cxpl", "compression", "length", "novelty"}


def content_delta_check(judgment_basis) -> Finding:
    """㉓ Judgment resting on agreement/match ALONE is rubber-stampable by
    near-identity claims — require an incompressibility / change-magnitude
    (content-delta) check.

    Grounds: mutual-grounding arc M5 (1990c34c) — a match-only gate is
    rubber-stamped by near-identity (contentless) claims; belief/depth metrics
    are blind, only a content check (incompressibility/length, cxpl-type)
    detects it. Scope: micro-substrate analogy — structure only.
    """
    basis = judgment_basis if isinstance(judgment_basis, (list, tuple)) else [judgment_basis]
    basis_l = [str(b).strip().lower() for b in basis]
    has_match = any(b in _MATCH_TERMS for b in basis_l)
    has_content = any(b in _CONTENT_TERMS for b in basis_l)
    if has_content:
        return Finding("㉓ content-delta", "OK",
                       "Judgment includes a content-delta "
                       "(incompressibility / change-magnitude) check.")
    if has_match:
        return Finding("㉓ content-delta", "WARN",
                       "Judgment rests on agreement/match alone — "
                       "rubber-stampable by near-identity (contentless) claims. "
                       "Add an incompressibility / change-magnitude "
                       "(content-delta) check.")
    return Finding("㉓ content-delta", "WARN",
                   f"Unrecognized judgment_basis {judgment_basis!r} — declare "
                   "match-type and/or content-delta terms.")


# ㉔㉕ Anchor-discipline probes — the other two anchor-reproduction-failure
# subtypes (㉑ already covers 'measured dynamics, not static guarantee').
# Catalog: catalog/fn-guard/anchor-reproduction-failure.md (3 real cases).
# Analogy from a micro-substrate experiment; STRUCTURE only, no ported numbers.
_ANCHOR_LINE_ALIGNED = {"separator-aligned", "sealed-separator", "aligned",
                        "sealed"}
_ANCHOR_LINE_COPIED = {"copied-from-strong", "copied-from-other-cell", "copied",
                       "borrowed"}


def anchor_line_source_check(anchor_line_source: str) -> Finding:
    """㉔ A positive-control anchor LINE must be aligned with the sealed
    separatrix of THIS cell, not copied from a stronger/other cell.

    Grounds: anchor-reproduction-failure 'anchor-line copy' subtype (M7b, am
    seal 50537aa6) — a PC1 anchor line 0.6 copied from a strong-pathology cell
    (SOLO8 bg~0.97) onto a mild cell (MUT8, prior 0.61~0.68) made a fresh-seed
    median 0.593 (inside the collapse zone) read as anchor failure, blocking the
    whole grid. The anchor line must be set to match the sealed separatrix.
    Scope: micro-substrate analogy — structure only, no ported numbers.
    """
    src = str(anchor_line_source).strip().lower()
    if src in _ANCHOR_LINE_ALIGNED:
        return Finding("㉔ anchor-line", "OK",
                       "Anchor line is aligned with this cell's sealed separatrix.")
    if src in _ANCHOR_LINE_COPIED:
        return Finding("㉔ anchor-line", "WARN",
                       "Anchor line copied from a stronger/other cell — a line "
                       "fit to a strong-pathology cell misjudges a mild cell "
                       "(fresh-seed median inside the collapse zone read as "
                       "anchor failure, blocking the grid). Align the anchor line "
                       "to THIS cell's sealed separatrix (illusion: "
                       "anchor-reproduction-failure, anchor-line-copy subtype).")
    return Finding("㉔ anchor-line", "WARN",
                   f"Unrecognized anchor_line_source {anchor_line_source!r} — "
                   "declare 'separator-aligned' or 'copied-from-other-cell'.")


_ANCHOR_CELL_DEEP = {"deep-regime", "deep", "interior"}
_ANCHOR_CELL_EDGE = {"threshold-cell", "boundary-cell", "threshold", "boundary",
                     "edge"}


def anchor_cell_check(anchor_cell: str) -> Finding:
    """㉕ A positive-control anchor CELL must sit in a deep regime, away from the
    threshold — a cell sitting on the threshold itself straddles the boundary
    seed-to-seed and cannot reproduce stably.

    Grounds: anchor-reproduction-failure 'threshold-cell' subtype (M8, am seal
    4a839158) — even with a separatrix-aligned line, a PC cell placed at the
    grounding threshold itself (N2T16, T*=16) crossed the boundary per seed
    group (bg 0.37→0.46→0.53) and failed to reproduce. A separatrix-aligned
    line is not enough; the anchor cell must be a deep-regime cell.
    Scope: micro-substrate analogy — structure only, no ported numbers.
    """
    cell = str(anchor_cell).strip().lower()
    if cell in _ANCHOR_CELL_DEEP:
        return Finding("㉕ anchor-cell", "OK",
                       "Anchor cell sits in a deep regime, away from the threshold.")
    if cell in _ANCHOR_CELL_EDGE:
        return Finding("㉕ anchor-cell", "WARN",
                       "Anchor cell sits on the threshold/boundary — it straddles "
                       "the boundary seed-to-seed and cannot reproduce stably "
                       "(even with a separatrix-aligned line). Move the anchor to "
                       "a deep-regime cell (illusion: anchor-reproduction-failure, "
                       "threshold-cell subtype).")
    return Finding("㉕ anchor-cell", "WARN",
                   f"Unrecognized anchor_cell {anchor_cell!r} — declare "
                   "'deep-regime' or 'threshold-cell'.")


# ─────────────────────────────────────────────────────────────
# ⑦ Too-good — suspiciously large improvement
# ─────────────────────────────────────────────────────────────
def too_good_check(name: str, claimed: float, baseline: float, *,
                   suspicious_margin: float = 0.30) -> Finding:
    diff = claimed - baseline
    if diff >= suspicious_margin:
        return Finding("⑦ too-good", "WARN",
            f"{name}: Δ={diff:+.3f} ≥ {suspicious_margin}. "
            f"Suspiciously large — check for measurement defects first.")
    return Finding("⑦ too-good", "OK", f"{name}: Δ={diff:+.3f} — within normal range.")


# ─────────────────────────────────────────────────────────────
# ⑧ Power — false-negative guard
# ─────────────────────────────────────────────────────────────
def power_check(n: int, baseline: float, *,
                min_detectable_effect: float = 0.05,
                alpha: float = 0.05,
                target_power: float = 0.80) -> Finding:
    """Warn when n is too small to detect the minimum detectable effect.

    Closes the gap between "bidirectional" (false positive AND negative)
    and the actual implementation — false negatives are silently missed
    without this probe.

    Uses a two-sample z-test approximation for binary proportion metrics.
    Defaults: alpha=0.05 (two-sided 95% CI), target_power=0.80.
    """
    # Derive critical values from the actual alpha/target_power arguments.
    # (Previously hardcoded to 1.96/0.842 — the message printed the requested
    #  power while n was always computed at 80%: the text and the number lied
    #  to each other. statistics.NormalDist is stdlib, so this stays zero-dep.)
    z_alpha2 = statistics.NormalDist().inv_cdf(1 - alpha / 2)
    z_beta = statistics.NormalDist().inv_cdf(target_power)
    p1 = min(1.0, baseline + min_detectable_effect)
    var = (baseline * (1 - baseline) + p1 * (1 - p1)) / 2  # pooled under H1
    n_required = math.ceil(
        ((z_alpha2 + z_beta) ** 2 * var) / (min_detectable_effect ** 2)
    )
    if n < n_required:
        return Finding("⑧ power", "WARN",
            f"n={n} insufficient to detect Δ={min_detectable_effect:+.2f} above "
            f"baseline={baseline} at {target_power:.0%} power (need n≥{n_required}). "
            f"High false-negative risk — a true effect may go undetected.")
    return Finding("⑧ power", "OK",
        f"n={n} ≥ {n_required} — sufficient for Δ={min_detectable_effect:+.2f} "
        f"at {target_power:.0%} power.")


# ─────────────────────────────────────────────────────────────
# ⑨ Multiple comparisons — garden-of-forking-paths
# ─────────────────────────────────────────────────────────────
def multiple_comparisons_check(ledger_path: str, *, alpha: float = 0.05) -> Finding:
    """Detect k>1 distinct experiments in the same ledger (Bonferroni alarm).

    Running k experiments and reporting only the best inflates the
    false-positive rate. Shows the Bonferroni-corrected alpha = alpha/k.

    Best practice: use separate ledgers per independent project, or
    pre-register all k hypotheses before running any of them.
    """
    if not os.path.exists(ledger_path):
        return Finding("⑨ multiple-comparisons", "OK",
            "No ledger — single experiment assumed.")

    unique_claims: set[str] = set()
    with open(ledger_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                cid = e.get("claim_id")
                if cid:
                    unique_claims.add(cid)
            except json.JSONDecodeError:
                continue

    k = len(unique_claims)
    if k <= 1:
        return Finding("⑨ multiple-comparisons", "OK",
            f"k={k} — single experiment, no correction needed.")

    corrected = alpha / k
    return Finding("⑨ multiple-comparisons", "WARN",
        f"k={k} distinct experiments in ledger → "
        f"Bonferroni α={corrected:.4f} (not {alpha}). "
        f"95% CI threshold is too lenient. "
        f"Use separate ledgers per project, or pre-register all k hypotheses.")


# ─────────────────────────────────────────────────────────────
# ⑪ Falsifiability — Popper gate
# ─────────────────────────────────────────────────────────────
_NEG_VERDICTS = ("KILL", "FAIL", "FALSIF", "RETRACT", "NEGATIVE", "REJECT")
_POS_VERDICTS = ("PASS", "SUPPORTED", "CONFIRMED", "WORTH", "OK")
_RESULT_KEYS = ("reported_acc", "acc", "result", "value", "metric_value", "reported_value")


def _norm_metric_name(s) -> str:
    # Exact-after-trim comparison only. No separator folding and no substring
    # matching: a registry alias that folded "human-eval" to "human eval" fired
    # on human-EVALUATION score columns, and substring verdict markers have
    # over-captured four separate times in one project's ledger audits. A missed
    # match keeps the WARN path; a false one grades the wrong quantity.
    return str(s).strip().casefold()
# Payload keys that carry a categorical verdict. Non-ASCII keys are here because
# ledgers written by Korean-language agents use them; a resolution recorded under
# "판정" is just as sealed as one under "verdict".
_VERDICT_KEYS = ("verdict", "판정", "결과")
# Free-text fallbacks, tried in order — first match wins, so the *headline* verdict
# is recovered when a sentence also mentions a secondary one
# (e.g. "… = KILL(delta below bar) · monotone PASS" resolves to KILL, not PASS).
_VERDICT_PATTERNS = (
    r"VERDICT\b.*?=\s*([A-Za-z_][\w-]*)",          # "VERDICT c1 = KILL"
    r"\bverdict\b[^:=\n]{0,60}[:=]\s*([A-Za-z_][\w-]*)",   # "verdict <name>: KILL(…)"
    r"판정\s*[:=]\s*\W{0,3}([A-Za-z_][\w-]*)",      # "M7c 판정: 🔴DISPERSION_FRAGILE"
    r"결과\s*[:=]\s*\W{0,3}([A-Za-z_][\w-]*)",      # "<claim> 결과=PASS(scope=…)"
)


def _recover_resolution_detail(ledger_path, claim_id: str, am_ledger=None, metric=None):
    """Internal recover_resolution that also reports HOW a number was found:

      'attributed' — the payload attributes its number to the sealed quantity:
                     {"metric": "<the sealed name>", "value": …}
      'named-key'  — the payload carries the number under a key equal to the
                     sealed metric name (exact after trim/casefold — never
                     substring, never separator-folded)
      'bare'       — a number under a generic result key, with no metric name
      'verdict' / 'retracted' — as before.

    The tier lets the caller say honestly whether the graded number is *known*
    to be of the sealed quantity or merely assumed to be. A number the payload
    explicitly attributes to a DIFFERENT metric is not recovered at all — not
    even as a bare candidate — because grading a measurement of some other
    quantity against this claim's threshold is a misrecovery, and a
    misrecovered resolution is a wrong answer.
    """
    def _paths(p):
        if p is None:
            return []
        return [p] if isinstance(p, (str, bytes, os.PathLike)) else [str(x) for x in p]

    files = _paths(ledger_path)
    files += [p for p in _paths(am_ledger) if p not in files]
    want = _norm_metric_name(metric) if metric else None
    attributed, named, bare, verdict = None, None, None, None
    for f in files:
        if not os.path.exists(f):
            continue
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("_type") == "retraction" and e.get("claim_id") == claim_id:
                    return "retracted", e.get("reason", ""), "retracted"
                if e.get("_type") == "action" and e.get("target") == claim_id:
                    pv = e.get("payload") if isinstance(e.get("payload"), dict) else {}
                    declared = pv.get("metric")
                    declared = (_norm_metric_name(declared)
                                if isinstance(declared, str) and declared.strip() else None)
                    num = next((float(pv[kk]) for kk in _RESULT_KEYS
                                if isinstance(pv.get(kk), (int, float))
                                and not isinstance(pv.get(kk), bool)), None)
                    if want:
                        if attributed is None and declared == want and num is not None:
                            attributed = num
                        if named is None:
                            for k, v in pv.items():
                                if (_norm_metric_name(k) == want
                                        and isinstance(v, (int, float))
                                        and not isinstance(v, bool)):
                                    named = float(v)
                                    break
                        if bare is None and declared is None and num is not None:
                            bare = num
                    elif bare is None and num is not None:
                        bare = num
                    if verdict is None:
                        v = next((pv[k] for k in _VERDICT_KEYS
                                  if isinstance(pv.get(k), str) and pv[k].strip()), None)
                        if v is None:
                            text = e.get("action", "") or ""
                            for pat in _VERDICT_PATTERNS:
                                m = re.search(pat, text, re.I)
                                if m:
                                    v = m.group(1)
                                    break
                        verdict = v
    if attributed is not None:
        return "acc", attributed, "attributed"
    if named is not None:
        return "acc", named, "named-key"
    if bare is not None:
        return "acc", bare, "bare"
    if verdict is not None:
        return "verdict", verdict, "verdict"
    return None, None, None


def recover_resolution(ledger_path, claim_id: str, am_ledger=None, metric=None):
    """Find a *sealed* resolution for claim_id so falsifiability can self-evaluate.

    Returns (kind, value):
      ('retracted', reason)  — a retraction is sealed for the claim,
      ('acc', float)         — an am_record(target=claim_id) carries a numeric result,
      ('verdict', 'KILL'…)   — an am_record(target=claim_id) carries a categorical verdict,
      (None, None)           — nothing sealed yet.

    `ledger_path` and `am_ledger` each accept a path or a sequence of paths, because a
    project's claims routinely live across many ledger files; passing one concatenated
    file would otherwise be forced on the caller. A retraction wins; otherwise a numeric
    result wins over a verdict label.

    `metric` (optional) is the sealed quantity name, normally
    `kill_threshold["metric"]`. When given, recovery prefers a number the payload
    attributes to that name — `{"metric": "<name>", "value": …}` — then a payload
    key equal to the name (exact after trim/casefold; never substring), then a bare
    result key. A number the payload attributes to a *different* metric is not
    recovered at all: it is a measurement of some other quantity.

    A verdict is read from a payload key first (`verdict`, and the Korean `판정`/`결과`),
    then from the action text. Recovery stays deliberately conservative: an entry whose
    verdict cannot be identified yields (None, None) so the caller keeps its WARN path —
    an unrecovered resolution is a human's problem, a *misrecovered* one is a wrong answer.
    """
    kind, val, _how = _recover_resolution_detail(ledger_path, claim_id, am_ledger, metric)
    return kind, val


# Kept so callers pinned to the pre-0.34 private name keep working.
_recover_resolution = recover_resolution


def falsifiability_check(ledger_path: str, claim_id: str, *,
                          reported_acc: float | None = None,
                          am_ledger: str | None = None) -> Finding:
    """⑪ Popper gate: verify a kill-condition was registered; auto-evaluate it.

    Checks the pre-registration for kill_condition / kill_threshold.

    Levels:
      FAIL — kill_threshold is registered AND reported_acc triggers it
             (the claim falsified itself by its own pre-registered criterion),
             or a sealed negative resolution (retraction / KILL verdict)
      WARN — no kill-condition at all (unfalsifiable), kill_threshold
             registered but no result sealed yet, or the resolution is a bare
             POSITIVE verdict label with no gradable number — "not falsified"
             would rest on the label alone
      OK   — kill threshold not triggered, or text-only condition registered

    Call standalone before publishing, or it runs automatically inside audit().
    """
    pre = _load_prereg(ledger_path, claim_id)
    if pre is None:
        return Finding("⑪ falsifiability", "WARN",
                       f"No pre-registration for '{claim_id}' — "
                       "kill-condition unknown.")

    kill_thr = pre.get("kill_threshold")
    sealed_metric = (str(kill_thr.get("metric") or "").strip() or None
                     if isinstance(kill_thr, dict) else None)

    # Auto-resolution: if no result was handed in, recover one from a sealed
    # resolution (retraction / am_record) instead of warning "not yet provided".
    note = ""
    if reported_acc is None:
        kind, val, how = _recover_resolution_detail(ledger_path, claim_id, am_ledger,
                                                    metric=sealed_metric)
        if kind == "retracted":
            tail = f": {val}" if val else ""
            return Finding("⑪ falsifiability", "FAIL",
                           f"Claim '{claim_id}' is RETRACTED (sealed){tail}. "
                           "Resolved as withdrawn / falsified.")
        if kind == "acc":
            reported_acc = val
            if how in ("attributed", "named-key"):
                note = ("  ← auto-recovered from sealed am_record "
                        f"(value recorded for metric '{sealed_metric}')")
            elif sealed_metric:
                note = ("  ← auto-recovered from sealed am_record (number carries "
                        f"no metric name — assumed to be '{sealed_metric}')")
            else:
                note = "  ← auto-recovered from sealed am_record"
        elif kind == "verdict":
            vu = val.upper()
            if vu.startswith(_NEG_VERDICTS):
                # Trusting a self-reported death is safe against inflation; the
                # claim is resolved-negative either way. But say plainly that the
                # sealed threshold itself was never machine-checked, so audits can
                # count "died by its own criterion" apart from "died, label only".
                return Finding("⑪ falsifiability", "FAIL",
                               f"Sealed verdict for '{claim_id}' = {val} → falsified "
                               "(per am_record(target)). The resolution carries no "
                               "gradable number — the claim died by its label; whether "
                               "it died by its own sealed threshold cannot be "
                               "machine-checked. Record the deciding number as "
                               "{'metric','value'} in the resolving am_record.")
            if vu.startswith(_POS_VERDICTS):
                # Trusting a self-reported survival is exactly how inflation
                # happens. A PASS nothing can re-check is not an OK.
                return Finding("⑪ falsifiability", "WARN",
                               f"Sealed verdict for '{claim_id}' = {val}, but the "
                               "resolution carries no gradable number — 'not falsified' "
                               "rests on the label alone; the sealed kill_threshold was "
                               "never checked against a measurement. Record the deciding "
                               "number as {'metric','value'} in the resolving "
                               "am_record(target).")
            # unknown verdict label → fall through to the standard (WARN) path

    f = _falsifiability_eval(pre, reported_acc)
    if note and f.msg:
        f = Finding(f.probe, f.level, f.msg + note)
    return f


# ─────────────────────────────────────────────────────────────
# ⑫ Retraction cascade
# ─────────────────────────────────────────────────────────────
def _load_dependency_graph(ledger_path: str) -> tuple[dict[str, list[str]], set[str]]:
    """Return (deps, retracted) by scanning the entire ledger.

    deps:      claim_id → list of claim_ids it depends on (from first preregister)
    retracted: set of claim_ids that have at least one retraction entry
    """
    deps: dict[str, list[str]] = {}
    retracted: set[str] = set()

    if not os.path.exists(ledger_path):
        return deps, retracted

    with open(ledger_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = e.get("claim_id")
            if not cid:
                continue
            if e.get("_type") == "retraction":
                retracted.add(cid)
            elif "_type" not in e:
                # preregister entry — record first occurrence only (first-write wins)
                if cid not in deps:
                    do = e.get("depends_on")
                    deps[cid] = do if isinstance(do, list) else []

    return deps, retracted


def retract(ledger_path: str, claim_id: str, reason: str) -> dict:
    """Append a chain-linked retraction entry to the ledger.

    Marks claim_id as retracted. Any claim that depends (directly or transitively)
    on a retracted claim will be flagged STALE by cascade_check(). Every call
    appends a new entry; the entry is chain-linked via prev_seal so retraction
    records cannot be silently deleted from the ledger.
    """
    ts = _utc_now()
    entry: dict = {
        "_type":    "retraction",
        "ts":       ts,
        "claim_id": claim_id,
        "reason":   reason,
    }
    prev_seal = _get_last_seal(ledger_path)
    entry["prev_seal"] = prev_seal
    entry["seal"] = hashlib.sha256(
        json.dumps(entry, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()

    with open(ledger_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def cascade_check(ledger_path: str, claim_id: str) -> Finding:
    """⑫ Retraction cascade: check if claim or any transitive dependency was retracted.

    Levels:
      FAIL — claim_id itself has a retraction entry in the ledger
      WARN — claim is STALE: a transitive dependency has been retracted
      OK   — no retraction risk found

    Policy: retraction propagates regardless of publication order. A claim
    built on a retracted foundation is automatically stale.
    Call standalone, or it runs automatically inside audit() (WARN/FAIL only).
    """
    deps, retracted = _load_dependency_graph(ledger_path)

    if claim_id in retracted:
        return Finding("⑫ retraction-cascade", "FAIL",
                       f"Claim '{claim_id}' has been retracted.")

    # BFS over dependency graph to find stale transitive dependencies
    visited: set[str] = set()
    queue: list[str] = list(deps.get(claim_id, []))
    stale: list[str] = []

    while queue:
        dep = queue.pop(0)
        if dep in visited:
            continue
        visited.add(dep)
        if dep in retracted:
            stale.append(dep)
        else:
            queue.extend(d for d in deps.get(dep, []) if d not in visited)

    if stale:
        return Finding("⑫ retraction-cascade", "WARN",
                       f"Claim '{claim_id}' is STALE: depends (transitively) on "
                       "retracted claim(s): "
                       + ", ".join(f"'{s}'" for s in stale))

    return Finding("⑫ retraction-cascade", "OK",
                   f"No retraction risk for '{claim_id}'.")


# ─────────────────────────────────────────────────────────────
# ⑬ Negative-claim audit — angle-count gate
# ─────────────────────────────────────────────────────────────
def negative_audit(ledger_path: str, *,
                   angles: list[str],
                   min_angles: int = 3,
                   conclusion_scope: list[str] | None = None,
                   tested_scope: list[str] | None = None) -> Finding:
    """⑬ Gate a Resolved-Negative conclusion: angle-count + optional scope check.

    A negative conclusion ("X does not work") is only trustworthy when multiple
    independent pre-registered experiments have all converged on the same result.
    Too few angles = premature closure (single failure may reflect a frame flaw,
    not a universal wall).

    Checks (in priority order):
      1. len(angles) >= min_angles (default 3) — angle-count gate
      2. Each angle has a preregister entry in the ledger — unregistered angles
         cannot be trusted as independent evidence
      3. No angle is retracted (WARN — weakened case, not outright FAIL)
      4. If conclusion_scope and tested_scope provided:
         conclusion must not be broader than tested scope (FAIL if over-claimed)

    Levels:
      FAIL — fewer angles than min_angles, unregistered angle(s), or scope overshoot
      WARN — all FAIL checks pass but at least one angle is retracted
      OK   — all checks pass
    """
    fails: list[str] = []
    warns: list[str] = []

    # Check 1: angle-count gate
    if len(angles) < min_angles:
        fails.append(
            f"only {len(angles)} angle(s) provided (need ≥{min_angles}) — "
            "premature closure risk")

    # Check 2+3: load ledger once for registration + retraction status
    deps, retracted_set = _load_dependency_graph(ledger_path)
    unregistered = [a for a in angles if a not in deps]
    if unregistered:
        fails.append(
            "unregistered angle(s): "
            + ", ".join(f"'{u}'" for u in unregistered))

    retracted_angles = [a for a in angles if a in retracted_set]
    if retracted_angles:
        warns.append(
            "retracted angle(s) weaken the case: "
            + ", ".join(f"'{r}'" for r in retracted_angles))

    # Check 4: scope (optional)
    if conclusion_scope is not None and tested_scope is not None:
        over = [s for s in conclusion_scope if s not in tested_scope]
        if over:
            fails.append(
                "conclusion scope includes untested domain(s): "
                + str(over))

    if fails:
        return Finding("⑬ negative-audit", "FAIL", "; ".join(fails) + ".")
    if warns:
        return Finding("⑬ negative-audit", "WARN", "; ".join(warns) + ".")
    n = len(angles)
    return Finding("⑬ negative-audit", "OK",
                   f"{n}/{n} independent pre-registered angle(s) verified — "
                   "negative conclusion is supported.")


# ─────────────────────────────────────────────────────────────
# ⑭ Judge consistency — flip-rate on repeated scoring
# ─────────────────────────────────────────────────────────────
def judge_consistency_check(score_pairs: list,
                            *, flip_threshold: float = 0.20) -> Finding:
    """⑭ Detect an unreliable LLM judge by measuring verdict flip-rate.

    An LLM judge is run twice on the same items; a high fraction of items
    receiving different scores on re-run indicates the judge is stochastic
    and cannot be trusted to produce reproducible rankings.

    Args:
        score_pairs: [(score_run1, score_run2), ...] — same item judged twice.
                     Scores may be 0/1 (pairwise) or integer (rating scale).
        flip_threshold: maximum acceptable flip fraction (default 0.20).

    Levels:
      FAIL — flip_rate > flip_threshold
      WARN — no pairs provided (can't assess)
      OK   — flip_rate ≤ flip_threshold
    """
    if not score_pairs:
        return Finding("⑭ judge-consistency", "WARN", "No score pairs provided.")

    n = len(score_pairs)
    flips = sum(1 for a, b in score_pairs if a != b)
    flip_rate = flips / n

    if flip_rate > flip_threshold:
        return Finding(
            "⑭ judge-consistency", "FAIL",
            f"Judge flip rate {flip_rate:.1%} > threshold {flip_threshold:.1%} "
            f"({flips}/{n} items changed verdict on re-run). "
            "Judge is unreliable — scores cannot be trusted.")
    return Finding(
        "⑭ judge-consistency", "OK",
        f"Judge flip rate {flip_rate:.1%} ≤ {flip_threshold:.1%} "
        f"({flips}/{n} flips). Consistent.")


# ─────────────────────────────────────────────────────────────
# ⑮ Judge position bias — systematic A/B preference
# ─────────────────────────────────────────────────────────────
def judge_bias_check(pairwise_results: list,
                     *, bias_threshold: float = 0.60) -> Finding:
    """⑮ Detect position bias in a pairwise LLM judge.

    In pairwise evaluation, the judge compares Response A vs Response B.
    A biased judge systematically favors whichever response appears first
    (or second) regardless of content.

    Args:
        pairwise_results: [0, 1, 0, ...] — 0 = A won, 1 = B won per comparison.
        bias_threshold: win-rate above which position bias is flagged (default 0.60).

    Levels:
      FAIL — A or B win-rate > bias_threshold
      WARN — no results provided
      OK   — both win-rates within threshold
    """
    if not pairwise_results:
        return Finding("⑮ judge-bias", "WARN", "No pairwise results provided.")

    n = len(pairwise_results)
    a_wins = sum(1 for r in pairwise_results if r == 0)
    a_rate = a_wins / n

    if a_rate > bias_threshold:
        return Finding(
            "⑮ judge-bias", "FAIL",
            f"Position A win rate {a_rate:.1%} > {bias_threshold:.1%}. "
            f"Strong position bias detected ({a_wins}/{n} items favor A).")
    if a_rate < (1.0 - bias_threshold):
        b_wins = n - a_wins
        return Finding(
            "⑮ judge-bias", "FAIL",
            f"Position B win rate {1.0-a_rate:.1%} > {bias_threshold:.1%}. "
            f"Strong position bias detected ({b_wins}/{n} items favor B).")
    return Finding(
        "⑮ judge-bias", "OK",
        f"Position A win rate {a_rate:.1%} — no significant position bias detected.")


# ─────────────────────────────────────────────────────────────
# ⑯ Inter-rater agreement — Cohen's κ
# ─────────────────────────────────────────────────────────────
def inter_rater_agreement(ratings_matrix: list,
                          *, min_kappa: float = 0.40) -> Finding:
    """⑯ Compute Cohen's κ to check multi-judge reliability.

    When two (or more) judges evaluate the same items, their ratings should
    agree beyond chance level. Low κ means judge results are effectively
    random relative to each other and cannot be averaged or reported as
    a single reliable signal.

    Args:
        ratings_matrix: [(judge1_score, judge2_score), ...] — one row per item.
                        Scores should be categorical (integers). For more than
                        2 raters, pass the first two columns only.
        min_kappa: minimum acceptable Cohen's κ (default 0.40 = "moderate").

    Levels:
      FAIL — κ < 0.20 (poor) or fewer than 3 items provided
      WARN — 0.20 ≤ κ < min_kappa (fair)
      OK   — κ ≥ min_kappa
    """
    if not ratings_matrix:
        return Finding("⑯ inter-rater", "WARN", "No ratings provided.")
    if len(ratings_matrix) < 3:
        return Finding("⑯ inter-rater", "FAIL",
                       f"Only {len(ratings_matrix)} item(s) — need ≥ 3 to compute κ reliably.")

    rater1 = [r[0] for r in ratings_matrix]
    rater2 = [r[1] for r in ratings_matrix]
    n = len(rater1)

    p_o = sum(1 for a, b in zip(rater1, rater2) if a == b) / n

    categories = sorted(set(rater1) | set(rater2))
    p_e = sum(
        (rater1.count(c) / n) * (rater2.count(c) / n)
        for c in categories
    )

    if p_e >= 1.0:
        kappa = 1.0
    else:
        kappa = (p_o - p_e) / (1.0 - p_e)

    if kappa < 0.20:
        return Finding(
            "⑯ inter-rater", "FAIL",
            f"Cohen's κ={kappa:.3f} < 0.20 — poor agreement. "
            "Judge scores are essentially random relative to each other.")
    if kappa < min_kappa:
        return Finding(
            "⑯ inter-rater", "WARN",
            f"Cohen's κ={kappa:.3f} < {min_kappa:.2f} — fair agreement only. "
            "Results may not reproduce with a different judge model.")
    return Finding(
        "⑯ inter-rater", "OK",
        f"Cohen's κ={kappa:.3f} ≥ {min_kappa:.2f} — acceptable inter-rater agreement.")


# ─────────────────────────────────────────────────────────────
# ⑰ Judge score sanity — degenerate distribution
# ─────────────────────────────────────────────────────────────
def judge_score_sanity(scores: list,
                       *, min_unique_ratio: float = 0.10) -> Finding:
    """⑰ Detect a degenerate judge that assigns the same score to everything.

    A judge that never varies its output provides no discrimination signal —
    ranking derived from such scores is meaningless even if aggregate numbers
    look reasonable.

    Args:
        scores: [8, 7, 8, 9, ...] — all scores from a single judge model.
        min_unique_ratio: minimum ratio of unique scores to total (default 0.10).

    Levels:
      FAIL — all scores identical (ratio = 0)
      WARN — unique ratio < min_unique_ratio or top score ≥ 90% of total
      OK   — distribution looks healthy
    """
    if not scores:
        return Finding("⑰ judge-score-sanity", "WARN", "No scores provided.")

    n = len(scores)
    unique_vals = set(scores)
    unique_count = len(unique_vals)
    unique_ratio = unique_count / n

    if unique_count == 1:
        return Finding(
            "⑰ judge-score-sanity", "FAIL",
            f"All {n} scores identical ({scores[0]}). "
            "Judge is not discriminating — scores are meaningless.")

    count: dict = {}
    for s in scores:
        count[s] = count.get(s, 0) + 1
    top_count = max(count.values())
    top_ratio = top_count / n

    if top_ratio > 0.90:
        top_val = max(count, key=lambda k: count[k])
        return Finding(
            "⑰ judge-score-sanity", "WARN",
            f"{top_ratio:.0%} of scores are '{top_val}' — near-degenerate distribution. "
            "Judge may not be discriminating.")
    if unique_ratio < min_unique_ratio:
        return Finding(
            "⑰ judge-score-sanity", "WARN",
            f"Only {unique_count}/{n} unique scores ({unique_ratio:.1%}). "
            "Low discrimination — consider a finer scoring scale.")
    return Finding(
        "⑰ judge-score-sanity", "OK",
        f"{unique_count} distinct values across {n} scores "
        f"({unique_ratio:.1%} unique ratio). Distribution looks healthy.")


# ─────────────────────────────────────────────────────────────
# ⑱ Judge position-swap — AB/BA cross-validation
# ─────────────────────────────────────────────────────────────
def judge_swap_check(forward_results: list, swapped_results: list,
                     *, position_lock_threshold: float = 0.65,
                     noise_threshold: float = 0.35) -> Finding:
    """⑱ Position-swap cross-validation for a pairwise LLM judge.

    Each pair is judged twice: once as (A, B) and once with positions swapped
    (B, A). A content-driven judge must invert its verdict when positions swap —
    the same response wins from either slot. A judge whose verdict stays with
    the *slot* is reading position, not content.

        lock = forward[i] == swapped[i]   (same slot won both → position-driven)

    This catches per-item bias that the aggregate win-rate (⑮) misses: a judge
    with moderate position preference stays under the ⑮ threshold whenever the
    content quality is unbalanced, but cannot survive the swap test.

    Interpretation of lock_rate:
      ~0.0  content-driven  (verdict follows the response)  → OK
      ~0.5  noise           (verdict tracks neither)        → WARN
      ~1.0  position-locked (verdict follows the slot)      → FAIL

    Args:
        forward_results: [0, 1, ...] — winner per item in original (A, B) order.
        swapped_results: [0, 1, ...] — winner per item in swapped (B, A) order.
        position_lock_threshold: lock_rate above this → FAIL (default 0.65).
        noise_threshold: lock_rate above this → WARN (default 0.35).

    Pairs containing values outside {0, 1} (e.g. -1 parse failures) are excluded.
    """
    if len(forward_results) != len(swapped_results):
        return Finding("⑱ judge-swap", "FAIL",
                       f"Length mismatch: {len(forward_results)} forward vs "
                       f"{len(swapped_results)} swapped results. "
                       "Each item must be judged in both orders.")

    valid = [(f, s) for f, s in zip(forward_results, swapped_results)
             if f in (0, 1) and s in (0, 1)]
    if not valid:
        return Finding("⑱ judge-swap", "WARN",
                       "No valid forward/swapped result pairs to compare.")

    n = len(valid)
    locked = sum(1 for f, s in valid if f == s)
    lock_rate = locked / n

    if lock_rate > position_lock_threshold:
        return Finding(
            "⑱ judge-swap", "FAIL",
            f"Position-lock rate {lock_rate:.1%} > {position_lock_threshold:.1%} "
            f"({locked}/{n} verdicts stayed with the slot after AB→BA swap). "
            "Judge is reading position, not content.")
    if lock_rate > noise_threshold:
        return Finding(
            "⑱ judge-swap", "WARN",
            f"Position-lock rate {lock_rate:.1%} in noise band "
            f"({noise_threshold:.1%}–{position_lock_threshold:.1%}). "
            "Verdicts track neither content nor position consistently — "
            "judge signal is weak.")
    return Finding(
        "⑱ judge-swap", "OK",
        f"Position-lock rate {lock_rate:.1%} ≤ {noise_threshold:.1%} "
        f"({n - locked}/{n} verdicts inverted with the swap). Content-driven.")


# ─────────────────────────────────────────────────────────────
# ⑲ Judge transitivity — preference-cycle detection
# ─────────────────────────────────────────────────────────────
def judge_transitivity_check(matches: list) -> Finding:
    """⑲ Detect preference cycles (A>B>C>A) in a pairwise tournament.

    When a judge ranks more than two models via pairwise comparisons, the
    aggregated preferences should form a transitive order. A cycle means the
    judge is not applying a consistent quality scale — any leaderboard built
    from its verdicts is an artifact of match ordering, not model quality.

    Args:
        matches: [(model_a, model_b, winner), ...] — one tuple per comparison;
                 winner is 0 (model_a won) or 1 (model_b won).  Multiple
                 comparisons of the same pair are aggregated by majority vote;
                 exactly tied pairs produce no edge.

    Levels:
      FAIL — at least one preference cycle exists (an example cycle is shown)
      WARN — fewer than 3 distinct models, or no usable (non-tied) pairs
      OK   — preference graph is acyclic (a consistent ranking exists)
    """
    if not matches:
        return Finding("⑲ judge-transitivity", "WARN", "No matches provided.")

    # Aggregate per unordered pair by majority vote
    wins: dict[tuple[str, str], int] = {}   # (a, b) sorted → net wins for a
    models: set[str] = set()
    for a, b, winner in matches:
        if a == b:
            continue
        models.update((a, b))
        key = (a, b) if a <= b else (b, a)
        first_won = (winner == 0) == (key == (a, b))
        wins[key] = wins.get(key, 0) + (1 if first_won else -1)

    if len(models) < 3:
        return Finding("⑲ judge-transitivity", "WARN",
                       f"Only {len(models)} distinct model(s) — need ≥ 3 "
                       "to test transitivity.")

    beats: dict[str, list[str]] = {m: [] for m in models}
    ties = 0
    for (a, b), net in wins.items():
        if net > 0:
            beats[a].append(b)
        elif net < 0:
            beats[b].append(a)
        else:
            ties += 1

    # DFS cycle detection with path reconstruction
    WHITE, GREY, BLACK = 0, 1, 2
    color = {m: WHITE for m in models}

    def _find_cycle(start: str) -> list[str] | None:
        stack: list[tuple[str, int]] = [(start, 0)]
        path: list[str] = []
        while stack:
            node, child_i = stack[-1]
            if child_i == 0:
                color[node] = GREY
                path.append(node)
            children = beats[node]
            if child_i < len(children):
                stack[-1] = (node, child_i + 1)
                nxt = children[child_i]
                if color[nxt] == GREY:
                    return path[path.index(nxt):] + [nxt]
                if color[nxt] == WHITE:
                    stack.append((nxt, 0))
            else:
                color[node] = BLACK
                path.pop()
                stack.pop()
        return None

    for m in sorted(models):
        if color[m] == WHITE:
            cycle = _find_cycle(m)
            if cycle:
                return Finding(
                    "⑲ judge-transitivity", "FAIL",
                    "Preference cycle detected: "
                    + " > ".join(cycle)
                    + ". Judge is not applying a consistent quality scale — "
                    "any leaderboard from these verdicts is order-dependent.")

    tie_note = f" ({ties} tied pair(s) excluded)" if ties else ""
    return Finding(
        "⑲ judge-transitivity", "OK",
        f"Preference graph over {len(models)} models is acyclic — "
        f"a consistent ranking exists{tie_note}.")


# ─────────────────────────────────────────────────────────────
# ⑳ Ranking stability — bootstrap resampling guard
# ─────────────────────────────────────────────────────────────
def ranking_stability_check(scores_a: list, scores_b: list, *,
                            n_boot: int = 1000, seed: int = 0,
                            min_stability: float = 0.95) -> Finding:
    """⑳ Check that "model A beats model B" survives bootstrap resampling.

    A ranking claim built on per-item scores can be a mirage: with few items
    or high variance, redrawing the same-sized sample flips the winner.  This
    probe resamples item indices with replacement n_boot times and measures
    how often the observed winner stays the winner.

    Deterministic: uses random.Random(seed) — same inputs always produce the
    same Finding (mirror discipline: audits must be reproducible).

    Args:
        scores_a: per-item scores for model A (paired with scores_b by index).
        scores_b: per-item scores for model B on the same items.
        n_boot:   bootstrap resamples (default 1000).
        seed:     RNG seed (default 0).
        min_stability: required fraction of resamples preserving the winner.

    Levels:
      FAIL — length mismatch, tied means (no ranking), or stability < 0.80
      WARN — fewer than 5 items, or 0.80 ≤ stability < min_stability
      OK   — stability ≥ min_stability
    """
    if len(scores_a) != len(scores_b):
        return Finding("⑳ ranking-stability", "FAIL",
                       f"Length mismatch: {len(scores_a)} vs {len(scores_b)} "
                       "scores. Items must be paired.")
    n = len(scores_a)
    if n == 0:
        return Finding("⑳ ranking-stability", "WARN", "No scores provided.")
    if n < 5:
        return Finding("⑳ ranking-stability", "WARN",
                       f"Only {n} item(s) — too few to assess ranking stability.")

    sum_a, sum_b = sum(scores_a), sum(scores_b)
    if sum_a == sum_b:
        return Finding("⑳ ranking-stability", "FAIL",
                       "Observed means are exactly tied — there is no ranking "
                       "to certify.")
    a_wins_observed = sum_a > sum_b
    winner, loser = ("A", "B") if a_wins_observed else ("B", "A")

    rng = random.Random(seed)
    same = 0
    for _ in range(n_boot):
        sa = sb = 0
        for _ in range(n):
            i = rng.randrange(n)
            sa += scores_a[i]
            sb += scores_b[i]
        if (sa > sb) == a_wins_observed and sa != sb:
            same += 1
    stability = same / n_boot

    if stability < 0.80:
        return Finding(
            "⑳ ranking-stability", "FAIL",
            f"Ranking '{winner} > {loser}' survives only {stability:.1%} of "
            f"{n_boot} bootstrap resamples (n={n}). The ranking is noise — "
            "indistinguishable from a tie.")
    if stability < min_stability:
        return Finding(
            "⑳ ranking-stability", "WARN",
            f"Ranking '{winner} > {loser}' survives {stability:.1%} of "
            f"{n_boot} resamples — below the {min_stability:.0%} bar. "
            "Collect more items before publishing this ranking.")
    return Finding(
        "⑳ ranking-stability", "OK",
        f"Ranking '{winner} > {loser}' survives {stability:.1%} of "
        f"{n_boot} bootstrap resamples (n={n}). Stable.")


# ─────────────────────────────────────────────────────────────
# Metric kind — so the binary/proportion probes don't false-FAIL on a
# percentage / delta / span / unbounded metric. A *declared* range/chance
# (from the prereg or an explicit arg) wins; otherwise it is inferred from the
# metric name; otherwise it defaults to the [0,1] proportion.
# ─────────────────────────────────────────────────────────────
_DELTA_HINTS = ("delta", "diff", "Δ", "change", "_lift", "gain", "improve_abs", "drop", "shift")
_PCT_HINTS = ("_pct", "pct", "percent", "_pp")
_SPAN_HINTS = ("span", "width", "elastic", "window", "magnitude", "count", "tokens",
               "steps", "length", "distance", "capacity")


def resolve_metric_kind(metric_name: str, metric_range=None, chance=None):
    """Return (lo, hi, chance, is_proportion, declared).

    is_proportion = the integer-grid / binomial probes (GRIM, small-sample CI) apply
    — true only for a [0,1] proportion or a [0,100] percentage (which normalises to
    one). Delta / span / unbounded metrics are continuous: those probes are skipped.
    """
    declared = metric_range is not None or chance is not None
    name = (metric_name or "").lower()
    if metric_range in ("unbounded", "real"):
        lo, hi = float("-inf"), float("inf")
    elif isinstance(metric_range, (list, tuple)) and len(metric_range) == 2:
        lo, hi = float(metric_range[0]), float(metric_range[1])
    elif any(h in name for h in _DELTA_HINTS):
        lo, hi = float("-inf"), float("inf")        # signed delta/change
    elif any(h in name for h in _PCT_HINTS):
        lo, hi = 0.0, 100.0                         # percentage
    elif any(h in name for h in _SPAN_HINTS):
        lo, hi = 0.0, float("inf")                  # non-negative magnitude
    else:
        lo, hi = 0.0, 1.0                           # default: proportion
    is_proportion = (lo, hi) == (0.0, 1.0) or (lo, hi) == (0.0, 100.0)
    if chance is None and is_proportion:
        chance = 50.0 if hi == 100.0 else 0.5
    return lo, hi, chance, is_proportion, declared


# ─────────────────────────────────────────────────────────────
# Binary / classification metric audit
# ─────────────────────────────────────────────────────────────
def audit(ledger_path: str, claim_id: str, *,
          reported_metric: str, reported_acc: float, n: int,
          baseline: float | None = None, task: str | None = None,
          db_dir: str | None = None,
          metric_range: list | str | None = None,
          chance: float | None = None) -> list[Finding]:
    findings: list[Finding] = []
    db_note = ""
    pre = _load_prereg(ledger_path, claim_id)

    # Metric kind: explicit arg > sealed prereg > inference from the metric name.
    if metric_range is None and pre is not None:
        metric_range = pre.get("metric_range")
    if chance is None and pre is not None:
        chance = pre.get("chance")
    lo, hi, chance, is_prop, declared = resolve_metric_kind(reported_metric, metric_range, chance)

    # Baseline precedence: explicit arg > declared chance > task DB > 0.5.
    if baseline is None:
        if chance is not None:
            baseline = chance
        else:
            b = lookup_baseline(task, db_dir)
            if b is not None:
                baseline, db_note = b, f"  ← DB lookup (task={task})"
            else:
                baseline = 0.5

    # Local memory: prior FAILED reproductions for this task (db/reproductions.jsonl)
    for r in lookup_reproduction(task, db_dir):
        rep = r.get("reproduction", {})
        findings.append(Finding("⚙ prior-reproduction", "WARN",
            f"task '{task}' has a prior reproduction failure on record: "
            f"'{r.get('claim','?')}' claimed acc={r.get('acc_claimed','?')} "
            f"(n={r.get('n_claimed','?')}) → reproduced acc={rep.get('acc','?')} "
            f"(n={rep.get('n','?')}). {r.get('note','')}".rstrip()))

    # ④a range — against the metric's declared/inferred range, not a hardcoded [0,1].
    if not (lo <= reported_acc <= hi):
        guide = "" if declared else (
            "  → if this is a %/delta/span metric, declare metric_range "
            "(e.g. [0,100] or \"unbounded\") + chance in mm_preregister.")
        findings.append(Finding("④a metric-range", "FAIL",
            f"reported value {reported_acc:.3f} is outside metric range "
            f"[{lo}, {hi}].{guide}"))
        return findings
    if n < 0:
        findings.append(Finding("④a n-range", "FAIL", f"n={n} must be ≥ 0."))
        return findings

    if is_prop:
        # Proportion ([0,1]) or percentage ([0,100], normalised) — integer-grid + binomial apply.
        scale = 100.0 if hi == 100.0 else 1.0
        acc01, base01 = reported_acc / scale, baseline / scale
        unit = "%" if scale == 100.0 else ""

        # ⑩ GRIM — only appended when FAIL to keep OK output clean
        grim = grim_check(acc01, n)
        if grim.level != "OK":
            findings.append(grim)

        k = round(acc01 * n)
        if 0 < n <= _EXACT_MAX_N:
            # Exact two-sided binomial test — the correct small-sample method (Wilson's
            # normal approximation is over-optimistic at the boundary; see eval/self_fpfn/v2).
            p = binom_two_sided_p(k, n, base01)
            if p > 0.05:
                findings.append(Finding("④a small-sample CI", "FAIL",
                    f"n={n}, acc={reported_acc:.3f}{unit} → exact binomial p={p:.3f} > 0.05 "
                    f"vs chance({baseline}{unit}).{db_note} Indistinguishable from chance."))
            elif acc01 < base01:
                findings.append(Finding("④a direction(anti-signal)", "FAIL",
                    f"n={n}, acc={reported_acc:.3f}{unit} → exact binomial p={p:.3f} ≤ 0.05 but "
                    f"below chance({baseline}{unit}). Worse than chance."))
            else:
                findings.append(Finding("④a small-sample CI", "OK",
                    f"n={n}, acc={reported_acc:.3f}{unit} → exact binomial p={p:.3f} ≤ 0.05 "
                    f"clears chance({baseline}{unit})."))
        else:
            clo, chi = wilson_ci(k, n)
            if clo <= base01 <= chi:
                findings.append(Finding("④a small-sample CI", "FAIL",
                    f"n={n}, acc={reported_acc:.3f}{unit} → 95%CI [{clo:.3f}, {chi:.3f}] "
                    f"⊃ chance({base01}).{db_note} Indistinguishable from chance."))
            elif chi < base01:
                findings.append(Finding("④a direction(anti-signal)", "FAIL",
                    f"n={n}, acc={reported_acc:.3f}{unit} → CI [{clo:.3f}, {chi:.3f}] "
                    f"< chance({base01}). Worse than chance."))
            else:
                findings.append(Finding("④a small-sample CI", "OK",
                    f"n={n}, acc={reported_acc:.3f}{unit} → CI [{clo:.3f}, {chi:.3f}] "
                    f"clears chance({base01})."))
    else:
        # Continuous (delta / span / unbounded): the proportion probes do not apply and
        # would false-FAIL, so they are skipped.
        msg = (f"'{reported_metric}' is a continuous metric (range [{lo}, {hi}]); the "
               f"integer-grid / binomial probes (GRIM, small-sample CI) are skipped.")
        if chance is None:
            msg += (" For a distinguishability test use continuous_audit() with a "
                    "baseline_value + std, or declare chance.")
        findings.append(Finding("④a metric-kind", "INFO", msg))
        if chance is not None and reported_acc < chance:
            findings.append(Finding("④a direction(anti-signal)", "WARN",
                f"value {reported_acc} is below chance {chance}."))

    # ① pre-registration
    if pre is None:
        findings.append(Finding("① pre-registration", "WARN",
            f"No pre-registration found for '{claim_id}'."))
    else:
        if not _verify_seal(pre):
            findings.append(Finding("① seal-tamper", "FAIL",
                f"Seal mismatch for '{claim_id}'. Ledger modified."))
        else:
            if n < pre["min_n"]:
                findings.append(Finding("① pre-registration(min_n)", "FAIL",
                    f"n={n} < registered min_n={pre['min_n']}."))
            if reported_metric != pre["metric"]:
                findings.append(Finding("① pre-registration(metric-swap)", "FAIL",
                    f"Reported metric '{reported_metric}' ≠ registered '{pre['metric']}'. "
                    f"Post-hoc swap. (seal={pre['seal']})"))
            if reported_acc < pre["pass_threshold"]:
                findings.append(Finding("① pre-registration(pass-threshold)", "FAIL",
                    f"acc={reported_acc:.3f} < registered pass_threshold="
                    f"{pre['pass_threshold']:.3f}. (seal={pre['seal']})"))
            # ⑪ falsifiability — only when seal is valid (no double-load)
            findings.append(_falsifiability_eval(pre, reported_acc))
            # ㉑㉒ grounding declarations sealed at preregistration time
            # (SPEC amendment A1) are audited automatically.
            if "anchor_basis" in pre:
                findings.append(anchor_basis_check(pre["anchor_basis"]))
            if "threshold_source" in pre:
                findings.append(threshold_provenance_check(pre["threshold_source"]))
            # ㉔㉕ anchor-discipline + known_confounds (SPEC amendment A2).
            if "anchor_line_source" in pre:
                findings.append(anchor_line_source_check(pre["anchor_line_source"]))
            if "anchor_cell" in pre:
                findings.append(anchor_cell_check(pre["anchor_cell"]))
            if pre.get("known_confounds"):
                findings.append(Finding("㉖ known-confounds", "INFO",
                    f"{len(pre['known_confounds'])} confound(s) declared before "
                    f"results: {pre['known_confounds']}. A pre-declared confound "
                    "legitimizes later attribution cycles; an undeclared one found "
                    "post-hoc does not."))

    # ⑫ cascade — retraction check (runs regardless of pre-registration)
    casc = cascade_check(ledger_path, claim_id)
    if casc.level != "OK":
        findings.append(casc)

    return findings


# ─────────────────────────────────────────────────────────────
# Continuous / regression metric audit
# ─────────────────────────────────────────────────────────────
def continuous_audit(ledger_path: str, claim_id: str, *,
                     reported_metric: str, reported_value: float,
                     baseline_value: float, n: int,
                     std: float | None = None,
                     higher_better: bool = True) -> list[Finding]:
    """Audit continuous/regression metrics (Pearson r, MSE, RMSE, …)."""
    findings: list[Finding] = []

    diff = (reported_value - baseline_value) if higher_better else (baseline_value - reported_value)
    if diff <= 0:
        symbol = "≤" if higher_better else "≥"
        findings.append(Finding("④a direction", "FAIL",
            f"value={reported_value:.4f} {symbol} baseline={baseline_value:.4f}. Baseline wins."))
    else:
        findings.append(Finding("④a direction", "OK",
            f"Δ={diff:+.4f} — {'higher' if higher_better else 'lower'}-is-better met."))

    if std is not None and std > 0:
        z = abs(reported_value - baseline_value) / std
        if z < 1.0:
            findings.append(Finding("④a effect-size", "WARN",
                f"z={z:.2f} < 1.0 — weak practical significance (n={n})."))
        else:
            findings.append(Finding("④a effect-size", "OK", f"z={z:.2f} ≥ 1.0."))

    pre = _load_prereg(ledger_path, claim_id)
    if pre is None:
        findings.append(Finding("① pre-registration", "WARN",
            f"No pre-registration for '{claim_id}'."))
    else:
        if not _verify_seal(pre):
            findings.append(Finding("① seal-tamper", "FAIL",
                f"Seal mismatch for '{claim_id}'."))
        else:
            if reported_metric != pre["metric"]:
                findings.append(Finding("① pre-registration(metric-swap)", "FAIL",
                    f"'{reported_metric}' ≠ registered '{pre['metric']}'. "
                    f"(seal={pre['seal']})"))
            if n < pre["min_n"]:
                findings.append(Finding("① pre-registration(min_n)", "FAIL",
                    f"n={n} < registered min_n={pre['min_n']}."))

    return findings


# ─────────────────────────────────────────────────────────────
# Full audit — all probes in one call
# ─────────────────────────────────────────────────────────────
def full_audit(ledger_path: str, claim_id: str, *,
               reported_metric: str, reported_acc: float, n: int,
               baseline: float | None = None, task: str | None = None,
               db_dir: str | None = None,
               competing_name: str | None = None,          # ②
               competing_acc: float | None = None,         # ②
               reward_terms: list[str] | None = None,      # ③
               train_items=None, test_items=None,           # ④a-2
               seed_results: list[float] | None = None,    # ⑤
               claimed_scope=None, tested_scope=None,      # ⑥
               min_detectable_effect: float | None = None, # ⑧
               check_chain: bool = True,                   # ① chain
               check_multiplicity: bool = False,           # ⑨
               angles: list[str] | None = None,            # ⑬
               min_angles: int = 3) -> list[Finding]:      # ⑬
    """Run all probes in one call. Optional probes activate when args are provided."""
    _baseline = baseline
    if _baseline is None:
        b = lookup_baseline(task, db_dir)
        _baseline = b if b is not None else 0.5

    findings: list[Finding] = []

    # ① + ④a-1
    findings.extend(audit(ledger_path, claim_id,
                          reported_metric=reported_metric,
                          reported_acc=reported_acc, n=n,
                          baseline=_baseline, task=task, db_dir=db_dir))
    # ① chain integrity (only failures — OK is implied by absence)
    if check_chain:
        for f in verify_chain(ledger_path):
            if f.level != "OK":
                findings.append(f)
    # ②
    if competing_name is not None and competing_acc is not None:
        findings.append(baseline_fairness(competing_name, reported_acc, competing_acc))
    # ③
    if reward_terms is not None:
        findings.append(gaming_check(reported_metric, reward_terms))
    # ④a-2
    if train_items is not None and test_items is not None:
        findings.append(leakage_check(train_items, test_items))
    # ⑤
    if seed_results is not None:
        findings.append(multiseed_check(seed_results, baseline=_baseline))
    # ⑥
    if claimed_scope is not None and tested_scope is not None:
        findings.append(scope_check(claimed_scope, tested_scope))
    # ⑦ always
    findings.append(too_good_check(claim_id, reported_acc, _baseline))
    # ⑧ power (optional)
    if min_detectable_effect is not None:
        findings.append(power_check(n, _baseline,
                                    min_detectable_effect=min_detectable_effect))
    # ⑨ multiple comparisons (optional)
    if check_multiplicity:
        findings.append(multiple_comparisons_check(ledger_path))
    # ⑬ negative audit (optional)
    if angles is not None:
        findings.append(negative_audit(ledger_path, angles=angles,
                                       min_angles=min_angles))

    return findings


# ─────────────────────────────────────────────────────────────
# ㉘ Subspace claim — declaration auditor (NOT a recomputer)
#
# THIS IS A DECLARATION AUDITOR, NOT A RECOMPUTER. It reads a submitted
# table of numbers. If `energy_kept` is written falsely, it passes. That
# limitation is structural — it applies to all seven findings below, not
# just the anchor one. The consistency laws C1–C4 raise the *cost* of a
# false table; they do not close the hole. Do not read them as a fix.
# ─────────────────────────────────────────────────────────────
_SUBSPACE_ROLES = frozenset(
    {"target", "null", "data_only", "dof_control", "matched_null"})
_ANCHOR_CODE_PATHS = frozenset({"frozen", "mixed", "reimplemented", "unknown"})


def _paired_signflip_p(diffs: list[float], *,
                       exact_max_n: int = 14,
                       mc_samples: int = 20000,
                       seed: int = 0) -> float | None:
    """Two-sided paired sign-flip permutation test. stdlib only, deterministic.

    n ≤ `exact_max_n` enumerates all 2ⁿ sign assignments (exact). Above that it
    draws `mc_samples` flips from a fixed-seed RNG, so repeated calls on the
    same input return the same p.

    Deliberately NOT the normal approximation used elsewhere: at n=10 the
    normal fallback is anti-conservative (over-rejects). An exact enumeration
    costs 1024 evaluations there — no reason to approximate.

    Returns None when there is nothing to test (n = 0).
    """
    d = [float(x) for x in diffs]
    n = len(d)
    if n == 0:
        return None
    obs = abs(sum(d) / n)
    # A run of exact zeros has no evidence in either direction; p = 1.
    if all(x == 0.0 for x in d):
        return 1.0

    if n <= exact_max_n:
        total = 1 << n
        hits = 0
        for mask in range(total):
            s = 0.0
            for i, x in enumerate(d):
                s += -x if (mask >> i) & 1 else x
            if abs(s / n) >= obs - 1e-15:
                hits += 1
        return hits / total

    rng = random.Random(seed)
    hits = 0
    for _ in range(mc_samples):
        s = 0.0
        for x in d:
            s += x if rng.getrandbits(1) else -x
        if abs(s / n) >= obs - 1e-15:
            hits += 1
    return hits / mc_samples


def _as_vec(value) -> list:
    """Accept a scalar or a per-bin vector; always return a list.

    105_-style reports carry length-4 per-bin vectors for `k`/`energy_kept`.
    Forcing them to scalars would average away exactly the per-bin overshoot
    the probe exists to catch, so vectors are first-class here.
    """
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _expand_cells(cells: list[dict]) -> tuple[list[dict], list[str]]:
    """Flatten vector-valued cells into one entry per bin. Returns (rows, errors)."""
    rows: list[dict] = []
    errors: list[str] = []
    for idx, c in enumerate(cells):
        if not isinstance(c, dict):
            errors.append(f"cells[{idx}] is not a dict")
            continue
        ks = _as_vec(c.get("k"))
        es = _as_vec(c.get("energy_kept"))
        if len(ks) != len(es):
            errors.append(
                f"cells[{idx}] (arm={c.get('arm')!r}): k has {len(ks)} entries "
                f"but energy_kept has {len(es)} — vector lengths must match")
            continue
        role = c.get("role")
        if role is not None and role not in _SUBSPACE_ROLES:
            errors.append(
                f"cells[{idx}] role={role!r} not in {sorted(_SUBSPACE_ROLES)}")
        for j, (k, e) in enumerate(zip(ks, es)):
            rows.append({
                "arm": c.get("arm"), "role": role, "seed": c.get("seed"),
                "bin": c.get("bin", j if len(ks) > 1 else None),
                "grid_point": c.get("grid_point"),
                "k": k, "energy_kept": e,
                "energy_target": c.get("energy_target"),
                "effect": c.get("effect"), "n": c.get("n"),
                "_cell": idx,
            })
    return rows, errors


def subspace_claim_check(report: dict, *,
                         energy_tol: float = 0.05,
                         alpha: float = 0.05,
                         dim_tol: float = 0.15) -> list[Finding]:
    """㉘ Audit a submitted "the gain lives in a few input directions" claim.

    ⚠️ **This is a declaration auditor, not a recomputer.** It never sees the
    basis, the perturbation samples, or the model — only the table the claimant
    submitted. A falsified `energy_kept` passes. C1–C4 make a consistent forgery
    expensive (you must forge the whole manifold, not one number); they do not
    make it impossible.

    That design is deliberate: a third party's model is not in our hands, so an
    executor could only ever audit our own claims. The auditor audits anyone's.

    `report` keys (all optional — a finding fires only when its inputs exist):
      anchor          dict  code_path (frozen|mixed|reimplemented|unknown),
                            mixed_detail, reference, tol, n_seeds, guard_seeds
      grid            dict  {"kind": "energy"|"k"} — absent means "no grid",
                            which makes energy matching NOT APPLICABLE (skip),
                            not FAILED
      cells           list  {arm, role, seed, bin, grid_point, k, energy_kept,
                            energy_target, effect, n} — k/energy_kept may be
                            scalars or per-bin vectors of equal length
      arms            dict  {arm: {"role":…, "effect_by_seed":[…]}} — the second
                            granularity tier the paired test needs
      bar             float the survival bar, for saturation
      ambient_dim     int   declared ambient dimension, cross-checked by C4
      n_basis_fit     int   samples used to fit the basis
      basis_fit_ids   list  ids used to ESTIMATE the basis
      effect_eval_ids list  ids used to EVALUATE the effect
      certificate     dict  {arm: {"passed": bool, …}} for matched_null arms

    Findings (all prefixed ㉘), with a priority rule: when the anchor fails,
    `null-ladder` cannot report OK — without a reproducible anchor the ratio
    normalizer is undefined, so the p-value sits on an unlabelled axis.

    ⚠️ **Swapped-role claims are guarded only partly, by
    `dof-outperforms-target`.** The table alone does not say which arm was the
    treatment. What it does say is that destroying the claimed structure cannot
    ADD effect, so a control that beats its target is incoherent — that law is
    the guard, and it holds `null-ladder` below OK when it fires. It catches the
    swap only when the true target genuinely beats its control; when the two are
    indistinguishable the swap stays invisible, and so does the effect it would
    hide. There was no guard at all until substrate-2 exposed the gap (seal
    `5c78e503`): the `relabeled_dof` case had passed on FM×CDE only because the
    shuffled arm did not beat the null *there*, which was substrate luck rather
    than a mechanism. The law is sealed on the FM×CDE holdout at 22/22
    (`582f4130`, result am `45d5f3d2`). See `eval/subspace_substrate2/RESULTS.md`.
    """
    findings: list[Finding] = []
    if not isinstance(report, dict):
        return [Finding("㉘ schema", "FAIL",
                        f"report must be a dict, got {type(report).__name__}.")]

    cells_in = report.get("cells") or []
    rows, schema_errors = _expand_cells(cells_in)
    if schema_errors:
        findings.append(Finding("㉘ schema", "FAIL",
            f"{len(schema_errors)} schema problem(s): " + "; ".join(schema_errors[:4]),
            data={"errors": schema_errors}))

    roles_present = {r["role"] for r in rows if r.get("role")}
    arms_meta = report.get("arms") or {}
    for name, meta in arms_meta.items():
        if isinstance(meta, dict) and meta.get("role"):
            roles_present.add(meta["role"])

    # ── ① no-anchor — a DECLARATION lint, not a reproduction verdict ─────
    # An arbitrary user has neither our frozen functions nor our sealed
    # baseline, so we can only ask whether the anchor was declared, and
    # declared in a way that cannot be read two ways.
    anchor = report.get("anchor")
    anchor_failed = False
    if not isinstance(anchor, dict) or not anchor:
        anchor_failed = True
        findings.append(Finding("㉘ no-anchor", "FAIL",
            "No anchor block. A bit-reproduction anchor must be declared "
            "before any ladder is read: without it the ratio normalizer is "
            "undefined and every downstream p-value sits on an unlabelled axis."))
    else:
        problems: list[str] = []
        cp = str(anchor.get("code_path", "")).strip().lower()
        if cp not in _ANCHOR_CODE_PATHS:
            problems.append(
                f"code_path={anchor.get('code_path')!r} not in "
                f"{sorted(_ANCHOR_CODE_PATHS)}")
        if cp == "mixed" and not str(anchor.get("mixed_detail", "")).strip():
            problems.append(
                "code_path='mixed' requires mixed_detail naming which part is "
                "frozen — 'mixed' alone cannot be read honestly")
        if cp == "reimplemented" and not str(anchor.get("reference", "")).strip():
            problems.append(
                "code_path='reimplemented' requires a reference to what was "
                "reimplemented against")
        if cp == "unknown":
            problems.append("code_path='unknown' — provenance not established")
        if anchor.get("tol") is None:
            problems.append("no tol declared")
        if anchor.get("n_seeds") is None:
            problems.append("no n_seeds declared")
        # Separate fields on purpose: folding guard seeds into n_seeds reads as
        # if the anchor had been verified across the whole main seed set.
        if anchor.get("guard_seeds") is None:
            problems.append(
                "no guard_seeds declared (must be separate from n_seeds — "
                "merging them overstates how widely the anchor was checked)")
        if problems:
            anchor_failed = True
            findings.append(Finding("㉘ no-anchor", "FAIL",
                f"Anchor declaration incomplete ({len(problems)}): "
                + "; ".join(problems),
                data={"problems": problems, "code_path": cp}))
        else:
            findings.append(Finding("㉘ no-anchor", "OK",
                f"Anchor declared: code_path={cp}, tol={anchor.get('tol')!r}, "
                f"n_seeds={anchor.get('n_seeds')}, "
                f"guard_seeds={anchor.get('guard_seeds')}.",
                data={"code_path": cp}))

    # ── ② energy-not-matched — ABSENT vs NOT-APPLICABLE ─────────────────
    # A report with no grid at all (104_-style) is not a failing report; it is
    # a report this finding does not apply to. Conflating the two turns a clean
    # case into a FAIL and misfires the FP kill.
    grid = report.get("grid")
    have_grid = isinstance(grid, dict) and grid.get("kind")
    if not have_grid:
        findings.append(Finding("㉘ energy-not-matched", "N/A",
            "No grid declared — energy matching does not apply to this report "
            "(this is 'not applicable', NOT 'absent and therefore failing')."))
    elif str(grid.get("kind")).lower() == "k":
        findings.append(Finding("㉘ energy-not-matched", "FAIL",
            "Arms are gridded on k, not on retained energy. At a fixed k the "
            "arms retain DIFFERENT amounts of energy, so a difference between "
            "them is confounded with how much signal each kept. Same k is NOT "
            "the same condition — re-grid on retained energy.",
            data={"grid_kind": "k"}))
    else:
        # Arms hit a shared energy target by choosing k SEPARATELY per arm (and
        # per bin). So the signature of the confound is not "achieved energies
        # differ" — k is an integer, so they always differ, by an amount that
        # varies per basis and per bin. The signature is arms sharing an
        # IDENTICAL k at a grid point while the report claims energy matching:
        # that is a k grid wearing an energy label.
        by_point: dict = {}
        for r in rows:
            if r["energy_kept"] is None or r["k"] is None:
                continue
            by_point.setdefault((r["grid_point"], r["bin"], r["seed"]), []).append(r)
        locked, spreads = [], []
        for key, group in sorted(by_point.items(), key=lambda kv: repr(kv[0])):
            per_arm: dict = {}
            for r in group:
                per_arm.setdefault(r["arm"], set()).add(float(r["k"]))
            if len(per_arm) < 2:
                continue
            vals = [float(r["energy_kept"]) for r in group]
            hi = max(vals)
            spreads.append((hi - min(vals)) / (abs(hi) or 1.0))
            if all(len(ks) == 1 for ks in per_arm.values()) and \
                    len({next(iter(ks)) for ks in per_arm.values()}) == 1:
                locked.append(f"{key!r} k={next(iter(next(iter(per_arm.values()))))}")
        frac = (len(locked) / len(spreads)) if spreads else None
        obs = {"max_energy_spread": max(spreads) if spreads else None,
               "n_grid_cells_compared": len(spreads),
               "k_locked_cells": len(locked), "k_locked_fraction": frac}
        if not spreads:
            findings.append(Finding("㉘ energy-not-matched", "N/A",
                "No grid cell carries two or more arms — nothing to compare.",
                data=obs))
        elif frac == 1.0:
            # Threshold-free by construction: a k grid is DEFINED by every arm
            # sharing k at every grid point. A fraction below 1 is coincidence
            # — arms picking small integer k do collide sometimes (real 105_:
            # 8 of 160 cells) — and calling that a k grid is reading a
            # coincidence as a design.
            findings.append(Finding("㉘ energy-not-matched", "FAIL",
                f"Grid declares energy matching, but EVERY arm shares the same "
                f"k in EVERY one of the {len(spreads)} compared cell(s) "
                f"(e.g. {locked[0]}). That is the definition of a k grid — "
                f"this one is wearing an energy label. At fixed k the arms "
                f"retain different amounts of energy, so any difference "
                f"between them is confounded.",
                data={**obs, "examples": locked[:5]}))
        else:
            findings.append(Finding("㉘ energy-not-matched", "OK",
                f"Energy grid: k varies across arms in "
                f"{len(spreads) - len(locked)} of {len(spreads)} compared "
                f"cell(s) (k-locked fraction {frac:.3f} < 1.0 = coincidence, "
                f"not design), and achieved energy meets the declared target "
                f"(see consistency-C3). Observed max spread of achieved energy "
                f"{obs['max_energy_spread']:.4f} — reported, NOT gated: k is "
                f"an integer, so the overshoot above a continuous target "
                f"differs per basis and per bin and cannot be held to a fixed "
                f"tolerance.",
                data=obs))

    # ── ③ dof-uncontrolled — severity conditioned on report completeness ──
    # A report that is otherwise complete but omits the degrees-of-freedom
    # control is hiding the confound (FAIL). A report that is openly partial
    # cannot be distinguished from one whose scope never included it (WARN).
    # Completeness is measured at CELL level, not arm level: a partial report
    # can still carry an arm-level per-seed effect vector (103_ does) while its
    # grid records only aggregates. What separates the two is whether the cells
    # themselves are per-seed.
    has_cell_seeds = any(r.get("seed") is not None for r in rows)
    otherwise_complete = bool(have_grid and has_cell_seeds)
    if "dof_control" in roles_present:
        findings.append(Finding("㉘ dof-uncontrolled", "OK",
            "A dof_control arm is present — the same-sample-count shuffled "
            "control is declared."))
    else:
        lvl = "FAIL" if otherwise_complete else "WARN"
        findings.append(Finding("㉘ dof-uncontrolled", lvl,
            "No arm carries role='dof_control'. A gain can come from spending "
            "more degrees of freedom rather than from any direction being "
            "special." + ("" if otherwise_complete else
                          " Report is partial (no grid and/or no per-seed "
                          "vectors), so this is WARN, not FAIL — absence of "
                          "scope is not the same as omission."),
            data={"otherwise_complete": otherwise_complete}))

    # ── ⑦ estimation-eval-overlap — closes with stdlib set algebra ───────
    fit_ids, eval_ids = report.get("basis_fit_ids"), report.get("effect_eval_ids")
    if fit_ids is None or eval_ids is None:
        findings.append(Finding("㉘ estimation-eval-overlap", "WARN",
            "basis_fit_ids / effect_eval_ids not declared — cannot tell whether "
            "the basis was estimated on the same samples the effect is scored on."))
    else:
        inter = sorted(set(fit_ids) & set(eval_ids), key=repr)
        if inter:
            findings.append(Finding("㉘ estimation-eval-overlap", "FAIL",
                f"{len(inter)} id(s) used BOTH to estimate the basis and to "
                f"evaluate the effect: {inter[:8]}. The basis is then fitted to "
                f"the noise it is later credited for.",
                data={"overlap": inter, "n_overlap": len(inter)}))
        else:
            findings.append(Finding("㉘ estimation-eval-overlap", "OK",
                f"Basis-estimation ids ({len(set(fit_ids))}) and effect-evaluation "
                f"ids ({len(set(eval_ids))}) are disjoint.",
                data={"n_overlap": 0}))

    n_basis_fit, ambient = report.get("n_basis_fit"), report.get("ambient_dim")
    if n_basis_fit is not None and ambient:
        if n_basis_fit < 3 * int(ambient):
            findings.append(Finding("㉘ underdetermined-basis", "WARN",
                f"n_basis_fit={n_basis_fit} < 3×ambient_dim={3*int(ambient)}. "
                f"A basis fitted from this few samples can align with noise "
                f"directions by chance. (Declaration lint — whether it actually "
                f"did is a property of the estimation run, which layer A "
                f"cannot see.)",
                data={"n_basis_fit": n_basis_fit, "ambient_dim": int(ambient)}))

    # ── ⑤ vacuous — neither collapse nor survival ────────────────────────
    matched_arms = sorted({r["arm"] for r in rows if r["role"] == "matched_null"} |
                          {a for a, m in arms_meta.items()
                           if isinstance(m, dict) and m.get("role") == "matched_null"},
                          key=repr)
    if matched_arms:
        cert = report.get("certificate") or {}
        failed = [a for a in matched_arms
                  if isinstance(cert.get(a), dict) and cert[a].get("passed") is False]
        undeclared = [a for a in matched_arms if a not in cert]
        if failed:
            findings.append(Finding("㉘ vacuous", "FAIL",
                f"matched_null arm(s) {failed} did not meet their certificate. "
                f"Such an arm counts as NEITHER collapse NOR survival — "
                f"submitting it as evidence of collapse is the vacuous illusion.",
                data={"failed_arms": failed}))
        elif undeclared:
            findings.append(Finding("㉘ vacuous", "WARN",
                f"matched_null arm(s) {undeclared} carry no certificate — "
                f"cannot tell a real collapse from a vacuous one.",
                data={"undeclared_arms": undeclared}))
        else:
            findings.append(Finding("㉘ vacuous", "OK",
                f"All {len(matched_arms)} matched_null arm(s) meet their certificate.",
                data={"arms": matched_arms}))

    # ── ⑥ saturation — the ladder has no resolving power left ────────────
    bar = report.get("bar")
    if bar is not None and have_grid:
        null_rows = [r for r in rows
                     if r["role"] in ("null", "matched_null") and r["effect"] is not None]
        if null_rows:
            points = sorted({r["grid_point"] for r in null_rows
                             if r["grid_point"] is not None}, key=repr)
            if points:
                top = points[-1]
                top_null = [float(r["effect"]) for r in null_rows if r["grid_point"] == top]
                if top_null and min(top_null) >= float(bar):
                    findings.append(Finding("㉘ saturation", "FAIL",
                        f"At the top grid point {top!r} the null arm already "
                        f"clears the bar (min null effect {min(top_null):.4f} ≥ "
                        f"bar {float(bar):.4f}). The grid is saturated, so the "
                        f"ladder cannot separate signal from null there.",
                        data={"top_point": repr(top), "min_null_effect": min(top_null)}))
                else:
                    findings.append(Finding("㉘ saturation", "OK",
                        f"Null arm stays below the bar at the top grid point "
                        f"{top!r} — the ladder still resolves.",
                        data={"top_point": repr(top)}))

    target_arms = sorted({a for a, m in arms_meta.items()
                          if isinstance(m, dict) and m.get("role") == "target"}, key=repr)
    null_arms = sorted({a for a, m in arms_meta.items()
                        if isinstance(m, dict) and m.get("role") in ("null", "matched_null")},
                       key=repr)

    def _seed_vec(arm):
        m = arms_meta.get(arm)
        return list(m.get("effect_by_seed") or []) if isinstance(m, dict) else []

    # ⬆ arm vectors are read by BOTH the coherence law below and the null
    #   ladder, so they are resolved once, before either.

    # ── ⑧ dof-outperforms-target — a coherence law, not a variance heuristic ──
    # A degrees-of-freedom control is the target's own procedure with the
    # claimed structure destroyed. Destroying the structure cannot ADD effect.
    # So a truthful table satisfies effect(dof_control) <= effect(target), and a
    # table that violates it is incoherent in one of exactly two ways, both of
    # which the reader needs to know: the role labels are swapped, or the arm
    # called a control is not one. Either way the report must not be read as a
    # confirmed win.
    #
    # ⚠️ What this deliberately is NOT: a rule that the target must be the
    # variance-optimal basis. That was the first idea and it is a category
    # error — a target arm is a hypothesis about where the EFFECT lives, not
    # where the variance lives, and 103_ labels its PCA arm `data_only` for
    # exactly that reason. Such a rule would FAIL honest reports whose treatment
    # is not the leading principal subspace.
    dof_arms = sorted({a for a, m in arms_meta.items()
                       if isinstance(m, dict) and m.get("role") == "dof_control"},
                      key=repr)
    dof_pairs = {}
    for t in target_arms:
        tv = _seed_vec(t)
        for dc in dof_arms:
            dv = _seed_vec(dc)
            m = min(len(tv), len(dv))
            if m == 0:
                continue
            diffs = [float(dv[i]) - float(tv[i]) for i in range(m)]
            dof_pairs[f"{dc}|{t}"] = {
                "n": m, "mean_excess": sum(diffs) / m,
                "p": _paired_signflip_p(diffs), "exact": m <= 14}
    dof_violated = bool([k for k, v in dof_pairs.items()
                        if v['mean_excess'] > 0 and v['p'] is not None
                        and v['p'] <= alpha])

    # ── ④ null-ladder — paired sign-flip, with the anchor priority rule ──
    if not target_arms or not null_arms:
        findings.append(Finding("㉘ null-ladder", "WARN",
            "Need at least one arm with role='target' and one with "
            "role='null'/'matched_null' to build a ladder.",
            data={"target_arms": target_arms, "null_arms": null_arms}))
    elif not any(_seed_vec(a) for a in target_arms):
        # Averaging first and permuting the average is a silent error: the
        # test then has n=1 no matter how many seeds were run.
        findings.append(Finding("㉘ insufficient-granularity", "WARN",
            "No per-seed effect vector on the target arm(s). A paired "
            "permutation test needs seed-level values; running it on an "
            "arm mean silently reduces n to 1."))
        findings.append(Finding("㉘ null-ladder", "WARN",
            "Cannot run the paired test without per-seed effect vectors."))
    else:
        results = {}
        for t in target_arms:
            tv = _seed_vec(t)
            for nl in null_arms:
                nv = _seed_vec(nl)
                if not nv:
                    continue
                m = min(len(tv), len(nv))
                if m == 0:
                    continue
                diffs = [float(tv[i]) - float(nv[i]) for i in range(m)]
                results[f"{t}|{nl}"] = {
                    "n": m,
                    "mean_diff": sum(diffs) / m,
                    "p": _paired_signflip_p(diffs),
                    "exact": m <= 14,
                }
        if not results:
            findings.append(Finding("㉘ null-ladder", "WARN",
                "No null arm carries a per-seed effect vector to pair against."))
        else:
            beaten = [k for k, v in results.items()
                      if v["p"] is not None and v["p"] <= alpha and v["mean_diff"] > 0]
            all_beaten = len(beaten) == len(results)
            if not all_beaten:
                findings.append(Finding("㉘ null-ladder", "FAIL",
                    f"Target does not clear every null rung "
                    f"({len(beaten)}/{len(results)} at α={alpha}): "
                    + "; ".join(f"{k}: p={v['p']:.4g}, Δ={v['mean_diff']:+.4g}"
                                for k, v in sorted(results.items())),
                    data={"results": results}))
            elif dof_violated:
                # Same priority shape as the anchor rule below: the ladder's
                # arithmetic is fine, but a report whose control beats its
                # treatment has not established which arm the treatment is, so
                # OK here would certify a comparison that was never made. A
                # consumer reading only this finding must not see a green light.
                findings.append(Finding("㉘ null-ladder", "WARN",
                    f"Target clears all {len(results)} null rung(s) at α={alpha}, "
                    f"but a dof_control arm outperforms the target — see "
                    f"dof-outperforms-target. Which arm is the treatment is not "
                    f"established, so this cannot be reported OK.",
                    data={"results": results, "held_by": "dof-outperforms-target"}))
            elif anchor_failed:
                # Priority rule — the reason 103_/105_ put the anchor first and
                # abort INVALID on failure. p is fine; the axis it sits on is not.
                findings.append(Finding("㉘ null-ladder", "WARN",
                    f"Target clears all {len(results)} null rung(s) at α={alpha}, "
                    f"but the anchor FAILED — the ratio normalizer is undefined, "
                    f"so this cannot be reported OK. Fix the anchor first.",
                    data={"results": results, "held_by": "no-anchor"}))
            else:
                findings.append(Finding("㉘ null-ladder", "OK",
                    f"Target clears all {len(results)} null rung(s) at α={alpha} "
                    f"(paired sign-flip; exact enumeration for n ≤ 14).",
                    data={"results": results}))

    if dof_pairs:
        beaten = {k: v for k, v in dof_pairs.items()
                  if v["mean_excess"] > 0 and v["p"] is not None and v["p"] <= alpha}
        leading = {k: v for k, v in dof_pairs.items()
                   if v["mean_excess"] > 0 and k not in beaten}
        if beaten:
            findings.append(Finding("㉘ dof-outperforms-target", "FAIL",
                f"A dof_control arm outperforms the target it controls for "
                f"({len(beaten)}/{len(dof_pairs)} pair(s) at α={alpha}): "
                + "; ".join(f"{k}: Δ={v['mean_excess']:+.4g}, p={v['p']:.4g}"
                            for k, v in sorted(beaten.items()))
                + ". Destroying the claimed structure cannot add effect, so "
                  "either the role labels are swapped or the arm declared a "
                  "control is not one. This report cannot be read as a "
                  "confirmed win regardless of what the null ladder says.",
                data={"pairs": dof_pairs, "violating": sorted(beaten)}))
        elif leading:
            findings.append(Finding("㉘ dof-outperforms-target", "WARN",
                f"A dof_control arm leads its target on the mean but not "
                f"significantly ({len(leading)}/{len(dof_pairs)} pair(s), "
                f"α={alpha}): "
                + "; ".join(f"{k}: Δ={v['mean_excess']:+.4g}, p={v['p']:.4g}"
                            for k, v in sorted(leading.items()))
                + ". Not a verdict — but a control that is level with its "
                  "treatment leaves nothing for the treatment to have caused.",
                data={"pairs": dof_pairs, "leading": sorted(leading)}))
        else:
            findings.append(Finding("㉘ dof-outperforms-target", "OK",
                f"Every dof_control arm stays at or below its target across "
                f"{len(dof_pairs)} pair(s) — the coherence law holds. "
                f"(Scope: this catches a target/dof_control label swap only "
                f"when the true target genuinely beats its control. When the "
                f"two are indistinguishable the swap is invisible here — and "
                f"so is the effect the swap would be hiding.)",
                data={"pairs": dof_pairs}))

    # ── C1–C4 internal-consistency laws (cost-raising, NOT a fix) ────────
    findings.extend(_subspace_consistency(rows, ambient_dim=ambient, dim_tol=dim_tol))
    return findings


def _subspace_consistency(rows: list[dict], *, ambient_dim=None,
                          dim_tol: float = 0.15) -> list[Finding]:
    """C1–C4 — laws a truthful table satisfies internally.

    These raise the price of a lie from "edit one number" to "construct a
    consistent forgery across the whole cell manifold". A consistent forgery
    still passes. C5 (concavity of energy in k) was tested and KILLED: 770 of
    1431 real cells violate it, because it only holds when the sorting
    criterion is the measuring criterion. Shipping it would have been a
    false-positive misfire machine — do not add it back.
    """
    out: list[Finding] = []
    if not rows:
        return out
    groups: dict = {}
    for r in rows:
        if r["k"] is None or r["energy_kept"] is None:
            continue
        groups.setdefault((r["arm"], r["seed"], r["bin"]), []).append(r)

    c1 = []   # same k, different energy
    c2 = []   # k up, energy down
    c3 = []   # achieved below target
    for key, g in sorted(groups.items(), key=lambda kv: repr(kv[0])):
        by_k: dict = {}
        for r in g:
            by_k.setdefault(float(r["k"]), set()).add(float(r["energy_kept"]))
        for k, es in sorted(by_k.items()):
            if len(es) > 1:
                c1.append(f"{key!r} k={k:g} → energies {sorted(es)}")
        ks = sorted(by_k)
        for a, b in zip(ks, ks[1:]):
            if max(by_k[b]) < min(by_k[a]) - 1e-12:
                c2.append(f"{key!r} k {a:g}→{b:g} but energy "
                          f"{min(by_k[a]):.6g}→{max(by_k[b]):.6g}")
        for r in g:
            tgt = r.get("energy_target")
            if tgt is not None and float(r["energy_kept"]) < float(tgt) - 1e-12:
                c3.append(f"{key!r} k={r['k']} energy {float(r['energy_kept']):.6g} "
                          f"< target {float(tgt):.6g}")

    for name, viol, law in (("C1", c1, "same k ⇒ identical energy (energy = f(basis, k))"),
                            ("C2", c2, "k increases ⇒ energy is non-decreasing"),
                            ("C3", c3, "achieved energy ≥ declared target (minimal-k rule)")):
        if viol:
            out.append(Finding(f"㉘ consistency-{name}", "FAIL",
                f"{len(viol)} violation(s) of {law}: " + "; ".join(viol[:3]),
                data={"law": law, "violations": viol[:50], "n_violations": len(viol)}))

    # C4 — the load-bearing one: a null arm's energy/k ≈ 1/d, so the table
    # alone testifies to the ambient dimension. That puts a ceiling on what the
    # target arm's (k, energy) pairs can claim.
    ratios = [float(r["k"]) / float(r["energy_kept"])
              for r in rows
              if r["role"] in ("null", "matched_null")
              and r["k"] not in (None, 0) and r["energy_kept"]]
    if ratios:
        recovered = sum(ratios) / len(ratios)
        data = {"recovered_dim": recovered, "n_null_cells": len(ratios)}
        if ambient_dim:
            rel = abs(recovered - float(ambient_dim)) / float(ambient_dim)
            data.update({"ambient_dim": float(ambient_dim), "rel_error": rel})
            lvl = "OK" if rel <= dim_tol else "WARN"
            out.append(Finding("㉘ consistency-C4", lvl,
                f"Ambient dimension recovered from null arms = {recovered:.2f} "
                f"vs declared {float(ambient_dim):.2f} (relative error {rel:.3f}, "
                f"tol {dim_tol}).", data=data))
        else:
            out.append(Finding("㉘ consistency-C4", "INFO",
                f"Ambient dimension recovered from null arms = {recovered:.2f} "
                f"({len(ratios)} null cells). Declare ambient_dim to have this "
                f"cross-checked.", data=data))
    return out


# ─────────────────────────────────────────────────────────────
# Verification groups + verify() — the three-tier entry point
# ─────────────────────────────────────────────────────────────
GROUPS: dict[str, list[str]] = {
    "ledger":   ["preregister", "verify_chain", "cascade_check"],
    "stats":    ["audit (Wilson CI/direction)", "multiseed_check",
                 "too_good_check", "power_check",
                 "multiple_comparisons_check", "grim_check"],
    "design":   ["baseline_fairness", "gaming_check", "leakage_check",
                 "scope_check", "falsifiability_check",
                 "anchor_basis_check", "threshold_provenance_check",
                 "content_delta_check", "anchor_line_source_check",
                 "anchor_cell_check"],
    "negative": ["negative_audit"],
    "subspace": ["subspace_claim_check"],
    "judge":    ["judge_consistency_check", "judge_bias_check",
                 "inter_rater_agreement", "judge_score_sanity",
                 "judge_swap_check"],
    "ranking":  ["judge_transitivity_check", "ranking_stability_check"],
}

# Finding probe-label symbol → group (labels all start with their symbol)
_SYMBOL_GROUP = {
    "①": "ledger", "⑫": "ledger",
    "④": "stats", "⑤": "stats", "⑦": "stats", "⑧": "stats",
    "⑨": "stats", "⑩": "stats",
    "②": "design", "③": "design", "⑥": "design", "⑪": "design",
    "㉑": "design", "㉒": "design", "㉓": "design",
    "㉔": "design", "㉕": "design", "㉖": "design",
    "⑬": "negative",
    "⑭": "judge", "⑮": "judge", "⑯": "judge", "⑰": "judge", "⑱": "judge",
    "⑲": "ranking", "⑳": "ranking",
    "㉘": "subspace",
}


def group_of(finding: Finding) -> str | None:
    """Return the verification group a Finding belongs to (None if ungrouped)."""
    if finding.probe.startswith("judge-parse"):
        return "judge"
    return _SYMBOL_GROUP.get(finding.probe[:1])


def verify(ledger_path: str, data: dict, *,
           groups: list[str] | None = None) -> list[Finding]:
    """Single entry point — run every probe whose inputs are present in `data`.

    Three tiers of use:
      FULL        verify(ledger, data)                  — everything applicable
      GROUP       verify(ledger, data, groups=["judge"]) — restrict to groups
      INDIVIDUAL  call any probe function directly

    `data` keys (all optional — a probe runs only when its inputs are present):
      claim_id, metric, acc, n, baseline          → core audit (①④a⑩⑪⑫ + ⑦)
      competing_name + competing_acc              → ② baseline fairness
      reward_terms                                → ③ gaming
      train_items + test_items                    → ④a leakage
      seed_results                                → ⑤ multi-seed
      claimed_scope + tested_scope                → ⑥ scope
      anchor_basis                                → ㉑ anchor basis
      threshold_source                            → ㉒ threshold provenance
      judgment_basis                              → ㉓ content delta
      anchor_line_source                          → ㉔ anchor line
      anchor_cell                                 → ㉕ anchor cell
      min_detectable_effect                       → ⑧ power
      check_multiplicity (bool)                   → ⑨ multiple comparisons
      angles [, min_angles, conclusion_scope]     → ⑬ negative audit
      score_pairs                                 → ⑭ judge consistency
      pairwise_results                            → ⑮ judge bias
      ratings_matrix                              → ⑯ inter-rater κ
      scores                                      → ⑰ judge score sanity
      forward_results + swapped_results           → ⑱ position swap
      matches                                     → ⑲ transitivity
      scores_a + scores_b                         → ⑳ ranking stability

    Same key names as the `mm verify --file` / `mm judge --file` JSON formats.
    Raises ValueError on unknown group names.
    """
    if groups:
        unknown = [g for g in groups if g not in GROUPS]
        if unknown:
            raise ValueError(
                f"Unknown group(s): {unknown}. Valid: {sorted(GROUPS)}")
    wanted = set(groups) if groups else set(GROUPS)

    findings: list[Finding] = []

    # Core experiment audit (ledger/stats/design/negative groups)
    if (wanted & {"ledger", "stats", "design", "negative"}):
        if data.get("acc") is not None and data.get("n") is not None:
            findings.extend(full_audit(
                ledger_path, data.get("claim_id", "?"),
                reported_metric=data.get("metric", "acc"),
                reported_acc=data["acc"], n=data["n"],
                baseline=data.get("baseline"), task=data.get("task"),
                competing_name=data.get("competing_name"),
                competing_acc=data.get("competing_acc"),
                reward_terms=data.get("reward_terms"),
                train_items=data.get("train_items"),
                test_items=data.get("test_items"),
                seed_results=data.get("seed_results"),
                claimed_scope=data.get("claimed_scope"),
                tested_scope=data.get("tested_scope"),
                min_detectable_effect=data.get("min_detectable_effect"),
                check_multiplicity=data.get("check_multiplicity", False),
                angles=data.get("angles"),
                min_angles=data.get("min_angles", 3)))
        else:
            # No reported result — still run what doesn't need acc/n
            if data.get("angles") is not None:
                findings.append(negative_audit(
                    ledger_path, angles=data["angles"],
                    min_angles=data.get("min_angles", 3),
                    conclusion_scope=data.get("conclusion_scope"),
                    tested_scope=data.get("tested_scope")))
            if data.get("claim_id"):
                casc = cascade_check(ledger_path, data["claim_id"])
                if casc.level != "OK":
                    findings.append(casc)
            for f in verify_chain(ledger_path):
                if f.level != "OK":
                    findings.append(f)

    # Grounding probes (design group) — run whenever their key is present,
    # independent of acc/n (these check declared design metadata, not results).
    if "design" in wanted:
        if data.get("anchor_basis") is not None:
            findings.append(anchor_basis_check(data["anchor_basis"]))
        if data.get("threshold_source") is not None:
            findings.append(threshold_provenance_check(data["threshold_source"]))
        if data.get("judgment_basis") is not None:
            findings.append(content_delta_check(data["judgment_basis"]))
        if data.get("anchor_line_source") is not None:
            findings.append(anchor_line_source_check(data["anchor_line_source"]))
        if data.get("anchor_cell") is not None:
            findings.append(anchor_cell_check(data["anchor_cell"]))

    # Judge group
    if "judge" in wanted:
        if "score_pairs" in data:
            findings.append(judge_consistency_check(
                [tuple(p) for p in data["score_pairs"]]))
        if "pairwise_results" in data:
            findings.append(judge_bias_check(data["pairwise_results"]))
        if "ratings_matrix" in data:
            findings.append(inter_rater_agreement(
                [tuple(r) for r in data["ratings_matrix"]]))
        if "scores" in data:
            findings.append(judge_score_sanity(data["scores"]))
        if "forward_results" in data and "swapped_results" in data:
            findings.append(judge_swap_check(
                data["forward_results"], data["swapped_results"]))

    # Ranking group
    if "ranking" in wanted:
        if "matches" in data:
            findings.append(judge_transitivity_check(
                [tuple(m) for m in data["matches"]]))
        if "scores_a" in data and "scores_b" in data:
            findings.append(ranking_stability_check(
                data["scores_a"], data["scores_b"]))

    # Group filter (full_audit emits across groups — keep only requested)
    if groups:
        findings = [f for f in findings if group_of(f) in wanted]

    return findings


# ─────────────────────────────────────────────────────────────
# Report printer
# ─────────────────────────────────────────────────────────────
def report(title: str, findings: list[Finding]) -> None:
    icon = {"OK": "✅", "WARN": "⚠️ ", "FAIL": "🔴", "INFO": "ℹ️ ", "N/A": "➖"}
    worst = "FAIL" if any(f.level == "FAIL" for f in findings) else \
            "WARN" if any(f.level == "WARN" for f in findings) else "OK"
    print(f"\n🪞 Audit: {title}")
    print(f"   Overall: {icon[worst]} {worst}")
    for f in findings:
        print(f"   {icon.get(f.level, 'ℹ️')} [{f.probe}] {f.msg}")


# ─────────────────────────────────────────────────────────────
# ⚙ Calibration + Witness run
# ─────────────────────────────────────────────────────────────
def calibrate() -> list[Finding]:
    """Self-test: run synthetic known-good/known-bad cases through key probes.

    Returns [OK] when all 5 cases produce expected outcomes — confirms the
    mirror itself has no regressions.  Returns [FAIL] if any case breaks.
    Run before witness() or in CI to confirm the tool is working correctly.
    """
    errors: list[str] = []

    # Case 1: tiny sample must trigger small-sample FAIL
    f = audit("/dev/null", "_calibrate",
              reported_metric="acc", reported_acc=0.556, n=9)
    if not any(x.level == "FAIL" for x in f):
        errors.append("n=9 small-sample probe should FAIL")

    # Case 2: honest large sample must not FAIL
    f = audit("/dev/null", "_calibrate",
              reported_metric="acc", reported_acc=0.78, n=1000)
    if any(x.level == "FAIL" for x in f):
        errors.append("n=1000 honest result should not produce FAIL")

    # Case 3: GRIM-impossible value must FAIL
    g = grim_check(0.33, 10)
    if g.level != "FAIL":
        errors.append("GRIM(0.33, n=10) should be FAIL")

    # Case 4: GRIM-possible value must be OK
    g = grim_check(0.70, 10)
    if g.level != "OK":
        errors.append("GRIM(0.70, n=10) should be OK")

    # Case 5: baseline inversion must FAIL
    b = baseline_fairness("competitor", 0.60, 0.80)
    if b.level != "FAIL":
        errors.append("Inverted baseline (our=0.60 < competitor=0.80) should FAIL")

    if errors:
        return [Finding("⚙ calibrate", "FAIL",
                        "Mirror is miscalibrated: " + "; ".join(errors))]
    return [Finding("⚙ calibrate", "OK",
                    "5/5 synthetic cases correct — mirror is calibrated.")]


def anchor(ledger_path: str) -> dict:
    """Compute a tamper-evident snapshot of the ledger's current state.

    Outputs a compact dict suitable for piping to any external storage:
      ts:           ISO timestamp
      entry_count:  number of entries currently in the ledger
      head_seal:    seal of the last entry ('empty' if ledger is missing/empty)
      anchor_hash:  SHA-256 of the entire ledger file bytes — changes on any
                    modification (add, edit, delete, replace)
      chain_ok:     True if verify_chain() found no failures

    This is the recommended defence against complete ledger replacement, which
    chain hashes alone cannot detect.  Pipe to wherever you trust:

        mm anchor >> ~/Dropbox/mm_anchors.jsonl
        mm anchor | gh gist create -
        mm anchor | aws s3 cp - s3://bucket/mm_anchor.json

    The receiver has an independent timestamp proof of what the ledger contained.
    """
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if not os.path.exists(ledger_path):
        return {
            "_type":        "anchor",
            "ts":           ts,
            "ledger_path":  ledger_path,
            "entry_count":  0,
            "head_seal":    "empty",
            "anchor_hash":  "empty",
            "chain_ok":     True,
        }

    with open(ledger_path, "rb") as f:
        raw = f.read()

    anchor_hash = hashlib.sha256(raw).hexdigest()
    entry_count = sum(
        1 for line in raw.decode("utf-8", errors="replace").splitlines()
        if line.strip()
    )
    head_seal = _get_last_seal(ledger_path)
    chain_ok = not any(
        f.level == "FAIL" for f in verify_chain(ledger_path)
    )
    return {
        "_type":        "anchor",
        "ts":           ts,
        "ledger_path":  ledger_path,
        "entry_count":  entry_count,
        "head_seal":    head_seal,
        "anchor_hash":  anchor_hash,
        "chain_ok":     chain_ok,
    }


def certificate(ledger_path: str, claim_id: str, *,
                findings: list[Finding] | None = None) -> dict:
    """📜 Issue a sealed verification certificate for a claim.

    Collapses the full integrity state of a claim into a single verifiable
    artifact that can be embedded in a paper, README, or release notes:

      - pre-registration seal (and whether it still verifies)
      - ledger chain integrity + anchor_hash (pins the exact ledger state)
      - retraction / cascade status
      - optional audit findings summary (pass `findings=audit(...)`)

    Verdict logic:
      REJECTED                 — chain broken, prereg seal tampered, claim
                                 retracted, or any FAIL finding
      UNVERIFIED               — no pre-registration exists for this claim
      CERTIFIED-WITH-WARNINGS  — stale dependency or WARN findings present
      CERTIFIED                — every check is clean

    The certificate embeds the ledger's anchor_hash, so it attests to one
    specific ledger state: regenerate the certificate after any ledger change.
    The certificate itself is sealed (SHA-256) — any field edit is detectable.
    Not appended to the ledger; it is an output artifact like anchor().
    """
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    a = anchor(ledger_path)
    pre = _load_prereg(ledger_path, claim_id)
    prereg_seal = pre["seal"] if pre else None
    seal_ok = _verify_seal(pre) if pre else None
    casc = cascade_check(ledger_path, claim_id)

    f_ok = f_warn = f_fail = 0
    if findings is not None:
        for f in findings:
            if f.level == "FAIL":
                f_fail += 1
            elif f.level == "WARN":
                f_warn += 1
            else:
                f_ok += 1

    if (not a["chain_ok"] or (pre is not None and not seal_ok)
            or casc.level == "FAIL" or f_fail):
        verdict = "REJECTED"
    elif pre is None:
        verdict = "UNVERIFIED"
    elif casc.level == "WARN" or f_warn:
        verdict = "CERTIFIED-WITH-WARNINGS"
    else:
        verdict = "CERTIFIED"

    cert: dict = {
        "_type":          "certificate",
        "ts":             ts,
        "claim_id":       claim_id,
        "verdict":        verdict,
        "prereg_seal":    prereg_seal,
        "prereg_seal_ok": seal_ok,
        "cascade":        casc.level,
        "chain_ok":       a["chain_ok"],
        "ledger_entries": a["entry_count"],
        "anchor_hash":    a["anchor_hash"],
        "findings":       ({"ok": f_ok, "warn": f_warn, "fail": f_fail}
                           if findings is not None else None),
    }
    cert["seal"] = hashlib.sha256(
        json.dumps(cert, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return cert


_BADGE_STYLE = {
    # verdict → (shields.io color name, hex for local SVG)
    "CERTIFIED":               ("brightgreen", "#4c1"),
    "CERTIFIED-WITH-WARNINGS": ("yellow",      "#dfb317"),
    "UNVERIFIED":              ("lightgrey",   "#9f9f9f"),
    "REJECTED":                ("red",         "#e05d44"),
}


def _shields_escape(s: str) -> str:
    """Escape a string for a shields.io static-badge URL segment."""
    return s.replace("-", "--").replace("_", "__").replace(" ", "_")


def badge(cert: dict, *, fmt: str = "markdown") -> str:
    """🏷 Render a certificate as an embeddable badge.

    Args:
        cert: dict returned by certificate().
        fmt:  "markdown" — shields.io image markdown for README embedding
              "svg"      — self-contained flat SVG (offline, no external service)

    The SVG embeds the certificate seal in a <title> tooltip so the badge is
    traceable back to the exact sealed certificate it renders.
    """
    verdict = cert["verdict"]
    claim_id = cert["claim_id"]
    if verdict not in _BADGE_STYLE:
        raise ValueError(f"Unknown verdict: {verdict!r}")
    color_name, color_hex = _BADGE_STYLE[verdict]

    if fmt == "markdown":
        label = _shields_escape(f"🪞 {claim_id}")
        msg = _shields_escape(verdict)
        return (f"![🪞 {claim_id}: {verdict}]"
                f"(https://img.shields.io/badge/{label}-{msg}-{color_name})")

    if fmt == "svg":
        label = f"🪞 {claim_id}"
        # ~6.5 px per char + padding; emoji counts double
        lw = int(len(label) * 6.5) + 16
        vw = int(len(verdict) * 6.5) + 16
        total = lw + vw
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="20" role="img" aria-label="{label}: {verdict}">
  <title>{label}: {verdict} (seal {cert['seal']}, anchor {cert['anchor_hash'][:16]}…)</title>
  <rect width="{lw}" height="20" fill="#555"/>
  <rect x="{lw}" width="{vw}" height="20" fill="{color_hex}"/>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="{lw / 2:.0f}" y="14">{label}</text>
    <text x="{lw + vw / 2:.0f}" y="14">{verdict}</text>
  </g>
</svg>"""

    raise ValueError(f"Unknown badge format: {fmt!r} (use 'markdown' or 'svg')")


def witness(ledger_path: str, claim_id: str, command: list[str], *,
            timeout: int | None = None) -> dict:
    """Execute command and seal a tamper-evident witness record in the ledger.

    Runs the command as a subprocess, captures stdout/stderr/returncode, hashes
    the output, and appends a chain-linked entry (with _type='witness') to the
    ledger file.  The sealed record proves: which command ran, when, and what
    it produced — output_hash changes if anything in stdout/stderr/returncode
    changes.

    Returns the witness entry dict (keys: seal, output_hash, returncode, …).
    Does NOT silently ignore re-runs — every call appends a new entry.
    """
    import subprocess

    ts_start = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        proc = subprocess.run(command, capture_output=True, text=True,
                              timeout=timeout)
        stdout, stderr = proc.stdout, proc.stderr
        returncode = proc.returncode
        run_status = "ok"
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or b"").decode("utf-8", errors="replace") \
                 if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = (exc.stderr or b"").decode("utf-8", errors="replace") \
                 if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        returncode, run_status = -1, "timeout"
    except Exception as exc:
        stdout, stderr = "", str(exc)
        returncode, run_status = -1, "error"

    ts_end = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    output_hash = hashlib.sha256(
        f"{returncode}\n{stdout}\n{stderr}".encode()
    ).hexdigest()

    entry: dict = {
        "_type":       "witness",
        "ts_start":    ts_start,
        "ts_end":      ts_end,
        "claim_id":    claim_id,
        "command":     command,
        "returncode":  returncode,
        "run_status":  run_status,
        "output_hash": output_hash,
    }
    prev_seal = _get_last_seal(ledger_path)
    entry["prev_seal"] = prev_seal
    entry["seal"] = hashlib.sha256(
        json.dumps(entry, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()

    with open(ledger_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────
def _auto(name: str, ledger: str = "mm_ledger.jsonl") -> None:
    import sys
    cands = [f"{name}.json", f"results/{name}.json", f"mm_results/{name}.json"]
    path = next((c for c in cands if os.path.exists(c)), None)
    if not path:
        print(f"🪞 No result file found for '{name}'. "
              f"Write your evaluation result to {name}.json.")
        print(f'   Expected format: {{"acc":0.72,"n":500,"metric":"acc","baseline":0.5}}')
        sys.exit(1)
    d = json.load(open(path, encoding="utf-8"))
    cid = d.get("claim_id", name)
    acc, n = d.get("acc"), d.get("n")
    if acc is None or n is None:
        print(f"🪞 Error: {path} must contain 'acc' and 'n'.")
        sys.exit(1)
    print(f"📂 Loaded {path}")
    report(cid, audit(ledger, cid, reported_metric=d.get("metric", "acc"),
                      reported_acc=acc, n=n, baseline=d.get("baseline", 0.5)))


def _cli() -> None:
    import argparse, sys
    _SUBCMDS = {"register", "audit", "calibrate", "run", "anchor", "retract",
                "negative", "judge", "certify", "verify"}
    if len(sys.argv) == 2 and sys.argv[1] not in _SUBCMDS \
            and not sys.argv[1].startswith("-"):
        _auto(sys.argv[1]); return
    p = argparse.ArgumentParser(
        prog="mm",
        description="🪞 Measurement Mirror — audit AI evaluation claims")
    p.add_argument("--ledger", default="mm_ledger.jsonl",
                   help="Ledger path (default: ./mm_ledger.jsonl)")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("register",
                       help="Seal evaluation criteria BEFORE running the experiment")
    r.add_argument("claim_id")
    r.add_argument("--metric", required=True)
    r.add_argument("--min-n", type=int, default=200)
    r.add_argument("--baseline", type=float, default=0.5)
    r.add_argument("--pass", dest="pass_threshold", type=float, default=0.60)
    r.add_argument("--kill", dest="kill_condition", default=None,
                   help='Human-readable kill condition, e.g. "acc < 0.55 on held-out"')
    r.add_argument("--kill-threshold", type=float, default=None,
                   help="Numeric kill threshold for automatic evaluation")
    r.add_argument("--kill-direction", choices=["below", "above"], default="below",
                   help="Fail when reported value is below/above threshold (default: below)")
    r.add_argument("--depends-on", dest="depends_on", nargs="+", default=None,
                   help="Claim IDs this claim depends on (space-separated)")

    a = sub.add_parser("audit", help="Audit evaluation results")
    a.add_argument("claim_id", nargs="?")
    a.add_argument("--acc", type=float)
    a.add_argument("--n", type=int)
    a.add_argument("--metric", default="acc")
    a.add_argument("--baseline", type=float, default=0.5)
    a.add_argument("--file", help="Result JSON: {claim_id, metric, acc, n, baseline}")

    sub.add_parser("calibrate",
                   help="Self-test: verify the mirror's probes return expected outcomes")

    an = sub.add_parser("anchor",
                        help="Print tamper-evident ledger snapshot to stdout for external archival")
    an.add_argument("--pretty", action="store_true",
                    help="Pretty-print JSON (default: compact single line for piping)")

    rt = sub.add_parser("retract",
                        help="Retract a claim; cascades STALE to all dependent claims")
    rt.add_argument("claim_id", help="Claim ID to retract")
    rt.add_argument("--reason", required=True,
                    help="Reason for retraction (e.g. 'data labelling error discovered')")

    ng = sub.add_parser("negative",
                        help="Gate a Resolved-Negative conclusion: angle-count + scope check")
    ng.add_argument("--angles", nargs="+", required=True,
                    help="Claim IDs of independent test angles (space-separated)")
    ng.add_argument("--min-angles", type=int, default=3,
                    help="Minimum required angles (default: 3)")

    vf = sub.add_parser("verify",
                        help="One-shot verification: full or group-filtered, from a JSON file")
    vf.add_argument("--file", default=None,
                    help="JSON data file — same keys as the Python verify() data dict")
    vf.add_argument("--groups", nargs="+", choices=sorted(GROUPS), default=None,
                    help="Restrict to verification group(s) "
                         f"(default: all — {', '.join(sorted(GROUPS))})")
    vf.add_argument("--list-groups", action="store_true",
                    help="List verification groups and their probes, then exit")

    jd = sub.add_parser("judge",
                        help="Audit LLM-judge scores from a JSON file (probes ⑭⑮⑯⑰⑱)")
    jd.add_argument("--file", required=True,
                    help="JSON with any of: score_pairs, pairwise_results, "
                         "ratings_matrix, scores, forward_results+swapped_results")

    ct = sub.add_parser("certify",
                        help="Issue a sealed verification certificate for a claim")
    ct.add_argument("claim_id")
    ct.add_argument("--acc", type=float, default=None,
                    help="Optional: reported accuracy — runs audit() and folds findings in")
    ct.add_argument("--n", type=int, default=None,
                    help="Sample size (required with --acc)")
    ct.add_argument("--metric", default="acc")
    ct.add_argument("--baseline", type=float, default=0.5)
    ct.add_argument("--pretty", action="store_true",
                    help="Pretty-print JSON (default: compact single line for piping)")
    ct.add_argument("--badge", choices=["markdown", "svg"], default=None,
                    help="Output an embeddable badge instead of the JSON certificate")

    rn = sub.add_parser("run",
                        help="Calibrate + witness-execute a command, sealing the run record")
    rn.add_argument("claim_id", help="Experiment / claim identifier")
    rn.add_argument("command", nargs=argparse.REMAINDER,
                    help="Command to execute (prefix with -- to separate mm flags)")
    rn.add_argument("--timeout", type=int, default=None,
                    help="Subprocess timeout in seconds (default: none)")
    rn.add_argument("--no-calibrate", dest="no_calibrate", action="store_true",
                    help="Skip self-calibration before running the command")

    args = p.parse_args()
    if args.cmd == "register":
        kill_thresh = None
        if args.kill_threshold is not None:
            kill_thresh = {
                "metric": args.metric,
                "threshold": args.kill_threshold,
                "direction": args.kill_direction,
            }
        e = preregister(args.ledger, args.claim_id, metric=args.metric,
                        min_n=args.min_n, baseline=args.baseline,
                        pass_threshold=args.pass_threshold,
                        kill_condition=args.kill_condition,
                        kill_threshold=kill_thresh,
                        depends_on=args.depends_on)
        kill_note = ""
        if kill_thresh:
            op = "<" if args.kill_direction == "below" else ">"
            kill_note = (f"  kill={args.metric} {op} {args.kill_threshold}")
        elif args.kill_condition:
            kill_note = f"  kill(text)={args.kill_condition!r}"
        print(f"🔒 Sealed: {args.claim_id}  metric={args.metric} "
              f"min_n={args.min_n} baseline={args.baseline}{kill_note}  seal={e['seal']}")
    elif args.cmd == "audit":
        if args.file:
            d = json.load(open(args.file, encoding="utf-8"))
            cid = d.get("claim_id", "?")
            acc, n = d.get("acc"), d.get("n")
            metric, baseline = d.get("metric", "acc"), d.get("baseline", 0.5)
        else:
            cid, acc, n = args.claim_id, args.acc, args.n
            metric, baseline = args.metric, args.baseline
        if acc is None or n is None:
            p.error("audit requires --acc and --n (or --file)")
        report(cid, audit(args.ledger, cid, reported_metric=metric,
                          reported_acc=acc, n=n, baseline=baseline))
    elif args.cmd == "calibrate":
        report("Mirror Calibration", calibrate())
    elif args.cmd == "anchor":
        a = anchor(args.ledger)
        if args.pretty:
            print(json.dumps(a, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(a, ensure_ascii=False))
    elif args.cmd == "retract":
        e = retract(args.ledger, args.claim_id, args.reason)
        print(f"🚫 Retracted: {args.claim_id}  reason={args.reason!r}  seal={e['seal']}")
    elif args.cmd == "negative":
        report("Negative-claim audit",
               [negative_audit(args.ledger, angles=args.angles,
                               min_angles=args.min_angles)])
    elif args.cmd == "verify":
        if args.list_groups:
            print("🪞 Verification groups:")
            for g in sorted(GROUPS):
                print(f"   {g:<9} {', '.join(GROUPS[g])}")
            return
        if not args.file:
            p.error("verify requires --file (or use --list-groups)")
        d = json.load(open(args.file, encoding="utf-8"))
        fs = verify(args.ledger, d, groups=args.groups)
        if not fs:
            print("🪞 No probes activated — the data file contains no "
                  "recognized keys (see `mm verify --list-groups`).")
            return
        scope_note = f" [{', '.join(args.groups)}]" if args.groups else " [full]"
        report(f"verify{scope_note} ({args.file})", fs)
    elif args.cmd == "judge":
        d = json.load(open(args.file, encoding="utf-8"))
        fs: list[Finding] = []
        if "score_pairs" in d:
            fs.append(judge_consistency_check([tuple(x) for x in d["score_pairs"]]))
        if "pairwise_results" in d:
            fs.append(judge_bias_check(d["pairwise_results"]))
        if "ratings_matrix" in d:
            fs.append(inter_rater_agreement([tuple(x) for x in d["ratings_matrix"]]))
        if "scores" in d:
            fs.append(judge_score_sanity(d["scores"]))
        if "forward_results" in d and "swapped_results" in d:
            fs.append(judge_swap_check(d["forward_results"], d["swapped_results"]))
        if "matches" in d:
            fs.append(judge_transitivity_check([tuple(m) for m in d["matches"]]))
        if "scores_a" in d and "scores_b" in d:
            fs.append(ranking_stability_check(d["scores_a"], d["scores_b"]))
        if not fs:
            p.error("judge --file JSON must contain at least one of: score_pairs, "
                    "pairwise_results, ratings_matrix, scores, "
                    "forward_results+swapped_results, matches, scores_a+scores_b")
        report(f"LLM-judge audit ({args.file})", fs)
    elif args.cmd == "certify":
        fnds = None
        if args.acc is not None:
            if args.n is None:
                p.error("certify --acc requires --n")
            fnds = audit(args.ledger, args.claim_id, reported_metric=args.metric,
                         reported_acc=args.acc, n=args.n, baseline=args.baseline)
        c = certificate(args.ledger, args.claim_id, findings=fnds)
        if args.badge:
            print(badge(c, fmt=args.badge))
        else:
            print(json.dumps(c, indent=2 if args.pretty else None,
                             ensure_ascii=False))
    elif args.cmd == "run":
        cmd = [c for c in (args.command or []) if c != "--"]
        if not cmd:
            p.error("run requires a command: mm run <claim_id> [--] <command...>")
        if not args.no_calibrate:
            cal = calibrate()
            report("Self-calibration", cal)
            if any(f.level == "FAIL" for f in cal):
                print("⚠️  Calibration failed — "
                      "witness run continues but verify your installation.")
        w = witness(args.ledger, args.claim_id, cmd, timeout=args.timeout)
        print(f"\n🎬 Witnessed: {args.claim_id}")
        print(f"   Command:     {' '.join(w['command'])}")
        print(f"   Started:     {w['ts_start']}")
        print(f"   Ended:       {w['ts_end']}")
        print(f"   Exit code:   {w['returncode']}  ({w['run_status']})")
        print(f"   Output hash: {w['output_hash']}")
        print(f"   Prev seal:   {w['prev_seal']}")
        print(f"   Seal:        {w['seal']}")


if __name__ == "__main__":
    _cli()
