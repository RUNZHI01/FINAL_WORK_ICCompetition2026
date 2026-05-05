from __future__ import annotations

from pathlib import Path


def format_arcgis_cache_relative_path(zoom: int, x: int, y: int, *, image_format: str = "png") -> str:
    """Match the ArcGIS cache naming used by the MyQtLocation reference plugin."""
    resolved_format = str(image_format or "png").strip().lower() or "png"
    return f"L{int(zoom):02d}/R{int(y):08X}/C{int(x):08X}.{resolved_format}"


def resolve_arcgis_cache_tile_path(
    tile_root: str | Path,
    *,
    zoom: int,
    x: int,
    y: int,
    image_format: str = "png",
) -> Path:
    root_path = Path(tile_root).expanduser().resolve()
    return root_path / format_arcgis_cache_relative_path(zoom, x, y, image_format=image_format)

