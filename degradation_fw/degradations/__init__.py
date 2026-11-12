"""All degradations, grouped by category. Import each module here so it registers itself.

weather/   天气 / 大气：雾 ...
lens/      镜头污染：脏污、水滴 ...
sensor/    传感器 / 成像：噪声、模糊 ...

New category = new sub-folder with an __init__.py.
"""

from .sensor import gaussian_noise  # noqa: F401

# TODO: enable once the adapters are written
# from .weather import fog          # noqa: F401
# from .lens import lens_dirt       # noqa: F401
