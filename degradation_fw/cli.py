"""Command line entry point:  degfw {list,apply,fog,weights,gui}"""

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
        reason = deg.unavailable_reason()
        if reason:
            print("    UNAVAILABLE here: " + reason.replace("\n", "\n    "))


def _cmd_weights(args) -> int:
    from .core import weights

    bad = 0
    for w in weights.manifest().values():
        state = weights.status(w, verify=args.verify)
        if state in ("missing", "wrong size", "SHA-256 mismatch") and args.download and w.url:
            print(f"{w.id}: downloading {w.url} ({w.size / 2**20:.0f} MiB)")
            weights.download(w, progress=_progress)
            print()
            state = "ok (downloaded)"
        print(f"  {w.id:<24} {state:<17} {w.size / 2**20:>7.1f} MiB  "
              f"{'download' if w.url else 'in git':<9} third_party/{w.relpath}")
        bad += state not in ("present", "ok", "ok (downloaded)")
    if bad:
        print(f"{bad} file(s) not usable." + ("" if args.download else "  Download with: uv run degfw weights --download"))
    elif not args.verify:
        print("All present (size checked). SHA-256: uv run degfw weights --verify")
    return 1 if bad else 0


def _progress(done: int, total: int) -> None:
    print(f"\r  {done / 2**20:.0f} / {total / 2**20:.0f} MiB ({done / max(total, 1):.0%})", end="", flush=True)


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


def _cmd_fog(args) -> None:
    from .degradations.weather.fog import run_cli

    failed = run_cli(args.input, args.output, args.visibility, fp16=args.fp16)
    if failed:
        raise SystemExit(1)


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

    fp = sub.add_parser("fog", help="add fog with Clear2Fog (Depth Pro depth + atmospheric scattering)",
                        description="Add fog to images with Clear2Fog. Output: OUTPUT/foggy_<name>_vis_<v>.png")
    fp.add_argument("-i", "--input", type=Path, nargs="+", required=True,
                    help="input image(s) and/or folder(s) with .png/.jpg/.jpeg")
    fp.add_argument("-o", "--output", type=Path, required=True, help="output folder")
    fp.add_argument("-v", "--visibility", type=int, nargs="+", default=[100],
                    help="visibility in metres, lower = denser fog (default 100); several values: one image each")
    fp.add_argument("--fp16", action="store_true",
                    help="run Depth Pro in float16: ~20x faster on an 8 GB GPU, results differ slightly "
                         "from Clear2Fog (default float32 = identical)")
    fp.set_defaults(func=_cmd_fog)

    wp = sub.add_parser("weights", help="state of the model weights of third_party code (third_party/weights.yaml)",
                        description="List the model weights in third_party/weights.yaml and whether they are here.")
    wp.add_argument("--verify", action="store_true", help="also check the SHA-256 of every file (reads them all)")
    wp.add_argument("--download", action="store_true", help="download missing files that have a url, then verify")
    wp.set_defaults(func=_cmd_weights)

    gp = sub.add_parser("gui", help="launch the GUI")
    gp.add_argument("--host", default="127.0.0.1")
    gp.add_argument("--port", type=int, default=7860)
    gp.add_argument("--no-browser", action="store_true")
    gp.set_defaults(func=_cmd_gui)

    args = parser.parse_args(argv)
    code = args.func(args)
    if code:
        raise SystemExit(code)


if __name__ == "__main__":
    main()
