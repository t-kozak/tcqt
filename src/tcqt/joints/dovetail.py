import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import cadquery as cq
from cadquery.occ_impl.geom import Vector
from cadquery.occ_impl.shapes import Edge, Wire

if TYPE_CHECKING:
    from ..workplane import Workplane


@dataclass
class DovetailJointConfig:
    # With of the widest part of the key
    key_width: float

    # Depth of the key
    key_depth: float

    # Clearance between the key and the keyway. It will be applied to the keyway (so key way will
    # be a bit bigger than the key)
    clearance: float = 0.1

    # Angle of the key (in degrees)
    angle: float = 45.0

    # Amount of keys
    amount: int = 1

    # Spacing between the keys
    spacing: float = 10.0

    # Center the keys around the origin
    center: bool = True


def create_dovetail_key(
    workplane: "Workplane", cfg: DovetailJointConfig
) -> "Workplane":
    # Geometry parameters
    half_base_width = cfg.key_width / 2.0
    taper_offset = cfg.key_depth * math.tan(math.radians(cfg.angle))
    inner_width = max(0.0, cfg.key_width - 2.0 * taper_offset)
    half_inner_width = inner_width / 2.0

    # Trapezoid points (XY plane): base at y=0, inner at y=key_depth
    pts = [
        Vector(-half_base_width, 0, 0),
        Vector(half_base_width, 0, 0),
        Vector(half_inner_width, cfg.key_depth, 0),
        Vector(-half_inner_width, cfg.key_depth, 0),
    ]

    # Build closed wire
    edges = [Edge.makeLine(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
    wire = Wire.assembleEdges(edges)

    # Create array of wires based on amount and spacing (centered around origin)
    pitch = cfg.key_width + cfg.spacing
    start_index = -(cfg.amount - 1) / 2.0
    wires = []
    for i in range(cfg.amount):
        x_offset = (start_index + i) * pitch
        wires.append(wire.moved(cq.Location(Vector(x_offset, 0, 0))))

    return workplane.newObject(wires)


def create_dovetail_keyway(
    workplane: "Workplane", cfg: DovetailJointConfig
) -> "Workplane":
    # Apply clearance to the keyway: enlarge widths and depth
    half_base_width = (cfg.key_width + 2.0 * cfg.clearance) / 2.0
    depth = cfg.key_depth + cfg.clearance
    taper_offset = depth * math.tan(math.radians(cfg.angle))
    inner_width = max(0.0, (cfg.key_width - 2.0 * taper_offset) + 2.0 * cfg.clearance)
    half_inner_width = inner_width / 2.0

    pts = [
        Vector(-half_base_width, 0, 0),
        Vector(half_base_width, 0, 0),
        Vector(half_inner_width, depth, 0),
        Vector(-half_inner_width, depth, 0),
    ]

    edges = [Edge.makeLine(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
    wire = Wire.assembleEdges(edges)

    pitch = (cfg.key_width + 2.0 * cfg.clearance) + cfg.spacing
    start_index = -(cfg.amount - 1) / 2.0
    wires = []
    for i in range(cfg.amount):
        x_offset = (start_index + i) * pitch
        wires.append(wire.moved(cq.Location(Vector(x_offset, 0, 0))))

    return workplane.newObject(wires)
