"""🪪 Optional Ed25519 identity for measure-mirror seals (SPEC §4 rule 4).

The core ledger is stdlib-only and records nobody: a sealed preregistration says WHAT was
fixed and WHEN it was chained, not WHO fixed it. This module lets the sealer sign each seal
with a private key, so anyone holding the matching public key can check who sealed it.
Same key format and signing rule as action-mirror's identity module. Optional — `pip install measure-mirror[signing]`.

Honest scope (do not oversell): a signature proves "the holder of THIS key signed it"
(attribution · impersonation-resistance · non-repudiation). It does NOT prove independence — one
operator can mint many keys (Sybil). And if the agent holds its own key it can use a different
one; the strongest form needs the harness to attest identity. Keys make *same-identity* provable;
they do not make distinct keys *independent*.
"""
from __future__ import annotations

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey, Ed25519PublicKey)
    from cryptography.exceptions import InvalidSignature
    _OK = True
except Exception:  # pragma: no cover - exercised only without the extra
    _OK = False


def available() -> bool:
    """True if the [signing] extra (cryptography) is installed."""
    return _OK


def _require():
    if not _OK:
        raise RuntimeError(
            "signing requires the optional dependency: pip install measure-mirror[signing]")


def generate(path: str) -> str:
    """Create an Ed25519 keypair, write the private key (raw hex) to `path`, return public hex."""
    _require()
    import os
    priv = Ed25519PrivateKey.generate()
    raw = priv.private_bytes_raw()
    with open(path, "w", encoding="utf-8") as f:
        f.write(raw.hex())
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return public_hex(path)


def public_hex(path: str) -> str:
    """Public key hex for the private key stored at `path`."""
    _require()
    raw = bytes.fromhex(open(path, encoding="utf-8").read().strip())
    priv = Ed25519PrivateKey.from_private_bytes(raw)
    return priv.public_key().public_bytes_raw().hex()


def sign(path: str, message: str) -> str:
    """Sign `message` (the entry seal) with the private key at `path`. Returns signature hex."""
    _require()
    raw = bytes.fromhex(open(path, encoding="utf-8").read().strip())
    priv = Ed25519PrivateKey.from_private_bytes(raw)
    return priv.sign(message.encode()).hex()


def verify(pubkey_hex: str, message: str, sig_hex: str) -> bool:
    """Verify that `sig_hex` is a valid signature of `message` under `pubkey_hex`."""
    if not _OK:
        return False
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pubkey_hex))
        pub.verify(bytes.fromhex(sig_hex), message.encode())
        return True
    except (InvalidSignature, ValueError):
        return False
