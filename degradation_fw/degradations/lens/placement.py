"""Exact placement of a generated lens-contamination shape (decision 0009).

The shape networks of third_party/camera_contamination_simulation take (x, y, size) and
draw a mask over the whole image, but they treat x, y only as a hint: a water droplet
lands on average 4-20 % of the longer image side away from the requested position
(measured 2026-11-24, up to 355 px on a 1920 x 1200 image). Here the network only
provides the shape: the mask it drew is moved so that the centroid of its droplet pixels
lies exactly on the requested position. If the shape consists of several separate pieces,
they are moved together and keep their relative positions.

Only numpy; the generator that uses this is in scripts/contamination_examples.py.
"""

from __future__ import annotations

import numpy as np

# Mask values below this are dropped when the shape is moved: the generators turn the
# mask into uint8 (np.uint8(mask * 255)), where they become 0 anyway.
NEGLIGIBLE = 1 / 255


def shape_pixels(mask: np.ndarray, threshold: float) -> np.ndarray:
    """Boolean map of the pixels that count as droplet: the same test as
    DropletGenerator.find_droplets (np.uint8(mask * 255) >= threshold * 255)."""
    return np.uint8(np.clip(mask, 0, 1) * 255) >= threshold * 255


def target_px(x: float, y: float, height: int, width: int) -> tuple[float, float]:
    """(column, row) in pixel indices of the relative position x, y (0..1): x = 0 is the
    left edge of the first column, x = 1 the right edge of the last one."""
    return x * width - 0.5, y * height - 0.5


def place_mask(
    shape: np.ndarray, x: float, y: float, height: int, width: int, threshold: float = 0.5
) -> tuple[np.ndarray, np.ndarray, int, int, dict]:
    """Moves a shape mask so that the centroid of its droplet pixels lies on (x, y).

    :param shape: 2-D mask in 0..1 as drawn by the network (any size, usually the
        max(height, width) square with the shape in its centre).
    :param x, y: Position in the image, 0..1 (x: column / width, y: row / height).
    :param height, width: Image size in px.
    :param threshold: Mask value from which a pixel counts as droplet (as in find_droplets).
    :return: (mask, canvas, top, left, info), in the form of render_mask(..., return_square=True):
        canvas holds the image area and the whole moved shape, mask = canvas[top:top + height,
        left:left + width] is the image part. info: centroid_px (column, row of the centroid in
        the image after the move; differs from the target by at most 0.5 px per axis, since
        the shape is moved by whole pixels), shift_px (column, row shift applied),
        at_network_edge (droplet pixels reach the border of the network's mask, so the shape
        may be cut off there).
    :raises ValueError: if no pixel of the shape reaches the threshold.
    """
    inside = shape_pixels(shape, threshold)
    if not inside.any():
        raise ValueError("the shape has no droplet pixel")
    rows, cols = np.nonzero(inside)
    centre_row, centre_col = rows.mean(), cols.mean()
    target_col, target_row = target_px(x, y, height, width)
    shift_row = int(round(target_row - centre_row))
    shift_col = int(round(target_col - centre_col))

    # Cut the shape to the part that is not negligible, then put it on a canvas that holds
    # both the image area and the moved shape
    keep = shape >= NEGLIGIBLE
    keep_rows, keep_cols = np.nonzero(keep.any(axis=1))[0], np.nonzero(keep.any(axis=0))[0]
    r0, r1, c0, c1 = keep_rows[0], keep_rows[-1] + 1, keep_cols[0], keep_cols[-1] + 1
    patch = np.where(keep[r0:r1, c0:c1], shape[r0:r1, c0:c1], 0).astype(shape.dtype)
    patch_top, patch_left = r0 + shift_row, c0 + shift_col  # in image coordinates
    canvas_top, canvas_left = min(0, patch_top), min(0, patch_left)
    canvas_bottom = max(height, patch_top + patch.shape[0])
    canvas_right = max(width, patch_left + patch.shape[1])
    canvas = np.zeros((canvas_bottom - canvas_top, canvas_right - canvas_left), dtype=shape.dtype)
    pr, pc = patch_top - canvas_top, patch_left - canvas_left
    canvas[pr : pr + patch.shape[0], pc : pc + patch.shape[1]] = patch
    top, left = -canvas_top, -canvas_left
    mask = canvas[top : top + height, left : left + width]

    at_edge = bool(inside[0].any() or inside[-1].any() or inside[:, 0].any() or inside[:, -1].any())
    info = {
        "centroid_px": [round(float(centre_col + shift_col), 2), round(float(centre_row + shift_row), 2)],
        "shift_px": [shift_col, shift_row],
        "at_network_edge": at_edge,
    }
    return mask, canvas, top, left, info
