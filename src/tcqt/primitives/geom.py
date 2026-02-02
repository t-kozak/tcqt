from typing import TYPE_CHECKING

from cadquery import Sketch

if TYPE_CHECKING:
    from .workplane import Workplane


def rrect(
    wp: "Workplane", width: float, height: float, radius: float, center: bool = True
) -> "Workplane":
    """
    Create a rounded rectangle (rectangle with filleted corners).

    Args:
        wp: The workplane to draw on
        width: Width of the rectangle
        height: Height of the rectangle
        radius: Corner radius
        center: If True, center the rectangle at current point. If False, start from bottom-left corner.

    Returns:
        Workplane with the rounded rectangle wire
    """
    # Clamp radius to maximum possible value
    max_radius = min(width, height) / 2
    radius = min(radius, max_radius)

    # Create a Sketch and draw the rectangle
    s = Sketch().rect(width, height)

    # Apply the fillet to all vertices of the sketch
    if radius > 0:
        s = s.vertices().fillet(radius)

    # Handle the positioning
    if not center:
        wp = wp.center(width / 2.0, height / 2.0)

    # Extract the wire from the sketch and add it to the workplane
    # _faces contains the Face objects from the sketch
    sketch_face = s._faces.Faces()[0]  # Get the first (and only) face
    wire = sketch_face.outerWire()  # Get the outer wire of the face

    return wp.eachpoint(lambda loc: wire.moved(loc), combine=False)
