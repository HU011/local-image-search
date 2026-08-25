"""Image encoding and decoding helpers."""

import base64
from io import BytesIO

from loguru import logger
from PIL import Image


def decode_base64_image(base64_str: str) -> Image.Image:
    """Decode a base64 image string into an RGB PIL image."""
    try:
        if "," in base64_str:
            base64_str = base64_str.split(",", 1)[1]

        image_data = base64.b64decode(base64_str)
        image = Image.open(BytesIO(image_data))

        if image.mode != "RGB":
            image = image.convert("RGB")

        return image

    except Exception as exc:
        logger.error(f"Image decode failed: {exc}")
        raise ValueError(f"Image decode failed: {exc}") from exc


def encode_image_to_base64(image: Image.Image, format: str = "JPEG") -> str:
    """Encode a PIL image as a base64 string."""
    buffer = BytesIO()
    image.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")
