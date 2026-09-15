"""Node identity: ed25519 keypairs, did:key ids, signing and verification.

Brief reference: section 9 (identity and signing). KNP-0 section 3.

A node is identified by `did:key:z6Mk...` over an ed25519 public key. No registry is needed
to verify a signature, which is what lets two nodes interact before they share a set.

The private key lives in `.kourob/keys/`, which is gitignored. Nothing in this module ever
returns or logs it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

__milestone__ = "M1"

#: Multicodec prefix for an ed25519 public key. did:key encodes this ahead of the raw key.
ED25519_MULTICODEC = b"\xed\x01"

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

KEY_DIR = ".kourob/keys"
PRIVATE_KEY_FILE = "node.ed25519"
PUBLIC_KEY_FILE = "node.pub"


def b58encode(data: bytes) -> str:
    """Bitcoin-alphabet base58, as did:key requires."""
    n = int.from_bytes(data, "big")
    out = ""
    while n:
        n, rem = divmod(n, 58)
        out = _B58_ALPHABET[rem] + out
    # Leading zero bytes are significant and encode as '1'.
    pad = len(data) - len(data.lstrip(b"\x00"))
    return "1" * pad + out


def b58decode(text: str) -> bytes:
    n = 0
    for char in text:
        idx = _B58_ALPHABET.find(char)
        if idx < 0:
            raise ValueError(f"not base58: {char!r}")
        n = n * 58 + idx
    pad = len(text) - len(text.lstrip("1"))
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\x00" * pad + body


def did_from_public_key(public_key: Ed25519PublicKey) -> str:
    """Render a did:key for an ed25519 public key."""
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    return "did:key:z" + b58encode(ED25519_MULTICODEC + raw)


def public_key_from_did(did: str) -> Ed25519PublicKey:
    """Recover the public key from a did:key. This is why no registry is needed."""
    if not did.startswith("did:key:z"):
        raise ValueError(f"not a did:key: {did!r}")
    decoded = b58decode(did.removeprefix("did:key:z"))
    if not decoded.startswith(ED25519_MULTICODEC):
        raise ValueError("did:key is not ed25519")
    return Ed25519PublicKey.from_public_bytes(decoded[len(ED25519_MULTICODEC) :])


def generate(node_dir: Path, *, overwrite: bool = False) -> str:
    """Create this node's keypair. Returns its did:key.

    Refuses to overwrite an existing key unless asked: a node that loses its key loses the
    ability to extend its own ledger, and every receipt it ever signed becomes
    unattributable.
    """
    key_dir = Path(node_dir) / KEY_DIR
    private_path = key_dir / PRIVATE_KEY_FILE
    if private_path.exists() and not overwrite:
        raise FileExistsError(
            f"{private_path} exists. A node's key is not regenerable: rotating it orphans "
            "every receipt it signed. Pass overwrite=True only if you mean it."
        )
    key_dir.mkdir(parents=True, exist_ok=True)

    private_key = Ed25519PrivateKey.generate()
    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    did = did_from_public_key(private_key.public_key())
    (key_dir / PUBLIC_KEY_FILE).write_text(did + "\n", encoding="utf-8")
    return did


def load_private_key(node_dir: Path) -> Ed25519PrivateKey:
    path = Path(node_dir) / KEY_DIR / PRIVATE_KEY_FILE
    if not path.exists():
        raise FileNotFoundError(f"no node key at {path}. Run `kourob keys init`.")
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError(f"{path} is not an ed25519 private key")
    return key


def load_did(node_dir: Path) -> str:
    """The node's public identity. Never touches the private key file."""
    path = Path(node_dir) / KEY_DIR / PUBLIC_KEY_FILE
    if not path.exists():
        raise FileNotFoundError(f"no node identity at {path}. Run `kourob keys init`.")
    return path.read_text(encoding="utf-8").strip()


def canonical(payload: dict[str, Any]) -> bytes:
    """JCS-style canonical JSON (RFC 8785, the subset we need).

    Sorted keys, no insignificant whitespace, UTF-8. Two implementations must agree
    byte-for-byte or every signature in the network is unverifiable.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def sign(private_key: Ed25519PrivateKey, payload: dict[str, Any]) -> str:
    """Sign the canonical form of `payload`. Returns base58."""
    return b58encode(private_key.sign(canonical(payload)))


def verify(did: str, payload: dict[str, Any], signature: str) -> bool:
    """Check a signature against the public key recovered from `did`."""
    try:
        public_key_from_did(did).verify(b58decode(signature), canonical(payload))
    except (InvalidSignature, ValueError):
        return False
    return True


__all__ = [
    "b58decode",
    "b58encode",
    "canonical",
    "did_from_public_key",
    "generate",
    "load_did",
    "load_private_key",
    "public_key_from_did",
    "sign",
    "verify",
]
