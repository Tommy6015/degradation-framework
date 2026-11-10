"""Gaussian sensor noise — a small, self-contained example degradation."""

from __future__ import annotations

import numpy as np

from ..base import Degradation
from ..params import Bool, Float
from ..registry import register


@register
class GaussianNoise(Degradation):
    name = "gaussian_noise"
    label = "高斯噪声 Gaussian noise"
    description = "Additive Gaussian noise, like a noisy camera sensor."
    params = {
        "sigma": Float(default=0.05, min=0.0, max=0.5, step=0.005, label="强度 sigma"),
        "per_channel": Bool(default=True, label="各通道独立 (彩色噪声)"),
    }

    def apply(self, image, rng, sigma, per_channel):
        shape = image.shape if per_channel else image.shape[:2] + (1,)
        noise = rng.normal(0.0, sigma, size=shape).astype(np.float32)
        return image + noise
