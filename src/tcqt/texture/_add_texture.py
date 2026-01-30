import logging

from cadquery import Face

from dtools.primitives.cache import read_from_cache, write_to_cache
from dtools.texture.tex_details import Texture
from dtools.workplane import Workplane

_log = logging.getLogger(__name__)


def add_texture(workplane: Workplane, details: Texture, cache_key: str | None = None):
    # Try to read from cache first
    cached_texture = read_from_cache(cache_key)
    if cached_texture is not None:
        _log.debug("Using cached texture geometry")
        return workplane + cached_texture

    # Determine which faces to process
    selected_faces = workplane.faces().vals()

    if len(selected_faces) > 0:
        faces_to_texture = selected_faces
    else:
        # No selection - get all faces
        try:
            solid = workplane.findSolid()
            faces_to_texture = solid.Faces()
        except Exception as e:
            raise ValueError("Workplane contains no solid") from e

    # Accumulate all texture geometry
    all_texture_geometry = Workplane()

    # Process each face
    for face in faces_to_texture:
        assert isinstance(face, Face)
        # Apply texture (your implementation)
        texture_geometry = details._create_for_face(face)

        # Accumulate texture geometry
        all_texture_geometry += texture_geometry

    # Write to cache if cache_key is provided
    write_to_cache(cache_key, all_texture_geometry)

    # Union or cut the texture into the original
    workplane += all_texture_geometry

    return workplane
