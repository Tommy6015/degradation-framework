# 0003: In folder runs, each image's seed is derived from (seed, relative path)

- Status: accepted (supersedes the earlier "seed + index")
- Date: 2026-11-19
- Related: `core/pipeline.py` (`image_seed`, `Pipeline.run_folder`); commit `21b2ef7`

## Context

In folder runs, image i (in sorted order) used to get the seed `configured seed + i`. Two problems:

- one image more or less in the folder changed the seeds, and so the results, of all images sorted after it;
- the two dataset versions generated with seeds 0 and 1 were only shifted by one: image k+1 of the seed-0 version used the same random numbers as image k of the seed-1 version.

## Decision

`image_seed(seed, rel_path)`: the image's path relative to the input folder (`/` separators, Unicode NFC normalised) is hashed with SHA-256 and passed together with the configured seed to
`numpy.random.SeedSequence`, which gives a 63-bit seed. As before, the seed actually used is recorded in each image's `.json`,
and `run_file(..., seed=that value)` redoes that single image.

## Options considered

- **File name instead of relative path**: images with the same name in different subfolders would get the same seed.
- **Hash of the image content**: one changed pixel changes the seed; and the image has to be read before its seed is known.
- **Keep seed + index**: the two problems above.

## Consequences

- Each image's result depends only on its own path and the configured seed.
- Processing a folder again with the same configuration gives different results than before 2026-11-19; earlier images can still be reproduced from the seed in their `.json`.
- Renaming or moving an image changes its seed.
