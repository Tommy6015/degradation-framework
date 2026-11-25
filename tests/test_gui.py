"""The gradio layout (gui/app.py); skipped when the GUI is not installed
(uv sync --extra gui). What it does is tested in test_gui_logic.py."""

import re

import pytest

gr = pytest.importorskip("gradio")  # GUI is optional
if not hasattr(gr, "Blocks"):
    # gradio writes hash_seed.txt into its package dir at runtime; after
    # uninstalling, that leftover dir still imports as an empty namespace
    pytest.skip("gradio not installed (only a leftover package dir)", allow_module_level=True)

from degradation_fw.gui.app import build_app  # noqa: E402

CJK = re.compile(r"[　-〿㐀-鿿＀-￯]")


def texts(app):
    """Every text the user can see: labels, info lines, placeholders, Markdown, buttons, choices."""
    for block in app.blocks.values():
        for attr in ("label", "info", "placeholder", "value"):
            value = getattr(block, attr, None)
            if isinstance(value, str):
                yield value
        for choice in getattr(block, "choices", None) or []:
            yield str(choice)


def test_gui_builds():
    build_app()


def test_gui_text_is_english_only():
    found = [t for t in texts(build_app()) if CJK.search(t)]
    assert not found, f"non-English text in the GUI: {found}"


def test_gui_lists_every_degradation_under_its_scope():
    labels = list(texts(build_app()))
    for expected in ("1 · Input folder", "2 · Output folder", "3 · Type of degradation", "4 · Degradation",
                     "6 · Preview: image", "7 · Generate", "Visibility (m)  [5–2000]", "LiDAR folder (optional)"):
        assert expected in labels, expected


def test_page_tells_gradio_the_browser_is_english():
    """The script goes to the very start of the page's <head>, before gradio's code;
    the length header is fixed; other paths are passed through untouched."""
    import asyncio

    from degradation_fw.gui.app import ENGLISH_ONLY, EnglishOnly

    page = b"<!doctype html><html><head><title>x</title></head></html>"

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"text/html"), (b"content-length", str(len(page)).encode())]})
        await send({"type": "http.response.body", "body": page})

    for path, edited in (("/", True), ("/config", False)):
        sent = []

        async def send(message, sent=sent):
            sent.append(message)

        asyncio.run(EnglishOnly(app)({"type": "http", "path": path}, None, send))
        body = sent[-1]["body"]
        assert body == (page.replace(b"<head>", b"<head>" + ENGLISH_ONLY) if edited else page)
        assert dict(sent[0]["headers"])[b"content-length"] == str(len(body)).encode()
