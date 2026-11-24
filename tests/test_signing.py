"""Signed seals: who sealed a preregistration (SPEC §4 rule 4).

Signing is optional. Without it a ledger line is byte-for-byte what it was before; with it
the entry carries `pubkey` (sealed) and `sig` (not sealed, over the stored seal string).
"""
import json
import os
import subprocess
import sys

import pytest

pytest.importorskip("cryptography")

from measure_mirror import identity, mm  # noqa: E402

CLI = "import sys; from measure_mirror.mm import _cli; sys.argv[0] = 'mm'; _cli()"
REF = os.path.join(os.path.dirname(__file__), os.pardir, "spec", "reference_verifier.py")


def _cli(cwd, *args, env=None):
    e = dict(os.environ)
    e.pop("MM_SIGN_KEY", None)
    e.pop("MM_SIGNER", None)
    e.update(env or {})
    return subprocess.run([sys.executable, "-c", CLI, *args], cwd=cwd, env=e,
                          capture_output=True, encoding="utf-8")


def _reg(ledger, cid, **kw):
    return mm.preregister(str(ledger), cid, metric="acc", min_n=200, baseline=0.5,
                          pass_threshold=0.6, **kw)


def _lines(ledger):
    return [json.loads(l) for l in open(ledger, encoding="utf-8") if l.strip()]


def _rewrite(ledger, entries):
    with open(ledger, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


@pytest.fixture
def keys(tmp_path):
    a, b = tmp_path / "alice.key", tmp_path / "mallory.key"
    return {"alice": (str(a), identity.generate(str(a))),
            "mallory": (str(b), identity.generate(str(b)))}


def _trusted(tmp_path, text):
    p = tmp_path / "trusted.txt"
    p.write_text(text, encoding="utf-8")
    return mm.load_trusted_keys(str(p))


def test_unsigned_entries_unchanged(tmp_path):
    led = tmp_path / "l.jsonl"
    e = _reg(led, "c1")
    assert "pubkey" not in e and "sig" not in e and "signer" not in e
    assert mm.verify_chain(str(led))[0].level == "OK"
    assert mm.verify_signatures(str(led))[0].level == "OK"


def test_signed_entry_verifies_and_chain_stays_intact(tmp_path, keys):
    led = tmp_path / "l.jsonl"
    key, pub = keys["alice"]
    _reg(led, "c0")                                   # older unsigned entry
    e = _reg(led, "c1", sign_key=key, signer="alice")
    mm.retract(str(led), "c0", "typo", sign_key=key, signer="alice")
    assert e["pubkey"] == pub and e["signer"] == "alice"
    assert identity.verify(pub, e["seal"], e["sig"])
    assert mm.verify_chain(str(led))[0].level == "OK"
    f = mm.verify_signatures(str(led))[0]
    assert f.level == "OK" and "NOT pinned" in f.msg
    t = mm.verify_signatures(str(led), _trusted(tmp_path, f"alice {pub}\n"))[0]
    assert t.level == "OK" and "trusted keys" in t.msg


def test_signed_ledger_passes_spec_reference_verifier(tmp_path, keys):
    led = tmp_path / "l.jsonl"
    _reg(led, "c1", sign_key=keys["alice"][0], signer="alice")
    _reg(led, "c2", sign_key=keys["alice"][0], signer="alice")
    r = subprocess.run([sys.executable, REF, str(led)], capture_output=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr


def test_tampered_content_fails_signature(tmp_path, keys):
    led = tmp_path / "l.jsonl"
    _reg(led, "c1", sign_key=keys["alice"][0], signer="alice")
    es = _lines(led)
    es[0]["pass_threshold"] = 0.5
    _rewrite(led, es)
    assert mm.verify_signatures(str(led))[0].level == "FAIL"


def test_resigned_rewrite_caught_only_with_trusted_keys(tmp_path, keys):
    """The attack the trusted-keys file exists for: rewrite, re-seal, re-sign with a new key."""
    led = tmp_path / "l.jsonl"
    _reg(led, "c1", sign_key=keys["alice"][0], signer="alice")
    forged = tmp_path / "forged.jsonl"
    e = _lines(led)[0]
    for k in ("seal", "sig", "pubkey", "prev_seal", "signer"):
        e.pop(k, None)
    e["pass_threshold"] = 0.5
    mm._append_sealed(str(forged), e, sign_key=keys["mallory"][0], signer="alice")
    assert mm.verify_chain(str(forged))[0].level == "OK"
    assert mm.verify_signatures(str(forged))[0].level == "OK"          # self-consistent only
    trusted = _trusted(tmp_path, f"alice {keys['alice'][1]}\n")
    f = mm.verify_signatures(str(forged), trusted)[0]
    assert f.level == "FAIL" and "not trusted" in f.msg


def test_stripped_signature_caught_with_trusted_keys(tmp_path, keys):
    led = tmp_path / "l.jsonl"
    _reg(led, "c1", signer="alice")                    # labelled alice but unsigned
    trusted = _trusted(tmp_path, f"alice {keys['alice'][1]}\n")
    f = mm.verify_signatures(str(led), trusted)[0]
    assert f.level == "FAIL" and "unsigned although" in f.msg


def test_require_signed(tmp_path, keys):
    led = tmp_path / "l.jsonl"
    _reg(led, "c0")
    _reg(led, "c1", sign_key=keys["alice"][0])
    fs = mm.verify_signatures(str(led), require_signed=True)
    assert fs[0].level == "FAIL" and "[1]" in fs[0].msg


def test_wildcard_trusted_key(tmp_path, keys):
    led = tmp_path / "l.jsonl"
    _reg(led, "c1", sign_key=keys["alice"][0])         # no signer label
    ok = mm.verify_signatures(str(led), _trusted(tmp_path, f"* {keys['alice'][1]}\n"))
    assert ok[0].level == "OK"
    bad = mm.verify_signatures(str(led), _trusted(tmp_path, f"alice {keys['alice'][1]}\n"))
    assert bad[0].level == "FAIL"


def test_bad_trusted_keys_file(tmp_path):
    with pytest.raises(ValueError):
        _trusted(tmp_path, "alice nothex\n")
    with pytest.raises(ValueError):
        _trusted(tmp_path, "just-one-column\n")


def test_signer_label_rejected_before_writing(tmp_path):
    led = tmp_path / "l.jsonl"
    with pytest.raises(ValueError):
        _reg(led, "c1", signer="two words")
    assert not led.exists()


def test_missing_key_file_writes_nothing(tmp_path):
    led = tmp_path / "l.jsonl"
    with pytest.raises(OSError):
        _reg(led, "c1", sign_key=str(tmp_path / "nope.key"))
    assert not led.exists()


def test_verify_seal_ignores_sig_per_spec(tmp_path, keys):
    """SPEC §4 rule 1 — `sig` is outside the sealed body (verify_chain used to include it)."""
    led = tmp_path / "l.jsonl"
    _reg(led, "c1", sign_key=keys["alice"][0])
    assert mm._verify_seal(_lines(led)[0])


def test_cli_keygen_register_verify_sig(tmp_path):
    r = _cli(tmp_path, "keygen", "me.key")
    assert r.returncode == 0, r.stderr
    pub = [l.split()[-1] for l in r.stdout.splitlines() if "Public key" in l][0]
    assert _cli(tmp_path, "keygen", "me.key").returncode == 2        # never overwrites
    r = _cli(tmp_path, "--new-ledger", "register", "c1", "--metric", "acc",
             "--sign-key", "me.key", "--signer", "alice")
    assert r.returncode == 0 and "Signed by key" in r.stdout, r.stdout + r.stderr
    (tmp_path / "trusted.txt").write_text(f"alice {pub}\n")
    ok = _cli(tmp_path, "verify-sig", "--trusted-keys", "trusted.txt", "--require-signed")
    assert ok.returncode == 0, ok.stdout
    (tmp_path / "other.txt").write_text(f"alice {'00' * 32}\n")
    bad = _cli(tmp_path, "verify-sig", "--trusted-keys", "other.txt")
    assert bad.returncode == 1 and "FAIL" in bad.stdout


def test_cli_signs_from_environment(tmp_path):
    assert _cli(tmp_path, "keygen", "ci.key").returncode == 0
    r = _cli(tmp_path, "--new-ledger", "register", "c1", "--metric", "acc",
             env={"MM_SIGN_KEY": "ci.key", "MM_SIGNER": "ci"})
    assert r.returncode == 0, r.stderr
    e = _lines(tmp_path / "mm_ledger.jsonl")[0]
    assert e["signer"] == "ci" and e["sig"]
