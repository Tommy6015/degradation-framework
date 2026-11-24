"""Exact placement of water droplets (decision 0009): the network only draws the shape,
the droplet's centroid is put exactly at the requested position.

Quick tests: placement.place_mask on synthetic shapes (numpy only).
Slow tests: the real droplet network through PlacedDropletGenerator in
scripts/contamination_examples.py (GPU, weights from third_party/weights.yaml).
"""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from degradation_fw.degradations.lens.placement import place_mask, shape_pixels, target_px

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "contamination_examples.py"


def blob(side: int, centres, radius: float) -> np.ndarray:
    """Soft round blobs on a side x side square (1 inside, smooth edge, 0 far away)."""
    rows, cols = np.mgrid[0:side, 0:side].astype(np.float32)
    mask = np.zeros((side, side), np.float32)
    for r, c in centres:
        d = np.hypot(rows - r, cols - c)
        mask = np.maximum(mask, np.clip((radius + 8 - d) / 16, 0, 1))
    return mask


def centroid_in_image(canvas, top, left, threshold=0.5):
    rows, cols = np.nonzero(shape_pixels(canvas, threshold))
    return cols.mean() - left, rows.mean() - top


@pytest.mark.parametrize("height, width", [(480, 480), (400, 640), (640, 400)])
@pytest.mark.parametrize("x, y", [(0.5, 0.5), (0.2, 0.3), (0.8, 0.7), (0.0, 0.5), (1.0, 0.0), (1.0, 1.0)])
def test_centroid_lands_on_target(height, width, x, y):
    shape = blob(max(height, width), [(150, 260)], 40)  # off-centre on purpose
    mask, canvas, top, left, info = place_mask(shape, x, y, height, width)
    assert mask.shape == (height, width)
    assert np.shares_memory(mask, canvas) and np.array_equal(mask, canvas[top : top + height, left : left + width])
    col, row = centroid_in_image(canvas, top, left)
    target_col, target_row = target_px(x, y, height, width)
    assert abs(col - target_col) <= 0.5 and abs(row - target_row) <= 0.5
    assert info["centroid_px"] == pytest.approx([col, row], abs=0.01)


def test_pieces_keep_their_relative_positions():
    """A shape made of several pieces moves as a whole: same pieces, same distances,
    the centroid of all droplet pixels together lands on the target."""
    shape = blob(480, [(100, 100), (300, 380), (400, 120)], 30)
    mask, canvas, top, left, _ = place_mask(shape, 0.7, 0.4, 400, 640)
    moved = shape_pixels(canvas, 0.5)
    rows, cols = np.nonzero(shape_pixels(shape, 0.5))
    rows2, cols2 = np.nonzero(moved)
    assert len(rows2) == len(rows)  # nothing lost, nothing added
    assert len(set(rows2 - rows)) == 1 and len(set(cols2 - cols)) == 1  # one common shift
    col, row = centroid_in_image(canvas, top, left)
    assert (col, row) == pytest.approx(target_px(0.7, 0.4, 400, 640), abs=0.5)


def test_whole_shape_kept_at_the_image_edge():
    """At the edge the canvas still holds the whole shape (the droplet's full size can be
    measured); only the image part is cut."""
    shape = blob(480, [(240, 240)], 60)
    mask, canvas, top, left, _ = place_mask(shape, 0.0, 0.0, 480, 480)
    assert np.uint8(canvas * 255).astype(int).sum() == np.uint8(shape * 255).astype(int).sum()
    assert 0 < shape_pixels(mask, 0.5).sum() < shape_pixels(shape, 0.5).sum() / 2  # about a quarter visible


def test_lossless_for_the_uint8_masks():
    """Values dropped when moving are below 1/255, i.e. 0 in the generators' uint8 masks."""
    rng = np.random.default_rng(0)
    shape = blob(256, [(128, 128)], 40) + rng.random((256, 256), dtype=np.float32) * (1 / 255)
    shape = np.clip(shape, 0, 1)
    _, canvas, _, _, _ = place_mask(shape, 0.3, 0.6, 256, 256)
    assert np.uint8(canvas * 255).astype(int).sum() == np.uint8(shape * 255).astype(int).sum()


def test_same_droplet_pixels_as_find_droplets():
    """shape_pixels uses find_droplets' rule: np.uint8(mask * 255) >= threshold * 255."""
    assert not shape_pixels(np.array([[0.5]]), 0.5).any()  # uint8(127.5) = 127 < 127.5
    assert shape_pixels(np.array([[0.502]]), 0.5).all()  # uint8(128.01) = 128


def test_no_droplet_pixel_is_an_error():
    with pytest.raises(ValueError, match="no droplet pixel"):
        place_mask(np.full((64, 64), 0.4, np.float32), 0.5, 0.5, 64, 64)


def test_network_edge_is_reported():
    shape = blob(200, [(100, 5)], 30)  # touches the left border of the network's square
    assert place_mask(shape, 0.5, 0.5, 200, 200)[4]["at_network_edge"]
    assert not place_mask(blob(200, [(100, 100)], 30), 0.5, 0.5, 200, 200)[4]["at_network_edge"]


# ---- the real droplet network --------------------------------------------------------


@pytest.fixture(scope="module")
def script():
    pytest.importorskip("torch")
    pytest.importorskip("cv2")
    from degradation_fw.core.weights import missing_weights

    reason = missing_weights(["contamination_droplet"])
    if reason:
        pytest.skip(reason)
    spec = importlib.util.spec_from_file_location("contamination_examples", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator(script):
    return script.PlacedDropletGenerator(str(script.weight_path("contamination_droplet")))


def seeded(script, seed):
    script.set_seed(seed)  # random, numpy and torch, as the script does before every image


@pytest.mark.slow
@pytest.mark.parametrize("height, width", [(960, 960), (1200, 1920)])
def test_real_droplets_land_exactly(script, generator, height, width):
    """5 positions x 2 sizes x 10 seeds: the droplet pixels' centroid is within 1 px of the
    target (without exact placement: 34-266 px on average, measured 2026-11-24)."""
    worst = 0.0
    for x, y in [(0.5, 0.5), (0.2, 0.3), (0.8, 0.7), (0.05, 0.5), (0.9, 0.1)]:
        for size in (0.15, 0.3):
            for seed in range(10):
                seeded(script, seed)
                _, canvas, top, left = generator.generate_mask(x, y, size, 41, 0, height, width, return_square=True)
                col, row = centroid_in_image(canvas, top, left)
                target_col, target_row = target_px(x, y, height, width)
                worst = max(worst, float(np.hypot(col - target_col, row - target_row)))
    assert worst <= 1.0


@pytest.mark.slow
def test_real_droplet_at_the_edge_keeps_its_full_size(script, generator):
    """Same seed in the centre and at the left edge: find_droplets measures the same size,
    and marks the edge droplet as cut."""
    image = np.full((400, 640, 3), 128, np.uint8)
    sizes = {}
    for x in (0.5, 0.0):
        seeded(script, 3)
        generator.simulate_droplet(
            f_C=script.F_C, raw_img=image, x=x, y=0.5, size=0.2,
            mask_blurr_gauss_kernel=41, blur_sigma=0, b_strength=0.001,
            ib_gauss_kernel=201, blurr_roi_gauss_kernel=41, mood="black", mask_threshold=script.MASK_THRESHOLD,
        )  # fmt: skip
        sizes[x] = [(d["size_px"], d["cut"]) for d in generator.last_droplets]
    assert [s for s, _ in sizes[0.5]] == [s for s, _ in sizes[0.0]]
    assert all(cut for _, cut in sizes[0.0]) and not any(cut for _, cut in sizes[0.5])


@pytest.mark.slow
def test_real_droplets_are_reproducible(script, generator):
    image = (np.random.default_rng(1).random((300, 480, 3)) * 255).astype(np.uint8)
    results = []
    for _ in range(2):
        seeded(script, 7)
        out, mask = generator.simulate_droplet(
            f_C=script.F_C, raw_img=image, x=0.3, y=0.6, size=0.25,
            mask_blurr_gauss_kernel=41, blur_sigma=0, b_strength=0.001,
            ib_gauss_kernel=201, blurr_roi_gauss_kernel=41, mood="black", mask_threshold=script.MASK_THRESHOLD,
        )  # fmt: skip
        results.append((out, mask, dict(generator.last_placement)))
    assert np.array_equal(results[0][0], results[1][0]) and np.array_equal(results[0][1], results[1][1])
    assert results[0][2] == results[1][2]


@pytest.mark.slow
def test_small_size_retries_until_there_is_a_droplet(script, generator):
    """At SIZE 0.05 the network sometimes draws no droplet; the generator calls it again
    (reproducibly) instead of returning an image without a droplet."""
    attempts = []
    for seed in range(10):
        seeded(script, seed)
        _, canvas, _, _ = generator.generate_mask(0.5, 0.5, 0.05, 41, 0, 960, 960, return_square=True)
        assert shape_pixels(canvas, script.MASK_THRESHOLD).any()
        attempts.append(generator.last_placement["attempts"])
    assert max(attempts) > 1  # the retry was needed at least once
    tiny = script.PlacedDropletGenerator(str(script.weight_path("contamination_droplet")), attempts=1)
    with pytest.raises(RuntimeError, match="no droplet"):
        for seed in range(50):  # some seed among these draws nothing at SIZE 0.01 on the first try
            seeded(script, seed)
            tiny.generate_mask(0.5, 0.5, 0.01, 41, 0, 960, 960)
