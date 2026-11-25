"""What a degradation knows about an image besides its pixels (decision 0010).

The pipeline passes a Context with every image to Degradation.apply. Most
degradations ignore it; fog uses it for what Clear2Fog needs beyond the pixels: the
source file (its EXIF focal length, and its name to find the LiDAR frame that belongs
to it) and the run's other images (the average atmospheric light for images without
sky).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Context:
    """source  the input file the image was read from (upright, see io.load_image), or
            None for an image in memory (e.g. a preview in the GUI, a test)
    batch   all input files of this run, in processing order, the source among them;
            () for an image in memory
    shared  a dict that lasts for the whole run, one per step: for what is computed
            once per run and then reused for every image (e.g. fog: the LiDAR index and
            the average atmospheric light). Starts empty in every run.
    info    filled by the degradation for this image: what it found or decided that is
            not a parameter (e.g. fog: where the depth and the atmospheric light came
            from). Recorded in the image's .json under the step, key "info"; must be
            JSON-serialisable (plain int / float / str / list / dict).
    """

    source: Path | None = None
    batch: tuple[Path, ...] = ()
    shared: dict[str, Any] = field(default_factory=dict)
    info: dict[str, Any] = field(default_factory=dict)
