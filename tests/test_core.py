"""Framework core: registry, params, pipeline, image I/O."""

import json

import numpy as np
import pytest
from PIL import Image

from degradation_fw import Degradation, Float, Folder, Pipeline, Step, available, get, register
from degradation_fw.core.io import load_image, save_image, unique_stems
from degradation_fw.core.pipeline import image_seed


def folder_seeds(p, src, dst):
    """{output file name: seed recorded in its .json} of one run_folder call."""
    return {o.name: json.loads(o.with_suffix(".json").read_text(encoding="utf-8"))["seed"]
            for o in p.run_folder(src, dst)}


def test_registry_lists_degradations():
    assert {"test_noise", "test_context", "fog"} <= set(available())


def test_register_rejects_reserved_param_names():
    """apply(image, rng, context, **params): a parameter may not take one of these names."""
    for reserved in ("image", "rng", "context"):
        cls = type("Bad", (Degradation,), {"name": f"bad_{reserved}", "label": "bad", "scope": "global",
                                          "params": {reserved: Float()}})
        with pytest.raises(ValueError, match="reserved"):
            register(cls)
    assert not {"bad_image", "bad_rng", "bad_context"} & set(available())


def test_register_rejects_a_missing_or_unknown_scope():
    for scope in ("", "Global", "sensor"):
        cls = type("Bad", (Degradation,), {"name": "bad_scope", "label": "bad", "scope": scope})
        with pytest.raises(ValueError, match="scope must be one of"):
            register(cls)
    assert "bad_scope" not in available()


def test_param_validation():
    deg = get("test_noise")
    with pytest.raises(ValueError):
        deg.resolve_params({"sigma": 99})
    with pytest.raises(KeyError):
        deg.resolve_params({"not_a_param": 1})


def test_pipeline_seed_reproducible(image):
    p = Pipeline([Step("test_noise", {"sigma": 0.1})])
    a, meta = p.run(image, seed=5)
    b, _ = p.run(image, seed=meta["seed"])
    np.testing.assert_array_equal(a, b)
    assert meta["steps"][0]["params"] == {"sigma": 0.1, "per_channel": True}


def test_pipeline_config_roundtrip(tmp_path):
    p = Pipeline([Step("test_noise", {"sigma": 0.2})], seed=3)
    path = tmp_path / "cfg.yaml"
    p.save(path)
    assert Pipeline.from_file(path).to_dict() == p.to_dict()


def test_run_folder_writes_images_and_metadata(tmp_path, image):
    src = tmp_path / "in" / "子目录"   # non-ASCII path on purpose
    save_image(image, src / "a.png")
    save_image(image, src / "b.jpg")
    p = Pipeline([Step("test_noise")], seed=0)
    outs = p.run_folder(tmp_path / "in", tmp_path / "out")
    assert len(outs) == 2
    for o in outs:
        assert load_image(o).shape == image.shape
        meta = json.loads(o.with_suffix(".json").read_text(encoding="utf-8"))
        assert meta["steps"][0]["name"] == "test_noise"


def test_folder_seeds_do_not_depend_on_other_images(tmp_path, image):
    src = tmp_path / "in"
    save_image(image, src / "a.png")
    save_image(image, src / "c.png")
    p = Pipeline([Step("test_noise")], seed=0)
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
    p = Pipeline([Step("test_noise")], seed=0)
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
    outs = Pipeline([Step("test_noise", {"sigma": 0.0})], seed=0).run_folder(src, tmp_path / "out")
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


# ---- what a degradation knows besides the pixels: its context (decision 0010) ------
def recorded_info(outputs):
    """{output file name: the first step's info from its .json}"""
    return {o.name: json.loads(o.with_suffix(".json").read_text(encoding="utf-8"))["steps"][0]["info"]
            for o in outputs}


def test_context_of_a_folder_run(tmp_path, image):
    """Each image knows its source file and all input files of the run; context.shared
    lasts for the whole run (one count over all images) and starts empty in the next run;
    what the degradation puts into context.info is in the image's .json."""
    src = tmp_path / "in"
    for name in ("a.png", "b.png", "sub/c.png"):
        save_image(image, src / name)
    p = Pipeline([Step("test_context")], seed=0)
    for run in ("out1", "out2"):
        info = recorded_info(p.run_folder(src, tmp_path / run))
        assert {n: i["source"] for n, i in info.items()} == {"a.png": "a.png", "b.png": "b.png", "c.png": "c.png"}
        assert all(i["batch"] == ["a.png", "b.png", "c.png"] for i in info.values())
        assert sorted(i["seen"] for i in info.values()) == [1, 2, 3]


def test_context_of_one_file_and_of_an_image_in_memory(tmp_path, image):
    save_image(image, tmp_path / "a.png")
    p = Pipeline([Step("test_context")], seed=0)
    meta = p.run_file(tmp_path / "a.png", tmp_path / "out.png")
    assert meta["steps"][0]["info"] == {"source": "a.png", "batch": ["a.png"], "seen": 1, "folder": ""}
    out, meta = p.run(image, seed=0)  # e.g. a preview: no file
    assert meta["steps"][0]["info"] == {"source": None, "batch": [], "seen": 1, "folder": ""}
    np.testing.assert_array_equal(out, image)
    # called directly, without a pipeline
    np.testing.assert_array_equal(get("test_context")(image), image)


def test_each_step_has_its_own_shared_state(tmp_path, image):
    save_image(image, tmp_path / "a.png")
    meta = Pipeline([Step("test_context"), Step("test_context")], seed=0).run_file(
        tmp_path / "a.png", tmp_path / "out.png")
    assert [s["info"]["seen"] for s in meta["steps"]] == [1, 1]


def test_steps_without_info_record_none(image):
    _, meta = Pipeline([Step("test_noise")], seed=0).run(image)
    assert "info" not in meta["steps"][0]


def test_folder_param(tmp_path):
    spec = Folder()
    assert spec.validate("") == "" and spec.validate(None) == ""
    assert spec.validate(str(tmp_path)) == str(tmp_path)
    assert spec.validate(f"  {tmp_path}  ") == str(tmp_path)
    with pytest.raises(ValueError, match="folder not found"):
        spec.validate(str(tmp_path / "missing"))
    (tmp_path / "a.png").write_bytes(b"")
    with pytest.raises(ValueError, match="folder not found"):  # a file is not a folder
        spec.validate(str(tmp_path / "a.png"))
