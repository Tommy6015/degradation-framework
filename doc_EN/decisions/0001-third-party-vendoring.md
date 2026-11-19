# 0001: Copy only the needed files of third-party code into `third_party/` and maintain it only there

- Status: accepted
- Date: 2026-11-12 (how code is vendored); revised 2026-11-19 (no more forks)
- Related: `third_party/README.md`; unmodified copies in commits `749d255` (camera_contamination_simulation) and `d9ba087` (Clear2Fog); revision commit `929270d`

## Context

The degradation effects come from research code (Clear2Fog, camera_contamination_simulation, …). These repositories:

- are large, with training code, experiments and paper figures, while generating degradations needs only a few of their files;
- often cannot be imported as they are (they import modules that do not exist, or pull in the LiDAR part and PyQt5);
- need small changes to be usable (e.g. only 960×960 supported, a C extension that does not install on Windows);
- are hardly updated by their authors any more (camera_contamination_simulation has two commits in total).

## Decision

- Copy only the needed files into `third_party/<repo>/`, keeping the LICENSE. The first, unmodified copy is a **separate commit**, the baseline for later comparison with the original.
- Third-party code is changed directly in `third_party/` and committed separately, with a commit message starting with `third_party/<repo>:`.
  The differences to the original are shown by `git diff <commit of the unmodified copy> -- third_party/<repo>`; no separate hand-written record.
- No forks are maintained. `third_party/README.md` records the original author's repository, the vendored version and the commit of the unmodified copy.

## Options considered

- **git submodule / subtree**: brings in the whole repository (training, experiments, figures); a submodule also needs `--recursive` when cloning and makes everyday work more involved.
- **pip-install the original repository**: most of this research code is not an installable package, and it needs changes.
- **Use the existing local clones directly** (without copying): the project would depend on folders outside the repository, would not run on another computer or for anyone else, and would not record which version is used.
- **Change the code in a fork, push, and copy it back** (tried once on 2026-11-19): every change has to be synchronised between two repositories and the registered commit hash updated.
  Not worth it for a single developer with code used only in this project. The changes were pushed to the fork's
  `any-image-size-and-droplet-fixes` branch, which is kept as an archive.

## Consequences

- degradation-framework is self-contained: a clone has all the code and needs no access to a fork or to the original repositories.
- Updates by the original authors have to be merged by hand: before copying a new version in, check one's own changes against the unmodified copy.
- The local fork clones and the forks on GitHub are no longer needed; they can be kept for reference or deleted.
