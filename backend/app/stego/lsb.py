"""Least-significant-bit embedding for RGB and RGBA PNG images.

The serialized header is version 1 and uses big-endian fields::

    magic (4 bytes) | version (1) | reserved (1) | payload length (8)
    | SHA-256 payload digest (32)

Header and payload bytes are written most-significant bit first into RGB
channels in row-major pixel order. Alpha channels are never written.
"""

from collections.abc import Buffer, Iterator
from io import BytesIO
from itertools import chain
import struct
from PIL import Image, UnidentifiedImageError

from backend.app.utils.hashing import sha256_digest

MAGIC = b"LSB1"
VERSION = 1
_HEADER = struct.Struct(">4sBBQ32s")
HEADER_SIZE = _HEADER.size
SUPPORTED_MODES = frozenset(("RGB", "RGBA"))


class LSBError(ValueError):
    """Base class for invalid LSB image data."""


class InvalidImageError(LSBError):
    """Raised when an image is invalid or has an unsupported mode."""


class CapacityError(LSBError):
    """Raised when a payload or encoded header does not fit."""


class HeaderError(LSBError):
    """Raised when an embedded LSB header is invalid."""


class ChecksumError(LSBError):
    """Raised when an extracted payload fails its SHA-256 checksum."""


def _image(png: Image.Image | Buffer) -> Image.Image:
    if isinstance(png, Image.Image):
        image = png
    elif isinstance(png, Buffer):
        try:
            with Image.open(BytesIO(bytes(png))) as opened:
                if opened.format != "PNG":
                    raise InvalidImageError("png must contain a PNG image")
                opened.load()
                image = opened.copy()
        except (UnidentifiedImageError, OSError) as error:
            raise InvalidImageError("png is not a valid PNG image") from error
    else:
        raise TypeError("png must be a Pillow Image or bytes-like PNG")

    if image.mode not in SUPPORTED_MODES:
        raise InvalidImageError(
            f"unsupported image mode {image.mode!r}; expected RGB or RGBA"
        )
    if image.width <= 0 or image.height <= 0:
        raise InvalidImageError("image dimensions must be positive")
    return image


def _channel_count(image: Image.Image) -> int:
    return image.width * image.height * 3


def calculate_capacity(png: Image.Image | Buffer) -> int:
    """Return the maximum payload size in bytes for an RGB/RGBA image."""
    image = _image(png)
    return max(0, (_channel_count(image) // 8) - HEADER_SIZE)


def _bits(data: bytes) -> Iterator[int]:
    """Yield data bits in MSB-first order without materializing a bit list."""
    for byte in data:
        for shift in range(7, -1, -1):
            yield (byte >> shift) & 1


def _channel_offset(rgb_channel: int, pixel_stride: int) -> int:
    """Map an RGB-channel ordinal to a packed RGB/RGBA byte offset."""
    pixel_index, channel_index = divmod(rgb_channel, 3)
    return pixel_index * pixel_stride + channel_index


def _read_bytes(pixel_bytes: bytes, pixel_stride: int, channel_start: int, count: int) -> bytes:
    result = bytearray(count)
    for bit_index in range(count * 8):
        offset = _channel_offset(channel_start + bit_index, pixel_stride)
        result[bit_index // 8] |= (pixel_bytes[offset] & 1) << (7 - bit_index % 8)
    return bytes(result)


def embed_lsb(png: Image.Image | Buffer, payload: Buffer) -> Image.Image:
    """Return a copy of *png* containing arbitrary binary *payload*.

    The SHA-256 digest detects accidental corruption; it is not
    authentication. Use the Phase 1 AES-GCM envelope for cryptographic
    authentication.
    """
    image = _image(png)
    if not isinstance(payload, Buffer):
        raise TypeError("payload must be bytes-like")
    raw_payload = bytes(payload)
    if _channel_count(image) < HEADER_SIZE * 8:
        raise CapacityError("image is too small to store the LSB header")
    capacity = max(0, (_channel_count(image) // 8) - HEADER_SIZE)
    if len(raw_payload) > capacity:
        raise CapacityError(
            f"payload is {len(raw_payload)} bytes but image capacity is {capacity} bytes"
        )

    header = _HEADER.pack(MAGIC, VERSION, 0, len(raw_payload), sha256_digest(raw_payload))
    encoded_bits = chain(_bits(header), _bits(raw_payload))
    output = image.copy()
    pixel_bytes = bytearray(output.tobytes())
    pixel_stride = len(pixel_bytes) // (image.width * image.height)
    for channel_index, bit in enumerate(encoded_bits):
        offset = _channel_offset(channel_index, pixel_stride)
        pixel_bytes[offset] = (pixel_bytes[offset] & ~1) | bit
    output.frombytes(pixel_bytes)
    return output


def extract_lsb(png: Image.Image | Buffer) -> bytes:
    """Extract and checksum-validate the payload from an LSB image."""
    image = _image(png)
    pixel_stride = 4 if image.mode == "RGBA" else 3
    pixel_bytes = image.tobytes()
    if _channel_count(image) < HEADER_SIZE * 8:
        raise HeaderError("image does not contain a complete LSB header")
    header = _read_bytes(pixel_bytes, pixel_stride, 0, HEADER_SIZE)
    magic, version, reserved, payload_length, expected_digest = _HEADER.unpack(header)
    if magic != MAGIC:
        raise HeaderError("invalid LSB magic identifier")
    if version != VERSION:
        raise HeaderError(f"unsupported LSB header version: {version}")
    if reserved != 0:
        raise HeaderError("invalid LSB header flags")
    capacity = calculate_capacity(image)
    if payload_length > capacity:
        raise CapacityError(
            f"encoded payload length {payload_length} exceeds image capacity {capacity}"
        )
    payload = _read_bytes(pixel_bytes, pixel_stride, HEADER_SIZE * 8, payload_length)
    if sha256_digest(payload) != expected_digest:
        raise ChecksumError("LSB payload checksum does not match")
    return payload
