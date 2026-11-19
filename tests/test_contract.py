"""Checks every registered degradation must pass. New degradations are picked up
automatically; those that need model weights are marked slow."""

import numpy as np
import pytest

from degradation_fw import available, get
from degradation_fw.core.weights import manifest


def _cases():
    return [pytest.param(n, marks=pytest.mark.slow) if get(n).requires_weights else n for n in available()]


@pytest.mark.parametrize("name", _cases())
def test_every_degradation_follows_contract(name, image, usable):
    """Keeps shape / dtype / range and doesn't modify its input."""
    deg = usable(name)
    original = image.copy()
    out = deg(image, np.random.default_rng(0))
    assert out.shape == image.shape
    assert out.dtype == np.float32
    assert out.min() >= 0.0 and out.max() <= 1.0
    np.testing.assert_array_equal(image, original)


@pytest.mark.parametrize("name", _cases())
def test_every_degradation_is_reproducible(name, image, usable):
    deg = usable(name)
    a = deg(image, np.random.default_rng(7))
    b = deg(image, np.random.default_rng(7))
    np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("name", available())
def test_every_degradation_declares_itself(name):
    """Label set, defaults valid, and every requires_weights id is in weights.yaml."""
    deg = get(name)
    assert deg.name == name and deg.label
    for spec in deg.params.values():
        spec.validate(spec.default)
    unknown = set(deg.requires_weights) - set(manifest())
    assert not unknown, f"{name}: requires_weights not in third_party/weights.yaml: {sorted(unknown)}"
