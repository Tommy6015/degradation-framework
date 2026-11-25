"""The GUI (gradio): input and output folder, a degradation chosen by type (global /
local), its parameters, a preview of one image, then the whole folder. Only the layout
is here; what it does is in logic.py. The menu and the parameter controls come from
the registry: a newly registered degradation shows up under its scope without any
change here. All text shown is English.

Run with:  uv run --extra gui degfw gui
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import gradio as gr

from ..core import registry
from ..core.base import SCOPES
from ..core.io import to_uint8
from ..core.params import Bool, Choice, Float, Folder, Int, Param
from . import logic

# A native "choose folder" dialog. It runs in its own process: tkinter is not made for
# the worker threads gradio calls this from.
_PICK_FOLDER = r"""
import sys, tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
path = filedialog.askdirectory(parent=root, initialdir=sys.argv[1] or None, title=sys.argv[2], mustexist=False)
root.destroy()
print(path or "")
"""


def pick_folder(current: str, title: str) -> str:
    """The folder chosen in the dialog, or `current` if it was cancelled."""
    current = (current or "").strip()
    start = current if current and Path(current).is_dir() else ""
    done = subprocess.run([sys.executable, "-c", _PICK_FOLDER, start, title], capture_output=True,
                          encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    chosen = done.stdout.strip()
    return str(Path(chosen)) if chosen else current


def _control(spec: Param, key: str):
    """The input control for one parameter (plus a Browse button for a folder)."""
    label, info = spec.label or key, spec.help or None
    if isinstance(spec, Int):
        return gr.Number(value=spec.default, label=f"{label}  [{spec.min}–{spec.max}]", info=info,
                         precision=0, minimum=spec.min, maximum=spec.max, step=spec.step), None
    if isinstance(spec, Float):
        return gr.Slider(spec.min, spec.max, value=spec.default, step=spec.step, label=label, info=info), None
    if isinstance(spec, Choice):
        return gr.Dropdown(list(spec.choices), value=spec.default, label=label, info=info), None
    if isinstance(spec, Bool):
        return gr.Checkbox(value=spec.default, label=label, info=info), None
    if isinstance(spec, Folder):
        with gr.Row(equal_height=True):
            box = gr.Textbox(value=spec.default, label=label, info=info, scale=6)
            browse = gr.Button("Browse…", scale=1, min_width=100)
        return box, browse
    raise TypeError(f"No GUI control for {type(spec).__name__}")


def build_app() -> gr.Blocks:
    groups = logic.menu()
    first_scope = next((s for s in SCOPES if groups[s]), SCOPES[0])
    first = groups[first_scope][0][1] if groups[first_scope] else None
    # Every degradation's controls, in one flat list for the callbacks:
    # layout[i] = (name, [param keys]) in the order of `controls`
    layout: list[tuple[str, list[str]]] = []
    controls: list[gr.components.Component] = []
    panels: dict[str, gr.Group] = {}

    with gr.Blocks(title="Degradation Framework") as app:
        gr.Markdown("# Degradation Framework\n"
                    "Degrade camera images: choose the input and output folders and a degradation, "
                    "check one image in the preview, then generate the whole folder.")

        # ---- 1, 2: folders -------------------------------------------------------
        with gr.Row(equal_height=True):
            in_dir = gr.Textbox(label="1 · Input folder", placeholder=r"D:\data\images", scale=6)
            in_browse = gr.Button("Browse…", scale=1, min_width=100)
        in_msg = gr.Markdown()
        with gr.Row(equal_height=True):
            out_dir = gr.Textbox(label="2 · Output folder", placeholder=r"D:\data\images_fog", scale=6)
            out_browse = gr.Button("Browse…", scale=1, min_width=100)
        out_msg = gr.Markdown()

        # ---- 3, 4, 5: degradation and its parameters ----------------------------------
        scope = gr.Radio([(logic.SCOPE_LABELS[s], s) for s in SCOPES], value=first_scope,
                         label="3 · Type of degradation")
        degradation = gr.Dropdown(groups[first_scope], value=first, label="4 · Degradation")
        deg_msg = gr.Markdown(logic.check_degradation(first).markdown() if first else "")
        gr.Markdown("**5 · Parameters**")
        for s in SCOPES:
            for _, name in groups[s]:
                deg = registry.get(name)
                with gr.Group(visible=name == first) as panels[name]:
                    keys = []
                    for key, spec in deg.params.items():
                        box, browse = _control(spec, key)
                        controls.append(box)
                        keys.append(key)
                        if browse is not None:
                            browse.click(lambda v, t=spec.label or key: pick_folder(v, t), box, box)
                    layout.append((name, keys))

        # ---- 6: preview -----------------------------------------------------------
        with gr.Row(equal_height=True):
            pick = gr.Dropdown([], label="6 · Preview: image", scale=6)
            preview_btn = gr.Button("Preview", scale=1, min_width=100)
        with gr.Row():
            original = gr.Image(label="Original", type="numpy", interactive=False)
            result = gr.Image(label="Result", type="numpy", interactive=False, format="png")
        preview_msg = gr.Markdown()

        # ---- 7: generate ------------------------------------------------------------
        generate_btn = gr.Button("7 · Generate", variant="primary")
        summary = gr.Markdown()
        table = gr.Dataframe(headers=["Input", "Output", "Notes"], interactive=False, visible=False, wrap=True)

        # ---- callbacks ---------------------------------------------------------------
        def params_of(name, values):
            it = iter(values)
            for n, keys in layout:
                own = {k: next(it) for k in keys}
                if n == name:
                    return logic.resolve(name, own)
            raise ValueError("Choose a degradation.")

        def on_input(folder, output):
            images, check = logic.scan_input(folder)
            names = logic.relative_names(images, folder) if images else []
            return (check.markdown(), gr.update(choices=names, value=names[0] if names else None),
                    logic.check_output(output, folder).markdown() if (output or "").strip() else "")

        def on_output(output, folder):
            return logic.check_output(output, folder).markdown()

        def on_scope(chosen):
            options = groups[chosen]
            name = options[0][1] if options else None
            message = (logic.check_degradation(name).markdown() if name
                       else f"No {chosen} degradation is available yet.")
            return (gr.update(choices=options, value=name), message,
                    *[gr.update(visible=n == name) for n in panels])

        def on_degradation(name):
            return (logic.check_degradation(name).markdown() if name else "",
                    *[gr.update(visible=n == name) for n in panels])

        def on_preview(name, folder, relative, *values):
            if not logic.check_degradation(name).ok:
                raise gr.Error(logic.check_degradation(name).message)
            if not relative:
                raise gr.Error("Choose an input folder with images first.")
            try:
                shown = logic.preview(name, params_of(name, values), folder, relative)
            except (ValueError, FileNotFoundError) as e:
                raise gr.Error(str(e)) from None
            return (to_uint8(shown.original), to_uint8(shown.result),
                    f"{relative}: {shown.notes} ({shown.seconds:.1f} s)")

        def on_generate(name, folder, output, *values, progress=gr.Progress()):
            if not logic.check_degradation(name).ok:
                raise gr.Error(logic.check_degradation(name).message)
            try:
                params = params_of(name, values)
                progress(0, desc="Starting (the model loads at the first image)…")
                done = logic.generate(name, params, folder, output,
                                      progress=lambda i, n, f: progress(i / n, desc=f"{i} / {n}: {f.name}"))
            except (ValueError, FileNotFoundError) as e:
                raise gr.Error(str(e)) from None
            return done.summary(), gr.update(value=done.rows, visible=True)

        for event in (in_dir.submit, in_dir.blur):
            event(on_input, [in_dir, out_dir], [in_msg, pick, out_msg])
        in_browse.click(lambda v: pick_folder(v, "Input folder"), in_dir, in_dir).then(
            on_input, [in_dir, out_dir], [in_msg, pick, out_msg])
        for event in (out_dir.submit, out_dir.blur):
            event(on_output, [out_dir, in_dir], out_msg)
        out_browse.click(lambda v: pick_folder(v, "Output folder"), out_dir, out_dir).then(
            on_output, [out_dir, in_dir], out_msg)
        scope.change(on_scope, scope, [degradation, deg_msg, *panels.values()])
        degradation.change(on_degradation, degradation, [deg_msg, *panels.values()])
        preview_btn.click(on_preview, [degradation, in_dir, pick, *controls], [original, result, preview_msg])
        generate_btn.click(on_generate, [degradation, in_dir, out_dir, *controls], [summary, table])

    return app


# Gradio translates its own texts (footer, list hints, progress, error dialogs) into the
# browser's language, e.g. Chinese, and has no setting to fix it. The GUI is English
# only, so the page says the browser is English before gradio's code runs. launch()'s
# `head` comes too late (gradio adds it after choosing the language), so the script goes
# into the page itself, by a middleware.
ENGLISH_ONLY = (b'<script>Object.defineProperty(navigator, "language", {get: () => "en"});'
                b'Object.defineProperty(navigator, "languages", {get: () => ["en"]});</script>')


class EnglishOnly:
    """ASGI middleware: puts ENGLISH_ONLY at the start of the page's <head> (GET /)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != "/":
            return await self.app(scope, receive, send)
        start, chunks = {}, []

        async def edit_page(message):
            if message["type"] == "http.response.start":
                start.update(message)
                return
            chunks.append(message.get("body", b""))
            if message.get("more_body"):
                return
            body = b"".join(chunks)
            headers = [(k, v) for k, v in start.get("headers", []) if k.lower() != b"content-length"]
            if b"<head>" in body:  # an HTML page (not compressed)
                body = body.replace(b"<head>", b"<head>" + ENGLISH_ONLY, 1)
            await send({**start, "headers": [*headers, (b"content-length", str(len(body)).encode())]})
            await send({"type": "http.response.body", "body": body})

        await self.app(scope, receive, edit_page)


def launch(server_name: str = "127.0.0.1", server_port: int = 7860, inbrowser: bool = True) -> None:
    """Serve the GUI until Ctrl+C (gradio's mount_gradio_app, behind EnglishOnly)."""
    import threading
    import webbrowser

    import uvicorn
    from fastapi import FastAPI

    server = FastAPI()
    server.add_middleware(EnglishOnly)
    server = gr.mount_gradio_app(server, build_app(), path="/")
    url = f"http://{'127.0.0.1' if server_name in ('', '0.0.0.0') else server_name}:{server_port}/"
    print(f"Degradation Framework GUI: {url}   (stop with Ctrl+C)")
    if inbrowser:
        threading.Timer(2.0, webbrowser.open, [url]).start()
    uvicorn.run(server, host=server_name, port=server_port, log_level="warning")
