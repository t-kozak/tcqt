import math
from dataclasses import dataclass
from typing import Literal

import cadquery as cq
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections  # type: ignore

from tcqt import Workplane


@dataclass
class ThreadSpec:
    length: float
    root_radius: float
    apex_radius: float
    base_width: float
    edge_width: float
    pitch: float
    fade_in_turns: float = 0.0
    fade_out_turns: float = 0.0


ConstructionMethod = Literal["sweep"]


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------


def make_thread(
    spec: ThreadSpec,
    external: bool = True,
    method: ConstructionMethod = "sweep",
) -> Workplane:
    """
    Create a thread solid by sweeping a trapezoidal profile along a helix.

    Two construction methods are available:

    ``"loft"`` (default)
        Lofts between discrete trapezoidal cross-sections placed along the
        helix.  Produces faceted geometry that OCCT's boolean engine
        handles reliably — the result can be freely unioned, cut,
        translated, etc.  Supports fade-in / fade-out.  ``sections_per_turn``
        controls smoothness (default 24 ≈ 15° per facet).

    ``"sweep"``
        Sweeps a single trapezoid along a true analytic helix using Frenet
        framing.  Produces smooth, compact geometry but OCCT boolean
        operations (union / cut) on the result are **unreliable** — they
        may silently lose geometry or raise exceptions.  Best used when the
        thread will live in a sub-assembly and never be booleaned.
        Fade-in / fade-out and ``sections_per_turn`` are ignored.

    The thread profile is a trapezoid:
        - height  = abs(apex_radius − root_radius)
        - base    = base_width   (at root for external, at apex for internal)
        - top     = edge_width   (the other end)

    For an external thread the base (wider side) faces inward toward the
    axis; for an internal thread the base faces outward.

    Args:
        spec:              Thread geometry.
        external:          True → external (bolt), False → internal (nut).
        method:            ``"loft"`` or ``"sweep"``.
        sections_per_turn: (loft only) Cross-sections per revolution.
        fade_in_turns:     (loft only) Turns over which the profile ramps
                           from zero to full size at the start.
        fade_out_turns:    (loft only) Same, at the end.

    Returns:
        cq.Workplane containing a single thread solid.
    """
    if method == "sweep":
        return _make_thread_sweep(spec, external)
    else:
        raise ValueError(f"Unknown construction method: {method!r}")


# -----------------------------------------------------------------------
# Sweep implementation  (smooth but boolean-fragile)
# -----------------------------------------------------------------------


def _make_thread_profile(spec: ThreadSpec, external: bool) -> Workplane:
    """Create the trapezoidal thread profile positioned at the helix start."""
    s = spec
    thread_height = abs(s.apex_radius - s.root_radius)
    half_base = s.base_width / 2.0
    half_edge = s.edge_width / 2.0

    helix_radius = s.root_radius if external else s.apex_radius

    # Tangent to the helix at the start point, used as the profile plane normal
    tangent_y = helix_radius
    tangent_z = s.pitch / (2.0 * math.pi)
    tangent_len = math.sqrt(tangent_y**2 + tangent_z**2)

    start_point = cq.Vector(helix_radius, 0, 0)
    tangent_dir = cq.Vector(0, tangent_y / tangent_len, tangent_z / tangent_len)

    # External threads grow outward from root; internal threads grow inward from apex
    radial_dir = cq.Vector(1, 0, 0) if external else cq.Vector(-1, 0, 0)

    profile_plane = cq.Plane(
        origin=start_point,
        xDir=radial_dir,
        normal=tangent_dir,
    )

    # Trapezoid: base_width at the helix surface, edge_width at the tip
    return (
        Workplane(profile_plane)
        .moveTo(0, -half_base)
        .lineTo(0, half_base)
        .lineTo(thread_height, half_edge)
        .lineTo(thread_height, -half_edge)
        .close()
    )


def _make_thread_helix(spec: ThreadSpec, external: bool) -> Workplane:
    """Create the helical sweep path along the thread axis."""
    helix_radius = spec.root_radius if external else spec.apex_radius

    helix_wire = cq.Wire.makeHelix(
        pitch=spec.pitch,
        height=spec.length,
        radius=helix_radius,
    )
    return Workplane("XY").add(helix_wire)


def _make_thread_sweep(spec: ThreadSpec, external: bool) -> Workplane:
    """Sweep the thread profile along the helix to produce the thread solid."""
    profile = _make_thread_profile(spec, external)
    helix = _make_thread_helix(spec, external)
    return profile.sweep(helix, isFrenet=True)


# -----------------------------------------------------------------------
# Loft implementation  (faceted but boolean-friendly)
# TODO - this one doesn't work - the internal and external threads don't align
# it's slow
# -----------------------------------------------------------------------


def _make_thread_loft(
    spec: ThreadSpec,
    external: bool,
    sections_per_turn: int,
    fade_in_turns: float,
    fade_out_turns: float,
) -> Workplane:

    s = spec
    thread_height = abs(s.apex_radius - s.root_radius)
    n_turns = s.length / s.pitch
    n_sections = int(n_turns * sections_per_turn) + 1

    half_base = s.base_width / 2.0
    half_edge = s.edge_width / 2.0

    if external:
        helix_r = s.root_radius
        inner_hw = half_base
        outer_hw = half_edge
        radial_sign = 1.0
    else:
        helix_r = s.apex_radius
        inner_hw = half_base
        outer_hw = half_edge
        radial_sign = -1.0

    dz_dtheta = s.pitch / (2.0 * math.pi)

    def _fade_factor(turns_elapsed: float) -> float:
        t = 1.0
        if fade_in_turns > 0.0 and turns_elapsed < fade_in_turns:
            t = min(t, turns_elapsed / fade_in_turns)
        if fade_out_turns > 0.0 and turns_elapsed > n_turns - fade_out_turns:
            t = min(t, (n_turns - turns_elapsed) / fade_out_turns)
        return max(t, 0.0)

    def _section_wire(theta: float, z: float, scale: float) -> cq.Wire:
        ct, st = math.cos(theta), math.sin(theta)
        rx, ry = ct, st

        tx_raw = -helix_r * st
        ty_raw = helix_r * ct
        tz_raw = dz_dtheta
        t_len = math.sqrt(tx_raw**2 + ty_raw**2 + tz_raw**2)
        tx, ty, tz = tx_raw / t_len, ty_raw / t_len, tz_raw / t_len

        bx = ty * 0.0 - tz * ry
        by = tz * rx - tx * 0.0
        bz = tx * ry - ty * rx

        cx = helix_r * ct
        cy = helix_r * st
        cz = z

        s_inner_hw = inner_hw * scale
        s_outer_hw = outer_hw * scale
        dr = radial_sign * thread_height * scale

        pts = [
            cq.Vector(cx + bx * s_inner_hw, cy + by * s_inner_hw, cz + bz * s_inner_hw),
            cq.Vector(cx - bx * s_inner_hw, cy - by * s_inner_hw, cz - bz * s_inner_hw),
            cq.Vector(
                cx - bx * s_outer_hw + rx * dr,
                cy - by * s_outer_hw + ry * dr,
                cz - bz * s_outer_hw,
            ),
            cq.Vector(
                cx + bx * s_outer_hw + rx * dr,
                cy + by * s_outer_hw + ry * dr,
                cz + bz * s_outer_hw,
            ),
        ]
        return cq.Wire.makePolygon(pts, close=True)

    loft = BRepOffsetAPI_ThruSections(True, True)
    for i in range(n_sections):
        turns_elapsed = i / sections_per_turn
        theta = 2.0 * math.pi * turns_elapsed
        z = turns_elapsed * s.pitch
        scale = _fade_factor(turns_elapsed)
        if scale < 1e-6:
            continue
        loft.AddWire(_section_wire(theta, z, scale).wrapped)

    loft.Build()
    if not loft.IsDone():
        raise RuntimeError("Thread loft failed -- check ThreadSpec values")

    solid = cq.Solid(loft.Shape())
    if not solid.isValid():
        raise RuntimeError("Thread loft produced invalid solid")

    return Workplane("XY").newObject([solid])
