import json

import numpy as np
import pytest

from degradation_fw import Pipeline, Step, available, get
from degradation_fw.core.io import load_image, save_image


@pytest.fixture
def image():
    rng = np.random.default_rng(123)
    return rng.random((32, 48, 3), dtype=np.float32)


def test_registry_lists_example():
    assert "gaussian_noise" in available()


def usable(name):
    """get(name), or skip the test if it can't run here (e.g. model weights missing)."""
    deg = get(name)
    reason = deg.unavailable_reason()
    if reason:
        pytest.skip(f"{name}: {reason}")
    return deg


@pytest.mark.parametrize("name", available())
def test_every_degradation_follows_contract(name, image):
    """Each registered degradation keeps shape/dtype/range and doesn't modify input."""
    deg = usable(name)
    original = image.copy()
    out = deg(image, np.random.default_rng(0))
    assert out.shape == image.shape
    assert out.dtype == np.float32
    assert out.min() >= 0.0 and out.max() <= 1.0
    np.testing.assert_array_equal(image, original)


@pytest.mark.parametrize("name", available())
def test_every_degradation_is_reproducible(name, image):
    deg = usable(name)
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
    gr = pytest.importorskip("gradio")  # GUI is optional
    if not hasattr(gr, "Blocks"):
        # gradio writes hash_seed.txt into its package dir at runtime; after
        # uninstalling, that leftover dir still imports as an empty namespace
        pytest.skip("gradio not installed (only a leftover package dir)")
    from degradation_fw.gui.app import build_app
    build_app()


def test_fog_denser_at_lower_visibility():
    """Clear2Fog: lower visibility -> more fog -> less contrast left in the image."""
    fog = usable("fog")
    rng = np.random.default_rng(0)
    # a simple scene: sky-like bright top half, textured bottom half
    img = np.concatenate([np.full((48, 96, 3), 0.85, np.float32),
                          rng.random((48, 96, 3), dtype=np.float32) * 0.6], axis=0)
    contrast = [fog(img, visibility=v).std() for v in (500, 100, 20)]
    assert contrast[0] > contrast[1] > contrast[2]
