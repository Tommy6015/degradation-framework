# Decision records

One file per decision: `NNNN-short-english-name.md`, numbered in increasing order, numbers never reused. Written from [template.md](template.md).

**When to write one:**

- there are several workable approaches and one of them was chosen;
- it is hard to change later, or changing it would affect existing results, data or file formats;
- in a few months someone (or you yourself) will ask "why was it done this way".

For example: how the degradation interface is extended, format and naming of output files, reproducibility rules, how third-party code is handled, choice of dependencies.
Everyday bug fixes and small refactorings need no record; the commit history is enough.

**Status:** proposed (still under discussion) → accepted; when a decision is later reversed, its file is not deleted: its status becomes "superseded by NNNN" or "deprecated", and a new record is written.

## Index

| No. | Decision | Status | Date |
|---|---|---|---|
| [0001](0001-third-party-vendoring.md) | Third-party code: copy only the needed files into `third_party/` and maintain it only there | Accepted | 2026-11-12, revised 2026-11-19 |
| [0002](0002-third-party-integration.md) | Conventions for loading third-party code, its dependencies and model weights | Accepted | 2026-11-19 |
| [0003](0003-folder-seeds.md) | In folder runs, each image's seed is derived from (seed, relative path) | Accepted | 2026-11-19 |
| [0004](0004-exif-orientation.md) | Images are turned upright by EXIF orientation when read; RGB and depth of the fog come from the same pixels | Accepted | 2026-11-19 |
| [0005](0005-output-name-collisions.md) | Taken output names get `_2`, `_3` instead of overwriting | Accepted | 2026-11-19 |
| [0008](0008-fog-lidar-depth-scale.md) | Fog depth: with LiDAR, the point cloud corrects the scale of Depth Pro (`degfw fog --lidar`) | Accepted | 2026-11-24 |
| [0009](0009-droplet-exact-placement.md) | Water drops are placed exactly where we specify (centroid aligned); the network only provides the shape; several pieces move together | Accepted | 2026-11-24 |

0006 (choice of degradations) and 0007 (interface extension) are reserved in the [roadmap](../roadmap.md)'s open decisions and not written yet.
