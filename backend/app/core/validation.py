"""Input validation helpers shared by the backend."""

from collections.abc import Buffer


def require_bytes(value: bytes | bytearray | memoryview, name: str) -> bytes:
    """Return *value* as immutable bytes or reject an invalid input type."""
    if not isinstance(value, Buffer):
        raise TypeError(f"{name} must be bytes-like")
    return bytes(value)


def require_password(password: str) -> str:
    """Validate a password without imposing an arbitrary minimum length."""
    if not isinstance(password, str):
        raise TypeError("password must be a string")
    if not password:
        raise ValueError("password must not be empty")
    return password
