"""TEMPLATE — copy this file to add a new degradation that wraps third_party code.

Steps:
  1. Copy into the right category folder, e.g. ``weather/fog.py``, and rename
     the class / ``name``.
  2. Fill in ``params`` (strength, type, ... — validated automatically).
  3. In ``apply``: convert the image to whatever the third-party code expects,
     call it, convert the result back to float32 RGB HxWx3 in [0, 1].
  4. Add ``from .weather import fog`` in ``degradations/__init__.py``.

This file is NOT imported, so it is not registered.
"""

from __future__ import annotations

import numpy as np

from degradation_fw.core.base import Degradation
from degradation_fw.core.params import Choice, Float, Int
from degradation_fw.core.paths import use_third_party  # noqa: F401
from degradation_fw.core.registry import register

# Third-party code lives under <repo>/third_party/<name>/, for example:
#
#   use_third_party("fog_xxx")          # adds third_party/fog_xxx to sys.path
#   from fog_model import add_fog       # import exactly as the original repo does


@register
class MyDegradation(Degradation):
    name = "my_degradation"            # unique id, used in YAML configs
    label = "显示名称 Display name"     # shown in the GUI
    description = "One-line description."
    params = {
        "strength": Float(default=0.5, min=0.0, max=1.0, step=0.01, label="强度"),
        "count": Int(default=10, min=0, max=200, label="数量"),
        "mode": Choice(default="a", choices=("a", "b"), label="模式"),
    }

    def apply(self, image: np.ndarray, rng: np.random.Generator, strength, count, mode):
        # --- convert to the third-party format (example: BGR uint8) ---
        # bgr_u8 = (image[..., ::-1] * 255).astype(np.uint8)
        #
        # --- call it. Pass `rng` or a seed derived from it, e.g.
        #     seed = int(rng.integers(2**31)), instead of letting it use
        #     global randomness, so results stay reproducible. ---
        # out = add_fog(bgr_u8, density=strength, seed=seed)
        #
        # --- convert back ---
        # return out[..., ::-1].astype(np.float32) / 255.0
        raise NotImplementedError
