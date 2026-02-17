import logging
from typing import TYPE_CHECKING, cast

from cadquery import Face

from ..cache import read_from_cache, write_to_cache
from .tex_details import Texture

if TYPE_CHECKING:
    from ..workplane import Workplane
_log = logging.getLogger(__name__)


def add_texture(
    workplane: "Workplane", details: Texture, cache_key: str | None = None
) -> "Workplane":

    # Try to read from cache first
    cached_texture = read_from_cache(cache_key)
    if cached_texture is not None:
        _log.debug("Using cached texture geometry")
        return workplane + cached_texture

    # Determine which faces to process
    selected_faces = workplane.faces().vals()

    if len(selected_faces) > 0:
        assert all(isinstance(f, Face) for f in selected_faces)
        faces_to_texture = cast(list[Face], selected_faces)
    else:
        # No selection - get all faces
        try:
            solid = workplane.findSolid()
            faces_to_texture = solid.Faces()
        except Exception as e:
            raise ValueError("Workplane contains no solid") from e

    # Process all faces through the texture (allows multi-face coordination)
    all_texture_geometry = details._create_for_faces(list(faces_to_texture))

    # Write to cache if cache_key is provided
    write_to_cache(cache_key, all_texture_geometry)

    # Union or cut the texture into the original
    workplane += all_texture_geometry

    return workplane
