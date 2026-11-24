"""LiDAR points as depth measurements for a camera image (dataset independent).

Used by `degfw fog --lidar` to correct the metric scale of the monocular depth
(decision 0008): the LiDAR points are projected into the image, and the depth map is
multiplied by the median ratio LiDAR depth / estimated depth at those pixels.

A dataset reader (e.g. degradation_fw.datasets.tumtraf) finds, for an image file
name, the point clouds taken with it and their calibration, as LidarView objects:

    views = reader.views_for(image_path.name)

Depth here is the camera z coordinate (distance along the optical axis), the same
quantity as the depth map of Depth Pro.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

MIN_POINTS = 50  # fewer LiDAR points in the image: too few for a reliable scale
MIN_DEPTH_M = 1.0  # points closer to the camera than this are ignored

_PCD_TYPES = {"F": "f", "I": "i", "U": "u"}


@dataclass(frozen=True)
class LidarView:
    """One point cloud as seen by one camera: everything needed to project its points."""

    point_cloud: Path | None  # None: the file is listed but was not found
    point_cloud_name: str
    lidar_to_camera: np.ndarray  # 4x4, X_camera = T @ X_lidar (homogeneous)
    camera_matrix: np.ndarray  # 3x3 intrinsics
    image_size: tuple[int, int]  # (width, height) the calibration is for
    source: str  # where the calibration comes from, e.g. the label file name


@dataclass(frozen=True)
class ScaleFit:
    """Result of fit_depth_scale."""

    scale: float  # multiply the depth map by this
    points: int  # LiDAR points used
    rel_error_median: float  # |scale * depth - lidar| / lidar at the points, after scaling
    rel_error_p90: float


def read_pcd_xyz(path: str | Path) -> np.ndarray:
    """x, y, z of all points of a .pcd file (DATA ascii or binary) as float64 (N, 3).
    Points with a non-finite coordinate are dropped. binary_compressed is not supported."""
    path = Path(path)
    with open(path, "rb") as f:
        header = {}
        while True:
            raw = f.readline()
            if not raw:
                raise ValueError(f"{path.name}: no DATA line in the PCD header")
            line = raw.decode("ascii", errors="replace").strip()
            if not line or line.startswith("#"):
                continue
            key, *values = line.split()
            header[key.upper()] = values
            if key.upper() == "DATA":
                break
        body = f.read()

    fields = header.get("FIELDS")
    if not fields or not {"x", "y", "z"} <= set(fields):
        raise ValueError(f"{path.name}: PCD without x, y, z fields")
    counts = [int(c) for c in header.get("COUNT", ["1"] * len(fields))]
    n = int(header.get("POINTS", [0])[0]) or int(header["WIDTH"][0]) * int(header["HEIGHT"][0])
    data = header["DATA"][0].lower()

    if data == "ascii":
        columns = np.loadtxt(body.decode("ascii").splitlines(), dtype=np.float64, ndmin=2)
        if columns.size == 0:
            return np.zeros((0, 3))
        starts = np.cumsum([0] + counts[:-1])
        xyz = columns[:, [starts[fields.index(a)] for a in "xyz"]]
    elif data == "binary":
        dtype = np.dtype([(name if name != "_" else f"_{i}",
                           f"{_PCD_TYPES[t]}{s}", (c,) if c > 1 else ())
                          for i, (name, s, t, c) in enumerate(zip(fields, header["SIZE"], header["TYPE"], counts))])
        points = np.frombuffer(body, dtype=dtype, count=n)
        xyz = np.stack([points[a].astype(np.float64) for a in "xyz"], axis=1)
    else:
        raise ValueError(f"{path.name}: PCD DATA {data} is not supported (only ascii and binary)")
    return xyz[np.isfinite(xyz).all(axis=1)]


def project_points(xyz: np.ndarray, lidar_to_camera: np.ndarray, camera_matrix: np.ndarray,
                   width: int, height: int, min_depth: float = MIN_DEPTH_M):
    """Project LiDAR points into the image. Returns pixel coordinates u (column), v (row)
    and camera depth z of the points that lie in front of the camera (z > min_depth) and
    inside the image."""
    xyz = np.asarray(xyz, dtype=np.float64).reshape(-1, 3)
    cam = (np.c_[xyz, np.ones(len(xyz))] @ np.asarray(lidar_to_camera, dtype=np.float64).T)[:, :3]
    cam = cam[cam[:, 2] > min_depth]
    uvw = cam @ np.asarray(camera_matrix, dtype=np.float64).T
    u, v = uvw[:, 0] / uvw[:, 2], uvw[:, 1] / uvw[:, 2]
    inside = (u >= 0) & (u < width) & (v >= 0) & (v < height)
    return u[inside], v[inside], cam[inside, 2]


def fit_depth_scale(depth: np.ndarray, u: np.ndarray, v: np.ndarray, z: np.ndarray) -> ScaleFit:
    """One scale factor for a depth map from LiDAR depths z at pixels (u, v): the median
    of z / depth, robust against points the camera cannot see (occluded from its
    viewpoint) or that moved between the LiDAR scan and the image."""
    d = depth[np.asarray(v).astype(int), np.asarray(u).astype(int)].astype(np.float64)
    z = np.asarray(z, dtype=np.float64)
    ok = np.isfinite(d) & (d > 0) & np.isfinite(z) & (z > 0)
    d, z = d[ok], z[ok]
    if len(z) == 0:
        raise ValueError("no usable LiDAR points")
    scale = float(np.median(z / d))
    rel = np.abs(scale * d - z) / z
    return ScaleFit(scale, len(z), float(np.median(rel)), float(np.percentile(rel, 90)))
