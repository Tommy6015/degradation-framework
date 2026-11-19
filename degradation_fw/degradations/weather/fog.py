"""雾 (fog) — Clear2Fog (third_party/Clear2Fog).

Method (unchanged from Clear2Fog):
  1. Depth Pro estimates a metric depth map (metres) from the single image.
  2. Atmospheric light L: dark-channel prior, restricted to pixels >= 1000 m away
     (the sky); its luminance is clipped to [162, 220] / 255 and used as grey.
     If an image has no sky, the average L over (up to 100) images of the input
     set is used, or 0.8 if none of them has sky either.
  3. Koschmieder's law: t = exp(-beta * depth) with beta = -ln(0.05) / visibility,
     foggy = clear * t + L * (1 - t).
  Fog density is set by the visibility (meteorological optical range) in metres:
  lower = denser fog.

Two ways to use it:
  - its own command (registered below), like Clear2Fog's c2f.py (only input,
    output, visibility):
        uv run degfw fog -i INPUT -o OUTPUT -v 100
  - as the registered degradation "fog" (params visibility, fp16), like any other:
        uv run degfw run fog -i INPUT -o OUTPUT -p visibility=50
    or as a step of a pipeline config (degfw apply, GUI).

Differences to running c2f.py. For images without an EXIF orientation tag none of
them changes the result (float32: pixel-identical):
  - Photos with an EXIF orientation tag (e.g. portrait photos from phones) are turned
    upright first, and RGB and depth come from the same pixels. c2f.py reads the RGB
    without and the depth with the rotation, so such photos fail there (90°) or get an
    upside-down depth map (180°).
  - The average atmospheric light (only used for images without sky) is computed
    only when such an image comes up, from a sample drawn with a fixed seed
    (c2f.py: always at start, unseeded sample). With <= 100 input images the
    sample is all images, as in c2f.py.
  - Several visibilities in one run reuse the depth map of each image.
  - Clear2Fog's package __init__ is bypassed, so its LiDAR part (and PyQt5) is
    not needed.
"""

from __future__ import annotations

import importlib
import json
import random
import tempfile
import time
from pathlib import Path

import numpy as np

from degradation_fw.core.base import Degradation
from degradation_fw.core.io import load_rgb_u8, to_uint8
from degradation_fw.core.params import Bool, Int
from degradation_fw.core.paths import import_third_party_package, third_party_dir, working_dir
from degradation_fw.core.registry import register, register_command
from degradation_fw.core.weights import missing_weights

REPO = "Clear2Fog"  # third_party/Clear2Fog
# Everything Clear2Fog needs: Python packages (dependency group clear2fog in pyproject.toml)
# and model weights (ids in third_party/weights.yaml)
MODULES = ("torch", "torchvision", "timm", "pillow_heif", "skimage")
WEIGHTS = ("depth_pro",)
MIN_SKY_DEPTH = 1000  # metres; c2f.py's min_depth for the atmospheric light
MAX_AVG_SAMPLES = 100  # as in FogCamera.__init__
SAMPLE_SEED = 0  # seed for picking the images that the average atmospheric light is computed from


def _import_clear2fog():
    """Clear2Fog's Depth Pro and camera fog modules. src/fog_pipeline is loaded as a
    private package (_tp_clear2fog) without running its __init__.py, which would also
    import the LiDAR part (and PyQt5)."""
    pkg = import_third_party_package(REPO, "src/fog_pipeline")
    depth_generation = importlib.import_module(f"{pkg.__name__}.depth_map.depth_generation")
    camera_fog = importlib.import_module(f"{pkg.__name__}.simulate_fog.camera.camera_fog_simulation")
    depth_pro_utils = importlib.import_module(f"{pkg.__name__}.depth_map.depth_pro.utils")
    return depth_generation.DepthGenerator, camera_fog.FogCamera, depth_pro_utils.load_rgb


class Clear2Fog:
    """Loaded Depth Pro model + Clear2Fog's FogCamera. Load once, reuse (see engine()).

    fp16=False (default): float32 as in c2f.py, identical results. On an 8 GB GPU
    Depth Pro then needs ~8 GB and spills into system memory (~20 s per image).
    fp16=True: half precision (as Apple's own Depth Pro CLI uses on GPU), ~1 s per
    image and ~3.7 GB; depth differs by ~0.1 % (median), so the fog differs slightly.
    """

    def __init__(self, fp16: bool = False):
        import torch

        missing = missing_weights(WEIGHTS)
        if missing:
            raise FileNotFoundError(missing)
        DepthGenerator, FogCamera, self._load_rgb = _import_clear2fog()
        self.fp16 = fp16
        t = time.time()
        # Depth Pro's checkpoint path is relative to the Clear2Fog root
        with working_dir(third_party_dir(REPO)):
            self.depth = DepthGenerator(precision=torch.float16 if fp16 else torch.float32)
        # FogCamera.__init__ would run Depth Pro on up to 100 images of a folder to
        # average the atmospheric light. Give it an empty folder (-> its fallback
        # 0.8) and set the average later, only if an image without sky needs it.
        with tempfile.TemporaryDirectory() as empty:
            self.fog = FogCamera(self.depth, empty, min_depth=MIN_SKY_DEPTH)
        self.fallback_light = self.fog.avg_atmospheric_light.copy()
        print(f"Clear2Fog: Depth Pro loaded on {self.depth.device} ({'float16' if fp16 else 'float32'}) "
              f"in {time.time() - t:.1f} s")

    # ---- image + depth -----------------------------------------------------------
    def load(self, path: str | Path) -> tuple[np.ndarray, np.ndarray]:
        """RGB (uint8, upright) and metric depth of an image file, both from the same
        pixels, so they always match. The depth uses the EXIF focal length if the file
        has one, as in c2f.py.

        c2f.py reads the RGB without and Depth Pro reads the file with the EXIF
        rotation, so a photo with an orientation tag failed there (90°: shapes differ)
        or got an upside-down depth map (180°). Without a tag the result is the same.
        """
        rgb = load_rgb_u8(path)
        _, _, f_px = self._load_rgb(path)  # Depth Pro's own loader, used only for the EXIF focal length
        return rgb, self.depth_from_array(rgb, f_px)

    def depth_from_array(self, rgb_u8: np.ndarray, f_px: float | None = None) -> np.ndarray:
        """Same as DepthGenerator.run, for an image in memory. f_px: focal length in
        pixels; None = estimated by Depth Pro (images in memory have no EXIF). float32
        out also with fp16, so the fog formula is computed in float32."""
        prediction = self.depth.model.infer(self.depth.transform(rgb_u8), f_px=f_px)
        return prediction["depth"].cpu().detach().float().numpy()

    # ---- atmospheric light -----------------------------------------------------
    def sky_light(self, rgb_u8: np.ndarray, depth: np.ndarray):
        """Atmospheric light from the sky of this image, or None if it has no sky."""
        return self.fog.estimate_atmospheric_light(rgb_u8, depth, min_depth=MIN_SKY_DEPTH)

    def set_average_light(self, image_paths: list[Path]) -> tuple[np.ndarray, int]:
        """As FogCamera.__init__: average sky light over up to 100 images (seeded sample).
        Returns (light, number of images that had sky)."""
        paths = list(image_paths)
        if len(paths) > MAX_AVG_SAMPLES:
            paths = random.Random(SAMPLE_SEED).sample(paths, MAX_AVG_SAMPLES)
        lights = []
        for p in paths:
            light = self.sky_light(*self.load(p))
            if light is not None:
                lights.append(light)
        if lights:
            self.fog.avg_atmospheric_light = np.mean(lights, axis=0)
        else:
            self.fog.avg_atmospheric_light = self.fallback_light.copy()
        return self.fog.avg_atmospheric_light, len(lights)

    # ---- fog -------------------------------------------------------------------
    def simulate(self, rgb_u8: np.ndarray, depth: np.ndarray, visibility: float) -> np.ndarray:
        """Clear2Fog's FogCamera.simulate, as called in c2f.py. uint8 RGB in and out."""
        return self.fog.simulate(rgb_u8, rgb_u8, depth, visibility=visibility, min_depth=MIN_SKY_DEPTH)


_ENGINE: Clear2Fog | None = None


def engine(fp16: bool = False) -> Clear2Fog:
    """The shared Clear2Fog instance (Depth Pro is ~1.9 GB, load it only once).
    Asking for the other precision replaces it (only one model in GPU memory)."""
    global _ENGINE
    if _ENGINE is None or _ENGINE.fp16 != fp16:
        _ENGINE = None  # free the old model first
        _ENGINE = Clear2Fog(fp16=fp16)
    return _ENGINE


@register
class Fog(Degradation):
    name = "fog"
    label = "雾 Fog (Clear2Fog)"
    description = ("Clear2Fog: Depth Pro monocular depth + atmospheric scattering model. "
                   "Lower visibility = denser fog.")
    requires_modules = MODULES
    requires_weights = WEIGHTS
    params = {
        "visibility": Int(default=100, min=5, max=2000, step=5, label="能见度 visibility (m)",
                          help="Meteorological optical range in metres; lower = denser fog"),
        "fp16": Bool(default=False, label="半精度 fp16 (快约 20 倍，结果略有差异)",
                     help="Run Depth Pro in float16: much faster on GPU, depth differs by ~0.1 %"),
    }

    def apply(self, image, rng, visibility, fp16):
        # Deterministic: no randomness involved, rng is not used.
        # A single image has no input set to average over, so an image without sky
        # uses Clear2Fog's fallback light (0.8). The `degfw fog` command averages.
        c2f = engine(fp16)
        rgb = to_uint8(image)
        foggy = c2f.simulate(rgb, c2f.depth_from_array(rgb), visibility)
        return foggy.astype(np.float32) / 255.0


# ---- command line: degfw fog -i INPUT -o OUTPUT -v VISIBILITY ------------------------
INPUT_EXTS = {".png", ".jpg", ".jpeg"}  # as c2f.py


def collect_inputs(inputs: list[Path]) -> list[Path]:
    """Files as given; folders: their .png / .jpg / .jpeg files (not subfolders), as c2f.py."""
    images = []
    for p in inputs:
        p = Path(p)
        if p.is_dir():
            images += sorted(q for q in p.iterdir() if q.is_file() and q.suffix.lower() in INPUT_EXTS)
        elif p.is_file():
            images.append(p)
        else:
            raise FileNotFoundError(f"Not found: {p}")
    return list(dict.fromkeys(images))


def run_cli(inputs: list[Path], out_dir: Path, visibilities: list[int], fp16: bool = False) -> int:
    """Fog every input image at every visibility. Output names as in c2f.py:
    <out>/foggy_<name>_vis_<v>.png. Returns the number of failed images."""
    from PIL import Image

    try:
        images = collect_inputs(inputs)
    except FileNotFoundError as e:
        raise SystemExit(str(e)) from None
    if not images:
        raise SystemExit("No input images found (.png / .jpg / .jpeg)")
    bad = [v for v in visibilities if v <= 0]
    if bad:
        raise SystemExit(f"Visibility must be > 0 m, got {bad}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"{len(images)} image(s), visibility: {', '.join(f'{v} m' for v in visibilities)}")

    c2f = engine(fp16)
    average_done = False
    record = {"method": "Clear2Fog", "visibility_m": visibilities,
              "depth_pro_precision": "float16" if fp16 else "float32", "images": {}}
    failed = 0
    for i, path in enumerate(images, start=1):
        t = time.time()
        try:
            rgb, depth = c2f.load(path)
            light = c2f.sky_light(rgb, depth)
            if light is None and not average_done:
                avg, n_sky = c2f.set_average_light(images)
                average_done = True
                record["average_light"] = {"value": [round(float(x), 4) for x in avg], "images_with_sky": n_sky}
                print(f"  (no sky in {path.name}: average atmospheric light over the input set = "
                      f"{np.round(avg, 3).tolist()}, from {n_sky} image(s) with sky)")
            for v in visibilities:
                foggy = c2f.simulate(rgb, depth, v)
                Image.fromarray(foggy).save(out_dir / f"foggy_{path.stem}_vis_{v}.png")
            record["images"][path.name] = {
                "source": str(path),
                "atmospheric_light": "sky" if light is not None else "average of input set",
                "depth_m": {"min": round(float(depth.min()), 2), "median": round(float(np.median(depth)), 2)},
            }
            print(f"[{i}/{len(images)}] {path.name}: {time.time() - t:.1f} s"
                  + ("" if light is not None else "  (no sky -> average light)"))
        except Exception as e:  # keep going, like c2f.py
            failed += 1
            print(f"[{i}/{len(images)}] {path.name}: FAILED: {e}")
    (out_dir / "fog_run.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Done: {len(images) - failed} of {len(images)} image(s) -> {out_dir}")
    return failed


def _add_arguments(parser) -> None:
    parser.add_argument("-i", "--input", type=Path, nargs="+", required=True,
                        help="input image(s) and/or folder(s) with .png/.jpg/.jpeg")
    parser.add_argument("-o", "--output", type=Path, required=True, help="output folder")
    parser.add_argument("-v", "--visibility", type=int, nargs="+", default=[100],
                        help="visibility in metres, lower = denser fog (default 100); several values: one image each")
    parser.add_argument("--fp16", action="store_true",
                        help="run Depth Pro in float16: ~20x faster on an 8 GB GPU, results differ slightly "
                             "from Clear2Fog (default float32 = identical)")


def _run_command(args) -> int:
    reason = Fog.unavailable_reason()
    if reason:
        raise SystemExit(f"fog cannot run here:\n{reason}")
    return 1 if run_cli(args.input, args.output, args.visibility, fp16=args.fp16) else 0


register_command(
    "fog", help="add fog with Clear2Fog (Depth Pro depth + atmospheric scattering)",
    description="Add fog to images with Clear2Fog. Output: OUTPUT/foggy_<name>_vis_<v>.png",
    add_arguments=_add_arguments, run=_run_command)
