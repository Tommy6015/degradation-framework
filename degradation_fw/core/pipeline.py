"""Chain several degradations and process single images or whole folders.

A pipeline config looks like (YAML / JSON / dict)::

    seed: 0
    steps:
      - name: gaussian_noise
        params: {sigma: 0.05}
      - name: fog
        params: {density: 0.6}
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import yaml

from . import registry
from .io import list_images, load_image, save_image


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

        Each image gets seed = pipeline seed + index (or random if seed is None).
        """
        src_dir, dst_dir = Path(src_dir), Path(dst_dir)
        files = list_images(src_dir)
        outputs = []
        for i, f in enumerate(files):
            seed = None if self.seed is None else self.seed + i
            dst = (dst_dir / f.relative_to(src_dir)).with_suffix(".png")
            self.run_file(f, dst, seed=seed)
            outputs.append(dst)
            if progress:
                progress(i + 1, len(files), f)
        return outputs
