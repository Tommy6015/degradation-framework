"""Image degradation framework."""

from .core.base import Degradation
from .core.params import Bool, Choice, Float, Int
from .core.pipeline import Pipeline, Step
from .core.registry import available, get, register, register_command

__all__ = ["Degradation", "Float", "Int", "Choice", "Bool",
           "Pipeline", "Step", "register", "register_command", "get", "available"]
__version__ = "0.1.0"
