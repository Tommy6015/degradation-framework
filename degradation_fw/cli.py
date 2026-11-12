"""Command line entry point:  degfw {list,apply,gui}"""

from __future__ import annotations

import argparse
from pathlib import Path

from .core import registry
from .core.pipeline import Pipeline


def _cmd_list(args) -> None:
    for name in registry.available():
        deg = registry.get(name)
        print(f"{name}  -  {deg.label}")
        for key, spec in deg.params.items():
            extra = ""
            if hasattr(spec, "min"):
                extra = f" [{spec.min}, {spec.max}]"
            elif hasattr(spec, "choices"):
                extra = f" {list(spec.choices)}"
            print(f"    {key}: {type(spec).__name__}{extra} default={spec.default!r}")


def _cmd_apply(args) -> None:
    p = Pipeline.from_file(args.config)
    if args.seed is not None:
        p.seed = args.seed
    src, dst = Path(args.input), Path(args.output)
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        p.save(dst / "pipeline.yaml")
        outs = p.run_folder(src, dst, progress=lambda i, n, f: print(f"[{i}/{n}] {f}"))
        print(f"Done: {len(outs)} images -> {dst}")
    else:
        meta = p.run_file(src, dst)
        print(f"Done: {dst} (seed={meta['seed']})")


def _cmd_gui(args) -> None:
    try:
        from .gui.app import launch
    except ImportError:
        raise SystemExit("GUI not installed. Run:  uv sync --extra gui") from None
    launch(server_name=args.host, server_port=args.port, inbrowser=not args.no_browser)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="degfw", description="Image degradation framework")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list available degradations and their params").set_defaults(func=_cmd_list)

    ap = sub.add_parser("apply", help="apply a pipeline config to an image or folder")
    ap.add_argument("-c", "--config", required=True, help="pipeline YAML")
    ap.add_argument("-i", "--input", required=True, help="image file or folder")
    ap.add_argument("-o", "--output", required=True, help="output file or folder")
    ap.add_argument("--seed", type=int, default=None, help="override config seed")
    ap.set_defaults(func=_cmd_apply)

    gp = sub.add_parser("gui", help="launch the GUI")
    gp.add_argument("--host", default="127.0.0.1")
    gp.add_argument("--port", type=int, default=7860)
    gp.add_argument("--no-browser", action="store_true")
    gp.set_defaults(func=_cmd_gui)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
