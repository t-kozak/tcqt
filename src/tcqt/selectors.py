import math
from typing import TYPE_CHECKING, List, Sequence

import cadquery as cq
from cadquery.selectors import Selector

if TYPE_CHECKING:
    from .workplane import Workplane


class OuterFaceSelector(Selector):
    def __init__(self, wp: "Workplane"):
        bb = wp.get_bbox()
        self.center = cq.Vector(
            (bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2, (bb.zmin + bb.zmax) / 2
        )

    def filter(self, objectList):
        outer = []
        for face in objectList:
            fc = face.Center()
            normal = face.normalAt(fc)
            to_center = self.center - fc
            if normal.dot(to_center) < 0:
                outer.append(face)
        return outer


class FacesAtAngleSelector(Selector):
    """
    Select faces at a specific angle from the XY plane

    Args:
        target_angle: Target angle in degrees from XY plane (0-90)
                     0° = parallel to XY, 90° = perpendicular to XY
        tolerance: Acceptable deviation in degrees (default: 5)
    """

    def __init__(self, target_angle: float, tolerance: float = 5.0):
        self.target_angle = target_angle
        self.tolerance = tolerance

    def filter(self, objectList: Sequence) -> List:
        """
        Filter faces based on their angle from the XY plane
        """
        result = []

        for obj in objectList:
            # Only process Face objects
            if hasattr(obj, "normalAt"):
                # Get the face's normal vector
                normal = obj.normalAt()

                # Calculate angle from XY plane
                # Angle from Z axis
                angle_from_z = math.degrees(math.acos(abs(normal.z)))
                # Convert to angle from XY plane
                angle_from_xy = 90 - angle_from_z

                # Check if within tolerance
                if abs(angle_from_xy - self.target_angle) <= self.tolerance:
                    result.append(obj)

        return result


class Selectors:
    @staticmethod
    def faces_at_angle(angle: float, tolerance: float = 5.0) -> Selector:
        return FacesAtAngleSelector(angle, tolerance)

    @staticmethod
    def outer(wp: Workplane) -> Selector:
        return OuterFaceSelector(wp)
