"""㉘ layer B — the subspace executor (`measure_mirror.subspace`).

Layer A audits a submitted table (stdlib, `tests/test_subspace_claim.py`).
Layer B produces one from arrays, and needs numpy. These tests check the three
things layer B can get wrong that layer A structurally cannot see:

  B1  the basis primitives (completeness, determinism, and the null arm's
      energy/k ≈ 1/d relation that layer A's C4 leans on)
  B2  the report builder — a layer-A-clean table, content-addressed ids, and an
      effect_fn fingerprint that is either real or openly absent
  B3  overfit_smallsample, including its own discrimination gate: the test
      suite deliberately makes the instrument inert and requires it to say so
"""
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy", reason="layer B requires the subspace extra")

from measure_mirror import subspace_claim_check
from measure_mirror.subspace import (
    Basis, build_subspace_report, cumulative_energy, energy_profile, fit_basis,
    k_for_energy, overfit_smallsample,
)

D = 24
REPO = Path(__file__).resolve().parents[1]


def _lvl(findings, suffix):
    hits = [f for f in findings if f.probe.endswith(suffix)]
    assert len(hits) <= 1, f"{suffix}: expected ≤1 finding, got {len(hits)}"
    return hits[0].level if hits else None


def _data(rng, n, d=D):
    return rng.standard_normal((n, d))


# ─────────────────────────────────────────────────────────────
# B1 — basis primitives
# ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("kind", ["pca", "random", "shuffled"])
def test_b1_basis_is_complete_and_orthonormal(kind):
    X = _data(np.random.default_rng(0), 200)
    b = fit_basis(X, kind=kind, rng_seed=7)
    assert isinstance(b, Basis)
    assert b.components.shape == (D, D)
    assert np.allclose(b.components @ b.components.T, np.eye(D), atol=1e-8)
    assert b.ambient_dim == D


def test_b1_rank_deficient_sample_is_padded_not_truncated():
    """n < d must still yield a full basis: with 20 samples in 24 dimensions the
    data spans only 20 directions, and truncating there would silently cap
    every energy target at whatever the sample happened to reach."""
    X = _data(np.random.default_rng(1), 20)
    b = fit_basis(X, kind="pca", rng_seed=7)
    assert b.rank == 20 and b.components.shape == (D, D)
    assert np.allclose(b.components @ b.components.T, np.eye(D), atol=1e-8)


def test_b1_deterministic_given_rng_seed():
    X = _data(np.random.default_rng(2), 50)
    a = fit_basis(X, kind="random", rng_seed=11).components
    c = fit_basis(X, kind="random", rng_seed=11).components
    e = fit_basis(X, kind="random", rng_seed=12).components
    assert np.array_equal(a, c)
    assert not np.array_equal(a, e)


def test_b1_energy_profile_sums_to_one_and_cumulative_is_monotone():
    """C2 (k up ⇒ energy non-decreasing) holds by construction, not by luck."""
    rng = np.random.default_rng(3)
    X, A = _data(rng, 100), _data(rng, 100)
    b = fit_basis(X, kind="pca", rng_seed=7)
    prof = energy_profile(b, A)
    assert prof.shape == (D,)
    assert prof.min() >= 0.0
    assert abs(float(prof.sum()) - 1.0) < 1e-9
    cum = cumulative_energy(b, A)
    assert np.all(np.diff(cum) >= -1e-12)


def test_b1_random_basis_reproduces_the_c4_relation():
    """A null arm keeps ≈ k/d of the energy — the relation layer A's C4 uses to
    recover the ambient dimension from the null arms alone. If a random basis
    here were sorted by achieved energy this would break, and C4 would start
    reporting a wrong dimension on honest layer-B output."""
    rng = np.random.default_rng(4)
    X = _data(rng, 500)
    b = fit_basis(X, kind="random", rng_seed=5)
    cum = cumulative_energy(b, X)
    for k in (4, 8, 16):
        assert abs(k / float(cum[k - 1]) - D) / D < 0.15


def test_b1_pca_concentrates_more_than_random_on_its_own_fit_sample():
    rng = np.random.default_rng(5)
    X = _data(rng, 200)
    cp = cumulative_energy(fit_basis(X, kind="pca", rng_seed=5), X)
    cr = cumulative_energy(fit_basis(X, kind="random", rng_seed=5), X)
    assert float(cp[4]) > float(cr[4])


def test_b1_k_for_energy_is_the_minimal_k():
    cum = np.array([0.3, 0.55, 0.72, 0.9, 1.0])
    assert k_for_energy(cum, 0.5) == 2
    assert k_for_energy(cum, 0.55) == 2          # boundary counts as reached
    assert k_for_energy(cum, 0.9) == 4
    assert k_for_energy(cum, 1.5) == 5           # unreachable → full basis


def test_b1_rejects_bad_input():
    b = fit_basis(_data(np.random.default_rng(6), 30), rng_seed=0)
    with pytest.raises(ValueError):
        fit_basis(np.zeros((0, D)))
    with pytest.raises(ValueError):
        fit_basis(_data(np.random.default_rng(6), 30), kind="nope")
    with pytest.raises(ValueError):
        b.top(0)
    with pytest.raises(ValueError):
        b.top(D + 1)
    with pytest.raises(ValueError):
        energy_profile(b, np.zeros((10, D)))     # zero energy is undefined
    with pytest.raises(ValueError):
        fit_basis(_data(np.random.default_rng(6), 30), kind="given",
                  given=np.ones((2, D)))         # not orthonormal


# ─────────────────────────────────────────────────────────────
# B2 — the report builder
# ─────────────────────────────────────────────────────────────
ARMS = {"PCA": {"role": "target", "basis": "pca"},
        "RANDOM": {"role": "null", "basis": "random"},
        "SHUFFLE": {"role": "dof_control", "basis": "shuffled"}}
ANCHOR = {"code_path": "frozen", "tol": {"bit_repro": 0.0},
          "n_seeds": 4, "guard_seeds": 2}


def _effect(ctx):
    """Toy effect: the retained fraction of the eval array's energy."""
    return float((ctx["proj"]["eval"] ** 2).sum() / (ctx["data"]["eval"] ** 2).sum())


def _dataset(*, seeds=(0, 1, 2, 3), overlap=False, n_basis=60, n_eval=120):
    out = {}
    for s in seeds:
        rng = np.random.default_rng(100 + s)
        basis = _data(rng, n_basis)
        out[s] = {"basis": basis,
                  "eval": basis if overlap else _data(rng, n_eval)}
    return out


_UNSET = object()


def _build(**kw):
    kw.setdefault("arms", ARMS)
    kw.setdefault("effect_fn", _effect)
    kw.setdefault("energy_targets", (0.5, 0.7, 0.9))
    kw.setdefault("anchor", ANCHOR)
    data = kw.pop("data", _UNSET)
    return build_subspace_report(_dataset() if data is _UNSET else data, **kw)


def test_b2_report_passes_layer_a_with_no_schema_or_consistency_defect():
    findings = subspace_claim_check(_build())
    assert _lvl(findings, "schema") is None
    assert _lvl(findings, "no-anchor") == "OK"
    assert _lvl(findings, "energy-not-matched") == "OK"
    assert _lvl(findings, "dof-uncontrolled") == "OK"
    assert _lvl(findings, "estimation-eval-overlap") == "OK"
    for law in ("consistency-C1", "consistency-C2", "consistency-C3"):
        assert _lvl(findings, law) is None, f"{law} violated on honest output"
    assert _lvl(findings, "consistency-C4") == "OK"


def test_b2_c3_holds_by_construction_when_energy_is_read_where_k_was_chosen():
    """Achieved ≥ declared target for every cell — the minimal-k rule."""
    rep = _build()
    assert rep["energy_measured_on"] == "eval"
    for c in rep["cells"]:
        assert c["energy_kept"] >= c["energy_target"] - 1e-12


def test_b2_content_ids_detect_real_reuse_that_a_label_would_hide():
    """The overlap test is content-addressed, so it cannot be defeated by
    calling the same rows a different split name."""
    clean = _build()
    assert not (set(clean["basis_fit_ids"]) & set(clean["effect_eval_ids"]))
    assert _lvl(subspace_claim_check(clean), "estimation-eval-overlap") == "OK"

    reused = _build(data=_dataset(overlap=True))
    assert set(reused["basis_fit_ids"]) == set(reused["effect_eval_ids"])
    assert _lvl(subspace_claim_check(reused), "estimation-eval-overlap") == "FAIL"


def test_b2_effect_fn_fingerprint_is_the_real_source_hash():
    import inspect
    rep = _build()
    assert rep["effect_fn_sha256"] == hashlib.sha256(
        inspect.getsource(_effect).encode()).hexdigest()
    assert "effect_fn_sha256_unavailable" not in rep


def test_b2_unreadable_effect_source_is_declared_absent_not_faked():
    """A hash of the repr would look like provenance while attesting to
    nothing, so the field goes to None with a stated reason instead."""
    fn = eval("lambda ctx: 0.5")          # no retrievable source
    rep = _build(effect_fn=fn)
    assert rep["effect_fn_sha256"] is None
    assert "source not retrievable" in rep["effect_fn_sha256_unavailable"]

    declared = _build(effect_fn=fn, effect_fn_source="lambda ctx: 0.5")
    assert declared["effect_fn_sha256"] == hashlib.sha256(
        b"lambda ctx: 0.5").hexdigest()


def test_b2_declares_layer_b_provenance():
    rep = _build()
    assert rep["layer"] == "B"
    assert rep["grid"] == {"kind": "energy", "targets": [0.5, 0.7, 0.9]}
    assert rep["ambient_dim"] == D
    assert rep["arm_effect_reduction"] == "mean"
    assert rep["basis_kinds"] == {"PCA": "pca", "RANDOM": "random",
                                  "SHUFFLE": "shuffled"}
    assert rep["numpy_version"] == np.__version__
    assert len(rep["cells"]) == len(ARMS) * 4 * 3
    for meta in rep["arms"].values():
        assert len(meta["effect_by_seed"]) == 4


def test_b2_energy_on_basis_split_reveals_the_overfitting_gap():
    """Reading the energy on the fit sample instead of the eval sample inflates
    it — that gap IS small-sample overfitting, so it is carried in the cell
    rather than averaged away."""
    rep = _build(data=_dataset(n_basis=20), energy_on="basis")
    assert rep["energy_measured_on"] == "basis"
    pca = [c for c in rep["cells"] if c["arm"] == "PCA"]
    assert all(c["energy_kept"] >= c["energy_kept_on_basis_split"] - 1e-12
               for c in pca)
    # the fit-sample basis is optimistic: fewer components claim the target
    ks = {c["grid_point"]: c["k"] for c in pca}
    eval_ks = {c["grid_point"]: c["k"]
               for c in _build(data=_dataset(n_basis=20))["cells"]
               if c["arm"] == "PCA"}
    assert ks[0.9] < eval_ks[0.9]


def test_b2_rejects_malformed_calls():
    with pytest.raises(ValueError):
        _build(data={})
    with pytest.raises(ValueError):
        _build(arms={})
    with pytest.raises(ValueError):
        _build(energy_targets=())
    with pytest.raises(ValueError):
        _build(arm_effect="median")
    with pytest.raises(ValueError):
        _build(ambient_dim=D + 1)
    with pytest.raises(KeyError):
        _build(basis_split="nope")


# ─────────────────────────────────────────────────────────────
# B3 — overfit_smallsample, and its own discrimination gate
# ─────────────────────────────────────────────────────────────
# Only the swept axis (n_basis) is trimmed. n_probe / n_eval keep their
# defaults deliberately: layer A's paired sign-flip enumerates exactly at these
# seed counts, so the positive control needs every seed's Δ to be stable. At
# n_probe=400 one seed's Δ landed at -0.001 and the control correctly declared
# itself blind — an underpowered control, not a lower bar to be tuned away.
FAST = dict(n_list=(20, 200))


def test_b3_reports_no_invented_effect_and_says_why_that_is_readable():
    findings = overfit_smallsample(**FAST)
    assert _lvl(findings, "overfit-smallsample-power") == "OK"
    assert _lvl(findings, "overfit-smallsample") == "OK"
    main = next(f for f in findings if f.probe.endswith("overfit-smallsample"))
    assert main.data["readable_n"] == [20, 200]
    assert main.data["withheld_n"] == []
    for run in main.data["table"]["null_disjoint"]:
        assert run["target_beats_null"] is False


def test_b3_positive_control_runs_at_every_n_not_only_the_largest():
    """A positive control only at the largest n would leave the small-n
    negative unreadable: 'did not win at n=20' and 'blind at n=20' look
    identical from outside."""
    findings = overfit_smallsample(**FAST)
    power = next(f for f in findings if f.probe.endswith("-power"))
    assert power.data["resolved_by_n"] == {20: True, 200: True}
    main = next(f for f in findings if f.probe.endswith("overfit-smallsample"))
    assert [r["n_basis"] for r in main.data["table"]["positive_control"]] == [20, 200]
    assert all(r["target_beats_null"] for r in main.data["table"]["positive_control"])


def test_b3_overlapping_samples_are_caught_by_layer_a():
    findings = overfit_smallsample(**FAST)
    main = next(f for f in findings if f.probe.endswith("overfit-smallsample"))
    ov = main.data["table"]["null_overlap"]
    assert ov["levels"]["㉘ estimation-eval-overlap"] == "FAIL"


def test_b3_inert_instrument_is_reported_vacuous_not_passed():
    """The load-bearing self-check. Removing the signal from the positive
    control makes the instrument unable to tell signal from noise; the null
    result is then meaningless. A check that returns OK here is a constant
    check, which is exactly how this probe's layer-A gate failed twice
    (sealed 98e993b2, 3e6bd450) before it was rebuilt."""
    findings = overfit_smallsample(positive_signal=0.0, **FAST)
    assert _lvl(findings, "overfit-smallsample-power") == "FAIL"
    assert _lvl(findings, "overfit-smallsample") == "WARN"
    main = next(f for f in findings if f.probe.endswith("overfit-smallsample"))
    assert main.data["withheld_n"] == [20, 200]
    assert "vacuous" in main.msg


def test_b3_is_deterministic_given_rng_seed():
    a = overfit_smallsample(rng_seed=4242, **FAST)
    b = overfit_smallsample(rng_seed=4242, **FAST)
    assert [(f.probe, f.level) for f in a] == [(f.probe, f.level) for f in b]
    ea = next(f for f in a if f.probe.endswith("overfit-smallsample"))
    eb = next(f for f in b if f.probe.endswith("overfit-smallsample"))
    assert (ea.data["table"]["null_disjoint"][0]["arm_effects"] ==
            eb.data["table"]["null_disjoint"][0]["arm_effects"])


# ─────────────────────────────────────────────────────────────
# 🦋 the scope of the zero-dependency claim
# ─────────────────────────────────────────────────────────────
def test_core_import_does_not_pull_in_numpy():
    """`stdlib only` must stay true of the core after layer B was added — so
    the core must not import the layer-B module. Checked in a subprocess with
    numpy blocked, because numpy is already imported in this one."""
    code = (
        "import sys\n"
        "class Block:\n"
        "    def find_module(self, name, path=None):\n"
        "        if name == 'numpy' or name.startswith('numpy.'):\n"
        "            raise ImportError('numpy blocked for this test')\n"
        "sys.meta_path.insert(0, Block())\n"
        "import measure_mirror\n"
        "assert 'numpy' not in sys.modules\n"
        "measure_mirror.subspace_claim_check({})\n"
        "print('OK')\n"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=REPO,
                       capture_output=True, text=True)
    assert r.returncode == 0 and "OK" in r.stdout, r.stderr


def test_advertising_states_the_scope_of_the_stdlib_claim():
    """Regression guard for catalog/self-catch/zero-dep-scope-overgeneralize.md
    — the entry that records this README overclaiming its own dependencies."""
    readme = (REPO / "README.md").read_text()
    assert 'pip install -e ".[subspace]"' in readme
    assert "Stdlib-only describes the core and every layer-A auditor" in readme
    assert "zero-dep-scope-overgeneralize" in readme
    assert "Zero-dep core" not in readme

    # Both READMEs, not just the English one. The KO file carried a *stronger*
    # version of the same overclaim ("외부 의존성 없음", judge not even named)
    # while the EN one was being corrected — a one-sided guard is how that
    # drift survives.
    ko = (REPO / "README_KO.md").read_text()
    assert 'pip install -e ".[subspace]"' in ko
    assert "stdlib 전용인 것은 코어와 A층" in ko
    assert "zero-dep-scope-overgeneralize" in ko
    assert "- **외부 의존성 없음**" not in ko

    init = (REPO / "measure_mirror" / "__init__.py").read_text()
    assert "의존성0인 것은 이 코어와 A층 감사기들뿐이다" in init

    pyproject = (REPO / "pyproject.toml").read_text()
    assert 'subspace = ["numpy>=1.21"]' in pyproject

    doc = (REPO / "measure_mirror" / "subspace.py").read_text()
    assert "This module is layer B and requires numpy" in doc
