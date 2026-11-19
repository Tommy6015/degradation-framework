"""Model weights of the third_party code, listed in third_party/weights.yaml.

    uv run degfw weights              state of every file (present / missing)
    uv run degfw weights --verify     also check the SHA-256 (reads every file)
    uv run degfw weights --download   download the missing files that have a url

An adapter declares what it needs with ``requires_weights = ("depth_pro",)``:
Degradation.unavailable_reason() then reports missing files (``degfw list``) and the
tests skip it. ``weight_path("depth_pro")`` gives the file's location.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import tempfile
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from .paths import PROJECT_ROOT, THIRD_PARTY_DIR

MANIFEST = THIRD_PARTY_DIR / "weights.yaml"
CHUNK = 1 << 20  # read / download in 1 MiB pieces
TIMEOUT = 60  # seconds without data before a download gives up


@dataclass(frozen=True)
class Weight:
    id: str
    path: Path  # absolute
    size: int  # bytes
    sha256: str
    url: str | None = None  # None: the file is in git
    note: str = ""

    @property
    def relpath(self) -> str:
        """Path relative to third_party/, as written in weights.yaml."""
        return self.path.relative_to(THIRD_PARTY_DIR).as_posix()

    def present(self) -> bool:
        """The file exists and has the expected size (quick; no hashing)."""
        return self.path.is_file() and self.path.stat().st_size == self.size


@lru_cache(maxsize=1)
def manifest() -> dict[str, Weight]:
    """All entries of weights.yaml, by id."""
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}
    weights = {}
    for wid, entry in data.items():
        try:
            weights[wid] = Weight(id=wid, path=THIRD_PARTY_DIR / entry["path"], size=int(entry["size"]),
                                  sha256=str(entry["sha256"]).lower(), url=entry.get("url"),
                                  note=entry.get("note", ""))
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"{MANIFEST.name}: entry {wid!r} needs path, size and sha256 ({e!r})") from None
    return weights


def get_weight(wid: str) -> Weight:
    try:
        return manifest()[wid]
    except KeyError:
        raise KeyError(f"Unknown model weights {wid!r}: not listed in {MANIFEST}") from None


def weight_path(wid: str) -> Path:
    """Absolute path of a weights file (whether it exists or not)."""
    return get_weight(wid).path


def missing_weights(ids: Iterable[str]) -> str | None:
    """None if every file is there (with the right size); otherwise what is missing
    and how to get it."""
    problems = []
    for wid in ids:
        w = get_weight(wid)
        if w.present():
            continue
        state = "has the wrong size" if w.path.is_file() else "not found"
        if w.url:
            how = "get it with:  uv run degfw weights --download"
        else:
            how = "it is in git, restore it with:  git checkout -- " + w.path.relative_to(PROJECT_ROOT).as_posix()
        problems.append(f"model weights {wid!r} {state}: {w.path}\n  {how}")
    return "\n".join(problems) or None


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def status(w: Weight, verify: bool = False) -> str:
    """'missing', 'wrong size', 'present' (size right, hash not checked),
    'ok' (hash checked) or 'SHA-256 mismatch'."""
    if not w.path.is_file():
        return "missing"
    if w.path.stat().st_size != w.size:
        return "wrong size"
    if not verify:
        return "present"
    return "ok" if sha256_of(w.path) == w.sha256 else "SHA-256 mismatch"


def download(w: Weight, progress: Callable[[int, int], None] | None = None) -> None:
    """Download w.url to w.path. The data goes to a temporary file next to it and is
    moved into place only if size and SHA-256 match weights.yaml, so an interrupted or
    wrong download never leaves a broken file at w.path."""
    if not w.url:
        raise ValueError(f"{w.id} has no url in {MANIFEST.name} (it is in git)")
    w.path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=w.path.parent, prefix=w.path.name + ".", suffix=".part")
    try:
        digest, done = hashlib.sha256(), 0
        with os.fdopen(fd, "wb") as f, urllib.request.urlopen(w.url, timeout=TIMEOUT) as response:
            total = int(response.headers.get("Content-Length") or w.size)
            while chunk := response.read(CHUNK):
                f.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        if done != w.size or digest.hexdigest() != w.sha256:
            raise ValueError(f"{w.id}: the download does not match {MANIFEST.name} "
                             f"(got {done} bytes, SHA-256 {digest.hexdigest()})")
        os.replace(tmp, w.path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
