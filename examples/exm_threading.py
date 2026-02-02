"""Example: creating male and female ISO threads with tcqt.

Run with:  pth examples/exm_threading.py
"""

import cadquery as cq

from tcqt.dev_tools import show
from tcqt.primitives.thread import IsoThread

# --- Thread parameters (M3) ---
MAJOR_DIAMETER = 3.0  # nominal thread diameter
PITCH = 0.5  # axial distance between crests
LENGTH = 8.0  # total threaded section length


def main():
    # External (male/bolt) thread
    male_thread = IsoThread(
        major_diameter=MAJOR_DIAMETER,
        pitch=PITCH,
        length=LENGTH,
        external=True,
        end_finishes=("fade", "square"),
    )

    # Combine thread ridges with a core cylinder to form the bolt
    male = (
        cq.Workplane("XY").circle(male_thread.min_radius).extrude(LENGTH)
    ) + male_thread

    # Internal (female/nut) thread
    female_thread = cq.Workplane("XY").circle(male_thread.min_radius).extrude(
        LENGTH
    ) + IsoThread(
        major_diameter=MAJOR_DIAMETER,
        pitch=PITCH,
        length=LENGTH,
        external=False,
        end_finishes=("square", "square"),
    )

    # Demo: create a threaded hole by cutting a bore and adding internal ridges
    block = cq.Workplane("XY").box(6, 6, LENGTH, centered=(True, True, False))
    threaded_block = block - female_thread

    ass = cq.Assembly()
    ass.add(male, name="male_thread", color=cq.Color("steelblue"))
    ass.add(
        threaded_block,
        name="threaded_block",
        loc=cq.Location((10, 0, 0)),
        color=cq.Color("goldenrod"),
    )
    show(ass)


if __name__ == "__main__":
    main()
