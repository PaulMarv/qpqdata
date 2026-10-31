"""Bounded raster decoding and fresh pixel-only encoding; originals never persisted."""

import hashlib
import io
from dataclasses import dataclass
from threading import BoundedSemaphore

from PIL import Image, ImageOps, UnidentifiedImageError

from app.auth import AuthError
from app.project_schemas import ProjectDefinition
from app.submission_schemas import MAX_BYTES, MAX_PIXELS

# Bound CPU/memory per process. More processes require matching deployment limits.
_PROCESSORS = BoundedSemaphore(2)


@dataclass(frozen=True)
class ProcessedImage:
    data: bytes
    format: str
    width: int
    height: int
    content_hash: str


def process_image(data: bytes, definition: ProjectDefinition) -> ProcessedImage:
    if not data or len(data) > MAX_BYTES:
        raise AuthError("Image must be between 1 byte and 10 MiB.", 413)
    if not _PROCESSORS.acquire(blocking=False):
        raise AuthError("Image processor busy. Retry shortly.", 429)
    try:
        with Image.open(io.BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as source:
            fmt = source.format
            if fmt not in definition.allowed_formats:
                raise AuthError("This image format is not accepted by the collection.", 400)
            if source.width * source.height > MAX_PIXELS or max(source.size) > 20000:
                raise AuthError("Image exceeds the 24 megapixel processing limit.", 413)
            if getattr(source, "n_frames", 1) != 1:
                raise AuthError("Animated images are not supported.", 400)
            source.load()  # Full decode rejects truncated/invalid content.
            oriented = ImageOps.exif_transpose(source)
            if oriented.width < definition.min_width or oriented.height < definition.min_height:
                raise AuthError("Image dimensions are below this collection's minimum.", 400)
            mode = "RGBA" if fmt in {"PNG", "WEBP"} and "A" in oriented.getbands() else "RGB"
            converted = oriented.convert(mode)
            # A new image discards EXIF, GPS, XMP, ICC, text and all other input info.
            clean = Image.frombytes(mode, converted.size, converted.tobytes())
            fingerprint = hashlib.sha256(
                f"{mode}:{clean.width}:{clean.height}:".encode() + clean.tobytes()
            ).hexdigest()
            output = io.BytesIO()
            clean.save(output, format=fmt, **({"quality": 90} if fmt in {"JPEG", "WEBP"} else {}))
            encoded = output.getvalue()
            if len(encoded) > MAX_BYTES:
                raise AuthError("Processed image exceeds the 10 MiB storage limit.", 413)
            return ProcessedImage(encoded, fmt, clean.width, clean.height, fingerprint)
    except AuthError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        raise AuthError("File is not a valid, supported JPEG, PNG or WebP image.", 400) from None
    finally:
        _PROCESSORS.release()
