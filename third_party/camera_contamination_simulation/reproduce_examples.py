"""Run the contamination generators of this repository on one or more images.

Equivalent to usage_example.ipynb, but
- works with any input image (the notebook's examples/ folder is not in the repo),
- fixes the random seeds, so a run can be repeated exactly,
- saves every result as a file instead of only showing it,
- you choose position, size and number of every contamination on the command line,
- can process many images or whole folders.

Contaminations are given as spots:  --opaque X Y SIZE  /  --semi X Y SIZE  /  --droplet X Y SIZE
  X     horizontal position, 0 = left edge, 1 = right edge
  Y     vertical position,   0 = top edge,  1 = bottom edge
  SIZE  size relative to the longer image side (0.15 small, 0.5 already large)
Repeat an option to add more spots of that type; all of them go onto ONE result image.
Only the types you give are run (--opaque-color / --opaque-gradient alone also count as
--opaque at its default spot). Defaults (DEFAULT_SPOTS below):
  --droplet            without numbers -> that type at its default spot
  no option at all     -> all three types at their default spots (the notebook examples)

Usage (from this folder, with the environment activated):

    # all three types at the default spots
    uv run python reproduce_examples.py --image IMG.jpg --out OUT

    # only water droplets, at the default spot
    uv run python reproduce_examples.py --droplet --image PATH/TO/FOLDER --out OUT

    # one water droplet in the upper right, for every image in a folder (add --recursive for subfolders)
    uv run python reproduce_examples.py --droplet 0.8 0.2 0.3 --image PATH/TO/FOLDER --out OUT

    # three droplets on the same image
    uv run python reproduce_examples.py --droplet 0.2 0.3 0.2 --droplet 0.6 0.5 0.15 --droplet 0.8 0.8 0.1 --image IMG.jpg --out OUT

    # opaque soiling in the centre and one droplet, several files and folders at once
    uv run python reproduce_examples.py --opaque 0.5 0.5 0.3 --droplet 0.2 0.2 0.2 --image a.jpg b.png FOLDER --out OUT

    # opaque soiling in your own colour (RGB 0..255), two spots
    uv run python reproduce_examples.py --opaque 0.3 0.5 0.2 --opaque 0.7 0.4 0.15 --opaque-color 90 70 50 --image IMG.jpg --out OUT

    # several colours at once: one result per colour, all with the same shapes
    uv run python reproduce_examples.py --opaque --opaque-color 0 0 0 --opaque-color 90 70 50 --image IMG.jpg --out OUT

    # gradient: edge colour -> centre colour; --opaque-gamma > 1 shows more of the edge colour
    uv run python reproduce_examples.py --opaque --opaque-gradient 139 90 43 0 0 0 --opaque-gamma 2 --image IMG.jpg --out OUT

    # earlier behaviour: centre-crop to a square
    uv run python reproduce_examples.py --droplet 0.3 0.4 0.5 --image IMG.jpg --out OUT --square

    # random shapes: every image draws its own seed (printed and saved to seed.json)
    uv run python reproduce_examples.py --droplet 0.3 0.4 0.5 --seed random --image FOLDER --out OUT

    # reproduce one result of a random run: same spots, seed from its seed.json
    uv run python reproduce_examples.py --droplet 0.3 0.4 0.5 --seed 1234567 --image IMG.jpg --out OUT

Output: with a single input image the results go directly into --out; with several,
each image gets its own subfolder --out/<image name>/. Per type: opaque_black.png and
opaque_brown.png (same shapes, two colours; with --opaque-color / --opaque-gradient one
file per given colour instead, e.g. opaque_90_70_50.png, opaque_139_90_43_to_0_0_0.png),
semi_scale10.png and semi_scale1000.png (two noise scales), droplet.png; each with a
_mask.png, plus overview.png and seed.json.
With --save-input also input.png, a copy of the input image (not saved by default).

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
- --seed N (default 0): fixed, every image uses seed N, so all images get the same
  shapes. --seed random: each image draws its own seed. Either way the seed used is
  printed and written to seed.json in the image's output folder (and, for several
  images, to seeds.json in --out), so any result can be reproduced with --seed N.
- The seed only changes the shapes (and how many separate droplets one spot
  splits into, distortion, ...). Position and size come from the spots. seed.json
  also records the spots, so it holds everything needed to rerun a result.
"""

from __future__ import annotations

import argparse
import json
import random
import secrets
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

# Default spots [x, y, size], used when an option is given without numbers (e.g. just
# --droplet) or when no option is given at all (then all three types are run).
# Taken from usage_example.ipynb. Edit here to change the defaults.
DEFAULT_SPOTS = {
    "opaque": [[0.5, 0.5, 0.3]],
    "semi": [[0.8, 0.6, 0.8]],
    "droplet": [[0.3, 0.4, 0.5]],
}

# Colours of the opaque soiling, used when neither --opaque-color nor --opaque-gradient
# is given: one solid black result and one brown-to-black gradient result.
OPAQUE_BLUR = (51, 51)  # Gaussian kernel (px, odd) that softens the edge of the opaque mask
OPAQUE_GAMMA = 0.5  # default for --opaque-gamma
DEFAULT_OPAQUE_VARIANTS = [
    {"name": "opaque_black", "color": [0, 0, 0]},
    {"name": "opaque_brown", "edge": [139, 90, 43], "centre": [0, 0, 0]},
]
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def parse_seed(value: str) -> int | None:
    """--seed: an integer (fixed) or 'random' (returned as None)."""
    if value.lower() == "random":
        return None
    try:
        seed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"must be an integer or 'random', got {value!r}") from None
    if not 0 <= seed < 2**32:
        raise argparse.ArgumentTypeError(f"must be between 0 and {2**32 - 1}")
    return seed


def draw_seed() -> int:
    # Not from random / np.random: those are re-seeded before every generator call.
    return secrets.randbelow(2**31)


def as_unit(mask: np.ndarray) -> np.ndarray:
    """Mask as float32 in 0..1 (opaque/semi return float 0..1, droplet returns uint8 0..255)."""
    m = mask.astype(np.float32)
    return m / 255.0 if np.issubdtype(mask.dtype, np.integer) else m


def apply_spots(img: np.ndarray, spots: list[list[float]], apply) -> tuple[np.ndarray, np.ndarray]:
    """Applies apply(img, x, y, size) -> (img, mask) for every spot, each on the result
    of the previous one. Returns the final image and the merged (max) mask in 0..1."""
    merged = None
    for x, y, size in spots:
        img, mask = apply(img, x, y, size)
        merged = as_unit(mask) if merged is None else np.maximum(merged, as_unit(mask))
    return img, merged


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


def process_image(path: Path, out: Path, args: argparse.Namespace, generators: dict) -> int:
    """Returns the seed used for this image."""
    raw = read_rgb(path)  # read first, so an unreadable file leaves no empty output folder
    out.mkdir(parents=True, exist_ok=True)
    if args.square:
        img960 = centre_square(raw, 960)  # opaque and semi-transparent soiling
        img966 = centre_square(raw, DROPLET_SIZE)  # droplet
        print(f"Input {path.name}: {raw.shape[1]}x{raw.shape[0]} px -> centre square (960 / {DROPLET_SIZE} px)")
    else:
        img960 = img966 = raw  # names kept from the square mode; here both are the original image
        print(f"Input {path.name}: {raw.shape[1]}x{raw.shape[0]} px, used at original size")

    seed = args.seed if args.seed is not None else draw_seed()
    print(f"  seed = {seed}" + (" (random)" if args.seed is None else ""))

    results = []  # (title, image, mask)

    # Every --opaque / --semi / --droplet X Y SIZE given on the command line is one
    # spot. All spots of one type are applied one after another onto the same image
    # (so N spots = N contaminations in one result), and their masks are merged.
    # The seed is set once before the spots, so each spot gets a different shape,
    # and the whole result is still reproducible from the seed.

    # 1. Opaque soiling (mud, dirt), in two colours. Both variants use the same
    #    seed, so they have the same shapes and differ only in colour.
    if args.opaque:
        opaque = generators["opaque"]
        for variant in args.opaque_variants:
            if "color" in variant:  # one solid colour
                def apply(im, x, y, s, v=variant):
                    return opaque.apply_mask_to_image(
                        im, x, y, s, mask_color=tuple(v["color"]), blur_kernel_size=OPAQUE_BLUR)
            else:  # gradient from the edge colour to the centre colour
                def apply(im, x, y, s, v=variant):
                    return opaque.apply_mask_to_image_twoc(
                        im, x, y, s, color_start=tuple(v["edge"]), color_end=tuple(v["centre"]),
                        blur_kernel_size=OPAQUE_BLUR, gamma=v["gamma"])  # fmt: skip
            set_seed(seed)
            img, mask = apply_spots(img960, args.opaque, apply)
            results.append((variant["name"], img, mask))
        print(f"  opaque: {len(args.opaque)} spot(s), {len(args.opaque_variants)} colour variant(s)")

    # 2. Semi-transparent soiling (dust, sand): Perlin noise texture, at two noise scales.
    #    Slow: one noise evaluation per pixel (about 1 million at 960x960), so the time grows
    #    with the image size and the number of spots.
    if args.semi:
        semi = generators["semi"]
        for scale in (10, 1000):
            set_seed(seed)
            t = time.time()
            img, mask = apply_spots(img960, args.semi, lambda im, x, y, s: semi.apply_mask_with_perlin_noise(
                im, x, y, s, mask_color=(125, 125, 125), noise_scale=scale))  # fmt: skip
            print(f"  semi-transparent, noise scale {scale}: {len(args.semi)} spot(s), {time.time() - t:.1f} s")
            results.append((f"semi_scale{scale}", img, mask))

    # 3. Water droplets. The network mask of one spot can contain several separate
    #    droplets; each is judged ZoomIn/ZoomOut by its own size.
    if args.droplet:
        droplet = generators["droplet"]
        cases = []

        def apply_droplet(im, x, y, s):
            out_img, m = droplet.simulate_droplet(
                f_C=F_C, raw_img=im, x=x, y=y, size=s,
                mask_blurr_gauss_kernel=41, blur_sigma=0, b_strength=0.001,
                ib_gauss_kernel=201, blurr_roi_gauss_kernel=41, mood="black", mask_threshold=MASK_THRESHOLD,
            )  # fmt: skip
            cases.extend(d["case"] for d in droplet.last_droplets)
            return out_img, m

        set_seed(seed)
        img, mask = apply_spots(img966, args.droplet, apply_droplet)
        print(f"  droplet: {len(args.droplet)} spot(s) -> {len(cases)} droplet(s): "
              f"{cases.count('ZoomIn')} ZoomIn, {cases.count('ZoomOut')} ZoomOut")  # fmt: skip
        results.append(("droplet", img, mask))

    # Save individual files and one overview figure
    if not args.save_input:
        pass  # default: no copy of the input image (use --save-input to keep one)
    elif args.square:
        if args.opaque or args.semi:
            save_rgb(out / "input.png", img960)
        if args.droplet:
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

    record = {
        "image": str(path), "seed": seed, "mode": "random" if args.seed is None else "fixed",
        "square": args.square,
        # spots as [x, y, size]; rerun with the same --opaque/--semi/--droplet and --seed to reproduce
        "opaque": args.opaque, "semi": args.semi, "droplet": args.droplet,
        # opaque colours (RGB 0..255): "color" = solid, "edge"/"centre"/"gamma" = gradient
        "opaque_colors": args.opaque_variants if args.opaque else [],
    }  # fmt: skip
    (out / "seed.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return seed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the contamination generators on one or more images.")
    parser.add_argument(
        "--image", type=Path, nargs="+", required=True, help="Clean input image(s) and/or folder(s) with images"
    )
    parser.add_argument("--out", type=Path, required=True, help="Folder for the results (created if missing)")
    spot_help = (
        "X Y SIZE, each 0..1 (X: left->right, Y: top->bottom, SIZE: relative to the longer side). "
        "Repeat for more spots. Without numbers: the default spot(s) {}."
    )
    for name, what in (("opaque", "opaque soiling"), ("semi", "semi-transparent soiling"), ("droplet", "water droplet")):
        parser.add_argument(
            f"--{name}", nargs="*", type=float, action="append", metavar="X Y SIZE",
            help=f"Add {what}: " + spot_help.format(DEFAULT_SPOTS[name]),
        )  # fmt: skip
    parser.add_argument(
        "--opaque-color", nargs=3, type=int, action="append", metavar=("R", "G", "B"),
        help="Opaque soiling in one solid colour, RGB 0..255. Repeat for more colours (one result each, same shapes).",
    )  # fmt: skip
    parser.add_argument(
        "--opaque-gradient", nargs=6, type=int, action="append", metavar=("R1", "G1", "B1", "R2", "G2", "B2"),
        help="Opaque soiling as a gradient: edge colour R1 G1 B1 -> centre colour R2 G2 B2. Repeatable.",
    )  # fmt: skip
    parser.add_argument(
        "--opaque-gamma", type=float, default=OPAQUE_GAMMA,
        help=f"Gradient shape (default {OPAQUE_GAMMA}): < 1 more of the centre colour, > 1 more of the edge colour",
    )  # fmt: skip
    parser.add_argument("--recursive", action="store_true", help="Also search subfolders of the given folders")
    parser.add_argument(
        "--seed", type=parse_seed, default=0,
        help="Integer for reproducible results (default 0), or 'random' for a new seed per image",
    )  # fmt: skip
    parser.add_argument(
        "--square", action="store_true", help="Centre-crop to 960x960 / 966x966 as before, instead of using the original size"
    )
    parser.add_argument("--save-input", action="store_true", help="Also save a copy of the input image (input.png); off by default")
    args = parser.parse_args()

    # Opaque colours. Giving a colour without --opaque means: opaque at its default spot.
    colour_given = bool(args.opaque_color or args.opaque_gradient)
    if colour_given and not args.opaque:
        args.opaque = [[]]
    if args.opaque_gamma <= 0:
        parser.error(f"--opaque-gamma must be > 0, got {args.opaque_gamma:g}")
    for values in (args.opaque_color or []) + (args.opaque_gradient or []):
        if not all(0 <= v <= 255 for v in values):
            parser.error(f"colour values must be 0..255, got {' '.join(map(str, values))}")
    if colour_given:
        variants = [{"name": "opaque_" + "_".join(map(str, c)), "color": c} for c in args.opaque_color or []]
        variants += [
            {"name": "opaque_" + "_".join(map(str, g[:3])) + "_to_" + "_".join(map(str, g[3:])),
             "edge": g[:3], "centre": g[3:]}
            for g in args.opaque_gradient or []
        ]  # fmt: skip
        variants = list({v["name"]: v for v in variants}.values())  # same colour twice -> once
    else:
        variants = [dict(v) for v in DEFAULT_OPAQUE_VARIANTS]
    for v in variants:
        if "edge" in v:
            v["gamma"] = args.opaque_gamma
    args.opaque_variants = variants

    # No option at all: all three types with their default spots
    use_all_defaults = not any(getattr(args, name) for name in GENERATORS)
    selected = []
    for name in GENERATORS:
        entries = getattr(args, name) or ([[]] if use_all_defaults else [])
        spots = []
        for entry in entries:
            if not entry:  # option without numbers -> default spot(s)
                spots += [list(s) for s in DEFAULT_SPOTS[name]]
                continue
            if len(entry) != 3:
                parser.error(f"--{name} needs 3 numbers (X Y SIZE) or none for the default, got {len(entry)}")
            x, y, size = entry
            if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < size <= 1):
                parser.error(f"--{name} {x:g} {y:g} {size:g}: x and y must be in 0..1, size in (0, 1]")
            spots.append(entry)
        setattr(args, name, spots)
        if spots:
            selected.append(f"{name} x{len(spots)}")
    if use_all_defaults:
        print("No --opaque / --semi / --droplet given: running all three at their default spots")

    images = collect_images(args.image, args.recursive)
    if not images:
        parser.error("no images found (supported: " + ", ".join(sorted(IMAGE_EXTENSIONS)) + ")")
    print(f"{len(images)} image(s), spots: {', '.join(selected)}")

    # Load only the models that are needed, once for all images
    generators = {}
    if args.opaque:
        generators["opaque"] = OpaqueContaminationGenerator("gen_models/best_model_total.pth")
    if args.semi:
        generators["semi"] = SemiContaminationGenerator("gen_models/best_model_semi.pth")
    if args.droplet:
        generators["droplet"] = DropletGenerator(model_path="gen_models/best_model_droplet.pth")

    failed, seeds = [], {}
    for i, (path, out) in enumerate(zip(images, output_folders(images, args.out)), start=1):
        print(f"[{i}/{len(images)}] ", end="")
        try:
            seeds[out.name] = {"image": str(path), "seed": process_image(path, out, args, generators)}
        except Exception as e:  # keep going with the other images
            print(f"  FAILED: {e}")
            failed.append(path)
    if len(images) > 1 and seeds:  # with one image, its seed.json already sits in --out
        summary = {"mode": "random" if args.seed is None else "fixed", "images": seeds}
        (args.out / "seeds.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Done: {len(images) - len(failed)} of {len(images)} image(s). Results in {args.out}")
    for path in failed:
        print(f"  failed: {path}")


if __name__ == "__main__":
    main()
