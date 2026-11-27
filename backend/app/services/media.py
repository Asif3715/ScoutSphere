"""Player photo processing, storage and signed delivery.

Uploads are never stored as received. Each image is decoded with Pillow (rejecting anything
that is not really a JPEG, PNG or WebP, and decompression bombs), rotated upright from its EXIF
orientation, cropped to a square, resized, and re-encoded as WebP. Re-encoding drops all
metadata, so GPS coordinates and camera details in phone photos never leave the server.

Files are served through short-lived HMAC-signed URLs, because an <img> tag cannot send the
in-memory bearer token. Expiry is rounded to a fixed window so the same URL (and the browser
cache) is reused for a while instead of changing on every request.
"""

import hashlib
import hmac
import io
import re
import secrets
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import get_settings
from app.core.errors import AppError

ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
FULL_SIZE = 640
THUMB_SIZE = 160
MIN_SIDE = 100
MAX_PIXELS = 40_000_000  # far above any phone photo; blocks decompression bombs
KEY_RE = re.compile(r"^players/[0-9a-f\-]{36}/[0-9a-f]{32}(-thumb)?\.webp$")

Image.MAX_IMAGE_PIXELS = MAX_PIXELS


@dataclass(frozen=True)
class Crop:
    x: int
    y: int
    size: int


def _bad(code: str, message: str) -> AppError:
    return AppError(422, code, message)


def process_photo(data: bytes, crop: Crop | None) -> tuple[bytes, bytes]:
    """Validates and normalizes an upload. Returns (full WebP, thumbnail WebP)."""
    if len(data) > get_settings().photo_max_bytes:
        raise AppError(413, "photo_too_large", "Photos must be 5 MB or smaller")
    if not data:
        raise _bad("invalid_photo", "The file is empty")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = probe.format
            probe.verify()  # structural check before decoding pixels
        if fmt not in ALLOWED_FORMATS:
            raise _bad("unsupported_photo_type", "Use a JPEG, PNG or WebP image")
        with Image.open(io.BytesIO(data)) as opened:
            opened.load()
            if getattr(opened, "n_frames", 1) > 1:
                opened.seek(0)  # animated WebP/PNG: keep the first frame only
            upright: Image.Image = ImageOps.exif_transpose(opened)
            img = (
                upright.convert("RGBA")
                if upright.mode in ("P", "LA", "RGBA")
                else upright.convert("RGB")
            )
    except AppError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise _bad("invalid_photo", "This image is too large to process") from None
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise _bad("unsupported_photo_type", "Use a JPEG, PNG or WebP image") from None

    w, h = img.size
    if min(w, h) < MIN_SIDE:
        raise _bad("photo_too_small", f"Photos must be at least {MIN_SIDE}×{MIN_SIDE} pixels")

    if crop is None:  # default: centred square
        side = min(w, h)
        crop = Crop((w - side) // 2, (h - side) // 2, side)
    if (
        crop.size < MIN_SIDE
        or crop.x < 0
        or crop.y < 0
        or crop.x + crop.size > w
        or crop.y + crop.size > h
    ):
        raise _bad("invalid_crop", "The selected area is outside the image")
    square = img.crop((crop.x, crop.y, crop.x + crop.size, crop.y + crop.size))
    if square.mode == "RGBA":  # flatten transparency onto white so avatars look clean
        bg = Image.new("RGB", square.size, (255, 255, 255))
        bg.paste(square, mask=square.getchannel("A"))
        square = bg

    def encode(side: int) -> bytes:
        out = io.BytesIO()
        resized = (
            square.resize((side, side), Image.Resampling.LANCZOS) if square.width > side else square
        )
        resized.save(out, "WEBP", quality=85, method=4)  # no exif/icc passed: metadata dropped
        return out.getvalue()

    return encode(FULL_SIZE), encode(THUMB_SIZE)


# ---- storage --------------------------------------------------------------------------
class LocalStorage:
    """Keeps files under MEDIA_ROOT. Keys are validated so a key can never escape the root."""

    def __init__(self, root: str | None = None):
        self.root = Path(root or get_settings().media_root).resolve()

    def _path(self, key: str) -> Path:
        if not KEY_RE.match(key):
            raise ValueError("invalid media key")
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("invalid media key")
        return path

    def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)  # atomic: readers never see a half-written file

    def path(self, key: str) -> Path | None:
        try:
            p = self._path(key)
        except ValueError:
            return None
        return p if p.is_file() else None

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except ValueError:
            pass


def storage() -> LocalStorage:
    return LocalStorage()


def new_photo_keys(player_id: uuid.UUID) -> tuple[str, str]:
    stem = f"players/{player_id}/{secrets.token_hex(16)}"
    return f"{stem}.webp", f"{stem}-thumb.webp"


def thumb_key(key: str) -> str:
    return key.removesuffix(".webp") + "-thumb.webp"


# ---- signed URLs ----------------------------------------------------------------------
def _signature(key: str, exp: int) -> str:
    secret = hashlib.sha256(b"media-url:" + get_settings().jwt_secret.encode()).digest()
    return hmac.new(secret, f"{key}|{exp}".encode(), hashlib.sha256).hexdigest()[:32]


def signed_path(key: str, now: float | None = None) -> str:
    window = get_settings().media_url_hours * 3600
    now = time.time() if now is None else now
    # Expires between one and two windows from now; constant within a window, so cacheable.
    exp = (int(now) // window + 2) * window
    return f"/api/v1/media/{key}?exp={exp}&sig={_signature(key, exp)}"


def verify(key: str, exp: int, sig: str, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    if exp < now or not KEY_RE.match(key):
        return False
    return hmac.compare_digest(_signature(key, exp), sig)
