from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from cockpit_native.qt_app import (
    available_qtlocation_providers,
    apply_repo_runtime_env,
    build_launch_options,
    build_runtime_theme_plan,
    normalize_map_backend,
    normalize_map_provider,
    normalize_map_tile_mode,
    resolve_default_world_map_backdrop,
    resolve_font_family,
    resolve_repo_runtime_cache_root,
    resolve_optional_repo_path,
    resolve_qtlocation_plugin_name,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class QtAppLaunchOptionsTest(unittest.TestCase):
    def test_normalize_map_backend_accepts_known_values(self) -> None:
        self.assertEqual(normalize_map_backend("svg"), "svg")
        self.assertEqual(normalize_map_backend("QtLocation"), "qtlocation")
        self.assertEqual(normalize_map_backend(" canvas "), "canvas")

    def test_normalize_map_backend_falls_back_to_auto(self) -> None:
        self.assertEqual(normalize_map_backend(None), "auto")
        self.assertEqual(normalize_map_backend("mapbox"), "auto")

    def test_normalize_map_provider_accepts_known_values(self) -> None:
        self.assertEqual(normalize_map_provider("osm"), "osm")
        self.assertEqual(normalize_map_provider(" OSM "), "osm")

    def test_normalize_map_provider_falls_back_to_auto(self) -> None:
        self.assertEqual(normalize_map_provider(None), "auto")
        self.assertEqual(normalize_map_provider("mymap"), "auto")

    def test_normalize_map_tile_mode_accepts_known_values(self) -> None:
        self.assertEqual(normalize_map_tile_mode("online"), "online")
        self.assertEqual(normalize_map_tile_mode(" LOCAL_ARCGIS_CACHE "), "local_arcgis_cache")

    def test_normalize_map_tile_mode_falls_back_to_auto(self) -> None:
        self.assertEqual(normalize_map_tile_mode(None), "auto")
        self.assertEqual(normalize_map_tile_mode("tilebox"), "auto")

    def test_resolve_optional_repo_path_returns_file_uri(self) -> None:
        resolved = resolve_optional_repo_path(
            "cockpit_native/qml/assets/world-map-backdrop.svg",
            project_root=PROJECT_ROOT,
        )

        self.assertTrue(resolved.startswith("file://"))
        self.assertIn("/cockpit_native/qml/assets/world-map-backdrop.svg", resolved)

    def test_build_launch_options_reads_map_env(self) -> None:
        options = build_launch_options(
            project_root=PROJECT_ROOT,
            software_render=True,
            env={
                "COCKPIT_NATIVE_MAP_BACKEND": "svg",
                "COCKPIT_NATIVE_MAP_PROVIDER": "osm",
                "COCKPIT_NATIVE_MAP_TILE_ROOT": "/tmp/ui_ref_mylocation/bin/dianzi_gaode_ArcgisServerTiles/_alllayers",
                "COCKPIT_NATIVE_WORLD_MAP_BACKDROP": "cockpit_native/qml/assets/world-map-backdrop.svg",
            },
        )

        self.assertTrue(options["softwareRender"])
        self.assertEqual(options["mapBackend"], "svg")
        self.assertEqual(options["mapProvider"], "osm")
        self.assertEqual(options["mapTileMode"], "local_arcgis_cache")
        self.assertTrue(str(options["mapTileRoot"]).startswith("file://"))
        self.assertTrue(str(options["worldMapBackdropSource"]).startswith("file://"))

    def test_build_launch_options_defaults_to_repo_backdrop(self) -> None:
        options = build_launch_options(project_root=PROJECT_ROOT, env={})
        self.assertIn("/cockpit_native/qml/assets/world-map-backdrop.svg", str(options["worldMapBackdropSource"]))

    def test_resolve_default_world_map_backdrop_uses_repo_asset(self) -> None:
        resolved = resolve_default_world_map_backdrop(PROJECT_ROOT)
        self.assertTrue(resolved.startswith("file://"))
        self.assertIn("/cockpit_native/qml/assets/world-map-backdrop.svg", resolved)

    def test_resolve_repo_runtime_cache_root_is_repo_local(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            cache_root = Path(resolve_repo_runtime_cache_root(project_root))
            self.assertEqual(
                cache_root,
                project_root / "cockpit_native" / "runtime" / "xdg_cache",
            )
            self.assertTrue(cache_root.is_dir())

    def test_apply_repo_runtime_env_sets_repo_cache_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            env = {}
            apply_repo_runtime_env(env, project_root=project_root)
            self.assertEqual(
                env["XDG_CACHE_HOME"],
                str(project_root / "cockpit_native" / "runtime" / "xdg_cache"),
            )

            preserved_env = {"XDG_CACHE_HOME": "/tmp/custom-cache"}
            apply_repo_runtime_env(preserved_env, project_root=project_root)
            self.assertEqual(preserved_env["XDG_CACHE_HOME"], "/tmp/custom-cache")

    def test_resolve_qtlocation_plugin_name_prefers_osm(self) -> None:
        self.assertEqual(
            resolve_qtlocation_plugin_name("auto", available_providers=["itemsoverlay", "osm"]),
            "osm",
        )
        self.assertEqual(
            resolve_qtlocation_plugin_name("osm", available_providers=["itemsoverlay", "osm"]),
            "osm",
        )
        self.assertEqual(
            resolve_qtlocation_plugin_name("auto", available_providers=[]),
            "",
        )

    def test_available_qtlocation_providers_returns_strings(self) -> None:
        providers = available_qtlocation_providers()
        self.assertTrue(all(isinstance(provider, str) for provider in providers))

    def test_resolve_font_family_prefers_first_available_match(self) -> None:
        resolved = resolve_font_family(
            ["Noto Sans CJK SC", "Ubuntu Sans"],
            available_families=["Ubuntu Sans", "DejaVu Sans"],
            fallback_family="Sans Serif",
        )
        self.assertEqual(resolved, "Ubuntu Sans")

    def test_build_runtime_theme_plan_contains_palette_entries(self) -> None:
        theme_plan = build_runtime_theme_plan()
        self.assertEqual(theme_plan["themeProfile"], "native_cockpit_runtime_v2")
        self.assertIn("sceneTop", theme_plan["themePalette"])
        self.assertIn("accentIce", theme_plan["themePalette"])


if __name__ == "__main__":
    unittest.main()
