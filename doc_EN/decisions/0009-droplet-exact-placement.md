# 0009: Water drops are placed exactly where we specify; the network only provides the shape

- Status: accepted
- Date: 2026-11-24
- Related: `degradation_fw/degradations/lens/placement.py` (`place_mask`), `scripts/contamination_examples.py` (`PlacedDropletGenerator`, `--droplet-placement`);
  tests `tests/degradations/test_droplet_placement.py`

## Context

- The task sheet asks for degradations of known type and intensity. Where a water drop sits decides which part of the scene it covers;
  exporting masks and analysing the effect on object detection both depend on it.
- The water drop network of camera_contamination_simulation takes `[x, y, size]` together with 100 random numbers and draws a probability map over the whole image.
  Where the drop actually ends up is decided by the network; x and y are only a hint.
- **The measured deviation is large** (5 positions × 2 SIZEs × 10 seeds):
  - the drop's centre is on average 4 % to 20 % of the longer side away from the requested position, more so near the edges: the network pulls drops inwards.
  - On average 34–192 px (at most 239 px) on 960×960 images, 69–266 px (at most 355 px) on 1920×1200 images.
- **The shape hardly depends on the position:** at all positions the aspect ratio is between 1.0 and 1.4 and the fill ratio between 0.5 and 0.75. Generating the shape at a fixed position and moving it therefore loses nothing.

## Decision

- **The network only provides the shape:** wherever the drop is requested, the network is asked to draw it in the centre (0.5, 0.5), with SIZE and random numbers as before.
  The shape is then complete and not cut off by the image edge.
- **Exact placement by the centroid:** take the drawn drop pixels (by the same rule as `find_droplets`: `np.uint8(mask * 255) >= threshold * 255`, threshold 0.5),
  compute their centroid, and shift the whole mask so that the centroid lies on (X·width − 0.5, Y·height − 0.5) (pixel index coordinates).
  The shift is by whole pixels, so the error is at most 0.5 px per axis.
- **Several pieces keep their shape:** they are shifted together, keeping their relative positions; the centroid of all pieces together is aligned.
- **Edges:** the shifted mask is placed on a canvas that holds both the image and the whole shape. The part outside the image is cut off,
  but `find_droplets` still measures the drop's full size on the whole canvas, so the zoom-in / zoom-out decision is unaffected.
- **Retry when no drop is drawn:** if the network's probability map has no drop pixel at all, the network is called again, up to 20 times. The random numbers continue, so the result stays reproducible;
  if all 20 attempts fail, an error is reported.
- **No change to the third-party code:** a subclass of `DropletGenerator` overrides only `generate_mask`: `simulate_droplet` gets its mask from this method,
  and everything after it (splitting, zoom-in / zoom-out, refraction, blending) is the original code. The shift itself is computed in the framework (`placement.py`, numpy only),
  to be reused when the drops are integrated into the framework in M4.
- **The original behaviour stays available:** with `--droplet-placement network` the original `DropletGenerator` is used directly, and the results are pixel-identical to before the change, for comparison.
  The default is `exact`.
- **Records:** `seed.json` records the placement used and, for each drop, the centroid reached, the shift, the number of network calls and whether the shape touches the edge of the network's canvas.

## Options considered

- **Pass the requested position to the network, then shift by the deviation**: the shape might keep position-dependent features. But near the edges the drop the network draws may be partly cut off by its canvas,
  and after the shift a straight cut would show; and the measurements show the shape hardly depends on the position. Not chosen.
- **Keep only the largest piece when the shape splits**: one position would then be exactly one drop, which keeps the labels simpler. But the cluster shape drawn by the network would be lost, and at larger SIZE the total area of the drops would shrink. Not chosen.
- **Align the centre of the bounding box**: for irregular shapes the bounding box centre can lie outside the drop; the centroid represents the drop's position better. Not chosen.
- **Sub-pixel shift (interpolation)**: would reduce the error from 0.5 px to nearly 0, but interpolation softens the mask, so it would no longer match the original rendering exactly. The whole-pixel error is small enough. Not chosen.
- **Change `simulate_droplet` in `third_party/`**: a subclass is enough, no change to the third-party code is needed ([decision 0001](0001-third-party-vendoring.md)). Not chosen.

## Consequences

- **Exact positions:** for 100 drops at each of two resolutions, the centroid is on average 0.35–0.39 px from the requested position, at most 0.61 px.
- **Default results change:** with the same parameters and seed, both position and shape of the drops differ from before: the shape now depends only on SIZE and the random numbers, no longer on the position.
  To get the earlier results, add `--droplet-placement network`.
- **Not affected:** the results of opaque and semi-transparent soiling are pixel-identical; their position is still only a hint. Whether to place them exactly as well is decided together with whether these two types are implemented.
- **Size still not exact:** SIZE is still only a hint to the network. The next step follows the same idea: scale the shape to the requested size before shifting it;
  this needs a definition of "size" (e.g. the diameter of the circle of equal area) and a unit (pixels, or millimetres converted with camera parameters).
- **Very small SIZE:** previously a spot could end up with no drop at all; now the network is called again until there is one. If SIZE is so small that 20 attempts fail, an error is reported instead of silently generating an image without a drop.
