"""Versioned binary envelope format for encrypted payloads.

Format (big-endian):

    magic(4) version(1) algorithm(1) kdf(1) reserved(1)
    salt_length(1) nonce_length(1) tag_length(1) reserved(1)
    scrypt_log_n(1) scrypt_r(4) scrypt_p(4) ciphertext_length(8)
    salt nonce ciphertext authentication_tag

The fixed header is authenticated as AES-GCM additional authenticated data.
"""

from dataclasses import dataclass
import struct

MAGIC = b"AIS1"
VERSION = 1
AES_256_GCM = 1
SCRYPT = 1
HEADER = struct.Struct(">4sBBBBBBBBBIIQ")
HEADER_SIZE = HEADER.size
SALT_LENGTH = 16
NONCE_LENGTH = 12
TAG_LENGTH = 16
MIN_SCRYPT_LOG_N = 14
MAX_SCRYPT_LOG_N = 20
MIN_SCRYPT_R = 1
MAX_SCRYPT_R = 32
MIN_SCRYPT_P = 1
MAX_SCRYPT_P = 16
MAX_CIPHERTEXT_LENGTH = 256 * 1024 * 1024 + TAG_LENGTH


class EnvelopeError(ValueError):
    """Raised when an envelope is structurally invalid or unsupported."""


@dataclass(frozen=True, slots=True)
class Envelope:
    """Validated envelope components, excluding any password or derived key."""

    header: bytes
    salt: bytes
    nonce: bytes
    ciphertext: bytes
    tag: bytes
    log_n: int
    r: int
    p: int


def validate_kdf_parameters(log_n: int, r: int, p: int) -> None:
    """Validate Scrypt parameters against supported and bounded values."""
    if not MIN_SCRYPT_LOG_N <= log_n <= MAX_SCRYPT_LOG_N:
        raise EnvelopeError("Scrypt log_n is outside the supported bounds")
    if not MIN_SCRYPT_R <= r <= MAX_SCRYPT_R:
        raise EnvelopeError("Scrypt r is outside the supported bounds")
    if not MIN_SCRYPT_P <= p <= MAX_SCRYPT_P:
        raise EnvelopeError("Scrypt p is outside the supported bounds")


def build_header(log_n: int, r: int, p: int, ciphertext_length: int) -> bytes:
    """Build and validate the fixed header for an encrypted payload."""
    validate_kdf_parameters(log_n, r, p)
    if not 0 <= ciphertext_length <= MAX_CIPHERTEXT_LENGTH:
        raise EnvelopeError("ciphertext length is outside the supported bounds")
    return HEADER.pack(
        MAGIC,
        VERSION,
        AES_256_GCM,
        SCRYPT,
        0,
        SALT_LENGTH,
        NONCE_LENGTH,
        TAG_LENGTH,
        0,
        log_n,
        r,
        p,
        ciphertext_length,
    )


def parse_envelope(data: bytes | bytearray | memoryview) -> Envelope:
    """Parse and validate an envelope before any expensive cryptographic work."""
    raw = bytes(data)
    if len(raw) < HEADER_SIZE:
        raise EnvelopeError("envelope is truncated before its header")

    fields = HEADER.unpack(raw[:HEADER_SIZE])
    (
        magic,
        version,
        algorithm,
        kdf,
        reserved_a,
        salt_length,
        nonce_length,
        tag_length,
        reserved_b,
        log_n,
        r,
        p,
        ciphertext_length,
    ) = fields
    if magic != MAGIC or version != VERSION:
        raise EnvelopeError("unsupported envelope magic or version")
    if algorithm != AES_256_GCM or kdf != SCRYPT:
        raise EnvelopeError("unsupported envelope algorithm or KDF")
    if reserved_a or reserved_b:
        raise EnvelopeError("reserved header fields must be zero")
    if (
        salt_length != SALT_LENGTH
        or nonce_length != NONCE_LENGTH
        or tag_length != TAG_LENGTH
    ):
        raise EnvelopeError("invalid envelope component length")
    validate_kdf_parameters(log_n, r, p)
    if ciphertext_length > MAX_CIPHERTEXT_LENGTH:
        raise EnvelopeError("ciphertext length exceeds the supported maximum")

    expected_length = HEADER_SIZE + salt_length + nonce_length + ciphertext_length + tag_length
    if len(raw) != expected_length:
        raise EnvelopeError("envelope length does not match its header")
    offset = HEADER_SIZE
    salt = raw[offset : offset + salt_length]
    offset += salt_length
    nonce = raw[offset : offset + nonce_length]
    offset += nonce_length
    ciphertext = raw[offset : offset + ciphertext_length]
    offset += ciphertext_length
    tag = raw[offset : offset + tag_length]
    return Envelope(raw[:HEADER_SIZE], salt, nonce, ciphertext, tag, log_n, r, p)
