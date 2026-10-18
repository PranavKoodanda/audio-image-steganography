"""Tests for encrypted payloads and envelope validation."""

import pytest

from backend.app.core.crypto import AuthenticationError, decrypt, encrypt
from backend.app.core.envelope import HEADER_SIZE, EnvelopeError, parse_envelope
from backend.app.utils.hashing import sha256_hex


PASSWORD = "correct horse battery staple"


def test_encryption_round_trip_and_hash() -> None:
    payload = b"RIFF\x00\x00\x00\x00WAVE" * 3
    encrypted = encrypt(payload, PASSWORD)
    assert decrypt(encrypted, PASSWORD) == payload
    assert sha256_hex(decrypt(encrypted, PASSWORD)) == sha256_hex(payload)


def test_incorrect_password() -> None:
    with pytest.raises(AuthenticationError):
        decrypt(encrypt(b"audio", PASSWORD), "wrong password")


def test_tampered_ciphertext() -> None:
    envelope = bytearray(encrypt(b"audio", PASSWORD))
    envelope[HEADER_SIZE + 16 + 12] ^= 1
    with pytest.raises(AuthenticationError):
        decrypt(envelope, PASSWORD)


def test_truncated_and_malformed_envelopes() -> None:
    encrypted = encrypt(b"audio", PASSWORD)
    with pytest.raises(EnvelopeError):
        decrypt(encrypted[:-1], PASSWORD)
    malformed = bytearray(encrypted)
    malformed[0:4] = b"bad!"
    with pytest.raises(EnvelopeError):
        parse_envelope(malformed)


@pytest.mark.parametrize(
    ("offset", "value"),
    [
        (12, b"\x01"),
        (13, b"\x00\x00\x00\x00"),
        (17, b"\x00\x00\x00\x00"),
    ],
)
def test_invalid_version_and_kdf_parameters(offset: int, value: bytes) -> None:
    encrypted = bytearray(encrypt(b"audio", PASSWORD))
    encrypted[4] = 2
    with pytest.raises(EnvelopeError):
        parse_envelope(encrypted)

    encrypted = bytearray(encrypt(b"audio", PASSWORD))
    encrypted[offset : offset + len(value)] = value
    with pytest.raises(EnvelopeError):
        parse_envelope(encrypted)


def test_empty_payload() -> None:
    encrypted = encrypt(b"", PASSWORD)
    assert decrypt(encrypted, PASSWORD) == b""


def test_fresh_salts_and_nonces() -> None:
    first = parse_envelope(encrypt(b"same", PASSWORD))
    second = parse_envelope(encrypt(b"same", PASSWORD))
    assert first.salt != second.salt
    assert first.nonce != second.nonce
