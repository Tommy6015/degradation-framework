"""Registry of available degradations.

Use ``@register`` on a Degradation subclass; it then shows up in the GUI and CLI.
"""

from __future__ import annotations

from .base import Degradation

_REGISTRY: dict[str, type[Degradation]] = {}


def register(cls: type[Degradation]) -> type[Degradation]:
    if not cls.name:
        raise ValueError(f"{cls.__name__} has no `name`")
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
