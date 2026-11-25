# Command line usage and caveats

This file collects the commands used to test each feature from the command line, and what to watch out for with each.
All commands are written for Windows PowerShell (the VS Code terminal) and are run from the repository root.
The method details of each degradation are in [degradations/](degradations/); all options of the contamination script are in [scripts/README.md](../scripts/README.md), or run it with `--help`.

> Lens contamination (water drops, opaque soiling, semi-transparent soiling) is not integrated into the framework yet; for now it runs separately with `scripts/contamination_examples.py`.
> Once it is integrated (M4), the commands in section 5 will change.

## 1. Preparation: enter the repository, set the paths

Run this block first in every new terminal. All commands below use its three variables:

```powershell
cd "D:\Laptops\Documents\GitHub\degradation-framework"
$src = "D:\TUBS\Masterarbeit\Phase 2\Demo\Input"     # input image folder
$out = "D:\TUBS\Masterarbeit\Phase 2\Demo\Output"    # top-level output folder
$tag = "261123_01"                                   # ID of this test run; use a new one each time so earlier results are not overwritten
```

- **Variables only live in the current terminal:** in a new terminal, run this block again.
- **Paths with spaces need quotes:** e.g. `Phase 2`. The quotes are already in the variable assignments, so `$src` can be used as it is;
  a combined path must be wrapped in double quotes as a whole, e.g. `"$out\Fog\$tag"`.
- **Input at run time:** for every degradation below there is also a version that asks for the values at run time. `Read-Host` prompts in the terminal; the command runs after you press Enter.

## 2. Overview of the commands

| Command | What it does |
|---|---|
| `uv run degfw list` | Lists all degradations and their parameters, and whether they can run on this machine; with missing dependencies or weights it shows `UNAVAILABLE` and the reason |
| `uv run degfw weights` | Shows whether the model weights are present; `--verify` checks the SHA-256, `--download` downloads missing weights |
| `uv run degfw run <name>` | Runs a single degradation, without a configuration file; parameters are given with `-p` |
| `uv run degfw apply -c <config>` | Chains several degradations as described in a configuration file |
| `uv run degfw fog` | The fog's own command, used like the original `c2f.py`; with LiDAR point clouds, `--lidar` corrects the depth |
| `uv run degfw gui` | Graphical interface (run `uv sync --extra gui` first) |
| `uv run python scripts/contamination_examples.py` | Lens contamination: water drops, opaque soiling, semi-transparent soiling |
| `uv run pytest` | Runs the tests |

## 3. General commands

```powershell
uv run degfw list
uv run degfw weights                  # add --verify to check the SHA-256, --download to download missing weights

# a single degradation (no configuration file); same result as degfw fog, output in the framework's format (see "Output" below)
uv run degfw run fog -i $src -o "$out\Fog_run\$tag" -p visibility=50 fp16=true
uv run degfw run fog -i $src -o "$out\Fog_run\$tag" -p visibility=50 fp16=true "lidar=$src\a9_dataset_r02_s03_Demo"   # with LiDAR

# several degradations chained by a configuration file
uv run degfw apply -c configs/example.yaml -i $src -o "$out\Apply\$tag"

# tests
uv run pytest -m "not slow"           # only those that need no model, under 1 second
uv run pytest                         # all, about 4 minutes, needs the GPU and the models
```

Caveats:
- **Parameters:** `-p` takes several `key=value` pairs. Values are parsed as YAML, so `50`, `0.1` and `true` become an integer, a float and a boolean.
  The parameters of each degradation are shown by `degfw list`.
- **Seeds:**
  - `degfw run` takes the seed from `--seed N`, default 0.
  - `degfw apply` uses the seed in the configuration file; `--seed N` overrides it for one run.
  - When a folder is processed, each image's seed is computed from this seed and the image's relative path. Adding or removing other images in the folder therefore does not change this image's result.
- **Subfolders:** `run` and `apply` process the images in all subfolders and keep the subfolder structure in the output.
- **Output:**
  - always `.png`;
  - next to each image a `.json` with the same name records the source, degradations, parameters and seed;
  - the output folder also gets a `pipeline.yaml`.
- **Images with the same name:** images in one folder with the same stem (e.g. `a.jpg` and `a.png`) are written as `a.png` and `a_2.png`, so they do not overwrite each other.
- **Portrait phone photos:** images are turned upright according to their EXIF orientation when read; the output images carry no orientation tag.
- **`degfw run fog` and `degfw fog` use the same fog code:** the same images at the same visibility give pixel-identical results,
  including LiDAR and the batch-average atmospheric light for images without sky ([decision 0010](decisions/0010-context-one-fog-code.md)). They differ only in usage and output:
  `degfw fog` takes several visibilities at once and writes `foggy_*.png` and `fog_run.json`; `degfw run fog` takes one visibility
  and writes the same output as any other degradation, with the fog's record (where depth and atmospheric light came from) under `info` in each image's `.json`.
  Also, `degfw run` goes into subfolders, `degfw fog` does not.
- **Interface:** without gradio installed, `degfw gui` only prints `GUI not installed. Run: uv sync --extra gui`.

## 4. Fog: `degfw fog`

Fixed values:

```powershell
# one visibility (metres)
uv run degfw fog -i $src -o "$out\Fog\$tag" -v 100

# several visibilities, one image each; --fp16 is much faster
uv run degfw fog -i $src -o "$out\Fog\$tag" -v 50 200 --fp16
```

Visibility entered at run time (several values allowed, separated by spaces):

```powershell
$v = (Read-Host "Visibility (metres, several allowed, separated by spaces)") -split '\s+'
uv run degfw fog -i $src -o "$out\Fog\$tag" -v $v
```

With LiDAR point clouds (TUMTraf dataset), add `--lidar` to correct the depth scale with the point clouds:

```powershell
# demo: images, point clouds and labels in the same folder
uv run degfw fog -i "$src\a9_dataset_r02_s03_Demo" -o "$out\Fog_lidar\$tag" -v 100 --fp16 --lidar "$src\a9_dataset_r02_s03_Demo"

# full dataset: -i is the image folder of one camera, --lidar the dataset root
uv run degfw fog -i "$src\a9_dataset_r02_s03\images\s110_camera_basler_south2_8mm" -o "$out\Fog_lidar\$tag" -v 100 --fp16 --lidar "$src\a9_dataset_r02_s03"
```

Caveats:
- **Intensity:**
  - `-v` is the visibility in metres, integers only; the smaller the value, the denser the fog. Without `-v` the default is 100.
  - For reference: 25 very dense, 50 dense, 100 medium, 250 light, 500 very light.
- **`--fp16`:** makes Depth Pro (the model that estimates depth) compute in half precision.
  - **Why it is faster:** in float32, Depth Pro needs almost 8 GB of video memory, which does not fit on the 8 GB GPU; the rest is moved to main memory, about 20 seconds per image.
    In float16 it needs about 3.7 GB, all in video memory, about 1 second per image.
  - **Cost:** compared with the original, each pixel differs by at most 2/255, which is not visible. Only without `--fp16` (float32) is the result pixel-identical to the original.
  - **Recommendation:** use `--fp16` for tests and previews. For generating a dataset, choose one precision and use it throughout, without mixing.
    The precision used is recorded as `depth_pro_precision` in `fog_run.json`.
- **First level only:** only `.png`, `.jpg` and `.jpeg` directly in the input folder are processed, not those in subfolders. `-i` accepts several files or folders.
- **Output:**
  - the output folder is created automatically;
  - results are named `foggy_<original name>_vis_<visibility>.png`, and a `fog_run.json` records the parameters of the run;
  - images with the same stem are renamed, e.g. `foggy_<name>_2_vis_100.png`, and the terminal shows this.
- **No sky (the terminal prints `no sky`):**
  - **Why sky is needed:** the colour and brightness of the fog (the atmospheric light) is estimated from the sky: pixels with a depth ≥ 1000 m count as sky.
    If an image has no such pixels, its atmospheric light cannot be estimated from the image itself.
  - **What happens now:** `degfw fog` uses the average atmospheric light of the images in the same input batch that have sky, computed from at most 100 of them; if no image in the batch has sky, it uses 0.8, a grey of about 204/255.
    The average, and how many images it was computed from, are recorded in `fog_run.json`.
  - **Watch out:** the same image without sky can get a different fog colour in different batches, and in a sequence the fog may jump from frame to frame.
    This has to be solved before a dataset is generated; see [open decision 3 in the roadmap](roadmap.md#open-decisions).
- **`--lidar` (depth corrected with point clouds):**
  - **Why:** with Depth Pro alone, the depth on roadside cameras is about 8 times too small, so the fog is much weaker than the nominal visibility: nominal 100 m looks like about 800 m.
    Add it whenever point clouds are available; details in [degradations/fog.md](degradations/fog.md) and [decision 0008](decisions/0008-fog-lidar-depth-scale.md).
  - **The first line** `LiDAR: ... 5 of 5 input image(s) listed`: how many input images have a point cloud in the labels.
  - **One line per image** `LiDAR: depth x 8.18 from 4829 points, error 2.3%`: the factor applied to the depth, the number of points used, the error after correction.
    `LiDAR not used: reason -> Depth Pro only` means this image used Depth Pro only.
  - **`degfw run fog` and configuration files support it too:** parameter `lidar`, e.g. `-p "lidar=$src\a9_dataset_r02_s03_Demo"`; a folder that does not exist is reported before any work.
  - **Time:** about 2 seconds per image (with `--fp16`). The full dataset has 1033 images per camera, so a full run takes over half an hour.
- The method and parameters in detail: [degradations/fog.md](degradations/fog.md).

## 5. Lens contamination: `scripts/contamination_examples.py`

### 5.1 Rules common to all three types

- **A spot is given as `X Y SIZE`:**
  - **X:** horizontal position, 0 = left edge, 1 = right edge;
  - **Y:** vertical position, 0 = top edge, 1 = bottom edge;
  - **SIZE:** size relative to the longer image side; 0.15 is small, 0.5 already large;
  - **Range:** X and Y must be between 0 and 1, SIZE greater than 0 and at most 1. Out of range, the script reports what is wrong and generates no image.
- **Position: exact for water drops, only a hint for the other two:**
  - **Water drops:** the network only draws the shape; the drawn drop is then moved as a whole so that its centroid lies exactly on (X, Y).
    If it splits into several pieces, they move together and keep their shape ([decision 0009](decisions/0009-droplet-exact-placement.md)).
    Measured error at most 1 pixel; when the network decided the position, it was on average 4 % to 20 % of the longer side off.
  - **Opaque and semi-transparent soiling:** X and Y are still only a hint to the network; the actual position deviates.
- **Several spots:** repeat the option, e.g. `--droplet 0.2 0.3 0.2 --droplet 0.7 0.6 0.15`; all spots go onto the same result image.
  All three types can also be given in the same command.
- **Only the types you give are run:**
  - an option without numbers (e.g. just `--droplet`) uses that type's default spot;
  - with no option at all, all three types run at their default spots.
  - So do not delete the `if (-not ...)` line in the run-time input commands below: when nothing is entered, it makes sure only that one type runs.
- **SIZE is only an approximate size:** the shape is drawn by a generator network, which does not guarantee that the drawn size equals SIZE.
  Measured for water drops (10 seeds per SIZE):
  - SIZE between 0.1 and 0.3 is the most stable; the actual size is about 0.8 times the nominal size (SIZE × longer side), but it varies by a factor of 2 to 3 between seeds;
  - at SIZE ≤ 0.1, some seeds produce no drop at all;
  - at SIZE ≥ 0.4, one spot splits into 2 to 4 drops; at 0.6 the whole image is covered.
  - Opaque and semi-transparent soiling use the same kind of network and show the same randomness.
  - The position of water drops is exact now (see the previous item), their size not yet; the next step is to set it exactly as well.
- **Seeds:**
  - `--seed N` fixes the shapes, default 0; all images use the same seed, so they get the same shapes;
  - `--seed random` draws a seed for each image;
  - the seed used is always written to `seed.json`, so the result can be reproduced with `--seed N`;
  - the seed only changes the shapes (and how many drops a spot splits into, the distortion, …); position and size are set only by `X Y SIZE`.
    A water drop's shape depends only on SIZE and the random numbers, no longer on its position.
- **Other options:**
  - `--recursive`: also process the images in subfolders;
  - `--save-input`: also save a copy of the input image, `input.png`;
  - `--square`: the earlier behaviour, crop to a square first and resize to 960×960 (966×966 for water drops).
- **Input formats:** `.png`, `.jpg`, `.jpeg`, `.bmp`, `.tif`, `.tiff`, `.webp`. `--image` accepts several files or folders.
- **Output:**
  - with a single input image, the results go directly into `--out`;
  - with several images, each image gets its own subfolder `--out\<image name>\`, and `--out` also gets a combined `seeds.json`;
  - for each type one result image plus its `_mask.png` (the contaminated area), and in addition `overview.png` (a comparison figure) and `seed.json` (seed and spots).
- **Needs an NVIDIA GPU:** the weights of the three models were saved on a GPU and can only be loaded on a machine with CUDA.
- **Parameters tuned for images of about 960 px:** pixel parameters such as the blur and the camera focal length (380 px) were set for images of about 960 px.
  At very different resolutions (e.g. 1920×1200) the edges look sharper or blurrier, and the water drops' zoom-in / zoom-out decision changes.

### 5.2 Water drops: `--droplet`

Fixed values:

```powershell
# one drop
uv run python scripts/contamination_examples.py --droplet 0.3 0.4 0.3 --image $src --out "$out\Droplet_testing\$tag"

# two drops on the same image
uv run python scripts/contamination_examples.py --droplet 0.2 0.3 0.2 --droplet 0.7 0.6 0.15 --image $src --out "$out\Droplet_testing\$tag"

# the original behaviour: the position only a hint to the network (for comparison)
uv run python scripts/contamination_examples.py --droplet 0.3 0.4 0.3 --droplet-placement network --image $src --out "$out\Droplet_testing\$tag"
```

Input at run time, variant 1: one input, drops separated by semicolons.

```powershell
$line  = Read-Host "Drops X Y SIZE, separated by semicolons (e.g. 0.3 0.4 0.2; 0.7 0.6 0.15)"
$drops = foreach ($d in ($line -split ';')) { if ($d.Trim()) { "--droplet"; $d.Trim() -split '\s+' } }
if (-not $drops) { $drops = @("--droplet") }
uv run python scripts/contamination_examples.py $drops --image $src --out "$out\Droplet_testing\$tag"
```

Input at run time, variant 2: one drop at a time, an empty line ends the input.

```powershell
$drops = @()
while ($true) {
    $d = Read-Host "Drop X Y SIZE (empty line to finish)"
    if ([string]::IsNullOrWhiteSpace($d)) { break }
    $drops += "--droplet"; $drops += $d.Trim() -split '\s+'
}
if (-not $drops) { $drops = @("--droplet") }
uv run python scripts/contamination_examples.py $drops --image $src --out "$out\Droplet_testing\$tag"
```

- **Default spot:** just `--droplet` gives `0.3 0.4 0.5`. According to the measurements in 5.1, SIZE 0.5 tends to split into several drops; for a single drop, use SIZE 0.1 to 0.3.
- **Exact placement:** the drop's centroid lies exactly on X Y.
  - **At the edge:** X and Y may be 0 or 1; the drop is put at the image edge and the part outside is cut off. Zoom-in / zoom-out is still decided by the drop's full size.
  - **Small SIZE retries:** if the network draws no drop at all (happens at SIZE ≤ 0.1), it is called again, up to 20 times, and the terminal says which attempt was used.
    The random numbers simply continue, so the result stays reproducible. If all 20 attempts fail, an error is reported and this image is not generated.
  - **Touching the edge of the network's canvas:** at large SIZE the shape may be cut off by the network's canvas; the terminal says so.
  - **The original behaviour:** with `--droplet-placement network`, X Y are only a hint to the network and the results are pixel-identical to before the change, for comparison.
- **Output:** `droplet.png` (the result) and `droplet_mask.png` (the area of all drops together).
  In `seed.json`, `droplet_placement` records which placement was used (`exact` / `network`);
  `droplet_placements` records for each drop the centroid reached (pixels), the shift, the number of network calls, and whether it touches the edge of the network's canvas.

### 5.3 Opaque soiling: `--opaque`

Fixed values:

```powershell
uv run python scripts/contamination_examples.py --opaque 0.5 0.5 0.3 --image $src --out "$out\Opaque_testing\$tag"
```

Input at run time, spots separated by semicolons:

```powershell
$line  = Read-Host "Spots X Y SIZE [colour], separated by semicolons (e.g. 0.3 0.5 0.2; 0.7 0.4 0.15 90 70 50)"
$spots = foreach ($s in ($line -split ';')) { if ($s.Trim()) { "--opaque"; $s.Trim() -split '\s+' } }
if (-not $spots) { $spots = @("--opaque") }
uv run python scripts/contamination_examples.py $spots --image $src --out "$out\Opaque_testing\$tag"
```

How to write a spot:
- **`X Y SIZE`:** uses the default colours (see the table below). Just `--opaque` uses the default spot `0.5 0.5 0.3`.
- **`X Y SIZE R G B`:** this spot in the given solid colour; RGB are integers from 0 to 255.
- **`X Y SIZE R1 G1 B1 R2 G2 B2`:** this spot as a gradient, from the edge colour R1 G1 B1 to the centre colour R2 G2 B2.

Instead of giving each spot a colour, colours can also be set for all spots. Add these options at the end of the command; each colour gives one image, all with the same shapes:
- **`--opaque-color 90 70 50`:** a solid colour; can be repeated for several colours;
- **`--opaque-gradient 139 90 43 0 0 0`:** a gradient (edge colour → centre colour); can also be repeated;
- **`--opaque-gamma 2`:** shifts the gradient. Above 1 more of the edge colour, below 1 more of the centre colour; default 0.5.
- These options without `--opaque` also generate opaque soiling at the default spot.

Colours and output files:

| Case | Output |
|---|---|
| No spot has its own colour, and no `--opaque-color` / `--opaque-gradient` | Two images: `opaque_black.png` (solid black), `opaque_brown.png` (gradient from brown 139 90 43 to black). Same shapes, different colours only |
| `--opaque-color` / `--opaque-gradient` given | One image per colour, e.g. `opaque_90_70_50.png`, `opaque_139_90_43_to_0_0_0.png` |
| Every spot has its own colour | Only one image, `opaque.png` |
| Some spots with a colour, some without | Spots with a colour keep it; the others follow the default (or given) colours, one image per colour |

### 5.4 Semi-transparent soiling: `--semi`

Fixed values:

```powershell
uv run python scripts/contamination_examples.py --semi 0.5 0.6 0.4 --semi-scale 50 --image $src --out "$out\Semi_testing\$tag"
```

Input at run time. It asks for three things in turn: spots (separated by semicolons), colour, noise scale; for the last two, an empty line keeps the default.

```powershell
$line  = Read-Host "Spots X Y SIZE [opacity], separated by semicolons (e.g. 0.5 0.6 0.4; 0.2 0.3 0.3 0.5)"
$color = Read-Host "Colour R G B (empty = default sand 194 178 128)"
$scale = Read-Host "Noise scale, several allowed (empty = default 10 and 1000)"
$a = foreach ($s in ($line -split ';')) { if ($s.Trim()) { "--semi"; $s.Trim() -split '\s+' } }
if (-not $a) { $a = @("--semi") }
if ($color.Trim()) { $a += "--semi-color"; $a += $color.Trim() -split '\s+' }
if ($scale.Trim()) { $a += "--semi-scale"; $a += $scale.Trim() -split '\s+' }
uv run python scripts/contamination_examples.py $a --image $src --out "$out\Semi_testing\$tag"
```

Settings:
- **Each spot:** `X Y SIZE`, or `X Y SIZE OPACITY`.
  - Position and size as in 5.1.
  - The 4th number is this spot's own opacity, 0 to 1: 1 is the original strength, 0.5 half of it, 0 invisible.
  - Just `--semi` uses the default spot `0.8 0.6 0.8`. The options below without `--semi` also generate semi-transparent soiling at the default spot.
- **`--semi-color R G B`:** the colour of the soiling, default sand 194 178 128.
  The original script used grey; for the same result as the original, use `--semi-color 125 125 125`.
- **`--semi-opacity`:** opacity for all spots, 0 to 1, default 1. Spots without a 4th number use it.
- **`--semi-scale`:** noise scale, which decides between fine grains and large patches: small values give fine grains, large values large patches.
  Several values are allowed, one image each, named e.g. `semi_scale50.png`. Without it, one image each for 10 and 1000.
- **How it is blended:** per pixel, result = image × (1 − a) + colour × a, with a = opacity × shape mask × noise texture.

Three things to watch out for:
- **Very slow:** the noise is computed pixel by pixel in pure Python, and the noise of the whole image is computed again for every spot and every noise scale.
  The larger the image and the more spots and scales, the slower it gets; large images such as 1920×1200 can take quite a while. Try a single scale first, e.g. `--semi-scale 50`.
- **The noise texture does not depend on the seed:** with the same image size and scale, the texture is exactly the same. The seed only changes the outline of the soiling.
- **Light colours are hard to see:** even at opacity 1 the soiling covers only about 30 % on average (shape and noise are both below 1). On bright scenes a light colour is hard to see;
  use a darker colour or larger spots.

## 6. When something goes wrong

| Symptom | Cause and fix |
|---|---|
| A degradation shows `UNAVAILABLE` in `degfw list` | The reason follows: for a missing Python package run `uv sync`; for missing weights run `uv run degfw weights --download` |
| The contamination script says `no images found` | The image format is not supported (formats in 5.1), or the images are in subfolders and `--recursive` is missing |
| The contamination script says something like `x and y must be in 0..1, size in (0, 1]` | A value is out of range; correct it as the message says. No image is generated in this case |
| The contamination script says `the network drew no droplet in 20 attempts` | The water drop's SIZE is too small for the network; use a larger SIZE. This image is not generated, the others are processed as usual |
| `degfw gui` says `GUI not installed` | Run `uv sync --extra gui` first |
| Fog is very slow (about 20 seconds per image) | `--fp16` is missing, see section 4 |
| With `--lidar`: `No TUMTraf (OpenLABEL) label files with LiDAR frames found` | The given folder (including subfolders) contains no TUMTraf label files. Check the path; usually give the dataset root |
