"""Password-based AES-256-GCM encryption for the project envelope."""

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
import secrets

from .envelope import (
    NONCE_LENGTH,
    SALT_LENGTH,
    TAG_LENGTH,
    build_header,
    parse_envelope,
)
from .validation import require_bytes, require_password

DEFAULT_SCRYPT_LOG_N = 16
DEFAULT_SCRYPT_R = 8
DEFAULT_SCRYPT_P = 1


class AuthenticationError(ValueError):
    """Raised when a password or authenticated payload is invalid."""


def _derive_key(password: str, salt: bytes, log_n: int, r: int, p: int) -> bytes:
    """Derive a 256-bit key with the Scrypt parameters stored in the envelope."""
    return Scrypt(
        salt=salt,
        length=32,
        n=1 << log_n,
        r=r,
        p=p,
    ).derive(password.encode("utf-8"))


def encrypt(
    payload: bytes | bytearray | memoryview,
    password: str,
    *,
    log_n: int = DEFAULT_SCRYPT_LOG_N,
    r: int = DEFAULT_SCRYPT_R,
    p: int = DEFAULT_SCRYPT_P,
) -> bytes:
    """Encrypt *payload* and return a self-contained authenticated envelope."""
    plaintext = require_bytes(payload, "payload")
    require_password(password)
    salt = secrets.token_bytes(SALT_LENGTH)
    nonce = secrets.token_bytes(NONCE_LENGTH)
    key = _derive_key(password, salt, log_n, r, p)
    header = build_header(log_n, r, p, len(plaintext))
    encrypted = AESGCM(key).encrypt(nonce, plaintext, header)
    return header + salt + nonce + encrypted[:-TAG_LENGTH] + encrypted[-TAG_LENGTH:]


def decrypt(envelope: bytes | bytearray | memoryview, password: str) -> bytes:
    """Authenticate and decrypt an envelope, raising on any authentication failure."""
    require_password(password)
    parsed = parse_envelope(require_bytes(envelope, "envelope"))
    key = _derive_key(password, parsed.salt, parsed.log_n, parsed.r, parsed.p)
    try:
        return AESGCM(key).decrypt(
            parsed.nonce,
            parsed.ciphertext + parsed.tag,
            parsed.header,
        )
    except InvalidTag as exc:
        raise AuthenticationError("invalid password or tampered encrypted payload") from exc
