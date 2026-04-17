import cadquery as cq

from tcqt import Assembly, Workplane
from tcqt.dev_tools import show

box_size = 20
frag_size = box_size / 2

frag = (
    Workplane("XY")
    .box(frag_size, frag_size, frag_size)
    .edges("<X and <Y")
    .fillet(frag_size / 2)
)

blue = cq.Color("blue")
green = cq.Color("green")

ass = Assembly()

combs: list[tuple[tuple[float, float, float], float, cq.Color]] = [
    ((0, 0, 0), 0, blue),
    ((frag_size, 0, 0), 90, green),
    ((0, frag_size, 0), -90, green),
    ((frag_size, frag_size, 0), 180, blue),
    #
    ((0, 0, frag_size), 0, green),
    ((frag_size, 0, frag_size), 90, blue),
    ((0, frag_size, frag_size), -90, blue),
    ((frag_size, frag_size, frag_size), 180, green),
]


for i, config in enumerate(combs):
    ass.add(
        frag.translate(config[0]).rotate_center("Z", config[1]),
        color=config[2],
        name=f"{i}",
        material_id=1 if config[2] == blue else 2,
    )
show(ass)

ass.export(
    "color_cube.3mf",
    filament_palette={1: "#0000FF", 2: "#23BD3C"},
    filament_types={1: "PET", 2: "TPU"},
)
