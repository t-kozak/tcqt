from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

MetricWasherType = Literal["normal", "large"]

if TYPE_CHECKING:
    from .screws import MetricScrewSize


@dataclass
class Washer:
    inner_diameter: float
    outer_diameter: float
    thickness: float

    @staticmethod
    def metric(
        screw_size: "MetricScrewSize", washer_type: MetricWasherType = "normal"
    ) -> "Washer":
        """
        Create a metric washer according to ISO 7089 (normal) or
        ISO 7090 (large) standards.

        Args:
            screw_size: The metric screw size
                (M1.6, M2, M2.5, M3, M4, M5, M6, M8, M10)
            washer_type: The washer type - "normal" (ISO 7089) or
                "large" (ISO 7090)

        Returns:
            MetricWasher with dimensions according to the ISO standards

        Raises:
            ValueError: If the combination of screw_size and washer_type
                is not available

        Note:
            - ISO 7089 (normal) covers sizes M1.6 through M64
            - ISO 7090 (large) only covers sizes M5 through M64
            - For sizes M1.6-M4, only "normal" type is available
        """
        # ISO 7089 - Normal series flat washers (Form A)
        # Dimensions: (inner_diameter, outer_diameter, thickness)
        iso_7089_dimensions = {
            "M1.6": (1.7, 4.0, 0.3),
            "M2": (2.2, 5.0, 0.3),
            "M2.5": (2.7, 6.0, 0.5),
            "M3": (3.2, 7.0, 0.5),
            "M4": (4.3, 9.0, 0.8),
            "M5": (5.3, 10.0, 1.0),
            "M6": (6.4, 12.0, 1.6),
            "M8": (8.4, 16.0, 1.6),
            "M10": (10.5, 20.0, 2.0),
        }

        # ISO 7090 - Large series flat washers (Form B, chamfered)
        # Only available from M5 upwards
        # Dimensions: (inner_diameter, outer_diameter, thickness)
        iso_7090_dimensions = {
            "M5": (5.3, 12.5, 1.0),
            "M6": (6.4, 15.0, 1.6),
            "M8": (8.4, 24.0, 1.6),
            "M10": (10.5, 30.0, 2.5),
        }

        if washer_type == "normal":
            if screw_size not in iso_7089_dimensions:
                raise ValueError(
                    f"ISO 7089 normal washer not available for size {screw_size}"
                )
            inner_d, outer_d, thickness = iso_7089_dimensions[screw_size]
        elif washer_type == "large":
            if screw_size not in iso_7090_dimensions:
                raise ValueError(
                    f"ISO 7090 large washer not available for size {screw_size}. "
                    f"Large washers are only available for M5 and above."
                )
            inner_d, outer_d, thickness = iso_7090_dimensions[screw_size]
        else:
            raise ValueError(f"Invalid washer type: {washer_type}")

        return Washer(
            inner_diameter=inner_d,
            outer_diameter=outer_d,
            thickness=thickness,
        )
