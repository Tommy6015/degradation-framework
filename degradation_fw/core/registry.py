"""Registry of available degradations, and of extra command-line commands.

Use ``@register`` on a Degradation subclass; it then shows up in the GUI and CLI
(``degfw list``, ``degfw run <name>``, configs for ``degfw apply``).

A degradation that needs a command of its own (most don't) registers it from its
own module with ``register_command``, e.g. ``degfw fog`` in weather/fog.py, so
cli.py never has to change for a new degradation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .base import Degradation

if TYPE_CHECKING:
    import argparse

_REGISTRY: dict[str, type[Degradation]] = {}


def register(cls: type[Degradation]) -> type[Degradation]:
    if not cls.name:
        raise ValueError(f"{cls.__name__} has no `name`")
    reserved = {"image", "rng", "context"} & set(cls.params)  # the other arguments of apply()
    if reserved:
        raise ValueError(f"{cls.name}: parameter name(s) {sorted(reserved)} are reserved")
    if cls.name in _REGISTRY and _REGISTRY[cls.name] is not cls:
        raise ValueError(f"Degradation name {cls.name!r} already registered")
    _REGISTRY[cls.name] = cls
    return cls


def _ensure_loaded() -> None:
    # Importing the package runs the @register decorators.
    from .. import degradations  # noqa: F401


def get(name: str) -> Degradation:
    _ensure_loaded()
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise KeyError(f"Unknown degradation {name!r}. Available: {available()}") from None


def available() -> list[str]:
    _ensure_loaded()
    return list(_REGISTRY)


# ---- extra commands: degfw <name> ---------------------------------------------------
@dataclass(frozen=True)
class Command:
    name: str
    help: str  # one line, shown in `degfw --help`
    add_arguments: Callable[[argparse.ArgumentParser], None]
    run: Callable[[argparse.Namespace], int | None]  # returns the exit code (None = 0)
    description: str | None = None  # shown in `degfw <name> --help`


_COMMANDS: dict[str, Command] = {}


def register_command(name: str, *, help: str, add_arguments: Callable[[argparse.ArgumentParser], None],
                     run: Callable[[argparse.Namespace], int | None],
                     description: str | None = None) -> Command:
    """Add ``degfw <name>``. Call it at the top level of the degradation's module; keep
    ``add_arguments`` light and load models only inside ``run``."""
    cmd = Command(name, help, add_arguments, run, description)
    if name in _COMMANDS and _COMMANDS[name].run is not run:
        raise ValueError(f"Command {name!r} already registered")
    _COMMANDS[name] = cmd
    return cmd


def commands() -> list[Command]:
    _ensure_loaded()
    return list(_COMMANDS.values())
