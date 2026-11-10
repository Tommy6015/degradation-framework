"""Image degradation framework."""

from .base import Degradation
from .params import Bool, Choice, Float, Int
from .pipeline import Pipeline, Step
from .registry import available, get, register

__all__ = ["Degradation", "Float", "Int", "Choice", "Bool",
           "Pipeline", "Step", "register", "get", "available"]
__version__ = "0.1.0"
