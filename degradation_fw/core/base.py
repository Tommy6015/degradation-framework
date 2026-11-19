"""Base class shared by every degradation."""

from __future__ import annotations

import importlib.util
from typing import Any, ClassVar

import numpy as np

from .params import Param


class Degradation:
    """Unified interface for one kind of degradation.

    Subclasses set ``name`` / ``label`` / ``params`` and implement ``apply``.

    Image convention: float32, shape (H, W, 3), RGB, values in [0, 1].
    """

    name: ClassVar[str] = ""          # unique id used in configs, e.g. "fog"
    label: ClassVar[str] = ""         # display name in the GUI
    description: ClassVar[str] = ""
    params: ClassVar[dict[str, Param]] = {}

    # What it needs to run, checked by unavailable_reason(): if something is missing,
    # `degfw list` says so and its tests are skipped, instead of failing.
    requires_modules: ClassVar[tuple[str, ...]] = ()  # top-level modules, from its dependency group
    requires_weights: ClassVar[tuple[str, ...]] = ()  # ids in third_party/weights.yaml

    @classmethod
    def unavailable_reason(cls) -> str | None:
        """None if the degradation can run here; otherwise why not. Checks
        requires_modules and requires_weights; override to check more."""
        missing = [m for m in cls.requires_modules if importlib.util.find_spec(m) is None]
        if missing:
            return (f"Python packages not installed: {', '.join(missing)} "
                    "(uv sync installs every dependency group)")
        if cls.requires_weights:
            from .weights import missing_weights

            return missing_weights(cls.requires_weights)
        return None

    def resolve_params(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        """Fill in defaults and validate. Unknown keys raise an error."""
        overrides = dict(overrides or {})
        unknown = set(overrides) - set(self.params)
        if unknown:
            raise KeyError(f"{self.name}: unknown params {sorted(unknown)}")
        resolved = {}
        for key, spec in self.params.items():
            value = overrides.get(key, spec.default)
            try:
                resolved[key] = spec.validate(value)
            except ValueError as e:
                raise ValueError(f"{self.name}.{key}: {e}") from None
        return resolved

    def apply(self, image: np.ndarray, rng: np.random.Generator, **params: Any) -> np.ndarray:
        """Return the degraded image. Must not modify ``image`` in place.

        ``rng`` is the only source of randomness allowed, so results are
        reproducible from the seed.
        """
        raise NotImplementedError

    def __call__(self, image: np.ndarray, rng: np.random.Generator | None = None,
                 **params: Any) -> np.ndarray:
        rng = rng if rng is not None else np.random.default_rng()
        out = self.apply(image, rng, **self.resolve_params(params))
        return np.clip(out.astype(np.float32, copy=False), 0.0, 1.0)
