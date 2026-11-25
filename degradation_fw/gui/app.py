"""Gradio GUI. Controls are generated from each degradation's ``params``.

Run with:  uv run degfw gui
"""

from __future__ import annotations

from pathlib import Path

import gradio as gr
import numpy as np

from ..core import registry
from ..core.io import to_float, to_uint8
from ..core.params import Bool, Choice, Float, Folder, Int, Param
from ..core.pipeline import Pipeline, Step


def _make_control(key: str, spec: Param):
    label = spec.label or key
    if isinstance(spec, Float):
        return gr.Slider(spec.min, spec.max, value=spec.default, step=spec.step,
                         label=label, info=spec.help or None)
    if isinstance(spec, Int):
        return gr.Slider(spec.min, spec.max, value=spec.default, step=spec.step,
                         label=label, info=spec.help or None)
    if isinstance(spec, Choice):
        return gr.Dropdown(list(spec.choices), value=spec.default, label=label,
                           info=spec.help or None)
    if isinstance(spec, Bool):
        return gr.Checkbox(value=spec.default, label=label, info=spec.help or None)
    if isinstance(spec, Folder):
        return gr.Textbox(value=spec.default, label=label, info=spec.help or None)
    raise TypeError(f"No GUI control for {type(spec).__name__}")


def build_app() -> gr.Blocks:
    names = registry.available()
    # layout[i] = (degradation name, [param keys]); the flat list `controls`
    # holds, per degradation: enabled checkbox, then one control per param.
    layout: list[tuple[str, list[str]]] = []
    controls: list[gr.components.Component] = []

    def pipeline_from_values(values) -> Pipeline:
        it = iter(values)
        steps = []
        for name, keys in layout:
            enabled = next(it)
            params = {k: next(it) for k in keys}
            if enabled:
                steps.append(Step(name, params))
        return Pipeline(steps=steps)

    def values_from_pipeline(p: Pipeline) -> list:
        by_name = {s.name: s.params for s in p.steps}
        out = []
        for name, keys in layout:
            deg = registry.get(name)
            out.append(name in by_name)
            resolved = deg.resolve_params(by_name.get(name, {}))
            out.extend(resolved[k] for k in keys)
        return out

    with gr.Blocks(title="Degradation Framework") as app:
        gr.Markdown("# 图像退化生成 Degradation Framework\n"
                    "勾选要使用的退化并调整参数（按从上到下的顺序依次叠加），然后处理单张图片或整个文件夹。")
        with gr.Row():
            # ---------------- left: degradation controls ----------------
            with gr.Column(scale=1):
                for name in names:
                    deg = registry.get(name)
                    with gr.Accordion(deg.label or name, open=False):
                        if deg.description:
                            gr.Markdown(deg.description)
                        controls.append(gr.Checkbox(value=False, label="启用"))
                        keys = []
                        for key, spec in deg.params.items():
                            controls.append(_make_control(key, spec))
                            keys.append(key)
                        layout.append((name, keys))

                with gr.Row():
                    seed = gr.Number(value=0, precision=0, label="随机种子 seed")
                    random_seed = gr.Checkbox(value=False, label="每次随机")

                with gr.Accordion("配置文件 (保存 / 读取参数预设)", open=False):
                    cfg_path = gr.Textbox(value="configs/my_preset.yaml", label="路径")
                    with gr.Row():
                        save_btn = gr.Button("保存配置")
                        load_btn = gr.Button("读取配置")
                    cfg_msg = gr.Markdown()

            # ---------------- right: processing ----------------
            with gr.Column(scale=2):
                with gr.Tab("单张图片"):
                    with gr.Row():
                        img_in = gr.Image(type="numpy", image_mode="RGB", label="输入")
                        img_out = gr.Image(type="numpy", label="输出", format="png")
                    run_btn = gr.Button("处理", variant="primary")
                    meta_out = gr.JSON(label="本次使用的参数（可复现）")

                with gr.Tab("批量处理文件夹"):
                    in_dir = gr.Textbox(label="输入文件夹", placeholder=r"D:\data\clean")
                    out_dir = gr.Textbox(label="输出文件夹", placeholder=r"D:\data\foggy")
                    batch_btn = gr.Button("开始批量处理", variant="primary")
                    batch_log = gr.Markdown()

        # ---------------- callbacks ----------------
        def get_seed(seed_val, rand):
            return None if rand else int(seed_val or 0)

        def run_single(image, seed_val, rand, *values):
            if image is None:
                raise gr.Error("请先上传一张图片")
            p = pipeline_from_values(values)
            if not p.steps:
                raise gr.Error("请至少启用一种退化")
            out, meta = p.run(to_float(image), seed=get_seed(seed_val, rand))
            return to_uint8(out), meta

        def run_batch(src, dst, seed_val, rand, *values, progress=gr.Progress()):
            if not src or not Path(src).is_dir():
                raise gr.Error(f"输入文件夹不存在: {src}")
            if not dst:
                raise gr.Error("请填写输出文件夹")
            p = pipeline_from_values(values)
            if not p.steps:
                raise gr.Error("请至少启用一种退化")
            p.seed = get_seed(seed_val, rand)
            Path(dst).mkdir(parents=True, exist_ok=True)
            p.save(Path(dst) / "pipeline.yaml")  # record the config next to the results
            outs = p.run_folder(src, dst, progress=lambda i, n, f: progress(i / n, desc=f.name))
            return f"完成：共处理 {len(outs)} 张，输出到 `{dst}`（每张图旁边有同名 .json 记录参数）"

        def save_cfg(path, seed_val, rand, *values):
            p = pipeline_from_values(values)
            p.seed = get_seed(seed_val, rand)
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            p.save(path)
            return f"已保存到 `{path}`"

        def load_cfg(path):
            if not Path(path).is_file():
                raise gr.Error(f"文件不存在: {path}")
            p = Pipeline.from_file(path)
            seed_val = 0 if p.seed is None else p.seed
            return [seed_val, p.seed is None, f"已读取 `{path}`", *values_from_pipeline(p)]

        run_btn.click(run_single, [img_in, seed, random_seed, *controls], [img_out, meta_out])
        batch_btn.click(run_batch, [in_dir, out_dir, seed, random_seed, *controls], batch_log)
        save_btn.click(save_cfg, [cfg_path, seed, random_seed, *controls], cfg_msg)
        load_btn.click(load_cfg, cfg_path, [seed, random_seed, cfg_msg, *controls])

    return app


def launch(**kwargs) -> None:
    build_app().launch(**kwargs)
