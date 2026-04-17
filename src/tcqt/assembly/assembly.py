from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, cast

import cadquery as cq
from cadquery import Color, Location, Shape, Workplane
from cadquery.assembly import ExportLiterals as CQExportLiterals
from cadquery.occ_impl.exporters.assembly import STEPExportModeLiterals

from .export_bambu_3mf import export_bambu_3mf


def _parse_color(color: Color | str | None) -> Color | None:
    """Return a Color instance from a Color, hex string, or None.

    Accepted hex formats (case-insensitive, optional leading '#'):
      - "RRGGBB"   — opaque RGB
      - "RRGGBBAA" — RGB with alpha
    """
    if color is None or isinstance(color, Color):
        return color
    raw = color.lstrip("#")
    if len(raw) == 6:
        r, g, b = (int(raw[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
        return Color(r, g, b)
    if len(raw) == 8:
        r, g, b, a = (int(raw[i : i + 2], 16) / 255.0 for i in (0, 2, 4, 6))
        return Color(r, g, b, a)
    raise ValueError(
        f"Invalid hex color {color!r}: expected 'RRGGBB' or 'RRGGBBAA'"
        " (with optional '#')"
    )


ExportLiterals = Literal[
    "STEP", "XML", "XBF", "VRML", "GLTF", "GLB", "VTKJS", "STL", "3mf"
]


class Assembly:
    def __init__(
        self,
        obj=None,
        loc: Location | None = None,
        name: str | None = None,
        color: Color | None = None,
        material=None,
        metadata: dict[str, Any] | None = None,
    ):
        self._assy = cq.Assembly(
            obj=obj,
            loc=loc,
            name=name,
            color=color,
            material=material,
            metadata=metadata,
        )

    def add(
        self,
        arg: Shape | Workplane | Assembly | cq.Assembly,
        name: str | None = None,
        color: Color | str | None = None,
        loc: Location | None = None,
        material_id: int | None = None,
    ) -> "Assembly":
        """
        Add a shape or sub-assembly.

        color: Color | str | None
            Color for this part. Accepts a Color instance or a hex string in
            'RRGGBB' or 'RRGGBBAA' format (optional leading '#').

        material_id: int | None
            Filament slot number (1-indexed) to assign this part in Bambu Studio.
            Parts sharing the same material_id are grouped into the same filament
            slot. None defaults to slot 1 at export time.
            If arg is a sub-Assembly, material_id is inherited by all its leaf
            parts that do not have their own explicit material_id.
        """
        cq_arg = arg._assy if isinstance(arg, Assembly) else arg
        self._assy.add(cq_arg, name=name, color=_parse_color(color), loc=loc)
        if material_id is not None:
            self._assy.children[-1].metadata["material_id"] = material_id
        return self

    def export(
        self,
        path: str,
        exportType: ExportLiterals | None = None,
        mode: STEPExportModeLiterals = "default",
        tolerance: float = 0.1,
        angularTolerance: float = 0.1,
        default_material_id: int = 1,
        filament_palette: dict[int, str] | None = None,
        filament_types: dict[int, str] | None = None,
        unit: str = "millimeter",
        title: str | None = None,
    ) -> "Assembly":
        """
        Save assembly to a file.

        If exportType is "3mf", or exportType is None and path ends with
        ".3mf", the Bambu-compatible exporter is used automatically.
        All other export types are delegated to cq.Assembly.export() unchanged.

        single_object: bool
            3mf only. When True (default), wraps all parts in a single
            top-level assembly object so Bambu Studio imports without a
            dialog. When False, each part is an independent build item.

        Extra kwargs for 3mf export: linear_deflection, angular_deflection.
        """
        use_bambu = exportType == "3mf" or (
            exportType is None and path.lower().endswith(".3mf")
        )
        if use_bambu:
            export_bambu_3mf(
                self._assy,
                Path(path),
                tolerance=tolerance,
                angular_tolerance=angularTolerance,
                default_material_id=default_material_id,
                filament_palette=filament_palette,
                filament_types=filament_types,
                unit=unit,
                title=title,
            )
        else:
            self._assy.export(
                path,
                exportType=cast(CQExportLiterals | None, exportType),
                mode=mode,
                tolerance=tolerance,
                angularTolerance=angularTolerance,
            )
        return self
