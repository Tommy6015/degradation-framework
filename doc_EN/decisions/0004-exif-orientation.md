# 0004: Images are turned upright by EXIF orientation when read; RGB and depth of the fog come from the same pixels

- Status: accepted
- Date: 2026-11-19
- Related: `core/io.py` (`load_rgb_u8`, `load_image`), `degradations/weather/fog.py` (`Clear2Fog.load`); commit `7a2e74d`

## Context

Phones store portrait photos sideways in the file, together with an EXIF orientation tag.

- Clear2Fog's `c2f.py` reads the RGB without applying the tag, while Depth Pro rotates the same file when computing the depth.
  For photos rotated by 90° the two shapes differ and processing fails; for 180° nothing fails, but the depth is upside down and the fog is silently wrong.
- The framework's own `load_image` did not apply the tag either: portrait photos were processed and saved sideways.

## Decision

- `core/io.py`: images are turned upright with `ImageOps.exif_transpose` when read (all 8 orientations) and converted to RGB.
  Every entry point (`degfw run`, `apply`, GUI, scripts) gets the upright image; output files carry no orientation tag.
- Fog: `Clear2Fog.load` computes RGB and depth from the same upright pixels; the EXIF focal length is still used.

## Options considered

- **Keep the behaviour of `c2f.py`**: tagged photos fail or come out wrong.
- **Only handle orientations 3/6/8 as Depth Pro does**: mirrored orientations (2/4/5/7) are not handled.
- **Handle it only in the fog adapter**: other degradations and the GUI would still process the sideways image; the paths would disagree.

## Consequences

- Photos with an orientation tag are now processed correctly, and the output is upright.
- Images without a tag give the same result as before, pixel by pixel (verified). So "pixel-identical to the original Clear2Fog" holds only for images without a tag.
