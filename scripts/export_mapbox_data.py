import json

import geopandas as gpd

from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG


def export_water(input_path, output_path):
    gdf = gpd.read_file(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(output_path, driver="GeoJSON")


def export_occurrences(input_path, output_path):
    gdf = gpd.read_file(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cols = [c for c in ["species", "year"] if c in gdf.columns]
    gdf[cols + ["geometry"]].to_file(output_path, driver="GeoJSON")


def export_species_config(output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(SPECIES_CONFIG, default=lambda o: list(o) if isinstance(o, set) else str(o)))


def export_all(data_dir, output_dir):
    export_water(
        data_dir / "water_africa_simplified.gpkg",
        output_dir / "water.geojson",
    )

    for _scientific_name, cfg in SPECIES_CONFIG.items():
        export_occurrences(
            data_dir / cfg["gbif_cache_file"],
            output_dir / f"occurrences_{cfg['gbif_cache_file'].replace('.gpkg', '.geojson')}",
        )

    export_species_config(output_dir / "species_config.json")


def main():
    from pathlib import Path
    export_all(
        data_dir=Path("data/processed"),
        output_dir=Path("apps/mapbox/data"),
    )

# pragma: no cover — __main__ block is an entry point, not unit-testable.
# Covered implicitly by running the script directly.
if __name__ == "__main__": # pragma: no cover
    main()