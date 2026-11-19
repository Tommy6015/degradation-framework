# 0002: Conventions for loading third-party code, its dependencies and model weights

- Status: accepted
- Date: 2026-11-19
- Related: `core/paths.py`, `core/weights.py`, `core/base.py`, `third_party/weights.yaml`, `pyproject.toml`, `degradations/_template.py`;
  commits `8b22d21`, `b71c292`

## Context

After integrating two third-party repositories, several problems showed up:

- The two repositories were integrated in two different ways: a fake package called `src` in `sys.modules` plus a temporary `chdir`, and a folder added to `sys.path`.
  Module names such as `src`, `noise` or `utils` are shared by the whole process, so with more repositories they would collide.
- All dependencies were in one list; it was not visible which package belongs to which repository.
- Some model weights were in git, others had to be downloaded by hand and placed deep inside third-party folders, with no common record.
- If any adapter failed while being imported, `degfw list`, the GUI and all tests failed with it.

## Decision

- **Loading**: third-party code is loaded only through `core/paths.py`.
  - `import_third_party_package(repo, package)`: for packages whose modules import each other relatively; loaded under the private name `_tp_<repo>`, without running the package's own `__init__.py`.
  - `use_third_party(repo, modules)`: for code whose modules import each other by top-level name; the module names it brings must be declared, and an already taken name is an error.
  - `working_dir(path)`: for code that opens files relative to the current directory; runs under a lock.
- **Lazy loading**: adapter modules load no third-party code or heavy dependencies at the top; they load them when first needed.
- **Declared requirements**: `requires_modules`, `requires_weights`. A degradation with something missing is only marked unavailable (`degfw list` gives the reason), and its tests are skipped.
- **Dependencies**: one dependency group per third-party repository in `pyproject.toml`, all installed by default (`default-groups = "all"`).
- **Weights**: each file is registered in `third_party/weights.yaml` with path, size, SHA-256 and download URL; `degfw weights` shows, verifies and downloads them.

## Options considered

- **Each adapter handles it itself**: the previous state, which had already produced two different approaches.
- **Group with optional-dependencies (extras)**: extras go into the package metadata and are meant for installable libraries; for a workspace, dependency groups fit better and can be installed by default.
- **Weight download as a script in `scripts/`**: downloading weights is a function of the framework itself, so it became the `degfw weights` command.

## Consequences

- The steps for integrating a new repository are fixed and written down in `degradations/_template.py`.
- With only the core dependencies installed (no torch etc.), the framework and the quick tests still run (verified: 31 tests passed, fog marked unavailable).
- Results did not change: fog in float32 and fp16, through both entry points, gives pixel-identical output to before.
