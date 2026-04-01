import geopandas as gpd


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