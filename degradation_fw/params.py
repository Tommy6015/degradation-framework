"""Parameter specifications.

Each degradation declares its parameters with these classes. The GUI reads them
to build sliders / dropdowns / checkboxes automatically, and the pipeline uses
them to validate and fill in defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Param:
    default: Any
    label: str = ""
    help: str = ""

    def validate(self, value: Any) -> Any:
        return value


@dataclass(frozen=True)
class Float(Param):
    default: float = 0.0
    min: float = 0.0
    max: float = 1.0
    step: float = 0.01

    def validate(self, value: Any) -> float:
        v = float(value)
        if not (self.min <= v <= self.max):
            raise ValueError(f"{v} not in [{self.min}, {self.max}]")
        return v


@dataclass(frozen=True)
class Int(Param):
    default: int = 0
    min: int = 0
    max: int = 100
    step: int = 1

    def validate(self, value: Any) -> int:
        v = int(value)
        if not (self.min <= v <= self.max):
            raise ValueError(f"{v} not in [{self.min}, {self.max}]")
        return v


@dataclass(frozen=True)
class Choice(Param):
    default: str = ""
    choices: tuple[str, ...] = field(default_factory=tuple)

    def validate(self, value: Any) -> str:
        v = str(value)
        if v not in self.choices:
            raise ValueError(f"{v!r} not in {self.choices}")
        return v


@dataclass(frozen=True)
class Bool(Param):
    default: bool = False

    def validate(self, value: Any) -> bool:
        return bool(value)
