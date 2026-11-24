"""MIRROR-SPEC v1 conformance: vectors, reference verifier, and package agreement.

Guards spec/vectors/ + spec/reference_verifier.py against regression, and
checks that the package's canonical linkage_check reproduces every expected
L1 verdict — i.e. that the reference implementation conforms to its own spec.
"""
import json
import subprocess
import sys
from pathlib import Path

from measure_mirror.mm import linkage_check

ROOT = Path(__file__).resolve().parent.parent
VECTORS = ROOT / "spec" / "vectors"
VERIFIER = ROOT / "spec" / "reference_verifier.py"


def _expected():
    with open(VECTORS / "expected.json", encoding="utf-8") as f:
        return json.load(f)


def test_reference_verifier_all_vectors_match():
    """The zero-dep reference verifier reproduces every expected verdict."""
    result = subprocess.run(
        [sys.executable, str(VERIFIER), "--vectors", str(VECTORS)],
        capture_output=True, encoding="utf-8",
    )
    assert result.returncode == 0, (
        f"conformance mismatches:\n{result.stdout}\n{result.stderr}"
    )
    assert "ALL VECTORS MATCH" in result.stdout


def test_package_linkage_check_matches_expected_l1():
    """mm.linkage_check (canonical L1) agrees with every expected L1 verdict."""
    for name, exp in _expected().items():
        want = exp.get("L1")
        if want is None:
            continue
        ok, msg, _ = linkage_check(str(VECTORS / name))
        got = "OK" if ok else "FAIL"
        assert got == want, f"{name}: expected L1={want}, got {got} ({msg})"


def test_uppercase_genesis_vector_present():
    """valid_02 pins SPEC §5.1 (case-insensitive genesis) — the rule that
    reconciles the mm ('genesis') / am ('GENESIS') producer split found in
    9 real family ledgers. See spec/vectors/README.md."""
    first = json.loads(
        (VECTORS / "valid_02_legacy.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert first["prev_seal"] == "GENESIS"
    ok, msg, _ = linkage_check(str(VECTORS / "valid_02_legacy.jsonl"))
    assert ok, msg


def test_verify_chain_accepts_uppercase_genesis():
    """verify_chain (L1+) must also honor SPEC §5.1 — regression guard for the
    case-sensitivity bug caught by the first conformance run (false-FAIL on
    am-produced ledgers starting with "GENESIS")."""
    from measure_mirror.mm import verify_chain

    findings = verify_chain(str(VECTORS / "valid_02_legacy.jsonl"))
    assert all(f.level != "FAIL" for f in findings), findings
