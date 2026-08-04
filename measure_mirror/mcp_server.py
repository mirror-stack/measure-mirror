"""
🪞 Measurement Mirror — MCP server

Exposes 26 probes + 6 utilities (37 tools) + the verify() umbrella (full / group-filtered) as MCP tools via stdio transport so any
MCP-compatible AI (Claude Code, Cursor, Windsurf, …) can call them
directly mid-conversation.

Install:
    pip install "measure-mirror[mcp]"

Claude Code (.mcp.json in project root):
    {
      "mcpServers": {
        "measure-mirror": {
          "command": "python",
          "args": ["-m", "measure_mirror.mcp_server"],
          "cwd": "/path/to/measure-mirror"
        }
      }
    }

Other MCP clients: run `mm-mcp` as the stdio server command.
"""
import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from . import mm

server = Server("measure-mirror")


# ─────────────────────────────────────────────────────────────
# Tool registry
# ─────────────────────────────────────────────────────────────
@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="mm_register",
            description=(
                "Seal evaluation criteria BEFORE running the experiment (pre-registration). "
                "Each entry is chain-hashed to the previous one — deletions and insertions "
                "are detected by mm_verify_chain. Must be called before the experiment runs. "
                "kill_condition / kill_threshold register what would falsify the claim — "
                "claims without either are flagged 'unfalsifiable' at audit time (⑪)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ledger_path":    {"type": "string",  "description": "Path to the JSONL ledger file"},
                    "claim_id":       {"type": "string",  "description": "Experiment / claim identifier"},
                    "metric":         {"type": "string",  "description": "Evaluation metric name (e.g. acc, f1)"},
                    "min_n":          {"type": "integer", "description": "Minimum required sample size", "default": 200},
                    "baseline":       {"type": "number",  "description": "Fair comparison baseline performance", "default": 0.5},
                    "pass_threshold": {"type": "number",  "description": "Registered passing bar", "default": 0.60},
                    "kill_condition": {"type": "string",  "description":
                                       "Human-readable falsification criterion, e.g. 'acc < 0.55 on held-out test'",
                                       "default": None},
                    "kill_threshold": {"type": "object",  "description":
                                       "Structured auto-evaluable form: "
                                       "{\"metric\": \"acc\", \"threshold\": 0.55, \"direction\": \"below\"}",
                                       "default": None},
                    "depends_on":     {"type": "array",   "items": {"type": "string"},
                                       "description":
                                       "Claim IDs this claim depends on. If any are retracted, "
                                       "this claim becomes STALE (⑫ cascade).",
                                       "default": None},
                    "anchor_basis":   {"type": "string",  "description":
                                       "Positive-control anchor basis, declared at seal time: "
                                       "'dynamics-measured' | 'structural-argument'. "
                                       "mm_audit reads it back and runs ㉑ automatically (SPEC amendment A1).",
                                       "default": None},
                    "threshold_source": {"type": "string", "description":
                                       "Pass/kill threshold provenance, declared at seal time: "
                                       "'external-fixed' | 'observed-distribution'. "
                                       "mm_audit reads it back and runs ㉒ automatically (SPEC amendment A1).",
                                       "default": None},
                    "anchor_cell":    {"type": "string",  "description":
                                       "PC anchor cell placement: 'deep-regime' | 'threshold-cell'. "
                                       "mm_audit runs ㉕ automatically (SPEC amendment A2).",
                                       "default": None},
                    "anchor_line_source": {"type": "string", "description":
                                       "PC anchor line source: 'separator-aligned' | 'copied-from-other-cell'. "
                                       "mm_audit runs ㉔ automatically (SPEC amendment A2).",
                                       "default": None},
                    "known_confounds": {"type": "array", "items": {"type": "string"},
                                       "description":
                                       "Confounds declared BEFORE results — a pre-declared confound "
                                       "legitimizes later attribution cycles; audit surfaces them as INFO "
                                       "(SPEC amendment A2).",
                                       "default": None},
                    "pre_seal_checks": {"type": "array", "items": {"type": "string"},
                                       "description":
                                       "Cheap machine-checks run BEFORE sealing: reachability-smoke | "
                                       "mass-balance-audit | neutral-control | manipulation-check | "
                                       "positive-control. mm_prereg_lint (㉗) reads them back; declaring "
                                       "none draws an INFO nudge.",
                                       "default": None},
                },
                "required": ["ledger_path", "claim_id", "metric"],
            },
        ),
        types.Tool(
            name="mm_cascade_check",
            description=(
                "⑫ Retraction cascade: check if a claim or any of its transitive dependencies "
                "has been retracted. "
                "FAIL when claim_id itself is retracted. "
                "WARN when the claim is STALE (depends on a retracted claim). "
                "OK when no retraction risk is found. "
                "Runs automatically inside mm_audit — call standalone to check without a full audit."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ledger_path": {"type": "string", "description": "Path to the JSONL ledger file"},
                    "claim_id":    {"type": "string", "description": "Claim ID to check"},
                },
                "required": ["ledger_path", "claim_id"],
            },
        ),
        types.Tool(
            name="mm_retract",
            description=(
                "Append a chain-linked retraction entry to the ledger. "
                "Marks claim_id as retracted; any claim that depends on it will be "
                "flagged STALE by mm_cascade_check. The retraction record is chain-linked "
                "so it cannot be silently deleted from the ledger."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ledger_path": {"type": "string", "description": "Path to the JSONL ledger file"},
                    "claim_id":    {"type": "string", "description": "Claim ID to retract"},
                    "reason":      {"type": "string", "description": "Reason for retraction"},
                },
                "required": ["ledger_path", "claim_id", "reason"],
            },
        ),
        types.Tool(
            name="mm_subspace_claim_check",
            description=(
                "㉘ Audit a submitted 'the gain lives in a few input directions' "
                "(active-subspace-style) claim. ⚠️ THIS IS A DECLARATION AUDITOR, "
                "NOT A RECOMPUTER — it reads the submitted table only, never the "
                "basis or the model, so a falsified energy_kept passes. The C1–C4 "
                "consistency laws raise the cost of a false table; they do not "
                "close the hole. "
                "Findings: no-anchor (declaration lint) · energy-not-matched · "
                "dof-uncontrolled · null-ladder (paired sign-flip; exact 2ⁿ "
                "enumeration for n ≤ 14) · vacuous · saturation · "
                "estimation-eval-overlap. Priority rule: when the anchor FAILs the "
                "null-ladder cannot report OK, because the ratio normalizer is "
                "undefined. A report with no grid yields N/A for energy matching, "
                "which is NOT a failure."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "report":      {"type": "object",
                                    "description":
                                    "Submitted claim table: anchor, grid, cells "
                                    "(arm/role/seed/grid_point/k/energy_kept/effect; "
                                    "k and energy_kept may be per-bin vectors), arms "
                                    "(with effect_by_seed), bar, ambient_dim, "
                                    "n_basis_fit, basis_fit_ids, effect_eval_ids, "
                                    "certificate. Roles: target · null · data_only · "
                                    "dof_control · matched_null"},
                    "energy_tol":  {"type": "number", "default": 0.05,
                                    "description":
                                    "Max relative spread of retained energy across "
                                    "arms at one grid point"},
                    "alpha":       {"type": "number", "default": 0.05,
                                    "description": "Significance level for the ladder"},
                    "dim_tol":     {"type": "number", "default": 0.15,
                                    "description":
                                    "Tolerance for C4 recovered-vs-declared "
                                    "ambient dimension"},
                },
                "required": ["report"],
            },
        ),
        types.Tool(
            name="mm_negative_audit",
            description=(
                "⑬ Gate a Resolved-Negative conclusion: angle-count gate + optional scope check. "
                "A negative conclusion is only trustworthy when multiple independent "
                "pre-registered experiments have all converged. "
                "FAIL when fewer than min_angles (default 3) are provided, when any angle "
                "lacks a preregister entry, or when conclusion_scope is broader than tested_scope. "
                "WARN when angles are sufficient but at least one is retracted (weakened case). "
                "OK when all checks pass."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ledger_path":       {"type": "string",
                                          "description": "Path to the JSONL ledger file"},
                    "angles":            {"type": "array", "items": {"type": "string"},
                                          "description":
                                          "Claim IDs of independent test angles"},
                    "min_angles":        {"type": "integer", "default": 3,
                                          "description": "Minimum required angles (default 3)"},
                    "conclusion_scope":  {"type": "array", "items": {"type": "string"},
                                          "description":
                                          "Scope of the negative conclusion (optional)",
                                          "default": None},
                    "tested_scope":      {"type": "array", "items": {"type": "string"},
                                          "description":
                                          "Scopes actually tested (optional)",
                                          "default": None},
                },
                "required": ["ledger_path", "angles"],
            },
        ),
        types.Tool(
            name="mm_falsifiability_check",
            description=(
                "⑪ Popper gate: verify that a kill-condition was registered and "
                "auto-evaluate it against the reported result. "
                "FAIL when kill_threshold is triggered (claim falsified by its own criterion). "
                "WARN when no kill-condition exists (unfalsifiable claim). "
                "OK when threshold is not triggered or text-only condition is registered. "
                "Runs automatically inside mm_audit — call standalone to check without full audit."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ledger_path":  {"type": "string",  "description": "Path to the JSONL ledger file"},
                    "claim_id":     {"type": "string",  "description": "Experiment / claim identifier"},
                    "reported_acc": {"type": "number",  "description":
                                     "Reported accuracy/proportion (optional; required to evaluate kill_threshold)",
                                     "default": None},
                },
                "required": ["ledger_path", "claim_id"],
            },
        ),
        types.Tool(
            name="mm_prereg_lint",
            description=(
                "㉗ Lint a sealed preregistration for QUALITY defects — the cheap machine-check "
                "to run right before spending compute. Unlike mm_falsifiability_check (which asks "
                "'does a kill-condition exist?'), this asks 'is the seal well-formed enough that "
                "the automated checks can fire, and is the bar meaningful?'. "
                "FAIL: kill-condition prose leaked into the `metric` field (malformed call), or a "
                "pass bar at/below declared chance. "
                "WARN: quantified kill written as free text with no structured kill_threshold, or "
                "min_n below the small-sample floor. "
                "INFO: no pre-seal machine-checks declared (reachability / accounting / neutral-"
                "control / manipulation / positive-control). "
                "claim_id omitted → lint every preregistration in the ledger."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ledger_path": {"type": "string", "description": "Path to the JSONL ledger file"},
                    "claim_id":    {"type": "string", "description":
                                    "Claim identifier to lint (optional; omit to lint all)",
                                    "default": None},
                },
                "required": ["ledger_path"],
            },
        ),
        types.Tool(
            name="mm_verify_chain",
            description=(
                "① Verify the full ledger chain integrity. "
                "Checks individual SHA-256 seals AND chain links (prev_seal). "
                "Catches: tampered entries, deleted entries, inserted entries. "
                "Call after any suspicious ledger activity, or routinely in CI."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ledger_path": {"type": "string", "description": "Path to the JSONL ledger file"},
                },
                "required": ["ledger_path"],
            },
        ),
        types.Tool(
            name="mm_audit",
            description=(
                "Audit a classification/accuracy metric result with probes ①+④a. "
                "Runs: Wilson CI small-sample check, direction check, pre-registration "
                "comparison (metric-swap, min_n, pass_threshold, seal tamper). "
                "Call after the experiment has completed."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ledger_path":     {"type": "string"},
                    "claim_id":        {"type": "string"},
                    "reported_metric": {"type": "string", "description": "Metric name being reported"},
                    "reported_acc":    {"type": "number", "description": "Reported accuracy (0–1)"},
                    "n":               {"type": "integer", "description": "Sample size"},
                    "baseline":        {"type": "number", "description": "Baseline performance (default 0.5)"},
                },
                "required": ["ledger_path", "claim_id", "reported_metric", "reported_acc", "n"],
            },
        ),
        types.Tool(
            name="mm_continuous_audit",
            description=(
                "Audit a continuous/regression metric (MSE, Pearson r, RMSE, …). "
                "Uses direction check + optional effect-size instead of Wilson CI. "
                "Set higher_better=False for loss metrics (lower is better)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ledger_path":      {"type": "string"},
                    "claim_id":         {"type": "string"},
                    "reported_metric":  {"type": "string"},
                    "reported_value":   {"type": "number"},
                    "baseline_value":   {"type": "number"},
                    "n":                {"type": "integer"},
                    "std":              {"type": "number", "description": "Std dev (optional, enables effect-size check)"},
                    "higher_better":    {"type": "boolean", "default": True},
                },
                "required": ["ledger_path", "claim_id", "reported_metric",
                             "reported_value", "baseline_value", "n"],
            },
        ),
        types.Tool(
            name="mm_full_audit",
            description=(
                "Run all probes in one call. Optional probes activate when their "
                "arguments are provided. Includes: ① pre-registration + chain check, "
                "② fair baseline, ③ gaming, ④a leakage, ⑤ multi-seed, ⑥ scope, "
                "⑦ too-good, ⑧ power (min_detectable_effect), ⑨ multiple comparisons "
                "(check_multiplicity)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ledger_path":            {"type": "string"},
                    "claim_id":               {"type": "string"},
                    "reported_metric":        {"type": "string"},
                    "reported_acc":           {"type": "number"},
                    "n":                      {"type": "integer"},
                    "baseline":               {"type": "number"},
                    "competing_name":         {"type": "string",  "description": "② Competing baseline name"},
                    "competing_acc":          {"type": "number",  "description": "② Competing baseline accuracy"},
                    "reward_terms":           {"type": "array",   "items": {"type": "string"},
                                               "description": "③ Training reward/loss term names"},
                    "train_items":            {"type": "array",   "items": {},
                                               "description": "④ Train items for leakage check"},
                    "test_items":             {"type": "array",   "items": {},
                                               "description": "④ Test items for leakage check"},
                    "seed_results":           {"type": "array",   "items": {"type": "number"},
                                               "description": "⑤ Per-seed result values"},
                    "claimed_scope":          {"type": "array",   "items": {"type": "string"},
                                               "description": "⑥ Claimed generalization scope"},
                    "tested_scope":           {"type": "array",   "items": {"type": "string"},
                                               "description": "⑥ Actually tested scope"},
                    "min_detectable_effect":  {"type": "number",
                                               "description": "⑧ Activate power check (minimum Δ to detect)"},
                    "check_multiplicity":     {"type": "boolean", "default": False,
                                               "description": "⑨ Activate multiple-comparisons Bonferroni check"},
                    "check_chain":            {"type": "boolean", "default": True,
                                               "description": "① Include chain integrity check"},
                },
                "required": ["ledger_path", "claim_id", "reported_metric", "reported_acc", "n"],
            },
        ),
        types.Tool(
            name="mm_baseline_fairness",
            description="② Detect crippled / tied / reversed baseline comparison.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name":          {"type": "string"},
                    "claimed":       {"type": "number"},
                    "baseline":      {"type": "number"},
                    "higher_better": {"type": "boolean", "default": True},
                    "margin":        {"type": "number",  "default": 0.01},
                    "n":             {"type": "integer", "description":
                                      "Sample size (optional). When given for an "
                                      "accuracy-style metric, also require the 95% "
                                      "Wilson CI to exclude the baseline — a Δ above "
                                      "the fixed margin can still be noise at small n."},
                },
                "required": ["name", "claimed", "baseline"],
            },
        ),
        types.Tool(
            name="mm_gaming_check",
            description="③ Detect eval metric appearing directly in reward/loss (self-fulfilling).",
            inputSchema={
                "type": "object",
                "properties": {
                    "metric":       {"type": "string"},
                    "reward_terms": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["metric", "reward_terms"],
            },
        ),
        types.Tool(
            name="mm_multiseed_check",
            description="⑤ Cross-seed variance alarm — unstable signal / lucky seed detection.",
            inputSchema={
                "type": "object",
                "properties": {
                    "seed_results": {"type": "array", "items": {"type": "number"}},
                    "baseline":     {"type": "number", "default": 0.5},
                    "cv_threshold": {"type": "number", "default": 0.10},
                },
                "required": ["seed_results"],
            },
        ),
        types.Tool(
            name="mm_scope_check",
            description="⑥ Detect claimed scope wider than tested evidence (over-generalization).",
            inputSchema={
                "type": "object",
                "properties": {
                    "claimed_scope": {"type": "array", "items": {"type": "string"}},
                    "tested_scope":  {"type": "array", "items": {"type": "string"}},
                },
                "required": ["claimed_scope", "tested_scope"],
            },
        ),
        types.Tool(
            name="mm_anchor_basis_check",
            description="㉑ PC anchor must rest on measured dynamics, not a static 'structurally guaranteed' argument (grounding: M11b).",
            inputSchema={
                "type": "object",
                "properties": {
                    "anchor_basis": {"type": "string",
                                     "description": "'dynamics-measured' or 'structural-argument'"},
                },
                "required": ["anchor_basis"],
            },
        ),
        types.Tool(
            name="mm_threshold_provenance_check",
            description="㉒ Pass/kill threshold must be externally fixed, not re-derived from the observed distribution (grounding: M9b/M10b).",
            inputSchema={
                "type": "object",
                "properties": {
                    "threshold_source": {"type": "string",
                                         "description": "'external-fixed' or 'observed-distribution'"},
                },
                "required": ["threshold_source"],
            },
        ),
        types.Tool(
            name="mm_content_delta_check",
            description="㉓ Judgment on agreement/match alone is rubber-stampable by near-identity claims — needs a content-delta check (grounding: M5).",
            inputSchema={
                "type": "object",
                "properties": {
                    "judgment_basis": {"type": "array", "items": {"type": "string"},
                                       "description": "judgment bases, e.g. ['match'] or ['match','incompressibility']"},
                },
                "required": ["judgment_basis"],
            },
        ),
        types.Tool(
            name="mm_anchor_line_source_check",
            description="㉔ PC anchor LINE must be aligned with this cell's sealed separatrix, not copied from a stronger/other cell (grounding: M7b anchor-line-copy).",
            inputSchema={
                "type": "object",
                "properties": {
                    "anchor_line_source": {"type": "string",
                                           "description": "'separator-aligned' or 'copied-from-other-cell'"},
                },
                "required": ["anchor_line_source"],
            },
        ),
        types.Tool(
            name="mm_anchor_cell_check",
            description="㉕ PC anchor CELL must sit in a deep regime, away from the threshold — a threshold cell straddles the boundary seed-to-seed (grounding: M8 threshold-cell).",
            inputSchema={
                "type": "object",
                "properties": {
                    "anchor_cell": {"type": "string",
                                    "description": "'deep-regime' or 'threshold-cell'"},
                },
                "required": ["anchor_cell"],
            },
        ),
        types.Tool(
            name="mm_leakage_check",
            description="④a Detect train∩test contamination: exact hash + normalized + token-Jaccard near-dup.",
            inputSchema={
                "type": "object",
                "properties": {
                    "train_items": {"type": "array", "items": {}, "description": "Train set items"},
                    "test_items":  {"type": "array", "items": {}, "description": "Test set items"},
                    "fuzzy":       {"type": "boolean", "default": True, "description":
                                    "Also catch normalized (case/whitespace/punct -> FAIL) and "
                                    "token-Jaccard near-duplicates (-> WARN). False = exact-only."},
                    "jaccard_threshold": {"type": "number", "default": 0.7,
                                          "description": "Token-Jaccard WARN threshold for near-dups."},
                },
                "required": ["train_items", "test_items"],
            },
        ),
        types.Tool(
            name="mm_too_good_check",
            description="⑦ Flag suspiciously large improvement before believing it.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name":              {"type": "string"},
                    "claimed":           {"type": "number"},
                    "baseline":          {"type": "number"},
                    "suspicious_margin": {"type": "number", "default": 0.30},
                },
                "required": ["name", "claimed", "baseline"],
            },
        ),
        types.Tool(
            name="mm_power_check",
            description=(
                "⑧ False-negative guard. Warn when n is too small to detect the "
                "minimum detectable effect at the target power level. "
                "Closes the gap between 'bidirectional' design and implementation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "n":                     {"type": "integer", "description": "Sample size"},
                    "baseline":              {"type": "number",  "description": "Baseline performance"},
                    "min_detectable_effect": {"type": "number",  "default": 0.05,
                                              "description": "Minimum Δ above baseline to detect"},
                    "alpha":                 {"type": "number",  "default": 0.05},
                    "target_power":          {"type": "number",  "default": 0.80},
                },
                "required": ["n", "baseline"],
            },
        ),
        types.Tool(
            name="mm_multiple_comparisons_check",
            description=(
                "⑨ Garden-of-forking-paths detector. Counts distinct experiments in "
                "the ledger and warns with the Bonferroni-corrected α when k>1. "
                "Running k experiments and reporting only the best inflates false-positive rate."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ledger_path": {"type": "string"},
                    "alpha":       {"type": "number", "default": 0.05},
                },
                "required": ["ledger_path"],
            },
        ),
        types.Tool(
            name="mm_anchor",
            description=(
                "📎 Compute a tamper-evident snapshot of the ledger's current state. "
                "Returns entry_count, head_seal, and anchor_hash (SHA-256 of the full "
                "ledger file). Pipe/save this externally to detect complete ledger "
                "replacement — the one attack that chain hashes alone cannot catch. "
                "chain_ok confirms the internal chain is also intact."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ledger_path": {"type": "string", "description": "Path to the JSONL ledger"},
                },
                "required": ["ledger_path"],
            },
        ),
        types.Tool(
            name="mm_calibrate",
            description=(
                "⚙ Self-test: run 5 synthetic known-good/known-bad cases through the "
                "mirror's key probes and verify they produce expected outcomes. "
                "Returns OK when the tool is working correctly, FAIL if any probe is "
                "broken. Run before witness() or in CI to confirm tool health."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="mm_witness",
            description=(
                "🎬 Execute a command and seal a tamper-evident witness record in the "
                "ledger. Captures stdout/stderr/returncode, hashes the output, and "
                "appends a chain-linked entry. Proves: which command ran, when, and "
                "exactly what it produced."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ledger_path": {"type": "string", "description": "Ledger JSONL path"},
                    "claim_id":    {"type": "string", "description": "Experiment identifier"},
                    "command":     {"type": "array", "items": {"type": "string"},
                                   "description": "Command + args as a list, e.g. [\"python\", \"eval.py\"]"},
                    "timeout":     {"type": "integer", "description": "Subprocess timeout in seconds",
                                   "default": None},
                },
                "required": ["ledger_path", "claim_id", "command"],
            },
        ),
        types.Tool(
            name="mm_grim_check",
            description=(
                "⑩ GRIM (Granularity-Related Inconsistency of Means) test. "
                "Checks that reported_acc × n is consistent with a whole-number count. "
                "If no integer k satisfies round(k/n, d) == reported_acc, the value "
                "is arithmetically impossible and was likely fabricated or mis-reported. "
                "Works for any proportion (accuracy, F1, recall, etc.) reported to d decimals."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "reported_acc": {"type": "number",
                                    "description": "Reported proportion (0–1), e.g. 0.71"},
                    "n":            {"type": "integer",
                                    "description": "Sample size"},
                    "n_decimals":   {"type": "integer",
                                    "description": "Decimal places to check (auto-inferred if omitted)",
                                    "default": None},
                },
                "required": ["reported_acc", "n"],
            },
        ),
        types.Tool(
            name="mm_judge_consistency_check",
            description=(
                "⑭ Detect an unreliable LLM judge by measuring verdict flip-rate. "
                "An LLM judge is run twice on the same items; a high fraction of items "
                "receiving different scores on re-run indicates the judge is stochastic "
                "and cannot be trusted to produce reproducible rankings. "
                "score_pairs: list of [score_run1, score_run2] pairs per item."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "score_pairs":    {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "number"}},
                        "description": "[[score_run1, score_run2], ...] — same item judged twice",
                    },
                    "flip_threshold": {"type": "number", "default": 0.20,
                                       "description": "Maximum acceptable flip fraction"},
                },
                "required": ["score_pairs"],
            },
        ),
        types.Tool(
            name="mm_judge_bias_check",
            description=(
                "⑮ Detect position bias in a pairwise LLM judge. "
                "A biased judge systematically favors whichever response appears first "
                "(or second) regardless of content. "
                "pairwise_results: list of 0 (A won) or 1 (B won) per comparison."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pairwise_results": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "[0, 1, 0, ...] — 0=A won, 1=B won per comparison",
                    },
                    "bias_threshold": {"type": "number", "default": 0.60,
                                       "description": "Win-rate above which position bias is flagged"},
                },
                "required": ["pairwise_results"],
            },
        ),
        types.Tool(
            name="mm_inter_rater_agreement",
            description=(
                "⑯ Compute Cohen's κ to check multi-judge reliability. "
                "When two judges evaluate the same items, their ratings should agree "
                "beyond chance. Low κ means judge results are effectively random relative "
                "to each other. ratings_matrix: [[judge1_score, judge2_score], ...] per item."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ratings_matrix": {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "number"}},
                        "description": "[[judge1_score, judge2_score], ...] — one row per item",
                    },
                    "min_kappa": {"type": "number", "default": 0.40,
                                  "description": "Minimum acceptable Cohen's κ"},
                },
                "required": ["ratings_matrix"],
            },
        ),
        types.Tool(
            name="mm_judge_score_sanity",
            description=(
                "⑰ Detect a degenerate judge that assigns the same score to everything. "
                "A judge that never varies its output provides no discrimination signal — "
                "ranking derived from such scores is meaningless even if aggregate numbers "
                "look reasonable. Checks unique-value ratio and dominant-value concentration."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "scores": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "All scores from a single judge model run",
                    },
                    "min_unique_ratio": {"type": "number", "default": 0.10,
                                         "description": "Minimum ratio of unique scores to total"},
                },
                "required": ["scores"],
            },
        ),
        types.Tool(
            name="mm_judge_swap_check",
            description=(
                "⑱ Position-swap cross-validation for a pairwise LLM judge. Each pair is "
                "judged as (A,B) and again with positions swapped (B,A). A content-driven "
                "judge inverts its verdict (same response wins from either slot); a "
                "position-locked judge keeps choosing the same slot. lock_rate ≈0 = "
                "content-driven (OK), ≈0.5 = noise (WARN), ≈1 = position-locked (FAIL). "
                "Catches bias that aggregate win-rate (⑮) misses when content quality "
                "is unbalanced."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "forward_results": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "[0, 1, ...] — winner per item in original (A, B) order",
                    },
                    "swapped_results": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "[0, 1, ...] — winner per item in swapped (B, A) order",
                    },
                    "position_lock_threshold": {"type": "number", "default": 0.65,
                                                "description": "lock_rate above this → FAIL"},
                    "noise_threshold": {"type": "number", "default": 0.35,
                                        "description": "lock_rate above this → WARN"},
                },
                "required": ["forward_results", "swapped_results"],
            },
        ),
        types.Tool(
            name="mm_certificate",
            description=(
                "📜 Issue a sealed verification certificate for a claim. Collapses "
                "pre-registration seal, ledger chain integrity, anchor_hash, retraction "
                "status, and (optionally) audit findings into a single SHA-256-sealed "
                "verdict: CERTIFIED / CERTIFIED-WITH-WARNINGS / UNVERIFIED / REJECTED. "
                "Pass reported_acc + n to run a full audit and fold the findings in. "
                "The anchor_hash pins the exact ledger state the certificate attests to."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ledger_path":  {"type": "string", "description": "Ledger JSONL path"},
                    "claim_id":     {"type": "string", "description": "Claim to certify"},
                    "reported_acc": {"type": "number",
                                     "description": "Optional: runs audit() and folds findings in"},
                    "n":            {"type": "integer",
                                     "description": "Sample size (required with reported_acc)"},
                    "reported_metric": {"type": "string", "default": "acc"},
                    "baseline":     {"type": "number", "default": 0.5},
                },
                "required": ["ledger_path", "claim_id"],
            },
        ),
        types.Tool(
            name="mm_judge_transitivity_check",
            description=(
                "⑲ Detect preference cycles (A>B>C>A) in a pairwise judge tournament. "
                "Aggregates matches per pair by majority vote and checks the preference "
                "graph for cycles. A cycle means the judge is not applying a consistent "
                "quality scale — any leaderboard built from its verdicts is an artifact "
                "of match ordering, not model quality."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "matches": {
                        "type": "array",
                        "items": {"type": "array"},
                        "description": "[[model_a, model_b, winner], ...] — winner is "
                                       "0 (model_a won) or 1 (model_b won)",
                    },
                },
                "required": ["matches"],
            },
        ),
        types.Tool(
            name="mm_ranking_stability_check",
            description=(
                "⑳ Check that a ranking claim ('model A beats model B') survives "
                "bootstrap resampling of the per-item scores. With few items or high "
                "variance, redrawing the sample flips the winner — the ranking is a "
                "mirage. Deterministic (seeded RNG). FAIL below 80% stability, WARN "
                "below min_stability (default 95%)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "scores_a": {"type": "array", "items": {"type": "number"},
                                 "description": "Per-item scores for model A"},
                    "scores_b": {"type": "array", "items": {"type": "number"},
                                 "description": "Per-item scores for model B (paired by index)"},
                    "n_boot":   {"type": "integer", "default": 1000},
                    "seed":     {"type": "integer", "default": 0},
                    "min_stability": {"type": "number", "default": 0.95},
                },
                "required": ["scores_a", "scores_b"],
            },
        ),
        types.Tool(
            name="mm_verify",
            description=(
                "🪞 Single entry point — runs every probe whose inputs are present in "
                "`data` (FULL verification), optionally restricted to groups (GROUP "
                "verification). Groups: ledger (prereg/chain/cascade), stats (CI, "
                "multi-seed, too-good, power, multiplicity, GRIM), design (baseline, "
                "gaming, leakage, scope, falsifiability), negative (closure gate), "
                "judge (⑭⑮⑯⑰⑱), ranking (⑲⑳). data keys: claim_id, metric, acc, n, "
                "baseline, competing_name+competing_acc, reward_terms, "
                "train_items+test_items, seed_results, claimed_scope+tested_scope, "
                "min_detectable_effect, check_multiplicity, angles, score_pairs, "
                "pairwise_results, ratings_matrix, scores, "
                "forward_results+swapped_results, matches, scores_a+scores_b."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ledger_path": {"type": "string", "description": "Ledger JSONL path"},
                    "data":        {"type": "object",
                                    "description": "Probe inputs — only probes whose keys "
                                                   "are present will run"},
                    "groups":      {"type": "array",
                                    "items": {"type": "string",
                                              "enum": ["ledger", "stats", "design",
                                                       "negative", "judge", "ranking"]},
                                    "description": "Optional: restrict to these groups"},
                },
                "required": ["ledger_path", "data"],
            },
        ),
        types.Tool(
            name="mm_badge",
            description=(
                "🏷 Render a claim's certificate as an embeddable badge. fmt='markdown' "
                "returns shields.io image markdown for README embedding; fmt='svg' "
                "returns a self-contained offline SVG with the certificate seal in its "
                "tooltip. Badge color reflects the verdict: CERTIFIED=green, "
                "WITH-WARNINGS=yellow, UNVERIFIED=grey, REJECTED=red."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ledger_path": {"type": "string", "description": "Ledger JSONL path"},
                    "claim_id":    {"type": "string", "description": "Claim to badge"},
                    "fmt":         {"type": "string", "enum": ["markdown", "svg"],
                                    "default": "markdown"},
                },
                "required": ["ledger_path", "claim_id"],
            },
        ),
    ]


# ─────────────────────────────────────────────────────────────
# Tool execution
# ─────────────────────────────────────────────────────────────
def _findings_to_text(findings: list[mm.Finding]) -> str:
    icon = {"OK": "✅", "WARN": "⚠️", "FAIL": "🔴", "INFO": "ℹ️", "N/A": "➖"}
    worst = "FAIL" if any(f.level == "FAIL" for f in findings) else \
            "WARN" if any(f.level == "WARN" for f in findings) else "OK"
    lines = [f"Overall: {icon[worst]} {worst}"]
    for f in findings:
        lines.append(f"{icon.get(f.level, 'ℹ️')} [{f.probe}] {f.msg}")
    return "\n".join(lines)


def _single(f: mm.Finding) -> str:
    icon = {"OK": "✅", "WARN": "⚠️", "FAIL": "🔴", "INFO": "ℹ️", "N/A": "➖"}
    return f"{icon.get(f.level, 'ℹ️')} [{f.probe}] {f.msg}"


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        if name == "mm_register":
            entry = mm.preregister(
                arguments["ledger_path"],
                arguments["claim_id"],
                metric=arguments["metric"],
                min_n=arguments.get("min_n", 200),
                baseline=arguments.get("baseline", 0.5),
                pass_threshold=arguments.get("pass_threshold", 0.60),
                kill_condition=arguments.get("kill_condition"),
                kill_threshold=arguments.get("kill_threshold"),
                depends_on=arguments.get("depends_on"),
                anchor_basis=arguments.get("anchor_basis"),
                threshold_source=arguments.get("threshold_source"),
                anchor_cell=arguments.get("anchor_cell"),
                anchor_line_source=arguments.get("anchor_line_source"),
                known_confounds=arguments.get("known_confounds"),
                pre_seal_checks=arguments.get("pre_seal_checks"),
            )
            kill_line = ""
            if entry.get("kill_threshold"):
                kt = entry["kill_threshold"]
                kill_line = (f"\nkill_threshold: {kt.get('metric','?')} "
                             f"{kt.get('direction','below')} {kt['threshold']}")
            elif entry.get("kill_condition"):
                kill_line = f"\nkill_condition: {entry['kill_condition']}"
            # Automatic seal-quality lint (㉗) — a FAIL here means the seal is
            # malformed or its bar is meaningless; fix and re-seal under a NEW
            # claim_id (first-write-wins makes this one uncorrectable).
            lint_notes = [f for f in mm._preseal_lint(entry) if f.level != "OK"]
            lint_block = ""
            if lint_notes:
                lint_block = "\n" + "\n".join(
                    f"{'🔴' if f.level == 'FAIL' else '⚠️' if f.level == 'WARN' else 'ℹ️'} "
                    f"[{f.probe}] {f.msg}" for f in lint_notes)
            result = (
                f"🔒 Sealed\n"
                f"claim_id: {entry['claim_id']}\n"
                f"metric: {entry['metric']}\n"
                f"min_n: {entry['min_n']}\n"
                f"baseline: {entry['baseline']}\n"
                f"pass_threshold: {entry['pass_threshold']}"
                f"{kill_line}\n"
                f"prev_seal: {entry['prev_seal']}\n"
                f"seal: {entry['seal']}"
                f"{lint_block}"
            )

        elif name == "mm_cascade_check":
            result = _single(mm.cascade_check(
                arguments["ledger_path"],
                arguments["claim_id"],
            ))

        elif name == "mm_subspace_claim_check":
            result = _findings_to_text(mm.subspace_claim_check(
                arguments["report"],
                energy_tol=arguments.get("energy_tol", 0.05),
                alpha=arguments.get("alpha", 0.05),
                dim_tol=arguments.get("dim_tol", 0.15),
            ))

        elif name == "mm_negative_audit":
            result = _single(mm.negative_audit(
                arguments["ledger_path"],
                angles=arguments["angles"],
                min_angles=arguments.get("min_angles", 3),
                conclusion_scope=arguments.get("conclusion_scope"),
                tested_scope=arguments.get("tested_scope"),
            ))

        elif name == "mm_retract":
            e = mm.retract(
                arguments["ledger_path"],
                arguments["claim_id"],
                arguments["reason"],
            )
            result = (
                f"🚫 Retracted: {e['claim_id']}\n"
                f"   Reason:     {e['reason']}\n"
                f"   Prev seal:  {e['prev_seal']}\n"
                f"   Seal:       {e['seal']}"
            )

        elif name == "mm_falsifiability_check":
            result = _single(mm.falsifiability_check(
                arguments["ledger_path"],
                arguments["claim_id"],
                reported_acc=arguments.get("reported_acc"),
            ))

        elif name == "mm_prereg_lint":
            findings = mm.prereg_lint(
                arguments["ledger_path"],
                arguments.get("claim_id"),
            )
            result = _findings_to_text(findings)

        elif name == "mm_verify_chain":
            findings = mm.verify_chain(arguments["ledger_path"])
            result = _findings_to_text(findings)

        elif name == "mm_audit":
            findings = mm.audit(
                arguments["ledger_path"],
                arguments["claim_id"],
                reported_metric=arguments["reported_metric"],
                reported_acc=arguments["reported_acc"],
                n=arguments["n"],
                baseline=arguments.get("baseline"),
            )
            result = _findings_to_text(findings)

        elif name == "mm_continuous_audit":
            findings = mm.continuous_audit(
                arguments["ledger_path"],
                arguments["claim_id"],
                reported_metric=arguments["reported_metric"],
                reported_value=arguments["reported_value"],
                baseline_value=arguments["baseline_value"],
                n=arguments["n"],
                std=arguments.get("std"),
                higher_better=arguments.get("higher_better", True),
            )
            result = _findings_to_text(findings)

        elif name == "mm_full_audit":
            findings = mm.full_audit(
                arguments["ledger_path"],
                arguments["claim_id"],
                reported_metric=arguments["reported_metric"],
                reported_acc=arguments["reported_acc"],
                n=arguments["n"],
                baseline=arguments.get("baseline"),
                competing_name=arguments.get("competing_name"),
                competing_acc=arguments.get("competing_acc"),
                reward_terms=arguments.get("reward_terms"),
                train_items=arguments.get("train_items"),
                test_items=arguments.get("test_items"),
                seed_results=arguments.get("seed_results"),
                claimed_scope=arguments.get("claimed_scope"),
                tested_scope=arguments.get("tested_scope"),
                min_detectable_effect=arguments.get("min_detectable_effect"),
                check_chain=arguments.get("check_chain", True),
                check_multiplicity=arguments.get("check_multiplicity", False),
            )
            result = _findings_to_text(findings)

        elif name == "mm_baseline_fairness":
            result = _single(mm.baseline_fairness(
                arguments["name"],
                arguments["claimed"],
                arguments["baseline"],
                higher_better=arguments.get("higher_better", True),
                margin=arguments.get("margin", 0.01),
                n=arguments.get("n"),
            ))

        elif name == "mm_gaming_check":
            result = _single(mm.gaming_check(
                arguments["metric"],
                arguments["reward_terms"],
            ))

        elif name == "mm_multiseed_check":
            result = _single(mm.multiseed_check(
                arguments["seed_results"],
                baseline=arguments.get("baseline", 0.5),
                cv_threshold=arguments.get("cv_threshold", 0.10),
            ))

        elif name == "mm_leakage_check":
            result = _single(mm.leakage_check(
                arguments["train_items"],
                arguments["test_items"],
                fuzzy=arguments.get("fuzzy", True),
                jaccard_threshold=arguments.get("jaccard_threshold", 0.7),
            ))

        elif name == "mm_scope_check":
            result = _single(mm.scope_check(
                arguments["claimed_scope"],
                arguments["tested_scope"],
            ))

        elif name == "mm_anchor_basis_check":
            result = _single(mm.anchor_basis_check(arguments["anchor_basis"]))

        elif name == "mm_threshold_provenance_check":
            result = _single(mm.threshold_provenance_check(arguments["threshold_source"]))

        elif name == "mm_content_delta_check":
            result = _single(mm.content_delta_check(arguments["judgment_basis"]))

        elif name == "mm_anchor_line_source_check":
            result = _single(mm.anchor_line_source_check(arguments["anchor_line_source"]))

        elif name == "mm_anchor_cell_check":
            result = _single(mm.anchor_cell_check(arguments["anchor_cell"]))

        elif name == "mm_too_good_check":
            result = _single(mm.too_good_check(
                arguments["name"],
                arguments["claimed"],
                arguments["baseline"],
                suspicious_margin=arguments.get("suspicious_margin", 0.30),
            ))

        elif name == "mm_power_check":
            result = _single(mm.power_check(
                arguments["n"],
                arguments["baseline"],
                min_detectable_effect=arguments.get("min_detectable_effect", 0.05),
                alpha=arguments.get("alpha", 0.05),
                target_power=arguments.get("target_power", 0.80),
            ))

        elif name == "mm_multiple_comparisons_check":
            result = _single(mm.multiple_comparisons_check(
                arguments["ledger_path"],
                alpha=arguments.get("alpha", 0.05),
            ))

        elif name == "mm_anchor":
            a = mm.anchor(arguments["ledger_path"])
            result = json.dumps(a, indent=2, ensure_ascii=False)

        elif name == "mm_calibrate":
            result = _findings_to_text(mm.calibrate())

        elif name == "mm_witness":
            w = mm.witness(
                arguments["ledger_path"],
                arguments["claim_id"],
                arguments["command"],
                timeout=arguments.get("timeout"),
            )
            result = (
                f"🎬 Witnessed: {w['claim_id']}\n"
                f"   Command:     {' '.join(w['command'])}\n"
                f"   Started:     {w['ts_start']}\n"
                f"   Ended:       {w['ts_end']}\n"
                f"   Exit code:   {w['returncode']}  ({w['run_status']})\n"
                f"   Output hash: {w['output_hash']}\n"
                f"   Prev seal:   {w['prev_seal']}\n"
                f"   Seal:        {w['seal']}"
            )

        elif name == "mm_grim_check":
            result = _single(mm.grim_check(
                arguments["reported_acc"],
                arguments["n"],
                n_decimals=arguments.get("n_decimals"),
            ))

        elif name == "mm_judge_consistency_check":
            result = _single(mm.judge_consistency_check(
                [tuple(p) for p in arguments["score_pairs"]],
                flip_threshold=arguments.get("flip_threshold", 0.20),
            ))

        elif name == "mm_judge_bias_check":
            result = _single(mm.judge_bias_check(
                arguments["pairwise_results"],
                bias_threshold=arguments.get("bias_threshold", 0.60),
            ))

        elif name == "mm_inter_rater_agreement":
            result = _single(mm.inter_rater_agreement(
                [tuple(r) for r in arguments["ratings_matrix"]],
                min_kappa=arguments.get("min_kappa", 0.40),
            ))

        elif name == "mm_judge_score_sanity":
            result = _single(mm.judge_score_sanity(
                arguments["scores"],
                min_unique_ratio=arguments.get("min_unique_ratio", 0.10),
            ))

        elif name == "mm_judge_swap_check":
            result = _single(mm.judge_swap_check(
                arguments["forward_results"],
                arguments["swapped_results"],
                position_lock_threshold=arguments.get("position_lock_threshold", 0.65),
                noise_threshold=arguments.get("noise_threshold", 0.35),
            ))

        elif name == "mm_certificate":
            fnds = None
            if arguments.get("reported_acc") is not None and arguments.get("n") is not None:
                fnds = mm.audit(
                    arguments["ledger_path"],
                    arguments["claim_id"],
                    reported_metric=arguments.get("reported_metric", "acc"),
                    reported_acc=arguments["reported_acc"],
                    n=arguments["n"],
                    baseline=arguments.get("baseline", 0.5),
                )
            c = mm.certificate(
                arguments["ledger_path"],
                arguments["claim_id"],
                findings=fnds,
            )
            result = json.dumps(c, indent=2, ensure_ascii=False)

        elif name == "mm_judge_transitivity_check":
            result = _single(mm.judge_transitivity_check(
                [tuple(m) for m in arguments["matches"]],
            ))

        elif name == "mm_ranking_stability_check":
            result = _single(mm.ranking_stability_check(
                arguments["scores_a"],
                arguments["scores_b"],
                n_boot=arguments.get("n_boot", 1000),
                seed=arguments.get("seed", 0),
                min_stability=arguments.get("min_stability", 0.95),
            ))

        elif name == "mm_verify":
            findings = mm.verify(
                arguments["ledger_path"],
                arguments["data"],
                groups=arguments.get("groups"),
            )
            result = (_findings_to_text(findings) if findings
                      else "No probes activated — data contains no recognized keys.")

        elif name == "mm_badge":
            c = mm.certificate(
                arguments["ledger_path"],
                arguments["claim_id"],
            )
            result = mm.badge(c, fmt=arguments.get("fmt", "markdown"))

        else:
            result = f"Unknown tool: {name}"

    except Exception as e:
        result = f"❌ Error: {e}"

    return [types.TextContent(type="text", text=result)]


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
async def _main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main():
    asyncio.run(_main())


if __name__ == "__main__":
    main()
