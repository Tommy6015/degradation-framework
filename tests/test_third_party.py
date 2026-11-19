"""Loading third-party code (core/paths.py) and the weights manifest (core/weights.py),
with small fake repositories in a temporary third_party folder."""

import hashlib
import importlib
import os
import sys
from dataclasses import replace

import pytest

from degradation_fw.core import paths, weights

FAKE_PREFIXES = ("_tp_fake", "_tp_init_repo", "tpfake_")


@pytest.fixture
def fake_third_party(tmp_path, monkeypatch):
    """An empty third_party folder for the loaders; sys.path and the fake modules
    are removed again afterwards."""
    root = tmp_path / "third_party"
    root.mkdir()
    monkeypatch.setattr(paths, "THIRD_PARTY_DIR", root)
    monkeypatch.setattr(sys, "path", list(sys.path))
    yield root
    for name in [n for n in sys.modules if n.startswith(FAKE_PREFIXES)]:
        del sys.modules[name]


def write(path, text=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---- import_third_party_package ---------------------------------------------------
def test_package_gets_a_private_name_and_skips_its_init(fake_third_party):
    pkg_dir = fake_third_party / "Fake-Repo" / "src" / "pkg"
    write(pkg_dir / "__init__.py", "raise RuntimeError('the package __init__ must not run')\n")
    write(pkg_dir / "sub" / "__init__.py")
    write(pkg_dir / "sub" / "a.py", "from .b import VALUE\n")  # relative imports work
    write(pkg_dir / "sub" / "b.py", "VALUE = 42\n")
    pkg = paths.import_third_party_package("Fake-Repo", "src/pkg")
    assert pkg.__name__ == "_tp_fake_repo"
    assert importlib.import_module("_tp_fake_repo.sub.a").VALUE == 42
    assert paths.import_third_party_package("Fake-Repo", "src/pkg") is pkg  # again: same package


def test_package_name_conflict_is_an_error(fake_third_party):
    write(fake_third_party / "Fake-Repo" / "pkg" / "m.py")
    write(fake_third_party / "fake_repo" / "pkg" / "m.py")  # would get the same name
    paths.import_third_party_package("Fake-Repo", "pkg")
    with pytest.raises(ImportError, match="alias"):
        paths.import_third_party_package("fake_repo", "pkg")
    assert paths.import_third_party_package("fake_repo", "pkg", alias="_tp_fake_2").__name__ == "_tp_fake_2"


def test_package_init_runs_if_asked(fake_third_party):
    write(fake_third_party / "init-repo" / "pkg" / "__init__.py", "FLAG = 'ran'\n")
    assert paths.import_third_party_package("init-repo", "pkg", run_init=True).FLAG == "ran"


# ---- use_third_party ----------------------------------------------------------------
def test_flat_modules_are_put_on_sys_path(fake_third_party):
    write(fake_third_party / "flat" / "tpfake_main.py", "from tpfake_helper import VALUE\n")
    write(fake_third_party / "flat" / "tpfake_helper.py", "VALUE = 7\n")
    folder = paths.use_third_party("flat", ["tpfake_main", "tpfake_helper"])
    assert str(folder) in sys.path
    assert importlib.import_module("tpfake_main").VALUE == 7
    paths.use_third_party("flat", ["tpfake_main"])  # again: fine


@pytest.mark.parametrize("name", ["json", "colorsys"])  # already imported / installed but not imported
def test_taken_module_name_is_an_error(fake_third_party, name):
    write(fake_third_party / "clash" / f"{name}.py")
    with pytest.raises(ImportError, match=name):
        paths.use_third_party("clash", [name])
    assert str((fake_third_party / "clash").resolve()) not in sys.path


def test_declared_module_must_exist(fake_third_party):
    write(fake_third_party / "flat" / "tpfake_main.py")
    with pytest.raises(FileNotFoundError):
        paths.use_third_party("flat", ["tpfake_main", "tpfake_not_there"])


def test_working_dir_restores_cwd(tmp_path):
    before = os.getcwd()
    with pytest.raises(RuntimeError):
        with paths.working_dir(tmp_path):
            assert os.path.samefile(os.getcwd(), tmp_path)
            raise RuntimeError
    assert os.getcwd() == before


# ---- weights.yaml -------------------------------------------------------------------
def test_manifest_entries_are_complete():
    entries = weights.manifest()
    assert entries
    for w in entries.values():
        assert len(w.sha256) == 64 and int(w.sha256, 16) >= 0, w.id
        assert w.size > 0, w.id
        assert w.path.resolve().is_relative_to(weights.THIRD_PARTY_DIR.resolve()), w.id


def test_weights_in_git_are_present():
    """Files without a url ship with the repository, so they must be here."""
    for w in weights.manifest().values():
        if not w.url:
            assert w.present(), f"{w.id}: {w.path}"


def fake_weight(tmp_path, data: bytes, **changes) -> weights.Weight:
    """A Weight whose url is a local file:// URL (no network needed)."""
    src = tmp_path / "source.bin"
    src.write_bytes(data)
    w = weights.Weight(id="fake", path=tmp_path / "models" / "fake.pt", size=len(data),
                       sha256=hashlib.sha256(data).hexdigest(), url=src.as_uri())
    return replace(w, **changes)


def test_download_checks_size_and_hash(tmp_path):
    data = b"weights" * 1000
    w = fake_weight(tmp_path, data)
    assert weights.status(w) == "missing"
    weights.download(w)
    assert w.path.read_bytes() == data
    assert weights.status(w, verify=True) == "ok"


def test_wrong_download_leaves_nothing_behind(tmp_path):
    w = fake_weight(tmp_path, b"something else", sha256="0" * 64)
    with pytest.raises(ValueError, match="does not match"):
        weights.download(w)
    assert not w.path.exists()
    assert not list(w.path.parent.glob("*.part"))


def test_missing_weights_says_how_to_get_them(tmp_path, monkeypatch):
    w = fake_weight(tmp_path, b"x")
    monkeypatch.setitem(weights.manifest(), "fake", w)
    assert "degfw weights --download" in weights.missing_weights(["fake"])
    w.path.parent.mkdir(parents=True)
    w.path.write_bytes(b"x")
    assert weights.missing_weights(["fake"]) is None
