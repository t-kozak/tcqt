import math
from typing import List, Sequence

from cadquery.selectors import Selector


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
