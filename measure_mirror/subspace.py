"""🪞 Measurement Mirror — subspace **executor** (layer B, optional module).

Install with the subspace extra:

    pip install "measure-mirror[subspace]"     # adds numpy

⚠️ **Scope of the zero-dependency claim.** *stdlib only* describes **layer A**
— `subspace_claim_check` in ``mm.py``, which audits a submitted table and never
touches numeric arrays. **This module is layer B and requires numpy.** The two
layers are advertised separately on purpose: folding an optional dependency
into a "zero deps" headline is the exact overgeneralisation
``catalog/self-catch/zero-dep-scope-overgeneralize.md`` records.

Layer A vs layer B, stated plainly
----------------------------------
==============  ==========================================  ===============
                layer A — ``mm.subspace_claim_check``       layer B — here
==============  ==========================================  ===============
sees            the submitted table only                    the arrays
deps            stdlib                                      numpy
can catch       declaration defects, internal inconsistency  what a table
                                                             cannot encode
cannot catch    a consistent forgery                        nothing it did
                                                             not itself run
audits          anyone's claim                              only your own run
==============  ==========================================  ===============

Layer B does **not** supersede layer A. It *produces* a table that layer A then
audits, so a layer-B run is checked by the same auditor a stranger's claim is.

What this module provides
-------------------------
``fit_basis``            estimate an ordered basis from perturbation samples
``energy_profile``       achieved energy fraction per component, in basis order
``k_for_energy``         minimal k whose cumulative energy meets a target
``build_subspace_report``  arrays + an effect callback → a layer-A report,
                           with ``effect_fn_sha256`` declared; with
                           ``certificate_tol=`` it also *computes* the
                           matched-null certificate the ``vacuous`` finding
                           consumes (certifying our own run — it cannot make
                           a stranger's certificate trustworthy)
``overfit_smallsample``  the layer-B judgment layer A is structurally unable to
                         make: run a synthetic zero-signal null and check that
                         the pipeline reports target ≈ null

Honest limits of this module
----------------------------
* ``fit_basis`` is deterministic given ``rng_seed``; it is *not* bit-stable
  across numpy/LAPACK versions. Declare the anchor you actually verified.
* ``build_subspace_report`` reports what it computed. It cannot certify the
  arrays you handed it are the arrays your claim is about.
* ``overfit_smallsample`` tests the pipeline on *synthetic* data. A pass says
  the instrument does not manufacture a win from noise on isotropic Gaussians;
  it says nothing about your substrate.
"""
from __future__ import annotations

import hashlib
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

try:                                            # pragma: no cover - trivial
    import numpy as np
except ImportError as exc:                      # pragma: no cover - trivial
    raise ImportError(
        "measure_mirror.subspace (layer B) requires numpy.\n"
        "    pip install \"measure-mirror[subspace]\"\n"
        "Layer A (measure_mirror.subspace_claim_check) has no such requirement "
        "— only layer B does."
    ) from exc

from . import mm
from .mm import Finding

__all__ = [
    "Basis", "fit_basis", "energy_profile", "cumulative_energy", "k_for_energy",
    "build_subspace_report", "overfit_smallsample", "BASIS_KINDS",
]

BASIS_KINDS = ("pca", "random", "shuffled", "given")


# ─────────────────────────────────────────────────────────────
# B1 — basis estimation primitives
# ─────────────────────────────────────────────────────────────
@dataclass
class Basis:
    """An ordered orthonormal basis of the ambient space.

    ``components`` is always (d, d) — a *complete* basis. When the fit sample
    has rank r < d the first r rows are the estimated directions and the
    remaining d-r are an arbitrary (deterministic) orthonormal complement.
    Completing the basis is not cosmetic: with n < d, k can legitimately exceed
    the rank, and truncating the basis at r would silently cap every energy
    target at whatever the sample happened to span.
    """
    components: Any                 # np.ndarray (d, d), rows orthonormal
    kind: str
    ambient_dim: int
    n_fit: int
    rank: int                       # rows that came from the data, not padding
    centered: bool
    meta: dict = field(default_factory=dict)

    def top(self, k: int):
        """The first k rows — the k-dimensional subspace."""
        if not (1 <= int(k) <= self.ambient_dim):
            raise ValueError(f"k must be in [1, {self.ambient_dim}], got {k!r}")
        return self.components[:int(k)]


def _rng(seed) -> Any:
    return np.random.default_rng(seed)


def _haar(d: int, rng) -> Any:
    """A Haar-distributed orthonormal basis, rows unsorted.

    Unsorted is the point. Sorting a random basis by achieved energy would make
    its cumulative energy an order statistic and break the ``energy/k ≈ 1/d``
    relation that layer A's C4 uses to recover the ambient dimension from the
    null arms alone.
    """
    q, r = np.linalg.qr(rng.standard_normal((d, d)))
    # Fix the sign convention so QR is a genuine Haar sample, not a biased one.
    q = q * np.sign(np.diag(r))
    return q.T


def _complete(comps: Any, d: int, rng) -> tuple[Any, int]:
    """Pad `comps` (r, d) up to a complete (d, d) orthonormal basis."""
    r = comps.shape[0]
    if r >= d:
        return comps[:d], d
    filler = rng.standard_normal((d - r, d))
    filler -= filler @ comps.T @ comps               # project out the span
    q, _ = np.linalg.qr(np.vstack([comps, filler]).T)
    out = np.vstack([comps, q.T[r:d]])
    return out, r


def _column_shuffle(X: Any, rng) -> Any:
    """Shuffle each column independently — same n, same d, same per-dimension
    marginals, cross-dimension covariance destroyed. That is the degrees-of-
    freedom control: a basis fitted here spends exactly as many parameters."""
    out = np.array(X, dtype=float, copy=True)
    for j in range(out.shape[1]):
        rng.shuffle(out[:, j])
    return out


def fit_basis(dX, *, kind: str = "pca", rng_seed: int = 0,
              center: bool = False, given=None) -> Basis:
    """Estimate an ordered basis from perturbation samples.

    Args:
      dX:     (n, d) array of perturbation samples.
      kind:   ``pca``      — right singular vectors, ordered by singular value.
              ``random``   — Haar orthonormal basis, deliberately unsorted.
              ``shuffled`` — PCA of a column-shuffled copy (dof control).
              ``given``    — use ``given`` (row-orthonormality is checked).
      center: subtract the sample mean before the SVD. Default False: dX is
              already a difference, and centering removes the mean shift, which
              in a perturbation study is often the very thing being claimed.
              It is a real choice, so it is recorded in ``Basis.centered``.
    """
    if kind not in BASIS_KINDS:
        raise ValueError(f"kind must be one of {BASIS_KINDS}, got {kind!r}")
    X = np.asarray(dX, dtype=float)
    if X.ndim != 2 or X.shape[0] < 1 or X.shape[1] < 1:
        raise ValueError(f"dX must be a non-empty 2-D array, got shape {X.shape}")
    n, d = X.shape
    rng = _rng(rng_seed)

    if kind == "given":
        comps = np.asarray(given, dtype=float)
        if comps.ndim != 2 or comps.shape[1] != d:
            raise ValueError(f"given basis must be (*, {d}), got {comps.shape}")
        gram = comps @ comps.T
        if not np.allclose(gram, np.eye(comps.shape[0]), atol=1e-8):
            raise ValueError("given basis rows are not orthonormal")
        comps, rank = _complete(comps, d, rng)
        return Basis(comps, kind, d, n, rank, False, {"rng_seed": rng_seed})

    if kind == "random":
        return Basis(_haar(d, rng), kind, d, n, d, False, {"rng_seed": rng_seed})

    src = _column_shuffle(X, rng) if kind == "shuffled" else X
    if center:
        src = src - src.mean(axis=0, keepdims=True)
    _, s, vt = np.linalg.svd(src, full_matrices=False)
    rank = int((s > s.max() * 1e-12).sum()) if s.size and s.max() > 0 else 0
    comps, _ = _complete(vt, d, rng)
    return Basis(comps, kind, d, n, min(rank, d), center,
                 {"rng_seed": rng_seed, "singular_values": s.tolist()})


def energy_profile(basis: Basis, A) -> Any:
    """Fraction of ``A``'s total energy carried by each component, in basis order.

    Returns a length-d vector summing to 1 (the basis is complete). Note this is
    the *achieved* energy on whatever array you pass — measuring it on the fit
    sample and on held-out data gives different numbers, and the gap between
    them is precisely what small-sample basis overfitting looks like.
    """
    M = np.asarray(A, dtype=float)
    if M.ndim != 2 or M.shape[1] != basis.ambient_dim:
        raise ValueError(f"A must be (*, {basis.ambient_dim}), got {M.shape}")
    total = float((M ** 2).sum())
    if total <= 0:
        raise ValueError("A carries zero energy — energy fractions are undefined")
    return ((M @ basis.components.T) ** 2).sum(axis=0) / total


def cumulative_energy(basis: Basis, A) -> Any:
    """Cumulative energy fraction, non-decreasing in k by construction (C2)."""
    return np.cumsum(energy_profile(basis, A))


def k_for_energy(cum, target: float) -> int:
    """Minimal k whose cumulative energy meets ``target`` (the minimal-k rule).

    Selecting k on the same array the energy is later reported on is what makes
    layer A's C3 (*achieved ≥ declared target*) hold by construction rather
    than by luck. Reporting an energy measured on a *different* array than the
    one k was chosen on can violate C3 on an entirely honest run — see
    ``build_subspace_report(energy_on=...)``.
    """
    c = np.asarray(cum, dtype=float)
    hit = np.nonzero(c >= float(target) - 1e-12)[0]
    return int(hit[0]) + 1 if hit.size else int(c.size)


# ─────────────────────────────────────────────────────────────
# B2 — arrays + effect callback → a layer-A report
# ─────────────────────────────────────────────────────────────
def _row_ids(A) -> list[str]:
    """Content-addressed row ids: sha256 of the row's exact float64 bytes.

    Deliberately *not* positional labels. ``basis_fit_ids ∩ effect_eval_ids``
    then tests whether the same samples were actually reused, which a caller
    cannot defeat by renaming its splits — and which layer A, seeing only the
    declared lists, has no way to compute for itself.
    """
    M = np.ascontiguousarray(np.asarray(A, dtype=float))
    return [hashlib.sha256(row.tobytes()).hexdigest()[:16] for row in M]


def _fn_fingerprint(fn: Callable, source: str | None) -> dict:
    """sha256 of the effect callback's source, or an explicit statement that it
    could not be read. Emitting a hash of something else (repr, qualname) would
    look like provenance while attesting to nothing."""
    if source is None:
        try:
            source = inspect.getsource(fn)
        except (OSError, TypeError) as exc:
            return {"effect_fn_sha256": None,
                    "effect_fn_sha256_unavailable":
                        f"{type(exc).__name__}: source not retrievable for "
                        f"{getattr(fn, '__qualname__', fn)!r} — pass "
                        f"effect_fn_source= to declare it explicitly"}
    return {"effect_fn_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "effect_fn_name": getattr(fn, "__qualname__", repr(fn))}


def build_subspace_report(data_by_seed: dict, *,
                          arms: dict,
                          effect_fn: Callable[[dict], float],
                          energy_targets: Sequence[float],
                          anchor: dict,
                          basis_split: str = "basis",
                          eval_split: str = "eval",
                          energy_on: str | None = None,
                          center: bool = False,
                          rng_seed: int = 0,
                          bar: float | None = None,
                          ambient_dim: int | None = None,
                          aux_by_seed: dict | None = None,
                          arm_effect: str = "mean",
                          certificate_tol: float | None = None,
                          effect_fn_source: str | None = None,
                          source: str = "",
                          extra: dict | None = None) -> dict:
    """Run the grid and emit a report in ``subspace_claim_check``'s schema.

    Args:
      data_by_seed: ``{seed: {split_name: (n, d) array}}``. Every seed must
                    carry at least ``basis_split`` and ``eval_split``; extra
                    splits (a probe-fitting sample, say) are projected and
                    handed to ``effect_fn`` untouched.
      arms:         ``{name: {"role": …, "basis": kind, "given": …?}}`` with
                    roles from layer A's vocabulary (target / null /
                    matched_null / dof_control / data_only).
      effect_fn:    called once per (arm, seed, energy target) with a ctx dict:
                    ``arm role seed grid_point k components proj data aux``.
                    ``proj[split]`` is the (m, k) coefficient array.
      energy_on:    which split the retained energy is measured on, and hence
                    which one k is selected against. Defaults to ``eval_split``
                    so that C3 holds by construction and the reported energy
                    describes the perturbation the effect was scored on. Set it
                    to ``basis_split`` to keep the eval array untouched by the
                    spectrum — at the cost that the reported energy is the
                    in-sample one, which small-sample overfitting inflates.
      arm_effect:   how per-seed arm effects are reduced across the grid
                    (``mean`` or ``max``). The paired sign-flip test in layer A
                    consumes these, so the reduction is declared in the report.
      certificate_tol: when set, every ``matched_null`` arm gets a **computed**
                    matching certificate embedded at ``report["certificate"]``
                    — the schema layer A's ``vacuous`` finding consumes. The
                    criterion is fixed, not caller-supplied: the energy the arm
                    retained **on the eval split** (the data the effect is
                    scored on) must meet the declared target within ``tol``,
                    for every cell. Measuring on the eval split is the point —
                    with ``energy_on=basis_split`` an arm can hit its target
                    in-sample while genuinely undershooting it on the data
                    that scored the effect, and *that* arm's low effect is
                    evidence of nothing (the vacuous illusion). ``None``
                    (default) emits no certificate, which layer A reports as
                    WARN — absence stays visible rather than passing silently.

    Returns the layer-A report dict, plus layer-B provenance keys
    (``layer``, ``effect_fn_sha256``, ``energy_measured_on``, ``basis_kinds``,
    ``numpy_version``). Layer A ignores keys it does not know.
    """
    if not data_by_seed:
        raise ValueError("data_by_seed is empty")
    if not arms:
        raise ValueError("arms is empty")
    if arm_effect not in ("mean", "max"):
        raise ValueError(f"arm_effect must be 'mean' or 'max', got {arm_effect!r}")
    targets = [float(t) for t in energy_targets]
    if not targets:
        raise ValueError("energy_targets is empty")
    energy_on = energy_on or eval_split

    seeds = sorted(data_by_seed)
    d_seen = {int(np.asarray(v, dtype=float).shape[1])
              for splits in data_by_seed.values() for v in splits.values()}
    if len(d_seen) != 1:
        raise ValueError(f"inconsistent ambient dimension across splits: {sorted(d_seen)}")
    d = d_seen.pop()
    if ambient_dim is not None and int(ambient_dim) != d:
        raise ValueError(f"ambient_dim={ambient_dim} but arrays are {d}-dimensional")

    cells: list[dict] = []
    per_arm_effects: dict[str, dict[int, list[float]]] = {a: {} for a in arms}
    fit_ids: set[str] = set()
    eval_ids: set[str] = set()
    cert_margins: dict[str, list[float]] = {}

    for seed in seeds:
        splits = data_by_seed[seed]
        for needed in (basis_split, eval_split, energy_on):
            if needed not in splits:
                raise KeyError(f"seed {seed!r} has no split {needed!r} "
                               f"(has {sorted(splits)})")
        arrays = {name: np.asarray(v, dtype=float) for name, v in splits.items()}
        fit_ids.update(_row_ids(arrays[basis_split]))
        eval_ids.update(_row_ids(arrays[eval_split]))

        for arm, spec in arms.items():
            role = spec.get("role")
            kind = spec.get("basis", "pca")
            # Distinct rng streams per (arm, seed) so the random and shuffled
            # arms are not accidentally the same draw for every arm.
            sub_seed = int(hashlib.sha256(
                f"{rng_seed}|{arm}|{seed}".encode()).hexdigest()[:8], 16)
            basis = fit_basis(arrays[basis_split], kind=kind, rng_seed=sub_seed,
                              center=center, given=spec.get("given"))
            cum = cumulative_energy(basis, arrays[energy_on])
            cum_eval = (cum if energy_on == eval_split
                        else cumulative_energy(basis, arrays[eval_split]))
            for tgt in targets:
                k = k_for_energy(cum, tgt)
                comps = basis.top(k)
                proj = {name: arr @ comps.T for name, arr in arrays.items()}
                eff = effect_fn({
                    "arm": arm, "role": role, "seed": seed, "grid_point": tgt,
                    "k": k, "components": comps, "basis": basis,
                    "proj": proj, "data": arrays,
                    "aux": (aux_by_seed or {}).get(seed),
                })
                eff = float(eff)
                cells.append({
                    "arm": arm, "role": role, "seed": int(seed),
                    "grid_point": tgt, "k": int(k),
                    "energy_kept": float(cum[k - 1]),
                    "energy_target": tgt, "effect": eff,
                    "n": int(arrays[eval_split].shape[0]),
                    # diagnostics, ignored by layer A: the same k measured on
                    # the other splits. The gap between them is small-sample
                    # basis overfitting, kept visible.
                    "energy_kept_on_basis_split":
                        float(cumulative_energy(basis, arrays[basis_split])[k - 1]),
                    "energy_kept_on_eval_split": float(cum_eval[k - 1]),
                })
                per_arm_effects[arm].setdefault(int(seed), []).append(eff)
                if role == "matched_null" and certificate_tol is not None:
                    cert_margins.setdefault(arm, []).append(
                        float(cum_eval[k - 1]) - tgt)

    reduce = (lambda v: sum(v) / len(v)) if arm_effect == "mean" else max
    arms_out = {
        arm: {"role": spec.get("role"),
              "basis": spec.get("basis", "pca"),
              "effect_by_seed": [reduce(per_arm_effects[arm][s])
                                 for s in sorted(per_arm_effects[arm])]}
        for arm, spec in arms.items()
    }

    report: dict = {
        "source": source or "measure_mirror.subspace.build_subspace_report",
        "layer": "B",
        "anchor": dict(anchor),
        "grid": {"kind": "energy", "targets": targets},
        "ambient_dim": d,
        "cells": cells,
        "arms": arms_out,
        "n_basis_fit": int(sum(
            np.asarray(data_by_seed[s][basis_split]).shape[0] for s in seeds)),
        "basis_fit_ids": sorted(fit_ids),
        "effect_eval_ids": sorted(eval_ids),
        "energy_measured_on": energy_on,
        "arm_effect_reduction": arm_effect,
        "basis_kinds": {a: s.get("basis", "pca") for a, s in arms.items()},
        "id_provenance": "sha256 of float64 row bytes (content-addressed, "
                         "not positional labels)",
        "numpy_version": np.__version__,
        **_fn_fingerprint(effect_fn, effect_fn_source),
    }
    if bar is not None:
        report["bar"] = float(bar)
    if certificate_tol is not None:
        cert = {}
        for arm, spec in arms.items():
            if spec.get("role") != "matched_null":
                continue
            margins = cert_margins.get(arm, [])
            cert[arm] = {
                # Computed from this run's own eval-split energies — NOT a
                # caller-declared verdict. An arm with no cells cannot certify.
                "passed": bool(margins) and min(margins) >= -float(certificate_tol),
                "min_margin": min(margins) if margins else None,
                "n_cells": len(margins),
                "tol": float(certificate_tol),
                "criterion": "energy retained on the eval split meets the "
                             "declared target within tol, for every cell",
                "measured_on": eval_split,
            }
        if cert:
            report["certificate"] = cert
    if extra:
        report.update(extra)
    return report


# ─────────────────────────────────────────────────────────────
# B3 — overfit_smallsample: the judgment layer A cannot make
# ─────────────────────────────────────────────────────────────
def _synth(rng, n: int, d: int, w, signal: float) -> tuple[Any, Any]:
    """Isotropic Gaussian perturbations, plus a planted direction at ``signal``.

    signal = 0 → dX is isotropic and y is independent of dX. There is nothing
    to find, and any arm that appears to find something is finding noise.
    signal > 0 → w is both a dominant direction of dX's covariance and the
    direction y depends on, which is what makes a *basis* estimated from dX
    able to recover it at all.
    """
    noise = rng.standard_normal((n, d))
    a = rng.standard_normal(n)
    dX = noise + signal * np.outer(a, w)
    y = signal * a + rng.standard_normal(n)
    return dX, y


def _r2_probe(ctx: dict) -> float:
    """Effect = out-of-sample R² of a linear probe on the retained coefficients.

    The probe is fitted on the ``probe`` split and scored on the ``eval`` split,
    both of which are held at a fixed large size. Only the *basis* sample size
    varies across the sweep, so probe-estimation variance cannot masquerade as
    a basis effect — the confound that would otherwise let the low-k arm win on
    degrees of freedom alone at a matched energy target.
    """
    Xp, Xe = ctx["proj"]["probe"], ctx["proj"]["eval"]
    yp, ye = ctx["aux"]["probe"], ctx["aux"]["eval"]
    Ap = np.hstack([Xp, np.ones((Xp.shape[0], 1))])
    coef, *_ = np.linalg.lstsq(Ap, yp, rcond=None)
    pred = np.hstack([Xe, np.ones((Xe.shape[0], 1))]) @ coef
    ss_res = float(((ye - pred) ** 2).sum())
    ss_tot = float(((ye - ye.mean()) ** 2).sum())
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0


_R2_PROBE_SOURCE = inspect.getsource(_r2_probe)

_ARMS = {
    "PCA":     {"role": "target",      "basis": "pca"},
    "RANDOM":  {"role": "null",        "basis": "random"},
    "SHUFFLE": {"role": "dof_control", "basis": "shuffled"},
}


def _one_condition(*, n_basis: int, signal: float, overlap: bool,
                   d: int, n_seeds: int, n_probe: int, n_eval: int,
                   energy_targets, rng_seed: int, alpha: float) -> dict:
    rng = _rng(rng_seed)
    w = rng.standard_normal(d)
    w /= np.linalg.norm(w)

    data, aux = {}, {}
    for s in range(n_seeds):
        srng = _rng((rng_seed, s, n_basis, int(signal * 1000), overlap))
        Xb, yb = _synth(srng, n_basis, d, w, signal)
        if overlap:
            # The basis is fitted on the very rows the effect is later scored
            # on — the defect `estimation-eval-overlap` exists to catch.
            data[s] = {"basis": Xb, "probe": Xb, "eval": Xb}
            aux[s] = {"probe": yb, "eval": yb}
        else:
            Xp, yp = _synth(srng, n_probe, d, w, signal)
            Xe, ye = _synth(srng, n_eval, d, w, signal)
            data[s] = {"basis": Xb, "probe": Xp, "eval": Xe}
            aux[s] = {"probe": yp, "eval": ye}

    anchor = {
        "code_path": "frozen",
        "tol": {"bit_repro": 0.0},
        "n_seeds": n_seeds,
        # Filled in by the caller after the re-run comparison actually happens.
        "guard_seeds": 0,
    }
    report = build_subspace_report(
        data, arms=_ARMS, effect_fn=_r2_probe, effect_fn_source=_R2_PROBE_SOURCE,
        energy_targets=energy_targets, anchor=anchor, aux_by_seed=aux,
        rng_seed=rng_seed, source=f"overfit_smallsample n_basis={n_basis} "
                                  f"signal={signal} overlap={overlap}")
    findings = mm.subspace_claim_check(report, alpha=alpha)
    levels = {f.probe: f.level for f in findings}
    ladder = next((f for f in findings if f.probe.endswith("null-ladder")), None)
    return {
        "n_basis": n_basis, "signal": signal, "overlap": overlap,
        "levels": levels,
        "ladder_level": ladder.level if ladder else None,
        "ladder_results": (ladder.data or {}).get("results") if ladder else None,
        "target_beats_null": bool(ladder is not None and ladder.level == "OK"),
        "arm_effects": {a: m["effect_by_seed"] for a, m in report["arms"].items()},
        "mean_k": {a: (sum(c["k"] for c in report["cells"] if c["arm"] == a)
                       / max(1, sum(1 for c in report["cells"] if c["arm"] == a)))
                   for a in _ARMS},
        "report": report,
    }


def overfit_smallsample(*, n_list: Sequence[int] = (20, 50, 200),
                        ambient_dim: int = 24,
                        n_seeds: int = 8,
                        n_probe: int = 2000,
                        n_eval: int = 2000,
                        energy_targets: Sequence[float] = (0.5, 0.7, 0.9),
                        positive_signal: float = 1.5,
                        rng_seed: int = 20260805,
                        alpha: float = 0.05,
                        keep_reports: bool = False) -> list[Finding]:
    """㉘ layer-B ``overfit_smallsample`` — does the pipeline invent a win?

    Layer A can only *lint* this (``underdetermined-basis`` fires when
    ``n_basis_fit < 3 × ambient_dim``); whether a basis fitted from that few
    samples actually aligned with noise is a property of the estimation run,
    which a table cannot encode. Layer B runs the estimation, so it can answer.

    Three conditions, on synthetic isotropic Gaussians:

      A. **null, disjoint** — signal 0, basis/probe/eval samples disjoint, at
         every ``n``. The target arm must NOT clear the null ladder.
      B. **null, overlapping** — signal 0, basis fitted on the rows the effect
         is scored on, at the *smallest* ``n`` (the worst case).
         ``estimation-eval-overlap`` must FAIL.
      C. **positive control, at every n** — ``positive_signal`` planted,
         disjoint. The target arm MUST clear the null ladder at each ``n``.

    C is not decoration, and it is run **per n** on purpose. A positive control
    at the largest ``n`` alone would leave the small-``n`` negative unreadable:
    "the target did not win at n=20" and "the instrument is blind at n=20" look
    identical from the outside, and reading the first without excluding the
    second is a vacuous negative — the failure mode this probe's own
    development hit three times (sealed ``98e993b2`` → ``3e6bd450`` →
    ``99a1a510``). Each ``n``'s null result is therefore reported only where
    that same ``n``'s positive control fired; the rest are withheld, not
    counted as passes.

    Returns Findings; ``data`` carries the per-condition table. Reports are
    dropped unless ``keep_reports=True`` (they are large).
    """
    ns = list(n_list)
    common = dict(d=ambient_dim, n_seeds=n_seeds, n_probe=n_probe,
                  n_eval=n_eval, energy_targets=energy_targets, alpha=alpha)
    null_runs = [_one_condition(n_basis=n, signal=0.0, overlap=False,
                                rng_seed=rng_seed + i, **common)
                 for i, n in enumerate(ns)]
    overlap_run = _one_condition(n_basis=min(ns), signal=0.0, overlap=True,
                                 rng_seed=rng_seed + 100, **common)
    pos_runs = [_one_condition(n_basis=n, signal=positive_signal, overlap=False,
                               rng_seed=rng_seed + 200 + i, **common)
                for i, n in enumerate(ns)]

    def _slim(r):
        out = {k: v for k, v in r.items() if k != "report"}
        if keep_reports:
            out["report"] = r["report"]
        return out

    table = {"null_disjoint": [_slim(r) for r in null_runs],
             "null_overlap": _slim(overlap_run),
             "positive_control": [_slim(r) for r in pos_runs]}

    out: list[Finding] = []

    # ── the discrimination gate, evaluated FIRST and per n ───────────────
    resolved = {n: r["target_beats_null"] for n, r in zip(ns, pos_runs)}
    blind = [n for n, ok in resolved.items() if not ok]
    overlap_caught = overlap_run["levels"].get(
        "㉘ estimation-eval-overlap") == "FAIL"
    if not blind and overlap_caught:
        out.append(Finding("㉘ overfit-smallsample-power", "OK",
            f"Instrument resolves at every sample size tested: with "
            f"signal={positive_signal} the target arm clears the null ladder at "
            f"n_basis ∈ {ns}, and the overlapping-sample condition is caught by "
            f"estimation-eval-overlap. The null results below are therefore "
            f"informative rather than vacuous.",
            data={"resolved_by_n": resolved, "overlap_caught": overlap_caught}))
    else:
        missing = ([] if not blind else
                   [f"positive control did not clear the null ladder at "
                    f"n_basis ∈ {blind}"]) + \
                  ([] if overlap_caught else
                   ["overlapping samples were not caught by "
                    "estimation-eval-overlap"])
        out.append(Finding("㉘ overfit-smallsample-power", "FAIL",
            "Instrument has no resolving power here (" + "; ".join(missing) +
            "). A check that returns the same verdict for a real signal and "
            "for noise is measuring nothing, so the null result at those "
            "sample sizes is vacuous and is withheld below rather than "
            "counted as a pass.",
            data={"resolved_by_n": resolved, "overlap_caught": overlap_caught,
                  "positive_control": [_slim(r) for r in pos_runs],
                  "null_overlap": _slim(overlap_run)}))

    # ── the null itself, read only where the instrument resolved ─────────
    readable = [r for r in null_runs if resolved.get(r["n_basis"])]
    withheld = [r["n_basis"] for r in null_runs if not resolved.get(r["n_basis"])]
    invented = [r for r in readable if r["target_beats_null"]]
    scope = (f"Scope: synthetic isotropic Gaussians in {ambient_dim} dimensions, "
             f"{n_seeds} seeds, effect = out-of-sample R² of a linear probe. "
             f"This says nothing about any real substrate.")
    if invented:
        out.append(Finding("㉘ overfit-smallsample", "FAIL",
            f"With signal 0 and disjoint samples, the target arm still cleared "
            f"the null ladder at n_basis ∈ "
            f"{[r['n_basis'] for r in invented]} (α={alpha}). The pipeline "
            f"manufactures a win from noise at that sample size: a basis "
            f"estimated from {min(r['n_basis'] for r in invented)} samples in "
            f"{ambient_dim} dimensions aligns with noise directions and the "
            f"effect follows it. " + scope,
            data={"table": table, "failing_n": [r["n_basis"] for r in invented],
                  "withheld_n": withheld}))
    elif not readable:
        out.append(Finding("㉘ overfit-smallsample", "WARN",
            f"No sample size could be read: the positive control failed at "
            f"every n_basis ∈ {ns}, so every null result is vacuous. " + scope,
            data={"table": table, "withheld_n": withheld}))
    else:
        msg = (f"With signal 0 and disjoint samples the target arm does not "
               f"clear the null ladder at n_basis ∈ "
               f"{[r['n_basis'] for r in readable]} — the pipeline does not "
               f"invent a subspace effect from noise there. ")
        if withheld:
            msg += (f"n_basis ∈ {withheld} is WITHHELD, not passed: the "
                    f"positive control did not fire there, so the null is "
                    f"unreadable. ")
        out.append(Finding("㉘ overfit-smallsample", "OK", msg + scope,
            data={"table": table, "readable_n": [r["n_basis"] for r in readable],
                  "withheld_n": withheld}))
    return out
