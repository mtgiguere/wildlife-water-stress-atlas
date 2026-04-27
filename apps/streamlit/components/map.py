"""
map.py

PyDeck map component builder for the Wildlife Water Stress Atlas.

WHY PYDECK:
-----------
PyDeck (deck.gl) handles large datasets efficiently via WebGL rendering.
With 20,000+ elephant occurrence points and thousands of water polygons,
matplotlib would be slow and Folium would struggle. PyDeck renders
everything on the GPU.

LAYER DESIGN:
-------------
Two layers compose the map:

1. GeoJsonLayer (water) — background context layer showing rivers,
   wetlands, pans, and floodplains. Not interactive — it's reference
   data, not the story.

2. ScatterplotLayer (occurrences) — the story. Each dot is an elephant
   occurrence record. Pickable so users can hover to see year, species,
   and coordinates. Color reflects recency — recent records brighter.

AFRICA VIEW:
------------
Initial view is centered on Africa (lat=0, lon=20) at zoom=3 which
shows the full continent with reasonable detail.
"""

import json

import geopandas as gpd
import pydeck as pdk

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Africa center and zoom — shows full continent comfortably
AFRICA_LATITUDE = 0.0
AFRICA_LONGITUDE = 20.0
AFRICA_ZOOM = 3

# Water layer styling — bright cyan-blue, visible on dark background
WATER_COLOR = [0, 180, 255, 200]

# Occurrence layer styling — warm orange, semi-transparent
OCCURRENCE_COLOR = [255, 140, 0, 200]
OCCURRENCE_RADIUS = 15_000  # 15km radius per dot


# ---------------------------------------------------------------------------
# Layer builders
# ---------------------------------------------------------------------------


def build_water_layer(gdf: gpd.GeoDataFrame) -> list[pdk.Layer]:
    """
    Build PyDeck layers for water sources.

    Returns two layers:
    - GeoJsonLayer for line geometries (rivers)
    - PolygonLayer for polygon geometries (lakes, wetlands, pans)

    Splitting by geometry type gives us explicit fill control over
    polygons which GeoJsonLayer struggles with on dark basemaps.
    """
    simplified = gdf.copy()
    simplified["geometry"] = simplified.geometry.simplify(0.01)
    simplified = simplified[~simplified.geometry.is_empty].copy()

    # Split by geometry type
    lines = simplified[simplified.geometry.geom_type == "LineString"].copy()
    polygons = simplified[simplified.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()

    layers = []

    # River lines
    if not lines.empty:
        geojson = json.loads(lines.to_json())
        layers.append(
            pdk.Layer(
                type="GeoJsonLayer",
                data=geojson,
                get_line_color=WATER_COLOR,
                get_line_width=300,
                pickable=False,
                stroked=True,
                filled=False,
            )
        )

    # Lake/wetland polygons — using PolygonLayer for explicit fill
    if not polygons.empty:
        # PolygonLayer needs coordinates as lists
        polygons["coordinates"] = polygons.geometry.apply(lambda g: list(g.exterior.coords) if g.geom_type == "Polygon" else list(g.geoms[0].exterior.coords))
        records = polygons[["coordinates"]].to_dict("records")

        layers.append(
            pdk.Layer(
                type="PolygonLayer",
                data=records,
                get_polygon="coordinates",
                get_fill_color=WATER_COLOR,
                get_line_color=WATER_COLOR,
                get_line_width=100,
                pickable=False,
                filled=True,
                stroked=True,
                extruded=False,
            )
        )

    return layers


def build_occurrences_layer(gdf: gpd.GeoDataFrame) -> pdk.Layer:
    """
    Build a PyDeck IconLayer for species occurrence points.

    Uses IconLayer to display species-specific emoji icons from Twemoji.
    Each species has its own icon URL in SPECIES_CONFIG — the icon
    automatically changes when the species selector changes.

    The layer IS pickable — users can hover over icons to see
    species, year, and coordinates in a tooltip.

    Args:
        gdf: Occurrences GeoDataFrame with geometry and year columns.
             Can be empty (no records for selected year) — handled
             gracefully by returning a valid layer with no data.

    Returns:
        pdk.Layer configured as an IconLayer.
    """

    if not gdf.empty:
        data = gdf.copy()
        data["longitude"] = data.geometry.x
        data["latitude"] = data.geometry.y
        cols = ["longitude", "latitude", "year"]
        if "species" in data.columns:
            cols.append("species")
        records = data[cols].to_dict("records")
    else:
        records = []

    return pdk.Layer(
        type="ScatterplotLayer",
        data=records,
        get_position=["longitude", "latitude"],
        get_fill_color=OCCURRENCE_COLOR,
        get_radius=OCCURRENCE_RADIUS,
        pickable=True,
        opacity=0.8,
        stroked=True,
        get_line_color=[255, 255, 255, 100],
        get_line_width=200,
    )


def build_deck(
    water_layers: list[pdk.Layer],
    occurrences_layer: pdk.Layer,
) -> pdk.Deck:
    """..."""
    view_state = pdk.ViewState(
        latitude=AFRICA_LATITUDE,
        longitude=AFRICA_LONGITUDE,
        zoom=AFRICA_ZOOM,
        pitch=0,
        bearing=0,
    )

    return pdk.Deck(
        layers=water_layers + [occurrences_layer],
        initial_view_state=view_state,
        tooltip={"text": "Year: {year}\nSpecies: {species}"},
        map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
    )
