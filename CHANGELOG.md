# Changelog

All notable changes to Measurement Mirror are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.35.0] — 2026-08-14

### Added
- **⑫g pre-seal lint: a threshold that does not say what it is a threshold *of*.**
  `preregister` already rejects a `kill_threshold` whose `threshold` is not numeric
  and whose `direction` is not `below|above` — but accepts one carrying no `metric`
  at all, and the lint said nothing. Auto-evaluation then has no key to look for in
  the sealed result, so `falsifiability_check` can never grade the claim by itself:
  the bar is sealed, the quantity it bars is not. This is the mirror image of ⑫b
  ("you wrote a number you could structure") and just as blinding.

  Measured on one real ledger before writing this: of 133 resolved-negative claims,
  **61 are sealed with a metric-less threshold**, and only **1** could be graded
  mechanically end-to-end. The library's own test-suite contained a metric-less
  threshold as scaffolding, which is a fair sign this is easy to omit rather than a
  user error. WARN, not FAIL — every seal already written stays valid, the gap just
  becomes countable.

### Changed
- `tests/test_preseal_lint.py`: one round-trip test used a metric-less
  `kill_threshold` as scaffolding and asserted a clean lint. Its subject is
  `pre_seal_checks` persistence, so the threshold now names its metric; the
  assertion is unchanged.

---

## [0.34.0] — 2026-08-12

### Added
- **`recover_resolution` is public.** Finding a claim's sealed resolution was
  already implemented — `falsifiability_check` has used it since the
  auto-resolution work — but only as a private `_recover_resolution`, so an
  auditor outside this package could not reuse it. The one that tried
  reimplemented the search by hand and recovered *fewer* resolutions than the
  function it did not know existed. A capability the product already has, that
  callers must rebuild to use, is a packaging defect rather than a missing
  feature. `_recover_resolution` remains as an alias for pre-0.34 callers.

### Changed
- **Resolution recovery reads the shapes ledgers actually use.** Previously a
  verdict was recovered from `payload.verdict` or from an action matching
  `VERDICT … = X`. Ledgers also record the same fact under the Korean payload
  keys `판정`/`결과`, and in prose (`verdict <claim>: KILL(…)`, `<claim> 결과=PASS(…)`,
  `M7c 판정: 🔴…`). Those now resolve too. Measured on a 583-claim ledger set,
  unresolved claims fell 148 → 124.
  - Patterns are tried in order and **first match wins**, so a sentence naming a
    headline verdict and a secondary one — `KILL(delta below bar) · monotone PASS`
    — resolves to the headline. A test pins that contract.
  - Recovery stays conservative by design: an unidentifiable verdict still
    yields `(None, None)` and the caller keeps its WARN path. An unrecovered
    resolution is a human's problem; a *misrecovered* one is a wrong answer.
- **`ledger_path` / `am_ledger` accept a sequence of paths.** A project's claims
  routinely span many ledger files (63 in the case that motivated this), and the
  single-path signature forced callers to concatenate them into a temp file on
  every run. Passing a list now works; a single path behaves exactly as before.

---

## [0.33.0] — 2026-08-10

### Added
- **㉘ mutant↔clause correspondence map — the aggregate detection score,
  decomposed** (`eval/subspace_mutant_map/`). Seal `5c78e503` proved an
  aggregate score cannot tell mechanism from substrate luck because it does
  not decompose into "planted defect ↔ the clause that caught it" rows; the
  mutation-testing frame (arXiv 2607.08028) treats that correspondence as the
  basic unit of verifier coverage. `build_map.py` runs the unmodified auditor
  on every planted layer-A negative AND its recovered honest parent (the
  clean report for deepcopy-mutants; the lying `grid.kind` declaration undone
  for the confound cases), diffs the finding profiles, and types each row:
  ATTRIBUTED / DOMINATED / CONSTANT_SUSPECT / EQUIVALENT_SUSPECT / UNSAT.
  Equivalent-mutant screening is thereby a procedure, not a judgment call —
  a planted fault whose whole profile equals its parent's is a planting
  failure, not an auditor pass. Sealed on the held-out homes
  (`subspace_mutant_clause_map_holdout_20260810`, seal `e7969656`, result
  `ddf46281`): TYPE_MATCH 12/12 = 1.0 against frozen per-recipe expectations,
  controls 4/4. The sealed finding: `energy_confound` is **DOMINATED**, not
  attributed — an honestly declared k grid already FAILs
  `energy-not-matched` by design, so the lie cannot improve the verdict and
  its "catch" validates nothing about the lie; and the vacuous real runs
  re-read as organic mutants show 43 of 100 planted sloppy runs were
  equivalent mutants (all 25 at n_fit=200), exposed by ground-truth
  relabelling rather than trusted intent.

---

## [0.32.0] — 2026-08-10

### Added
- **㉘ `vacuous` — both directions exercised on real runs for the first time.**
  Until now the finding had only ever fired on synthetic tables: the FM×CDE
  corpus carries zero real VACUOUS labels, and the planted FN case hand-writes
  a certificate failure into a real report (recorded openly in
  `eval/subspace_planted/RESULTS.md`). Now layer B **computes** the
  certificate: `build_subspace_report(certificate_tol=…)` certifies every
  `matched_null` arm against the energy it retained **on the eval split** —
  the data the effect is scored on — so an arm that hits its target in-sample
  while genuinely undershooting it where the effect was measured fails its
  certificate organically, with no field edited. Cells now also carry
  `energy_kept_on_eval_split`, so the certificate is recomputable from the
  table it ships with. Without `certificate_tol` the report carries no
  certificate and layer A keeps saying WARN — absence stays visible.
  - Sealed: claim `subspace_vacuous_real_runs_balanced_20260810_v2`
    (`2a22a95a`, result am `79cd0816`), **BALANCED_CASE 1.0** against a
    pre-committed bar of 1.0 (chance 0.5) — unmatched 48/48 · matched 143/143,
    9 boundary runs withheld, ground-truth labelling with an equivalent-mutant
    filter (a "sloppy" run the manipulation failed to bite is scored as the
    matched arm it actually is).
  - The first sealed attempt (`17c36ad6`) went **INVALID** on its own anchor
    clause — a literal "all unmatched" tripped on one boundary-band margin
    whose behaviour was correct. Consumed as INVALID, re-sealed on a fresh
    seed block; kept in `eval/subspace_vacuous_real/RESULTS.md` and added to
    `catalog/self-catch/prereg-clause-defect-family.md` as a live case.
  - Scope stated where it is claimed: synthetic isotropic Gaussians, own-run
    certificates only — a consistent forgery still passes layer A, and the
    planted synthetic cases stay in the set guarding the adapter path.

---

## [0.31.0] — 2026-08-06

### Added
- **㉘ `dof-outperforms-target` — the guard substrate-2 proved was missing.**
  v0.30.1 recorded that ㉘ had *no* mechanism against a swapped-role claim and
  that the `relabeled_dof` case had passed on FM×CDE by substrate luck. This
  closes that, with a **coherence law rather than a heuristic**: a
  degrees-of-freedom control is the target's own procedure with the claimed
  structure destroyed, and destroying structure cannot *add* effect, so a
  truthful table satisfies `effect(dof_control) ≤ effect(target)`. A violation
  means the role labels are swapped or the arm called a control is not one.
  - FAIL is decided by the same paired sign-flip the null ladder uses (exact 2ⁿ
    for n ≤ 14); a control merely leading on the mean is WARN, not a verdict.
  - A violation **holds `null-ladder` below OK**, the same priority shape the
    anchor rule uses — otherwise a consumer reading only the ladder would see a
    green light on a report whose control beats its treatment.
  - No `dof_control` arm ⇒ no finding at all. Absence is `dof-uncontrolled`'s
    business, not this one's.
  - Sealed on the FM×CDE **holdout** (v01+v05, never used to design any
    role-swap rule): claim `582f4130`, result am `45d5f3d2`,
    **CASE_ACCURACY 22/22 = 1.0** against a pre-committed bar of 1.0
    (chance 0.6364), FP=0, FN=0, zero constant findings. Re-scoring substrate-2
    — the design set, no evidential weight — gives FN=0 there too.
  - **Scope, stated rather than implied:** it catches the swap only when the
    true target genuinely beats its control. When the two are indistinguishable
    the swap stays invisible — and so does the effect it would hide.
- `tests/test_subspace_claim.py` +6, including one that pins the **rejected**
  alternative so it cannot creep back: a rule keyed on "the target must need the
  fewest components at a given energy" is a category error (a target is a
  hypothesis about where the *effect* lives, not the *variance*), and it would
  FAIL honest reports whose treatment is not the leading principal subspace.

---

## [0.30.1] — 2026-08-06

### Changed
- **㉘'s scope clause is now backed by evidence, and the evidence is a KILL.**
  Replaying the planted recipes on a **second real substrate** — 768-d DINO crop
  embeddings from another arc, versus FM×CDE's 24-d adapter deltas (claim
  `subspace_claim_check_substrate2_generalization_20260806_v4`, seal `5c78e503`,
  result am `2ab6eab7`) — scored **CASE_ACCURACY 0.80 against a pre-committed
  bar of 1.0** (chance 0.60): FP=1, FN=1. Per the seal's pre-commitment there was
  no repair round.
  - **The load-bearing finding: ㉘ has no guard against a swapped-role claim.**
    If a report labels its degrees-of-freedom control as the target, nothing in
    the function detects it — the table alone does not say which arm was the
    treatment. The `relabeled_dof` case passed on FM×CDE only because the
    shuffled arm did not beat the null *there*. That pass looked like a guard
    and was substrate luck. On substrate-2 the shuffled arm beats the random
    null on all 8 splits (0.4437 vs 0.4240, chance 0.3469) and `null-ladder`
    confirms the swap. Recorded in the function's own docstring and in both
    READMEs, because a reader of the old text would over-trust the probe.
  - A substrate fact worth its own line: **a column-shuffled basis is not a null
    on real anisotropic embeddings** — shuffling destroys cross-dimension
    covariance but preserves the per-dimension marginals that carry the signal.
  - The FP is the auditor being *right*: exactly one evaluation row is
    byte-identical to a row the basis was fitted on (the substrate has 4
    duplicate pair-feature rows), so index-disjoint splits were not
    content-disjoint. That diagnosis is unsealed, is labelled as such, and was
    **not** used to rescore.
  - This does **not** falsify seal `99a1a510`, the FM×CDE holdout judgment,
    which was explicitly scoped to one experiment family.
- `eval/subspace_substrate2/` — generator, case set, the KILL score output under
  a name that says so, and `RESULTS.md`. The substrate's provenance is checked
  rather than assumed: the COCO annotation sha256 head matches the value the
  original pilot sealed, and regeneration reproduces its object, pair and
  relation counts exactly.
- 🦋 Catalog 70 → 71: `fn-guard/guard-passed-by-substrate-luck` — a guard case
  can pass because the substrate made the defect invisible rather than because
  the tool has a mechanism, and one substrate can never tell the two apart.

---

## [0.30.0] — 2026-08-05

### Added
- **㉘ layer B — `measure_mirror/subspace.py`, the executor.** Layer A audits a
  submitted table; layer B *produces* one from the arrays and hands it straight
  back to layer A, so an own run is judged by the same auditor a stranger's
  claim is. Requires numpy: `pip install "measure-mirror[subspace]"`.
  - `fit_basis` / `energy_profile` / `cumulative_energy` / `k_for_energy` —
    basis estimation with `pca` / `random` / `shuffled` (dof control) / `given`.
    A rank-deficient sample is *padded* to a complete basis, not truncated:
    with n < d, truncating at the sample's rank would silently cap every energy
    target at whatever that sample happened to span. The `random` basis is
    deliberately left unsorted, which is what preserves the `energy/k ≈ 1/d`
    relation layer A's C4 uses to recover the ambient dimension.
  - `build_subspace_report(...)` — arrays + an effect callback → a layer-A
    report. Declares `effect_fn_sha256` (sha256 of the callback's source); when
    the source cannot be read the field is `None` with a stated reason, because
    hashing a repr would look like provenance while attesting to nothing.
    `basis_fit_ids` / `effect_eval_ids` are **content-addressed** (sha256 of
    each row's float64 bytes), so `estimation-eval-overlap` tests actual reuse
    rather than declared labels.
  - `overfit_smallsample(...)` — the judgment layer A is structurally unable to
    make. Layer A can only lint `underdetermined-basis` from a declared
    `n_basis_fit`; whether such a basis really aligned with noise is a property
    of the estimation run. Synthetic isotropic Gaussians, signal 0,
    `n_basis ∈ {20, 50, 200}`: the target arm must not clear the null ladder.
    **A positive control runs at every `n`, not only the largest** — otherwise
    "the target did not win at n=20" and "the instrument is blind at n=20" are
    indistinguishable, and any `n` whose control fails is reported *withheld*,
    never counted as a pass.
- `tests/test_subspace_runner.py` (25) — includes a test that deliberately makes
  the instrument inert (`positive_signal=0.0`) and requires it to report itself
  vacuous, and a subprocess test that imports the core with numpy blocked.

### Changed
- **Dependency advertising now carries its scope.** "Zero-dep core" became
  "stdlib-only core", stated together with the two optional modules that do
  have dependencies (`judge` → openai/anthropic, `subspace` → numpy). Dropping
  that qualifier is the overgeneralisation recorded in
  `catalog/self-catch/zero-dep-scope-overgeneralize.md`, caught on this
  README once already; a test now guards the wording.
- CI installs `.[test,subspace]` — without it the layer-B tests would skip and
  layer B would ship unexercised by CI.
- 🦋 Catalog 67 → 70, all three from this arc with ledger seals:
  `fn-guard/constant-check-passes-vacuously` (98e993b2) — a check whose verdict
  is the same for every case catches every planted negative for free;
  `self-catch/coincidence-read-as-design` (3e6bd450) — "any collision proves
  design" cannot separate honest 8-of-160 collisions from a real 5-of-5 grid,
  and the fix removed the threshold rather than tuning it;
  `contamination/devset-consumed-by-repair-signal` (99a1a510) — a set you
  repaired against is development signal, and its later perfect score carries
  no evidential weight.

---

## [0.29.0] — 2026-08-04

### Added
- **㉘ `subspace_claim_check` — a declaration auditor for "the gain lives in a
  few input directions" (active-subspace-style) claims.** Layer A only: stdlib,
  no numpy, and it never sees the basis, the perturbation samples, or the model
  — only the table the claimant submitted. **A falsified `energy_kept` passes.**
  That limit is structural and applies to all seven findings; the C1–C4
  consistency laws raise the *cost* of a false table, they do not close the
  hole. Findings: `no-anchor` · `energy-not-matched` · `dof-uncontrolled` ·
  `null-ladder` · `vacuous` · `saturation` · `estimation-eval-overlap`, with a
  priority rule — a failed anchor holds `null-ladder` below OK, because without
  a reproducible anchor the ratio normalizer is undefined.
- `_paired_signflip_p` — exact 2ⁿ enumeration for n ≤ 14, fixed-seed Monte
  Carlo above. Deliberately not the normal approximation used elsewhere, which
  is anti-conservative at n=10.
- `Finding.data: dict | None` — probes attach computed numbers here instead of
  encoding them in `msg`. ⚠️ **Breaking for `astuple`/`asdict` callers**: they
  now yield 4 elements, so a comparison against a 3-tuple literal breaks. No
  in-repo caller does this.
- `eval/subspace_planted/` — two-directional planted control set built from
  real sealed experiment output, every case labelled with `layer`
  (real / half / synthetic / B) and `provenance`, plus a scorer with a
  **discriminative-power gate**: a finding that gates a planted negative must
  emit at least two distinct levels, or the run is killed.
- `tests/test_changelog_sync.py` — the version in `pyproject.toml` must have a
  CHANGELOG entry. This file was the one sync target no test covered.

### Fixed
- **Latent crash in `report()` and the MCP formatters.** Both indexed `icon` by
  finding level, but the dict held only OK/WARN/FAIL while five call sites
  already emitted `INFO` or `N/A` — any such finding reaching the printer
  raised `KeyError`. Levels added and lookups made total.
- Documented `wilson_ci`, `lookup_baseline` and `lookup_reproduction`, which
  were in `__all__` (a public API promise) with zero mentions in any doc.
- `README_KO.md` said "26개 프로브" in two places while another line said "27종
  probe"; the count guard only matched the latter phrasing, so that drift had
  gone unnoticed. `docs/GUIDE_KO.md` stated no total at all where the English
  guide does.

### Validation
Two-directional judgment, pre-registered before each run, all results sealed:
`98e993b2` 🔴 KILL (FP=2) → `3e6bd450` 🔴 KILL (FP=1) → `99a1a510` 🟢 **PASS
22/22** on homes held out from development. Neither repair was a threshold
change — the tolerance that caused the first kill was removed as a gate
entirely. Both kills are pinned as regression tests. Scope left open is
recorded in the seal, not hidden: an arm whose energy overshoot far exceeds the
others' is undetectable, `vacuous` is validated synthetically in both
directions, and a consistent forged table still passes.

---

## [0.28.1] — 2026-07-21

### Fixed
- **`power_check` now honors its `alpha` and `target_power` arguments.**
  The critical values were hardcoded (`z_alpha2 = 1.96`, `z_beta = 0.842`),
  so the message interpolated the requested power (e.g. "at 99% power") while
  the required-n was *always* computed at 80% power / α=0.05. The printed text
  and the printed number contradicted each other — a text-vs-number lie, the
  worst class of defect for an honesty-audit tool. Both z-values are now
  derived from the arguments via `statistics.NormalDist().inv_cdf` (stdlib,
  still zero-dependency). Now `target_power=0.99` → n≥1829 (was 781) and
  `alpha=0.0001` → n≥2229. Default behavior (α=0.05, power=0.80) is unchanged.
  Reported by external review.

### Added
- `test_mm.py` regression tests asserting the computed n tracks both
  `target_power` and `alpha` (not just the message text).

---

## [0.28.0] — 2026-07-17

### Security
- **verify_chain no longer waives the chain link for entries missing prev_seal.**
  SPEC §4 rule 3 mandates prev_seal and says a missing value is treated as the
  empty string so the §5 linkage comparison fails naturally — but verify_chain
  had an `if prev_seal is not None` guard that *silently skipped* the link,
  returning "Chain intact" for a ledger whose entries carry no chain at all.
  An attacker could strip prev_seal from every entry, reseal each one
  standalone, then delete/reorder freely and still get a green verdict.
  verify_chain now follows the SPEC (and matches the already-compliant
  `linkage_check` and action/provenance mirrors): a missing prev_seal fails
  the link. Seal recomputation is unchanged; legacy 16-hex seals still verify.
  Reported by external review; attack reproduced, fixed, regression-tested.

### Added
- `tests/test_chain_attacks.py` — strip-prev_seal downgrade, single/first
  missing link, tamper+reseal; `test_mm` legacy case flipped to assert the fix.

---

## [0.27.1] — 2026-07-21

### Added
- **🦋 `catalog/draft_specimen.py`** — auto-draft a catalog specimen from a **sealed
  retraction**, closing the "forgot to collect" gap without breaking the catalog's
  no-fabrication rule. It **transcribes only the provable parts** — claim_id, seal,
  retraction reason, ledger — into the specimen's 실사례 line, and leaves every
  interpretive field (증상 / 기전 / 탐지법 / 오적용) as an explicit TODO for a human to
  complete from the actual arc. It never invents a case and never writes the mechanism
  story. Suggests a category from keywords, writes `<slug>.DRAFT.md` (gitignored until a
  human completes it and promotes `.DRAFT.md → .md`). Regression suite:
  `tests/test_draft_specimen.py`.

## [0.27.0] — 2026-07-17

### Security
- **Seal width: 16-hex (64-bit) truncation → full 64-hex SHA-256 digest**
  (SPEC v1.1 §4). 64-bit truncated seals allowed a dishonest sealer to
  birthday-search (~2^32 hashes) two entries sharing one seal and swap them
  after sealing. New entries (preregister / retract / witness runs / judge
  runs / verification certificates, and `output_hash`) now carry the full
  digest. **Legacy 16-hex seals keep verifying** via prefix match — mixed
  chains are supported; no ledger migration needed. Reported by external
  review; verified and fixed the same day.

### Added
- Conformance vector `valid_05_legacy16.jsonl` (legacy-acceptance) and
  `tests/test_seal_upgrade.py` regression suite.

---

## [0.26.1] — 2026-07-21

Dogfooding fix — ㉗ `prereg_lint` false-positive classes, found by auditing it
against 64 real ledgers (373 preregistrations).

### Fixed
- **㉗ pass-bar-below-chance (⑫c) no longer uses `baseline` as the chance floor.**
  In practice `baseline` is a comparison-arm score (e.g. 0.92, or the other arm of a
  two-arm compare), not the random floor — treating `pass ≤ baseline` as "below chance"
  produced **44 false FAILs** across the audited ledgers (each a wrong compute-gate
  BLOCK). ㉗ now uses an **explicitly declared `chance`** only, and additionally skips:
  a `pass_threshold` of 0/absent (a placeholder for a claim whose real bar is the
  `kill_threshold`), and non-[0,1]/unbounded metrics (where `pass` is a delta/margin,
  not an absolute score). After the fix the audit flags **4 FAILs, all genuine**
  kill-condition-leaked-into-`metric` seals — and zero false positives.
- **㉗ quantified-text-only-kill (⑫b) now requires a number in a *comparison* context**
  (`below 0.5`, `acc < 0.55`, `0.3 미만`), so an incidental digit — a sha256, a date,
  `n=600`, a filename `v2`, a section `§6` — no longer reads as a missing threshold.

Behaviour change: a below-chance FAIL now requires `chance=` to be declared. Callers
that relied on `baseline` being read as the floor should declare `chance` explicitly.

## [0.26.0] — 2026-07-21

Pre-seal lint — a machine-check for seal *quality*, run before spending compute.

### Added
- **`prereg_lint` (㉗)** — lints a sealed pre-registration for defects that let
  silent compute leak past `falsifiability_check` (which only asks *whether* a
  kill-condition exists). Catches the failure classes a real experiment arc lost
  compute to (semantic-fuel cell arc, 2026-07-20~21):
  - a kill-condition that **leaked into the `metric` field** from a malformed
    call — the human eye sees a criterion, the parser sees none (FAIL);
  - a quantified kill written as **free text with no structured `kill_threshold`**
    → cannot be auto-evaluated (WARN);
  - a **pass bar at or below chance** (FAIL);
  - `min_n` below the small-sample floor (WARN);
  - **no pre-seal machine-checks declared** (INFO nudge).
  Ledger-level entry point; `_preseal_lint()` is the pure per-record core.
- **`preregister(pre_seal_checks=[...])`** — declare the cheap checks run before
  sealing (`reachability-smoke`, `mass-balance-audit`, `neutral-control`,
  `manipulation-check`, `positive-control`); `prereg_lint` reads them back.
- **`mm_prereg_lint` MCP tool** exposing the above.

## [0.25.0] — 2026-07-09

Anchor-discipline probes — completing the anchor trio, calibrated before use.

### Added
- **Anchor-discipline probes ㉔㉕** (`design` group; design doc
  `docs/GROUNDING_PROBES_DESIGN.md`) — the other two
  `anchor-reproduction-failure` catalog subtypes, completing the trio with ㉑:
  - `anchor_line_source_check` (㉔) — a positive-control anchor **line** copied
    from a stronger/other cell instead of aligned to this cell's sealed
    separatrix (grounds: M7b anchor-line-copy).
  - `anchor_cell_check` (㉕) — a positive-control anchor **cell** sitting on the
    threshold/boundary (straddles it seed-to-seed) instead of a deep regime
    (grounds: M8 threshold-cell).

  Structure only — no numbers ported. Vocab classifiers, fail-closed
  (unrecognized → WARN). Wired into `verify(data)` via `anchor_line_source` /
  `anchor_cell` keys and exposed as MCP tools.
- **Self FP/FN calibration for ㉔㉕** (`eval/self_fpfn/`): 14 core labeled
  cases (ground truth from the catalog subtypes, not probe code) + 2 disclosed
  fail-closed vocab traps. Core 0 FN / 0 FP (whole suite core: 74, still 0/0);
  traps fired as pre-registered. Sealed before running — the "mm flagged"
  qualification gate for these probes.
- **SPEC amendment A2** (§11, visible append — v1.0 normative text unchanged):
  optional `preregister` fields `anchor_cell`, `anchor_line_source`, and
  `known_confounds`. `preregister()` seals them; `audit()` auto-runs ㉔/㉕ and
  surfaces `known_confounds` as an INFO (a pre-declared confound legitimizes
  later attribution cycles); `mm_register` (MCP) exposes all three.

---

## [0.24.0] — 2026-07-08

Grounding probes: the mutual-grounding arc's sealed defense laws land as
real probes — calibrated before they may speak.

### Added
- **Grounding probes ㉑㉒㉓** (`design` group; design doc
  `docs/GROUNDING_PROBES_DESIGN.md`):
  - `anchor_basis_check` (㉑) — a positive-control anchor resting on a static
    "structurally guaranteed" argument instead of measured dynamics.
  - `threshold_provenance_check` (㉒) — a pass/kill threshold re-derived from
    the observed distribution (self-calibrating, attacker-draggable) instead
    of externally fixed.
  - `content_delta_check` (㉓) — judgment on agreement/match alone
    (rubber-stampable by near-identity claims) without a content-delta check.

  Structure only — no numbers ported from the source experiment (scope
  sentence in each docstring). Wired into `verify(data)` via
  `anchor_basis` / `threshold_source` / `judgment_basis` keys, exposed as
  MCP tools, vocab classifiers that **fail closed** (unrecognized → WARN).
- **Self FP/FN calibration for ㉑㉒㉓** (`eval/self_fpfn/`): 27 core labeled
  cases (ground truth from the sealed laws, not probe code) + 3 disclosed
  fail-closed vocab traps. Result: core 0 FN / 0 FP (whole suite: 60 core
  cases, still 0/0); traps fired exactly as pre-registered. Pre-registered
  and sealed before running — this is the qualification gate the design doc
  requires before reports may say "mm flagged" for these probes (ledgers are
  local provenance, not in this repo).
- **SPEC amendment A1** (visible append, §11 — v1.0 normative text
  unchanged): optional `preregister` fields `anchor_basis` and
  `threshold_source`, declared at seal time. `preregister()` seals them,
  `audit()` reads them back and runs ㉑/㉒ automatically; `mm_register`
  (MCP) exposes both. ㉓ stays on the `verify(data)` path (its input
  describes the analysis, not the prereg).

---

## [0.23.0] — 2026-07-03

### Fixed
- **Malformed `kill_threshold` no longer seals silently then crashes**
  (issue #18). A `kill_threshold` dict without a numeric `threshold` key
  used to pass `preregister()` unchecked and then raise `KeyError: 'threshold'`
  inside `audit()` / `falsifiability_check()` the moment a result was
  provided — and first-write-wins made it uncorrectable (re-registering the
  same `claim_id` was a no-op). Defense in depth:
  - **`preregister()` validates at seal time** — a dict `kill_threshold` must
    carry a numeric `threshold` and (if present) `direction ∈ {below, above}`,
    else `ValueError` while it can still be fixed.
  - **`_falsifiability_eval` degrades gracefully** — an already-sealed
    malformed entry now returns `WARN` ("Malformed kill_threshold … cannot
    auto-evaluate") instead of crashing every downstream audit.

  Found by dogfooding: it's easy to pass a domain-specific `kill_threshold`
  (e.g. `{"H1_reject_if": ...}`) that reads fine and seals fine. 5 regression
  tests added (`tests/test_kill_threshold_validation.py`).

---

## [0.22.1] — 2026-07-02

Docs consistency sweep after the day's five releases (audited EN↔KO drift,
stale commands, broken links).

### Added
- **`docs/SPEC_KO.md`** — Korean reference translation of MIRROR-SPEC v1.0
  (clearly marked non-normative: the English SPEC.md governs).
- **`catalog/README_KO.md`** — fully-Korean catalog front page.
- README (EN+KO): prominent links to MIRROR-SPEC v1.0 and the illusion
  catalog — v0.19–0.22's two headline artifacts were not reachable from
  the front page.
- `docs/CHRONICLE.md`: afterword chapter — the day the mirror forged
  itself (SPEC ratification + catalog promotion, 4 code bugs / 22 spec
  defects surfaced by spec-writing).

### Fixed
- **CHRONICLE evidence links were all broken** (pointed at pre-reorg
  `db/*.jsonl`; files live under `db/curated/` and `db/measured/`).
- **README_KO Quick Start taught the unfalsifiable path** — it predated
  the 0.17.1 onboarding fixes (no `--kill-threshold`, auto-load-first
  ordering). Ported to parity with the English Quick Start.
- README_KO stack blockquote was missing the four-pillars sentence
  (PILLARS_KO link) present in the English version.

---

## [0.22.0] — 2026-07-02

**측정착시 도감 v1 (Catalog of Measurement Illusions)** — the knowledge asset
promoted to a first-class artifact: 30 entries, every one backed by a real
recorded case from our own sealed research history (no invented examples).

### Added
- **`catalog/`** — 30 entries across 4 categories: `gaming/` 12 (best-of-N,
  small-n, crippled baseline, metric switch, …), `self-catch/` 7,
  `fn-guard/` 9, `contamination/` 2. One file per illusion: signature /
  mechanism / real case (provenance to `db/curated/` + ledger seals) /
  detection probe / **misapplication warning** (bidirectional defense —
  over-labeling is itself an illusion).
- 4 new specimens mined from a sealed retrospective census of the family
  ledgers (44 files, 571 lines; census protocol preregistered, seal
  `f7fd1cda…`, result sealed `9cc064ad…`): instrument-bug-as-verdict,
  anchor-reproduction-failure, untestable-substrate,
  kill-tripped-but-invalid. Raw seeds appended to
  `db/curated/false_negative_guards.jsonl` (5 → 9).

### Notes
- Census byproduct worth recording: **166/166 preregistrations (100%) carry
  kill criteria** — falsifiability compliance across the whole ledger
  history; 22 retractions, 3 amendments, 0 malformed lines.

---

## [0.21.0] — 2026-07-02

**MIRROR-SPEC v1.0 RATIFIED.** The second clean-room round (fresh agent,
spec text only) achieved byte-exact §4.1 canonicalization, 5/5 blind-vector
verdicts, correct answers to all five targeted ambiguity probes, and valid
ledger production including amendments — with zero blocking ambiguities.
The freeze criterion ("a newcomer interoperates from the spec alone") is
met; the spec is now frozen per §9.

### Changed (spec — final pre-freeze errata, from round-2 pedantic log)
- §3.1: non-UTF-8 bytes = malformed content (step 2); blank = empty or
  whitespace-only; duplicate keys = last-wins (pinned: it changes seals).
- §3.3: present-but-non-string `seal`/`prev_seal` string-coerced, no crash.
- §4.1.4: Python `repr` is normative where languages' shortest-round-trip
  renderings diverge (exponent thresholds); misleading "Python/JS" fixed.
- §5.1: genesis comparison pinned to ASCII-case-insensitive.
- §6.1: `entries` value pinned for step 4/5 failures.
- §6.2: L1+ runs only when L1 is OK.
- §7.1: amendment identified solely by top-level `amends_seal`; `_type` MAY
  be "preregister" or "amendment" but MUST NOT be relied on.
- §8: vectors = companion artifacts; text alone suffices to implement.

### Fixed
- **`linkage_check` crashed (UnicodeDecodeError) on non-UTF-8 bytes** —
  the round-2 log asked whether bad bytes are "unreadable" or "malformed";
  the code's answer was neither. Fourth real bug surfaced by spec-writing.
  Reference verifier fixed identically; vector `invalid_09_bad_utf8` guards.

---

## [0.20.0] — 2026-07-02

SPEC r2: close the 12 ambiguities logged by the newcomer interoperability
test (a clean-room agent given ONLY docs/SPEC.md; it produced a valid ledger
and judged 5 blind vectors 5/5, but flagged every place it had to guess).

### Changed (spec)
- **§4.1 canonical JSON is now spelled out byte-exactly** — recursive key
  sort, separators, escaping, and number serialization (shortest round-trip
  float repr, int≠float) — instead of deferring to "Python json.dumps
  defaults". This is what the "any language" claim needed.
- §4 rule 4: Ed25519 layer specified (sig = hex signature over the UTF-8
  bytes of the 16-hex seal string; pubkey = hex 32-byte raw key) — matches
  action-mirror's implementation.
- §3: non-object JSON lines are malformed; missing seal/prev_seal read as
  `""` (verifiers MUST NOT crash); on-disk line formatting explicitly
  unconstrained; LF + anchor-hash byte-sensitivity note.
- §6.1: indices are 0-based entry positions; conformance granularity defined
  (verdict + failing step, message text informative).
- §6.2: "type-aware" mislabel fixed (recomputation needs no type knowledge).
- §7.1: preregister identified by shape (`_type` optional, both accepted);
  amendment's normative marker = top-level `amends_seal` (kill_threshold
  copy + metric prefix = tolerated legacy); retraction claim_id matching
  scoped to audit layer.
- §4 rule 5: 64-bit seal truncation / duplicate-seal non-guarantee stated.

### Fixed
- **`linkage_check` crashed (AttributeError) on JSON lines that parse but
  are not objects** (`42`, `[1,2]`) — found because the newcomer asked what
  the verdict should be and the spec had no answer. Now FAILs as malformed
  (§6.1 step 2). Reference verifier fixed identically.

### Added
- Vector `valid_04_numbers` — byte-pins §4.1 canonicalization (floats, int
  vs float, nested sort, unicode, bool, null).
- Vector `invalid_08_non_object` — regression guard for the crash fix.

---

## [0.19.1] — 2026-07-02

### Fixed
- **`verify_chain` false-FAIL on uppercase genesis** (the 0.19.0 known
  issue). First-entry `prev_seal` is now compared case-insensitively per
  SPEC §5.1, matching `linkage_check`. action-mirror writes `"GENESIS"`
  (9 real family ledgers), measure-mirror writes `"genesis"`; both are
  valid. Caught by conformance vector `valid_02_legacy`; regression test
  `test_verify_chain_accepts_uppercase_genesis` added.

---

## [0.19.0] — 2026-07-02

MIRROR-SPEC v1 (DRAFT): promote the ledger format from "what the code does"
to a normative specification. From ratification onward, the spec is the source
of truth and the packages are reference implementations.

### Added
- **`docs/SPEC.md`** — MIRROR-SPEC v1.0 DRAFT: normative ledger format &
  verification protocol (seal algorithm §4, chain rules §5, verification
  levels L1/L1+/L2/L3a/L3b §6, all 11 record types §7, conformance §8,
  freeze policy §9, legacy variances §10). Honest scope stated up front:
  integrity/non-erasability/falsifiability/verifiability — never content
  truth, never independence.
- **`spec/vectors/`** — 11 conformance vectors (4 valid, 7 invalid) with
  `expected.json` verdicts; each invalid vector pins one attack (tamper,
  delete, replace, truncate, rewrite…). Regenerable via `spec/gen_vectors.py`.
- **`spec/reference_verifier.py`** — single-file, zero-dependency verifier
  implementing L1 + seal recomputation + L2 peer-witness; `--vectors` runs
  the conformance suite (ALL MATCH).
- **`tests/test_spec_vectors.py`** — CI guard: reference verifier reproduces
  all expected verdicts; `mm.linkage_check` agrees with every expected L1.

### Known issue (documented, not yet fixed)
- Producers split on genesis case (`mm` writes `"genesis"`, `am` writes
  `"GENESIS"`; 9 real family ledgers start uppercase). `mm.linkage_check`
  accepts both — SPEC §5.1 codifies this. `mm.verify_chain` compares
  case-sensitively and false-FAILs am-produced ledgers; pinned by vector
  `valid_02_legacy`, fix planned as a follow-up release.

---

## [0.18.0] — 2026-06-29

Single-source the stack's linkage check (P2). The format-agnostic
`prev_seal→seal` linkage verification existed in **three** copies that had
already drifted — and two of them carried latent crash bugs.

### Added
- **`mm.linkage_check(path) -> (ok, message, entries)`** — the one canonical,
  stdlib-only, format-agnostic linkage verifier (works on any mirror ledger:
  claims / actions / provenance). Unlike `verify_chain()` it does not recompute
  measure-mirror's own seal, so it is the check both stack verifiers share.

### Fixed
- **`stack/verify_self.py:generic_linkage` no longer crashes on bad input.** It
  now delegates to `mm.linkage_check`, so an **empty** ledger (previously
  `None[:16]` → `TypeError`) and a **malformed JSON** line (previously an
  uncaught `JSONDecodeError`) are reported as a clean `FAIL`, not a stack trace.
  Valid ledgers verify identically (bundled evidence still `ALL OK 6/6`).

### Notes
- The outsider `mirror-stack-verify` CLI (in `mirror-stack-mcp`) keeps an
  intentional inline copy for self-containment, now **conformance-pinned** to
  this canonical definition by a test there — so the two can no longer diverge.

Adds 6 tests (235 → 241). No probe semantics changed.

---

## [0.17.1] — 2026-06-29

Stranger-onboarding fixes — the Quick Start now walks a newcomer from install to
first sealed claim and verify with **0 blocking steps** (measured against a clean venv).

### Fixed
- **CLI Quick Start no longer dead-ends.** The README presented `mm my_model` (auto-loads
  `my_model.json`) as the natural Step 2, but nothing in the walk created that file — a
  newcomer hit `🪞 No result file found` (exit 1). Step 2 now leads with the inline-flags
  audit (`mm audit my_model --acc 0.72 --n 500`, nothing else to create) and shows the
  file-based forms only after actually writing `my_model.json`.
- **Quick Start now models the disciplined seal.** Both the README examples and
  `examples/quickstart.py` pre-registered *without* a kill-condition, so every audit on the
  "honest happy path" printed a `⚠️ Unfalsifiable` warning — teaching newcomers the
  un-falsifiable path. They now seal a `kill_threshold` (`acc < 0.55`), so the happy path
  audits clean (✅ OK) and a failing value trips a proper `FAIL` (falsified by its own
  pre-registered criterion). Python-API snippet corrected to the structured
  `kill_threshold={"metric","threshold","direction"}` form.
- **Python-API Quick Start snippet now runs copy-paste verbatim.** It referenced
  undefined `train_set`/`test_set` in `full_audit(...)` (→ `NameError`) and then a
  differently-named `train_items`/`test_items` in the individual-probe line. Both unified
  and defined up front, so the whole block runs clean (exit 0) as a newcomer pastes it.
- **Clarified "re-registration is silently ignored."** The Design Principles wording read
  as if the *file write* is dropped; reworded to state precisely that only the first sealed
  registration counts in `audit()`, while a later one is still appended to the chain (the
  record is never silently lost) and cannot override the original.

Docs/examples only — no probe semantics changed (235 tests unchanged). Verified by an
independent newcomer agent: CLI Quick Start = 0 blocks; Python Quick Start now runs verbatim.

---

## [0.17.0] — 2026-06-25

Auto-resolution — `falsifiability_check` evaluates a sealed result, instead of
warning "result not yet provided".

### Changed
- **`falsifiability_check(...)` self-evaluates from a sealed resolution.** When no
  `reported_acc` is handed in, it now recovers one from the ledger instead of
  returning WARN: a **retraction** → `FAIL` (RETRACTED, resolved-negative); an
  **`am_record(target=claim_id)`** with a numeric result (`reported_acc`/`acc`/
  `result`/`value`/…) → the kill-condition is evaluated against it (annotated
  *auto-recovered*); an `am_record` with a categorical `verdict` (or a
  `VERDICT … = X` action) → `FAIL` for KILL/FALSIFIED/…, `OK` for PASS/SUPPORTED/….
  An explicit `reported_acc` still wins; an unresolved claim keeps the WARN.

### Added
- **`am_ledger=` arg** on `falsifiability_check` (the action ledger to scan for the
  result; the claims ledger is always scanned for retractions + co-located actions).
- `_recover_resolution()` helper and `tests/test_auto_resolution.py` (8 tests:
  unresolved WARN, numeric recovery, KILL/PASS verdicts, sealed retraction,
  explicit override, co-located action, unknown-verdict fall-through).

### Migration
No change for callers that pass `reported_acc`. Standalone falsifiability checks
on a resolved claim now return a verdict instead of WARN — pass `am_ledger=` if
the result lives in a separate action ledger.

---

## [0.16.0] — 2026-06-25

Metric-kind self-calibration — the proportion probes no longer false-FAIL on
percentage / delta / span / unbounded metrics.

### Changed
- **`audit()` is metric-kind aware.** The hardcoded `0.0 ≤ acc ≤ 1.0` range check
  and the `baseline = 0.5` default are gone. The metric's range and chance level
  now come from (in precedence) an explicit arg → the sealed pre-registration →
  inference from the metric name (`*_pct` → `[0,100]`, `*delta` → unbounded,
  `*span`/`*window` → `[0,∞)`, else the `[0,1]` proportion). The integer-grid /
  binomial probes (GRIM, small-sample CI) now run **only on proportions** — a
  percentage is normalised to `[0,1]`; a delta/span/unbounded metric skips them
  (with an explicit `④a metric-kind` note pointing to `continuous_audit()`).
  A range error now tells you how to fix it (`declare metric_range=…`).
- **Small-sample distinguishability uses an exact two-sided binomial test** for
  small `n` (Wilson's normal approximation is over-optimistic at the boundary;
  measured in `eval/self_fpfn/v2`), falling back to Wilson for `n > 10_000`.

### Added
- **`metric_range` + `chance`** optional fields on `preregister()` (sealed) and
  optional args on `audit()`. Backward compatible: omitting them reproduces the
  previous behaviour for `[0,1]` proportions.
- `resolve_metric_kind()` helper and `tests/test_metric_kind.py` (15 tests:
  inference, explicit override, no-false-FAIL on %/delta/span, declared-chance
  beats 0.5, GRIM still catches genuine impossibilities, sealed round-trip).

### Migration
No change needed for `[0,1]` accuracy claims. For a percentage / delta / span
metric, pass `metric_range` (and `chance` for a distinguishability test) to
`preregister`/`audit`, or rely on the name-based inference.

---

## [0.15.1] — 2026-06-15

Pre-PyPI stability hardening (no public API change).

### Changed
- **Narrowed exception handling** in the `db/` lookup helpers
  (`lookup_baseline`, `lookup_reproduction`, the curated-pattern loader): the
  broad `except Exception:` that silently returned `None`/`[]` is now
  `except (OSError, json.JSONDecodeError)`. Missing/corrupt db files still
  degrade gracefully, but an *unexpected* error now surfaces instead of being
  swallowed — for an integrity tool a hidden error must never become a silent
  "OK".

### Added
- **Property-based tests** (`tests/test_properties.py`, Hypothesis) for the
  deterministic probes — random inputs across the whole domain assert invariants
  (Wilson CI is always a valid sub-interval of [0,1]; GRIM never rejects a
  reachable proportion; exact/identical leakage always FAILs; no probe crashes on
  edge inputs like n=0, p=0/1, empty lists, unicode). 188 → 206 tests.
- **`package` CI job** + `tests/smoke_installed.py` — builds the wheel, installs
  it into a clean environment, and smoke-tests the *installed* package (run from
  outside the source tree). Catches the "works in the repo, broken on
  `pip install`" class and locks the graceful-degrade contract when `db/` is
  absent (`db/` is repo-local and intentionally not shipped in the wheel).

---

## [0.15.0] — 2026-06-14

Driven by external review and a new self-evaluation of the tool's own FP/FN.

### Added
- **`eval/self_fpfn/`** — measures the probe suite's *own* false-positive /
  false-negative rate on a labeled set (answers "who measures the measurer?").
  v1: core 33 in-scope cases → FN 0/19, FP 0/14 (small-n Wilson upper ~0.17–0.22,
  a gross-miscalibration smoke test). v2: 1119 oracle-labeled cases with oracles
  **independent of the probe** — GRIM vs brute-force k-sweep (0/304, shortcut
  proven complete) and small-sample vs **exact binomial** (FN 7/542 = 0.0129,
  all over-optimistic near the boundary; quantifies the Wilson-vs-exact gap and
  motivates a future exact/Clopper-Pearson option). Each run pre-registered and
  hash-sealed before execution; `tests/test_self_fpfn.py` guards the result.
- **`baseline_fairness(..., n=…)`** — optional sample size. For accuracy-style
  metrics, a Δ above the fixed `margin` must *also* clear the baseline by 95%
  Wilson CI; otherwise it is flagged as not statistically distinguishable. The
  fixed margin alone is n-blind. Backward compatible (no `n` → prior behaviour).
- **`leakage_check` fuzzy matching** — beyond exact hash intersection: a
  normalized match (case / whitespace / punctuation) → FAIL, and a token-Jaccard
  near-duplicate (≥ threshold, default 0.7) → WARN. `fuzzy=False` restores
  exact-only. Honest limit: semantic paraphrase below the threshold still needs
  embedding-based matching (documented, not papered over with a lossy low
  threshold). Both new options are exposed on the MCP server.
- 6 new tests (188 → 194, all passing). `__version__` 0.15.0.

## [0.14.3] — 2026-06-12

### Added
- **⑩ GRIM `items=` parameter** — number of items averaged per subject
  (default 1). A mean of `items` integer responses from each of `n` subjects
  has granularity `N = n·items` (the GRIM paper's standard multi-item form).
  Previously the caller had to pass `n·items` by hand; now `grim_check(value,
  n, items=3)` handles it. `items < 1` guards to WARN.
- **External validation test** — `grim_check` cross-checked against the
  `scrutiny` (R) package's GRIM vignette: **18/18 verdicts reproduced** (means,
  multi-item Likert, percentages). Locked in as a regression test so our GRIM
  stays aligned with the de-facto reference implementation.
- 2 new tests (186 → 188, all passing). `__version__` 0.14.3.

### Notes
- Dog-fooding GRIM against external data (scrutiny's 18-case set) is what
  surfaced both the `items` gap here and the `k≤n` mean bug in 0.14.2 — the
  tool's own discipline applied to itself, again.

## [0.14.2] — 2026-06-12

### Fixed
- **⑩ GRIM now works on means, not just proportions.** Dog-fooding the tool
  against the GRIM paper's own canonical example (Brown & Heathers 2017:
  "28 integers cannot mean 5.19") surfaced a real bug: `grim_check` capped the
  candidate count at `k ≤ n`, which silently assumed a proportion (`k = acc·n ≤
  n`). A **mean** of integers has `k = mean·n > n` (e.g. Likert avg 5.18 at
  n=28 → k=145), so valid means like 5.18 were wrongly reported FAIL while the
  error message itself listed `k=145 → 5.18` as a candidate (self-contradiction).
  Fix: `0 ≤ k ≤ n` → `k ≥ 0`. Verified against 5 GRIM-paper cases and 3
  proportion regressions; recorded in `db/curated/self_catches.jsonl`.
- 3 new regression tests (183 → 186, all passing). `__version__` 0.14.2.

---

## [0.14.1] — 2026-06-12

**db split by producer** — `db/` is now physically divided so "what the tool
measured" and "what we wrote by hand" can never be confused.

### Changed
- **`db/measured/`** — measure-mirror's own quantitative output:
  `baselines.json`, `reproductions.jsonl`. Verdicts are computed by the tool;
  cross-check confirmed feeding `(acc, n)` back through the Wilson-CI logic
  reproduces every recorded verdict with **0 mismatches**.
- **`db/curated/`** — human-curated qualitative records: `self_catches`,
  `false_negative_guards`, `gaming_patterns`, `contamination`, and the new
  `research_closures.jsonl`.
- **13 qualitative closures moved out of `reproductions.jsonl`** — they carried
  `verdict: FAIL` but no `acc`/`n`, so they were never measure-mirror output.
  They now live in `curated/research_closures.jsonl` (`catch_history` kind
  `closure`). `reproductions.jsonl` keeps only the 2 quantitative records the
  tool can actually re-judge.
- Code paths updated: `lookup_baseline` / `lookup_reproduction` /
  `record_reproduction` → `db/measured/`; `catch_history` → `db/curated/`
  (now 5 kinds, adds `closure`).
- New `db/README.md` documents the measured/curated distinction.
- README / README_KO `db/` sections rewritten around the split.
- `__version__` 0.14.1. 183 tests still pass (paths updated).

---

## [0.14.0] — 2026-06-12

**Local memory release** — `db/` reframed from a (dead) shared database into
working local memory, and `reproductions.jsonl` wired into the audit loop.

### Added
- **`lookup_reproduction(task, db_dir)`** — read prior FAILED reproductions for
  a task from `db/reproductions.jsonl` (skips `_doc` header rows, returns
  FAIL-verdict records only).
- **`record_reproduction(task, *, claim, acc_claimed, n_claimed, acc, n, ...)`**
  — the write companion: append a reproduction result; verdict (FAIL/PASS) is
  auto-judged from the reproduction's own Wilson CI vs the task baseline. Memory
  now *grows* — a recorded failure warns every future audit on that task.
- **`audit(task=...)` now surfaces prior reproduction failures** as a
  `⚙ prior-reproduction` WARN. The real ZERO `musr` 55.6%/64.5% records that had
  been sitting dead in `db/` since the 2026-06-08 seed are now live.
- **`catch_history(*, kind, source, db_dir)`** — query the local **catch log**
  across `self_catches` / `false_negative_guards` / `gaming_patterns` /
  `contamination`, each record tagged with its `kind`. These four files are
  reframed from "dead narrative notes" to **structured detection history**:
  what you already caught (false positives on yourself, re-checked false
  negatives, gaming signatures, contamination), searchable so you don't
  re-derive it. Read-only — not auto-wired into `audit` (fuzzy text matching
  would mean false positives), honestly so.

### Changed
- **README / README_KO: `db/` honestly reframed** from "Shared Integrity
  Database (CVE model)" → "Local Memory". The shared-DB framing failed the
  trust ⊥ reputation dilemma (nobody crowd-shares their own failures); the value
  that holds — *warn future-me about patterns past-me got burned by* — needs no
  sharing and works regardless of data privacy.
- Honest labeling: only `baselines.json` (read) and `reproductions.jsonl`
  (read+write) are wired into code. `self_catches` / `false_negative_guards` /
  `gaming_patterns` / `contamination` are now labeled narrative notes, not
  promised as automatic features (the tool applies its own "no dead-legacy
  halo" discipline to its own db).
- 10 new tests (total: 169 → 179, all passing).
- `__init__.py` exports `lookup_reproduction`, `record_reproduction`;
  `__version__` 0.14.0.

---

## [0.13.0] — 2026-06-11

**Simplification release** — three verification tiers, no new probes.

### Added
- **`verify(ledger_path, data, *, groups=None)`** — single entry point.
  Input-driven: every probe whose keys exist in `data` runs; nothing else does.
  - FULL tier: `verify(ledger, data)` — one-shot, everything applicable
  - GROUP tier: `verify(ledger, data, groups=["judge"])` — restrict to groups
  - INDIVIDUAL tier: existing probe functions, unchanged
- **`GROUPS` registry + `group_of(finding)`** — 6 verification groups:
  `ledger` (①⑫+chain) · `stats` (④⑤⑦⑧⑨⑩) · `design` (②③⑥⑪) ·
  `negative` (⑬) · `judge` (⑭–⑱) · `ranking` (⑲⑳).
- **CLI `mm verify --file data.json [--groups ...] [--list-groups]`**.
- **MCP `mm_verify`** — full/group verification for agents (30 tools total).

### Changed
- **`judge_run` no longer auto-fires ⑯ inter_rater_agreement** — run-1 vs
  run-2 of the same judge duplicates the signal ⑭ already measures. ⑯ remains
  available standalone for two genuinely different judges.
- README probe tables reorganized by verification group; "Three Verification
  Tiers" section added (EN/KO). GUIDE: tier/group overview section (EN/KO).
- 9 new tests (total: 160 → 169, all passing).
- `__init__.py`: exports `verify`, `GROUPS`, `group_of`; `__version__` 0.13.0.

---

## [0.12.0] — 2026-06-11

### Added
- **⑲ `judge_transitivity_check(matches)`** — preference-cycle detection for
  pairwise judge tournaments. Aggregates matches per pair by majority vote and
  DFS-checks the preference graph; a cycle (A>B>C>A) means the judge has no
  consistent quality scale and any leaderboard from its verdicts is an artifact
  of match ordering. Tied pairs produce no edge (no false cycles).
- **⑳ `ranking_stability_check(scores_a, scores_b, *, n_boot=1000, seed=0, min_stability=0.95)`**
  — bootstrap guard against ranking mirages. Resamples paired per-item scores
  and measures how often "A beats B" survives. Deterministic (seeded RNG).
  FAIL below 80% stability, WARN below 95%, FAIL on exactly tied means.
- **`badge(cert, *, fmt="markdown"|"svg")`** — render a certificate as an
  embeddable badge. Markdown form uses shields.io (verdict-colored: green /
  yellow / grey / red); SVG form is self-contained and offline, with the
  certificate seal + anchor-hash prefix embedded in the tooltip for
  traceability.
- **CLI**: `mm certify --badge {markdown,svg}`; `mm judge --file` now also
  accepts `matches` (⑲) and `scores_a`+`scores_b` (⑳) keys.
- **3 new MCP tools**: `mm_judge_transitivity_check`,
  `mm_ranking_stability_check`, `mm_badge` (29 tools total).
- 16 new tests (total: 144 → 160, all passing).

### Changed
- Probe count: 18 → 20 / utilities 5 → 6. README "23 Probes + 6 Utilities".
- `badge` added to sync-gate `_MCP_UTILITY_TOOLS`.
- `__init__.py`: exports `judge_transitivity_check`, `ranking_stability_check`,
  `badge`; `__version__` 0.12.0.
- mm.py imports `random` (stdlib — still zero external dependencies).

---

## [0.11.0] — 2026-06-11

### Added
- **⑱ `judge_swap_check(forward_results, swapped_results, *, position_lock_threshold=0.65, noise_threshold=0.35)`**
  — Position-swap cross-validation. Each pair is judged as (A,B) and again as
  (B,A); a content-driven judge inverts its verdict, a content-blind judge keeps
  choosing the same slot. Catches the hardest judge pathology: a deterministic,
  balanced judge that never reads the responses **passes ⑭⑮⑯⑰ and is caught
  only by ⑱** (see `examples/demo_judge.py`).
  - lock_rate ≈ 0 → OK (content-driven) · ≈ 0.5 → WARN (noise) · ≈ 1 → FAIL (position-locked)
- **`certificate(ledger_path, claim_id, *, findings=None)`** — sealed verification
  certificate utility. Collapses prereg seal + chain integrity + retraction status
  + optional audit findings into one SHA-256-sealed verdict:
  `CERTIFIED / CERTIFIED-WITH-WARNINGS / UNVERIFIED / REJECTED`.
  Embeds the ledger `anchor_hash`, pinning the exact ledger state attested to.
- **`judge_run` upgrades**:
  - `swap_positions=True` — extra AB→BA pass, fires ⑱ automatically,
    records `swap_lock_rate` in the ledger entry.
  - **Parse-failure handling** — unparseable judge responses (-1) are excluded
    from all probes (previously they silently distorted ⑮ bias and ⑰ sanity);
    `judge-parse` WARN fires above 10% failure rate, FAIL when nothing parsed.
    New return keys: `swap_scores`, `parse_failures`.
- **CLI**: `mm judge --file scores.json` (audit pre-collected judge scores,
  probes ⑭⑮⑯⑰⑱) and `mm certify <claim_id> [--acc X --n N] [--pretty]`.
- **2 new MCP tools**: `mm_judge_swap_check`, `mm_certificate` (26 tools total).
- **`examples/demo_judge.py`** — mock-judge demo, no API key needed: honest
  judge, content-blind judge (⑱-only catch), degenerate judge.
- 17 new tests (total: 127 → 144, all passing).

### Changed
- Probe count: 17 → 18 (mm.py) / utilities 4 → 5. README "21 Probes + 5 Utilities".
- `certificate` added to sync-gate `_MCP_UTILITY_TOOLS`.
- `__init__.py`: exports `judge_swap_check`, `certificate`; `__version__` 0.11.0.

---

## [0.10.0] — 2026-06-11

### Added
- **⑭ `judge_consistency_check(score_pairs, *, flip_threshold=0.20)`**
  — Detects an unreliable LLM judge by measuring verdict flip-rate.  Run the
  judge twice on the same items; if >`flip_threshold` fraction of verdicts
  change, the judge cannot be trusted.
- **⑮ `judge_bias_check(pairwise_results, *, bias_threshold=0.60)`**
  — Detects systematic position preference (A-wins / B-wins) in a pairwise
  judge. If either position wins >60% of comparisons, FAIL.
- **⑯ `inter_rater_agreement(ratings_matrix, *, min_kappa=0.40)`**
  — Computes Cohen's κ between two judge runs / raters.  WARN below 0.40,
  FAIL below 0.20 (poor agreement = scores are effectively noise).
- **⑰ `judge_score_sanity(scores, *, min_unique_ratio=0.10)`**
  — Catches a degenerate judge that assigns identical scores to every item.
  FAIL if all scores identical; WARN if >90% share the same value.
- **`measure_mirror/judge.py`** — optional LLM-as-a-Judge runner module
  (install: `pip install "measure-mirror[judge]"`).
  - `openai_judge(model, *, system_prompt, prompt_fn, pairwise)` → callable
  - `anthropic_judge(model, *, system_prompt, prompt_fn, pairwise)` → callable
  - `judge_run(ledger_path, claim_id, *, judge_fn, items, runs=2, pairwise=True)`
    → dict with `findings`, `scores`, `score_pairs`, `ledger_entry`.
    Automatically fires probes ⑭⑮⑯⑰ and appends a chain-linked
    `_type: judge_run` entry to the ledger.
- **`pyproject.toml`** — new `judge` optional-dependency group:
  `pip install "measure-mirror[judge]"` adds `openai>=1.0` and `anthropic>=0.20`.
- **4 new MCP tools**: `mm_judge_consistency_check`, `mm_judge_bias_check`,
  `mm_inter_rater_agreement`, `mm_judge_score_sanity`.
- 24 new tests (total: 101 → 125, all passing).

### Changed
- Probe count: 16 → 20 (⑭⑮⑯⑰ added). README updated: "20 Probes + 4 Utilities".
- MCP server docstring: "16 probes" → "20 probes".
- Module docstring: updated to list ⑭⑮⑯⑰.

---

## [0.9.0] — 2026-06-11

### Added
- **⑬ `negative_audit(ledger_path, *, angles, min_angles=3, conclusion_scope, tested_scope)`**
  — Negative-claim audit / premature-closure gate. A "Resolved-Negative" conclusion is
  only trustworthy when multiple independent pre-registered experiments converge.
  - `FAIL` — fewer than `min_angles` (default 3) angles provided; any angle lacks a
    preregister entry; or `conclusion_scope` is broader than `tested_scope`.
  - `WARN` — angle count is sufficient but at least one angle has been retracted
    (weakened case — not yet invalid).
  - `OK` — all checks pass.
  - Optional `conclusion_scope` / `tested_scope` pair activates scope check at the
    same call (complements the existing `scope_check` probe for positive claims).
- **`full_audit()` gains `angles` and `min_angles` optional params** — if `angles` is
  provided, `negative_audit` runs automatically and appends its finding.
- **CLI `mm negative --angles <id1> [id2 ...]  [--min-angles N]`** — standalone
  negative-claim audit from the command line.
- **`mm_negative_audit`** MCP tool.
- 8 new tests (total: 93 → 101, all passing).

### Changed
- Probe count: 15 → 16. README / README_KO updated: "16 Probes + 4 Utilities".
- Module docstring: updated to list ⑬.

---

## [0.8.0] — 2026-06-11

### Added
- **⑫ `cascade_check(ledger_path, claim_id)`** — Retraction cascade probe.
  Checks whether a claim, or any of its transitive dependencies, has been
  retracted. Levels: `FAIL` (claim itself retracted), `WARN` (claim is STALE:
  a dependency was retracted), `OK` (no retraction risk). Runs automatically
  inside `audit()` — only WARN/FAIL are appended to findings.
- **`retract(ledger_path, claim_id, reason)`** — Retraction utility.
  Appends a chain-linked `_type="retraction"` entry to the ledger. Retraction
  records cannot be silently deleted — removing them breaks the chain and is
  detected by `verify_chain()`. Every call appends a new entry.
- **`preregister()` gains `depends_on: list[str] | None`** — seal which prior
  claims this claim builds on. If any of those are later retracted,
  `cascade_check()` flags this claim STALE, transitively.
- **CLI `mm retract <claim_id> --reason "..."`** — command to record a
  retraction. Prints the seal of the retraction entry.
- **CLI `mm register`** gains `--depends-on <id1> [id2 ...]` flag.
- **`mm_cascade_check`** MCP tool (probe — returns Finding).
- **`mm_retract`** MCP tool (utility — returns dict, like `mm_anchor`).
- **`mm_register`** MCP schema updated with optional `depends_on` field.
- 10 new tests (total: 83 → 93, all passing).
- Sync gate: `"retract"` added to `_MCP_UTILITY_TOOLS` exclusion list.

### Changed
- Probe count: 14 → 15. Utilities: 3 → 4. README / README_KO updated.
- Module docstring: "10 probes" corrected to "12 probes" (⑪ was already present).

---

## [0.7.0] — 2026-06-11

### Added
- **⑪ `falsifiability_check(ledger_path, claim_id, *, reported_acc)`** — Popper gate.
  Verifies that a kill-condition was registered with the claim and auto-evaluates
  the structured `kill_threshold` against the reported result.
  - `FAIL` when `kill_threshold` is triggered — claim falsified by its own
    pre-registered criterion.
  - `WARN` when no kill-condition exists ("unfalsifiable") or threshold is
    registered but result not yet provided.
  - `OK` when threshold is not triggered or a text-only condition is registered.
  - Runs automatically inside `audit()` (zero extra code required).
- **`preregister()` gains two optional fields**:
  - `kill_condition: str` — human-readable falsification description.
  - `kill_threshold: dict` — structured auto-evaluable form:
    `{"metric": "acc", "threshold": 0.55, "direction": "below"}`.
    `direction` can be `"below"` (error ≥ threshold) or `"above"` (higher-is-bad
    metrics like MSE). Both fields are sealed into the chain hash.
- **CLI `mm register`** gains three new flags:
  `--kill <text>`, `--kill-threshold <float>`, `--kill-direction below|above`.
- **`mm_falsifiability_check`** MCP tool.
- **`mm_register`** MCP schema updated with `kill_condition` / `kill_threshold`.
- **`_load_prereg()` robustness fix**: now skips witness/anchor entries
  (`_type` present) so they are never confused with preregister entries.
- 11 new tests (total: 72 → 83, all passing).

### Changed
- Probe count: 13 → 14. README / README_KO updated: "14 Probes + 3 Utilities".

---

## [0.6.0] — 2026-06-11

### Added
- **`anchor(ledger_path)`** — tamper-evident ledger snapshot utility. Computes
  the SHA-256 of the full ledger file (`anchor_hash`) plus the last entry's
  seal (`head_seal`), entry count, and `chain_ok` (from `verify_chain()`).
  Printed to stdout as compact JSON so users can pipe it to any external
  storage they trust (Dropbox, Gist, S3, etc.). The `anchor_hash` detects
  **complete ledger file replacement** — the one attack chain hashes cannot
  catch alone. Available as `mm anchor [--pretty]` CLI command and
  `mm_anchor` MCP tool.
- 5 new tests (total: 67 → 72, all passing).
- Sync gate: `"anchor"` added to `_MCP_UTILITY_TOOLS` exclusion list.

### Changed
- MCP server: 15 → 16 tools (13 probes + 3 utilities: anchor, calibrate, witness).
- Probe + utility table in README/README_KO updated to "13 Probes + 3 Utilities".

---

## [0.5.0] — 2026-06-11

### Added
- **`calibrate()`** — self-test utility. Runs 5 synthetic known-good/bad cases
  through the key probes (small-sample FAIL, honest large-sample OK, GRIM FAIL,
  GRIM OK, baseline inversion FAIL) and verifies expected outcomes. Returns
  `[OK]` when the mirror is healthy; `[FAIL]` with details when any case breaks.
  Available as `mm calibrate` CLI command and `mm_calibrate` MCP tool.
- **`witness(ledger_path, claim_id, command, *, timeout)`** — witness-run utility.
  Executes a command via subprocess, captures stdout/stderr/returncode, hashes
  the output (`output_hash`), and appends a chain-linked `_type="witness"` entry
  to the ledger. Proves which command ran, when, and exactly what it produced.
  Available as `mm run <claim_id> [--] <command...>` CLI command (also runs
  calibration first unless `--no-calibrate`) and `mm_witness` MCP tool.
- 8 new tests (total: 59 → 67, all passing).
- Sync gate updated: `witness` added to `_MCP_UTILITY_TOOLS` exclusion list.

### Changed
- `mm run` subcommand added to CLI alongside existing `register` / `audit`.
- Probe + utility count in README/README_KO updated: "13 Probes + 2 Utilities".
- MCP server docstring updated: 13 probes + 2 utilities (15 tools total).

---

## [0.4.0] — 2026-06-11

### Added
- **⑩ `grim_check(reported_acc, n, *, n_decimals)`** — GRIM
  (Granularity-Related Inconsistency of Means) test. Checks that
  `reported_acc × n` is consistent with a whole-number count `k`. If no
  integer `k` satisfies `round(k/n, d) == reported_acc`, the value is
  arithmetically impossible and was likely fabricated or mis-reported.
  Decimal precision is auto-inferred from the Python float representation;
  override with `n_decimals`. Example: `grim_check(0.33, 10)` → FAIL
  (no integer k satisfies round(k/10, 2) == 0.33). Runs automatically
  inside `audit()` — only appended to findings on FAIL to keep OK output clean.
- `mm_grim_check` MCP tool exposing the GRIM probe to AI agents.
- 9 new tests for GRIM (total: 46 → 55, all passing).

### Changed
- Probe count: 12 → 13 (README/README_KO updated).
- `mm.py` docstring updated: "9 probes" → "10 probes".

---

## [0.3.0] — 2026-06-11

### Added
- **① Chain hash ledger** — `preregister()` now embeds `prev_seal` in every
  entry before computing the SHA-256 seal. The full ledger becomes a
  tamper-evident chain. `verify_chain(ledger_path)` walks all entries and
  checks both individual seals and chain links. Catches: entry deletion,
  insertion, and content modification. Backward-compatible: legacy entries
  without `prev_seal` skip the chain check gracefully.
- **⑧ `power_check(n, baseline, *, min_detectable_effect, alpha, target_power)`**
  — False-negative guard. Warns when `n` is too small to detect the minimum
  detectable effect at the specified power level (default 80%). Closes the
  gap between the "bidirectional" design principle and the actual
  implementation. Available standalone and via `full_audit(min_detectable_effect=...)`.
- **⑨ `multiple_comparisons_check(ledger_path, *, alpha)`** — Garden-of-forking-
  paths detector. Counts distinct `claim_id` values in the ledger and warns
  with the Bonferroni-corrected α when k>1. Re-registrations for the same
  `claim_id` count as k=1 (consistent with first-write-wins). Available
  standalone and via `full_audit(check_multiplicity=True)`.
- `full_audit()` gains two new optional parameters: `min_detectable_effect`
  (activates ⑧) and `check_multiplicity` (activates ⑨).
- Tests expanded from 28 → 46 (all passing).

### Changed
- Probe count: 9 → 12 (README/README_KO updated).
- Documented chain-hash limitation: complete ledger file replacement is not
  caught — git commit anchoring is the recommended complement.

---

## [0.2.0] — 2026-06-11

### Added
- **③ `gaming_check(metric, reward_terms)`** — Detects eval metric appearing
  directly in the training reward/loss (self-fulfilling artifact).
- **⑤ `multiseed_check(seed_results, *, baseline, cv_threshold)`** — Alarms on
  unstable cross-seed results or baseline falling within the seed range.
- **⑦ `too_good_check(name, claimed, baseline, *, suspicious_margin)`** —
  Flags suspiciously large improvements before they are believed.
- **`continuous_audit()`** — Audits non-binary metrics (MSE, Pearson r, RMSE…)
  using direction check + optional effect-size (z-score).
- **`full_audit()`** — Single call that runs all probes; optional probes
  activate when their args are provided.
- **MCP server** (`measure_mirror/mcp_server.py`, entry point `mm-mcp`) —
  All probes exposed as MCP tools for AI agent integration.
- **pytest plugin** (`measure_mirror/pytest_plugin.py`) — `assert_clean()`
  turns FAIL findings into CI failures.
- `pyproject.toml` v0.2.0 with `[mcp]` and `[test]` optional dependencies.
- `examples/quickstart.py` and `examples/mcp_example.py`.
- English-primary README with `README_KO.md` for Korean users.

### Fixed
- `_load_prereg()` now returns the **first** matching entry (was returning
  last). This is the correct behavior: first-write wins.
- `_verify_seal()` added to `audit()` — tamper detection was missing.
- `pass_threshold` check added to `audit()` — registered bar was not enforced.

---

## [0.1.0] — 2026-06-08 (initial public release)

### Added
- Core probe engine with zero dependencies (Python stdlib only).
- **① Pre-registration** — append-only JSONL ledger, SHA-256 seal, first-write
  wins, metric-swap detection, min_n enforcement.
- **② `baseline_fairness()`** — crippled / tied / reversed baseline detection.
- **④a `wilson_ci()`** — small-sample Wilson score confidence interval.
- **④a `leakage_check()`** — train∩test hash intersection.
- **④a direction** — anti-signal detection (worse than chance).
- **⑥ `scope_check()`** — over-generalization detection.
- **`audit()`** — binary/classification metric audit combining ①+④a.
- `report()` printer, `lookup_baseline()` DB helper.
- CLI entry point `mm` with `register` and `audit` subcommands.
- `db/baselines.json` shared baseline database (git-based, no server).
- Apache 2.0 license. Dog-fooded on ZERO and Field projects.
