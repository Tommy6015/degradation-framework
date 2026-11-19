# Fog `fog` (Clear2Fog)

Code: `degradation_fw/degradations/weather/fog.py`; third-party code: `third_party/Clear2Fog/` (Depth Pro + camera fog).

## Usage

As with Clear2Fog's `c2f.py`, only input, output and visibility (metres; lower = denser fog) are needed:

```bash
uv run degfw fog -i image_or_folder -o output_folder -v 100
```

- `-v` accepts several values, e.g. `-v 25 50 100 250 500`: the depth of each image is estimated once, and one image is written per visibility.
- Output names as in `c2f.py`: `foggy_<original name>_vis_<visibility>.png`, directly in the output folder; plus `fog_run.json` with the parameters.
  If images in different folders have the same name (or `a.jpg` sits next to `a.png`), the later ones get `_2`, `_3` and do not overwrite earlier results.
- float32 by default, **pixel-identical** to the original Clear2Fog (for images without an EXIF orientation tag). On an 8 GB GPU, Depth Pro does not fit in memory and takes about 20 s per image;
  with `--fp16` about 1 s per image, at most 2/255 different from the original in each pixel.
- Images with an EXIF orientation tag, such as portrait photos from phones, are turned upright before the fog is added, and the output is upright (the original `c2f.py` fails on such photos or gets an upside-down depth).
- Before the first use, download the Depth Pro weights (about 1.9 GB, not in git): `uv run degfw weights --download`.
- Like any other degradation, it can also be used as `uv run degfw run fog -i input -o output -p visibility=50`,
  or in a YAML pipeline: `- name: fog` + `params: {visibility: 50, fp16: true}`.

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `visibility` | Int, 5–2000 | 100 | Visibility (meteorological optical range) in metres; lower = denser fog |
| `fp16` | Bool | false | Run Depth Pro in half precision: about 20x faster, depth differs by about 0.1 % (median), results differ slightly |

## Method (same as Clear2Fog)

1. Depth Pro estimates a metric depth map (metres) from the single image.
2. Atmospheric light L: dark channel prior, restricted to pixels ≥ 1000 m away (the sky); its luminance is clipped to [162, 220] / 255 and used as grey.
   Images without sky use the average L over the input set (up to 100 images), or 0.8 if none of them has sky either.
3. Koschmieder's law: t = exp(-β · depth), β = -ln(0.05) / visibility; foggy = clear · t + L · (1 - t).

Call order: section 3.2 of [architecture.md](../architecture.md); output files and the fields of `fog_run.json`: section 4.3.

## Differences to running `c2f.py`

For images without an EXIF orientation tag, none of these changes the result (float32 pixel-identical, covered by the regression test in `tests/degradations/test_fog.py`):

- Photos with an orientation tag are turned upright first, and RGB and depth come from the same pixels ([decision 0004](../decisions/0004-exif-orientation.md)).
- The average atmospheric light is computed only when an image without sky comes up, from a sample drawn with a fixed seed (`c2f.py`: always at the start, unseeded sample); with up to 100 input images the sample is all images, as in `c2f.py`.
- With several visibilities in one run, the depth of each image is computed only once.
- Clear2Fog's `src/fog_pipeline/__init__.py` is bypassed, so its LiDAR part and PyQt5 are not needed.
- Output names of inputs with the same name get `_2`, `_3` ([decision 0005](../decisions/0005-output-name-collisions.md)); `c2f.py` overwrites them.

## `degfw fog` versus `degfw run fog`

| | `degfw fog` | `degfw run fog` / configuration file / GUI |
|---|---|---|
| Focal length | From the file's EXIF (if present) | Estimated by Depth Pro (the framework's degradation interface only gets the pixels) |
| Images without sky | Average atmospheric light of the whole input set | Always 0.8 |
| Output | `foggy_*_vis_*.png` + `fog_run.json` | As for every degradation: `.png` + `.json` of the same name |

So for photos with an EXIF focal length, or images without sky, the two ways can give different results.
