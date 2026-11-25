"""Shared fixtures, and two small degradations that exist only in the tests.

Tests that run a model (GPU, weights from third_party/weights.yaml) are marked
``slow``. Quick run without them:  uv run pytest -m "not slow"

Layout: test_*.py here for the framework (core, CLI, third-party loading, GUI);
tests/degradations/test_<name>.py for one degradation each; tests/data/ for small
fixed input and reference images.
"""

from pathlib import Path

import numpy as np
import pytest

from degradation_fw import Bool, Degradation, Float, Folder, get, register

DATA_DIR = Path(__file__).parent / "data"


# ---- degradations for testing the framework itself (no GPU, no model) ---------------
# Registered here, so they also go through test_contract.py like the real ones.
@register
class NoiseForTests(Degradation):
    """Additive Gaussian noise: uses rng and has parameters with ranges."""

    name = "test_noise"
    label = "测试用噪声 Noise (tests only)"
    params = {
        "sigma": Float(default=0.05, min=0.0, max=0.5, step=0.005, label="sigma"),
        "per_channel": Bool(default=True, label="per channel"),
    }

    def apply(self, image, rng, context, sigma, per_channel):
        shape = image.shape if per_channel else image.shape[:2] + (1,)
        return image + rng.normal(0.0, sigma, size=shape).astype(np.float32)


@register
class ContextForTests(Degradation):
    """Leaves the image as it is and records what its context says: the source file,
    the run's input files, and how many images of the run it has seen so far (counted
    in context.shared, which lasts for the whole run)."""

    name = "test_context"
    label = "测试用来源信息 Context (tests only)"
    params = {"folder": Folder(label="a folder (optional)")}

    def apply(self, image, rng, context, folder):
        context.shared["seen"] = context.shared.get("seen", 0) + 1
        context.info.update(source=context.source.name if context.source else None,
                            batch=[p.name for p in context.batch], seen=context.shared["seen"],
                            folder=folder)
        return image.copy()


@pytest.fixture
def image():
    """Small random RGB float32 image."""
    rng = np.random.default_rng(123)
    return rng.random((32, 48, 3), dtype=np.float32)


@pytest.fixture
def data_dir() -> Path:
    """tests/data: small fixed images (inputs and reference outputs)."""
    return DATA_DIR


@pytest.fixture
def usable():
    """usable(name) -> the degradation, or skip the test if it cannot run here
    (missing Python package or model weights, see Degradation.unavailable_reason)."""

    def get_usable(name):
        deg = get(name)
        reason = deg.unavailable_reason()
        if reason:
            pytest.skip(f"{name}: {reason}")
        return deg

    return get_usable
