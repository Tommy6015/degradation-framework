# 0008: Fog depth: with LiDAR, the point cloud corrects the scale of Depth Pro

- Status: accepted
- Date: 2026-11-24
- Related: `core/lidar.py`, `datasets/tumtraf.py`, `degradations/weather/fog.py` (`lidar_scaled_depth`, `degfw fog --lidar`);
  tests `tests/test_lidar.py`, `tests/degradations/test_fog.py`

## Context

- The fog's intensity is given by the visibility, and Koschmieder's law uses each pixel's distance. If the scale of the depth is wrong,
  the visibility as an intensity label is wrong; the task sheet asks for degradations of known intensity (F4).
- Depth Pro estimates metric depth from a single image. Measured on the TUMTraf A9 roadside camera `s110_camera_basler_south2_8mm`:
  5 frames, compared with the points of `s110_lidar_ouster_south` projected into the image.
  - **Depth Pro's depth is only 0.12–0.13 of the LiDAR depth:** the median depth of the scene is 2.7 m for Depth Pro and 22 m for the LiDAR;
    even with the true focal length from the calibration it is only 0.15. The street seen from above is taken for a miniature model.
  - **Consequence:** fog at a nominal visibility of 100 m looks like about 800 m.
  - **But the ratio is very stable:** near (< 30 m) and far (≥ 60 m) it is almost the same, and the 10–90 % percentiles are 0.12–0.13.
    So the relative structure is right; what is wrong is mainly the overall scale.
  - **Frame-to-frame jitter:** the scale computed from the LiDAR varies between 7.7 and 8.2 from frame to frame (about 7 %), so in a sequence the fog density would jump with it.
- The TUMTraf A9 label files (OpenLABEL format) contain the camera intrinsics, the camera pose relative to the LiDAR,
  and the image file names belonging to each point cloud frame; no separate calibration file is needed.

## Decision

- **Usage:** `degfw fog --lidar FOLDER`. If given, the LiDAR corrects the scale of the depth; without it nothing changes.
- **Per image:**
  1. Find the point cloud and calibration of this frame in the labels, by the image file name (`datasets/tumtraf.py`). If several LiDARs belong to the image, the points of all of them are used.
  2. Project the points into the image (`core/lidar.py`). Depth is the z coordinate in the camera frame, i.e. the distance along the optical axis, the same quantity as Depth Pro's depth.
  3. Scale = median(LiDAR depth ÷ Depth Pro depth), depth = Depth Pro × scale. The atmospheric light estimation and the fog itself are unchanged;
     the sky test (≥ 1000 m) and the average atmospheric light over the batch also use the corrected depth.
  4. **Fallback:** with fewer than 50 points in the image, a missing point cloud file, or a calibration for a different image size, the image uses Depth Pro only;
     the terminal says so, and `fog_run.json` records the reason.
- **Record:** for each image, `fog_run.json` records the depth source, the scale, the number of points used, the residual error after correction (median and 90th percentile), and the label and point cloud files used.
- **Coordinate convention of the TUMTraf labels:** `pose_wrt_parent` maps coordinates of the parent system into the child system, X_child = P · X_parent.
  This was checked by projecting the points into the image: with the opposite direction, the points do not match the image at all.
- **Dataset-specific code only in `datasets/tumtraf.py`:** it turns each image's point clouds and calibration into `LidarView`s (defined in `core/lidar.py`).
  For another dataset, another reader providing `views_for(image file name)` is enough; `core/lidar.py` and the fog code stay unchanged.

## Options considered

- **Point cloud only, no Depth Pro**: after projection only 0.2 % of the pixels have a point, and only in rows 134 to 852 (of 1200);
  the near road in the lower third of the image and the nearby cars have no points at all. These areas could only be interpolated or extrapolated, and the near range is exactly where the fog must be right. Not chosen.
- **LiDAR values directly at pixels with a point, corrected Depth Pro elsewhere**: the points are sparse, so the fog would show dot-like spots.
  The median error after correction is already only 2–3 %, so there is little to gain. Not chosen.
- **A scale per region (a scale map interpolated from the points)**: the ratio is almost the same near and far, so one global scale is enough. To be added if another camera turns out to need it.
- **One scale for a whole sequence**: with a correction per frame, the median depth of all 5 frames is already 22.0 ± 0.1 m; Depth Pro's frame-to-frame jitter is gone. Not needed.
- **Compensating the time offset between camera and LiDAR** (30–80 ms): moving cars are off by about 1 m, but with the median this hardly affects the scale. Not done.

## Consequences

- **Data with LiDAR:** the fog density matches the nominal visibility. On the 5 demo images the scale is 7.66 to 8.22,
  and at the points the median relative depth error after correction is 2.1 % to 2.6 %.
- **Without `--lidar`:** the results are pixel-identical to before (regression test `test_fog_matches_reference`).
- **Datasets without LiDAR still have the problem:** with Depth Pro alone, the fog on roadside cameras can be much weaker than the nominal visibility.
  Whether to correct the scale another way (e.g. with a camera calibration, from the camera height and the ground plane, which give the distance of the road) is decided together with the intensity levels (F4).
- **Only `degfw fog` can use it:** `degfw run fog`, `apply` and the GUI cannot use the LiDAR yet, because the degradation interface only gets the pixels, not where the image comes from;
  this waits for the M3 interface extension (source information).
- **Supported:** only TUMTraf OpenLABEL labels, and PCD files with ascii or binary data; no new dependencies.
