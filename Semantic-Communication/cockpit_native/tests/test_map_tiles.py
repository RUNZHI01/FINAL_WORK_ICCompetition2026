from __future__ import annotations

from pathlib import Path
import unittest

from cockpit_native.map_tiles import (
    format_arcgis_cache_relative_path,
    resolve_arcgis_cache_tile_path,
)


class ArcGisCacheTilePathTest(unittest.TestCase):
    def test_format_arcgis_cache_relative_path_matches_reference_layout(self) -> None:
        self.assertEqual(
            format_arcgis_cache_relative_path(13, 0x194C, 0x0D18),
            "L13/R00000D18/C0000194C.png",
        )

    def test_format_arcgis_cache_relative_path_honors_requested_extension(self) -> None:
        self.assertEqual(
            format_arcgis_cache_relative_path(8, 0xCA, 0x69, image_format="jpg"),
            "L08/R00000069/C000000CA.jpg",
        )

    def test_resolve_arcgis_cache_tile_path_appends_relative_layout(self) -> None:
        tile_path = resolve_arcgis_cache_tile_path(
            Path("/tmp/ui_ref_mylocation/bin/dianzi_gaode_ArcgisServerTiles/_alllayers"),
            zoom=13,
            x=0x194C,
            y=0x0D18,
        )

        self.assertEqual(
            tile_path,
            Path("/tmp/ui_ref_mylocation/bin/dianzi_gaode_ArcgisServerTiles/_alllayers/L13/R00000D18/C0000194C.png"),
        )


if __name__ == "__main__":
    unittest.main()
