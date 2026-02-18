"""
3D Design Package

A collection of tools for 3D design using CadQuery.
"""

from .cache import cached_workplane, read_from_cache, write_to_cache
from .dev_tools import show
from .selectors import Selectors
from .texture.brick import BrickTexture
from .texture.hex import HoneycombTexture
from .texture.hex_grid import HexGridTexture
from .texture.linear import LinearTexture
from .texture.rooftop import RooftopTileTexture
from .transforms import align
from .workplane import Workplane

__all__ = [
    "Workplane",
    "BrickTexture",
    "HoneycombTexture",
    "HexGridTexture",
    "LinearTexture",
    "RooftopTileTexture",
    "Selectors",
    "align",
    "cached_workplane",
    "read_from_cache",
    "write_to_cache",
    "show",
]
