"""What the GUI does, without gradio: the menu from the registry, checking the folders,
preview and generation. app.py only lays it out, so all of this is tested without the
GUI installed (tests/test_gui_logic.py).

Generation is the framework's usual folder run (Pipeline.run_folder, like degfw run):
the same code and the same results as on the command line, a .png and a .json per image
and the run's pipeline.yaml in the output folder (degfw apply -c that file repeats it).
The preview computes one image exactly as the generation does: same seed, and the whole
input folder as the run's images (the fog's average atmospheric light depends on it).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ..core import registry
from ..core.base import SCOPES
from ..core.io import IMAGE_EXTS, list_images, load_image
from ..core.pipeline import Pipeline, Step, image_seed

SCOPE_LABELS = {"global": "Global (whole image)", "local": "Local (part of the image)"}
SEED = 0  # the run's seed; per image: image_seed(SEED, relative path), as in degfw run --seed 0


@dataclass(frozen=True)
class Check:
    """Result of checking an input: level "ok", "warning" (can go on) or "error" (cannot)."""

    level: str
    message: str

    @property
    def ok(self) -> bool:
        return self.level != "error"

    def markdown(self) -> str:
        return {"ok": "✓ ", "warning": "⚠ ", "error": "✗ "}[self.level] + self.message


# ---- menu ---------------------------------------------------------------------------
def menu(names: list[str] | None = None) -> dict[str, list[tuple[str, str]]]:
    """{scope: [(label, name), ...]} for every scope in SCOPES, in registry order; a scope
    without degradations gets []. names: which degradations (default: all registered)."""
    names = registry.available() if names is None else names
    groups: dict[str, list[tuple[str, str]]] = {scope: [] for scope in SCOPES}
    for name in names:
        deg = registry.get(name)
        groups[deg.scope].append((deg.label or name, name))
    return groups


def check_degradation(name: str | None) -> Check:
    if not name:
        return Check("error", "Choose a degradation.")
    reason = registry.get(name).unavailable_reason()
    if reason:
        return Check("error", f"Cannot run on this machine: {reason}")
    return Check("ok", registry.get(name).description or name)


def resolve(name: str, values: dict[str, Any]) -> dict[str, Any]:
    """The degradation's parameters from the controls' values, checked; ValueError with a
    readable message if one is out of range."""
    try:
        return registry.get(name).resolve_params(values)
    except (KeyError, ValueError) as e:
        raise ValueError(str(e.args[0])) from None


# ---- folders ----------------------------------------------------------------------
def scan_input(folder: str) -> tuple[list[Path], Check]:
    """The images under the input folder, subfolders included (as degfw run), and what
    to tell the user."""
    folder = (folder or "").strip()
    if not folder:
        return [], Check("error", "Choose the folder with the input images.")
    path = Path(folder)
    if not path.is_dir():
        return [], Check("error", f"Folder not found: {folder}")
    images = list_images(path)
    if not images:
        return [], Check("error", "No images in this folder or its subfolders "
                                  f"(supported: {' '.join(sorted(IMAGE_EXTS))}).")
    in_subfolders = sum(1 for p in images if p.parent != path)
    return images, Check("ok", f"{len(images)} image(s)"
                               + (f", {in_subfolders} of them in subfolders" if in_subfolders else "") + ".")


def check_output(output: str, input_folder: str = "") -> Check:
    output = (output or "").strip()
    if not output:
        return Check("error", "Choose the folder for the results.")
    out = Path(output).resolve()
    if (input_folder or "").strip():
        inp = Path(input_folder.strip()).resolve()
        if out == inp or inp in out.parents:
            return Check("error", "The output folder must not be the input folder or inside it: results "
                                  "would replace input images of the same name, or be read as input next time.")
    if out.exists() and not out.is_dir():
        return Check("error", f"Not a folder: {output}")
    if out.is_dir() and any(out.iterdir()):
        return Check("warning", "This folder is not empty: results with the same names will be overwritten.")
    return Check("ok", "Empty folder." if out.is_dir() else "New folder, created when generating.")


def relative_names(images: list[Path], folder: str) -> list[str]:
    """Image paths relative to the input folder, as shown in the preview's list."""
    root = Path(folder.strip())
    return [p.relative_to(root).as_posix() for p in images]


# ---- preview and generation -----------------------------------------------------------
def _pipeline(name: str, params: dict[str, Any]) -> Pipeline:
    return Pipeline([Step(name, params)], seed=SEED)


def describe(name: str, step_meta: dict[str, Any]) -> str:
    info = step_meta.get("info")
    return registry.get(name).describe(info) if info else ""


@dataclass
class Preview:
    original: np.ndarray  # float32 RGB [0, 1]
    result: np.ndarray    # float32 RGB [0, 1]; to_uint8(result) is what generate() writes
    notes: str
    seconds: float


def preview(name: str, params: dict[str, Any], input_folder: str, relative: str) -> Preview:
    """One input image as generate() makes it: same seed (from its relative path) and
    the whole input folder as the run's images."""
    images, check = scan_input(input_folder)
    if not check.ok:
        raise ValueError(check.message)
    root = Path(input_folder.strip())
    source = root / relative
    if source not in images:
        raise ValueError(f"Not an image of the input folder: {relative}")
    t = time.time()
    original = load_image(source)
    result, meta = _pipeline(name, params).run(original, seed=image_seed(SEED, source.relative_to(root)),
                                               source=source, batch=tuple(images))
    return Preview(original, result, describe(name, meta["steps"][0]), time.time() - t)


@dataclass
class Generated:
    output_folder: Path
    rows: list[list[str]] = field(default_factory=list)  # [input, output, notes] per image
    seconds: float = 0.0

    def summary(self) -> str:
        return (f"Done: {len(self.rows)} image(s) in {self.seconds:.1f} s → `{self.output_folder}` "
                "(a .json per image, and pipeline.yaml to repeat the run with degfw apply).")


def generate(name: str, params: dict[str, Any], input_folder: str, output_folder: str,
             progress: Callable[[int, int, Path], None] | None = None) -> Generated:
    """Degrade every image of the input folder into the output folder, as degfw run does."""
    images, check = scan_input(input_folder)
    if not check.ok:
        raise ValueError(check.message)
    out_check = check_output(output_folder, input_folder)
    if not out_check.ok:
        raise ValueError(out_check.message)
    src, dst = Path(input_folder.strip()), Path(output_folder.strip())
    pipeline = _pipeline(name, params)
    t = time.time()
    dst.mkdir(parents=True, exist_ok=True)
    pipeline.save(dst / "pipeline.yaml")
    outputs = pipeline.run_folder(src, dst, progress=progress)
    result = Generated(dst, seconds=time.time() - t)
    for out in outputs:
        meta = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
        result.rows.append([Path(meta["source"]).relative_to(src).as_posix(), out.relative_to(dst).as_posix(),
                            describe(name, meta["steps"][0])])
    return result
