from cadquery import Assembly

from tcqt.dev_tools import show
from tcqt.threads import ThreadSpec, make_thread
from tcqt.workplane import Workplane


def main():
    core_radius = 3
    apex_radius = core_radius + 1
    thread_len = 10
    spec = ThreadSpec(thread_len, core_radius, apex_radius, 1, 0.2, 1)
    internal = make_thread(spec=spec, external=False, method="sweep").rotate_center(
        "Z", 180
    )
    external = make_thread(spec=spec, external=True, method="sweep")

    ass = Assembly()
    # ass.add(external.rotate_center("Z", 180), color=Color("blue"))

    screw_core = (
        Workplane("XY")
        .cylinder(12, 3)
        .aligned(
            internal,
            (
                "center",
                "center",
                "end",
            ),
        )
    )
    screw = screw_core + external
    cut = Workplane("XY").box(1, 50, 5).aligned(screw, ("center", "center", "end"))
    ass.add(screw - cut, name="screw")
    pipe = Workplane("XY").cylinder(20, apex_radius).faces("|Z").shell(1) + internal
    ass.add(pipe, name="pipe")
    # screw.toCompound().export("screw.stl")
    show(ass)


if __name__ == "__main__":
    main()
