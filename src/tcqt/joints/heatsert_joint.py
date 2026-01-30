from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, override

import cadquery as cq

from ..screws import Screw
from ..washers import Washer
from .joint import Joint, JointFaceSelector

if TYPE_CHECKING:
    from ..workplane import Workplane

_VERSION = "0.1"


@dataclass
class HeatsertJoint(Joint):
    screw: Screw
    boss_height: float  # Height of screw boss (clearance for shaft, stops head)

    heatsert_length: Literal["4", "6", "8", "10"] | float

    washer: Washer | None = None

    def __post_init(self):
        assert self.screw.length > 0, "Got a screw of 0 length"

    @override
    def apply_female(
        self,
        workplane: "Workplane",
        face: JointFaceSelector,
        offset: tuple[float, float] = (0, 0),
        guide_hole_depth: float = 1.0,
    ) -> "Workplane":
        """
        Create the female part of a screw joint (contains heatsert and remaining shaft).

        The female part has:
        - A hole for the heatsert
        - A guide hole (1mm deep, slightly larger diameter) for easier heatsert
          insertion
        - A hole for the remaining screw shaft

        Args:
            wp: "Workplane" to cut holes into
            config: Configuration describing the screw joint
            face: Face selector indicating screw insertion direction (e.g., "Z>" means
                  top to bottom)
            offset: XY offset from origin for hole placement
            guide_hole_clearance: Additional clearance for the guide hole beyond
                  heatsert diameter
            guide_hole_depth: Depth of the guide hole (default 1mm)

        Returns:
            "Workplane" with the cut geometry to subtract from the female part
        """

        # 1. Calculate all dimensions
        # ========================================================
        axis, is_positive, workplane_str = _parse_face_selector(face)
        bbox = workplane.get_bbox()
        if is_positive:
            if axis == "X":
                base_workplane_offset = bbox.xmax
            elif axis == "Y":
                base_workplane_offset = bbox.ymax
            elif axis == "Z":
                base_workplane_offset = bbox.zmax
            else:
                raise ValueError(f"invalid face selector: {face}")
        else:
            if axis == "X":
                base_workplane_offset = bbox.xmin
            elif axis == "Y":
                base_workplane_offset = bbox.ymin
            elif axis == "Z":
                base_workplane_offset = bbox.zmin
            else:
                raise ValueError(f"invalid face selector: {face}")

        washer_thickness = self.washer.thickness if self.washer else 0.0
        remaining_shaft_length = (
            float(self.screw.length) - self.boss_height - washer_thickness
        )
        if remaining_shaft_length < 0:
            raise ValueError(
                f"Not enough space for heatsert. {remaining_shaft_length = }"
            )
        # Extend it by some % for safety
        remaining_shaft_length *= 1.05

        # ensure it's float - handler Literals
        heatsert_length = float(self.heatsert_length) + guide_hole_depth
        print(f"{remaining_shaft_length = }")

        # 2. Create the workplanes
        # ========================================================
        from ..workplane import Workplane

        cut_wp = Workplane(workplane_str).workplane(base_workplane_offset)
        shaft_hole = cut_wp.workplane(-remaining_shaft_length if is_positive else 0)
        heatsert_hole = cut_wp.workplane(-heatsert_length if is_positive else 0)
        guide_hole = cut_wp.workplane(-guide_hole_depth if is_positive else 0)

        # 3. Create the three holes
        # ========================================================

        if remaining_shaft_length > 0:
            shaft_hole = (
                shaft_hole.moveTo(*offset)
                .circle(self.screw.shaft_hole_radius)
                .extrude(remaining_shaft_length)
            )

        heatsert_hole = (
            heatsert_hole.moveTo(*offset)
            .circle(self.screw.heatsert_radius)
            .extrude(float(self.heatsert_length))
        )

        guide_hole = (
            guide_hole.moveTo(*offset)
            .circle(self.screw.heatsert_guide_radius)
            .extrude(guide_hole_depth)
        )

        # Merge and return.
        all = heatsert_hole + guide_hole + shaft_hole
        return workplane - all

    def apply_male(
        self,
        workplane: "Workplane",
        face: JointFaceSelector,
        offset: tuple[float, float] = (0, 0),
    ) -> "Workplane":
        axis, is_positive, workplane_str = _parse_face_selector(face)

        # Get the bounding box to determine the full height

        val = workplane.val()
        if isinstance(val, cq.Shape):
            bbox = val.BoundingBox()
        else:
            # If no shape yet, use the workplane's objects
            bbox = workplane.findSolid().BoundingBox()

        workplane_offset = 0
        if axis == "X":
            total_height = bbox.xlen
            workplane_offset = bbox.xmin
        elif axis == "Y":
            total_height = bbox.ylen
            workplane_offset = bbox.ymin
        elif axis == "Z":
            total_height = bbox.zlen
            workplane_offset = bbox.zmin
        else:
            raise ValueError(f"invalid face selector: {face}")

        print(f"{is_positive =}")

        # Create a new workplane on the appropriate plane
        from ..workplane import Workplane

        cut_wp = Workplane(workplane_str)

        # Shaft hole (goes through entire body)

        shaft_hole = (
            cut_wp.workplane(workplane_offset)
            .moveTo(offset[0], offset[1])
            .circle(self.screw.shaft_hole_radius)
            .extrude(total_height)
        )

        # Optional washer
        washer_outer_d = self.washer.outer_diameter if self.washer else 0.0

        # Head hole (offset by boss height in the appropriate direction)
        head_radius = max(
            self.screw.head_hole_radius,
            washer_outer_d,
        )
        head_height = total_height - self.boss_height

        head_offset = workplane_offset
        head_offset += self.boss_height if is_positive else 0
        head_hole = (
            cut_wp.workplane(head_offset)
            .moveTo(offset[0], offset[1])
            .circle(head_radius)
            .extrude(head_height)
        )

        return workplane - shaft_hole - head_hole


def _parse_face_selector(face: JointFaceSelector) -> tuple[str, bool, str]:
    """
    Parse face selector to extract axis, direction, and workplane.

    Args:
        face: Face selector like "Z>", "X<", etc.

    Returns:
        Tuple of (axis, is_positive_direction, workplane)
        - axis: "X", "Y", or "Z"
        - is_positive_direction: True for ">", False for "<"
        - workplane: The plane to draw circles on (e.g., "XY" for Z axis)
    """
    axis = face[0]
    direction = face[1]
    is_positive = direction == ">"

    # Determine the workplane based on the axis
    if axis == "X":
        workplane = "YZ"
    elif axis == "Y":
        workplane = "XZ"
    elif axis == "Z":
        workplane = "XY"
    else:
        raise ValueError(f"Got invalid face selector: {face}")

    return axis, is_positive, workplane
