"""LiDAR points as depth measurements (core/lidar.py) and the TUMTraf label reader
(datasets/tumtraf.py). Synthetic data only: no GPU, no dataset needed."""

import json

import numpy as np
import pytest

from degradation_fw.core.lidar import fit_depth_scale, project_points, read_pcd_xyz
from degradation_fw.datasets.tumtraf import TumTrafLidar

K = np.array([[100.0, 0.0, 50.0], [0.0, 100.0, 40.0], [0.0, 0.0, 1.0]])  # 100 x 80 image


def write_pcd_ascii(path, rows, fields="x y z intensity", extra_header=""):
    n = len(rows)
    k = len(fields.split())
    path.write_text(
        "# .PCD v0.7 - Point Cloud Data file format\nVERSION 0.7\n"
        f"FIELDS {fields}\nSIZE {' '.join(['4'] * k)}\nTYPE {' '.join(['F'] * k)}\n"
        f"COUNT {' '.join(['1'] * k)}\n{extra_header}WIDTH {n}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\n"
        f"POINTS {n}\nDATA ascii\n" + "".join(" ".join(str(x) for x in r) + "\n" for r in rows))


def test_read_pcd_ascii_drops_non_finite_points(tmp_path):
    p = tmp_path / "a.pcd"
    write_pcd_ascii(p, [(1, 2, 3, 10), (4, 5, 6, 20), ("nan", 0, 0, 0)])
    assert read_pcd_xyz(p).tolist() == [[1, 2, 3], [4, 5, 6]]


def test_read_pcd_binary_mixed_types(tmp_path):
    """TUMTraf-like fields: x y z float32 between other fields of other sizes."""
    dtype = np.dtype([("intensity", "<f4"), ("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
                      ("t", "<u4"), ("ring", "u1"), ("ambient", "<u2")])
    pts = np.zeros(3, dtype)
    pts["x"], pts["y"], pts["z"] = [1.5, -2, 30], [0, 1, 2], [10, 20, 0.25]
    header = ("VERSION 0.7\nFIELDS intensity x y z t ring ambient\nSIZE 4 4 4 4 4 1 2\n"
              "TYPE F F F F U U U\nCOUNT 1 1 1 1 1 1 1\nWIDTH 3\nHEIGHT 1\nPOINTS 3\nDATA binary\n")
    p = tmp_path / "b.pcd"
    p.write_bytes(header.encode() + pts.tobytes())
    assert np.allclose(read_pcd_xyz(p), np.stack([pts["x"], pts["y"], pts["z"]], 1))


def test_read_pcd_rejects_compressed(tmp_path):
    p = tmp_path / "c.pcd"
    p.write_text("FIELDS x y z\nSIZE 4 4 4\nTYPE F F F\nWIDTH 0\nHEIGHT 1\nDATA binary_compressed\n")
    with pytest.raises(ValueError, match="binary_compressed"):
        read_pcd_xyz(p)


def test_project_points_keeps_points_in_front_and_inside():
    xyz = np.array([[0, 0, 10],      # image centre
                    [1, 0, 10],      # 10 px to the right
                    [0, 0, -5],      # behind the camera
                    [100, 0, 10],    # outside the image
                    [0, 0, 0.5]])    # closer than MIN_DEPTH_M
    u, v, z = project_points(xyz, np.eye(4), K, 100, 80)
    assert np.allclose(u, [50, 60]) and np.allclose(v, [40, 40]) and np.allclose(z, [10, 10])


def test_project_points_applies_the_transform():
    """LiDAR 5 m behind the camera along its optical axis: X_cam = X_lidar - (0, 0, 5)."""
    t = np.eye(4)
    t[2, 3] = -5
    _, _, z = project_points(np.array([[0, 0, 15]]), t, K, 100, 80)
    assert np.allclose(z, [10])


def test_fit_depth_scale_is_robust_to_outliers():
    rng = np.random.default_rng(0)
    true = rng.uniform(10, 100, (80, 100))
    depth = true / 8  # monocular depth with a wrong scale
    v, u = rng.integers(0, 80, 500), rng.integers(0, 100, 500)
    z = true[v, u].copy()
    z[:100] *= 3  # 20 % of the points occluded / moved
    fit = fit_depth_scale(depth, u + 0.5, v + 0.5, z)
    assert fit.scale == pytest.approx(8, rel=1e-6)
    assert fit.points == 500 and fit.rel_error_median == pytest.approx(0, abs=1e-9)


# ---- TUMTraf (OpenLABEL) labels ---------------------------------------------------
CAM = "s110_camera_basler_south2_8mm"
LIDAR = "s110_lidar_ouster_south"


def pose(tx=0.0, ty=0.0, tz=0.0, rot=None):
    m = np.eye(4)
    if rot is not None:
        m[:3, :3] = rot
    m[:3, 3] = (tx, ty, tz)
    return {"matrix4x4": m.ravel().tolist()}


def write_label(folder, stem, image_names, pcd_name, cam_pose, frame_key="0"):
    label = {"openlabel": {
        "metadata": {"schema_version": "1.0.0"},
        "coordinate_systems": {
            "hd_map_origin": {"type": "scene_cs", "parent": "", "children": ["s110_base"]},
            "s110_base": {"type": "local_cs", "parent": "hd_map_origin", "children": [LIDAR],
                          "pose_wrt_parent": pose(100, -400, 5)},
            LIDAR: {"type": "sensor_cs", "parent": "s110_base", "children": [CAM],
                    "pose_wrt_parent": pose(-2, 16, 8)},
            CAM: {"type": "sensor_cs", "parent": LIDAR, "children": [], "pose_wrt_parent": cam_pose},
        },
        "streams": {CAM: {"type": "camera", "stream_properties": {"intrinsics_pinhole": {
            "width_px": 100, "height_px": 80, "camera_matrix_3x4": np.c_[K, np.zeros(3)].tolist()}}}},
        "frames": {frame_key: {"objects": {}, "frame_properties": {
            "point_cloud_file_name": pcd_name, "image_file_names": image_names}}},
    }}
    (folder / f"{stem}.json").write_text(json.dumps(label))


def test_tumtraf_finds_point_cloud_and_calibration(tmp_path):
    rot = np.array([[0, -1, 0], [0, 0, -1], [1, 0, 0]], float)  # LiDAR x forward -> camera z forward
    cam_pose = pose(0.5, 1.0, 1.5, rot)
    (tmp_path / "labels").mkdir()
    (tmp_path / "points").mkdir()
    write_label(tmp_path / "labels", "f0", [f"0001_{CAM}.jpg", "0001_s110_camera_basler_south1_8mm.jpg"],
                f"0001_{LIDAR}.pcd", cam_pose)
    write_pcd_ascii(tmp_path / "points" / f"0001_{LIDAR}.pcd", [(20, 0, 0, 1)])
    (tmp_path / "fog_run.json").write_text('{"method": "Clear2Fog"}')  # not a label file: ignored

    lidar = TumTrafLidar(tmp_path)
    assert lidar.label_files == 1 and lidar.images == 1  # south1 has no calibration in this file
    (view,) = lidar.views_for(f"0001_{CAM}.jpg")
    # camera's parent is the LiDAR: lidar_to_camera is exactly the camera's pose_wrt_parent
    assert np.allclose(view.lidar_to_camera, np.array(cam_pose["matrix4x4"]).reshape(4, 4))
    assert view.point_cloud == tmp_path / "points" / f"0001_{LIDAR}.pcd"
    assert view.image_size == (100, 80) and np.allclose(view.camera_matrix, K) and view.source == "f0.json"
    assert lidar.views_for("unknown.jpg") == []
    # a point 20 m ahead of the LiDAR is ~21.5 m ahead of the camera
    _, _, z = project_points(read_pcd_xyz(view.point_cloud), view.lidar_to_camera, view.camera_matrix, 100, 80)
    assert np.allclose(z, [21.5])


def test_tumtraf_missing_point_cloud_and_folder(tmp_path):
    write_label(tmp_path, "f0", [f"0001_{CAM}.jpg"], f"0001_{LIDAR}.pcd", pose())
    (view,) = TumTrafLidar(tmp_path).views_for(f"0001_{CAM}.jpg")
    assert view.point_cloud is None and view.point_cloud_name == f"0001_{LIDAR}.pcd"
    with pytest.raises(FileNotFoundError):
        TumTrafLidar(tmp_path / "missing")
