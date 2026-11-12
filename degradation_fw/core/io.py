"""Image I/O. Uses Pillow so non-ASCII (e.g. Chinese) Windows paths work."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def to_float(img: np.ndarray) -> np.ndarray:
    """uint8 / any RGB(A) / gray array -> float32 HxWx3 in [0, 1]."""
    arr = np.asarray(img)
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=-1)
    if arr.shape[-1] == 4:
        arr = arr[..., :3]
    if arr.dtype == np.uint8:
        return arr.astype(np.float32) / 255.0
    return arr.astype(np.float32)


def to_uint8(img: np.ndarray) -> np.ndarray:
    return (np.clip(img, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def load_image(path: str | Path) -> np.ndarray:
    with Image.open(path) as im:
        return to_float(np.asarray(im.convert("RGB")))


def save_image(img: np.ndarray, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(to_uint8(img)).save(path)


def list_images(folder: str | Path) -> list[Path]:
    folder = Path(folder)
    return sorted(p for p in folder.rglob("*") if p.suffix.lower() in IMAGE_EXTS)
