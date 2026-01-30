import logging
import math
from dataclasses import dataclass
from typing import override

from cadquery import Face

from ..workplane import Workplane
from .tex_details import Texture

_log = logging.getLogger(__name__)


@dataclass
class HexGridTexture(Texture):
    hex_diameter: float
    hex_height: float
    side_thickness: float

    edge_width: float | None = None

    @override
    def _create_for_face(self, face: Face) -> Workplane:
        # --- 1. CALCULATION ---
        d = self.hex_diameter
        h = self.hex_height

        # The flat-to-flat width of a hexagon is d * sqrt(3)/2
        flat_width = d * math.sqrt(3) / 2

        # Spacing for the rectangular arrays
        # We need large gaps in the individual arrays so the second array can fit in
        # between
        x_spacing = d * 1.5
        y_spacing = flat_width

        # --- 2. POSITIONING ---
        # Get the boundary to determine where to start
        face_b_box = face.BoundingBox()

        # Grid counts (ensure enough coverage)
        xc = int(face_b_box.xlen / self.hex_diameter) - 1
        yc = int(face_b_box.ylen / self.hex_diameter) + 3

        # --- 3. GENERATION ---

        # Hexagon Grid A (Base)
        hex1 = (
            self._wp_for_face(face)
            .rarray(xSpacing=x_spacing, ySpacing=y_spacing, xCount=xc, yCount=yc)
            .polygon(6, d)
            .extrude(h)
        )
        # Holes Grid A (Matches Hex 1 position)
        holes1 = (
            self._wp_for_face(face)
            .rarray(xSpacing=x_spacing, ySpacing=y_spacing, xCount=xc, yCount=yc)
            .polygon(6, d - self.side_thickness)
            .extrude(h)
        )

        t_vec = (x_spacing / 2, y_spacing / 2, 0)
        # Hexagon Grid B (Offset)
        hex2 = (
            self._wp_for_face(face)
            .transformed(offset=t_vec)
            .rarray(xSpacing=x_spacing, ySpacing=y_spacing, xCount=xc, yCount=yc)
            .polygon(6, d)
            .extrude(h)
        )

        # Holes Grid B (Matches Hex 2 position)
        holes2 = (
            self._wp_for_face(face)
            .transformed(offset=t_vec)
            .rarray(xSpacing=x_spacing, ySpacing=y_spacing, xCount=xc, yCount=yc)
            .polygon(6, d - self.side_thickness)
            .extrude(h)
        )

        # --- 4. BOOLEAN OPERATIONS ---

        texture = (hex1 - holes1) + (hex2 - holes2)
        texture = self._cut_to_face_boundary(face, texture, self.hex_height)

        if self.edge_width is not None:
            texture += self._wire_edge(face, self.hex_height, self.edge_width)
        return texture
