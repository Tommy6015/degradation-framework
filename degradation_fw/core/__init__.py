"""Framework core — shared by every degradation. Normally you don't need to touch this.

base.py      Degradation base class (unified interface)
params.py    parameter types: Float / Int / Choice / Bool
registry.py  @register decorator, get(), available()
pipeline.py  chain degradations, batch folders, save metadata
io.py        image load / save / format conversion
paths.py     project paths, helper to import third_party code
"""
