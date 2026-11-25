"""TEMPLATE — copy this file to add a new degradation that wraps third_party code.

Steps:
  1. Vendor the code into third_party/<repo>/ (see third_party/README.md). Copy this
     file into the right category folder, e.g. ``weather/rain.py``, and rename the
     class and ``name``.
  2. Dependencies: one group for the repo in pyproject.toml ([dependency-groups]),
     then ``uv lock``. Model weights: one entry per file in third_party/weights.yaml,
     then ``uv run degfw weights --download``.
  3. Declare both in ``requires_modules`` / ``requires_weights``: if something is
     missing, ``degfw list`` says why and the tests skip it, instead of failing.
  4. Load the third-party code lazily, inside a function (``_model`` below), never at
     the top of this file: every adapter is imported at start-up (degfw, the GUI, the
     tests), so one heavy or broken import here would slow down or break all of them.
     Load it only with the functions in core/paths.py:
       import_third_party_package(repo, package)   package with relative imports
       use_third_party(repo, modules)              modules that import each other by name
       working_dir(folder)                         code that opens files relative to the cwd
  5. Fill in ``params``. In ``apply``: convert the image to what the code expects,
     call it, convert the result back to float32 RGB HxWx3 in [0, 1]. ``context``
     (core/context.py) says where the image comes from: its source file, the run's
     other input files, a dict kept for the whole run (for what is computed once per
     run), and ``context.info`` for what to record in the image's .json. Most
     degradations ignore it; weather/fog.py uses all of it.
  6. Register it: ``from .weather import rain`` in degradations/__init__.py. Then
     ``degfw run rain -i IN -o OUT -p key=value`` works and the generic tests check it;
     put its own tests in tests/degradations/test_rain.py.
  7. Only if it needs a command of its own (most don't): register_command(...), as in
     weather/fog.py.

This file is NOT imported, so it is not registered.
"""

from __future__ import annotations

import numpy as np

from degradation_fw.core.base import Degradation
from degradation_fw.core.params import Choice, Float, Int
from degradation_fw.core.paths import use_third_party
from degradation_fw.core.registry import register
from degradation_fw.core.weights import weight_path

REPO = "my_repo"  # folder in third_party/

_MODEL = None


def _model():
    """The third-party model, loaded on first use and then kept (load it only once)."""
    global _MODEL
    if _MODEL is None:
        # e.g. third_party/my_repo/my_model.py, which itself does `import my_utils`
        use_third_party(REPO, modules=["my_model", "my_utils"])
        import my_model

        _MODEL = my_model.load(weight_path("my_model_weights"))
    return _MODEL


@register
class MyDegradation(Degradation):
    name = "my_degradation"            # unique id, used in configs and `degfw run`
    label = "显示名称 Display name"     # shown in the GUI
    description = "One-line description."
    requires_modules = ("torch", "cv2")         # from its dependency group
    requires_weights = ("my_model_weights",)    # ids in third_party/weights.yaml
    params = {
        "strength": Float(default=0.5, min=0.0, max=1.0, step=0.01, label="强度"),
        "count": Int(default=10, min=0, max=200, label="数量"),
        "mode": Choice(default="a", choices=("a", "b"), label="模式"),
    }

    def apply(self, image: np.ndarray, rng: np.random.Generator, context, strength, count, mode):
        model = _model()
        # --- convert to the third-party format (example: BGR uint8) ---
        bgr_u8 = (image[..., ::-1] * 255 + 0.5).astype(np.uint8)
        # --- call it. Pass `rng` or a seed drawn from it instead of letting it use
        #     global randomness, so results stay reproducible from the seed. ---
        out = model.add_effect(bgr_u8, strength=strength, count=count, mode=mode,
                               seed=int(rng.integers(2**31)))
        # --- convert back ---
        return out[..., ::-1].astype(np.float32) / 255.0
