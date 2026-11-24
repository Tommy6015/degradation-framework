"""TUMTraf (A9) dataset: the LiDAR frames and calibration that belong to a camera image,
read from its OpenLABEL label files (labels_point_clouds/<lidar>/*.json).

For now only what `degfw fog --lidar` needs; the dataset adapter (M6) grows from here.

Each label file describes LiDAR frames (usually one):
  frames.<n>.frame_properties.point_cloud_file_name        the .pcd of the frame
  frames.<n>.frame_properties.image_file_names             camera images taken with it
  streams.<camera>.stream_properties.intrinsics_pinhole    camera matrix and image size
  coordinate_systems.<name>.parent / .pose_wrt_parent      the calibration tree
Convention, checked by projecting the points onto the images (decision 0008):
pose_wrt_parent maps coordinates of the parent system into the child system,
X_child = P @ X_parent; e.g. a camera whose parent is the LiDAR: X_camera = P @ X_lidar.
Point clouds are in the coordinate system whose name is part of the .pcd file name
(e.g. ..._s110_lidar_ouster_south.pcd -> s110_lidar_ouster_south); cameras are the
streams whose name is part of the image file name.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from degradation_fw.core.lidar import LidarView


class TumTrafLidar:
    """Index of all OpenLABEL label files and .pcd files under a folder (searched
    recursively), e.g. the root of a TUMTraf A9 sequence, or one folder holding images,
    point clouds and labels together.

        lidar = TumTrafLidar("a9_dataset_r02_s03")
        views = lidar.views_for("1651673049_991297808_s110_camera_basler_south2_8mm.jpg")
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        if not self.root.is_dir():
            raise FileNotFoundError(f"LiDAR folder not found: {self.root}")
        self.point_clouds: dict[str, Path] = {}
        for p in sorted(self.root.rglob("*.pcd")):
            self.point_clouds.setdefault(p.name, p)
        self._views: dict[str, list[LidarView]] = {}
        self.label_files = 0
        for p in sorted(self.root.rglob("*.json")):
            views = _views_from_label(p, self.point_clouds)
            if views is None:
                continue  # not an OpenLABEL file (e.g. a fog_run.json)
            self.label_files += 1
            for image_name, view in views:
                self._views.setdefault(image_name, []).append(view)

    @property
    def images(self) -> int:
        """Number of image file names that have at least one LiDAR view."""
        return len(self._views)

    def views_for(self, image_name: str) -> list[LidarView]:
        """The point clouds (with calibration) taken together with this image, matched
        by file name; empty if no label file lists it."""
        return list(self._views.get(image_name, []))


def _views_from_label(path: Path, point_clouds: dict[str, Path]):
    """[(image file name, LidarView)] of one label file, None if it is no OpenLABEL file.
    Images whose camera or LiDAR has no usable calibration in the file are left out."""
    try:
        label = json.loads(path.read_text(encoding="utf-8"))["openlabel"]
        frames = label["frames"]
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        return None
    systems = label.get("coordinate_systems", {})
    streams = label.get("streams", {})
    views = []
    for frame in frames.values():
        props = frame.get("frame_properties", {})
        pcd_name = props.get("point_cloud_file_name")
        lidar = _name_in(pcd_name, systems)
        if not pcd_name or not lidar:
            continue
        for image_name in props.get("image_file_names", []):
            camera = _name_in(image_name, streams)
            intrinsics = streams.get(camera, {}).get("stream_properties", {}).get("intrinsics_pinhole", {})
            if not camera or "camera_matrix_3x4" not in intrinsics or camera not in systems:
                continue
            try:
                transform = _to_system(systems, camera) @ np.linalg.inv(_to_system(systems, lidar))
            except (KeyError, ValueError, np.linalg.LinAlgError):
                continue
            views.append((image_name, LidarView(
                point_cloud=point_clouds.get(pcd_name),
                point_cloud_name=pcd_name,
                lidar_to_camera=transform,
                camera_matrix=np.asarray(intrinsics["camera_matrix_3x4"], dtype=np.float64)[:, :3],
                image_size=(int(intrinsics["width_px"]), int(intrinsics["height_px"])),
                source=path.name,
            )))
    return views


def _name_in(file_name: str | None, names) -> str | None:
    """The longest of `names` that is part of the file name (None if none is)."""
    if not file_name:
        return None
    found = [n for n in names if n and n in file_name]
    return max(found, key=len) if found else None


def _to_system(systems: dict, name: str) -> np.ndarray:
    """4x4 matrix mapping coordinates of the root system into system `name`, by walking
    up the parents: X_child = pose_wrt_parent @ X_parent at every step."""
    transform = np.eye(4)
    seen = set()
    while name:
        if name in seen:
            raise ValueError(f"cycle in coordinate_systems at {name}")
        seen.add(name)
        system = systems[name]
        pose = system.get("pose_wrt_parent")
        if pose is not None:
            transform = transform @ np.asarray(pose["matrix4x4"], dtype=np.float64).reshape(4, 4)
        name = system.get("parent") or ""
    return transform
