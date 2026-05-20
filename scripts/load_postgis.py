from pathlib import Path

import geopandas as gpd
from sqlalchemy import create_engine

from wildlife_water_stress_atlas.config.species import SPECIES_CONFIG

ENGINE = create_engine("postgresql://postgres:atlas123@127.0.0.1:5433/wildlife_atlas")
DATA_DIR = Path("data/processed")


def load_water():
    print("Loading water layer...")
    gdf = gpd.read_file(DATA_DIR / "water_africa_simplified.gpkg")
    gdf.to_postgis("water_sources", ENGINE, if_exists="replace", index=False)
    print(f"Done — {len(gdf)} features loaded")


def load_occurrences():
    for scientific_name, cfg in SPECIES_CONFIG.items():
        print(f"Loading {cfg['common_name']}...")
        gdf = gpd.read_file(DATA_DIR / cfg["gbif_cache_file"])
        table = f"occurrences_{scientific_name.lower().replace(' ', '_')}"
        gdf.to_postgis(table, ENGINE, if_exists="replace", index=False)
        print(f"  Done — {len(gdf)} records")


def build_indexes():
    print("Building GIST indexes...")
    with ENGINE.connect() as conn:
        conn.execute("CREATE INDEX IF NOT EXISTS ON water_sources USING GIST(geometry);")
        for scientific_name in SPECIES_CONFIG:
            table = f"occurrences_{scientific_name.lower().replace(' ', '_')}"
            conn.execute(f"CREATE INDEX IF NOT EXISTS ON {table} USING GIST(geometry);")
    print("Done!")


if __name__ == "__main__":
    load_water()
    load_occurrences()
