"""Base class shared by every degradation."""

from __future__ import annotations

import importlib.util
from typing import Any, ClassVar

import numpy as np

from .context import Context
from .params import Param

# Where a degradation acts: on the whole image (e.g. fog) or on a part of it (e.g. a
# raindrop on the lens). The GUI groups its menu by this; every degradation declares one.
SCOPES = ("global", "local")


class Degradation:
    """Unified interface for one kind of degradation.

    Subclasses set ``name`` / ``label`` / ``scope`` / ``params`` and implement ``apply``.

    Image convention: float32, shape (H, W, 3), RGB, values in [0, 1].
    Parameters may not be called image, rng or context (the arguments of ``apply``).
    """

    name: ClassVar[str] = ""          # unique id used in configs, e.g. "fog"
    label: ClassVar[str] = ""         # display name in the GUI (English)
    description: ClassVar[str] = ""   # one sentence (English), shown in the GUI
    scope: ClassVar[str] = ""         # "global" (whole image) or "local" (part of it), see SCOPES
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

    @classmethod
    def describe(cls, info: dict[str, Any]) -> str:
        """One line for people about what this degradation recorded in context.info for
        an image (the GUI shows it per image). Default: key=value pairs; override to say
        it better."""
        return ", ".join(f"{k}={v}" for k, v in info.items())

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

    def apply(self, image: np.ndarray, rng: np.random.Generator, context: Context,
              **params: Any) -> np.ndarray:
        """Return the degraded image. Must not modify ``image`` in place.

        ``rng`` is the only source of randomness allowed, so results are
        reproducible from the seed. ``context``: what is known about the image besides
        its pixels (source file, the run's other images, ...; see core/context.py);
        most degradations ignore it.
        """
        raise NotImplementedError

    def __call__(self, image: np.ndarray, rng: np.random.Generator | None = None,
                 context: Context | None = None, **params: Any) -> np.ndarray:
        rng = rng if rng is not None else np.random.default_rng()
        context = context if context is not None else Context()
        out = self.apply(image, rng, context, **self.resolve_params(params))
        return np.clip(out.astype(np.float32, copy=False), 0.0, 1.0)
