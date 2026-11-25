"""Framework core — shared by every degradation. Normally you don't need to touch this.

base.py      Degradation base class (unified interface; requires_modules / requires_weights)
context.py   what a degradation knows about the image besides its pixels (source, run, info)
params.py    parameter types: Float / Int / Choice / Bool / Folder
registry.py  @register, get(), available(); register_command() for a degradation's own command
pipeline.py  chain degradations, batch folders, save metadata
io.py        image load / save / format conversion
paths.py     project paths; the only way to load third_party code (see its docstring)
weights.py   model weights listed in third_party/weights.yaml: find, verify, download
lidar.py     LiDAR points as depth measurements: read PCD, project into an image, fit a depth scale
"""
