"""All degradations. Import each module here so it registers itself.

The import order is the order shown in the GUI.
"""

from . import gaussian_noise  # noqa: F401

# TODO: add wrappers for the vendored third_party code, e.g.
# from . import fog        # noqa: F401
# from . import lens_dirt  # noqa: F401
