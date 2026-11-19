"""Image I/O. Uses Pillow so non-ASCII (e.g. Chinese) Windows paths work.

Images are read upright: phone cameras store portrait photos sideways plus an EXIF
orientation tag, and that tag is applied when reading (output files carry no tag).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

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


def load_rgb_u8(path: str | Path) -> np.ndarray:
    """uint8 RGB H x W x 3, upright (EXIF orientation applied); any colour mode
    (grey, palette, RGBA, CMYK, ...) converted to RGB."""
    with Image.open(path) as im:
        return np.array(ImageOps.exif_transpose(im).convert("RGB"))  # a writable copy


def load_image(path: str | Path) -> np.ndarray:
    """float32 RGB H x W x 3 in [0, 1], upright (see load_rgb_u8)."""
    return to_float(load_rgb_u8(path))


def save_image(img: np.ndarray, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(to_uint8(img)).save(path)


def list_images(folder: str | Path) -> list[Path]:
    folder = Path(folder)
    return sorted(p for p in folder.rglob("*") if p.suffix.lower() in IMAGE_EXTS)


def unique_stems(paths: Sequence[str | Path]) -> list[str]:
    """Output base names for files whose results go into one folder: each file's stem,
    with _2, _3, ... added when the stem is already taken by an earlier file (compared
    case-insensitively, as on Windows), so no result overwrites another:
    a.jpg, a.png -> a, a_2. The first file in the given order keeps its plain name."""
    used: set[str] = set()
    names = []
    for p in paths:
        stem = name = Path(p).stem
        n = 2
        while name.lower() in used:
            name, n = f"{stem}_{n}", n + 1
        used.add(name.lower())
        names.append(name)
    return names
