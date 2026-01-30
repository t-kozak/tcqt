import cadquery as cq

_ocp_show = None

try:
    from cadquery.vis import show as ocp_show

    _ocp_show = ocp_show
except ImportError:
    pass


def show(itm: cq.Workplane | cq.Assembly, show_coords: bool = False):
    if show_coords:
        show_with_coords(itm)

    else:
        if _ocp_show:
            _ocp_show(itm)


def show_with_coords(itm: cq.Workplane | cq.Assembly):
    origin_pt = cq.Workplane().sphere(2)

    x_axis = cq.Workplane("YZ").circle(1).extrude(10)
    y_axis = cq.Workplane("XZ").circle(1).extrude(10)
    z_axis = cq.Workplane("XY").circle(1).extrude(10)

    assem = cq.Assembly()
    assem.add(
        origin_pt,
        name="origin",
        color=cq.Color("white"),
        loc=cq.Location((-0.5, -0.5, -0.5)),
    )
    assem.add(
        x_axis,
        name="x_axis",
        color=cq.Color("red"),
        loc=cq.Location((-0.5, -0.5, -0.5)),
    )
    assem.add(
        y_axis,
        name="y_axis",
        color=cq.Color("green"),
        loc=cq.Location((-0.5, -0.5, -0.5)),
    )
    assem.add(
        z_axis,
        name="z_axis",
        color=cq.Color("blue"),
        loc=cq.Location((-0.5, -0.5, -0.5)),
    )
    assem.add(itm)
    show(assem)


try:
    from tqdm import tqdm  # pyright: ignore[reportAssignmentType]
except ImportError:
    # Fallback if tqdm is not available
    def tqdm(iterable, desc=None, total=None, disable=False):
        if disable:
            return iterable
        print(f"{desc}: Starting...")
        return iterable


assert tqdm is not None
