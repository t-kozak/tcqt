"""
Bambu Studio-compatible 3mf exporter for CadQuery assemblies.

Each leaf of the assembly (i.e. each call to ``Assembly.add(shape, ...)``)
becomes a "part" inside a single Bambu Studio object. Parts share perimeters,
infill, and walls at slice time -- the slicer treats the whole thing as one
fused solid with per-part filament assignments. That makes this format a good
fit for multi-material prints where volumes share boundaries, e.g. a wheel
with a PETG hub and a TPU tire.

The ``material_id`` on each leaf maps to a Bambu filament slot (1-indexed).
The user picks the actual filament (color + material type) at slice time in
Bambu Studio; this exporter only declares the slot assignments.

Usage
-----
    from export_bambu_3mf import export_bambu_3mf

    wheel = Assembly(name="wheel")
    wheel.add(hub_solid,  name="hub",  material_id=1)
    wheel.add(tire_solid, name="tire", material_id=2)

    export_bambu_3mf(
        wheel,
        "wheel.3mf",
        filament_palette={1: "#1A1A1A", 2: "#1A1A1A"},
        filament_types={1: "PETG",     2: "TPU"},
    )
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from xml.sax.saxutils import escape as _xml_escape
from xml.sax.saxutils import quoteattr as _xml_attr

import cadquery as cq

# --- package-level boilerplate --------------------------------------------

_CONTENT_TYPES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="png" ContentType="image/png"/>
</Types>
"""

_RELS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""

# 3mf <component transform> / <item transform> -- 12 floats, column-major 3x4.
_IDENTITY_12 = "1 0 0 0 1 0 0 0 1 0 0 0"
# Bambu model_settings.config "matrix" metadata -- 16 floats, row-major 4x4.
_IDENTITY_16 = "1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"


# --- internal data structures ---------------------------------------------


@dataclass
class _Leaf:
    name: str
    vertices: list  # [(x, y, z), ...]
    triangles: list  # [(v1, v2, v3), ...]
    material_id: int
    color: cq.Color | None = None


# --- shape / traversal helpers --------------------------------------------


def _get_shape(obj: Any) -> cq.Shape | None:
    """Coerce a Workplane/Shape/None into a single Shape (or None)."""
    if obj is None:
        return None
    if isinstance(obj, cq.Shape):
        return obj
    if isinstance(obj, cq.Workplane):
        shapes = [v for v in obj.vals() if isinstance(v, cq.Shape)]
        if not shapes:
            return None
        if len(shapes) == 1:
            return shapes[0]
        return cq.Compound.makeCompound(shapes)
    return None


def _walk(
    node: cq.Assembly,
    parent_loc: cq.Location,
    parent_mid: int | None,
    parent_color: cq.Color | None,
) -> Iterable[tuple[str, cq.Shape, cq.Location, int | None, cq.Color | None]]:
    """Depth-first walk, yielding (name, shape, world_loc, mid, color) per leaf.

    Inherits ``material_id`` and ``color`` from the nearest ancestor that
    defines them, and accumulates the world-space location by composing each
    node's local ``loc`` onto its parent's world transform.
    """
    effective_loc = parent_loc * (node.loc or cq.Location())
    metadata = node.metadata or {}
    effective_mid = metadata.get("material_id", parent_mid)
    effective_color = node.color if node.color is not None else parent_color

    shape = _get_shape(node.obj)
    if shape is not None:
        yield node.name or "part", shape, effective_loc, effective_mid, effective_color

    for child in node.children:
        yield from _walk(child, effective_loc, effective_mid, effective_color)


def _uniquify(names: list[str]) -> list[str]:
    """Disambiguate duplicate names with -2, -3, ... suffixes."""
    seen: dict[str, int] = {}
    out: list[str] = []
    for n in names:
        if n in seen:
            seen[n] += 1
            out.append(f"{n}-{seen[n]}")
        else:
            seen[n] = 1
            out.append(n)
    return out


# --- color helpers --------------------------------------------------------


def _color_to_hex(color: cq.Color | None) -> str | None:
    if color is None:
        return None
    r, g, b, _a = color.toTuple()
    return "#{:02X}{:02X}{:02X}".format(
        int(round(r * 255)), int(round(g * 255)), int(round(b * 255))
    )


def _normalise_hex(h: str) -> str:
    return h if h.startswith("#") else f"#{h}"


def _build_palette(
    leaves: list[_Leaf],
    explicit_palette: dict[int, str] | None,
    max_slot: int,
) -> list[str]:
    """Resolve per-slot hex colours. Explicit palette wins over leaf colours;
    unspecified slots default to white."""
    palette: dict[int, str] = {}
    for leaf in leaves:
        if leaf.material_id in palette:
            continue
        h = _color_to_hex(leaf.color)
        if h is not None:
            palette[leaf.material_id] = h
    if explicit_palette:
        for k, v in explicit_palette.items():
            palette[k] = _normalise_hex(v)
    return [palette.get(i, "#FFFFFF") for i in range(1, max_slot + 1)]


# --- XML building ---------------------------------------------------------


def _fmt_f(v: float) -> str:
    # 9 significant digits is comfortably below float32 precision loss and
    # avoids scientific notation for typical model coordinates.
    return f"{v:.9g}"


def _build_model_xml(
    leaves: list[_Leaf], wrapper_id: int, unit: str, title: str | None
) -> str:
    parts: list[str] = []
    w = parts.append

    w('<?xml version="1.0" encoding="UTF-8"?>\n')
    w(
        f'<model unit="{unit}" xml:lang="en-US" '
        f'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
        f'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">\n'
    )
    if title:
        w(f' <metadata name="Title">{_xml_escape(title)}</metadata>\n')
    w(' <metadata name="Application">cadquery-bambu-export</metadata>\n')
    w(' <metadata name="BambuStudio:3mfVersion">1</metadata>\n')
    w(" <resources>\n")

    # One <object> per leaf, containing its mesh.
    for i, leaf in enumerate(leaves, start=1):
        w(f'  <object id="{i}" type="model">\n')
        w("   <mesh>\n")
        w("    <vertices>\n")
        w(
            "".join(
                f'     <vertex x="{_fmt_f(x)}" y="{_fmt_f(y)}" z="{_fmt_f(z)}"/>\n'
                for x, y, z in leaf.vertices
            )
        )
        w("    </vertices>\n")
        w("    <triangles>\n")
        w(
            "".join(
                f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>\n'
                for a, b, c in leaf.triangles
            )
        )
        w("    </triangles>\n")
        w("   </mesh>\n")
        w("  </object>\n")

    # Wrapper object that aggregates the leaf-objects as components.
    # Bambu Studio treats this as "one model, N parts".
    w(f'  <object id="{wrapper_id}" type="model">\n')
    w("   <components>\n")
    for i in range(1, len(leaves) + 1):
        w(f'    <component objectid="{i}" transform="{_IDENTITY_12}"/>\n')
    w("   </components>\n")
    w("  </object>\n")

    w(" </resources>\n")
    w(" <build>\n")
    w(f'  <item objectid="{wrapper_id}" transform="{_IDENTITY_12}"/>\n')
    w(" </build>\n")
    w("</model>\n")
    return "".join(parts)


def _build_model_settings_xml(
    leaves: list[_Leaf],
    wrapper_id: int,
    wrapper_name: str,
    default_material_id: int,
) -> str:
    """Emit Metadata/model_settings.config -- Bambu's per-part extruder map.

    Part ids must match the object ids used in 3dmodel.model's wrapper
    <components>.
    """
    out: list[str] = ['<?xml version="1.0" encoding="UTF-8"?>\n<config>\n']
    out.append(f' <object id="{wrapper_id}">\n')
    out.append(f'  <metadata key="name" value={_xml_attr(wrapper_name)}/>\n')
    out.append(f'  <metadata key="extruder" value="{default_material_id}"/>\n')
    for i, leaf in enumerate(leaves, start=1):
        out.append(f'  <part id="{i}" subtype="normal_part">\n')
        out.append(f'   <metadata key="name" value={_xml_attr(leaf.name)}/>\n')
        out.append(f'   <metadata key="matrix" value="{_IDENTITY_16}"/>\n')
        out.append(f'   <metadata key="extruder" value="{leaf.material_id}"/>\n')
        out.append("  </part>\n")
    out.append(" </object>\n</config>\n")
    return "".join(out)


def _build_project_settings_json(
    filament_colours: list[str],
    filament_types: list[str] | None,
) -> str:
    """Minimal project_settings.config -- just enough to colour the slot previews."""
    settings: dict[str, Any] = {
        "filament_colour": filament_colours,
        "nozzle_diameter": ["0.4"],
    }
    if filament_types is not None:
        settings["filament_type"] = filament_types
    return json.dumps(settings, indent=4)


# --- public entrypoint ----------------------------------------------------


def export_bambu_3mf(
    assembly: Any,
    path: str | Path,
    *,
    tolerance: float = 0.1,
    angular_tolerance: float = 0.1,
    default_material_id: int = 1,
    filament_palette: dict[int, str] | None = None,
    filament_types: dict[int, str] | None = None,
    unit: str = "millimeter",
    title: str | None = None,
) -> Path:
    """
    Export a CadQuery assembly as a Bambu Studio-compatible 3mf file.

    The assembly is serialised as a single Bambu model object containing one
    "part" per leaf. Each part is assigned to a filament slot via the leaf's
    ``metadata["material_id"]`` (inherited from subassemblies if not set on
    the leaf itself). Because Bambu Studio unions the parts per-layer at
    slice time, the result prints as one fused solid with per-part filament
    changes -- ideal for multi-material designs like a PETG-hub / TPU-tire
    wheel.

    Parameters
    ----------
    assembly
        An ``Assembly`` wrapper (with an ``._assy`` attribute) or a plain
        ``cq.Assembly``.
    path
        Output ``.3mf`` path.
    tolerance, angular_tolerance
        Passed to ``Shape.tessellate``. Tighter values → larger files.
    default_material_id
        Filament slot used for leaves (and the wrapper fallback) that have
        no ``material_id`` set anywhere in their ancestor chain.
    filament_palette
        Optional ``{slot: "#RRGGBB"}`` map used to populate
        ``filament_colour`` in ``project_settings.config``. If omitted, the
        first ``cq.Color`` seen on a leaf for each slot is used; unused
        slots default to white. This only affects what Bambu Studio shows
        as the slot colour before the user loads a real filament.
    filament_types
        Optional ``{slot: "PETG"}`` / ``{slot: "TPU"}`` map. If provided,
        populates ``filament_type`` in project_settings.config for the
        slicer preview. Bambu still lets the user pick the real filament at
        slice time.
    unit
        3mf unit; default ``"millimeter"``.
    title
        Optional model title. Defaults to the assembly's name, then to the
        output filename stem.

    Returns
    -------
    pathlib.Path
        The written path.
    """
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Accept either the user's Assembly wrapper or a bare cq.Assembly.
    cq_assy: cq.Assembly = getattr(assembly, "_assy", assembly)
    if not isinstance(cq_assy, cq.Assembly):
        raise TypeError(
            "Expected an Assembly wrapper with ._assy or a cq.Assembly, "
            f"got {type(assembly).__name__}"
        )

    # 1. Walk the tree, inheriting material_id / color / transform.
    raw = list(_walk(cq_assy, cq.Location(), None, None))
    if not raw:
        raise ValueError("Assembly is empty -- nothing to export.")

    # 2. Tessellate each leaf in world coordinates. Baking the world transform
    #    into the vertices keeps the 3mf component transforms at identity,
    #    which means we never have to worry about row-major vs column-major
    #    matrix conventions between the two files that reference each part.
    leaves: list[_Leaf] = []
    for name, shape, world_loc, mid, color in raw:
        positioned = shape.moved(world_loc)
        verts, tris = positioned.tessellate(tolerance, angular_tolerance)
        if not verts or not tris:
            continue
        leaves.append(
            _Leaf(
                name=name,
                vertices=[(v.x, v.y, v.z) for v in verts],
                triangles=[tuple(t) for t in tris],
                material_id=mid if mid is not None else default_material_id,
                color=color,
            )
        )
    if not leaves:
        raise ValueError("Tessellation produced no triangles -- nothing to export.")

    # 3. Make part names unique -- they become Bambu's part labels.
    for leaf, n in zip(leaves, _uniquify([leaf.name for leaf in leaves])):
        leaf.name = n

    # 4. Assign object ids. Leaves are 1..N, wrapper is N+1.
    wrapper_id = len(leaves) + 1

    # 5. Resolve palette / filament types.
    max_slot = max(leaf.material_id for leaf in leaves)
    max_slot = max(max_slot, default_material_id)
    if filament_palette:
        max_slot = max(max_slot, max(filament_palette.keys()))
    if filament_types:
        max_slot = max(max_slot, max(filament_types.keys()))
    colours = _build_palette(leaves, filament_palette, max_slot)
    types = (
        [filament_types.get(i, "PLA") for i in range(1, max_slot + 1)]
        if filament_types is not None
        else None
    )

    # 6. Serialise the three files that matter.
    wrapper_name = title or cq_assy.name or out_path.stem
    model_xml = _build_model_xml(leaves, wrapper_id, unit, title)
    settings_xml = _build_model_settings_xml(
        leaves, wrapper_id, wrapper_name, default_material_id
    )
    project_json = _build_project_settings_json(colours, types)

    # 7. Package.
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES_XML)
        zf.writestr("_rels/.rels", _RELS_XML)
        zf.writestr("3D/3dmodel.model", model_xml)
        zf.writestr("Metadata/model_settings.config", settings_xml)
        zf.writestr("Metadata/project_settings.config", project_json)

    return out_path
