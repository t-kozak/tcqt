from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Screw:
    """Immutable dataclass representing a metric screw with all its properties."""

    thread_pitch: float
    shaft_diameter: tuple[float, float]  # (min, max)
    shaft_hole_radius: float
    head_diameter: tuple[float, float]  # (min, max)
    head_hole_radius: float
    head_height: tuple[float, float]  # (min, max)
    chamfer_radius: float
    hex_socket_size: float
    spline_socket_size: float
    key_engagement: float
    transition_dia: tuple[float, float]  # (min, max)
    heatsert_radius: float
    heatsert_guide_radius: float
    length: float = -1.0  # Optional screw shaft length

    def copy_with(self, length: float | None = None) -> "Screw":
        """Create a new Screw instance with the specified length.

        Args:
            length: The length of the screw shaft in mm

        Returns:
            A new Screw instance with all the same properties but with the specified length

        Example:
            >>> screw = MScrewType.M3.with_length(12.0)
        """
        from dataclasses import replace

        return replace(self, length=self.length if length is None else length)


MetricScrewSize = Literal[
    # "M1.6",
    "M2",
    # "M2.5",
    "M3",
    "M4",
    # "M5",
    # "M6",
    # "M8",
]


class MetricScrews:
    """Metric screw types as static class attributes."""

    M2 = Screw(
        thread_pitch=0.4,
        shaft_diameter=(1.86, 2.00),
        shaft_hole_radius=2.4 / 2,
        head_diameter=(3.65, 3.80),
        head_hole_radius=4.6 / 2,
        head_height=(1.91, 2.00),
        chamfer_radius=0.20,
        hex_socket_size=1.5,
        spline_socket_size=1.829,
        key_engagement=1.00,
        transition_dia=(2.6, 2.6),
        heatsert_radius=3.1 / 2,
        heatsert_guide_radius=3.7 / 2,
    )

    M3 = Screw(
        thread_pitch=0.5,
        shaft_diameter=(2.86, 3.00),
        head_diameter=(5.32, 5.50),
        head_hole_radius=6.1 / 2,
        shaft_hole_radius=3.6 / 2,
        head_height=(2.89, 3.00),
        chamfer_radius=0.30,
        hex_socket_size=2.5,
        spline_socket_size=2.819,
        key_engagement=1.50,
        transition_dia=(3.6, 3.6),
        heatsert_radius=4.0 / 2,
        heatsert_guide_radius=5.2 / 2,
    )

    M4 = Screw(
        thread_pitch=0.7,
        shaft_diameter=(3.82, 4.00),
        head_diameter=(6.80, 7.00),
        head_hole_radius=7.7 / 2,
        shaft_hole_radius=4.6 / 2,
        head_height=(3.88, 4.00),
        chamfer_radius=0.40,
        hex_socket_size=3.0,
        spline_socket_size=3.378,
        key_engagement=2.00,
        transition_dia=(4.7, 4.7),
        heatsert_radius=4.8 / 2,
        heatsert_guide_radius=6.1 / 2,
    )

    # M5 = Screw(
    #     thread_pitch=0.8,
    #     shaft_diameter=(4.82, 5.00),
    #     shaft_hole_radius=5.20 / 2,
    #     head_diameter=(8.27, 8.50),
    #     head_hole_radius=8.7 / 2,
    #     head_height=(4.86, 5.00),
    #     chamfer_radius=0.50,
    #     hex_socket_size=4.0,
    #     spline_socket_size=4.648,
    #     key_engagement=2.50,
    #     transition_dia=(5.7, 5.7),
    #     heatsert_radius=5.8 / 2,
    #     heatsert_guide_radius=6.8 / 2,
    # )

    # M6 = Screw(
    #     thread_pitch=1.0,
    #     shaft_diameter=(5.82, 6.00),
    #     shaft_hole_radius=6.20 / 2,
    #     head_diameter=(9.74, 10.00),
    #     head_hole_radius=10.5 / 2,
    #     head_height=(5.85, 6.00),
    #     chamfer_radius=0.60,
    #     hex_socket_size=5.0,
    #     spline_socket_size=5.486,
    #     key_engagement=3.00,
    #     transition_dia=(6.8, 6.8),
    #     heatsert_radius=8.0 / 2,
    #     heatsert_guide_radius=8.3,
    # )

    # M8 = Screw(
    #     thread_pitch=1.25,
    #     shaft_diameter=(7.78, 8.00),
    #     shaft_hole_radius=8.20 / 2,
    #     head_diameter=(12.70, 13.00),
    #     head_hole_radius=13.5 / 2,
    #     head_height=(7.83, 8.00),
    #     chamfer_radius=0.80,
    #     hex_socket_size=6.0,
    #     spline_socket_size=7.391,
    #     key_engagement=4.00,
    #     transition_dia=(9.2, 9.2),
    #     heatsert_radius=9.6 / 2,
    #     heatsert_guide_radius=10,
    # )

    _size_mapping = {
        "M2": M2,
        "M3": M3,
        "M4": M4,
        # "M5": M5,
        # "M6": M6,
        # "M8": M8,
    }

    @classmethod
    def by_size(cls, size: MetricScrewSize) -> Screw:
        return cls._size_mapping[size]
