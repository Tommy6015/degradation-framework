"""Chain several degradations and process single images or whole folders.

A pipeline config looks like (YAML / JSON / dict)::

    seed: 0
    steps:
      - name: gaussian_noise
        params: {sigma: 0.05}
      - name: fog
        params: {visibility: 50}
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import yaml

from . import registry
from .io import list_images, load_image, save_image, unique_stems


def image_seed(seed: int, rel_path: str | Path) -> int:
    """Seed of one image in a folder run, derived from the run's seed and the image's
    path relative to the folder ('/' separators). It does not depend on which other
    images are in the folder, and runs with different seeds get unrelated seeds.
    (It used to be seed + index: one image more or less shifted the seeds of all later
    images, and image k+1 of the run with seed 0 had the same seed as image k of the
    run with seed 1.) 63-bit; recorded in each image's .json, so one image can be redone
    with run_file(..., seed=that)."""
    key = unicodedata.normalize("NFC", Path(rel_path).as_posix()).encode("utf-8")
    words = np.frombuffer(hashlib.sha256(key).digest()[:16], dtype="<u4")
    state = np.random.SeedSequence([int(seed), *(int(w) for w in words)]).generate_state(1, dtype=np.uint64)
    return int(state[0] >> np.uint64(1))


@dataclass
class Step:
    name: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Pipeline:
    steps: list[Step] = field(default_factory=list)
    seed: int | None = None

    # ---- construction -------------------------------------------------
    @classmethod
    def from_dict(cls, cfg: dict[str, Any]) -> "Pipeline":
        steps = [Step(s["name"], dict(s.get("params") or {})) for s in cfg.get("steps", [])]
        return cls(steps=steps, seed=cfg.get("seed"))

    @classmethod
    def from_file(cls, path: str | Path) -> "Pipeline":
        text = Path(path).read_text(encoding="utf-8")
        return cls.from_dict(yaml.safe_load(text) or {})

    def to_dict(self) -> dict[str, Any]:
        return {"seed": self.seed,
                "steps": [{"name": s.name, "params": s.params} for s in self.steps]}

    def save(self, path: str | Path) -> None:
        Path(path).write_text(yaml.safe_dump(self.to_dict(), allow_unicode=True, sort_keys=False),
                              encoding="utf-8")

    # ---- running ------------------------------------------------------
    def run(self, image: np.ndarray, seed: int | None = None) -> tuple[np.ndarray, dict[str, Any]]:
        """Apply all steps. Returns (image, metadata) where metadata records
        the fully resolved params and the seed, enough to reproduce the result."""
        if seed is None:
            seed = self.seed if self.seed is not None else int(np.random.SeedSequence().entropy % 2**32)
        # One independent child stream per step: changing one step's params
        # does not change the randomness of the others.
        children = np.random.SeedSequence(seed).spawn(len(self.steps))
        out = image
        applied = []
        for step, ss in zip(self.steps, children):
            deg = registry.get(step.name)
            params = deg.resolve_params(step.params)
            out = deg(out, np.random.default_rng(ss), **params)
            applied.append({"name": step.name, "params": params})
        return out, {"seed": seed, "steps": applied}

    def run_file(self, src: str | Path, dst: str | Path, seed: int | None = None) -> dict[str, Any]:
        out, meta = self.run(load_image(src), seed=seed)
        dst = Path(dst)
        save_image(out, dst)
        meta = {"source": str(src), **meta}
        dst.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False),
                                            encoding="utf-8")
        return meta

    def run_folder(self, src_dir: str | Path, dst_dir: str | Path,
                   progress: Callable[[int, int, Path], None] | None = None) -> list[Path]:
        """Process every image under src_dir, keeping the sub-folder layout.

        Each image gets the seed image_seed(pipeline seed, its path relative to src_dir),
        or a random one if the pipeline has no seed; the seed used is in its .json.
        Results are .png: two images of one folder with the same stem (a.jpg, a.png)
        give a.png and a_2.png instead of overwriting each other.
        """
        src_dir, dst_dir = Path(src_dir), Path(dst_dir)
        files = list_images(src_dir)
        rels = [f.relative_to(src_dir) for f in files]
        dsts = [Path()] * len(files)
        by_folder: dict[str, list[int]] = {}
        for i, rel in enumerate(rels):
            by_folder.setdefault(rel.parent.as_posix().lower(), []).append(i)
        for idx in by_folder.values():
            for i, stem in zip(idx, unique_stems([rels[i] for i in idx])):
                dsts[i] = dst_dir / rels[i].parent / f"{stem}.png"
        outputs = []
        for i, (f, rel, dst) in enumerate(zip(files, rels, dsts)):
            seed = None if self.seed is None else image_seed(self.seed, rel)
            self.run_file(f, dst, seed=seed)
            outputs.append(dst)
            if progress:
                progress(i + 1, len(files), f)
        return outputs
