import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from cadquery import Face, Vector

from .tex_details import Texture

if TYPE_CHECKING:
    from ..workplane import Workplane


@dataclass
class RooftopTileTexture(Texture):
    tile_width: float = 12.0
    tile_height: float = 8.0
    spacing: float = 1.0
    overlap: float = 3.0
    step: float = 0.3
    tilt: float = 4
    row_offset: float | None = None
    depth: float = 2.0

    def __post_init__(self):
        if self.row_offset is None:
            self.row_offset = self.tile_width / 2.0

    @override
    def _create_for_face(self, face: Face) -> "Workplane":
        return self._generate_tiles_for_face(face, x_offset=0.0)

    @override
    def _create_for_faces(self, faces: list[Face]) -> "Workplane":
        from ..workplane import Workplane

        offsets = self._compute_box_offsets(faces)

        all_geometry = Workplane()
        for i, face in enumerate(faces):
            x_off = offsets.get(id(face), 0.0)
            all_geometry += self._generate_tiles_for_face(
                face, x_offset=x_off + i * self.tile_width * 0.4
            )
        return all_geometry

    def _generate_tiles_for_face(
        self, face: Face, x_offset: float = 0.0
    ) -> "Workplane":
        from ..workplane import Workplane

        bbox = face.BoundingBox()
        diagonal = math.sqrt(bbox.xlen**2 + bbox.ylen**2)

        col_pitch = self.tile_width + self.spacing
        row_pitch = self.tile_height - self.overlap

        col_count = int(math.ceil(2 * diagonal / col_pitch)) + 2
        row_count = int(math.ceil(2 * diagonal / row_pitch)) + 2

        wplane = self._wp_for_face(face)

        # Determine which direction along the row axis is "downhill"
        # by projecting gravity (0, 0, -1) onto the workplane's local X axis.
        # Rows with lower i are in the negative-X direction.
        x_dir = wplane.plane.xDir
        gravity_along_x = -x_dir.z
        step_sign = 1 if gravity_along_x > 0 else -1

        half_rows = row_count // 2
        # Pull tiles inward to compensate for the tilt lifting the eaves edge.
        tilt_offset = math.sin(math.radians(self.tilt)) * self.tile_height / 2
        result = Workplane()

        for i in range(row_count):
            row_y = (i - half_rows) * row_pitch
            stagger = (self.row_offset or 0.0) if i % 2 == 1 else 0.0
            z_lift = step_sign * (half_rows - i) * self.step - (
                tilt_offset * (1 + (i * 0.07))
            )

            # Tilt each tile around the ridge-parallel axis (local Y) so that
            # the eaves edge lifts away from the roof, making the tile less steep.
            tile_tilt = -step_sign * self.tilt

            row = (
                wplane.transformed(
                    offset=(row_y, x_offset + stagger, z_lift),
                    rotate=(0, tile_tilt, 0),
                )
                .rarray(1, col_pitch, 1, col_count)
                .rect(self.tile_height, self.tile_width)
                .extrude(self.depth)
            )
            result = result.union(row)

        # Cutting boundary must extend in both directions from the face to
        # capture tiles with both positive and negative z_lift values.
        max_lift = half_rows * self.step
        outer_wire = face.outerWire()
        cutting_solid = (
            self._wp_for_face(face)
            .transformed(offset=(0, 0, -max_lift))
            .add(outer_wire)
            .toPending()
            .extrude(self.depth + 2 * max_lift)
        )
        return result.intersect(cutting_solid)

    # --- Box continuity helpers ---

    def _compute_box_offsets(self, faces: list[Face]) -> dict[int, float]:
        """Detect box-like face groups and compute per-face x offsets
        so the tile pattern wraps continuously around the box."""
        axes = [Vector(1, 0, 0), Vector(0, 1, 0), Vector(0, 0, 1)]
        col_pitch = self.tile_width + self.spacing

        offsets: dict[int, float] = {}

        for axis in axes:
            group = [
                f
                for f in faces
                if abs(f.normalAt().dot(axis)) < 0.01  # type: ignore[arg-type]
            ]
            if len(group) < 3:
                continue

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

                normal = face.normalAt()  # type: ignore[call-arg]
                tangent = axis.cross(normal)  # type: ignore[arg-type]
                t_len = math.sqrt(tangent.x**2 + tangent.y**2 + tangent.z**2)
                if t_len < 1e-9:
                    continue
                tangent = Vector(
                    tangent.x / t_len, tangent.y / t_len, tangent.z / t_len
                )

                verts = face.outerWire().Vertices()
                projections = [
                    v.Center().x * tangent.x
                    + v.Center().y * tangent.y
                    + v.Center().z * tangent.z
                    for v in verts
                ]
                face_width = max(projections) - min(projections)
                cumulative += face_width

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
