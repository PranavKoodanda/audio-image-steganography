"""End-to-end WAV-in-PNG encryption and steganography workflows."""

from collections.abc import Buffer
from io import BytesIO
import wave

from PIL import Image, UnidentifiedImageError

from backend.app.core.crypto import decrypt, encrypt
from backend.app.stego.lsb import extract_lsb, embed_lsb
from backend.app.stego.png_chunk import embed_payload, extract_payload

SUPPORTED_METHODS = frozenset(("chunk", "lsb"))


class WorkflowError(ValueError):
    """Base class for invalid workflow inputs or recovered data."""


class UnsupportedMethodError(WorkflowError):
    """Raised when a workflow method is not supported."""


class InvalidWAVError(WorkflowError):
    """Raised when input or recovered bytes are not a valid WAV file."""


class InvalidPNGError(WorkflowError):
    """Raised when a PNG cannot be decoded or validated."""


def _require_method(method: str) -> str:
    if not isinstance(method, str):
        raise TypeError("method must be a string")
    if method not in SUPPORTED_METHODS:
        raise UnsupportedMethodError(
            f"unsupported method {method!r}; expected 'chunk' or 'lsb'"
        )
    return method


def _require_bytes(value: Buffer, name: str) -> bytes:
    if not isinstance(value, Buffer):
        raise TypeError(f"{name} must be bytes-like")
    return bytes(value)


def _validate_wav(data: bytes) -> None:
    if not data:
        raise InvalidWAVError("WAV data must not be empty")
    try:
        with wave.open(BytesIO(data), "rb") as audio:
            frame_count = audio.getnframes()
            channel_count = audio.getnchannels()
            sample_width = audio.getsampwidth()
            if (
                channel_count <= 0
                or sample_width <= 0
                or frame_count <= 0
                or audio.getcomptype() != "NONE"
            ):
                raise InvalidWAVError("WAV must contain uncompressed PCM audio frames")
            frame_data = audio.readframes(frame_count)
            expected_length = frame_count * channel_count * sample_width
            if len(frame_data) != expected_length:
                raise InvalidWAVError("WAV frame data length is inconsistent")
    except (InvalidWAVError, wave.Error, EOFError) as error:
        if isinstance(error, InvalidWAVError):
            raise
        raise InvalidWAVError("invalid WAV data") from error


def _validate_png(png: bytes) -> None:
    try:
        _validate_png_with_pillow(png)
    except (ValueError, SyntaxError, UnidentifiedImageError, OSError) as error:
        raise InvalidPNGError("invalid PNG data") from error


def _validate_png_with_pillow(png: bytes) -> None:
    with Image.open(BytesIO(png)) as image:
        if image.format != "PNG":
            raise InvalidPNGError("input must be a PNG image")
        image.verify()


def hide_wav_in_png(
    wav_data: Buffer,
    png: Buffer,
    password: str,
    method: str,
) -> bytes:
    """Encrypt WAV bytes and embed the authenticated envelope in a PNG."""
    selected_method = _require_method(method)
    raw_wav = _require_bytes(wav_data, "wav_data")
    raw_png = _require_bytes(png, "png")
    _validate_wav(raw_wav)
    _validate_png(raw_png)

    encrypted = encrypt(raw_wav, password)
    if selected_method == "chunk":
        return embed_payload(raw_png, encrypted)

    try:
        with Image.open(BytesIO(raw_png)) as image:
            embedded = embed_lsb(image, encrypted)
            output = BytesIO()
            embedded.save(output, format="PNG")
            return output.getvalue()
    except OSError as error:
        raise InvalidPNGError("PNG cannot store the encrypted WAV envelope") from error


def recover_wav_from_png(png: Buffer, password: str, method: str) -> bytes:
    """Extract, authenticate, decrypt, and validate WAV bytes from a PNG."""
    selected_method = _require_method(method)
    raw_png = _require_bytes(png, "png")
    _validate_png(raw_png)

    encrypted = (
        extract_payload(raw_png)
        if selected_method == "chunk"
        else extract_lsb(raw_png)
    )
    recovered = decrypt(encrypted, password)
    _validate_wav(recovered)
    return recovered
