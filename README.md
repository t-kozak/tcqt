# tcqt - Ted's CadQuery Tools

A collection of utilities for [CadQuery](https://cadquery.readthedocs.io/) covering part components, missing geometries, and development tools.

All functionality is exposed through a `Workplane` subclass of `cadquery.Workplane` -- no monkey patching, full type-checking support.

## Features

### Part Components

- **Joints** -- parametric dovetail (keys + keyways) and heatsert screw joints with an abstract `Joint` base for custom implementations
- **Screws** -- metric screw specs (M2, M3, M4) as frozen dataclasses with dimensions for shafts, heads, hex sockets, and heatsert inserts
- **Washers** -- ISO 7089/7090 metric washers (normal and large) for M1.6 through M64
- **Textures** -- surface texture system with honeycomb, linear stripe, and hex grid patterns; applied to any face with automatic boundary clipping

### Missing Geometries

- **Teardrop** -- 3D-print-friendly hole profile with 45-degree angled top to reduce overhangs and support material
- **Rounded rectangle** -- sketch-based `rrect` with automatic radius clamping
- **Parabolic channel** -- spline-based parabolic channel profile with configurable wall and lip thickness

### Development Tools

- **Caching** -- BREP-based disk cache (`~/.cache/tcqt_cache/`) with a `@cached_workplane` decorator for expensive operations like texture generation
- **Showing** -- VTK-based visualization with optional coordinate axes overlay
- **Batch merging** -- threaded tree-merge for combining large numbers of shapes efficiently

### Workplane Extras

- Polar coordinate movement (`polar_move_to`)
- Center-relative rotation (`rotate_center`)
- Multi-axis alignment (`aligned`, `align_to`)
- `auto_clean` toggle for boolean operations
- `build_dir` support for export paths

## Installation

Requires Python >= 3.11.

```sh
uv add tcqt
```

Or from source:

```sh
git clone <repo-url>
cd tcqt
uv sync
```

## Quick Start

```python
from tcqt import Workplane

# Rounded rectangle with teardrop holes
wp = (
    Workplane("XY")
    .rrect(40, 20, 3)
    .extrude(10)
    .faces(">Z")
    .workplane()
    .teardrop(radius=2.5)
    .cutThruAll()
)
```

```python
from tcqt import cached_workplane, Workplane
from tcqt.texture import HoneycombTexture

# Cached honeycomb texture
@cached_workplane
def textured_panel(cache_key=None):
    panel = Workplane("XY").box(50, 50, 3)
    texture = HoneycombTexture(hex_side_len=3, hex_height_min=0.5, hex_height_max=1.5)
    return panel.texture(texture, cache_key=cache_key)
```

```python
from tcqt.joints import HeatsertJoint
from tcqt.screws import MetricScrews

# Heatsert screw joint
joint = HeatsertJoint(screw=MetricScrews.M3, boss_height=5.0, heatsert_length="6")
part = joint.apply_female(wp, face="Z>", offset=(10, 10))
```
