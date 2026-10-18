"""Tests for direct PNG custom-chunk embedding."""

from io import BytesIO
import struct
import zlib

import pytest
from PIL import Image

from backend.app.stego.png_chunk import (
    IEND_CHUNK_TYPE,
    PAYLOAD_CHUNK_TYPE,
    PNGChunkError,
    PNG_SIGNATURE,
    embed_payload,
    extract_payload,
)


def _image_png() -> bytes:
    image = Image.new("RGBA", (4, 3))
    image.putdata([(x * 20, y * 30, 100, 255) for y in range(3) for x in range(4)])
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _chunks(png: bytes) -> list[tuple[bytes, bytes, bytes]]:
    result = []
    offset = len(PNG_SIGNATURE)
    while offset < len(png):
        length = struct.unpack(">I", png[offset : offset + 4])[0]
        end = offset + 12 + length
        result.append((png[offset + 4 : offset + 8], png[offset + 8 : offset + 8 + length], png[offset:end]))
        offset = end
    return result


def test_round_trip_and_empty_binary_payloads() -> None:
    png = _image_png()
    for payload in (b"", bytes(range(256)) + b"\x00\xff"):
        embedded = embed_payload(png, payload)
        assert extract_payload(embedded) == payload


def test_chunk_is_before_iend_and_crc_is_correct() -> None:
    embedded = embed_payload(_image_png(), b"payload")
    chunks = _chunks(embedded)
    assert chunks[-2][0] == PAYLOAD_CHUNK_TYPE
    assert chunks[-1][0] == IEND_CHUNK_TYPE
    assert extract_payload(embedded) == b"payload"
    payload_data = chunks[-2][1]
    assert struct.unpack(">I", chunks[-2][2][-4:])[0] == zlib.crc32(
        PAYLOAD_CHUNK_TYPE + payload_data
    ) & 0xFFFFFFFF


def test_pixels_and_original_chunks_are_preserved() -> None:
    original = _image_png()
    embedded = embed_payload(original, b"audio envelope")
    original_chunks = _chunks(original)
    embedded_chunks = _chunks(embedded)
    assert [chunk[2] for chunk in embedded_chunks if chunk[0] != PAYLOAD_CHUNK_TYPE] == [
        chunk[2] for chunk in original_chunks
    ]
    with Image.open(BytesIO(original)) as first, Image.open(BytesIO(embedded)) as second:
        assert first.size == second.size
        assert first.mode == second.mode
        assert first.tobytes() == second.tobytes()


def test_invalid_signature_truncated_chunk_invalid_crc_and_missing_iend() -> None:
    png = _image_png()
    with pytest.raises(PNGChunkError):
        extract_payload(b"not a png")
    with pytest.raises(PNGChunkError):
        extract_payload(png[:-2])

    invalid_crc = bytearray(embed_payload(png, b"x"))
    invalid_crc[-13] ^= 1
    with pytest.raises(PNGChunkError):
        extract_payload(invalid_crc)

    without_iend = png[: -12]
    with pytest.raises(PNGChunkError):
        extract_payload(without_iend)


def test_missing_and_duplicate_payload_chunks_are_rejected() -> None:
    png = _image_png()
    with pytest.raises(PNGChunkError, match="does not contain"):
        extract_payload(png)

    once = embed_payload(png, b"one")
    with pytest.raises(PNGChunkError, match="already contains"):
        embed_payload(once, b"two")

    chunks = _chunks(once)
    duplicate = (
        PNG_SIGNATURE
        + b"".join(chunk[2] for chunk in chunks[:-1])
        + chunks[-2][2]
        + chunks[-1][2]
    )
    with pytest.raises(PNGChunkError, match="duplicate"):
        extract_payload(duplicate)


def test_payload_chunk_in_wrong_position_is_rejected() -> None:
    original_chunks = _chunks(_image_png())
    payload_chunk = embed_payload(_image_png(), b"payload")
    payload = _chunks(payload_chunk)[-2][2]
    misplaced = (
    PNG_SIGNATURE
    + original_chunks[0][2]  # IHDR remains first
    + payload                # stEg is misplaced
    + b"".join(chunk[2] for chunk in original_chunks[1:])
)
    with pytest.raises(PNGChunkError, match="immediately before IEND"):
        extract_payload(misplaced)
