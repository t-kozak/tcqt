import abc
from typing import TYPE_CHECKING

from cadquery import Face, Plane

if TYPE_CHECKING:
    from ..workplane import Workplane


class Texture(abc.ABC):
    @abc.abstractmethod
    def _create_for_face(self, face: Face) -> "Workplane":
        raise NotImplementedError("This should be implemented in subclasses")

    def _create_for_faces(self, faces: list[Face]) -> "Workplane":
        """Create texture geometry for a collection of faces.

        Subclasses that need multi-face coordination (e.g., box continuity)
        should override this method. The default implementation calls
        _create_for_face for each face individually.
        """
        from ..workplane import Workplane

        all_geometry = Workplane()
        for face in faces:
            all_geometry += self._create_for_face(face)
        return all_geometry

    def _wp_for_face(self, face: Face) -> "Workplane":
        """Create a workplane aligned with the face.

        The workplane will be positioned at the face center with its normal
        pointing outward, so that extrusions go in the outward direction.

        Args:
            face: The face to create a workplane for

        Returns:
            A workplane aligned with the face
        """
        center = face.Center()
        normal = face.normalAt()  # type: ignore

        # Create a plane using the face's center and normal
        # This automatically handles any face orientation
        plane = Plane(origin=center, normal=normal)

        # Create workplane from the plane
        from ..workplane import Workplane

        return Workplane(plane)

    def _wire_edge(self, face: Face, height: float, thickness: float) -> "Workplane":
        """Create an inward-facing wall along the face's wire boundary.

        Args:
            face: The face to create the wall for
            height: The height of the wall extrusion
            thickness: The thickness of the wall (inward from the wire)

        Returns:
            A workplane containing the wall geometry
        """
        # Get the outer wire of the face
        outer_wire = face.outerWire()

        # Create workplane aligned with the face
        wp = self._wp_for_face(face)

        # Create the outer boundary by extruding the wire
        outer_solid = wp.add(outer_wire).toPending().extrude(height)

        # Offset the wire inward by the thickness amount
        # Negative offset creates an inward offset
        inner_wire = outer_wire.offset2D(-thickness)

        # Create the inner boundary
        inner_solid = (
            self._wp_for_face(face).add(inner_wire).toPending().extrude(height)
        )

        # Subtract the inner from the outer to create the wall
        return outer_solid.cut(inner_solid)

    def _cut_to_face_boundary(
        self, face: Face, texture: "Workplane", height: float
    ) -> "Workplane":
        """Cut the texture workplane to match the face boundary.

        Args:
            face: The face to cut to
            texture: The texture workplane to cut
            height: The height of the texture extrusion

        Returns:
            The cut texture workplane
        """
        # Get the outer wire of the face and extrude it to create a cutting tool
        outer_wire = face.outerWire()
        cutting_solid = (
            self._wp_for_face(face).add(outer_wire).toPending().extrude(height * 2)
        )

        # Intersect the texture with the face boundary
        return texture.intersect(cutting_solid)
