import pandas as pd
import geopandas as gpd

def combine_water_layers(
    rivers: gpd.GeoDataFrame,
    lakes: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Combine river and lake layers into a single water layer.
    """
    combined = pd.concat([rivers, lakes], ignore_index=True)

    return gpd.GeoDataFrame(combined, crs="EPSG:4326")


def load_rivers(filepath: str) -> gpd.GeoDataFrame:
    """
    Load river dataset into GeoDataFrame.
    """
    gdf = gpd.read_file(filepath)

    # Ensure CRS is WGS84
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")

    return gdf

def load_lakes(filepath: str) -> gpd.GeoDataFrame:
    """
    Load lake dataset into GeoDataFrame.
    """
    gdf = gpd.read_file(filepath)

    # Ensure CRS is WGS84
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")

    return gdf