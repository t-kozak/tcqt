import hashlib
import logging
import math
import os
import random
from dataclasses import dataclass

import cadquery as cq
from dev_tools import tqdm
from stopwatch import Stopwatch

from ..transforms.merge import merge_shapes_in_batches_threaded
from ..workplane import Workplane
from .tex_details import Texture

_log = logging.getLogger(__name__)


@dataclass
class HoneycombTexture(Texture):
    hex_side_len: float
    hex_height_min: float
    hex_height_max: float
    height_steps: int = 10
    rotation_degrees: float = 0.0
    spacing_coefficient: float = 1.0
    random_seed: int = 42

    def _create_for_face(self, face: cq.Face) -> Workplane:
        # Get face bounding box to determine texture area
        assert isinstance(face, cq.Face)

        # Generate hex texture for this face
        res = _generate_hex_texture_for_face(
            face,
            self,
            False,
        )
        if not res:
            return Workplane()
        hex_texture, _, __ = res

        return self._cut_to_face_boundary(face, hex_texture, self.hex_height_max)


def _get_face_coordinate_system(
    face_normal: cq.Vector, details: HoneycombTexture
) -> tuple[cq.Vector, cq.Vector]:
    """
    Calculate proper u and v vectors for a face based on its normal and apply rotation.
    This ensures consistent orientation across all face types.
    """
    # Normalize the normal vector
    normal = face_normal.normalized()

    # Choose a reference vector that is guaranteed not to be parallel
    # We'll test multiple reference vectors to find one that works
    reference_candidates = [
        cq.Vector(1, 0, 0),  # X axis
        cq.Vector(0, 1, 0),  # Y axis
        cq.Vector(0, 0, 1),  # Z axis
    ]

    u_vec = None

    for reference in reference_candidates:
        # Calculate cross product
        cross_result = normal.cross(reference)

        # Check if cross product has sufficient magnitude (not parallel)
        cross_magnitude = math.sqrt(
            cross_result.x**2 + cross_result.y**2 + cross_result.z**2
        )

        if cross_magnitude > 1e-6:  # Not parallel (within tolerance)
            u_vec = cross_result.normalized()
            break

    if u_vec is None:
        # This should never happen with our three orthogonal reference vectors
        raise ValueError("Could not find suitable reference vector for face normal")

    # Calculate v vector (second tangent vector, perpendicular to both normal and u)
    v_vec = normal.cross(u_vec).normalized()

    # Apply rotation if specified
    if abs(details.rotation_degrees) > 1e-6:  # Only rotate if rotation is significant
        rotation_radians = math.radians(details.rotation_degrees)
        cos_theta = math.cos(rotation_radians)
        sin_theta = math.sin(rotation_radians)

        # Rotate u and v vectors around the normal vector using Rodrigues' rotation
        # formula
        # For rotation around normal vector: new_u = u*cos(θ) + v*sin(θ)
        # new_v = -u*sin(θ) + v*cos(θ)
        rotated_u = u_vec.multiply(cos_theta).add(v_vec.multiply(sin_theta))
        rotated_v = u_vec.multiply(-sin_theta).add(v_vec.multiply(cos_theta))

        u_vec = rotated_u.normalized()
        v_vec = rotated_v.normalized()

    return u_vec, v_vec


def _hex_would_intersect_face(
    local_x: float,
    local_y: float,
    hex_side_len: float,
    face: cq.Face,
    face_center: cq.Vector,
    u_vec: cq.Vector,
    v_vec: cq.Vector,
) -> bool:
    """
    Check if a hexagon at the given local coordinates would intersect with the face.
    This checks if any part of the hexagon intersects with the face boundary.
    """
    # Convert local coordinates to 3D world position
    world_pos = face_center + u_vec.multiply(local_x) + v_vec.multiply(local_y)

    # Project the world position back onto the face plane
    # This gives us the 2D coordinates in the face's local coordinate system
    relative_pos = world_pos - face_center
    u_proj = relative_pos.dot(u_vec)
    v_proj = relative_pos.dot(v_vec)

    # Get face vertices in the face's coordinate system
    face_vertices = face.outerWire().Vertices()
    face_2d_points = []

    for vertex in face_vertices:
        vertex_pos = vertex.Center()
        vertex_relative = vertex_pos - face_center
        vertex_u = vertex_relative.dot(u_vec)
        vertex_v = vertex_relative.dot(v_vec)
        face_2d_points.append((vertex_u, vertex_v))

    # Calculate hexagon vertices in 2D face coordinate system
    # Hexagon radius (distance from center to vertex)
    hex_radius = hex_side_len

    # Generate hexagon vertices (6 vertices of a regular hexagon)
    hex_vertices = []
    for i in range(6):
        angle = i * math.pi / 3  # 60 degrees per vertex
        hex_u = u_proj + hex_radius * math.cos(angle)
        hex_v = v_proj + hex_radius * math.sin(angle)
        hex_vertices.append((hex_u, hex_v))

    # Check if any hexagon vertex is inside the face
    for hex_u, hex_v in hex_vertices:
        if _point_in_polygon(hex_u, hex_v, face_2d_points):
            return True

    # Check if any face vertex is inside the hexagon
    for face_u, face_v in face_2d_points:
        if _point_in_polygon(face_u, face_v, hex_vertices):
            return True

    # Check if any hexagon edge intersects with any face edge
    for i in range(6):
        hex_p1 = hex_vertices[i]
        hex_p2 = hex_vertices[(i + 1) % 6]

        for j in range(len(face_2d_points)):
            face_p1 = face_2d_points[j]
            face_p2 = face_2d_points[(j + 1) % len(face_2d_points)]

            if _line_segments_intersect(hex_p1, hex_p2, face_p1, face_p2):
                return True

    return False


def _point_in_polygon(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
    """
    Point-in-polygon test using ray casting algorithm.
    """
    n = len(polygon)
    inside = False

    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    else:
                        xinters = p1x  # Handle horizontal edge case
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


def _line_segments_intersect(
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    p4: tuple[float, float],
) -> bool:
    """
    Check if two line segments intersect.
    """
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4

    # Calculate the direction of the lines
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)

    # Lines are parallel
    if abs(denom) < 1e-10:
        return False

    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom

    # Check if intersection point is on both line segments
    return 0 <= t <= 1 and 0 <= u <= 1


def _calculate_hex_grid(
    face: cq.Face,
    details: HoneycombTexture,
    u_vec: cq.Vector,
    v_vec: cq.Vector,
) -> tuple[int, int, float, float, float, float, float, float]:
    """
    Calculate the grid dimensions and spacing for hexagonal texture on a face.

    Returns:
        Tuple of (rows, cols, x_spacing, y_spacing, face_width, face_height,
        half_width, half_height)
    """
    # Get face center
    face_center = face.Center()

    # Calculate face dimensions in the texture coordinate system
    # Project face vertices onto the texture plane to get accurate dimensions
    face_vertices = face.outerWire().Vertices()

    # Project all vertices onto the texture coordinate system
    u_coords = []
    v_coords = []

    for vertex in face_vertices:
        vertex_pos = vertex.Center()
        # Vector from face center to vertex
        relative_pos = vertex_pos - face_center

        # Project onto u and v vectors
        u_proj = relative_pos.dot(u_vec)
        v_proj = relative_pos.dot(v_vec)

        u_coords.append(u_proj)
        v_coords.append(v_proj)

    # Calculate dimensions in texture coordinate system
    u_min, u_max = min(u_coords), max(u_coords)
    v_min, v_max = min(v_coords), max(v_coords)

    face_width = u_max - u_min
    face_height = v_max - v_min

    # Calculate hexagon spacing for proper honeycomb pattern
    x_spacing = details.hex_side_len * math.sqrt(3)
    y_spacing = details.hex_side_len * 0.5
    x_spacing *= details.spacing_coefficient
    y_spacing *= details.spacing_coefficient

    # Calculate grid dimensions with tighter bounds since we're doing
    # intersection checks
    # Reduced margin since we check intersections
    cols = int(math.ceil(face_width / x_spacing)) + 1
    rows = int(math.ceil(face_height / y_spacing)) + 1

    _log.debug(
        f"Hex texture grid: {cols} columns × {rows} rows = "
        f"{cols * rows} potential positions"
    )

    half_width = face_width / 2
    half_height = face_height / 2

    return (
        rows,
        cols,
        x_spacing,
        y_spacing,
        face_width,
        face_height,
        half_width,
        half_height,
    )


def _create_height_groups(
    face: cq.Face,
    details: HoneycombTexture,
    rows: int,
    cols: int,
    x_spacing: float,
    y_spacing: float,
    half_width: float,
    half_height: float,
    face_center: cq.Vector,
    u_vec: cq.Vector,
    v_vec: cq.Vector,
) -> dict[float, list[tuple[cq.Vector, float, float]]]:
    """
    Create height groups by iterating over rows and columns to determine
    hexagon positions and heights.

    Returns:
        Dictionary mapping discretized heights to lists of
        (world_pos, local_x, local_y) tuples
    """
    # Discretize heights
    height_range = details.hex_height_max - details.hex_height_min
    height_step_size = (
        height_range / details.height_steps if details.height_steps > 1 else 0
    )

    # Group positions by discretized height
    height_groups = {}

    rng = random.Random(details.random_seed)

    # Count how many hexagons will actually be generated
    hex_count = 0
    for row in range(rows):
        for col in range(cols):
            # Local 2D coordinates in texture plane (relative to face center)
            local_x = (col * x_spacing) - half_width
            local_y = (row * y_spacing) - half_height

            # Offset every other row for honeycomb pattern
            if row % 2 == 1:
                local_x += x_spacing / 2

            # Check if hexagon would intersect with the face before creating it
            if _hex_would_intersect_face(
                local_x,
                local_y,
                details.hex_side_len,
                face,
                face_center,
                u_vec,
                v_vec,
            ):
                hex_count += 1

    _log.debug(f"Will generate {hex_count} hexagons")

    # Start timing hexagon generation
    generation_timer = Stopwatch()
    generation_timer.start()
    # Now actually generate the hexagons
    for row in range(rows):
        for col in range(cols):
            # Local 2D coordinates in texture plane (relative to face center)
            local_x = (col * x_spacing) - half_width
            local_y = (row * y_spacing) - half_height

            # Offset every other row for honeycomb pattern
            if row % 2 == 1:
                local_x += x_spacing / 2

            # Check if hexagon would intersect with the face before creating it
            if _hex_would_intersect_face(
                local_x,
                local_y,
                details.hex_side_len,
                face,
                face_center,
                u_vec,
                v_vec,
            ):
                # Generate random height and discretize
                random_height = rng.uniform(
                    details.hex_height_min, details.hex_height_max
                )
                if details.height_steps > 1:
                    step_index = int(
                        (random_height - details.hex_height_min) / height_step_size
                    )
                    step_index = min(step_index, details.height_steps - 1)
                    discretized_height = details.hex_height_min + (
                        step_index * height_step_size
                    )
                else:
                    discretized_height = random_height

                # Convert local 2D coordinates to 3D world coordinates
                world_pos = (
                    face_center + u_vec.multiply(local_x) + v_vec.multiply(local_y)
                )

                if discretized_height not in height_groups:
                    height_groups[discretized_height] = []
                height_groups[discretized_height].append((world_pos, local_x, local_y))

    # Log hexagon generation timing
    _log.debug(
        f"Hexagon generation completed in {generation_timer.elapsed:.2f} seconds"
    )

    return height_groups


def _generate_cache_hash(
    height_groups: dict[float, list[tuple[cq.Vector, float, float]]],
    face: cq.Face,
    details: HoneycombTexture,
    face_center: cq.Vector,
    u_vec: cq.Vector,
    v_vec: cq.Vector,
    show_progress: bool,
) -> str:
    """
    Generate a hash from the function arguments for caching purposes.

    Returns:
        A hexadecimal hash string representing the input arguments
    """
    # Create a string representation of the arguments
    # For complex objects, we'll use their string representation or key attributes
    args_str = ""

    # Hash height_groups by converting to a deterministic string
    height_groups_str = str(sorted(height_groups.items()))
    args_str += f"height_groups:{height_groups_str};"

    # Hash face by its key geometric properties
    # pyright: ignore[reportCallIssue]
    face_str = (
        f"face_normal:{face.normalAt()};"  # pyright: ignore[reportCallIssue]
        f"face_center:{face.Center()};"
        f"face_area:{face.Area()}"
    )
    args_str += f"face:{face_str};"

    # Hash details object by its attributes
    details_str = (
        f"hex_side_len:{details.hex_side_len};"
        f"hex_height_min:{details.hex_height_min};"
        f"hex_height_max:{details.hex_height_max};"
        f"height_steps:{details.height_steps};"
        f"rotation_degrees:{details.rotation_degrees}"
    )
    args_str += f"details:{details_str};"

    # Hash vectors
    args_str += f"face_center:{face_center};u_vec:{u_vec};v_vec:{v_vec};"

    # Hash boolean
    args_str += f"show_progress:{show_progress}"

    # Generate SHA-256 hash
    return "hex-" + hashlib.sha256(args_str.encode()).hexdigest()


def _generate_surface_from_height_groups(
    height_groups: dict[float, list[tuple[cq.Vector, float, float]]],
    face: cq.Face,
    details: HoneycombTexture,
    face_center: cq.Vector,
    u_vec: cq.Vector,
    v_vec: cq.Vector,
    show_progress: bool,
) -> Workplane | None:
    """
    Generate the actual 3D surface from height groups by creating hexagons.

    Returns:
        Workplane containing all the generated hexagons, or None if no hexagons
        were created
    """
    # Generate cache hash from input arguments
    cache_hash = _generate_cache_hash(
        height_groups, face, details, face_center, u_vec, v_vec, show_progress
    )

    # Check if cache file exists
    cache_dir = "./caches"
    cache_file = os.path.join(cache_dir, f"{cache_hash}.brep")

    if os.path.exists(cache_file):
        _log.debug(f"Loading cached result from {cache_file}...")
        try:
            # Load cached Workplane using importBrep
            cached_result = cq.importers.importBrep(cache_file)
            _log.debug(f"Loaded cached result from {cache_file}... done")
            # Convert to our custom Workplane type by creating a new Workplane
            # with the imported object
            return Workplane("XY").newObject([cached_result.val()])
        except Exception as e:
            _log.warning(f"Failed to load cache file {cache_file}: {e}")
            # Continue with normal computation if cache loading fails

    all_hex_shapes = []

    for batch_height, positions in height_groups.items():
        if not positions:
            continue

        if batch_height == 0:
            continue

        # Create workplane aligned with the face
        face_plane_obj = cq.Plane(
            origin=face_center,
            xDir=u_vec,
            normal=face.normalAt(),  # pyright: ignore[reportCallIssue]
        )
        face_plane = Workplane(face_plane_obj)

        # Create all hexagons for this height level with progress bar
        progress_desc = f"Generating hexagons (height={batch_height:.1f})"
        for _, local_x, local_y in tqdm(
            positions, desc=progress_desc, disable=not show_progress
        ):
            try:
                # Create hexagon in the face plane
                hex_shape = (
                    face_plane.moveTo(local_x, local_y)
                    .polygon(6, details.hex_side_len)
                    .extrude(batch_height)  # Extrude along the face normal
                )
                all_hex_shapes.append(hex_shape)
            except Exception as e:
                _log.warning(f"Could not create hexagon at {local_x}, {local_y}: {e}")
                continue

    # Merge all hex shapes using tree-based batching with multi-threading

    _log.debug(
        f"Merging {len(all_hex_shapes)} hexagons using threaded tree-based batching..."
    )

    # Start timing the merge operation
    merge_timer = Stopwatch()
    merge_timer.start()
    result = merge_shapes_in_batches_threaded(
        all_hex_shapes, show_progress=show_progress
    )

    # Log merge timing
    merge_time = merge_timer.elapsed

    _log.debug(f"Merge operation completed in {merge_time:.2f} seconds")

    # Save result to cache
    if result is not None:
        try:
            # Ensure cache directory exists
            os.makedirs(cache_dir, exist_ok=True)

            # Save result to cache file using BREP format
            cq.exporters.export(exportType="BREP", w=result, fname=cache_file)
            _log.debug(f"Cached result saved to {cache_file}")
        except Exception as e:
            _log.warning(f"Failed to save cache file {cache_file}: {e}")

    return result


def _generate_hex_texture_for_face(
    face: cq.Face,
    details: HoneycombTexture,
    show_progress: bool = False,
) -> tuple[Workplane, cq.Vector, cq.Vector] | None:
    """
    Generate hexagonal texture positioned and oriented for a specific face.
    """
    _log.debug("Generating hex texture for face...")
    # Get face center and normal
    face_center = face.Center()
    face_normal = face.normalAt()  # type: ignore

    # Create proper coordinate system for the face
    u_vec, v_vec = _get_face_coordinate_system(face_normal, details)

    # Calculate grid dimensions and spacing
    (
        rows,
        cols,
        x_spacing,
        y_spacing,
        _,
        __,
        half_width,
        half_height,
    ) = _calculate_hex_grid(face, details, u_vec, v_vec)

    # Create height groups by iterating over the grid
    height_groups = _create_height_groups(
        face,
        details,
        rows,
        cols,
        x_spacing,
        y_spacing,
        half_width,
        half_height,
        face_center,
        u_vec,
        v_vec,
    )

    if not height_groups:
        _log.debug("Generating hex texture for face... failed - no height groups.")
        return None

    # Generate the surface from height groups
    result = _generate_surface_from_height_groups(
        height_groups, face, details, face_center, u_vec, v_vec, show_progress
    )

    if result is None:
        _log.debug("Generating hex texture for face... failed.")
        return None
    _log.debug("Generating hex texture for face... done.")
    return result, u_vec, v_vec


if __name__ == "__main__":
    from ocp_vscode import show

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s (%(name)s)",
        datefmt="%H:%M:%S",
    )
    with Stopwatch() as x:
        _log.info("Starting HexTest example")

        result = Workplane("XY").box(150, 150, 25)
        result = (
            result.edges("|Z")
            .fillet(5)
            .faces(">Z")
            .texture(
                HoneycombTexture(hex_side_len=40, hex_height_min=1, hex_height_max=10),
            )
        )

        show(result)
        _log.info(f"HexTest example completed in {x.elapsed:.2f} seconds")
