"""Example: rooftop tiles on a 45-degree gable roof."""

from pathlib import Path

from tcqt import Selectors, Workplane
from tcqt.dev_tools import show
from tcqt.texture import RooftopTileTexture

WALL_W = 60
WALL_D = 80
WALL_H = 40
ROOF_OVERHANG = 5
ROOF_THICKNESS = 2


def main():
    Workplane.build_dir = Path(__file__).parent / "build"
    # --- walls (simple box) ---
    walls = Workplane("XY").box(WALL_W, WALL_D, WALL_H)

    # --- gable roof ---
    # The ridge height equals half the wall width for a 45-degree slope.
    ridge_h = WALL_W / 2

    # Triangle profile in XZ, extruded along Y
    half_w = WALL_W / 2 + ROOF_OVERHANG
    roof = (
        Workplane("XZ")
        .moveTo(-half_w, 0)
        .lineTo(0, ridge_h)
        .lineTo(half_w, 0)
        .close()
        .extrude(WALL_D + 2 * ROOF_OVERHANG, both=True)
        # Hollow out to leave just the shell
        # .faces(">Z")
        # .shell(-ROOF_THICKNESS)
    )

    # Move roof so its base sits on top of the walls
    roof = roof.translate((0, 0, WALL_H / 2))

    # --- apply tile texture to the two sloped faces ---
    texture = RooftopTileTexture(
        tile_width=50.0,
        tile_height=15.0,
        spacing=0.8,
    )

    textured_roof = roof.faces(Selectors.faces_at_angle(45)).texture(texture)
    textured_roof.export("root.step")
    show(textured_roof)

    # --- assemble ---
    # assembly = cq.Assembly()
    # assembly.add(walls, color=cq.Color("gray"))
    # assembly.add(textured_roof, color=cq.Color("firebrick"))
    # show(assembly)


if __name__ == "__main__":
    main()
