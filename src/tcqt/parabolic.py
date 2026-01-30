from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .workplane import Workplane


def parabolic_channel(
    workplane: "Workplane",
    length=60.0,
    width=40.0,
    side_thickness=10.0,
    top_thickness=10.0,
) -> "Workplane":
    return (
        workplane
        # Top parabola
        .spline([(length / 2, width), (length, 0)], includeCurrent=True)
        # Smooth right bottom leg
        .spline(
            [
                (length - (side_thickness / 2), -(side_thickness / 3)),
                (length - side_thickness, 0),
            ],
            includeCurrent=True,
        )
        # bottom parabola
        .spline(
            [
                (length / 2, width - top_thickness),
                (side_thickness, 0),
            ],
            includeCurrent=True,
        )
        # Smooth left bottom leg
        .spline(
            [(side_thickness / 2, -(side_thickness / 3)), (0, 0)], includeCurrent=True
        )
        # .line(-thickness, 0)
        .close()
    )
