"""What the GUI does (gui/logic.py), tested without gradio. Uses the test-only
degradations from conftest.py: test_noise (global, random) and test_context (local)."""

import json

import numpy as np
import pytest
from PIL import Image

from degradation_fw import Degradation, Pipeline, Step
from degradation_fw.core import registry
from degradation_fw.core.io import load_image, save_image, to_uint8
from degradation_fw.gui import logic


@pytest.fixture
def folder(tmp_path, image):
    """An input folder with three images, one in a subfolder."""
    src = tmp_path / "in"
    for i, name in enumerate(("a.png", "b.jpg", "sub/c.png")):
        save_image(np.clip(image + 0.1 * i, 0, 1), src / name)
    return src


def test_menu_groups_by_scope():
    groups = logic.menu()
    assert ("Fog (Clear2Fog)", "fog") in groups["global"] and ("Noise (tests only)", "test_noise") in groups["global"]
    assert groups["local"] == [("Context (tests only)", "test_context")]
    assert list(groups) == ["global", "local"]


def test_menu_has_every_scope_even_without_degradations():
    assert logic.menu(["fog"]) == {"global": [("Fog (Clear2Fog)", "fog")], "local": []}


def test_new_degradation_appears_in_the_menu(monkeypatch):
    """Registering a degradation is all it takes: no GUI code changes."""

    class Raindrop(Degradation):
        name, label, scope = "raindrop_for_test", "Raindrop (test)", "local"

    monkeypatch.setitem(registry._REGISTRY, Raindrop.name, Raindrop)
    assert ("Raindrop (test)", "raindrop_for_test") in logic.menu()["local"]


def test_check_degradation_says_why_it_cannot_run(monkeypatch):
    class NeedsMissingPackage(Degradation):
        name, label, scope = "needs_missing", "Needs a missing package", "global"
        requires_modules = ("no_such_module_xyz",)

    monkeypatch.setitem(registry._REGISTRY, NeedsMissingPackage.name, NeedsMissingPackage)
    check = logic.check_degradation("needs_missing")
    assert check.level == "error" and "no_such_module_xyz" in check.message
    assert logic.check_degradation("test_noise").ok
    assert not logic.check_degradation(None).ok


def test_scan_input(tmp_path, folder):
    images, check = logic.scan_input(f"  {folder}  ")
    assert [p.name for p in images] == ["a.png", "b.jpg", "c.png"] and check.ok
    assert check.message == "3 image(s), 1 of them in subfolders."
    assert logic.relative_names(images, str(folder)) == ["a.png", "b.jpg", "sub/c.png"]
    for value, expected in (("", "Choose the folder"), (str(tmp_path / "missing"), "Folder not found")):
        images, check = logic.scan_input(value)
        assert images == [] and check.level == "error" and expected in check.message
    (tmp_path / "empty").mkdir()
    (tmp_path / "empty" / "notes.txt").write_text("x")
    images, check = logic.scan_input(str(tmp_path / "empty"))
    assert images == [] and check.level == "error" and "No images" in check.message


def test_check_output(tmp_path, folder):
    assert logic.check_output("", str(folder)).level == "error"
    for inside in (folder, folder / "out", folder / "sub" / "deeper"):
        check = logic.check_output(str(inside), str(folder))
        assert check.level == "error" and "must not be the input folder or inside it" in check.message
    assert logic.check_output(str(tmp_path / "new"), str(folder)) == logic.Check(
        "ok", "New folder, created when generating.")
    (tmp_path / "used").mkdir()
    (tmp_path / "used" / "old.png").write_bytes(b"")
    assert logic.check_output(str(tmp_path / "used"), str(folder)).level == "warning"
    (tmp_path / "file.txt").write_text("x")
    assert logic.check_output(str(tmp_path / "file.txt"), str(folder)).level == "error"


def test_resolve_gives_readable_errors():
    assert logic.resolve("test_noise", {"sigma": 0.1, "per_channel": False}) == {"sigma": 0.1, "per_channel": False}
    with pytest.raises(ValueError, match="test_noise.sigma: 9.0 not in"):
        logic.resolve("test_noise", {"sigma": 9.0, "per_channel": True})


def test_generate_writes_what_degfw_run_writes(tmp_path, folder):
    """Same files and pixels as a folder run of the framework with seed 0, plus a row
    per image; pipeline.yaml repeats the run."""
    params = {"sigma": 0.1, "per_channel": True}
    done = logic.generate("test_noise", params, str(folder), str(tmp_path / "gui"))
    assert [r[:2] for r in done.rows] == [["a.png", "a.png"], ["b.jpg", "b.png"], ["sub/c.png", "sub/c.png"]]
    expected = Pipeline([Step("test_noise", params)], seed=0).run_folder(folder, tmp_path / "cli")
    for out in expected:
        rel = out.relative_to(tmp_path / "cli")
        np.testing.assert_array_equal(np.asarray(Image.open(tmp_path / "gui" / rel)), np.asarray(Image.open(out)))
    again = Pipeline.from_file(tmp_path / "gui" / "pipeline.yaml").run_folder(folder, tmp_path / "again")
    assert len(again) == 3
    assert "3 image(s)" in done.summary() and str(tmp_path / "gui") in done.summary()


def test_generate_shows_what_each_image_recorded(tmp_path, folder):
    done = logic.generate("test_context", {"folder": ""}, str(folder), str(tmp_path / "out"))
    assert done.rows[2][2] == "source=c.png, batch=['a.png', 'b.jpg', 'c.png'], seen=3, folder="


def test_generate_refuses_bad_folders(tmp_path, folder):
    with pytest.raises(ValueError, match="Folder not found"):
        logic.generate("test_noise", {}, str(tmp_path / "missing"), str(tmp_path / "out"))
    with pytest.raises(ValueError, match="must not be the input folder"):
        logic.generate("test_noise", {}, str(folder), str(folder / "out"))
    assert not (folder / "out").exists()


def test_preview_is_exactly_the_generated_image(tmp_path, folder):
    """Same seed and same run context: the preview of each image is pixel for pixel what
    generate() writes for it (checked with a random degradation, where the seed matters)."""
    params = {"sigma": 0.2, "per_channel": True}
    logic.generate("test_noise", params, str(folder), str(tmp_path / "out"))
    for relative, output in (("a.png", "a.png"), ("b.jpg", "b.png"), ("sub/c.png", "sub/c.png")):
        shown = logic.preview("test_noise", params, str(folder), relative)
        np.testing.assert_array_equal(to_uint8(shown.result), np.asarray(Image.open(tmp_path / "out" / output)))
        np.testing.assert_array_equal(shown.original, load_image(folder / relative))


def test_preview_knows_the_whole_input_folder(folder):
    shown = logic.preview("test_context", {"folder": ""}, str(folder), "b.jpg")
    assert shown.notes == "source=b.jpg, batch=['a.png', 'b.jpg', 'c.png'], seen=1, folder="
    with pytest.raises(ValueError, match="Not an image of the input folder"):
        logic.preview("test_context", {"folder": ""}, str(folder), "nope.png")


def test_fog_describes_its_record():
    from degradation_fw.degradations.weather.fog import Fog

    lidar = {"atmospheric_light": "sky", "depth_m": {"min": 3.1, "median": 22.0},
             "depth": {"source": "depth_pro+lidar_scale", "lidar_scale": 8.1756, "lidar_points": 4829,
                       "lidar_rel_error": {"median": 0.0231, "p90": 0.08}}}
    assert Fog.describe(lidar) == ("depth: LiDAR x 8.18 (4829 points, error 2.3%), median 22.0 m; "
                                   "light: from its own sky")
    average = {"atmospheric_light": "average of input set", "depth_m": {"min": 1.0, "median": 9.5},
               "depth": {"source": "depth_pro"}, "average_light": {"value": [0.7, 0.75, 0.8], "images_with_sky": 3}}
    assert Fog.describe(average) == ("depth: Depth Pro, median 9.5 m; "
                                     "light: no sky, average of the input images [0.7, 0.75, 0.8] (3 with sky)")
    json.dumps(lidar)  # what the pipeline records must be JSON
