"""All degradations, grouped by category. Import each module here so it registers itself.

weather/   天气 / 大气：雾
lens/      镜头污染：水滴（接入进行中；精确放置已在 lens/placement.py）

New category = new sub-folder with an __init__.py. The categories follow the light's
path (scene / atmosphere -> lens -> sensor), which is also the order in which they are
combined.
"""

from .weather import fog  # noqa: F401  (Clear2Fog; loads Depth Pro only when first used)
