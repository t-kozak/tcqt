"""Example: additive vs subtractive brick texture on a box.

Left box  -- bricks extruded outward (additive, cut=False, default)
Right box -- mortar grooves cut inward (subtractive, cut=True)
"""

from pathlib import Path

import cadquery as cq

from tcqt import Selectors, Workplane
from tcqt.dev_tools import show
from tcqt.texture import BrickTexture

SPACING = 60  # gap between the two boxes


def main():
    Workplane.build_dir = Path(__file__).parent / "build"

    tex = BrickTexture(brick_width=8.0, brick_height=4.0, spacing=1.0, depth=1.5)

    # additive = Workplane("XY").box(40, 40, 10).faces(">Z").texture(tex)
    # subtractive = Workplane("XY").box(40, 40, 10).faces(">Z").texture(tex, cut=True)

    # # Shift the subtractive box to the right so both are visible side by side
    # subtractive = subtractive.translate((SPACING, 0, 0))

    shell = Workplane("XY").box(60, 60, 30).faces("|Z").shell(-2)
    shell = (
        shell.faces("not |Z")
        .faces(Selectors.outer(shell))
        .texture(tex, cut=True)
        .translate((0, SPACING, 0))
    )

    ass = cq.Assembly()
    # ass.add(additive, name="additive")
    # ass.add(subtractive, name="subtractive")
    ass.add(shell, name="shell")

    show(ass)


if __name__ == "__main__":
    main()
