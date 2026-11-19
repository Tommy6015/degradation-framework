"""Shared fixtures.

Tests that run a model (GPU, weights from third_party/weights.yaml) are marked
``slow``. Quick run without them:  uv run pytest -m "not slow"

Layout: test_*.py here for the framework (core, CLI, third-party loading, GUI);
tests/degradations/test_<name>.py for one degradation each; tests/data/ for small
fixed input and reference images.
"""

from pathlib import Path

import numpy as np
import pytest

from degradation_fw import get

DATA_DIR = Path(__file__).parent / "data"


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
