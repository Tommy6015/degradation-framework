"""Project paths, and how adapters load the vendored code in third_party/.

Load third-party code only through these functions, and only inside an adapter's
functions (lazily), never at the top of an adapter module: see
degradations/_template.py.

  import_third_party_package(repo, package)
      For a package whose modules import each other relatively (``from .x import y``),
      e.g. Clear2Fog's src/fog_pipeline. It is imported under a private name,
      ``_tp_<repo>``, so it takes no generic top-level name such as ``src``; its own
      __init__.py is skipped unless run_init=True.

  use_third_party(repo, modules)
      For code whose modules import each other by top-level name
      (``from noise import pnoise2``), e.g. camera_contamination_simulation. Its
      folder goes on sys.path; ``modules`` lists the top-level names it brings. If one
      of them is already taken (imported from elsewhere, or provided by an installed
      package or another third_party folder), that is an error, instead of silently
      using the wrong module.

  working_dir(path)
      For code that opens files relative to the current directory (e.g. Depth Pro's
      checkpoint path). chdir affects the whole process, so such blocks are serialised.
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import os
import re
import sys
import threading
import types
from collections.abc import Generator, Iterable
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
THIRD_PARTY_DIR = PROJECT_ROOT / "third_party"

_CWD_LOCK = threading.RLock()


def third_party_dir(repo: str) -> Path:
    """third_party/<repo>, which must exist."""
    folder = THIRD_PARTY_DIR / repo
    if not folder.is_dir():
        raise FileNotFoundError(f"third_party/{repo} not found at {folder}")
    return folder


def _inside(path: str | os.PathLike | None, folder: Path) -> bool:
    if not path:
        return False
    try:
        Path(path).resolve().relative_to(folder.resolve())
    except ValueError:
        return False
    return True


def import_third_party_package(repo: str, package: str = ".", *, alias: str | None = None,
                               run_init: bool = False) -> types.ModuleType:
    """Import the package third_party/<repo>/<package> under the name ``_tp_<repo>``
    (or ``alias``) and return it. Its modules are then imported with
    ``importlib.import_module(pkg.__name__ + ".sub.module")``; their relative imports
    work as in the original repository. Calling it again returns the same package.

    run_init=False (default): the package's own __init__.py is not run, so modules can
    be used without what it imports (e.g. Clear2Fog's LiDAR part); __init__.py files of
    its sub-packages still run as usual.
    """
    folder = (third_party_dir(repo) / package).resolve()
    if not folder.is_dir():
        raise FileNotFoundError(f"third_party/{repo}/{package} not found at {folder}")
    name = alias or "_tp_" + re.sub(r"\W+", "_", repo).strip("_").lower()
    existing = sys.modules.get(name)
    if existing is not None:
        if [str(p) for p in getattr(existing, "__path__", [])] == [str(folder)]:
            return existing
        raise ImportError(f"Package name {name!r} is already used for "
                          f"{list(getattr(existing, '__path__', []))}; load third_party/{repo}/{package} "
                          f"with another alias=")
    if run_init:
        spec = importlib.util.spec_from_file_location(name, folder / "__init__.py",
                                                      submodule_search_locations=[str(folder)])
        if spec is None or spec.loader is None:
            raise ImportError(f"third_party/{repo}/{package} has no __init__.py")
    else:  # only a __path__: the package's __init__.py does not run
        spec = importlib.machinery.ModuleSpec(name, None, is_package=True)
        spec.submodule_search_locations = [str(folder)]
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    if run_init:
        try:
            spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[name]
            raise
    return module


def use_third_party(repo: str, modules: Iterable[str]) -> Path:
    """Put third_party/<repo> on sys.path for code that imports its own modules by
    top-level name, after checking that none of these names is taken. Returns the folder.

    ``modules``: every top-level module of the folder that will be imported, also
    indirectly, e.g. ``["contamination_simulation", "noise"]`` when
    contamination_simulation.py does ``from noise import pnoise2``.
    """
    folder = third_party_dir(repo).resolve()
    names = list(modules)
    if not names:
        raise ValueError("use_third_party: list the top-level modules this code brings")
    on_path = str(folder) in sys.path
    for name in names:
        if not ((folder / f"{name}.py").is_file() or (folder / name / "__init__.py").is_file()):
            raise FileNotFoundError(f"third_party/{repo} has no top-level module {name!r}")
        loaded = sys.modules.get(name)
        if loaded is not None:
            if _inside(getattr(loaded, "__file__", None), folder):
                continue
            raise ImportError(f"third_party/{repo} brings a module {name!r}, but a different {name!r} "
                              f"is already imported ({getattr(loaded, '__file__', None) or loaded!r})")
        if not on_path:
            spec = importlib.util.find_spec(name)
            if spec is not None and not _inside(spec.origin, folder):
                raise ImportError(f"third_party/{repo} brings a module {name!r}, which would hide "
                                  f"{spec.origin or 'an existing package of that name'}")
    if not on_path:
        sys.path.insert(0, str(folder))
    return folder


@contextlib.contextmanager
def working_dir(path: str | os.PathLike) -> Generator[Path, None, None]:
    """Run a block with ``path`` as the current directory, for third-party code that
    opens files relative to it. chdir affects the whole process, so these blocks are
    serialised by a lock (matters when the GUI handles requests in threads). Where the
    code accepts absolute paths, pass those instead."""
    with _CWD_LOCK:
        old = os.getcwd()
        os.chdir(path)
        try:
            yield Path(path)
        finally:
            os.chdir(old)
