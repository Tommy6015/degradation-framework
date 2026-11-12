"""Run the contamination generators of this repository on one or more images.

Equivalent to usage_example.ipynb, but
- works with any input image (the notebook's examples/ folder is not in the repo),
- fixes the random seeds, so a run can be repeated exactly,
- saves every result as a file instead of only showing it,
- can run only some of the generators (--only) and process many images or whole folders.

Usage (from the repository root, with the environment activated):

    # one image, all three generators
    uv run python reproduce_examples.py --image PATH/TO/IMAGE.jpg --out PATH/TO/OUTPUT_FOLDER

    # only water droplets, for every image in a folder (add --recursive for subfolders)
    uv run python reproduce_examples.py --only droplet --image PATH/TO/FOLDER --out PATH/TO/OUTPUT_FOLDER

    # several files and folders at once; --only takes one or more of: opaque semi droplet
    uv run python reproduce_examples.py --only droplet opaque --image a.jpg b.png PATH/TO/FOLDER --out OUT

    # earlier behaviour: centre-crop to a square
    uv run python reproduce_examples.py --image PATH/TO/IMAGE.jpg --out PATH/TO/OUTPUT_FOLDER --square

Output: with a single input image the results go directly into --out; with several,
each image gets its own subfolder --out/<image name>/.

Notes:
- By default the image is used at its own size (any width and height); all
  generators in contamination_simulation.py accept any size. Shapes are not
  stretched: the 64x64 mask is scaled uniformly to a max(H, W) square and
  centre-cropped, and x, y stay positions in the image (see image_to_model_xy).
- --square reproduces the earlier behaviour: centre-crop to a square and resize
  to 960x960 (opaque, semi-transparent) and 966x966 (droplet), as in the notebook.
- The pixel parameters below (blur kernels, b_strength, F_C) were tuned for images
  of about 960 px. On much larger or smaller images the edges look sharper or
  blurrier; F_C (in px) should be scaled with the image resolution, otherwise the
  droplet's ZoomIn/ZoomOut decision changes.
- The shape network draws random noise inside forward(), so without fixed seeds
  every call gives a different shape. The seeds are reset before every generator
  call, so each image's result does not depend on the other images in the batch.
"""

from __future__ import annotations

import argparse
import random
import time
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")  # save figures to files, no window needed
import matplotlib.pyplot as plt
import numpy as np
import torch

from contamination_simulation import DropletGenerator, OpaqueContaminationGenerator, SemiContaminationGenerator

DROPLET_SIZE = 966  # size used in the original example (defisheyed WoodScape images)
F_C = 380  # camera focal length in px used by the authors for WoodScape (see end of contamination_simulation.py)
MASK_THRESHOLD = 0.5  # mask value from which a pixel counts as droplet (bounding box / ZoomIn-ZoomOut decision)
GENERATORS = ("opaque", "semi", "droplet")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def read_rgb(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)  # works with non-ASCII Windows paths
    bgr = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if bgr is None:
        raise OSError(f"Could not read image: {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def centre_square(img: np.ndarray, size: int) -> np.ndarray:
    h, w = img.shape[:2]
    s = min(h, w)
    top, left = (h - s) // 2, (w - s) // 2
    return cv2.resize(img[top : top + s, left : left + s], (size, size), interpolation=cv2.INTER_AREA)


def write_png(path: Path, img: np.ndarray) -> None:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise OSError(f"Could not encode image: {path}")
    buf.tofile(str(path))  # works with non-ASCII Windows paths


def save_rgb(path: Path, img: np.ndarray) -> None:
    write_png(path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))


def save_mask(path: Path, mask: np.ndarray) -> None:
    m = mask.astype(np.float32)
    if m.max() > 1.0:
        m = m / 255.0
    write_png(path, (np.clip(m, 0, 1) * 255).astype(np.uint8))


def collect_images(inputs: list[Path], recursive: bool) -> list[Path]:
    """Expands the --image arguments: files are taken as they are, folders are searched for images."""
    images = []
    for path in inputs:
        if path.is_dir():
            found = path.rglob("*") if recursive else path.iterdir()
            images += sorted(p for p in found if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
        elif path.is_file():
            images.append(path)
        else:
            raise FileNotFoundError(f"Not found: {path}")
    return list(dict.fromkeys(images))  # drop duplicates, keep order


def output_folders(images: list[Path], out: Path) -> list[Path]:
    """One image: --out itself. Several: --out/<image name>, made unique if two images share a name."""
    if len(images) == 1:
        return [out]
    folders, used = [], set()
    for image in images:
        name, n = image.stem, 2
        while name.lower() in used:
            name, n = f"{image.stem}_{n}", n + 1
        used.add(name.lower())
        folders.append(out / name)
    return folders


def process_image(path: Path, out: Path, args: argparse.Namespace, generators: dict) -> None:
    raw = read_rgb(path)  # read first, so an unreadable file leaves no empty output folder
    out.mkdir(parents=True, exist_ok=True)
    if args.square:
        img960 = centre_square(raw, 960)  # opaque and semi-transparent soiling
        img966 = centre_square(raw, DROPLET_SIZE)  # droplet
        print(f"Input {path.name}: {raw.shape[1]}x{raw.shape[0]} px -> centre square (960 / {DROPLET_SIZE} px)")
    else:
        img960 = img966 = raw  # names kept from the square mode; here both are the original image
        print(f"Input {path.name}: {raw.shape[1]}x{raw.shape[0]} px, used at original size")

    results = []  # (title, image, mask)

    # 1. Opaque soiling (mud, dirt): same parameters as the notebook
    if "opaque" in generators:
        opaque = generators["opaque"]
        set_seed(args.seed)
        img, mask = opaque.apply_mask_to_image(img960, 0.5, 0.5, 0.3, mask_color=(0, 0, 0), blur_kernel_size=(51, 51))
        results.append(("opaque_black", img, mask))
        img, mask = opaque.apply_mask_to_image_twoc(
            img960, 0.5, 0.5, 0.2, color_start=(139, 90, 43), color_end=(0, 0, 0), blur_kernel_size=(51, 51), gamma=0.5
        )
        results.append(("opaque_brown", img, mask))

    # 2. Semi-transparent soiling (dust, sand): Perlin noise texture.
    #    Slow: one noise evaluation per pixel (about 1 million at 960x960), so the time grows with the image size.
    if "semi" in generators:
        for scale in (10, 1000):
            set_seed(args.seed)
            t = time.time()
            img, mask = generators["semi"].apply_mask_with_perlin_noise(
                img960, 0.8, 0.6, 0.8, mask_color=(125, 125, 125), noise_scale=scale
            )
            print(f"  semi-transparent, noise scale {scale}: {time.time() - t:.1f} s")
            results.append((f"semi_scale{scale}", img, mask))

    # 3. Water droplet: the notebook example plus two small droplets of the SAME
    #    size at different positions. The network mask can contain several separate
    #    droplets; each is judged ZoomIn/ZoomOut by its own size (simulate_droplet
    #    prints one line per droplet).
    if "droplet" in generators:
        droplet = generators["droplet"]
        for name, x, y, size in (
            ("droplet_notebook", 0.3, 0.4, 0.5),  # parameters of usage_example.ipynb
            ("droplet_small_topleft", 0.1, 0.1, 0.15),
            ("droplet_small_bottomright", 0.7, 0.7, 0.15),
        ):
            set_seed(args.seed)
            img, mask = droplet.simulate_droplet(
                f_C=F_C, raw_img=img966, x=x, y=y, size=size,
                mask_blurr_gauss_kernel=41, blur_sigma=0, b_strength=0.001,
                ib_gauss_kernel=201, blurr_roi_gauss_kernel=41, mood="black", mask_threshold=MASK_THRESHOLD,
            )  # fmt: skip
            cases = [d["case"] for d in droplet.last_droplets]
            if cases:
                print(f"  {name}: {len(cases)} droplet(s): {cases.count('ZoomIn')} ZoomIn, {cases.count('ZoomOut')} ZoomOut")
            else:
                print(f"  {name}: empty mask (no droplet generated)")
            results.append((name, img, mask))

    # Save individual files and one overview figure
    if args.square:
        if "opaque" in generators or "semi" in generators:
            save_rgb(out / "input.png", img960)
        if "droplet" in generators:
            save_rgb(out / "input_droplet.png", img966)  # the droplet input differs (966 px) in square mode
    else:
        save_rgb(out / "input.png", raw)
    for title, img, mask in results:
        save_rgb(out / f"{title}.png", img)
        save_mask(out / f"{title}_mask.png", mask)

    fig, axes = plt.subplots(len(results), 2, figsize=(8, 4 * len(results)), squeeze=False)
    for row, (title, img, mask) in zip(axes, results):
        row[0].imshow(img)
        row[0].set_title(title)
        row[1].imshow(mask, cmap="gray")
        row[1].set_title(f"{title} mask")
        for ax in row:
            ax.axis("off")
    fig.tight_layout()
    fig.savefig(out / "overview.png", dpi=80)
    plt.close(fig)  # free memory when processing many images


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the contamination generators on one or more images.")
    parser.add_argument(
        "--image", type=Path, nargs="+", required=True, help="Clean input image(s) and/or folder(s) with images"
    )
    parser.add_argument("--out", type=Path, required=True, help="Folder for the results (created if missing)")
    parser.add_argument(
        "--only", nargs="+", choices=GENERATORS, default=list(GENERATORS), help="Generators to run (default: all three)"
    )
    parser.add_argument("--recursive", action="store_true", help="Also search subfolders of the given folders")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--square", action="store_true", help="Centre-crop to 960x960 / 966x966 as before, instead of using the original size"
    )
    args = parser.parse_args()

    images = collect_images(args.image, args.recursive)
    if not images:
        parser.error("no images found (supported: " + ", ".join(sorted(IMAGE_EXTENSIONS)) + ")")
    print(f"{len(images)} image(s), generators: {', '.join(args.only)}")

    # Load only the selected models, once for all images
    generators = {}
    if "opaque" in args.only:
        generators["opaque"] = OpaqueContaminationGenerator("gen_models/best_model_total.pth")
    if "semi" in args.only:
        generators["semi"] = SemiContaminationGenerator("gen_models/best_model_semi.pth")
    if "droplet" in args.only:
        generators["droplet"] = DropletGenerator(model_path="gen_models/best_model_droplet.pth")

    failed = []
    for i, (path, out) in enumerate(zip(images, output_folders(images, args.out)), start=1):
        print(f"[{i}/{len(images)}] ", end="")
        try:
            process_image(path, out, args, generators)
        except Exception as e:  # keep going with the other images
            print(f"  FAILED: {e}")
            failed.append(path)
    print(f"Done: {len(images) - len(failed)} of {len(images)} image(s). Results in {args.out}")
    for path in failed:
        print(f"  failed: {path}")


if __name__ == "__main__":
    main()
