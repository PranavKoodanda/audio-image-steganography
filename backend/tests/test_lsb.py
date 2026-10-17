from io import BytesIO

import pytest
from PIL import Image

from backend.app.stego.lsb import (
    CapacityError,
    ChecksumError,
    HEADER_SIZE,
    HeaderError,
    InvalidImageError,
    calculate_capacity,
    embed_lsb,
    extract_lsb,
)
from backend.app.utils.image_metrics import calculate_image_metrics


def _image(mode: str = "RGBA", size: tuple[int, int] = (8, 8)) -> Image.Image:
    image = Image.new(mode, size)
    if mode == "RGBA":
        image.putdata(
            [
                ((index * 17) % 256, (index * 31) % 256, 91, 200 + index % 50)
                for index in range(size[0] * size[1])
            ]
        )
    else:
        image.putdata(
            [((index * 17) % 256, (index * 31) % 256, 91) for index in range(size[0] * size[1])]
        )
    return image


def test_binary_and_empty_round_trips() -> None:
    for image, payload in ((_image(size=(12, 12)), b""), (_image(size=(30, 30)), bytes(range(256)))):
        assert extract_lsb(embed_lsb(image, payload)) == payload


def test_capacity_and_too_large_payload() -> None:
    image = _image("RGB", (4, 4))
    assert calculate_capacity(image) == 0
    with pytest.raises(CapacityError):
        embed_lsb(image, b"x")

    larger = _image("RGB", (20, 20))
    capacity = calculate_capacity(larger)
    assert capacity > 0
    assert len(extract_lsb(embed_lsb(larger, b"x" * capacity))) == capacity


def test_bytes_input_and_invalid_images() -> None:
    output = BytesIO()
    _image("RGB", (12, 12)).save(output, format="PNG")
    encoded = embed_lsb(output.getvalue(), b"payload")
    assert extract_lsb(encoded) == b"payload"
    with pytest.raises(InvalidImageError):
        calculate_capacity(b"not an image")
    with pytest.raises(InvalidImageError):
        calculate_capacity(Image.new("L", (8, 8)))


def test_corrupted_header_and_checksum() -> None:
    image = _image("RGB", (12, 12))
    encoded = embed_lsb(image, b"payload")
    pixels = list(encoded.get_flattened_data())
    pixels[0] = (pixels[0][0] ^ 1, pixels[0][1], pixels[0][2])
    corrupted_header = encoded.copy()
    corrupted_header.putdata(pixels)
    with pytest.raises(HeaderError):
        extract_lsb(corrupted_header)

    pixels = list(encoded.get_flattened_data())
    payload_channel_ordinal = HEADER_SIZE * 8
    payload_pixel_index, payload_channel_index = divmod(payload_channel_ordinal, 3)
    pixel = pixels[payload_pixel_index]
    corrupted_pixel = list(pixel)
    corrupted_pixel[payload_channel_index] ^= 1
    pixels[payload_pixel_index] = tuple(corrupted_pixel)
    corrupted_payload = encoded.copy()
    corrupted_payload.putdata(pixels)
    with pytest.raises(ChecksumError):
        extract_lsb(corrupted_payload)


def test_alpha_is_preserved_and_metrics_ignore_it() -> None:
    image = _image(size=(12, 12))
    encoded = embed_lsb(image, b"payload")
    assert [pixel[3] for pixel in image.get_flattened_data()] == [
        pixel[3] for pixel in encoded.get_flattened_data()
    ]
    metrics = calculate_image_metrics(image, encoded)
    assert metrics.changed_rgb_channels > 0
    assert metrics.changed_channel_ratio == metrics.changed_rgb_channels / (12 * 12 * 3)
    assert metrics.mse > 0
    assert metrics.psnr > 0
    assert calculate_image_metrics(image, image).psnr == float("inf")
    with pytest.raises(ValueError, match="matching dimensions"):
        calculate_image_metrics(image, _image(size=(7, 12)))


def test_metrics_reject_empty_images() -> None:
    empty = Image.new("RGB", (0, 0))
    with pytest.raises(ValueError, match="positive dimensions"):
        calculate_image_metrics(empty, empty)
