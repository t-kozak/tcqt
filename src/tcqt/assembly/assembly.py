from __future__ import annotations

from dataclasses import dataclass, field
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

_MATERIAL_TOKEN = object()


@dataclass(frozen=True)
class Material:
    id: int
    color: str
    type: str
    _token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self._token is not _MATERIAL_TOKEN:
            raise TypeError(
                "_Material cannot be instantiated directly; use Assembly.add_material()"
            )


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
        self._materials: list[Material] = []

    def add_material(self, colour: str, filament_type: str = "PLA") -> Material:
        """Register a filament and return a handle for use with add().

        colour: str
            Hex color string in 'RRGGBB' or 'RRGGBBAA' format (optional '#').
        filament_type: str
            Filament type label shown in Bambu Studio (e.g. "PLA", "PETG", "TPU").
        """
        mat = Material(
            id=len(self._materials) + 1,
            color=colour,
            type=filament_type,
            _token=_MATERIAL_TOKEN,
        )
        self._materials.append(mat)
        return mat

    def add(
        self,
        arg: Shape | Workplane | Assembly | cq.Assembly,
        name: str | None = None,
        color: Color | str | None = None,
        loc: Location | None = None,
        material: Material | None = None,
    ) -> "Assembly":
        """
        Add a shape or sub-assembly.

        color: Color | str | None
            Color for this part. Accepts a Color instance or a hex string in
            'RRGGBB' or 'RRGGBBAA' format (optional leading '#').

        material: _Material | None
            Filament to assign this part, obtained from add_material(). Parts
            sharing the same material are grouped into the same filament slot.
            None defaults to slot 1 at export time.
            If arg is a sub-Assembly, the material is inherited by all its leaf
            parts that do not have their own explicit material.
        """
        cq_arg = arg._assy if isinstance(arg, Assembly) else arg
        if color is None and material is not None:
            color = material.color
        self._assy.add(cq_arg, name=name, color=_parse_color(color), loc=loc)
        if material is not None:
            self._assy.children[-1].metadata["material_id"] = material.id
        return self

    def export(
        self,
        path: str,
        exportType: ExportLiterals | None = None,
        mode: STEPExportModeLiterals = "default",
        tolerance: float = 0.1,
        angularTolerance: float = 0.1,
        default_material_id: int = 1,
        unit: str = "millimeter",
        title: str | None = None,
    ) -> "Assembly":
        """
        Save assembly to a file.

        If exportType is "3mf", or exportType is None and path ends with
        ".3mf", the Bambu-compatible exporter is used automatically.
        All other export types are delegated to cq.Assembly.export() unchanged.

        Filament palette and types are built automatically from materials
        registered via add_material().
        """
        use_bambu = exportType == "3mf" or (
            exportType is None and path.lower().endswith(".3mf")
        )
        if use_bambu:
            filament_palette = {m.id: m.color for m in self._materials} or None
            filament_types = {m.id: m.type for m in self._materials} or None
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
