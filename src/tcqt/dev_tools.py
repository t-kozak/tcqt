import cadquery as cq

from tcqt.assembly.assembly import Assembly

_ocp_show = None

try:
    from ocp_vscode import show as ocp_show

    _ocp_show = ocp_show
except ImportError:
    from cadquery.vis import show as ocp_show

    _ocp_show = ocp_show


def show(itm: cq.Workplane | cq.Assembly | cq.Solid | Assembly):
    try:
        from ocp_vscode import show as ocp_show

        ocp_show(itm)
        return
    except Exception:
        pass

    from cadquery.vis import show as vis_show

    vis_show(itm)


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
