"""Fog (Clear2Fog). The model tests are slow: Depth Pro in float32, about 20 s per
image on an 8 GB GPU.

Regenerate the reference image after an intentional change of the results:
    uv run python tests/degradations/test_fog.py
"""

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from degradation_fw.core.io import load_image, to_uint8
from degradation_fw.core.lidar import MIN_POINTS, LidarView
from degradation_fw.degradations.weather.fog import collect_inputs, lidar_scaled_depth

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
REFERENCE_INPUT = DATA_DIR / "fog_scene.png"
REFERENCE_OUTPUT = DATA_DIR / "fog_scene_vis100.png"
REFERENCE_VISIBILITY = 100


def test_collect_inputs_like_c2f(tmp_path):
    """Folders give their .png / .jpg / .jpeg files (not subfolders), files count as given,
    duplicates once."""
    for name in ("b.jpg", "a.png", "c.JPEG", "notes.txt", "sub/d.png"):
        (tmp_path / name).parent.mkdir(exist_ok=True)
        (tmp_path / name).write_bytes(b"")
    found = collect_inputs([tmp_path, tmp_path / "a.png"])
    assert [p.name for p in found] == ["a.png", "b.jpg", "c.JPEG"]
    with pytest.raises(FileNotFoundError):
        collect_inputs([tmp_path / "missing.png"])


# ---- depth scale from LiDAR (degfw fog --lidar, decision 0008) -----------------------
CAMERA_MATRIX = np.array([[100.0, 0.0, 64.0], [0.0, 100.0, 48.0], [0.0, 0.0, 1.0]])  # 128 x 96


def lidar_view(tmp_path, points, name="f.pcd", size=(128, 96)):
    """A LidarView whose LiDAR frame is the camera frame, with the given points."""
    pcd = tmp_path / name
    pcd.write_text(f"FIELDS x y z\nSIZE 4 4 4\nTYPE F F F\nWIDTH {len(points)}\nHEIGHT 1\nDATA ascii\n"
                   + "".join(f"{x} {y} {z}\n" for x, y, z in points))
    return LidarView(pcd, name, np.eye(4), CAMERA_MATRIX, size, "label.json")


def scene_points(true_depth, n, seed=0):
    """n LiDAR points on a scene with the given depth map (camera frame)."""
    rng = np.random.default_rng(seed)
    v, u = rng.integers(0, 96, n), rng.integers(0, 128, n)
    z = true_depth[v, u]
    return np.stack([(u + 0.5 - 64) * z / 100, (v + 0.5 - 48) * z / 100, z], 1)


def test_lidar_scaled_depth_corrects_the_scale(tmp_path):
    true = np.linspace(10, 120, 96 * 128).reshape(96, 128).astype(np.float32)
    estimated = true / 8  # Depth Pro on an elevated camera: far too near
    depth, record = lidar_scaled_depth(estimated, [lidar_view(tmp_path, scene_points(true, 300))])
    assert np.allclose(depth, true, rtol=1e-3) and depth.dtype == np.float32
    assert record["source"] == "depth_pro+lidar_scale" and record["lidar_scale"] == pytest.approx(8, rel=1e-3)
    assert record["lidar_points"] == 300 and record["lidar_rel_error"]["median"] < 1e-3
    assert record["lidar_frames"] == [{"label": "label.json", "point_cloud": "f.pcd", "points_in_view": 300}]


def test_lidar_scaled_depth_falls_back_to_depth_pro(tmp_path):
    """No LiDAR frame, too few points in view, calibration for another image size, or a
    missing point cloud: the depth stays as it is, and the record says why."""
    estimated = np.full((96, 128), 5.0, np.float32)
    true = estimated * 8
    cases = {
        "no LiDAR frame lists this image": [],
        f"{MIN_POINTS - 1} LiDAR point(s) in view": [lidar_view(tmp_path, scene_points(true, MIN_POINTS - 1),
                                                                name="few.pcd")],
        "calibration is for 1920x1200": [lidar_view(tmp_path, scene_points(true, 300), name="other_size.pcd",
                                                    size=(1920, 1200))],
        "gone.pcd not found": [LidarView(None, "gone.pcd", np.eye(4), CAMERA_MATRIX, (128, 96), "label.json")],
    }
    for reason, views in cases.items():
        depth, record = lidar_scaled_depth(estimated, views)
        assert depth is estimated and record["source"] == "depth_pro"
        assert reason in record["lidar_not_used"]


@pytest.mark.slow
def test_fog_command_with_lidar(usable, tmp_path):
    """degfw fog --lidar: an image with a TUMTraf label and point cloud gets its depth
    scaled (denser fog here, the LiDAR says the scene is farther away), an image
    without one keeps Depth Pro's depth; both recorded in fog_run.json."""
    usable("fog")
    from degradation_fw.degradations.weather.fog import engine, run_cli

    # TUMTraf naming: the camera's name is part of the image file name, the LiDAR's
    # name part of the point cloud file name
    images, lidar = tmp_path / "in", tmp_path / "lidar"
    images.mkdir()
    lidar.mkdir()
    rgb = np.asarray(Image.open(REFERENCE_INPUT).convert("RGB"))  # 96 x 128
    for name in ("0001_cam.png", "0002_cam.png"):
        Image.fromarray(rgb).save(images / name)
    # a LiDAR frame for 0001 only, in the camera's own frame, 3x farther than Depth Pro says
    depth_pro = engine().load(images / "0001_cam.png")[1]
    lidar_view(lidar, scene_points(depth_pro * 3, 400), name="0001_lidar.pcd")
    (lidar / "0001_lidar.json").write_text(json.dumps({"openlabel": {
        "coordinate_systems": {"lidar": {"parent": ""},
                               "cam": {"parent": "lidar", "pose_wrt_parent": {"matrix4x4": np.eye(4).ravel().tolist()}}},
        "streams": {"cam": {"stream_properties": {"intrinsics_pinhole": {
            "width_px": 128, "height_px": 96, "camera_matrix_3x4": np.c_[CAMERA_MATRIX, np.zeros(3)].tolist()}}}},
        "frames": {"0": {"frame_properties": {"point_cloud_file_name": "0001_lidar.pcd",
                                              "image_file_names": ["0001_cam.png"]}}}}}))

    assert run_cli([images], tmp_path / "out", [REFERENCE_VISIBILITY], lidar=lidar) == 0
    record = json.loads((tmp_path / "out" / "fog_run.json").read_text(encoding="utf-8"))
    assert record["lidar"] == str(lidar)
    scaled, kept = record["images"]["0001_cam"]["depth"], record["images"]["0002_cam"]["depth"]
    assert scaled["source"] == "depth_pro+lidar_scale" and scaled["lidar_scale"] == pytest.approx(3, rel=0.01)
    assert kept["source"] == "depth_pro" and "no LiDAR frame" in kept["lidar_not_used"]
    foggy = [np.asarray(Image.open(tmp_path / "out" / f"foggy_{n}_cam_vis_{REFERENCE_VISIBILITY}.png"), float)
             for n in ("0001", "0002")]
    assert foggy[0].std() < foggy[1].std()  # 3x farther -> denser fog, less contrast left


@pytest.mark.slow
def test_fog_denser_at_lower_visibility(usable):
    """Lower visibility -> more fog -> less contrast left in the image."""
    fog = usable("fog")
    rng = np.random.default_rng(0)
    # a simple scene: sky-like bright top half, textured bottom half
    img = np.concatenate([np.full((48, 96, 3), 0.85, np.float32),
                          rng.random((48, 96, 3), dtype=np.float32) * 0.6], axis=0)
    contrast = [fog(img, visibility=v).std() for v in (500, 100, 20)]
    assert contrast[0] > contrast[1] > contrast[2]


@pytest.mark.slow
def test_fog_command_rotated_photos_and_same_names(usable, tmp_path):
    """A portrait photo stored sideways with an EXIF orientation tag (as phones do)
    failed in c2f.py (RGB and depth rotated differently); now it is fogged upright.
    The same file name in two input folders: two results, nothing overwritten."""
    usable("fog")
    from degradation_fw.degradations.weather.fog import run_cli

    stored = np.asarray(Image.open(REFERENCE_INPUT).convert("RGB"))  # 96 x 128, landscape
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90° clockwise to view
    for folder in ("a", "b"):
        (tmp_path / folder).mkdir()
        Image.fromarray(stored).save(tmp_path / folder / "portrait.jpg", exif=exif.tobytes(), quality=95)
    assert run_cli([tmp_path / "a", tmp_path / "b"], tmp_path / "out", [REFERENCE_VISIBILITY]) == 0
    for name in ("portrait", "portrait_2"):
        out = np.asarray(Image.open(tmp_path / "out" / f"foggy_{name}_vis_{REFERENCE_VISIBILITY}.png"))
        assert out.shape == (128, 96, 3)  # upright


@pytest.mark.slow
def test_fog_matches_reference(usable):
    """Regression test: the float32 result for tests/data/fog_scene.png must stay as it
    was when the adapter was checked to be pixel-identical to Clear2Fog's c2f.py.
    Tolerance for GPU / driver differences: at most 1 grey level, on at most 0.5 % of
    the pixels. fp16 (1 level on ~1.7 % of the pixels) or a changed model fails."""
    fog = usable("fog")
    out = to_uint8(fog(load_image(REFERENCE_INPUT), visibility=REFERENCE_VISIBILITY))
    expected = np.asarray(Image.open(REFERENCE_OUTPUT).convert("RGB"))
    diff = np.abs(out.astype(int) - expected).max(axis=2)
    assert diff.max() <= 1, f"max difference {diff.max()} grey levels"
    assert (diff > 0).mean() <= 0.005, f"{(diff > 0).mean():.2%} of the pixels differ"


if __name__ == "__main__":  # regenerate the reference image
    from degradation_fw import get

    result = get("fog")(load_image(REFERENCE_INPUT), visibility=REFERENCE_VISIBILITY)
    Image.fromarray(to_uint8(result)).save(REFERENCE_OUTPUT, optimize=True)
    print(f"written {REFERENCE_OUTPUT}")
