"""Fog (Clear2Fog). The model tests are slow: Depth Pro in float32, about 20 s per
image on an 8 GB GPU.

Regenerate the reference image after an intentional change of the results:
    uv run python tests/degradations/test_fog.py
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from degradation_fw.core.io import load_image, to_uint8
from degradation_fw.degradations.weather.fog import collect_inputs

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
