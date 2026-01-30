import logging
import math
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Literal,
    Optional,
    Self,
    Union,
    cast,
    override,
)

import cadquery as cq

from . import align, parabolic, teardrop

__all__ = ["align"]

_log = logging.getLogger(__name__)


if TYPE_CHECKING:
    from .texture import Texture


class Workplane(cq.Workplane):
    auto_clean: bool = True
    build_dir: str | Path | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def teardrop(
        self, radius: float = 1, rotate: float = 0, clip: float | None = None
    ) -> Self:
        return cast(Self, teardrop.teardrop(self, radius, rotate, clip))

    def texture(self, details: "Texture", cache_key: str | None = None) -> Self:
        # Import here to avoid circular import
        from .texture import add_texture

        return cast(Self, add_texture(self, details, cache_key))

    def polar_move_to(self, phi: float, r: float, relative: bool = False) -> Self:
        # Convert polar coordinates to Cartesian
        x = r * math.cos(phi)
        y = r * math.sin(phi)

        if relative:
            # Get current position and add the calculated offset
            val = self.val()
            assert isinstance(val, cq.Vector)
            current_pos = val
            x += current_pos.x
            y += current_pos.y

        # Delegate to base class moveTo method
        return cast(Self, self.moveTo(x, y))

    def parabolic_channel(
        self,
        length=60.0,
        width=40.0,
        side_thickness=10.0,
        top_thickness=10.0,
    ) -> Self:
        return cast(
            Self,
            parabolic.parabolic_channel(
                self,
                length,
                width,
                side_thickness,
                top_thickness,
            ),
        )

    def get_center(self) -> cq.Vector:
        val = self.val()
        if isinstance(val, cq.Vector):
            return val
        elif isinstance(val, cq.Shape):
            return val.BoundingBox().center
        else:
            raise ValueError(f"Invalid type: {type(val)}")

    def get_bbox(self) -> cq.BoundBox:
        val = self.val()
        if isinstance(val, cq.Shape):
            return val.BoundingBox()
        else:
            raise ValueError(f"Invalid type: {type(val)}")

    def rotate_center(self, axis: Literal["X", "Y", "Z"], angle: float) -> Self:
        center = self.get_center()
        if axis == "X":
            start_vector = (center.x, center.y, center.z)
            end_vector = (center.x + 1, center.y, center.z)
        elif axis == "Y":
            start_vector = (center.x, center.y, center.z)
            end_vector = (center.x, center.y + 1, center.z)
        elif axis == "Z":
            start_vector = (center.x, center.y, center.z)
            end_vector = (center.x, center.y, center.z + 1)
        return self.rotate(start_vector, end_vector, angle)

    @override
    def cut(
        self,
        toCut: Union["cq.Workplane", cq.Solid, cq.Compound],
        clean: bool = True,
        tol: Optional[float] = None,
    ) -> Self:
        clean = clean and self.auto_clean
        _log.debug(f"cutting. clean? {clean}")
        return cast(Self, super().cut(toCut, clean, tol))

    def intersect(
        self,
        toIntersect: Union["cq.Workplane", cq.Solid, cq.Compound],
        clean: bool = True,
        tol: Optional[float] = None,
    ) -> Self:
        clean = clean and self.auto_clean
        return super().intersect(toIntersect, clean, tol)

    def union(
        self,
        toUnion: Optional[Union["cq.Workplane", cq.Solid, cq.Compound]] = None,
        clean: bool = True,
        glue: bool = False,
        tol: Optional[float] = None,
    ) -> Self:
        clean = clean and self.auto_clean

        return super().union(toUnion, clean, glue, tol)

    def export(
        self,
        fname: str | Path,
        tolerance: float = 0.1,
        angularTolerance: float = 0.1,
        opt: Optional[Dict[str, Any]] = None,
    ) -> Self:
        fname = Path(fname)
        if self.build_dir is not None:
            if isinstance(self.build_dir, str):
                self.build_dir = Path(self.build_dir)
            fname = self.build_dir / fname
        fname.parent.mkdir(parents=True, exist_ok=True)
        fname = str(fname)
        return super().export(fname, tolerance, angularTolerance, opt)

    def rrect(self, width: float, height: float, radius: float, center: bool = True):
        from geom import rrect

        return rrect(self, width, height, radius, center)

    def move_center_to(self, loc: tuple[float, ...]) -> Self:
        from .transforms.align import move_center_to

        return cast(Self, move_center_to(self, loc))

    def aligned(
        self,
        other: Self,
        alignment: tuple[align.Alignment, align.Alignment, align.Alignment],
    ) -> Self:
        return cast(Self, align.align_to(self, other, alignment))
