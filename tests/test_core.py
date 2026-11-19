"""Framework core: registry, params, pipeline, image I/O."""

import json

import numpy as np
import pytest
from PIL import Image

from degradation_fw import Pipeline, Step, available, get
from degradation_fw.core.io import load_image, save_image, unique_stems
from degradation_fw.core.pipeline import image_seed


def folder_seeds(p, src, dst):
    """{output file name: seed recorded in its .json} of one run_folder call."""
    return {o.name: json.loads(o.with_suffix(".json").read_text(encoding="utf-8"))["seed"]
            for o in p.run_folder(src, dst)}


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


def test_folder_seeds_do_not_depend_on_other_images(tmp_path, image):
    src = tmp_path / "in"
    save_image(image, src / "a.png")
    save_image(image, src / "c.png")
    p = Pipeline([Step("gaussian_noise")], seed=0)
    before = folder_seeds(p, src, tmp_path / "out1")
    save_image(image, src / "b.png")  # one more image, sorted between the two
    after = folder_seeds(p, src, tmp_path / "out2")
    assert after["a.png"] == before["a.png"] and after["c.png"] == before["c.png"]
    assert len(set(after.values())) == 3


def test_folder_seeds_of_different_runs_are_unrelated():
    names = [f"img{i:03d}.png" for i in range(50)]
    assert not {image_seed(0, n) for n in names} & {image_seed(1, n) for n in names}
    assert image_seed(0, "sub/a.png") == image_seed(0, "sub/a.png")


def test_recorded_seed_redoes_one_image(tmp_path, image):
    save_image(image, tmp_path / "in" / "a.png")
    p = Pipeline([Step("gaussian_noise")], seed=0)
    seed = folder_seeds(p, tmp_path / "in", tmp_path / "out")["a.png"]
    p.run_file(tmp_path / "in" / "a.png", tmp_path / "again.png", seed=seed)
    np.testing.assert_array_equal(load_image(tmp_path / "again.png"), load_image(tmp_path / "out" / "a.png"))


def test_unique_stems():
    assert unique_stems(["x/a.jpg", "y/A.png", "a_2.png", "b.png"]) == ["a", "A_2", "a_2_2", "b"]


def test_same_stem_in_one_folder_does_not_overwrite(tmp_path, image):
    src = tmp_path / "in"
    save_image(image, src / "a.png")
    save_image(image * 0.5, src / "a.jpg")
    save_image(image, src / "sub" / "a.png")  # another folder: keeps its plain name
    outs = Pipeline([Step("gaussian_noise", {"sigma": 0.0})], seed=0).run_folder(src, tmp_path / "out")
    assert sorted(o.relative_to(tmp_path / "out").as_posix() for o in outs) == ["a.png", "a_2.png", "sub/a.png"]
    sources = {json.loads(o.with_suffix(".json").read_text(encoding="utf-8"))["source"] for o in outs}
    assert len(sources) == 3  # each result has its own .json, pointing to its own input


def test_load_image_applies_exif_orientation(tmp_path):
    """A photo stored sideways with orientation tag 6 ("rotate 90° clockwise to view")
    is read upright: 40 x 30 stored -> 30 wide, 40 high; the stored left half on top."""
    stored = np.zeros((30, 40, 3), np.uint8)
    stored[:, :20] = (255, 0, 0)
    exif = Image.Exif()
    exif[0x0112] = 6
    Image.fromarray(stored).save(tmp_path / "portrait.jpg", exif=exif.tobytes(), quality=95)
    img = load_image(tmp_path / "portrait.jpg")
    assert img.shape == (40, 30, 3)
    assert img[:18, :, 0].mean() > 0.9 and img[22:, :, 0].mean() < 0.1
