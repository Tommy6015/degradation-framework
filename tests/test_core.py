"""Framework core: registry, params, pipeline, image I/O."""

import json

import numpy as np
import pytest

from degradation_fw import Pipeline, Step, available, get
from degradation_fw.core.io import load_image, save_image


def test_registry_lists_example():
    assert "gaussian_noise" in available()


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
