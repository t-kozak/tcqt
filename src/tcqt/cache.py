import functools
import hashlib
import logging
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, ParamSpec

import cadquery as cq

if TYPE_CHECKING:
    from .workplane import Workplane

P = ParamSpec("P")

_CACHES_DIR = Path(tempfile.gettempdir()) / "tcqt_cache"

_log = logging.getLogger(__name__)


def read_from_cache(cache_key: str | None) -> "Workplane | None":
    """
    Read texture geometry from cache if available.

    Args:
        cache_key: Optional cache key. If None, returns None immediately.

    Returns:
        Cached Workplane if found, None otherwise
    """
    if cache_key is None:
        return None

    cache_file = _CACHES_DIR / f"{cache_key}.brep"

    if not cache_file.exists():
        return None

    _log.debug(f"Loading cached texture from {cache_file}...")
    try:
        from .workplane import Workplane

        # Load cached Workplane using importBrep
        cached_result = cq.importers.importBrep(str(cache_file))
        _log.debug(f"Loaded cached texture from {cache_file}... done")
        # Convert to our custom Workplane type
        return Workplane("XY").newObject([cached_result.val()])
    except Exception as e:
        _log.warning(f"Failed to load cache file {cache_file}: {e}")
        return None


def write_to_cache(cache_key: str | None, texture_geometry: "Workplane") -> None:
    """
    Write texture geometry to cache.

    Args:
        cache_key: Optional cache key. If None, does nothing.
        texture_geometry: The texture geometry to cache
    """
    if cache_key is None:
        return

    cache_file = _CACHES_DIR / f"{cache_key}.brep"

    try:
        # Ensure cache directory exists
        _CACHES_DIR.mkdir(parents=True, exist_ok=True)

        # Save result to cache file using BREP format
        cq.exporters.export(
            exportType="BREP", w=texture_geometry, fname=str(cache_file)
        )
        _log.debug(f"Cached texture saved to {cache_file}")
    except Exception as e:
        _log.warning(f"Failed to save cache file {cache_file}: {e}")


def _make_cache_key(func: Callable[..., "Workplane"], args: tuple, kwargs: dict) -> str:
    name = func.__qualname__
    params_repr = repr((args, sorted(kwargs.items())))
    params_hash = hashlib.sha256(params_repr.encode()).hexdigest()[:16]
    return f"{name}_{params_hash}"


def cached_workplane(func: Callable[P, "Workplane"]) -> Callable[P, "Workplane"]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> "Workplane":
        cache_key = _make_cache_key(func, args, kwargs)
        cached = read_from_cache(cache_key)
        if cached is not None:
            return cached
        result = func(*args, **kwargs)
        write_to_cache(cache_key, result)
        return result

    return wrapper
