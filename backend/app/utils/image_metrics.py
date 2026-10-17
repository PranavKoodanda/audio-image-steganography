"""Image-quality measurements for RGB and RGBA decoded images."""

from dataclasses import dataclass
import math

from PIL import Image


@dataclass(frozen=True, slots=True)
class ImageMetrics:
    """Pixel differences measured across RGB channels only."""

    changed_rgb_channels: int
    changed_channel_ratio: float
    mse: float
    psnr: float

    @property
    def changed_channels(self) -> int:
        """Backward-friendly shorthand for the RGB channel count."""
        return self.changed_rgb_channels


def calculate_image_metrics(first: Image.Image, second: Image.Image) -> ImageMetrics:
    """Compare two RGB/RGBA images, excluding alpha from all measurements."""
    if not isinstance(first, Image.Image) or not isinstance(second, Image.Image):
        raise TypeError("images must be Pillow Image instances")
    if first.size != second.size:
        raise ValueError("images must have matching dimensions")
    if first.mode not in {"RGB", "RGBA"} or second.mode not in {"RGB", "RGBA"}:
        raise ValueError("images must use RGB or RGBA mode")
    if first.width == 0 or first.height == 0:
        raise ValueError("images must have positive dimensions")

    first_rgb = first.convert("RGB")
    second_rgb = second.convert("RGB")
    changed = 0
    squared_error = 0
    for first_value, second_value in zip(first_rgb.tobytes(), second_rgb.tobytes()):
        difference = second_value - first_value
        changed += difference != 0
        squared_error += difference * difference
    total_channels = first.width * first.height * 3
    mse = squared_error / total_channels
    psnr = math.inf if mse == 0 else 10 * math.log10((255 * 255) / mse)
    return ImageMetrics(changed, changed / total_channels, mse, psnr)


compare_images = calculate_image_metrics
