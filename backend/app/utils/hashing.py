"""Hashing helpers used to verify exact byte recovery."""

import hashlib
from collections.abc import Buffer


def sha256_digest(data: Buffer) -> bytes:
    """Return the raw SHA-256 digest of a bytes-like value."""
    return hashlib.sha256(bytes(data)).digest()


def sha256_hex(data: Buffer) -> str:
    """Return the lowercase hexadecimal SHA-256 digest."""
    return hashlib.sha256(bytes(data)).hexdigest()
