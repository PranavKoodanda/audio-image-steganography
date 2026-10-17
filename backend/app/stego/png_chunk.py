"""Embedding and extraction of payloads in a custom PNG ancillary chunk.

The ``stEg`` chunk is inserted immediately before ``IEND``. This module
operates on PNG bytes directly and never decodes or re-encodes image data.
"""

from dataclasses import dataclass
import struct
import zlib
from collections.abc import Buffer

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PAYLOAD_CHUNK_TYPE = b"stEg"
IEND_CHUNK_TYPE = b"IEND"
CHUNK_HEADER_SIZE = 8
CHUNK_TRAILER_SIZE = 4
MAX_CHUNK_DATA_LENGTH = 256 * 1024 * 1024


class PNGChunkError(ValueError):
    """Raised when a PNG or its custom payload chunk is invalid."""


@dataclass(frozen=True, slots=True)
class _Chunk:
    """A parsed PNG chunk including its exact serialized bytes."""

    chunk_type: bytes
    data: bytes
    serialized: bytes


def _require_png_bytes(png: Buffer) -> bytes:
    """Return immutable PNG bytes and reject non-bytes-like inputs."""
    if not isinstance(png, Buffer):
        raise TypeError("png must be bytes-like")
    return bytes(png)


def _parse_chunks(png: bytes) -> tuple[_Chunk, ...]:
    """Parse a complete PNG and validate every chunk and CRC."""
    if not png.startswith(PNG_SIGNATURE):
        raise PNGChunkError("invalid PNG signature")

    chunks: list[_Chunk] = []
    offset = len(PNG_SIGNATURE)
    while offset < len(png):
        chunk_start = offset
        if len(png) - offset < CHUNK_HEADER_SIZE:
            raise PNGChunkError("truncated PNG chunk header")
        data_length = struct.unpack(">I", png[offset : offset + 4])[0]
        if data_length > MAX_CHUNK_DATA_LENGTH:
            raise PNGChunkError("PNG chunk is too large")
        chunk_type = png[offset + 4 : offset + 8]
        if len(chunk_type) != 4 or not all(
            65 <= byte <= 90 or 97 <= byte <= 122 for byte in chunk_type
        ):
            raise PNGChunkError("invalid PNG chunk type")

        offset += CHUNK_HEADER_SIZE
        remaining = len(png) - offset
        if remaining < data_length + CHUNK_TRAILER_SIZE:
            raise PNGChunkError("truncated PNG chunk data or CRC")
        data = png[offset : offset + data_length]
        offset += data_length
        stored_crc = struct.unpack(">I", png[offset : offset + 4])[0]
        offset += CHUNK_TRAILER_SIZE
        calculated_crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        if stored_crc != calculated_crc:
            raise PNGChunkError("invalid PNG chunk CRC")

        serialized = png[chunk_start:offset]
        chunks.append(_Chunk(chunk_type, data, serialized))
        if chunk_type == IEND_CHUNK_TYPE:
            if data_length != 0 or offset != len(png):
                raise PNGChunkError("IEND must be empty and be the final chunk")
            return tuple(chunks)

    raise PNGChunkError("PNG is missing IEND")


def _make_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Serialize a PNG chunk with a CRC-32 over its type and data."""
    if len(data) > MAX_CHUNK_DATA_LENGTH:
        raise PNGChunkError("payload is too large")
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def embed_payload(png: Buffer, payload: Buffer) -> bytes:
    """Insert *payload* as a ``stEg`` chunk immediately before ``IEND``.

    Existing ``stEg`` chunks are rejected to avoid ambiguous extraction and
    accidental replacement of an existing payload.
    """
    raw_png = _require_png_bytes(png)
    if not isinstance(payload, Buffer):
        raise TypeError("payload must be bytes-like")
    raw_payload = bytes(payload)

    chunks = _parse_chunks(raw_png)
    if any(chunk.chunk_type == PAYLOAD_CHUNK_TYPE for chunk in chunks):
        raise PNGChunkError("PNG already contains a stEg payload chunk")
    if chunks[-1].chunk_type != IEND_CHUNK_TYPE:
        raise PNGChunkError("PNG is missing IEND")

    prefix = b"".join(chunk.serialized for chunk in chunks[:-1])
    return PNG_SIGNATURE + prefix + _make_chunk(PAYLOAD_CHUNK_TYPE, raw_payload) + chunks[-1].serialized


def extract_payload(png: Buffer) -> bytes:
    """Extract the sole ``stEg`` payload immediately before the final ``IEND``."""
    chunks = _parse_chunks(_require_png_bytes(png))
    payload_chunks = [
        chunk for chunk in chunks if chunk.chunk_type == PAYLOAD_CHUNK_TYPE
    ]
    if not payload_chunks:
        raise PNGChunkError("PNG does not contain a stEg payload chunk")
    if len(payload_chunks) > 1:
        raise PNGChunkError("PNG contains duplicate stEg payload chunks")
    payload_index = next(
        index
        for index, chunk in enumerate(chunks)
        if chunk.chunk_type == PAYLOAD_CHUNK_TYPE
    )
    if payload_index != len(chunks) - 2:
        raise PNGChunkError("stEg payload chunk must be immediately before IEND")
    return chunks[payload_index].data
