import random
import time

import cadquery as cq

from tcqt import Workplane, cached_workplane
from tcqt.dev_tools import show


@cached_workplane
def heavy_build(delay: float) -> Workplane:
    time.sleep(delay)
    return Workplane("XY").box(10, 12, 13)


def main():
    rnd_delay = int(random.random() * 1000) / 100
    print(f"First pass, should be slow ({rnd_delay:.2f}) delay")
    itm = heavy_build(rnd_delay)
    print("2nd pass, should be fast")
    itm2 = heavy_build(rnd_delay)
    print("Done")

    ass = cq.Assembly()
    ass.add(itm)
    ass.add(itm2, loc=cq.Location((10, 10, 0)))
    show(ass)


if __name__ == "__main__":
    main()
