import json

import numpy as np
import pytest

from degradation_fw import Pipeline, Step, available, get
from degradation_fw.io import load_image, save_image


@pytest.fixture
def image():
    rng = np.random.default_rng(123)
    return rng.random((32, 48, 3), dtype=np.float32)


def test_registry_lists_example():
    assert "gaussian_noise" in available()


@pytest.mark.parametrize("name", available())
def test_every_degradation_follows_contract(name, image):
    """Each registered degradation keeps shape/dtype/range and doesn't modify input."""
    deg = get(name)
    original = image.copy()
    out = deg(image, np.random.default_rng(0))
    assert out.shape == image.shape
    assert out.dtype == np.float32
    assert out.min() >= 0.0 and out.max() <= 1.0
    np.testing.assert_array_equal(image, original)


@pytest.mark.parametrize("name", available())
def test_every_degradation_is_reproducible(name, image):
    deg = get(name)
    a = deg(image, np.random.default_rng(7))
    b = deg(image, np.random.default_rng(7))
    np.testing.assert_array_equal(a, b)


def test_param_validation():
    deg = get("gaussian_noise")
    with pytest.raises(ValueError):
        deg.resolve_params({"sigma": 99})
    with pytest.raises(KeyError):
        deg.resolve_params({"not_a_param": 1})


def test_pipeline_seed_reproducible(image):
    p = Pipeline([Step("gaussian_noise", {"sigma": 0.1})])
    a, meta = p.run(image, seed=5)
    b, _ = p.run(image, seed=meta["seed"])
    np.testing.assert_array_equal(a, b)
    assert meta["steps"][0]["params"] == {"sigma": 0.1, "per_channel": True}


def test_pipeline_config_roundtrip(tmp_path):
    p = Pipeline([Step("gaussian_noise", {"sigma": 0.2})], seed=3)
    path = tmp_path / "cfg.yaml"
    p.save(path)
    assert Pipeline.from_file(path).to_dict() == p.to_dict()


def test_run_folder_writes_images_and_metadata(tmp_path, image):
    src = tmp_path / "in" / "子目录"   # non-ASCII path on purpose
    save_image(image, src / "a.png")
    save_image(image, src / "b.jpg")
    p = Pipeline([Step("gaussian_noise")], seed=0)
    outs = p.run_folder(tmp_path / "in", tmp_path / "out")
    assert len(outs) == 2
    for o in outs:
        assert load_image(o).shape == image.shape
        meta = json.loads(o.with_suffix(".json").read_text(encoding="utf-8"))
        assert meta["steps"][0]["name"] == "gaussian_noise"


def test_gui_builds():
    from degradation_fw.gui.app import build_app
    build_app()
