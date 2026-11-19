"""Command line entry point:  degfw {list,run,apply,weights,gui}

plus the commands that degradation modules register themselves (e.g. ``degfw fog``,
see registry.register_command). Nothing here is specific to one degradation.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path

import yaml

from .core import registry
from .core.pipeline import Pipeline, Step

BUILTIN_COMMANDS = {"list", "run", "apply", "weights", "gui"}


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


def _check_usable(names: Iterable[str]) -> None:
    """Exit with a clear message if a degradation is unknown or cannot run here."""
    for name in names:
        try:
            deg = registry.get(name)
        except KeyError as e:
            raise SystemExit(e.args[0]) from None
        reason = deg.unavailable_reason()
        if reason:
            raise SystemExit(f"{name} cannot run here:\n{reason}")


def _run_pipeline(p: Pipeline, src: str | Path, dst: str | Path) -> None:
    """Image -> image file; folder -> folder (with pipeline.yaml). Shared by run and apply."""
    src, dst = Path(src), Path(dst)
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        p.save(dst / "pipeline.yaml")
        outs = p.run_folder(src, dst, progress=lambda i, n, f: print(f"[{i}/{n}] {f}"))
        print(f"Done: {len(outs)} images -> {dst}")
    elif src.is_file():
        meta = p.run_file(src, dst)
        print(f"Done: {dst} (seed={meta['seed']})")
    else:
        raise SystemExit(f"Not found: {src}")


def _parse_params(items: list[str] | None) -> dict:
    """-p KEY=VALUE ... -> dict. Values are read as YAML, like in config files:
    50 -> int, 0.3 -> float, true -> bool, anything else -> string."""
    params = {}
    for item in items or []:
        key, sep, value = item.partition("=")
        if not sep or not key.strip():
            raise SystemExit(f"-p expects KEY=VALUE, got {item!r}")
        params[key.strip()] = yaml.safe_load(value) if value.strip() else ""
    return params


def _cmd_run(args) -> None:
    params = _parse_params(args.param)
    _check_usable([args.name])
    try:
        registry.get(args.name).resolve_params(params)  # unknown / invalid params: stop before any work
    except (KeyError, ValueError) as e:
        raise SystemExit(e.args[0]) from None
    _run_pipeline(Pipeline([Step(args.name, params)], seed=args.seed), args.input, args.output)


def _cmd_apply(args) -> None:
    p = Pipeline.from_file(args.config)
    if args.seed is not None:
        p.seed = args.seed
    _check_usable(s.name for s in p.steps)
    _run_pipeline(p, args.input, args.output)


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


def _cmd_gui(args) -> None:
    try:
        from .gui.app import launch
    except ImportError:
        raise SystemExit("GUI not installed. Run:  uv sync --extra gui") from None
    launch(server_name=args.host, server_port=args.port, inbrowser=not args.no_browser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="degfw", description="Image degradation framework")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list degradations, their params and whether they can run here"
                   ).set_defaults(func=_cmd_list)

    rp = sub.add_parser("run", help="apply one degradation to an image or folder",
                        description="Apply one registered degradation (see degfw list) to an image or a folder. "
                                    "Writes the result(s) and a .json with the params and seed next to each.")
    rp.add_argument("name", help="degradation name, see degfw list")
    rp.add_argument("-i", "--input", required=True, help="image file or folder")
    rp.add_argument("-o", "--output", required=True, help="output file or folder")
    rp.add_argument("-p", "--param", nargs="+", action="extend", metavar="KEY=VALUE",
                    help="parameters, e.g. -p visibility=50 fp16=true (others keep their defaults)")
    rp.add_argument("--seed", type=int, default=0, help="random seed (default 0)")
    rp.set_defaults(func=_cmd_run)

    ap = sub.add_parser("apply", help="apply a pipeline config (several degradations) to an image or folder")
    ap.add_argument("-c", "--config", required=True, help="pipeline YAML")
    ap.add_argument("-i", "--input", required=True, help="image file or folder")
    ap.add_argument("-o", "--output", required=True, help="output file or folder")
    ap.add_argument("--seed", type=int, default=None, help="override config seed")
    ap.set_defaults(func=_cmd_apply)

    wp = sub.add_parser("weights", help="state of the model weights of third_party code (third_party/weights.yaml)",
                        description="List the model weights in third_party/weights.yaml and whether they are here.")
    wp.add_argument("--verify", action="store_true", help="also check the SHA-256 of every file (reads them all)")
    wp.add_argument("--download", action="store_true", help="download missing files that have a url, then verify")
    wp.set_defaults(func=_cmd_weights)

    for cmd in registry.commands():  # registered by degradation modules, e.g. degfw fog
        if cmd.name in BUILTIN_COMMANDS:
            raise RuntimeError(f"A degradation module registered the built-in command name {cmd.name!r}")
        cp = sub.add_parser(cmd.name, help=cmd.help, description=cmd.description)
        cmd.add_arguments(cp)
        cp.set_defaults(func=cmd.run)

    gp = sub.add_parser("gui", help="launch the GUI")
    gp.add_argument("--host", default="127.0.0.1")
    gp.add_argument("--port", type=int, default=7860)
    gp.add_argument("--no-browser", action="store_true")
    gp.set_defaults(func=_cmd_gui)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    code = args.func(args)
    if code:
        raise SystemExit(code)


if __name__ == "__main__":
    main()
