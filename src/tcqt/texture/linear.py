import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cadquery import Face

from .tex_details import Texture

if TYPE_CHECKING:
    from ..workplane import Workplane


@dataclass
class LinearTexture(Texture):
    thickness: float = 1.0
    spacing: float = 3.0
    angle_deg: float = 45.0
    height: float = 3.0

    def _create_for_face(self, face: Face) -> "Workplane":
        bbox = face.BoundingBox()

        # Calculate the diagonal length needed to cover the rotated bounding box
        # For any angle, the diagonal of the bounding box is the max coverage needed
        diagonal = math.sqrt(bbox.xlen**2 + bbox.ylen**2)
        length = diagonal * 2

        # Calculate how many lines are needed to cover the perpendicular dimension
        # The perpendicular coverage distance is also the diagonal
        count = int(math.ceil(diagonal / self.spacing)) + 1
        count *= 2

        print(f"Generating with: {count = }; {length = }")
        wplane = self._wp_for_face(face)

        # First rotate the workplane, then create the pattern
        # This ensures the pattern is created in the rotated orientation
        wplane = wplane.transformed(rotate=(0, 0, self.angle_deg))

        wplane = (
            wplane.rarray(self.spacing, ySpacing=self.spacing, xCount=1, yCount=count)
            .rect(length, self.thickness)
            .extrude(self.height)
        )

        # Cut the texture to the face boundary
        wplane = self._cut_to_face_boundary(face, wplane, self.height)

        return wplane
