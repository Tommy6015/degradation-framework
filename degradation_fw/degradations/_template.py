"""TEMPLATE — copy this file to add a new degradation that wraps third_party code.

Steps:
  1. Copy to e.g. ``fog.py`` and rename the class / ``name``.
  2. Fill in ``params`` (they become GUI controls automatically).
  3. In ``apply``: convert the image to whatever the third-party code expects,
     call it, convert the result back to float32 RGB HxWx3 in [0, 1].
  4. Add ``from . import fog`` in ``degradations/__init__.py``.

This file is NOT imported, so it does not appear in the GUI.
"""

from __future__ import annotations

import numpy as np

from ..base import Degradation
from ..params import Choice, Float, Int
from ..registry import register

# Third-party code lives under <repo>/third_party/<name>/. Import it however
# that project is laid out, for example:
#
#   import sys
#   from pathlib import Path
#   sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "third_party" / "fog_xxx"))
#   from fog_xxx import add_fog


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
