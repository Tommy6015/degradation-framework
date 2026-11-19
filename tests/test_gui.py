import pytest


def test_gui_builds():
    gr = pytest.importorskip("gradio")  # GUI is optional
    if not hasattr(gr, "Blocks"):
        # gradio writes hash_seed.txt into its package dir at runtime; after
        # uninstalling, that leftover dir still imports as an empty namespace
        pytest.skip("gradio not installed (only a leftover package dir)")
    from degradation_fw.gui.app import build_app
    build_app()
