import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from cadquery import Face, Vector

from .tex_details import Texture

if TYPE_CHECKING:
    from ..workplane import Workplane


@dataclass
class BrickTexture(Texture):
    brick_width: float = 10.0
    brick_height: float = 5.0
    spacing: float = 1.0
    row_offset: float | None = None
    depth: float = 1.0

    def __post_init__(self):
        if self.row_offset is None:
            self.row_offset = self.brick_width / 2.0

    @override
    def _create_for_face(self, face: Face) -> "Workplane":
        return self._generate_bricks_for_face(face, x_offset=0.0)

    @override
    def _create_for_faces(self, faces: list[Face]) -> "Workplane":
        from ..workplane import Workplane

        offsets = self._compute_box_offsets(faces)

        all_geometry = Workplane()
        for face in faces:
            x_off = offsets.get(id(face), 0.0)
            all_geometry += self._generate_bricks_for_face(face, x_offset=x_off)
        return all_geometry

    def _generate_bricks_for_face(
        self, face: Face, x_offset: float = 0.0
    ) -> "Workplane":
        bbox = face.BoundingBox()
        diagonal = math.sqrt(bbox.xlen**2 + bbox.ylen**2)

        col_pitch = self.brick_width + self.spacing
        row_pitch = self.brick_height + self.spacing

        col_count = int(math.ceil(2 * diagonal / col_pitch)) + 2
        row_count = int(math.ceil(2 * diagonal / row_pitch)) + 2
        # Ensure even so we split evenly between even/odd passes
        if row_count % 2 != 0:
            row_count += 1
        half_rows = row_count // 2

        wplane = self._wp_for_face(face)

        # Pass 1: even rows
        even = (
            wplane.transformed(offset=(0, x_offset, 0))
            .rarray(row_pitch * 2, col_pitch, half_rows, col_count)
            .rect(self.brick_height, self.brick_width)
            .extrude(self.depth)
        )

        # Pass 2: odd rows, shifted by row_offset along columns and one row_pitch along rows
        odd = (
            wplane.transformed(offset=(row_pitch, x_offset + self.row_offset, 0))
            .rarray(row_pitch * 2, col_pitch, half_rows, col_count)
            .rect(self.brick_height, self.brick_width)
            .extrude(self.depth)
        )

        result = even.union(odd)
        return self._cut_to_face_boundary(face, result, self.depth)

    # --- Box continuity helpers ---

    def _compute_box_offsets(self, faces: list[Face]) -> dict[int, float]:
        """Detect box-like face groups and compute per-face x offsets
        so the brick pattern wraps continuously around the box."""
        axes = [Vector(1, 0, 0), Vector(0, 1, 0), Vector(0, 0, 1)]
        col_pitch = self.brick_width + self.spacing

        offsets: dict[int, float] = {}

        for axis in axes:
            group = [
                f
                for f in faces
                if abs(f.normalAt().dot(axis)) < 0.01  # type: ignore[arg-type]
            ]
            if len(group) < 3:
                continue

            # Build perpendicular basis for angle sorting
            ref1, ref2 = _perpendicular_basis(axis)

            def _face_angle(face: Face) -> float:
                c = face.Center()
                p1 = c.x * ref1.x + c.y * ref1.y + c.z * ref1.z
                p2 = c.x * ref2.x + c.y * ref2.y + c.z * ref2.z
                return math.atan2(p2, p1)

            sorted_group = sorted(group, key=_face_angle)

            cumulative = 0.0
            for face in sorted_group:
                offsets[id(face)] = cumulative % col_pitch

                # Tangential width: extent of face along common_axis x face_normal
                normal = face.normalAt()
                tangent = axis.cross(normal)  # type: ignore[arg-type]
                t_len = math.sqrt(tangent.x**2 + tangent.y**2 + tangent.z**2)
                if t_len < 1e-9:
                    continue
                tangent = Vector(tangent.x / t_len, tangent.y / t_len, tangent.z / t_len)

                verts = face.outerWire().Vertices()
                projections = [
                    v.Center().x * tangent.x
                    + v.Center().y * tangent.y
                    + v.Center().z * tangent.z
                    for v in verts
                ]
                face_width = max(projections) - min(projections)
                cumulative += face_width

            # Remove these faces from further axis checks
            faces = [f for f in faces if f not in group]

        return offsets


def _perpendicular_basis(axis: Vector) -> tuple[Vector, Vector]:
    """Return two orthonormal vectors perpendicular to the given axis."""
    candidates = [Vector(1, 0, 0), Vector(0, 1, 0), Vector(0, 0, 1)]
    for ref in candidates:
        cross = axis.cross(ref)
        mag = math.sqrt(cross.x**2 + cross.y**2 + cross.z**2)
        if mag > 1e-6:
            v1 = Vector(cross.x / mag, cross.y / mag, cross.z / mag)
            v2_raw = axis.cross(v1)
            v2_mag = math.sqrt(v2_raw.x**2 + v2_raw.y**2 + v2_raw.z**2)
            v2 = Vector(v2_raw.x / v2_mag, v2_raw.y / v2_mag, v2_raw.z / v2_mag)
            return v1, v2
    raise ValueError("Could not find perpendicular basis")
