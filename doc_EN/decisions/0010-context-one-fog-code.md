# 0010: Degradations get source information beyond the pixels; the fog has one processing code

- Status: accepted
- Date: 2026-11-25
- Related: `degradation_fw/core/context.py` (`Context`), `core/base.py`, `core/pipeline.py`, `core/params.py` (`Folder`),
  `degradations/weather/fog.py` (`FogRun`); tests `tests/test_core.py`, `tests/degradations/test_fog.py`;
  [decision 0008](0008-fog-lidar-depth-scale.md); open decisions 2 and 3 in the roadmap

## Context

- **The common interface hands over only the pixels:** the framework's degradation interface is `apply(image, rng, params)`. A registered degradation
  (the path of `degfw run`, `degfw apply`, configuration files and the GUI) knows only the pixels of this one image.
- **The fog needs more than the pixels:**
  - **the image file:** its EXIF focal length (for Depth Pro), and its name (to find the LiDAR point cloud that belongs to it, [decision 0008](0008-fog-lidar-depth-scale.md));
  - **the run's other images:** images without sky use the batch-average atmospheric light;
  - **the LiDAR folder.**
- **So the fog had two codes:** in M1, to match the original `c2f.py`, the fog got its own command `degfw fog`, which reads the files itself and processes the whole batch;
  the LiDAR correction was later added only there. The registered fog fell behind: 0.8 for every image without sky, no EXIF focal length, no LiDAR.
  The same images gave different results on the two paths.
- **The registered path cannot be dropped:** configuration files (F10), combining degradations in order (F5) and adding a degradation with just one adapter (N1) all rely on it.

## Decision

- **Source information `Context`:** for every step of every image, the pipeline hands the degradation a `Context` besides the pixels:
  - `source`: the image's file; `None` for an image in memory (e.g. a preview in the GUI);
  - `batch`: all input files of this run;
  - `shared`: a dict for the whole run, one per step. What needs computing only once goes here; the next run starts empty;
  - `info`: the degradation's record for this image, written to the `.json` under this step's `info`.
- **The interface becomes `apply(image, rng, context, **params)`.** Parameters may not be called `image`, `rng` or `context`; checked at registration.
  Degradations that need no source information ignore `context`.
- **The fog has one code, `FogRun`:** one per run; EXIF focal length, Depth Pro, LiDAR correction, atmospheric light (from the sky, or the batch average, computed when first needed)
  and fog are only here. `degfw fog` and the registered fog both call it; the registered fog keeps it in `context.shared` for the whole run.
- **New parameter `lidar` for the registered fog:** new parameter type `Folder`, a folder path, empty = none. A given folder that does not exist is reported before any work.
- **`degfw fog` is unchanged:** usage, output files and `fog_run.json` are as before.
- **No average atmospheric light carried over between runs:** the Depth Pro engine is loaded once per process and shared by all runs. Before every fog, `FogRun` sets the engine's
  average atmospheric light to the current run's value, so runs one after another in the same process (e.g. in the GUI) never use what an earlier run left there.
- **Switching precision frees the old model's GPU memory:** before the engine changes precision (fp16 ↔ float32), the old model is deleted and PyTorch's GPU memory cache emptied.
  Otherwise the old model's memory stays in the cache, and the next float32 model (about 8 GB) spills even more into system memory: the full test suite went from under 4 to over 10 minutes.
  Switching fp16 on and off in the GUI would hit the same.
- **Clean-up along the way:** the example degradation `gaussian_noise` is removed (with the `sensor/` folder, empty without it), and so is the empty placeholder `lens/lens_dirt.py`.
  The framework's own tests use two test-only degradations in `tests/conftest.py` (`test_noise`, `test_context`), registered only in the tests.

## Options considered

- **Remove the registered fog, keep only `degfw fog`**: simplest, but the fog could then not be written in a configuration file or combined with other degradations (F5, F10, N1). Rejected.
- **Let the GUI call the code of `degfw fog` directly**: the GUI would need a separate path just for the fog, with an output format different from all other degradations and not reproducible with `degfw apply`;
  the next degradation that needs source information would need yet another one. Rejected.
- **Put the LiDAR folder into the source information instead of a fog parameter**: once dataset adapters (M6) read datasets, point clouds are part of the dataset, so the source information fits better.
  But for now only the fog uses it; as a parameter it goes straight into configuration files and `-p`, and into the metadata. A parameter for now; revisit in M6.
- **Cache batch results in global variables of the fog module**: runs would affect each other, e.g. the average atmospheric light of one run leaking into the next. Rejected in favour of one `shared` per run.
- **A "prepare" call on the whole batch before a step starts**: one more method on the base class; and the fog's average atmospheric light is only needed when an image without sky comes up,
  so computing it at first use saves time. Rejected.

## Consequences

- **The registered fog and `degfw fog` give the same results:** compared pixel by pixel on the two demo sets `Phase 2\Input\Demo` (4 images, 1 without sky) and
  `Phase 2\Input\a9_dataset_r02_s03_Demo` (5 images, with LiDAR). Covering fp16 at visibilities 50 and 100, float32 at 100, with and without LiDAR,
  through `degfw run fog` and `degfw apply`: all 32 images are pixel-identical to `degfw fog`, and every image records the same depth and atmospheric light source.
  Automatic test: `test_fog_degradation_same_as_fog_command` (once with, once without LiDAR).
- **`degfw fog` is unchanged:** 4 runs as a baseline before the change (27 images, including no sky, LiDAR and float32), repeated after it:
  all output images pixel-identical, `fog_run.json` identical. The regression test `test_fog_matches_reference` passes as well.
- **The registered fog's results change** (fog images made earlier with `degfw run fog` or a configuration file):
  - images without sky: 0.8 before, now the batch average, e.g. [0.718, 0.746, 0.807] for the image without sky in the Demo set;
  - photos with an EXIF focal length: now use it, as `degfw fog` does. TUMTraf images have no EXIF focal length and are not affected;
  - images with sky and without an EXIF focal length, and images in memory (`get("fog")(image)`, GUI preview): unchanged. The regression test's reference image is made this way.
- **The `.json` gains `info`:** the fog records the atmospheric light source, minimum and median depth, the depth source (with LiDAR: scale, points, error),
  and the average when the batch average was used. Same fields as each image's entry in `fog_run.json`.
- **The interface changes:** new degradations take one more argument, `context`, in `apply` (`_template.py` is updated). Configuration files that use `gaussian_noise` need changing;
  `configs/example.yaml` now uses the fog.
- **Still open:**
  - for images without sky the result depends on which other images are in the batch (open decision 3 in the roadmap); the two paths now just depend on the batch in the same way.
  - Redoing one such image alone (`run_file`) needs the same batch, `batch=`, to come out the same. `info` holds the average used; redoing from the record could come later.
  - The two commands may read different images: `degfw fog` only the .png .jpg .jpeg directly in each folder, `degfw run` / `apply` also subfolders and more formats. The batch average is over what each reads.
- **Noticed along the way:** one image of the a9 demo set has no sky with Depth Pro alone; after the LiDAR scale correction (about × 8) its distant pixels are beyond 1000 m, so it uses its own sky.
  A wrong depth scale also makes the "is there sky" test wrong; to consider when deciding open decision 3.
